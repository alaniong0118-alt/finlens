"""SEC-like observations, real ORM fixtures, no network or AI calls."""
from datetime import date, datetime
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
    monkeypatch.setattr(main, "HttpSessionLocal", sessionmaker(bind=engine))
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


@pytest.mark.parametrize("ticker", ["TSLA", "AAPL", "AMZN", "COST"])
def test_gross_margin_valid_authoritative_inputs_are_not_ticker_specific(db, ticker):
    """Compatible synthetic inputs, not a claim of current issuer coverage."""
    session, company = db
    company.ticker = ticker
    session.commit()
    revenue = add(db, "Revenues", "100")
    gross_profit = add(db, "GrossProfit", "40")
    response = TestClient(main.app).get(f"/companies/{ticker}/financials/summary")
    assert response.status_code == 200
    point = response.json()["metrics"]["gross_margin"]
    assert point["status"] == "available" and Decimal(point["value"]) == Decimal(".4")
    assert {p["fact_id"] for p in point["provenance"]} == {revenue.id, gross_profit.id}


@pytest.mark.parametrize("case", ["missing", "period", "unit", "old_period"])
def test_gross_margin_rejects_missing_or_incompatible_gross_profit(db, case):
    add(db, "Revenues", "100")
    if case != "missing":
        kwargs = {"period": {"start": "2025-01-02"},
                  "unit": {"unit": "EUR"},
                  "old_period": {"start": "2024-01-01", "end": "2024-03-31"}}[case]
        add(db, "GrossProfit", "40", **kwargs)
    point = TestClient(main.app).get("/companies/TEST/financials/summary").json()["metrics"]["gross_margin"]
    assert point["status"] == "unavailable" and point["value"] is None
    assert point["provenance"] == []


@pytest.mark.parametrize("concept", ["OperatingExpenses", "CostsAndExpenses", "OperatingIncomeLoss",
                                     "CostOfRevenue", "CostOfGoodsAndServicesSold"])
def test_gross_margin_does_not_use_unreviewed_cost_or_expense_fallbacks(db, concept):
    add(db, "Revenues", "100")
    add(db, concept, "60")
    point = view(db).summary().metrics["gross_margin"]
    assert point.status == "unavailable" and point.value is None


def test_aapl_like_same_filing_gross_profit_does_not_prove_revenue_scope(db):
    """Matching period/unit/accession alone must not waive economic coverage."""
    add(db, "RevenueFromContractWithCustomerExcludingAssessedTax", "109417000000")
    add(db, "GrossProfit", "54770000000")
    point = TestClient(main.app).get("/companies/TEST/financials/summary").json()["metrics"]["gross_margin"]
    assert point["status"] == "unavailable" and point["value"] is None
    assert "scope" in point["reason"]


def reviewed_aapl_inputs(db):
    session, company = db
    company.ticker, company.cik = "AAPL", "0000320193"
    session.commit()
    metadata = dict(start="2026-03-29", end="2026-06-27", filed=date(2026, 7, 31),
                    accession_number="0000320193-26-000020", fiscal_year=2026,
                    fiscal_period="Q3", frame="CY2026Q2")
    revenue = add(db, "RevenueFromContractWithCustomerExcludingAssessedTax", "109417000000", **metadata)
    gross_profit = add(db, "GrossProfit", "54770000000", **metadata)
    return revenue, gross_profit


