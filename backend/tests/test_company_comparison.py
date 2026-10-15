"""Pure synthetic financial objects and mocked read-only sessions; no database I/O."""
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app import main, freshness_service, revenue_scope_authorizations as permissions
from app import sec_evidence_adapter, financial_metric_registry
from app.financial_metrics_service import FinancialMetrics, ANNUAL_COMPARISON_METRICS, UnknownCompany
from app.financial_metric_schemas import AnnualFinancialComparison


COMPANY = SimpleNamespace(ticker="TEST", cik="0000000001", name="Synthetic company")


@pytest.fixture(autouse=True)
def forbid_live_dependencies(monkeypatch):
    monkeypatch.setattr("app.database.engine.connect", Mock(side_effect=AssertionError("Live database forbidden")))
    monkeypatch.setattr("app.sec_client._sec_get", Mock(side_effect=AssertionError("SEC request forbidden")))
    monkeypatch.setattr("app.answer_service._get_openai_client", Mock(side_effect=AssertionError("AI request forbidden")))


def fact(concept="Revenues", value="100", start="2025-01-01", end="2025-12-31", **overrides):
    values = dict(id=1, company_cik=COMPANY.cik, metric=concept, value=Decimal(value), unit="USD",
                  period_start=date.fromisoformat(start), period_end=date.fromisoformat(end),
                  period_type="annual", fiscal_year=2026, fiscal_period="Q1", frame=None,
                  form="10-K", filed=date(2026, 2, 1), accession_number="0000000001-26-000001",
                  source=f"SEC Company Facts API: {concept}", created_at=datetime(2026, 2, 1))
    values.update(overrides)
    return SimpleNamespace(**values)


def view(*facts, company=COMPANY):
    return FinancialMetrics(company, list(facts))


def rollover_view():
    """Shared with the frontend contract test: actual backend serialization."""
    return view(fact(value="100", start="2022-01-02", end="2022-12-31", id=1),
                fact(value="125", start="2023-01-01", end="2024-01-06", id=2))


def test_annual_yoy_uses_dates_across_calendar_end_year_rollover():
    response = rollover_view().annual_comparison(2024)
    point = response.metrics["revenue_growth_yoy"]
    assert point.status == "available" and point.value == Decimal(".25")
    assert [i.period.fiscal_year for i in point.inputs] == [2024, 2022]
    assert [i.period.end for i in point.inputs] == [date(2024, 1, 6), date(2022, 12, 31)]


def test_discovery_includes_cash_flow_year_even_when_other_year_has_revenue():
    model = view(fact(), fact("NetCashProvidedByUsedInOperatingActivities", "9", start="2024-01-01", end="2024-12-31", id=2),
                 fact("PaymentsToAcquirePropertyPlantAndEquipment", "3", start="2024-01-01", end="2024-12-31", id=3))
    prior_summary = model.summary("annual").model_dump(mode="json")
    assert model.annual_comparison().fiscal_years == [2025, 2024]
    response = model.annual_comparison(2024)
    assert (response.period.start, response.period.end) == (date(2024, 1, 1), date(2024, 12, 31))
    assert response.metrics["revenue"].status == "unavailable"
    assert response.metrics["net_margin"].status == "unavailable"
    assert response.metrics["operating_cash_flow"].value == Decimal("9")
    assert response.metrics["capital_expenditures"].value == Decimal("3")
    assert response.metrics["free_cash_flow"].value == Decimal("6")
    assert [s.fact_id for s in response.metrics["free_cash_flow"].provenance] == [2, 3]
    assert model.summary("annual").model_dump(mode="json") == prior_summary
    assert [p.fiscal_year for p in model.reporting_periods("annual")] == [2025]


@pytest.mark.parametrize("concept,metric", [("NetCashProvidedByUsedInOperatingActivities", "operating_cash_flow"),
                                            ("PaymentsToAcquirePropertyPlantAndEquipment", "capital_expenditures")])
def test_discovery_includes_each_cash_flow_metric_without_other_annual_anchors(concept, metric):
    response = view(fact(concept, "3", start="2024-01-01", end="2024-12-31")).annual_comparison(2024)
    assert response.fiscal_years == [2024] and response.period is not None
    assert response.metrics[metric].status == "available"
    assert response.metrics["revenue"].status == "unavailable"
    assert response.metrics["free_cash_flow"].status == "unavailable"


