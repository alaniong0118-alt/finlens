"""Detached admitted observations only; run through run_financial_insights.py."""
from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal, localcontext
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app import main, freshness_service
from app.financial_metric_engine import BALANCE_SHEET_RATIOS, FinancialMetricEngine
from app.financial_metrics_service import FinancialMetrics

COMPANY = SimpleNamespace(cik="0000000001", ticker="TEST", name="Synthetic ratio company")
LIABILITIES = "total_liabilities_to_total_assets"
CASH = "cash_and_equivalents_to_total_liabilities"


def facts(liabilities="100", assets="300", cash="10"):
    rows = []
    for concept, value in [("Liabilities", liabilities), ("Assets", assets), ("CashAndCashEquivalentsAtCarryingValue", cash)]:
        if value is None:
            continue
        rows.append(SimpleNamespace(id=len(rows)+1, company_cik=COMPANY.cik, metric=concept,
            value=Decimal(value), unit="USD", period_start=None, period_end=date(2025, 12, 31),
            period_type="instant", fiscal_year=2025, fiscal_period="FY", frame=None,
            form="10-K", filed=date(2026, 2, 1), accession_number="0000000001-26-000001",
            source="SEC Company Facts API: "+concept, created_at=datetime(2026, 2, 1)))
    return rows


def ratios(rows=None):
    return FinancialMetrics(COMPANY, facts() if rows is None else rows).summary(include_balance_ratios=True).balance_sheet_ratios


def test_decimal_precision_complete_lineage_and_opt_in_serialization():
    rows = facts()
    with localcontext() as context:
        context.prec = 4
        model = FinancialMetrics(COMPANY, rows)
        summary = model.summary(include_balance_ratios=True)
    point = summary.balance_sheet_ratios[LIABILITIES]
    assert point.value == Decimal("0.3333333333333333333333333333")
    assert point.formula == "total_liabilities / total_assets" and point.period.kind == "instant"
    assert point.period.end == date(2025, 12, 31) and point.period.start is None
    assert [i.role for i in point.inputs] == ["total_liabilities", "total_assets"]
    assert [i.fact_ids for i in point.inputs] == [[1], [2]]
    assert [s.fact_id for s in point.provenance] == [1, 2]
    assert all(i.period == point.period and i.unit == "USD" for i in point.inputs)
    assert all(s.company_cik == COMPANY.cik and s.period_end == point.period.end for s in point.provenance)
    assert summary.model_dump(mode="json")["balance_sheet_ratios"][LIABILITIES]["value"] == str(point.value)
    assert "balance_sheet_ratios" not in model.summary().model_dump(mode="json")
    assert "balance_sheet_ratios" not in model.annual_comparison().model_dump(mode="json")
    assert len(summary.metrics) == 15 and len(BALANCE_SHEET_RATIOS) == 2


def test_dates_do_not_follow_revenue_or_restrict_to_its_interval():
    rows = facts()
    revenue = SimpleNamespace(**vars(rows[0]));revenue.id=9;revenue.metric="Revenues"
    revenue.source="SEC Company Facts API: Revenues";revenue.value=Decimal("777")
    revenue.period_start=date(2024, 1, 1);revenue.period_end=date(2024, 12, 31)
    model = FinancialMetrics(COMPANY, [*rows, revenue])
    summary = model.summary("annual", include_balance_ratios=True)
    assert summary.period.end == date(2024, 12, 31)
    assert summary.metrics["total_assets"].status == "unavailable"  # old contract unchanged
    assert summary.balance_sheet_ratios[LIABILITIES].period.end == date(2025, 12, 31)
    assert summary.balance_sheet_ratios[LIABILITIES].status == "available"
    assert FinancialMetrics(COMPANY, rows).summary().period is None
    assert ratios(rows)[CASH].status == "available"  # no revenue needed


@pytest.mark.parametrize("target,field,value,reason", [
    ("Liabilities", "unit", "EUR", "currencies"),
    ("Assets", "unit", "USD/shares", "currencies"),
    ("Assets", "company_cik", "0000000002", "No admitted USD"),
    ("Assets", "period_end", date(2025, 9, 30), "other dates"),
    ("Liabilities", "accession_number", "0000000001-26-000002", "filing scopes"),
    ("Assets", "form", "10-K/A", "filing scopes"),
    ("Assets", "filed", date(2026, 2, 2), "vintages"),
    ("Assets", "source", "untrusted Assets", "unsupported sources"),
    ("Assets", "value", Decimal("0"), "denominator"),
    ("Assets", "value", Decimal("-1"), "denominator"),
    ("Liabilities", "value", Decimal("-1"), "numerator"),
])
def test_incompatible_or_invalid_inputs_are_explanatory(target, field, value, reason):
    rows = facts()
    setattr(next(r for r in rows if r.metric == target), field, value)
    point = ratios(rows)[LIABILITIES]
    assert point.status == "unavailable" and point.value is None and reason in point.reason
    assert point.provenance == point.inputs == [] and point.formula == "total_liabilities / total_assets"


@pytest.mark.parametrize("cash,liabilities,status,value", [("0", "100", "available", "0"), ("-1", "100", "unavailable", None), ("10", "0", "unavailable", None), ("10", "-1", "unavailable", None)])
def test_cash_zero_is_valid_but_negative_or_nonpositive_denominator_refuses(cash, liabilities, status, value):
    point = ratios(facts(cash=cash, liabilities=liabilities))[CASH]
    assert point.status == status and point.value == (Decimal(value) if value is not None else None)