def test_reviewed_aapl_consolidated_gross_margin_api_and_provenance(db):
    from decimal import localcontext
    revenue, gross_profit = reviewed_aapl_inputs(db)
    response = TestClient(main.app).get("/companies/AAPL/financials/summary")
    assert response.status_code == 200
    metrics = response.json()["metrics"]
    point = metrics["gross_margin"]
    with localcontext() as context:
        context.prec = 28
        expected = Decimal("54770000000") / Decimal("109417000000")
    assert point["status"] == "available" and Decimal(point["value"]) == expected
    assert point["formula"] == "gross_profit / revenue"
    assert {p["fact_id"] for p in point["provenance"]} == {revenue.id, gross_profit.id}
    assert all(p["accession_number"] == "0000320193-26-000020" for p in point["provenance"])
    assert {i["role"] for i in point["inputs"]} == {"gross_profit", "revenue"}
    # Coverage approval must not leak into other margin/basis calculations.
    add(db, "NetIncomeLoss", "100", start="2026-03-29", end="2026-06-27", filed=date(2026, 7, 31))
    api = TestClient(main.app)
    assert api.get("/companies/AAPL/financials/summary").json()["metrics"]["net_margin"]["value"] is None
    assert api.get("/companies/AAPL/financials/summary?period=annual").json()["metrics"]["gross_margin"]["value"] is None


@pytest.mark.parametrize("mismatch", [
    "issuer", "revenue_concept", "gross_profit_concept", "revenue_value", "gross_profit_value",
    "revenue_unit", "gross_profit_unit", "period", "gross_profit_accession", "both_accessions",
    "filed", "form", "missing", "both_periods", "both_units",
])
def test_reviewed_aapl_gross_margin_fails_closed_on_changed_source_pair(db, mismatch):
    revenue, gross_profit = reviewed_aapl_inputs(db)
    session, company = db
    if mismatch == "issuer":
        company.cik = revenue.company_cik = gross_profit.company_cik = "0000000002"
    elif mismatch.endswith("concept"):
        row = revenue if mismatch.startswith("revenue") else gross_profit
        row.source = "SEC Company Facts API: " + ("SalesRevenueNet" if row is revenue else "OperatingIncomeLoss")
    elif mismatch.endswith("value"):
        row = revenue if mismatch.startswith("revenue") else gross_profit
        row.value += Decimal("1")
    elif mismatch == "both_units":
        revenue.unit = gross_profit.unit = "EUR"
    elif mismatch.endswith("unit"):
        (revenue if mismatch.startswith("revenue") else gross_profit).unit = "EUR"
    elif mismatch == "period":
        gross_profit.period_start = date(2026, 3, 30)
    elif mismatch == "both_periods":
        revenue.period_start = gross_profit.period_start = date(2026, 3, 30)
    elif mismatch == "gross_profit_accession":
        gross_profit.accession_number = "0000320193-26-000021"
    elif mismatch == "both_accessions":
        revenue.accession_number = gross_profit.accession_number = "0000320193-26-000021"
    elif mismatch == "filed":
        revenue.filed = gross_profit.filed = date(2026, 8, 1)
    elif mismatch == "form":
        revenue.form = gross_profit.form = "10-Q/A"
    else:
        session.delete(gross_profit)
    session.commit()
    point = TestClient(main.app).get("/companies/AAPL/financials/summary").json()["metrics"]["gross_margin"]
    assert point["status"] == "unavailable" and point["value"] is None


def test_total_revenue_gross_margin_rejects_cross_filing_pair(db):
    add(db, "Revenues", "100")
    add(db, "GrossProfit", "40", accession_number="0000000001-25-000002")
    point = view(db).summary().metrics["gross_margin"]
    assert point.value is None and "same filing accession" in point.reason


@pytest.mark.parametrize("metric", ["revenue", "gross_profit"])
@pytest.mark.parametrize("approved_last", [False, True])
@pytest.mark.parametrize("identical", [False, True])
def test_reviewed_aapl_candidate_values_independent_of_insertion_order(db, metric, approved_last, identical):
    session, company = db
    company.ticker, company.cik = "AAPL", "0000320193"
    session.commit()
    concept = "GrossProfit" if metric == "gross_profit" else "RevenueFromContractWithCustomerExcludingAssessedTax"
    approved_value = "54770000000" if metric == "gross_profit" else "109417000000"

    def competing_row():
        return add(db, concept, approved_value if identical else "60000000000",
                   start="2026-03-29", end="2026-06-27", filed=date(2026, 7, 31),
                   accession_number="0000320193-26-000020", frame="CY2026Q2")

    if approved_last:
        competing = competing_row()
    revenue, gross_profit = reviewed_aapl_inputs(db)
    approved = gross_profit if metric == "gross_profit" else revenue
    if not approved_last:
        competing = competing_row()
    assert (approved.id > competing.id) == approved_last
    response = TestClient(main.app).get("/companies/AAPL/financials/summary")
    assert response.status_code == 200
    point = response.json()["metrics"]["gross_margin"]
    if identical:
        assert point["status"] == "available"
        assert Decimal(point["value"]) == Decimal("0.5005620698794520047159033788")
    else:
        assert point["status"] == "unavailable" and point["value"] is None


