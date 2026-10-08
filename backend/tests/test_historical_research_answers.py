"""Real answer API + normalized financial service, isolated DB and forbidden clients."""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import event

from app import main
from app.financial_metric_registry import METRICS
from app.financial_metric_schemas import FiscalPeriodRequest
from app.models import Company
from test_financial_metrics import db, add, view
from test_research_answers import ask


def annual(db, year, value="100", concept="Revenues", **kwargs):
    return add(db, concept, value, start=f"{year}-01-01", end=f"{year}-12-31",
               filed=date(year + 1, 2, 1), form="10-K", **kwargs)


@pytest.mark.parametrize("question", [
    "2024 revenue", "revenue in 2024", "What was revenue in FY2024?", "2024 annual revenue",
])
def test_explicit_fiscal_year_uses_annual_not_filing_context(db, question):
    row = annual(db, 2024, "100", fiscal_year=2026)
    add(db, value="999", start="2024-04-01", end="2024-06-30", filed=date(2024, 8, 1))
    result = ask(question)
    assert result["answer_kind"] == "historical_metric" and result["status"] == "available"
    assert Decimal(result["observation"]["value"]) == 100
    assert result["observation"]["provenance"][0]["fact_id"] == row.id
    assert result["observation"]["period"]["fiscal_year"] == 2024
    assert result["observation"]["provenance"][0]["source_fiscal_year"] == 2026
    assert "FY2024" in result["answer_text"]


@pytest.mark.parametrize("question", ["Q2 2025 revenue", "2025 Q2 revenue", "revenue in Q2 FY2025"])
def test_direct_fiscal_quarter_never_uses_ytd(db, question):
    annual(db, 2025, "1000")
    add(db, value="250", start="2025-04-01", end="2025-06-30", filed=date(2025, 8, 1))
    add(db, value="450", end="2025-06-30", filed=date(2025, 8, 1))
    result = ask(question)
    assert result["status"] == "available" and Decimal(result["observation"]["value"]) == 250
    assert result["observation"]["period"]["kind"] == "quarter"
    assert result["observation"]["period"]["fiscal_period"] == "Q2"


@pytest.mark.parametrize("question", [
    "2024 vs 2025 revenue", "compare 2024 and 2025 revenue", "revenue from 2024 to 2025",
    "2024-2025 revenue growth", "2024–2025 revenue growth", "revenue growth from 2024 to 2025",
    "how much did revenue grow from 2024 to 2025?", "did revenue increase from 2024 to 2025?",
    "What was revenue growth from 2024 to 2025?", "2025 vs 2024 revenue",
])
def test_comparison_uses_exact_annual_values_and_both_provenances(db, question):
    left, right = annual(db, 2024, "100"), annual(db, 2025, "108.3")
    result = ask(question)
    assert result["answer_kind"] == "period_comparison" and result["status"] == "available"
    assert result["observation"] is None
    comparison = result["comparison"]
    assert Decimal(comparison["absolute_change"]) == Decimal("8.3")
    assert Decimal(comparison["percentage_change"]) == Decimal("0.083")
    assert comparison["earlier"]["provenance"][0]["fact_id"] == left.id
    assert comparison["later"]["provenance"][0]["fact_id"] == right.id
    assert comparison["direction"] == "increase" and result["formatted_value"] == "+8.30%"
    if question.lower().startswith("did"):
        assert result["answer_text"].startswith("Yes.")


@pytest.mark.parametrize("earlier,later,absolute,pct,direction", [
    ("0", "10", "10", None, "increase"),
    ("-10", "-5", "5", None, "increase"),
    ("-10", "5", "15", None, "increase"),
    ("10", "-5", "-15", "-1.5", "decrease"),
    ("10", "0", "-10", "-1", "decrease"),
    ("10", "10", "0", "0", "no_change"),
])
def test_comparison_zero_negative_equal_values(db, earlier, later, absolute, pct, direction):
    annual(db, 2024, earlier, "NetIncomeLoss")
    annual(db, 2025, later, "NetIncomeLoss")
    result = ask("how much did net income change between 2024 and 2025?")
    assert result["status"] == "available"
    comparison = result["comparison"]
    assert Decimal(comparison["absolute_change"]) == Decimal(absolute)
    assert comparison["direction"] == direction
    if pct is None:
        assert comparison["percentage_change"] is None and comparison["percentage_status"] == "unavailable"
        assert "positive earlier value" in comparison["percentage_reason"]
    else:
        assert Decimal(comparison["percentage_change"]) == Decimal(pct)


