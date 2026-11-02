"""Real history HTTP serialization for the frontend contract; guarded runner only.

No checked-in response fixtures: the Node test invokes this file to capture the
current FastAPI response bytes/headers. All issuer facts below are synthetic.
"""
from datetime import date
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql

from app import config, database, freshness_service, main
from app import revenue_scope_authorizations as auth, sec_evidence_adapter as adapter
from app.models import Company, CompanyRefreshState, FinancialFact
from test_financial_insights import COMPANY, fact


BALANCE = ("cash_and_equivalents", "total_assets", "total_liabilities")
FLOW = ("operating_cash_flow", "capital_expenditures", "free_cash_flow")
SLOTS = [(name, "instant") for name in BALANCE] + [
    (name, kind) for kind in ("half_year", "nine_months") for name in FLOW]
EXACT = "9007199254740993.123456789"
CAPEX = "10.000000001"
FCF = "9007199254740983.123456788"
VALUES = dict(zip(BALANCE, (EXACT, "19007199254740993.123456789", "10000000000000000.000000001")))
VALUES.update(operating_cash_flow=EXACT, capital_expenditures=CAPEX, free_cash_flow=FCF)
CONCEPTS = dict(zip(BALANCE, ("CashAndCashEquivalentsAtCarryingValue", "Assets", "Liabilities")))
CONCEPTS.update(operating_cash_flow="NetCashProvidedByUsedInOperatingActivities",
                capital_expenditures="PaymentsToAcquirePropertyPlantAndEquipment")


def forbidden(*args, **kwargs):
    raise AssertionError("Contract tests allow only fake read-only sessions")


def facts_for(scenario):
    rows = []
    for year in (2024, 2025):
        for name, kind in SLOTS:
            if name == "free_cash_flow":
                continue  # Derived by the actual engine, never supplied as a fact.
            if scenario == "empty" or (scenario == "sparse" and (
                    name == "cash_and_equivalents" or year == 2025 and name in {"total_liabilities", "capital_expenditures"})):
                continue
            end = date(year, {"instant": 12, "half_year": 6, "nine_months": 9}[kind],
                       31 if kind == "instant" else 30)
            rows.append(fact(CONCEPTS[name], VALUES[name], year, id=len(rows)+1,
                period_start=None if kind == "instant" else date(year, 1, 1), period_end=end,
                period_type=kind, form="10-K" if kind == "instant" else "10-Q",
                fiscal_year=year+1, fiscal_period="FY" if kind == "instant" else "Q3"))
    return rows


class ReadOnlyFacts:
    """Accept only the real loader's three SELECTs and transaction setup."""
    def __init__(self, rows, pin, close_error=False):
        self.rows, self.pin, self.close_error = rows, pin, close_error
        self.events, self.sql = [], []
        self.link = Mock()

    def get_bind(self):
        return SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

    def connection(self):
        return self.link

    def execute(self, statement):
        assert str(statement) == "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
        self.events.append("readonly")

    def select(self, statement, entity, event):
        assert statement.is_select and statement.column_descriptions[0]["entity"] is entity
        compiled = statement.compile(dialect=postgresql.dialect())
        assert list(compiled.params.values()) == [COMPANY.cik if entity is FinancialFact else COMPANY.ticker]
        self.sql.append(str(compiled))
        self.events.append(event)

    def scalar(self, statement):
        entity = statement.column_descriptions[0]["entity"]
        if entity is CompanyRefreshState:
            self.select(statement, entity, "version")
            return self.pin
        self.select(statement, Company, "company")
        return COMPANY

    def scalars(self, statement):
        self.select(statement, FinancialFact, "facts")
        return self.rows

    def close(self):
        self.events.append("close")
        if self.close_error:
            raise RuntimeError("synthetic private cleanup diagnostic")

    def invalidate(self):
        self.events.append("invalidate")

    commit = rollback = add = add_all = delete = flush = forbidden


@pytest.fixture(autouse=True)
def restricted_offline(monkeypatch):
    monkeypatch.setattr(config, "_SERVER_PROFILE", config.ServerProfile("sec_readonly", True))
    for owner, name in ((database.engine, "connect"), (database, "SessionLocal"),
                        (main, "HttpSessionLocal"), (main, "InsightsSessionLocal")):
        monkeypatch.setattr(owner, name, forbidden)
    monkeypatch.setattr(freshness_service, "schema_ready", lambda _: True)

    def no_authorization_evidence(session, cik, rows):
        # The offline runner blocks artifact loading. Stub only this unused
        # dependency, with empty current registries asserted, never financials.
        assert cik == COMPANY.cik and rows is not None
        assert not auth.REVENUE_SELECTION_AUTHORIZATIONS
        assert not auth.DENOMINATOR_AUTHORIZATIONS and not adapter.PRODUCTION_EVIDENCE_POLICIES
        session.events.append("empty_authorization_evidence")
        return ()
    monkeypatch.setattr(adapter, "load_production_evidence", no_authorization_evidence)