@pytest.mark.parametrize("metric", ["revenue", "gross_profit"])
@pytest.mark.parametrize("context", ["company", "accession", "period", "unit", "concept", "filed"])
def test_reviewed_aapl_conflict_guard_ignores_unrelated_observations(db, metric, context):
    revenue, gross_profit = reviewed_aapl_inputs(db)
    source = gross_profit if metric == "gross_profit" else revenue
    fields = {column.name: getattr(source, column.name) for column in FinancialFact.__table__.columns
              if column.name != "id"}
    fields["value"] = Decimal("60000000000")
    if context == "company":
        fields["company_cik"] = "0000000002"
    elif context == "accession":
        fields["accession_number"] = "0000320193-26-000019"
    elif context == "period":
        fields["period_start"] = date(2026, 1, 1)
        fields["period_end"] = date(2026, 3, 28)
    elif context == "unit":
        fields["unit"] = "EUR"
    elif context == "concept":
        fields["source"] = "SEC Company Facts API: OperatingIncomeLoss"
    else:
        fields["filed"] = date(2026, 7, 30)
    # Lower ID for same-period older/contextual facts keeps normal selection fixed.
    fields["id"] = 0
    db[0].add(FinancialFact(**fields))
    db[0].commit()
    point = TestClient(main.app).get("/companies/AAPL/financials/summary").json()["metrics"]["gross_margin"]
    assert point["status"] == "available"
    assert Decimal(point["value"]) == Decimal("0.5005620698794520047159033788")


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


# C5: supplied ORM observations only. These tests never open a database. The
# fingerprints were frozen BEFORE extraction against this immutable commit.
C5_BASELINE = "6838af1d9164979daebb179144d67cd154da020e"
C5_FINGERPRINTS = {
    "standard": "7746ca4fe3d4862d5328a7d8961d904261ce97ef8952a0ece4fdb753088a4ffe",
    "rank": "f4e36126b5952ddd16505d413ddb2c2993e771b6b72e0bcecb139a584f996017",
    "negative_capex": "2ababdefd505f022cca45efc50a7899d5e224ee2506b2462c9e6a4864bfaa3c0",
    "bank": "7980c58dcd02ae7a7e68338124d4edccd4d67fbac0dadf68fb3263d562bfc42b",
    "ambiguous": "a2d97be95132ab967740f4a6fad1b5da340cd839dc884091f0388ddba1545aa7",
    "bank_conflict": "30e169bce312b8feffc03528c0969dc8dc9bdcd7500abd4f0e5032fe96c9bf14",
    "basis_change": "1685ee50eca9cfa61ce94c4d0a9274bc6bd9a27ca1474baf29171ae94cb3284f",
    "week": "e68fba1cb7b6e890f291f09d71101120bb8c7ae0364f0b90c0e6fe6d759d9fa2",
    "pinned": "e573e07b29e7f1dbc9634c8c9862ddffefed2010a82d58247501aba5e0a40287",
}


def c5_reference():
    import os
    import subprocess
    from types import ModuleType
    from pathlib import Path
    source = subprocess.run(
        ["git", "show", f"{C5_BASELINE}:backend/app/financial_metrics_service.py"],
        cwd=Path(__file__).resolve().parents[2], env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        capture_output=True, text=True, check=True).stdout
    module = ModuleType("c5_immutable_financial_reference")
    exec(compile(source, f"{C5_BASELINE}:financial_metrics_service.py", "exec"), module.__dict__)
    return module.FinancialMetrics