def test_quarter_comparison_retains_jpm_bank_basis(db):
    annual(db, 2024, "400", "RevenuesNetOfInterestExpense")
    annual(db, 2025, "450", "RevenuesNetOfInterestExpense")
    for year, value in [(2024, "100"), (2025, "110")]:
        add(db, "RevenuesNetOfInterestExpense", value, start=f"{year}-04-01", end=f"{year}-06-30", filed=date(year, 8, 1))
    result = ask("compare Q2 2024 and Q2 2025 revenue")
    assert result["status"] == "available"
    for side in ["earlier", "later"]:
        assert result["comparison"][side]["revenue_basis"] == "net_interest"
    assert ask("2024 gross margin")["status"] == "not_applicable"


def test_incompatible_revenue_bases_are_not_forced_cost_shape(db):
    annual(db, 2024, "100", "Revenues")
    annual(db, 2025, "110", "SalesRevenueNet")
    result = ask("2024-2025 revenue growth")
    assert result["status"] == "unavailable" and result["comparison"]["absolute_change"] is None
    assert "economic bases" in result["explanation"]
    assert result["comparison"]["earlier"]["provenance"] and result["comparison"]["later"]["provenance"]


def test_margin_comparison_preserves_inputs_and_uses_percentage_points(db):
    for year, revenue, income in [(2024, "100", "20"), (2025, "200", "50")]:
        annual(db, year, revenue)
        annual(db, year, income, "OperatingIncomeLoss")
    result = ask("compare 2024 and 2025 operating margin")
    assert result["status"] == "available"
    assert Decimal(result["comparison"]["absolute_change"]) == Decimal("0.05")
    assert result["formatted_value"] == "+5.00 percentage points"
    assert result["comparison"]["percentage_status"] == "not_applicable"
    assert len(result["comparison"]["earlier"]["inputs"]) == 2


def test_derived_scope_compatibility_uses_registry(db, monkeypatch):
    # A future approved margin denominator must not automatically authorize
    # comparing different revenue bases across periods.
    from app.financial_metric_registry import REVENUE_CONCEPTS, RevenueConcept
    monkeypatch.setitem(REVENUE_CONCEPTS, "SalesRevenueNet", RevenueConcept("net_sales", "fixture", True))
    for year, concept in [(2024, "Revenues"), (2025, "SalesRevenueNet")]:
        annual(db, year, "100", concept)
        annual(db, year, "20", "OperatingIncomeLoss")
    assert ask("compare 2024 and 2025 operating margin")["status"] == "unavailable"


def test_eps_as_filed_warning_no_percentage_claim(db):
    for year, value in [(2024, "1.2345"), (2025, "2.3")]:
        annual(db, year, value, "EarningsPerShareDiluted", unit="USD/shares")
    historical = ask("2025 diluted EPS")
    assert historical["status"] == "available" and historical["comparability"]["status"] == "unverified"
    comparison = ask("2024 vs 2025 diluted EPS")
    assert comparison["status"] == "available" and comparison["comparability"]["value_basis"] == "reported_as_filed"
    assert comparison["comparison"]["percentage_status"] == "not_applicable"
    assert Decimal(comparison["comparison"]["earlier"]["value"]) == Decimal("1.2345")


def test_no_q4_synthesis_no_ytd_and_no_wrong_year(db):
    annual(db, 2024)
    add(db, value="25", start="2024-01-01", end="2024-06-30", filed=date(2024, 8, 1))
    for question in ["Q2 2024 revenue", "Q4 2024 revenue", "2023 revenue", "2024 vs 2027 revenue"]:
        result = ask(question)
        assert result["matched"] and result["status"] == "unavailable"
        assert result["formatted_value"] is None