@pytest.mark.parametrize("start,end", [("2024-01-02", "2024-12-31"), ("2023-10-01", "2024-09-30")])
def test_conflicting_cash_flow_windows_are_ambiguous_even_with_unique_revenue_year(start, end):
    model = view(fact(), fact("NetCashProvidedByUsedInOperatingActivities", "9", start="2024-01-01", end="2024-12-31", id=2),
                 fact("PaymentsToAcquirePropertyPlantAndEquipment", "3", start=start, end=end, id=3))
    assert model.annual_comparison().fiscal_years == [2025, 2024]
    response = model.annual_comparison(2024)
    assert response.period is None and "ambiguous" in response.period_reason
    assert all(p.status == "unavailable" and p.value is None for p in response.metrics.values())


def test_conflicting_cash_flow_window_cannot_be_hidden_by_same_year_revenue():
    response = view(fact(start="2024-01-01", end="2024-12-31"),
                    fact("NetCashProvidedByUsedInOperatingActivities", "9", start="2023-10-01", end="2024-09-30", id=2)).annual_comparison(2024)
    assert response.period is None and "ambiguous" in response.period_reason
    assert response.metrics["revenue"].status == "unavailable"


def test_only_exact_annual_cash_flow_dates_are_used():
    model = view(fact(), fact("NetCashProvidedByUsedInOperatingActivities", "9", start="2024-01-01", end="2024-12-31", id=2),
                 fact("PaymentsToAcquirePropertyPlantAndEquipment", "3", start="2024-01-01", end="2024-06-30", id=3),
                 fact("PaymentsToAcquirePropertyPlantAndEquipment", "4", start="2023-01-01", end="2023-12-31", id=4))
    response = model.annual_comparison(2024)
    assert response.period is not None
    assert response.metrics["operating_cash_flow"].value == Decimal("9")
    assert response.metrics["capital_expenditures"].status == "unavailable"
    assert response.metrics["free_cash_flow"].status == "unavailable"


def test_discovery_is_observed_deduplicated_and_never_latest_data():
    model = view(fact(), fact(id=2), fact(start="2024-01-01", end="2024-12-31"),
                 fact(start="2023-01-01", end="2023-06-30"))
    response = model.annual_comparison()
    assert response.fiscal_years == [2025, 2024]
    assert response.period is None and response.metrics == {}
    point = model.annual_comparison(2024).metrics["revenue"]
    assert point.period.end == date(2024, 12, 31)
    assert point.period.fiscal_year == 2024  # Ignore source filing FY2026.
    assert point.provenance[0].source_fiscal_year == 2026


@pytest.mark.parametrize("start,end", [("2024-09-29", "2025-09-27"), ("2024-09-22", "2025-09-27")])
def test_exact_week_calendar_dates_survive(start, end):
    result = view(fact(start=start, end=end)).annual_comparison(2025)
    assert result.period.start == date.fromisoformat(start)
    assert result.period.end == date.fromisoformat(end)
    assert result.period.fiscal_label_basis == "annual_period_end_year"
    assert result.metrics["revenue"].value == Decimal("100")


def test_different_calendars_are_not_normalized_to_common_dates():
    calendar = view(fact()).annual_comparison(2025)
    fiscal = view(fact(start="2024-10-01", end="2025-09-30")).annual_comparison(2025)
    assert calendar.period != fiscal.period


@pytest.mark.parametrize("facts,year,word", [
    ([fact(), fact(start="2024-01-01", end="2024-12-31")], 2023, "No stored"),
    ([fact(start="2025-01-01", end="2025-06-30")], 2025, "No stored"),
    ([fact(), fact(start="2024-10-01", end="2025-09-30")], 2025, "ambiguous"),
])
def test_missing_and_ambiguous_windows_never_substitute(facts, year, word):
    result = view(*facts).annual_comparison(year)
    assert result.period is None and word in result.period_reason
    assert tuple(result.metrics) == ANNUAL_COMPARISON_METRICS
    assert all(p.status == "unavailable" and p.value is None and p.period is None for p in result.metrics.values())