def c5_rows(case):
    from datetime import datetime
    from types import SimpleNamespace
    company = SimpleNamespace(cik="0000000001", ticker="TEST", name="C5 synthetic issuer")
    rows = []

    def row(concept="Revenues", value="100", year=2025, **changes):
        fields = dict(id=len(rows)+1, company_cik=company.cik, metric=concept,
            source="SEC Company Facts API: " + concept, value=Decimal(value), unit="USD",
            period_start=date(year, 1, 1), period_end=date(year, 12, 31), period_type="annual",
            fiscal_year=2099, fiscal_period="Q3", form="10-K", filed=date(year+1, 2, 1),
            accession_number=f"0000000001-{year % 100 + 1:02d}-000001", frame=None,
            created_at=datetime(2026, 3, 4, 5, 6, 7, 123456))
        fields.update(changes)
        item = FinancialFact(**fields)
        rows.append(item)
        return item

    for year, revenue in ((2024, "100"), (2025, "120")):
        for concept, value in (("Revenues", revenue), ("GrossProfit", "40"),
                ("OperatingIncomeLoss", "20"), ("NetIncomeLoss", "-10"),
                ("NetCashProvidedByUsedInOperatingActivities", "80"),
                ("PaymentsToAcquirePropertyPlantAndEquipment", "30")):
            row(concept, value, year)
        row("EarningsPerShareDiluted", "1.23456789", year, unit="USD/shares")
        row("Assets", "500", year, period_start=None)
    if case == "rank":
        row("Revenues", "121")  # Same vintage, conflicting value: general selection ranks IDs.
        row("Revenues", "122", frame="CY2025", fiscal_year=2025, fiscal_period="FY")
        row("RevenueFromContractWithCustomerExcludingAssessedTax", "999", filed=date(2026, 3, 1))
        row("Revenues", "777", source="untrusted: Revenues")
        row("Revenues", "888", company_cik="0000000002")
    elif case == "negative_capex":
        row("PaymentsToAcquirePropertyPlantAndEquipment", "-30")
    elif case == "bank":
        rows = []
        row("RevenuesNetOfInterestExpense", "100")
        row("NetIncomeLoss", "20")
        row("GrossProfit", "40")
    elif case == "ambiguous":
        rows = []
        row("RevenueFromContractWithCustomerExcludingAssessedTax", "100")
        row("SalesRevenueNet", "100")
        row("NetIncomeLoss", "20")
    elif case == "bank_conflict":
        row("RevenuesNetOfInterestExpense", "120")
    elif case == "basis_change":
        rows[0].source = "SEC Company Facts API: SalesRevenueNet"
    elif case == "week":
        rows = []
        row(year=2024, period_start=date(2023, 10, 1), period_end=date(2024, 9, 28))
        row(value="110", year=2025, period_start=date(2024, 9, 29), period_end=date(2025, 10, 4))
        row(value="30", year=2025, period_start=date(2024, 12, 29), period_end=date(2025, 3, 29), form="10-Q")
        row(value="60", year=2025, period_start=date(2024, 9, 29), period_end=date(2025, 3, 29), form="10-Q")
    elif case == "pinned":
        company.cik = "0000320193"
        rows = []
        common = dict(period_start=date(2026, 3, 29), period_end=date(2026, 6, 27),
            form="10-Q", filed=date(2026, 7, 31), accession_number="0000320193-26-000020")
        row("RevenueFromContractWithCustomerExcludingAssessedTax", "109417000000", **common)
        row("GrossProfit", "54770000000", **common)
    elif case != "standard":
        raise AssertionError(case)
    return company, rows