def test_unlabeled_sparse_quarter_does_not_guess_fiscal_year_xom_shape(db):
    add(db, value="50", start="2025-04-01", end="2025-06-30", filed=date(2025, 8, 1))
    assert ask("Q2 2025 revenue")["status"] == "unavailable"
    assert ask("2025 revenue")["status"] == "unavailable"
    assert ask("latest quarterly revenue")["status"] == "available"


def test_multiple_annual_dates_for_one_fiscal_label_are_ambiguous(db):
    annual(db, 2024)
    add(db, value="999", start="2023-10-01", end="2024-09-30", filed=date(2025, 1, 1), form="10-K")
    result = ask("2024 revenue")
    assert result["status"] == "unavailable" and "ambiguous" in result["explanation"]


def test_latest_filing_vintage_is_traceable_not_averaged(db):
    original = annual(db, 2024, "100")
    restated = add(db, value="110", start="2024-01-01", end="2024-12-31", filed=date(2026, 2, 1), form="10-K/A")
    point = ask("2024 revenue")["observation"]
    assert Decimal(point["value"]) == 110 and point["provenance"][0]["fact_id"] == restated.id
    assert point["alternatives"][0]["fact_id"] == original.id


def test_instant_metric_uses_requested_reporting_end_not_duration(db):
    annual(db, 2024)
    add(db, "Assets", "500", start=None, end="2024-12-31", filed=date(2025, 2, 1))
    result = ask("2024 total assets")
    assert result["status"] == "available" and result["observation"]["period"]["kind"] == "instant"
    assert "as of 2024-12-31" in result["answer_text"]


@pytest.mark.parametrize("question", [
    "Why did revenue grow from 2024 to 2025?", "What caused margin decline?", "What is Apple's main product?",
    "What are Apple's biggest risks?", "2024 revenue and net income", "2024 2025 revenue", "2024 revenue trend",
    "2024 revenue forecast", "calendar 2024 revenue", "revenue in March 2024", "revenue as of June 2024",
    "How is 2024 revenue reported?", "What accounting method was used for 2024 revenue?",
    "How much 2024 revenue and how was it reported?", "2024 vs 2024 revenue", "Q2 revenue",
    "revenue from 2025 to 2024", "2024 Q2 annual revenue", "2024 services revenue", "2024 revenue per employee",
])
def test_unsupported_historical_intents_stay_evidence_research(db, question):
    assert ask(question)["status"] == "not_matched"


