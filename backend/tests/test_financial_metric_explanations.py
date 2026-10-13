"""Derived failure explanations and real answer serialization without database I/O."""
from datetime import date, datetime, timedelta
from decimal import Decimal
import socket
from types import SimpleNamespace

import pytest
from sqlalchemy.engine import Engine

from app import aapl_net_margin_activation as activation
from app import revenue_scope_authorizations as auth, sec_evidence_adapter as evidence
from app.financial_metric_registry import METRICS, REVENUE_EQUIVALENCES
from app.financial_metric_schemas import FinancialPeriod, NormalizedMetric
from app.financial_metrics_service import FinancialMetrics
from app.models import FinancialFact
from app.research_answer_service import (
    ResearchAnswer, recognize_operation, resolve_answer, resolve_historical_answer,
)


COMPANY = SimpleNamespace(cik="0000000001", ticker="TEST", name="Fixture company")
PERIOD = FinancialPeriod(kind="quarter", start=date(2025, 1, 1), end=date(2025, 3, 31))
CUSTOMER = "RevenueFromContractWithCustomerExcludingAssessedTax"
MISSING = "No compatible stored SEC fact for this period, concept and unit."
AMBIGUOUS = "Incompatible revenue scopes; no unambiguous canonical observation."
PREFIX = "Missing or invalid compatible inputs. "