def c5_payload(model):
    from app.financial_metric_registry import METRICS
    from app.financial_metric_schemas import FiscalPeriodRequest
    payload = {}
    for kind in ("annual", "quarter", "half_year", "nine_months", "instant"):
        payload[f"summary:{kind}"] = model.summary(kind).model_dump(mode="json")
        for metric in METRICS:
            payload[f"history:{metric}:{kind}"] = model.history(metric, kind).model_dump(mode="json")
    for year in (None, 2024, 2025, 2026):
        payload[f"annual:{year}"] = model.annual_comparison(year).model_dump(mode="json")
    for metric in METRICS:
        for quarter in (None, 1):
            earlier = FiscalPeriodRequest(fiscal_year=2024, quarter=quarter)
            later = FiscalPeriodRequest(fiscal_year=2025, quarter=quarter)
            payload[f"fiscal:{metric}:{quarter}"] = model.fiscal_observation(metric, later).model_dump(mode="json")
            payload[f"comparison:{metric}:{quarter}"] = model.compare_fiscal(metric, earlier, later).model_dump(mode="json")
    payload["base"] = {name: [p.model_dump(mode="json") for p in points] for name, points in model.base.items()}
    return payload


def c5_fingerprint(payload):
    import hashlib
    import json
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@pytest.mark.parametrize("case", ["standard", "rank", "negative_capex", "bank", "ambiguous",
                                  "bank_conflict", "basis_change", "week", "pinned"])
def test_c5_immutable_baseline_serialization(case):
    company, rows = c5_rows(case)
    expected = c5_payload(c5_reference()(company, rows))
    assert c5_fingerprint(expected) == C5_FINGERPRINTS[case]
    assert c5_payload(FinancialMetrics(company, rows)) == expected
    assert c5_payload(FinancialMetrics(company, list(reversed(rows)))) == expected


def test_c5_independent_selection_and_diagnostic_contracts():
    company, rows = c5_rows("rank")
    model = FinancialMetrics(company, rows)
    revenue = model.summary("annual").metrics["revenue"]
    assert revenue.value == Decimal("122")
    assert [p.fact_id for p in revenue.provenance] == [18]
    assert [p.fact_id for p in revenue.alternatives] == [17, 9, 19]
    assert model.facts == rows[:-1] and all(a is b for a, b in zip(model.facts, rows))
    assert model.source("revenue", rows[17]) == revenue.provenance[0]
    company, rows = c5_rows("negative_capex")
    model = FinancialMetrics(company, rows)
    assert model.base["capital_expenditures"][-1].value == Decimal("-30")
    assert model.summary("annual").metrics["free_cash_flow"].value is None
    company, rows = c5_rows("standard")
    metrics = FinancialMetrics(company, rows).summary("annual").metrics
    assert metrics["free_cash_flow"].value == Decimal("50")
    assert metrics["gross_margin"].value == Decimal("0.3333333333333333333333333333")
    assert metrics["revenue_growth_yoy"].value == Decimal(".2")


@pytest.mark.parametrize("path", ["selection", "denominator"])
@pytest.mark.parametrize("changed_start", [False, True])
def test_c5_authorization_parity_complete_original_inventory(monkeypatch, path, changed_start):
    from test_revenue_scope_authorizations import (
        COMPANY, selection_fixture, denominator_fixture, fact,
    )
    rows, proofs, approval = (selection_fixture if path == "selection" else denominator_fixture)(monkeypatch)
    if changed_start:
        rows.append(fact(3, period_start=date(2025, 1, 2)))
    old, new = c5_reference()(COMPANY, rows, authorization_evidence=proofs), FinancialMetrics(COMPANY, rows, authorization_evidence=proofs)
    assert c5_payload(new) == c5_payload(old)
    assert new.selection_approvals == old.selection_approvals
    assert new.selection_rejections == old.selection_rejections
    point = next(p for p in new.history("revenue" if path == "selection" else "net_margin").history
                 if p.period.start == date(2025, 1, 1))
    if changed_start:
        assert point.status == "unavailable" and "candidate_manifest_changed" in point.reason
        assert [p.fact_id for p in point.alternatives] == [1, 2, 3]
    else:
        assert point.scope_authorization.approval_id == approval.ref.approval_id