def test_metrics_use_existing_observations_and_endpoint_summary_semantics():
    model = view(fact(), fact("OperatingIncomeLoss", "20", id=2), fact("NetIncomeLoss", "10", id=3),
                 fact("NetCashProvidedByUsedInOperatingActivities", "-7", id=4),
                 fact("PaymentsToAcquirePropertyPlantAndEquipment", "3", id=5),
                 fact(value="80", start="2024-01-01", end="2024-12-31", id=6))
    before = model.summary("annual").model_dump(mode="json")
    result = model.annual_comparison(2025)
    for name in ANNUAL_COMPARISON_METRICS:
        assert result.metrics[name].model_dump(mode="json") == before["metrics"][name]
    assert result.metrics["net_margin"].value == Decimal(".1")
    assert result.metrics["revenue_growth_yoy"].value == Decimal(".25")
    assert result.metrics["free_cash_flow"].value == Decimal("-10")
    assert [s.fact_id for s in result.metrics["free_cash_flow"].provenance] == [4, 5]
    assert model.summary("annual").model_dump(mode="json") == before


@pytest.mark.parametrize("concepts", [[], ["NetCashProvidedByUsedInOperatingActivities"], ["PaymentsToAcquirePropertyPlantAndEquipment"]])
def test_missing_cash_flow_inputs_are_preserved(concepts):
    result = view(fact(), *(fact(c, id=i+2) for i, c in enumerate(concepts))).annual_comparison(2025)
    assert result.metrics["free_cash_flow"].status == "unavailable"
    for metric, concept in [("operating_cash_flow", "NetCashProvidedByUsedInOperatingActivities"),
                            ("capital_expenditures", "PaymentsToAcquirePropertyPlantAndEquipment")]:
        assert result.metrics[metric].status == ("available" if concept in concepts else "unavailable")


def test_wrong_period_negative_capex_and_incompatible_net_margin_stay_unavailable():
    result = view(fact("RevenueFromContractWithCustomerExcludingAssessedTax"),
                  fact("NetIncomeLoss", "10", id=2),
                  fact("NetCashProvidedByUsedInOperatingActivities", "9", start="2025-01-01", end="2025-06-30", id=3),
                  fact("PaymentsToAcquirePropertyPlantAndEquipment", "-3", id=4)).annual_comparison(2025)
    assert result.metrics["revenue"].revenue_basis == "customer_contract"
    assert result.metrics["net_margin"].status == "unavailable"
    assert "approved" in result.metrics["net_margin"].reason
    assert result.metrics["operating_cash_flow"].status == "unavailable"
    assert result.metrics["capital_expenditures"].status == "unavailable"
    assert result.metrics["free_cash_flow"].status == "unavailable"


def test_revenue_scope_conflicts_are_not_resolved_by_comparison():
    result = view(fact("RevenueFromContractWithCustomerExcludingAssessedTax"),
                  fact("SalesRevenueNet", id=2)).annual_comparison(2025)
    assert result.period is not None
    assert result.metrics["revenue"].status == "unavailable"
    assert len(result.metrics["revenue"].alternatives) == 2


@pytest.mark.parametrize("extra", [{"unit": "EUR"}, {"company_cik": "0000000002"},
                                    {"period_start": date(2025, 1, 1), "period_end": date(2025, 6, 30)}])
def test_net_margin_rejects_missing_or_incompatible_numerator(extra):
    result = view(fact(), fact("NetIncomeLoss", "10", id=2, **extra)).annual_comparison(2025)
    assert result.metrics["net_margin"].status == "unavailable"
    assert result.metrics["net_margin"].value is None
    assert result.metrics["net_margin"].provenance == []


def test_foreign_company_facts_cannot_leak_and_response_scope_is_validated():
    result = view(fact(), fact(value="999", id=2, company_cik="0000000002")).annual_comparison(2025)
    assert result.metrics["revenue"].value == Decimal("100")
    payload = result.model_dump()
    payload["company_cik"] = "0000000002"
    with pytest.raises(ValidationError):
        AnnualFinancialComparison.model_validate(payload)
    payload = result.model_dump()
    payload["requested_fiscal_year"] = 2024
    with pytest.raises(ValidationError):
        AnnualFinancialComparison.model_validate(payload)