@pytest.fixture(autouse=True)
def no_io_or_activation(monkeypatch):
    def inactive():
        assert auth.REVENUE_SELECTION_AUTHORIZATIONS == ()
        assert auth.DENOMINATOR_AUTHORIZATIONS == ()
        assert auth.AUTHORIZATION_WITHDRAWALS == ()
        assert evidence.PRODUCTION_EVIDENCE_POLICIES == ()
        assert REVENUE_EQUIVALENCES == frozenset()
        assert activation._ACTIVATION_ENABLED is False

    def forbidden(*args, **kwargs):
        pytest.fail("Database/network access forbidden in explanation regressions")

    inactive()
    monkeypatch.setattr(Engine, "connect", forbidden)
    monkeypatch.setattr(Engine, "raw_connection", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr("app.sec_client._sec_get", forbidden)
    yield
    inactive()


def fact(number, concept="Revenues", value="100", start="2025-01-01", end="2025-03-31"):
    start, end = date.fromisoformat(start), date.fromisoformat(end)
    return FinancialFact(
        id=number, company_cik=COMPANY.cik, metric=concept, value=Decimal(value), unit="USD",
        period_start=start, period_end=end, period_type="quarter", fiscal_year=end.year,
        fiscal_period="Q1", frame=None, form="10-K" if (end-start).days > 300 else "10-Q",
        filed=end + timedelta(days=30), accession_number=f"{COMPANY.cik}-{end.year % 100:02d}-000001",
        source=f"SEC Company Facts API: {concept}", created_at=datetime(2026, 1, 1),
    )


def assert_unavailable(point, metric, period):
    assert point.status == "unavailable" and point.value is None
    assert point.period == period and point.unit == METRICS[metric].unit
    assert point.formula == METRICS[metric].formula
    assert point.provenance == point.alternatives == point.inputs == []
    assert point.revenue_basis is None and point.scope_authorization is None
    assert NormalizedMetric.model_validate_json(point.model_dump_json()) == point


@pytest.mark.parametrize("metric,names,roles,labels", [
    ("free_cash_flow", ("operating_cash_flow", "capital_expenditures"),
     ("operating_cash_flow", "capital_expenditures"), ("Operating cash flow", "Capital expenditures")),
    ("gross_margin", ("gross_profit", "revenue"), ("gross_profit", "revenue"), ("Gross profit", "Revenue")),
    ("operating_margin", ("operating_income", "revenue"), ("operating_income", "revenue"), ("Operating income", "Revenue")),
    ("net_margin", ("net_income", "revenue"), ("net_income", "revenue"), ("Net income", "Revenue")),
    ("revenue_growth_yoy", ("revenue", "revenue"), ("current", "prior"), ("Current revenue", "Prior revenue")),
])
@pytest.mark.parametrize("failed", [(0,), (1,), (0, 1)])
def test_failed_operands_keep_roles_reasons_and_order(metric, names, roles, labels, failed):
    service = FinancialMetrics(COMPANY, [])
    reasons = ("First operand has no compatible local observation.", "Second operand has ambiguous scope.")
    operands = [NormalizedMetric(metric=name, unit=METRICS[name].unit, status="available",
                                 value=Decimal("100"), period=PERIOD) for name in names]
    for index in failed:
        operands[index] = service.missing(names[index], reasons[index], PERIOD)
    before = [p.model_dump(mode="json") for p in operands]
    point = service.calculate(metric, operands, PERIOD, roles)
    assert point.reason == PREFIX + " ".join(f"{labels[i]}: {reasons[i]}" for i in failed)
    assert_unavailable(point, metric, PERIOD)
    assert [p.model_dump(mode="json") for p in operands] == before


@pytest.mark.parametrize("reason", [None, ""])
def test_missing_child_reason_has_neutral_fallback(reason):
    service = FinancialMetrics(COMPANY, [])
    operands = [service.missing("net_income", reason, PERIOD), service.missing("revenue", AMBIGUOUS, PERIOD)]
    point = service.calculate("net_margin", operands, PERIOD, ["net_income", "revenue"])
    assert point.reason == PREFIX + "Net income: No failure reason supplied. Revenue: " + AMBIGUOUS
    assert_unavailable(point, "net_margin", PERIOD)


def test_not_applicable_operand_keeps_parent_unavailable():
    service = FinancialMetrics(COMPANY, [])
    operands = [service.missing("gross_profit", "Observed net-interest revenue basis.", PERIOD, "not_applicable"),
                service.missing("revenue", MISSING, PERIOD)]
    point = service.calculate("gross_margin", operands, PERIOD, ["gross_profit", "revenue"])
    assert point.reason == PREFIX + "Gross profit: Observed net-interest revenue basis. Revenue: " + MISSING
    assert_unavailable(point, "gross_margin", PERIOD)


def test_negative_capex_reason_survives_fcf_without_changing_source():
    rows = [fact(1), fact(2, "NetCashProvidedByUsedInOperatingActivities", "50"),
            fact(3, "PaymentsToAcquirePropertyPlantAndEquipment", "-10")]
    service = FinancialMetrics(COMPANY, rows)
    point = service.summary().metrics["free_cash_flow"]
    assert point.reason == PREFIX + "Capital expenditures: Negative payment fact conflicts with positive-outflow CapEx convention."
    assert_unavailable(point, "free_cash_flow", service.summary().period)
    assert rows[2].value == Decimal("-10")


def test_ambiguous_revenue_reason_survives_margin_without_selecting_alternatives():
    service = FinancialMetrics(COMPANY, [fact(1, CUSTOMER), fact(2, "SalesRevenueNet"),
                                        fact(3, "NetIncomeLoss", "20")])
    summary = service.summary()
    revenue, margin = summary.metrics["revenue"], summary.metrics["net_margin"]
    assert revenue.reason == AMBIGUOUS and {p.fact_id for p in revenue.alternatives} == {1, 2}
    assert margin.reason == PREFIX + "Revenue: " + AMBIGUOUS
    assert_unavailable(margin, "net_margin", summary.period)


@pytest.mark.parametrize("failed_years", [(2025,), (2024,), (2024, 2025)])
@pytest.mark.parametrize("reverse", [False, True])
def test_yoy_identifies_current_and_prior_ambiguous_revenue(failed_years, reverse):
    rows = []
    for year in (2024, 2025):
        concepts = (CUSTOMER, "SalesRevenueNet") if year in failed_years else ("Revenues",)
        for concept in concepts:
            rows.append(fact(len(rows) + 1, concept, start=f"{year}-01-01", end=f"{year}-03-31"))
    service = FinancialMetrics(COMPANY, list(reversed(rows)) if reverse else rows)
    summary = service.summary()
    point = summary.metrics["revenue_growth_yoy"]
    labels = [label for year, label in ((2025, "Current revenue"), (2024, "Prior revenue")) if year in failed_years]
    assert point.reason == PREFIX + " ".join(f"{label}: {AMBIGUOUS}" for label in labels)
    assert_unavailable(point, "revenue_growth_yoy", summary.period)


@pytest.mark.parametrize("intent", ["quarter", "latest_available"])
def test_deterministic_answer_serializes_operand_reason(intent):
    service = FinancialMetrics(COMPANY, [fact(1), fact(2, "NetCashProvidedByUsedInOperatingActivities", "50")])
    answer = resolve_answer(service, "quarterly free cash flow", "free_cash_flow", intent)
    payload = answer.model_dump(mode="json")
    expected = PREFIX + "Capital expenditures: " + MISSING
    assert payload["explanation"] == payload["observation"]["reason"] == expected
    assert expected in payload["answer_text"]
    assert payload["status"] == "unavailable" and payload["formatted_value"] is None
    assert_unavailable(answer.observation, "free_cash_flow", service.summary().period)
    assert ResearchAnswer.model_validate_json(answer.model_dump_json()) == answer


@pytest.mark.parametrize("question", ["2025 free cash flow", "compare 2024 and 2025 free cash flow"])
def test_historical_answer_serializes_operand_reason(question):
    rows = [fact(year * 2 + offset, concept, start=f"{year}-01-01", end=f"{year}-12-31")
            for year in (2024, 2025)
            for offset, concept in enumerate(("Revenues", "NetCashProvidedByUsedInOperatingActivities"))]
    service = FinancialMetrics(COMPANY, rows)
    operation, rejection = recognize_operation(question, COMPANY, [COMPANY])
    assert rejection is None
    answer = resolve_historical_answer(service, question, operation)
    payload = answer.model_dump(mode="json")
    expected = PREFIX + "Capital expenditures: " + MISSING
    assert payload["status"] == "unavailable" and payload["formatted_value"] is None
    assert expected in payload["explanation"] and expected in payload["answer_text"]
    if answer.observation:
        assert payload["observation"]["reason"] == expected
        assert_unavailable(answer.observation, "free_cash_flow", answer.observation.period)
    else:
        for side, year in (("earlier", 2024), ("later", 2025)):
            assert payload["comparison"][side]["reason"] == expected
            assert payload["comparison"][side]["value"] is None
            assert f"FY{year}: {expected}" in payload["explanation"]
        assert payload["comparison"]["absolute_change"] is None
        assert payload["comparison"]["percentage_change"] is None
    assert ResearchAnswer.model_validate_json(answer.model_dump_json()) == answer


def test_available_calculations_and_input_provenance_are_unchanged():
    concepts = ("Revenues", "GrossProfit", "OperatingIncomeLoss", "NetIncomeLoss",
                "NetCashProvidedByUsedInOperatingActivities", "PaymentsToAcquirePropertyPlantAndEquipment")
    rows = [fact(i, concept, value) for i, (concept, value) in enumerate(
        zip(concepts, ("100", "40", "20", "-10", "50", "60"), strict=True), 1)]
    rows.append(fact(7, value="80", start="2024-01-01", end="2024-03-31"))
    summary = FinancialMetrics(COMPANY, rows).summary()
    for metric, value, ids, roles in [
        ("gross_margin", ".4", [2, 1], ["gross_profit", "revenue"]),
        ("operating_margin", ".2", [3, 1], ["operating_income", "revenue"]),
        ("net_margin", "-.1", [4, 1], ["net_income", "revenue"]),
        ("free_cash_flow", "-10", [5, 6], ["operating_cash_flow", "capital_expenditures"]),
        ("revenue_growth_yoy", ".25", [1, 7], ["current", "prior"]),
    ]:
        point = summary.metrics[metric]
        assert point.status == "available" and point.value == Decimal(value) and point.reason is None
        assert [p.fact_id for p in point.provenance] == ids and point.alternatives == []
        assert [p.fact_ids for p in point.inputs] == [[i] for i in ids]
        assert [p.role for p in point.inputs] == roles
        assert point.formula == METRICS[metric].formula and point.period == summary.period
        assert point.scope_authorization is None