@pytest.mark.parametrize("value", ["0", "-10"])
def test_c5_nonpositive_denominators_keep_exact_baseline_reasons(value):
    company, rows = c5_rows("standard")
    rows[0].value = rows[8].value = Decimal(value)
    model = FinancialMetrics(company, rows)
    assert c5_payload(model) == c5_payload(c5_reference()(company, rows))
    metrics = model.summary("annual").metrics
    for name in ("gross_margin", "net_margin", "operating_margin", "revenue_growth_yoy"):
        assert metrics[name].value is None and "positive" in metrics[name].reason


@pytest.mark.parametrize("rounding", ["ROUND_DOWN", "ROUND_UP", "ROUND_HALF_EVEN"])
def test_c5_precision_28_preserves_ambient_rounding_without_quantization(rounding):
    from decimal import localcontext
    company, rows = c5_rows("standard")
    rows[8].value, rows[9].value = Decimal("7"), Decimal("2")
    with localcontext() as context:
        context.prec, context.rounding = 6, rounding
        point = FinancialMetrics(company, rows).summary("annual").metrics["gross_margin"]
        assert context.prec == 6 and context.rounding == rounding
        assert point == c5_reference()(company, rows).summary("annual").metrics["gross_margin"]
        with localcontext() as expected_context:
            expected_context.prec = 28
            assert point.value == Decimal("2") / Decimal("7")
        assert len(point.value.as_tuple().digits) == 28


@pytest.mark.parametrize("field,value", [
    ("source", "untrusted: Revenues"), ("unit", "EUR"), ("form", "8-K"),
    ("accession_number", "invalid"), ("filed", date(2024, 1, 1)),
    ("value", Decimal("NaN")), ("period_start", None),
])
def test_c5_source_eligibility_is_preserved_before_conversion(field, value):
    company, rows = c5_rows("standard")
    for fact in rows:
        setattr(fact, field, value)
    model = FinancialMetrics(company, rows)
    assert c5_payload(model) == c5_payload(c5_reference()(company, rows))
    if field != "period_start":
        assert model.summary("annual").metrics["revenue"].value is None


def test_c5_pinned_exception_retains_raw_conflict_and_single_pair_guards():
    from copy import copy
    company, rows = c5_rows("pinned")
    model = FinancialMetrics(company, rows)
    summary = model.summary().metrics
    gross, revenue = summary["gross_profit"], summary["revenue"]
    assert summary["gross_margin"].value == Decimal("0.5005620698794520047159033788")
    changed_value = gross.model_copy(update={"value": Decimal("54770000001")})
    assert model.calculate("gross_margin", (changed_value, revenue), revenue.period, ("gross_profit", "revenue")).value is None
    gross.provenance.append(gross.provenance[0].model_copy())
    assert model.calculate("gross_margin", (gross, revenue), revenue.period, ("gross_profit", "revenue")).value is None
    conflict = copy(rows[1])
    conflict.id = 3
    conflict.value = Decimal("54770000001")
    conflict.frame = "CY2026Q2"
    changed = rows + [conflict]
    assert c5_payload(FinancialMetrics(company, changed)) == c5_payload(c5_reference()(company, changed))
    assert FinancialMetrics(company, changed).summary().metrics["gross_margin"].value is None