@pytest.mark.parametrize("missing", ["liabilities", "assets", "cash"])
def test_missing_operands(missing):
    points = ratios(facts(**{missing: None}))
    name = CASH if missing == "cash" else LIABILITIES
    assert points[name].status == "unavailable" and points[name].reason
    assert all(p.value is None for p in ratios([]).values())


def test_latest_date_does_not_silently_fall_back_to_older_matching_pair():
    rows = facts()
    newer = SimpleNamespace(**vars(rows[0]));newer.id=8;newer.period_end=date(2026, 3, 31);newer.filed=date(2026, 5, 1)
    points = ratios([*rows, newer])
    assert points[LIABILITIES].period.end == date(2026, 3, 31)
    assert points[LIABILITIES].status == "unavailable" and "2026-03-31" in points[LIABILITIES].reason


def test_conflicting_selected_scope_refuses_and_order_does_not_change_result():
    rows = facts()
    conflict = SimpleNamespace(**vars(rows[1]));conflict.id=9;conflict.value=Decimal("301")
    rows.append(conflict)
    assert ratios(rows)[LIABILITIES].status == "unavailable"
    assert "Conflicting" in ratios(rows)[LIABILITIES].reason
    assert ratios(rows) == ratios(list(reversed(rows)))


def test_older_alternative_does_not_conflict_with_a_matching_selected_vintage():
    rows=facts();older=SimpleNamespace(**vars(rows[1]));older.id=9;older.value=Decimal("250")
    older.filed=date(2026,1,15);older.accession_number="0000000001-26-000002"
    point=ratios([*rows,older])[LIABILITIES]
    assert point.status=="available" and [s.fact_id for s in point.provenance]==[1,2]
    assert [s.fact_id for s in point.alternatives]==[9]


def test_captured_sources_do_not_reread_mutated_rows():
    rows=facts();model=FinancialMetrics(COMPANY, rows)
    rows[0].value=Decimal("999");rows[0].accession_number="0000000001-26-000009"
    point=model.summary(include_balance_ratios=True).balance_sheet_ratios[LIABILITIES]
    assert point.inputs[0].value==100 and point.provenance[0].value==100
    assert point.provenance[0].accession_number=="0000000001-26-000001"


def test_engine_rejects_cross_company_projection_even_with_eligible_metric():
    model=FinancialMetrics(COMPANY,facts())
    observations=list(model._engine.observations)
    original=observations[0];projection=dict(original.source_projection);projection["company_cik"]="0000000002"
    observations[0]=replace(original,source_projection=tuple(projection.items()))
    result=FinancialMetricEngine(tuple(observations),model._engine.permissions).balance_sheet_ratios(COMPANY.cik)
    assert result[LIABILITIES].status=="unavailable" and "same company" in result[LIABILITIES].reason


def test_projection_values_cannot_disagree_and_unsupported_adapter_fails_closed():
    model=FinancialMetrics(COMPANY,facts());observations=list(model._engine.observations)
    original=observations[0];projection=dict(original.source_projection);projection["value"]=Decimal("999")
    observations[0]=replace(original,source_projection=tuple(projection.items()))
    assert FinancialMetricEngine(tuple(observations),model._engine.permissions).balance_sheet_ratios(COMPANY.cik)[LIABILITIES].status=="unavailable"
    assert FinancialMetricEngine(model._engine.observations,object()).balance_sheet_ratios(COMPANY.cik)[LIABILITIES].status=="unavailable"


def test_zero_liabilities_numerator_and_proportions_above_one_have_no_score_threshold():
    assert ratios(facts(liabilities="0"))[LIABILITIES].value==0
    assert ratios(facts(liabilities="600",assets="300"))[LIABILITIES].value==2


@pytest.mark.parametrize("pin", [0, 7])
def test_actual_summary_route_opt_in_preserves_pin_and_readonly_cleanup(monkeypatch,pin):
    session=Mock();session.get_bind.return_value.dialect.name="postgresql";session.scalar.return_value=pin
    monkeypatch.setattr(main,"HttpSessionLocal",lambda:session)
    monkeypatch.setattr(freshness_service,"schema_ready",lambda _:True)
    loader=Mock(return_value=FinancialMetrics(COMPANY,facts()))
    monkeypatch.setattr(main,"load_financial_metrics",loader)
    with TestClient(main.app) as client:
        response=client.get("/companies/TEST/financials/summary?period=quarter",headers={"X-FinLens-Data-Version":str(pin)})
    assert response.status_code==200 and response.headers["X-FinLens-Data-Version"]==str(pin)
    assert response.json()["balance_sheet_ratios"][LIABILITIES]["value"]=="0.3333333333333333333333333333"
    # Existing read_session closes its uncommitted transaction; do not invent
    # an explicit rollback call or claim native PostgreSQL proof from a mock.
    assert session.close.called and not session.commit.called
    assert any("READ ONLY" in str(call.args[0]) for call in session.execute.call_args_list)


def test_stale_pin_never_loads_ratios(monkeypatch):
    session=Mock();session.get_bind.return_value.dialect.name="postgresql";session.scalar.return_value=7
    monkeypatch.setattr(main,"HttpSessionLocal",lambda:session)
    monkeypatch.setattr(freshness_service,"schema_ready",lambda _:True)
    loader=Mock(side_effect=AssertionError("Stale request must not calculate"));monkeypatch.setattr(main,"load_financial_metrics",loader)
    with TestClient(main.app) as client:
        response=client.get("/companies/TEST/financials/summary",headers={"X-FinLens-Data-Version":"0"})
    assert response.status_code==409 and not loader.called and session.close.called