def test_original_aapl_gross_margin_and_historical_unavailable_states_are_unchanged():
    pin = financial_metric_registry.GROSS_MARGIN_COVERAGE[0]
    aapl = SimpleNamespace(ticker="AAPL", cik=pin.company_cik, name="Apple synthetic fixture")
    identity = dict(company_cik=pin.company_cik, period_start=pin.start, period_end=pin.end,
                    form=pin.form, filed=pin.filed, accession_number=pin.accession)
    historical = dict(company_cik=pin.company_cik, start="2017-10-01", end="2018-03-31", filed=date(2018, 5, 1))
    model = view(fact(pin.revenue_concept, str(pin.revenue), **identity),
                 fact(pin.gross_profit_concept, str(pin.gross_profit), id=2, **identity),
                 fact("NetIncomeLoss", "29789000000", id=3, **identity),
                 fact("RevenueFromContractWithCustomerExcludingAssessedTax", "149430000000", id=4, **historical),
                 fact("SalesRevenueNet", "149430000000", id=5, **historical), company=aapl)
    before = model.summary("quarter").model_dump(mode="json")
    past = model.history("revenue", "half_year").model_dump(mode="json")
    model.annual_comparison()
    model.annual_comparison(2026)
    assert before == model.summary("quarter").model_dump(mode="json")
    assert past == model.history("revenue", "half_year").model_dump(mode="json")
    assert before["metrics"]["gross_margin"]["status"] == "available"
    assert before["metrics"]["net_margin"]["status"] == "unavailable"
    assert past["history"][0]["status"] == "unavailable"


@pytest.fixture
def api(monkeypatch):
    # The production read_session/version route runs, backed by a SELECT-only fake.
    session = Mock()
    session.__enter__ = Mock(return_value=session)
    session.__exit__ = Mock(return_value=False)
    session.get_bind.return_value.dialect.name = "postgresql"
    session.scalar.return_value = 7
    monkeypatch.setattr(main, "HttpSessionLocal", lambda: session)
    monkeypatch.setattr(freshness_service, "schema_ready", lambda _: True)
    model = view(fact())
    loader = Mock(return_value=model)
    monkeypatch.setattr(main, "load_financial_metrics", loader)
    with TestClient(main.app) as client:
        yield client, loader, session, model


def test_api_exact_year_choices_version_pin_and_existing_endpoints(api):
    client, loader, session, model = api
    headers = {"X-FinLens-Data-Version": "7"}
    discovery = client.get("/companies/test/financials/annual", headers=headers)
    assert discovery.status_code == 200
    assert discovery.headers["X-FinLens-Data-Version"] == "7"
    assert discovery.headers["Cache-Control"] == "no-store"
    assert discovery.json()["fiscal_years"] == [2025]
    assert discovery.json()["metrics"] == {}
    selected = client.get("/companies/TEST/financials/annual?fiscal_year=2025", headers=headers)
    assert selected.json() == model.annual_comparison(2025).model_dump(mode="json")
    summary = client.get("/companies/TEST/financials/summary?period=annual", headers=headers)
    assert summary.json() == model.summary("annual").model_dump(mode="json")
    history = client.get("/companies/TEST/financials/metrics/revenue?period=annual", headers=headers)
    assert history.json() == model.history("revenue", "annual").model_dump(mode="json")
    assert all("READ ONLY" in str(call.args[0]) for call in session.execute.call_args_list)
    loader.reset_mock()
    stale = client.get("/companies/TEST/financials/annual?fiscal_year=2025", headers={"X-FinLens-Data-Version": "6"})
    assert stale.status_code == 409 and stale.headers["X-FinLens-Error-Code"] == "DATA_VERSION_CHANGED"
    loader.assert_not_called()


def test_api_invalid_year_and_unknown_company(api):
    client, loader, _, _ = api
    assert client.get("/companies/TEST/financials/annual?fiscal_year=1899").status_code == 422
    assert client.get("/companies/TEST/financials/annual?fiscal_year=2100").status_code == 422
    loader.side_effect = UnknownCompany("UNKNOWN")
    assert client.get("/companies/UNKNOWN/financials/annual").status_code == 404


def test_api_rejects_inconsistent_company_identity(api):
    client, loader, _, _ = api
    loader.return_value = view(fact(), company=SimpleNamespace(ticker="OTHER", cik=COMPANY.cik, name="Other"))
    assert client.get("/companies/TEST/financials/annual?fiscal_year=2025").status_code == 409


def test_production_permissions_remain_inactive():
    assert permissions.REVENUE_SELECTION_AUTHORIZATIONS == ()
    assert permissions.DENOMINATOR_AUTHORIZATIONS == ()
    assert permissions.AUTHORIZATION_WITHDRAWALS == ()
    assert sec_evidence_adapter.PRODUCTION_EVIDENCE_POLICIES == ()
    assert not financial_metric_registry.REVENUE_EQUIVALENCES