@pytest.mark.parametrize("decision", ["fact_id_tie", "total_preference", "formula", "changed_start_inventory", "pinned_conflict"])
def test_c5_decision_mutation_controls_are_detected(monkeypatch, decision):
    """Each intentional wrong decision must trip an independent contract test.

    Mutations affect only this test process, never production files or goldens.
    """
    from dataclasses import replace
    from app import financial_metric_engine as engine
    if decision == "fact_id_tie":
        original_sorted = sorted
        def wrong_sorted(values, *, key=None, reverse=False):
            values = list(values)
            if values and key is not None:
                probe = key(values[0])
                if isinstance(probe, tuple) and len(probe) == 6:
                    actual_key = key
                    key = lambda item: (*actual_key(item)[:-1], -actual_key(item)[-1])
            return original_sorted(values, key=key, reverse=reverse)
        monkeypatch.setattr(engine, "sorted", wrong_sorted, raising=False)
        check = test_c5_independent_selection_and_diagnostic_contracts
    elif decision == "total_preference":
        monkeypatch.setattr(engine.FinancialMetricEngine, "revenue_candidates", lambda self, candidates: candidates)
        check = test_c5_independent_selection_and_diagnostic_contracts
    elif decision == "formula":
        original = engine.FinancialMetricEngine.calculate
        def wrong_formula(*args):
            point = original(*args)
            return replace(point, value=point.value+1) if point.value is not None else point
        monkeypatch.setattr(engine.FinancialMetricEngine, "calculate", wrong_formula)
        check = test_c5_independent_selection_and_diagnostic_contracts
    elif decision == "changed_start_inventory":
        original = FinancialMetrics.authorization_facts
        def incomplete_inventory(self, *args):
            return [f for f in original(self, *args) if f.period_start == date(2025, 1, 1)]
        monkeypatch.setattr(FinancialMetrics, "authorization_facts", incomplete_inventory)
        check = lambda: test_c5_authorization_parity_complete_original_inventory(monkeypatch, "selection", True)
    else:
        monkeypatch.setattr(FinancialMetrics, "reviewed_gross_margin_scope", lambda *args: True)
        def check():
            from copy import copy
            company, rows = c5_rows("pinned")
            conflict = copy(rows[1])
            conflict.id, conflict.value = 3, Decimal("54770000001")
            conflict.frame = "CY2026Q2"
            point = FinancialMetrics(company, rows + [conflict]).summary().metrics["gross_margin"]
            assert point.status == "unavailable" and point.value is None
    with pytest.raises(AssertionError):
        check()


@pytest.mark.parametrize("role,index", [("selected", 17), ("ranked_alternative", 16), ("excluded_alternative", 18)])
@pytest.mark.parametrize("field,value", [
    ("value", Decimal("9999")), ("period_start", date(2025, 1, 2)),
    ("period_end", date(2025, 12, 30)), ("filed", date(2026, 4, 1)),
    ("source", "SEC Company Facts API: SalesRevenueNet"),
    ("accession_number", "0000000001-26-000099"), ("unit", "EUR"),
    ("metric", "changed stored metric"), ("frame", "changed frame"),
    ("fiscal_year", 2025), ("fiscal_period", "FY"),
    ("created_at", datetime(2026, 5, 6, 7, 8, 9)),
])
def test_c5_p2_snapshot_matches_baseline_after_original_row_mutation(role, index, field, value):
    company, rows = c5_rows("rank")
    old, new = c5_reference()(company, rows), FinancialMetrics(company, rows)
    before = c5_payload(old)
    assert c5_payload(new) == before
    setattr(rows[index], field, value)
    assert new.facts[index] is old.facts[index] is rows[index]
    # Retained originals are live for the original authorization/diagnostic helpers.
    assert new.source("revenue", rows[index]) == old.source("revenue", rows[index])
    assert c5_payload(old) == before
    assert c5_payload(new) == before
    base = new.base["revenue"][-1]
    observed = new.observation("revenue", base.period)
    assert observed == base == old.observation("revenue", base.period)
    assert observed.value == observed.provenance[0].value == Decimal("122")
    assert [s.value for s in observed.alternatives] == [Decimal("121"), Decimal("120"), Decimal("999")]