def test_selected_company_mismatch_and_bounded_versioned_selects(db):
    db[0].add(Company(ticker="MSFT", name="Microsoft Corp", cik="0000789019", exchange="NASDAQ"))
    db[0].commit()
    assert ask("Microsoft revenue in 2025")["status"] == "company_mismatch"
    annual(db, 2024)
    annual(db, 2025, "110")
    queries = []
    def record(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            queries.append(statement)
    engine = db[0].get_bind()
    event.listen(engine, "before_cursor_execute", record)
    try:
        assert ask("2024-2025 revenue growth")["status"] == "available"
        assert len(queries) == 3  # version + catalog + facts
    finally:
        event.remove(engine, "before_cursor_execute", record)


def test_period_kind_mixing_cannot_compare_even_service_directly(db):
    annual(db, 2024)
    annual(db, 2025)
    add(db, value="20", start="2025-04-01", end="2025-06-30", filed=date(2025, 8, 1))
    result = view(db).compare_fiscal("revenue", FiscalPeriodRequest(fiscal_year=2024), FiscalPeriodRequest(fiscal_year=2025, quarter=2))
    assert result.status == "unavailable" and result.absolute_change is None


@pytest.mark.parametrize("metric", list(METRICS))
def test_all_canonical_metrics_have_historical_api_routing(db, metric):
    from app.research_answer_service import QUESTION_TERMS
    annual(db, 2024)
    result = ask(f"2024 {QUESTION_TERMS[metric][1][0]}")
    assert result["matched"] and result["metric"] == metric
    assert result["answer_kind"] == "historical_metric"


def test_changed_fiscal_calendar_is_not_silently_comparable(db):
    annual(db, 2024)
    add(db, value="110", start="2024-10-01", end="2025-09-30", filed=date(2025, 11, 1), form="10-K")
    result = ask("2024 vs 2025 revenue")
    assert result["status"] == "unavailable" and "boundaries do not align" in result["explanation"]


def test_direction_no_answer_still_shows_values(db):
    annual(db, 2024, "100")
    annual(db, 2025, "90")
    result = ask("did revenue increase from 2024 to 2025?")
    assert result["answer_text"].startswith("No.")
    assert "$100.00" in result["answer_text"] and "$90.00" in result["answer_text"]


@pytest.mark.parametrize("question", [
    "2022 vs 2025 year over year revenue growth",
    "2022-2025 YoY revenue growth",
    "Compare FY2022 and FY2025 YoY revenue growth",
    "2022-2025 revenue growth yoy",
    "revenue growth from 2022 to 2025 year-over-year",
    "from Q2 FY2022 to Q2 FY2025 YoY revenue growth",
    "Compare FY2024 and FY2025 YoY revenue growth",
    "2024 vs 2025 year over year revenue growth",
    "compare year over year revenue growth between 2024 and 2025",
    "from Q1 FY2024 to Q2 FY2025 YoY revenue growth",
    "Why did year over year revenue growth increase from 2024 to 2025?",
    "2022-2025 annualized revenue growth",
    "2022-2025 revenue CAGR",
])
def test_yoy_ambiguous_rate_comparisons_and_unsupported_growth_reject_via_api(db, question):
    # All relevant years exist: rejection must be about intent, not missing data.
    for year, value in [(2022, "80"), (2023, "90"), (2024, "100"), (2025, "110")]:
        annual(db, year, value)
    result = ask(question)
    assert result["status"] == "not_matched" and not result["matched"]
    assert result["comparison"] is None and result["formatted_value"] is None


@pytest.mark.parametrize("question", [
    "2024-2025 revenue growth",
    "2024-2025 YoY revenue growth",
    "2024-2025 year over year revenue growth",
    "2024-2025 year-over-year revenue growth",
    "2024-2025 revenue growth yoy",
    "revenue growth from 2024 to 2025 year over year",
])
def test_yoy_adjacent_year_interval_preserves_exact_comparison_via_api(db, question):
    left, right = annual(db, 2024, "100"), annual(db, 2025, "110")
    result = ask(question)
    assert result["status"] == "available" and result["metric"] == "revenue"
    assert Decimal(result["comparison"]["absolute_change"]) == 10
    assert Decimal(result["comparison"]["percentage_change"]) == Decimal("0.1")
    assert result["comparison"]["earlier"]["provenance"][0]["fact_id"] == left.id
    assert result["comparison"]["later"]["provenance"][0]["fact_id"] == right.id
    if "yoy" in question.lower() or "year over year" in question.lower() or "year-over-year" in question.lower():
        assert "Year-over-year change." in result["answer_text"]


@pytest.mark.parametrize("question", ["2022-2025 revenue growth", "2022 vs 2025 revenue"])
def test_multiyear_growth_is_explicitly_cumulative_via_api(db, question):
    annual(db, 2022, "80")
    annual(db, 2025, "100")
    result = ask(question)
    assert result["status"] == "available" and result["formatted_value"] == "+25.00%"
    assert "cumulative period-to-period" in result["answer_text"].lower()
    assert "yoy" not in result["answer_text"].lower()
    assert "annualized" not in result["answer_text"].lower()


@pytest.mark.parametrize("question", [
    "2024-2025 YoY revenue growth", "2024-2025 year over year revenue growth",
])
@pytest.mark.parametrize("problem", ["missing", "incompatible"])
def test_yoy_qualified_growth_keeps_missing_and_basis_checks_via_api(db, question, problem):
    annual(db, 2024, "100")
    if problem == "incompatible":
        annual(db, 2025, "110", "SalesRevenueNet")
    result = ask(question)
    assert result["matched"] and result["status"] == "unavailable"
    assert result["comparison"]["absolute_change"] is None
    assert result["formatted_percentage_change"] is None
    assert ("economic bases" if problem == "incompatible" else "requested fiscal") in result["explanation"]


def test_yoy_single_period_and_explicit_quarter_keep_existing_metric_semantics(db):
    annual(db, 2024, "100")
    annual(db, 2025, "110")
    single = ask("2025 yoy revenue growth")
    assert single["status"] == "available" and single["metric"] == "revenue_growth_yoy"
    assert Decimal(single["observation"]["value"]) == Decimal("0.1")
    for year, value in [(2024, "20"), (2025, "25")]:
        add(db, value=value, start=f"{year}-04-01", end=f"{year}-06-30", filed=date(year, 8, 1))
    quarter = ask("from Q2 FY2024 to Q2 FY2025 YoY revenue growth")
    assert quarter["status"] == "available" and quarter["formatted_value"] == "+25.00%"
    assert quarter["comparison"]["earlier"]["period"]["kind"] == "quarter"
    assert quarter["comparison"]["later"]["period"]["kind"] == "quarter"


def test_yoy_qualified_question_keeps_company_mismatch_protection(db):
    db[0].add(Company(ticker="MSFT", name="Microsoft Corp", cik="0000789019", exchange="NASDAQ"))
    db[0].commit()
    result = ask("Microsoft 2024-2025 YoY revenue growth")
    assert result["status"] == "company_mismatch" and not result["matched"]


@pytest.mark.parametrize("question", [
    "Did YoY revenue growth increase from 2024 to 2025?",
    "How much did YoY revenue growth change from 2024 to 2025?",
    "Did revenue growth decrease from 2024 to 2025?",
    "How much did revenue growth grow from 2024 to 2025?",
    "Did TEST's revenue growth rate increase from 2024 to 2025?",
    "What was the change in year-over-year revenue growth from 2024 to 2025?",
    "Did year-to-year sales growth increase from 2024 to 2025?",
    "Compare FY2024 and FY2025 YoY revenue growth",
    "2022-2025 year-to-year revenue growth",
    "revenue growth from 2022 to 2025 year-to-year",
    "2022-2025 year to year revenue growth",
    "FY2022 vs FY2025 YEAR-TO-YEAR revenue growth?",
    "2022–2025 year.to.year revenue growth",
    "2022-2025 revenue growth (%/year)",
    "2022-2025 revenue growth/year",
    "2022-2025 revenue growth (% / year)",
    "2022-2025 revenue growth / yr",
    "2022-2025 revenue growth / fiscal year",
    "latest revenue growth/year",
    "revenue growth (% / year)",
    "2022-2025 revenue growth per year",
    "2022-2025 annualized revenue growth",
    "2022-2025 revenue CAGR",
    "Why did revenue increase from 2024 to 2025?",
    "How is TEST's 2024 revenue reported?",
    "2024-2025 revenue and net income",
])
def test_math_intent_rejections_via_api(db, question):
    for year, value in [(2022, "40"), (2023, "50"), (2024, "100"), (2025, "110")]:
        annual(db, year, value)
    # Revenue rises while its independently computed YoY rate falls.
    assert Decimal(ask("2024 YoY revenue growth")["observation"]["value"]) == 1
    assert Decimal(ask("2025 YoY revenue growth")["observation"]["value"]) == Decimal("0.1")
    result = ask(question)
    assert result["status"] == "not_matched" and not result["matched"]
    assert result["comparison"] is None and result["formatted_value"] is None


@pytest.mark.parametrize("question", [
    "Did revenue increase from 2024 to 2025?",
    "How much did revenue grow from 2024 to 2025?",
    "What was revenue growth from 2024 to 2025?",
    "2024-2025 revenue growth",
    "2024-2025 YoY revenue growth",
    "2024-2025 year-to-year revenue growth",
    "revenue growth from 2024 to 2025 YEAR TO YEAR",
    "What was the % change in revenue from 2024 to 2025?",
    "2024-2025 revenue change (%)",
])
def test_math_intent_supported_level_changes_via_api(db, question):
    left, right = annual(db, 2024, "100"), annual(db, 2025, "110")
    result = ask(question)
    assert result["status"] == "available" and result["formatted_percentage_change"] == "+10.00%"
    assert result["comparison"]["earlier"]["provenance"][0]["fact_id"] == left.id
    assert result["comparison"]["later"]["provenance"][0]["fact_id"] == right.id
    if "year" in question.lower() or "yoy" in question.lower():
        assert "Year-over-year change." in result["answer_text"]


@pytest.mark.parametrize("question", [
    "What was the % change in operating margin from 2024 to 2025?",
    "2024-2025 operating margin change (%)",
    "What was the percentage change in operating margin from 2024 to 2025?",
    "What was the percent change in operating margin from 2024 to 2025?",
    "2024-2025 operating margin % increase",
    "2024-2025 operating margin change ( % )",
])
def test_math_intent_relative_margin_change_rejects_via_api(db, question):
    for year, revenue, income in [(2024, "100", "20"), (2025, "110", "27.5")]:
        annual(db, year, revenue)
        annual(db, year, income, "OperatingIncomeLoss")
    ordinary = ask("2024-2025 operating margin change")
    assert ordinary["status"] == "available"
    assert ordinary["formatted_absolute_change"] == "+5.00 percentage points"
    assert ordinary["formatted_percentage_change"] is None
    assert Decimal(ordinary["comparison"]["earlier"]["value"]) == Decimal("0.2")
    assert Decimal(ordinary["comparison"]["later"]["value"]) == Decimal("0.25")
    assert ask(question)["status"] == "not_matched"


@pytest.mark.parametrize("problem", ["missing", "incompatible"])
def test_math_intent_year_to_year_preserves_unavailable_via_api(db, problem):
    annual(db, 2024, "100")
    if problem == "incompatible":
        annual(db, 2025, "110", "SalesRevenueNet")
    result = ask("2024-2025 year-to-year revenue growth")
    assert result["matched"] and result["status"] == "unavailable"
    assert result["comparison"]["absolute_change"] is None


def test_math_intent_mismatch_precedes_unsupported_math_via_api(db):
    db[0].add(Company(ticker="MSFT", name="Microsoft Corp", cik="0000789019", exchange="NASDAQ"))
    db[0].commit()
    assert ask("Microsoft 2022-2025 revenue growth (%/year)")["status"] == "company_mismatch"


def test_math_intent_ordinary_multiyear_is_cumulative_via_api(db):
    annual(db, 2022, "40")
    annual(db, 2025, "110")
    result = ask("2022-2025 revenue growth")
    assert result["formatted_percentage_change"] == "+175.00%"
    assert "Cumulative period-to-period change." in result["answer_text"]
    assert "Year-over-year" not in result["answer_text"]


# Metamorphic API cases: harmless typography must preserve mathematical intent.
def math_wording(question, variant):
    if variant == "caps":
        return question.upper()
    if variant == "spacing":
        return "  " + "  ".join(question.split()) + "  "
    if variant == "punctuation":
        return question.replace("'", "’").replace("-", "–").replace("growth", "(growth)")
    return question


@pytest.mark.parametrize("variant", ["plain", "caps", "spacing", "punctuation"])
@pytest.mark.parametrize("question", [
    "Did revenue's growth decrease from 2024 to 2025?",
    "How much did the growth in revenue change from 2024 to 2025?",
    "Did the growth of revenue decrease from 2024 to 2025?",
    "How much did growth in sales grow from 2024 to 2025?",
    "Did revenue's growth increase from 2024 to 2025?",
    "Did revenue growth change from 2024 to 2025?",
    "Did YoY revenue growth decrease from 2024 to 2025?",
    "Did revenue growth rate increase from 2024 to 2025?",
    "How much did the revenue growth rate change from 2024 to 2025?",
])
def test_preflight_growth_operand_api(db, question, variant):
    for year, value in [(2023, "50"), (2024, "100"), (2025, "110")]:
        annual(db, year, value)
    assert Decimal(ask("2024 YoY revenue growth")["observation"]["value"]) == 1
    assert Decimal(ask("2025 YoY revenue growth")["observation"]["value"]) == Decimal("0.1")
    result = ask(math_wording(question, variant))
    assert result["status"] == "not_matched" and not result["matched"]
    assert result["comparison"] is None and result["formatted_value"] is None


@pytest.mark.parametrize("variant", ["plain", "caps", "spacing", "punctuation"])
@pytest.mark.parametrize("question", [
    "How much did operating margin grow from 2024 to 2025 (%)?",
    "2024-2025 operating margin grew (%)",
    "2024-2025 operating margin increase (%)",
    "2024-2025 operating margin decrease (%)",
    "2024-2025 operating margin change (%)",
    "2024-2025 operating margin growth (%)",
    "How much did operating margin grow from 2024 to 2025 percent?",
    "2024-2025 operating margin grew (percentage)",
    "2024-2025 operating margin (%)",
])
def test_preflight_relative_margin_api(db, question, variant):
    for year, revenue, income in [(2024, "100", "20"), (2025, "110", "27.5")]:
        annual(db, year, revenue)
        annual(db, year, income, "OperatingIncomeLoss")
    result = ask(math_wording(question, variant))
    assert result["status"] == "not_matched" and result["formatted_value"] is None
    ordinary = ask("Compare operating margin in 2024 and 2025.")
    assert ordinary["status"] == "available"
    assert ordinary["formatted_absolute_change"] == "+5.00 percentage points"
    assert ordinary["formatted_percentage_change"] is None


@pytest.mark.parametrize("variant", ["plain", "caps", "spacing", "punctuation"])
@pytest.mark.parametrize("qualifier", [
    "(% / fiscal-year)", "(% / (year))", "(% / (fiscal-year))",
    "%/year", "% / yr", "per-year", "per fiscal year", "/calendar-year",
    "annualized", "CAGR", "(% / ((year)))",
])
def test_preflight_annualized_api(db, qualifier, variant):
    annual(db, 2022, "40")
    annual(db, 2025, "110")
    result = ask(math_wording(f"2022-2025 revenue growth {qualifier}", variant))
    assert result["status"] == "not_matched" and result["comparison"] is None
    cumulative = ask("2022-2025 revenue growth")
    assert cumulative["formatted_percentage_change"] == "+175.00%"
    assert "Cumulative period-to-period change." in cumulative["answer_text"]


@pytest.mark.parametrize("variant", ["plain", "caps", "spacing", "punctuation"])
@pytest.mark.parametrize("question", [
    "Did revenue increase from 2024 to 2025?",
    "How much did revenue grow from 2024 to 2025?",
    "What was revenue growth from 2024 to 2025?",
    "What was the % change in revenue from 2024 to 2025?",
    "2024-2025 YoY revenue growth",
    "2024-2025 year-to-year revenue growth",
])
def test_preflight_supported_levels_api(db, question, variant):
    left, right = annual(db, 2024, "100"), annual(db, 2025, "110")
    result = ask(math_wording(question, variant))
    assert result["status"] == "available" and result["formatted_percentage_change"] == "+10.00%"
    assert result["comparison"]["earlier"]["provenance"][0]["fact_id"] == left.id
    assert result["comparison"]["later"]["provenance"][0]["fact_id"] == right.id


@pytest.mark.parametrize("question", [
    "Compare operating margin in 2024 and 2025.",
    "Operating margin change from 2024 to 2025.",
    "How much did operating margin grow from 2024 to 2025?",
    "2024-2025 operating margin grew",
])
def test_preflight_ordinary_margin_points_api(db, question):
    for year, revenue, income in [(2024, "100", "20"), (2025, "110", "27.5")]:
        annual(db, year, revenue)
        annual(db, year, income, "OperatingIncomeLoss")
    result = ask(question)
    assert result["status"] == "available"
    assert result["formatted_absolute_change"] == "+5.00 percentage points"
    assert result["formatted_percentage_change"] is None


@pytest.mark.parametrize("question", [
    "2024-2025 revenue growth (percentage points)",
    "2022-2025 revenue growth / something",
    "How much did revenue grow and how was it reported from 2024 to 2025?",
    "Why did revenue's growth decrease from 2024 to 2025?",
    "2022-2025 year-to-year revenue growth",
])
def test_preflight_unsupported_and_ambiguous_api(db, question):
    annual(db, 2022, "40")
    annual(db, 2024, "100")
    annual(db, 2025, "110")
    assert ask(question)["status"] == "not_matched"