def capture(monkeypatch, metric, kind, scenario="full", pin=0, stale=False, close_error=False):
    session = ReadOnlyFacts(facts_for(scenario), pin, close_error)
    factory = Mock(return_value=session)
    monkeypatch.setattr(main, "HttpSessionLocal", factory)
    expected = pin+1 if stale else pin
    path = f"/companies/{COMPANY.ticker}/financials/metrics/{metric}?period={kind}&limit=12"
    with TestClient(main.app) as client:
        reply = client.get(path, headers={"X-FinLens-Data-Version": str(expected)})
    assert factory.call_count == 1
    assert reply.headers["X-FinLens-Data-Version"] == str(pin)
    assert reply.headers["Cache-Control"] == "no-store"
    assert session.events[0] == "readonly" and session.events.count("close") == 1
    if stale:
        assert reply.status_code == 409 and reply.headers["X-FinLens-Error-Code"] == "DATA_VERSION_CHANGED"
        assert session.events == ["readonly", "version", "close"]
    elif close_error:
        assert reply.status_code == 500 and "private" not in reply.text
        assert session.events[-2:] == ["close", "invalidate"]
        session.link.invalidate.assert_called_once_with()
    else:
        assert reply.status_code == 200, reply.text
        assert session.events == ["readonly", "version", "company", "facts", "empty_authorization_evidence", "close"]
        assert_metric(reply.json(), metric, kind, scenario)
    return dict(metric=metric, kind=kind, scenario=scenario, publication=pin, request_pin=expected,
                path=path, status=reply.status_code, headers=list(reply.headers.multi_items()), body=reply.text)


def assert_metric(body, metric, kind, scenario):
    assert (body["ticker"], body["company_cik"], body["metric"], body["requested_period"], body["unit"]) == (
        COMPANY.ticker, COMPANY.cik, metric, kind, "USD")
    if scenario == "empty" or scenario == "sparse" and metric == "cash_and_equivalents":
        assert body["status"] == "unavailable" and body["reason"] and body["history"] == []
        return
    assert body["status"] == "available" and body["reason"] is None
    assert len(body["history"]) == (1 if scenario == "sparse" and metric in {"total_liabilities", "capital_expenditures"} else 2)
    for point in body["history"]:
        period = point["period"]
        assert period["kind"] == kind
        assert period["end"] in [f"{year}-" + {"instant": "12-31", "half_year": "06-30", "nine_months": "09-30"}[kind] for year in (2024, 2025)]
        assert period["start"] == (None if kind == "instant" else period["end"][:4] + "-01-01")
        assert period["fiscal_year"] is None and period["fiscal_period"] is None
        missing = scenario == "sparse" and metric == "free_cash_flow" and period["end"].startswith("2025")
        if missing:
            assert point["status"] == "unavailable" and point["reason"] and point["value"] is None
            assert point["inputs"] == point["provenance"] == []
            continue
        assert point["status"] == "available" and point["value"] == VALUES[metric]
        assert point["reason"] is None
        for source in point["provenance"]:
            assert source["value"] == VALUES[source["canonical_metric"]]
            assert source["period_start"] == period["start"] and source["period_end"] == period["end"]
            assert source["filed"] == f"{int(period['end'][:4])+1}-02-01"
            assert source["source_fiscal_year"] == int(period["end"][:4])+1
            assert source["sec_url"].endswith(source["accession_number"] + "-index.html")
        if metric == "free_cash_flow":
            assert point["formula"] == "operating_cash_flow - capital_expenditures"
            assert len(point["inputs"]) == len(point["provenance"]) == 2
            for operand in point["inputs"]:
                source, = [s for s in point["provenance"] if s["canonical_metric"] == operand["role"]]
                assert operand["metric"] == source["canonical_metric"]
                assert operand["value"] == source["value"] and operand["fact_ids"] == [source["fact_id"]]
                assert operand["period"] == period
        else:
            assert point["formula"] is None and point["inputs"] == [] and len(point["provenance"]) == 1


MATRIX = [(scenario, pin, metric, kind) for scenario, pin in
          (("full", 0), ("full", 7), ("sparse", 7), ("empty", 0)) for metric, kind in SLOTS]


@pytest.mark.parametrize("scenario,pin,metric,kind", MATRIX)
def test_real_history_response(monkeypatch, scenario, pin, metric, kind):
    capture(monkeypatch, metric, kind, scenario, pin)


@pytest.mark.parametrize("pin", [0, 7])
@pytest.mark.parametrize("metric,kind", [(BALANCE[0], "instant"), (FLOW[0], "half_year"), (FLOW[2], "nine_months")])
def test_stale_pin_rejects_before_loader_and_closes(monkeypatch, pin, metric, kind):
    capture(monkeypatch, metric, kind, pin=pin, stale=True)


def test_cleanup_failure_cannot_publish_success(monkeypatch):
    capture(monkeypatch, FLOW[2], "half_year", close_error=True)


def test_export_current_backend_responses(monkeypatch):
    target = os.environ.get("FINLENS_HISTORY_CONTRACT_OUTPUT")
    capabilities = TestClient(main.app).get("/capabilities")
    assert capabilities.status_code == 200
    assert capabilities.json() == dict(research_mode=True, server_profile="sec_readonly",
        ai_analysis_configured=False, ai_analysis_enabled=False, filing_research_enabled=False)
    replies = [capture(monkeypatch, metric, kind, scenario, pin) for scenario, pin, metric, kind in MATRIX]
    replies += [capture(monkeypatch, metric, kind, pin=pin, stale=True) for pin in (0, 7)
                for metric, kind in ((BALANCE[0], "instant"), (FLOW[0], "half_year"), (FLOW[2], "nine_months"))]
    replies.append(capture(monkeypatch, FLOW[2], "half_year", close_error=True))
    assert len(replies) == 43
    if target:
        Path(target).write_text(json.dumps(dict(company=vars(COMPANY), capabilities=capabilities.json(),
            values=VALUES, replies=replies)), encoding="utf-8")