@pytest.mark.parametrize("operand", ["gross_profit", "revenue"])
@pytest.mark.parametrize("field,value,available", [
    ("accession_number", "0000320193-26-000099", False),
    ("original_concept", "SalesRevenueNet", False),
    ("period_start", date(2026, 3, 30), False), ("period_end", date(2026, 6, 26), False),
    ("value", Decimal("1"), False), ("unit", "EUR", False),
    ("company_cik", "0000000002", False), ("form", "10-Q/A", False),
    ("filed", date(2026, 8, 1), False),
    ("source", "changed supplied source annotation", True),
    ("frame", "changed supplied frame", True),
    ("stored_at", datetime(2026, 8, 1, 1, 2, 3), True),
])
def test_c5_p2_helper_preserves_same_id_submitted_provenance(operand, field, value, available):
    company, rows = c5_rows("pinned")
    old, new = c5_reference()(company, rows), FinancialMetrics(company, rows)
    supplied = old.summary().metrics
    gross, revenue = supplied["gross_profit"].model_copy(deep=True), supplied["revenue"].model_copy(deep=True)
    changed = gross if operand == "gross_profit" else revenue
    original_id = changed.provenance[0].fact_id
    changed.provenance[0] = changed.provenance[0].model_copy(update={field: value})
    assert changed.provenance[0].fact_id == original_id
    args = ("gross_margin", (gross, revenue), revenue.period, ("gross_profit", "revenue"))
    expected = old.calculate(*args)
    assert (expected.status == "available") is available
    actual = new.calculate(*args)
    assert actual == expected
    if available:
        assert getattr(actual.provenance[0 if operand == "gross_profit" else 1], field) == value


def test_c5_p2_legitimate_helper_inputs_need_no_local_row_or_input_ancestry_lookup():
    from app.financial_metric_schemas import MetricInput
    company, rows = c5_rows("standard")
    supplied = c5_reference()(company, rows).summary("annual").metrics
    cash, capex = supplied["operating_cash_flow"], supplied["capital_expenditures"]
    cash.inputs = [MetricInput(role="prior derivation", metric=cash.metric, value=cash.value,
                              unit=cash.unit, period=cash.period, fact_ids=[cash.provenance[0].fact_id])]
    args = ("free_cash_flow", (cash, capex), cash.period, (cash.metric, capex.metric))
    expected = c5_reference()(company, []).calculate(*args)
    assert expected.value == Decimal("50")
    assert FinancialMetrics(company, []).calculate(*args) == expected


@pytest.mark.parametrize("field,value", [
    ("value", Decimal("101")), ("period_start", date(2025, 1, 2)),
    ("source", "SEC Company Facts API: SalesRevenueNet"),
    ("accession_number", "0000000001-25-000099"),
])
def test_c5_p2_authorization_diagnostics_still_use_original_rows(monkeypatch, field, value):
    from test_revenue_scope_authorizations import COMPANY, denominator_fixture
    rows, proofs, _ = denominator_fixture(monkeypatch)
    old = c5_reference()(COMPANY, rows, authorization_evidence=proofs)
    new = FinancialMetrics(COMPANY, rows, authorization_evidence=proofs)
    assert old.summary().metrics["net_margin"].status == new.summary().metrics["net_margin"].status == "available"
    setattr(rows[0], field, value)
    assert c5_payload(new) == c5_payload(old)
    expected, actual = old.summary().metrics["net_margin"], new.summary().metrics["net_margin"]
    assert actual == expected and actual.status == "unavailable"
    if actual.alternatives:
        # Rejection diagnostics retain the original operation's live raw inventory;
        # they must not be replaced by the selected/base construction snapshot.
        assert actual.alternatives[0] == old.source("revenue", rows[0])


@pytest.mark.parametrize("local_indices", [(), (0,), (1,)])
def test_c5_p2_missing_local_authorization_operand_keeps_baseline_unavailable(monkeypatch, local_indices):
    from test_revenue_scope_authorizations import COMPANY, denominator_fixture
    rows, proofs, _ = denominator_fixture(monkeypatch)
    supplied = c5_reference()(COMPANY, rows, authorization_evidence=proofs).summary().metrics
    args = ("net_margin", (supplied["net_income"], supplied["revenue"]),
            supplied["revenue"].period, ("net_income", "revenue"))
    local = [rows[i] for i in local_indices]
    expected = c5_reference()(COMPANY, local, authorization_evidence=proofs).calculate(*args)
    assert expected.status == "unavailable"
    assert FinancialMetrics(COMPANY, local, authorization_evidence=proofs).calculate(*args) == expected
