"""SEC-like observations, real ORM fixtures, no network or AI calls."""
from datetime import date
from decimal import Decimal
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import main
from app.database import Base
from app.financial_metrics_service import FinancialMetrics, load_financial_metrics
from app.financial_metric_schemas import NormalizedFinancialSummary, NormalizedMetricHistory
from app.models import Company, FinancialFact


@pytest.fixture
def db(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(main, "SessionLocal", sessionmaker(bind=engine))
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setattr("app.answer_service._get_openai_client", Mock(side_effect=AssertionError("Forbidden AI")))
    monkeypatch.setattr("app.sec_client._sec_get", Mock(side_effect=AssertionError("Forbidden SEC download")))
    with Session(engine) as session:
        company = Company(ticker="TEST", cik="0000000001", name="Fixture company", exchange="NYSE")
        session.add(company)
        session.commit()
        yield session, company
    engine.dispose()


def add(db, concept="Revenues", value="100", start="2025-01-01", end="2025-03-31", **kwargs):
    session, company = db
    record = FinancialFact(
        company_cik=company.cik, metric=concept, value=Decimal(value), unit="USD",
        period_start=date.fromisoformat(start) if start else None, period_end=date.fromisoformat(end),
        period_type="quarter", fiscal_year=2026, fiscal_period="Q3", form="10-Q",
        filed=date(2025, 5, 1), accession_number="0000000001-25-000001",
        source=f"SEC Company Facts API: {concept}",
    )
    for name, value in kwargs.items():
        setattr(record, name, value)
    session.add(record)
    session.commit()
    return record


def view(db):
    return load_financial_metrics(db[0], "test")


@pytest.mark.parametrize("concept", ["Revenues", "SalesRevenueNet", "RevenueFromContractWithCustomerExcludingAssessedTax", "RevenuesNetOfInterestExpense"])
def test_audited_revenue_aliases_and_provenance(db, concept):
    row = add(db, concept, metric="Revenues")
    point = view(db).summary().metrics["revenue"]
    assert point.value == Decimal("100") and point.provenance[0].original_concept == concept
    assert point.provenance[0].fact_id == row.id and point.provenance[0].source_fiscal_year == 2026
    assert point.period.fiscal_year is None  # No observed fiscal boundary; do not copy filing FY.
    assert point.provenance[0].sec_url == "https://www.sec.gov/Archives/edgar/data/1/000000000125000001/0000000001-25-000001-index.html"


def test_alias_priority_restated_values_and_determinism(db):
    old = add(db, "Revenues", "90")
    preferred = add(db, "Revenues", "100", filed=date(2025, 5, 2))
    point = view(db).summary().metrics["revenue"]
    assert point.provenance[0].fact_id == preferred.id
    assert point.alternatives[0].fact_id == old.id
    restated = add(db, "Revenues", "110", form="10-K/A", filed=date(2026, 2, 1))
    assert view(db).summary().metrics["revenue"].provenance[0].fact_id == restated.id
    facts = list(db[0].query(FinancialFact).all())
    assert FinancialMetrics(db[1], facts).summary() == FinancialMetrics(db[1], list(reversed(facts))).summary()


@pytest.mark.parametrize("unit", ["EUR", "shares", "USD/shares"])
def test_incompatible_units_rejected(db, unit):
    add(db, unit=unit)
    assert view(db).summary().metrics["revenue"].status == "unavailable"


def test_unknown_source_concept_not_hidden_by_legacy_metric(db):
    add(db, "SegmentRevenue", metric="Revenues")
    assert view(db).history("revenue").status == "unavailable"


def test_dates_separate_quarter_ytd_annual_despite_false_stored_labels(db):
    add(db, value="10")
    add(db, value="25", end="2025-06-30", filed=date(2025, 8, 1))
    add(db, value="40", end="2025-09-30", filed=date(2025, 11, 1))
    add(db, value="60", end="2025-12-31", filed=date(2026, 2, 1), form="10-K")
    service = view(db)
    for kind, value in [("quarter", "10"), ("half_year", "25"), ("nine_months", "40"), ("annual", "60")]:
        assert service.history("revenue", kind).history[0].value == Decimal(value)
    assert service.summary().period.end == date(2025, 3, 31)
    assert len(service.history("revenue").history) == 1  # Never synthesize Q4.


def test_instant_points_do_not_become_quarterly_flows(db):
    add(db)
    add(db, "Assets", "500", start=None)
    add(db, "Liabilities", "250")  # A duration is invalid for a balance sheet fact.
    summary = view(db).summary()
    assert summary.metrics["total_assets"].value == 500
    assert summary.metrics["total_assets"].period.kind == "instant"
    assert summary.metrics["total_liabilities"].status == "unavailable"
    assert not view(db).history("total_assets", "quarter").history
    assert view(db).history("total_assets", "instant").history[0].value == 500


def test_non_calendar_fiscal_boundary_and_filing_context(db):
    add(db, start="2024-07-01", end="2025-06-30", form="10-K", filed=date(2025, 8, 1))
    add(db, start="2025-01-01", end="2025-03-31", fiscal_year=2027, fiscal_period="Q1")
    point = view(db).summary().metrics["revenue"]
    assert point.period.fiscal_year == 2025 and point.period.fiscal_period == "Q3"
    assert point.provenance[0].source_fiscal_year == 2027


def test_current_fiscal_year_uses_ytd_start_and_previous_year_boundary(db):
    add(db, start="2023-10-01", end="2024-09-28", form="10-K", filed=date(2024, 11, 1))
    add(db, start="2024-09-29", end="2025-03-29")
    add(db, start="2024-12-29", end="2025-03-29")
    point = view(db).summary().metrics["revenue"]
    assert point.period.fiscal_period == "Q2" and point.period.fiscal_year == 2025


@pytest.mark.parametrize("prior,current,expected", [("100", "120", ".2"), ("100", "80", "-.2"), ("0", "10", None), ("-10", "10", None)])
def test_yoy_period_comparability_and_denominators(db, prior, current, expected):
    add(db, value=prior, start="2024-01-01", end="2024-03-31")
    add(db, value="999", start="2024-01-01", end="2024-06-30")  # Incompatible YTD.
    add(db, value=current)
    point = view(db).summary().metrics["revenue_growth_yoy"]
    assert point.value == (Decimal(expected) if expected else None)
    if expected:
        assert len(point.inputs) == len(point.provenance) == 2
        assert point.inputs[1].period.end == date(2024, 3, 31)


def test_yoy_non_calendar_53_week_quarter_and_missing_prior(db):
    add(db, value="100", start="2023-10-01", end="2023-12-30", filed=date(2024, 2, 1))
    add(db, value="110", start="2024-09-29", end="2025-01-04", filed=date(2025, 2, 1))
    assert view(db).summary().metrics["revenue_growth_yoy"].value == Decimal(".1")
    assert view(db).summary("annual").metrics["revenue_growth_yoy"].value is None


@pytest.mark.parametrize("revenue", ["100", "0", "-100"])
def test_margin_formulas_negative_earnings_and_denominators(db, revenue):
    add(db, value=revenue)
    add(db, "GrossProfit", "40")
    add(db, "OperatingIncomeLoss", "20")
    add(db, "NetIncomeLoss", "-10")
    summary = view(db).summary()
    for name, expected in [("gross_margin", ".4"), ("operating_margin", ".2"), ("net_margin", "-.1")]:
        point = summary.metrics[name]
        assert point.value == (Decimal(expected) if revenue == "100" else None)
        assert point.unit == "ratio"


def test_incompatible_period_inputs_not_combined(db):
    add(db)
    add(db, "NetIncomeLoss", "20", start="2025-01-02")
    assert view(db).summary().metrics["net_margin"].value is None


@pytest.mark.parametrize("capex,expected", [("30", "50"), ("100", "-20"), ("0", "80"), ("-30", None)])
def test_capex_positive_outflow_and_fcf(db, capex, expected):
    add(db, "NetCashProvidedByUsedInOperatingActivities", "80")
    add(db, "PaymentsToAcquirePropertyPlantAndEquipment", capex)
    point = view(db).summary().metrics["free_cash_flow"]
    assert point.value == (Decimal(expected) if expected else None)
    if expected:
        assert {s.original_concept for s in point.provenance} == {"NetCashProvidedByUsedInOperatingActivities", "PaymentsToAcquirePropertyPlantAndEquipment"}


def test_negative_operating_cash_flow_is_preserved(db):
    add(db, "NetCashProvidedByUsedInOperatingActivities", "-20")
    add(db, "PaymentsToAcquirePropertyPlantAndEquipment", "30")
    assert view(db).summary().metrics["free_cash_flow"].value == -50


def test_history_status_describes_the_returned_window(db):
    add(db)
    add(db, "NetIncomeLoss", "20")
    add(db, start="2025-04-01", end="2025-06-30", filed=date(2025, 8, 1))
    history = view(db).history("net_margin", limit=1)
    assert history.status == "unavailable" and history.history[0].value is None


def test_net_interest_bank_basis_does_not_force_gross_margin(db):
    add(db, "RevenuesNetOfInterestExpense")
    add(db, "NetIncomeLoss", "20")
    add(db, "GrossProfit", "40")
    summary = view(db).summary()
    assert summary.metrics["gross_margin"].status == "not_applicable"
    assert summary.metrics["net_margin"].value == Decimal(".2")


def test_latest_period_precedes_latest_filing(db):
    add(db, value="10", filed=date(2026, 1, 1))
    add(db, value="20", start="2025-04-01", end="2025-06-30", filed=date(2025, 8, 1))
    assert view(db).summary().metrics["revenue"].value == 20


@pytest.mark.parametrize("kind,start,end,preferred", [
    ("quarter", "2025-01-01", "2025-03-31", "10-Q/A"),
    ("annual", "2024-01-01", "2024-12-31", "10-K/A"),
])
def test_same_date_duplicates_form_amendment_and_id_tie_break(db, kind, start, end, preferred):
    for form in ("10-K", "10-Q", "10-Q/A", "10-K/A"):
        add(db, value="100", start=start, end=end, form=form)
    newer_id = add(db, value="101", start=start, end=end, form=preferred)
    point = view(db).summary(kind).metrics["revenue"]
    assert point.provenance[0].fact_id == newer_id.id
    assert len(point.alternatives) == 4  # Conflicting values are visible, never averaged.


def test_legacy_financial_analysis_contract(db):
    from app.financial_analysis import get_financial_history, get_financial_snapshot, get_financial_summary
    for start, end, revenue, income, eps in [
        ("2024-01-01", "2024-03-31", "100", "10", "1"),
        ("2025-01-01", "2025-03-31", "120", "12", "1.2"),
    ]:
        add(db, value=revenue, start=start, end=end)
        add(db, "NetIncomeLoss", income, start=start, end=end)
        add(db, "EarningsPerShareDiluted", eps, start=start, end=end, unit="USD/shares")
    summary = get_financial_summary(db[0], db[1].cik)
    assert summary["metrics"]["revenue_yoy_growth"]["value"] == Decimal("20")
    assert summary["metrics"]["net_margin"]["value"] == Decimal("10")
    assert len(get_financial_history(db[0], db[1].cik)) == 2
    assert get_financial_snapshot(db[0], db[1].cik)["values"]["revenue"] == Decimal("120")


def test_eps_units_and_exact_decimal_serialization(db):
    add(db, "EarningsPerShareDiluted", "1.2345", unit="USD/shares")
    point = view(db).summary().metrics["diluted_eps"]
    assert point.unit == "USD/share" and point.model_dump(mode="json")["value"] == "1.2345"


def test_api_errors_schema_no_key_and_query_bound(db):
    client = TestClient(main.app)
    response = client.get("/companies/TEST/financials/metrics/revenue")
    assert response.status_code == 200 and response.json()["status"] == "unavailable"
    assert response.json()["history"] == []
    assert client.get("/companies/MISSING/financials/summary").json()["detail"]["code"] == "unknown_company"
    assert client.get("/companies/TEST/financials/metrics/mystery").json()["detail"]["code"] == "unknown_metric"
    assert client.get("/companies/TEST/financials/summary?period=monthly").status_code == 422
    assert client.get("/companies/TEST/financials/metrics/revenue?limit=0").status_code == 422
    add(db)
    statements = []
    def observe(_conn, _cursor, statement, *_):
        if statement.lstrip().lower().startswith("select"):
            statements.append(statement)
    event.listen(db[0].bind, "before_cursor_execute", observe)
    try:
        response = client.get("/companies/TEST/financials/summary")
    finally:
        event.remove(db[0].bind, "before_cursor_execute", observe)
    assert response.status_code == 200 and len(statements) == 3  # version + existing company/facts reads
    summary = NormalizedFinancialSummary.model_validate(response.json())
    assert summary.metrics["gross_margin"].value is None
    history = client.get("/companies/TEST/financials/metrics/revenue").json()
    assert NormalizedMetricHistory.model_validate(history).history[0].value == 100


@pytest.mark.parametrize("following_end,expected_year", [("2022-12-31", 2022), ("2023-01-07", 2023)])
def test_dec_jan_year_is_unknown_until_52_or_53_week_annual_is_observed(db, following_end, expected_year):
    add(db, start="2021-01-03", end="2022-01-01", filed=date(2022, 2, 1), form="10-K")
    add(db, start="2022-01-02", end="2022-07-02", filed=date(2022, 8, 1))
    quarter = add(db, start="2022-04-03", end="2022-07-02", filed=date(2022, 8, 1))
    before = view(db).summary().metrics["revenue"]
    assert before.period.fiscal_year is None and before.period.fiscal_period == "Q2"
    add(db, start="2022-01-02", end=following_end, filed=date(2023, 2, 1), form="10-K")
    after = view(db).summary().metrics["revenue"]
    assert after.period.fiscal_year == expected_year and after.period.fiscal_period == "Q2"
    assert after.period.fiscal_label_basis == "observed_annual_boundary"
    assert before.provenance[0].fact_id == after.provenance[0].fact_id == quarter.id
    assert before.value == after.value


def test_non_calendar_53_week_fiscal_projection_remains_unambiguous(db):
    add(db, start="2023-10-01", end="2024-10-05", filed=date(2024, 11, 1), form="10-K")
    add(db, start="2024-10-06", end="2025-04-05")
    add(db, start="2025-01-05", end="2025-04-05")
    period = view(db).summary().period
    assert period.fiscal_year == 2025 and period.fiscal_period == "Q2"


def test_repeated_jan_dec_calendar_evidence_preserves_current_year(db):
    add(db, start="2023-01-01", end="2023-12-31", filed=date(2024, 2, 1), form="10-K")
    add(db, start="2024-01-01", end="2024-12-31", filed=date(2025, 2, 1), form="10-K")
    add(db, start="2025-01-01", end="2025-06-30", filed=date(2025, 8, 1))
    add(db, start="2025-04-01", end="2025-06-30", filed=date(2025, 8, 1))
    period = view(db).summary().period
    assert period.fiscal_year == 2025 and period.fiscal_period == "Q2"
    assert period.fiscal_label_basis == "ytd_start_with_observed_calendar_year_pattern"


def test_one_calendar_like_annual_does_not_prove_current_year_end(db):
    add(db, start="2024-01-01", end="2024-12-31", filed=date(2025, 2, 1), form="10-K")
    add(db, start="2025-01-01", end="2025-06-30", filed=date(2025, 8, 1))
    add(db, start="2025-04-01", end="2025-06-30", filed=date(2025, 8, 1))
    period = view(db).summary().period
    assert period.fiscal_year is None and period.fiscal_period == "Q2"


@pytest.mark.parametrize("subset", ["RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"])
@pytest.mark.parametrize("later", [False, True])
def test_known_total_cannot_be_overridden_by_subset(db, subset, later):
    total = add(db, "Revenues", "100")
    component = add(db, subset, "60", filed=date(2025, 5, 2) if later else date(2025, 5, 1))
    add(db, "NetIncomeLoss", "10")
    summary = view(db).summary()
    assert summary.metrics["revenue"].value == 100
    assert summary.metrics["revenue"].revenue_basis == "total_revenue"
    assert summary.metrics["revenue"].provenance[0].fact_id == total.id
    assert summary.metrics["revenue"].alternatives[0].fact_id == component.id
    assert summary.metrics["net_margin"].value == Decimal(".1")


@pytest.mark.parametrize("other", ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax"])
def test_conflicting_bank_revenue_scopes_are_unavailable_with_diagnostics(db, other):
    bank = add(db, "RevenuesNetOfInterestExpense", "100")
    incompatible = add(db, other, "150", filed=date(2025, 5, 2))
    add(db, "NetIncomeLoss", "20")
    summary = view(db).summary()
    revenue = summary.metrics["revenue"]
    assert revenue.status == "unavailable" and revenue.value is None
    assert {s.fact_id for s in revenue.alternatives} == {bank.id, incompatible.id}
    assert summary.metrics["net_margin"].value is None
    assert summary.metrics["revenue_growth_yoy"].value is None
    assert view(db).history("revenue").history[0].status == "unavailable"


def test_different_components_without_total_are_ambiguous(db):
    add(db, "SalesRevenueNet", "60")
    add(db, "RevenueFromContractWithCustomerExcludingAssessedTax", "70")
    assert view(db).summary().metrics["revenue"].status == "unavailable"


@pytest.mark.parametrize("current_concept", ["RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet", "RevenuesNetOfInterestExpense"])
def test_yoy_incompatible_revenue_scope_transition_is_unavailable(db, current_concept):
    add(db, "Revenues", "100", start="2024-01-01", end="2024-03-31")
    add(db, current_concept, "110")
    assert view(db).summary().metrics["revenue_growth_yoy"].status == "unavailable"


def test_aliases_are_comparable_only_with_explicit_reviewed_declaration(db, monkeypatch):
    from app import financial_metric_registry as registry
    # Simulates a future reviewed scope declaration, not a production claim
    # that these taxonomy concepts are universally interchangeable.
    add(db, "SalesRevenueNet", "100", start="2024-01-01", end="2024-03-31")
    add(db, "RevenueFromContractWithCustomerExcludingAssessedTax", "110")
    assert view(db).summary().metrics["revenue_growth_yoy"].value is None
    monkeypatch.setattr(registry, "REVENUE_EQUIVALENCES", frozenset((frozenset(("net_sales", "customer_contract")),)))
    assert view(db).summary().metrics["revenue_growth_yoy"].value == Decimal(".1")
    old = add(db, "SalesRevenueNet", "105")
    point = view(db).summary().metrics["revenue"]
    assert point.value == 110 and old.id in [s.fact_id for s in point.alternatives]


@pytest.mark.parametrize("concept", ["RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"])
def test_component_only_revenue_is_labelled_but_not_a_consolidated_margin_base(db, concept):
    add(db, concept, "60")
    for name in ("NetIncomeLoss", "GrossProfit", "OperatingIncomeLoss"):
        add(db, name, "10")
    summary = view(db).summary()
    assert summary.metrics["revenue"].value == 60 and summary.metrics["revenue"].revenue_basis != "total_revenue"
    assert all(summary.metrics[n].value is None for n in ("net_margin", "gross_margin", "operating_margin"))


def test_eps_vintage_changes_remain_source_faithful_and_comparability_unverified(db):
    first = add(db, "EarningsPerShareDiluted", "2", unit="USD/shares")
    second = add(db, "EarningsPerShareDiluted", "1", start="2025-04-01", end="2025-06-30", filed=date(2025, 8, 1), unit="USD/shares")
    history = view(db).history("diluted_eps")
    assert [p.value for p in history.history] == [Decimal("2"), Decimal("1")]
    assert [p.provenance[0].fact_id for p in history.history] == [first.id, second.id]
    assert history.comparability.status == "unverified"
    assert history.comparability.value_basis == "reported_as_filed"
    actual = TestClient(main.app).get("/companies/TEST/financials/metrics/diluted_eps").json()
    assert actual["comparability"]["status"] == "unverified"
    assert [Decimal(p["value"]) for p in actual["history"]] == [Decimal("2"), Decimal("1")]
    assert "comparability" not in TestClient(main.app).get("/companies/TEST/financials/metrics/revenue").json()


@pytest.mark.parametrize("damage", ["order", "kind", "dates", "value", "fact_id", "concept", "accession", "unit", "sec_url"])
def test_history_verification_rejects_semantic_and_provenance_corruption(db, damage):
    from scripts.verify_financial_metrics import verify_history
    first = add(db)
    second = add(db, value="120", start="2025-04-01", end="2025-06-30", filed=date(2025, 8, 1))
    rows = {first.id: first, second.id: second}
    history = view(db).history("revenue")
    verify_history(history, rows)
    point = history.history[0]
    if damage == "order":
        history.history.reverse()
    elif damage == "kind":
        point.period.kind = "half_year"
    elif damage == "dates":
        point.period.start = date(2025, 1, 2)
    elif damage == "value":
        point.value = Decimal("999")
    elif damage == "fact_id":
        point.provenance[0].fact_id = second.id
    elif damage == "concept":
        point.provenance[0].original_concept = "SegmentRevenue"
    elif damage == "accession":
        point.provenance[0].accession_number = "0000000001-25-999999"
    elif damage == "sec_url":
        point.provenance[0].sec_url = "https://www.sec.gov/wrong"
    else:
        history.unit = point.unit = "EUR"
    with pytest.raises(AssertionError):
        verify_history(history, rows)


@pytest.mark.parametrize("damage", ["drop_observation", "fiscal_label", "company"])
def test_http_history_verification_checks_response_body(db, damage):
    from scripts.verify_financial_metrics import verify_http_history
    row = add(db)
    expected = view(db).history("revenue")
    payload = expected.model_dump(mode="json")
    verify_http_history(payload, expected, {row.id: row})
    if damage == "drop_observation":
        payload["history"] = []
    elif damage == "fiscal_label":
        payload["history"][0]["period"]["fiscal_year"] = 2099
    else:
        payload["ticker"] = "OTHER"
    with pytest.raises(AssertionError):
        verify_http_history(payload, expected, {row.id: row})
