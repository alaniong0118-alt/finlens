"""Permanent deterministic-answer regressions: synthetic SEC-shaped ORM fixtures.

Real-data acceptance is separately recorded by the read-only verifier. These
tests forbid both SEC/provider requests and never use the real database.
"""
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from app import main
from app.models import Company
from app.research_answer_service import QUESTION_TERMS, format_value, recognize, resolve_answer
from test_financial_metrics import db, add, view  # shared isolated fixture


def ask(question, ticker="TEST"):
    response = TestClient(main.app).post(f"/companies/{ticker}/research-answer", json={"question": question})
    assert response.status_code == 200
    return response.json()


@pytest.mark.parametrize("metric,definition", QUESTION_TERMS.items())
def test_every_explicit_alias_and_period(metric, definition):
    company = Company(ticker="AAPL", name="Apple Inc.", cik="0000320193")
    for term in definition[1]:
        for scope, intent in [("latest quarterly", "quarter"), ("annual", "annual"), ("latest available", "latest_available")]:
            assert recognize(f"What was Apple's {scope} {term}?", company, [company]) == (metric, intent, None)


@pytest.mark.parametrize("question", [
    "What is Apple's main product?", "What are Apple's biggest risks?", "Why is AI demand increasing?",
    "What clinical trial results did Apple report?", "What drove revenue growth?",
    "Why did sales increase?", "services revenue", "iPhone sales", "segment profit",
    "revenue in 2024", "Q1 revenue", "revenue last quarter", "revenue next year", "current quarter revenue",
    "gross profit vs net income", "gross or net margin", "profit margin", "cash flow", "basic EPS",
    "What will revenue be?", "quarterly annual revenue", "revenue and revenue", "revenue trend",
    "revenue growth QoQ", "revenue per employee", "adjusted earnings", "sales forecast",
])
def test_unsupported_and_ambiguous_do_not_overmatch(question):
    company = Company(ticker="AAPL", name="Apple Inc.", cik="0000320193")
    assert recognize(question, company, [company])[2] == "not_matched"


@pytest.mark.parametrize("question", [
    "How is Apple's revenue reported?", "How does Apple report revenue?",
    "How is Apple's net income reported?", "How did Apple report net income?",
    "How was Apple's quarterly revenue reported?", "How is Apple reporting revenue?",
    "Tell me how Apple reported revenue.", "How is revenue accounted for?",
    "What accounting method does Apple use to report revenue?",
    "What is Apple's revenue reporting policy?",
    "What is Apple's revenue reporting?", "What is reporting revenue?",
    "How much revenue did Apple report and how was it reported?",
    "What is Apple's main product?", "What drove revenue growth?",
    "services revenue", "revenue in March 2024", "revenue and net income",
])
def test_method_and_unsupported_questions_return_evidence_fallback(db, question):
    db[1].ticker, db[1].name = "AAPL", "Apple Inc."
    db[0].commit()
    add(db)
    add(db, "NetIncomeLoss", "20")
    result = ask(question, "AAPL")
    assert result["status"] == "not_matched" and result["matched"] is False
    assert result["metric"] is None and result["observation"] is None
    assert result["answer_text"] is None


@pytest.mark.parametrize("question,metric,intent", [
    ("How much revenue did Apple report?", "revenue", "latest_available"),
    ("How much net income did Apple report?", "net_income", "latest_available"),
    ("What revenue did Apple report?", "revenue", "latest_available"),
    ("What was Apple's reported revenue?", "revenue", "latest_available"),
    ("What was Apple's reported net income?", "net_income", "latest_available"),
    ("How much quarterly revenue did Apple report?", "revenue", "quarter"),
    ("What was Apple's reported quarterly revenue?", "revenue", "quarter"),
    ("How much revenue is Apple reporting?", "revenue", "latest_available"),
    ("What revenue is Apple reporting?", "revenue", "latest_available"),
    ("Tell me how much revenue Apple reported.", "revenue", "latest_available"),
])
def test_reported_value_questions_keep_numeric_answers(db, question, metric, intent):
    db[1].ticker, db[1].name = "AAPL", "Apple Inc."
    db[0].commit()
    add(db)
    add(db, "NetIncomeLoss", "20")
    result = ask(question, "AAPL")
    assert result["status"] == "available" and result["matched"] is True
    assert result["metric"] == metric and result["period_intent"] == intent
    assert Decimal(result["observation"]["value"]) == Decimal("100" if metric == "revenue" else "20")
    assert result["observation"]["provenance"]


def test_aapl_quarterly_real_shape_value_provenance_no_ai(db):
    db[1].ticker, db[1].name, db[1].cik = "AAPL", "Apple Inc.", "0000320193"
    db[0].commit()
    fact = add(db, "RevenueFromContractWithCustomerExcludingAssessedTax", "109417000000",
               start="2026-03-29", end="2026-06-27", filed=date(2026, 7, 31), accession_number="0000320193-26-000077")
    result = ask("What was Apple's latest quarterly revenue?", "aapl")
    assert result["matched"] and result["status"] == "available"
    assert result["metric"] == "revenue" and result["period_intent"] == "quarter"
    assert result["formatted_value"] == "$109.42B"
    point = result["observation"]
    assert Decimal(point["value"]) == Decimal("109417000000") and point["period"]["end"] == "2026-06-27"
    source = point["provenance"][0]
    assert source["fact_id"] == fact.id and source["company_cik"] == "0000320193"
    assert source["filed"] == "2026-07-31" and source["form"] == "10-Q"
    assert source["sec_url"].startswith("https://www.sec.gov/Archives/edgar/data/320193/")
    assert "June 27, 2026" in result["answer_text"]


def test_jpm_net_interest_revenue_basis_retained(db):
    add(db, "RevenuesNetOfInterestExpense", "200")
    result = ask("latest quarterly revenue")
    assert Decimal(result["observation"]["value"]) == Decimal("200")
    assert result["observation"]["revenue_basis"] == "net_interest"
    assert result["observation"]["provenance"][0]["original_concept"] == "RevenuesNetOfInterestExpense"


def test_cost_incompatible_growth_remains_unavailable(db):
    add(db, "Revenues", "100", start="2024-01-01", end="2024-03-31", filed=date(2024, 5, 1))
    add(db, "SalesRevenueNet", "150")
    result = ask("latest quarterly revenue growth")
    assert result["status"] == "unavailable" and result["formatted_value"] is None
    assert result["observation"]["value"] is None
    assert result["explanation"] == "Current/prior revenue economic bases are not explicitly comparable."
    assert result["explanation"] in result["answer_text"]


def test_eps_warning_exact_source_and_units(db):
    add(db, "EarningsPerShareDiluted", "1.2345", unit="USD/shares")
    result = ask("latest diluted earnings per share")
    assert result["formatted_value"] == "$1.23 per share"
    assert result["comparability"]["status"] == "unverified"
    assert result["comparability"]["value_basis"] == "reported_as_filed"
    assert result["observation"]["provenance"][0]["value"] == "1.2345"
    assert result["observation"]["unit"] == "USD/share"


def test_explicit_annual_and_latest_available_do_not_relabel_ytd(db):
    add(db, value="60", start="2024-01-01", end="2024-12-31", filed=date(2025, 2, 1), form="10-K")
    add(db, value="10")
    add(db, value="25", end="2025-06-30", filed=date(2025, 8, 1))
    annual = ask("annual revenue")
    assert annual["observation"]["value"] is not None and Decimal(annual["observation"]["value"]) == Decimal("60") and annual["observation"]["period"]["kind"] == "annual"
    quarter = ask("quarterly revenue")
    assert quarter["observation"]["value"] is not None and Decimal(quarter["observation"]["value"]) == Decimal("10")
    latest = ask("latest revenue")
    assert latest["observation"]["value"] is not None and Decimal(latest["observation"]["value"]) == Decimal("25") and latest["observation"]["period"]["kind"] == "half_year"
    assert "six-month YTD period" in latest["answer_text"]
    assert "quarter" not in latest["answer_text"]


def test_latest_tie_prefers_direct_quarter(db):
    add(db, value="25", end="2025-06-30", filed=date(2025, 8, 1))
    add(db, value="15", start="2025-04-01", end="2025-06-30", filed=date(2025, 8, 1))
    assert ask("latest revenue")["observation"]["period"]["kind"] == "quarter"


def test_quarter_never_substitutes_annual_or_older_metric(db):
    add(db, value="60", start="2024-01-01", end="2024-12-31", filed=date(2025, 2, 1), form="10-K")
    assert ask("quarterly revenue")["status"] == "unavailable"
    add(db, value="10")
    add(db, "NetIncomeLoss", "3")
    add(db, value="15", start="2025-04-01", end="2025-06-30", filed=date(2025, 8, 1))
    result = ask("quarterly net income")
    assert result["status"] == "unavailable" and result["observation"]["period"]["end"] == "2025-06-30"


def test_latest_growth_does_not_backfill_available_old_period(db):
    add(db, value="100", start="2024-01-01", end="2024-03-31", filed=date(2024, 5, 1))
    add(db, value="110")
    add(db, "SalesRevenueNet", "150", start="2025-04-01", end="2025-06-30", filed=date(2025, 8, 1))
    result = ask("latest revenue growth")
    assert result["status"] == "unavailable" and result["observation"]["period"]["end"] == "2025-06-30"


def test_instant_metric_is_honestly_as_of_not_quarter_flow(db):
    add(db)
    add(db, "Assets", "500", start=None)
    latest = ask("latest total assets")
    quarterly = ask("quarterly total assets")
    for result in (latest, quarterly):
        assert result["observation"]["period"]["kind"] == "instant"
        assert "as of March 31, 2025" in result["answer_text"]
        assert "quarter ended" not in result["answer_text"]
    assert "quarterly reporting date" in quarterly["answer_text"]


def test_annual_balance_sheet_date_is_not_claimed_as_latest_overall(db):
    add(db, value="60", start="2024-01-01", end="2024-12-31", filed=date(2025, 2, 1), form="10-K")
    add(db, "Assets", "450", start=None, end="2024-12-31", filed=date(2025, 2, 1), form="10-K")
    add(db)
    add(db, "Assets", "500", start=None)
    annual = ask("annual total assets")
    latest = ask("latest total assets")
    assert annual["observation"]["period"]["end"] == "2024-12-31"
    assert "as of December 31, 2024 (latest available annual reporting date)" in annual["answer_text"]
    assert latest["observation"]["period"]["end"] == "2025-03-31"
    assert "latest available observation" in latest["answer_text"]


def test_unavailable_fcf_not_applicable_and_zero(db):
    add(db)
    assert ask("quarterly free cash flow")["observation"]["value"] is None
    add(db, "NetIncomeLoss", "0")
    assert ask("quarterly net income")["formatted_value"] == "$0.00"
    add(db, "RevenuesNetOfInterestExpense", "100")
    assert ask("quarterly gross margin")["status"] == "not_applicable"


def test_derived_answer_retains_formula_inputs_and_source_values(db):
    add(db)
    add(db, "NetIncomeLoss", "20")
    result = ask("quarterly net margin")
    assert result["formatted_value"] == "20.00%"
    assert result["observation"]["formula"] == "net_income / revenue"
    assert len(result["observation"]["inputs"]) == len(result["observation"]["provenance"]) == 2


def test_fcf_negative_result_retains_positive_outflow_inputs(db):
    add(db)
    add(db, "NetCashProvidedByUsedInOperatingActivities", "5")
    add(db, "PaymentsToAcquirePropertyPlantAndEquipment", "8")
    result = ask("quarterly free cash flow")
    assert result["formatted_value"] == "-$3.00"
    assert result["observation"]["formula"] == "operating_cash_flow - capital_expenditures"
    assert [Decimal(i["value"]) for i in result["observation"]["inputs"]] == [Decimal(5), Decimal(8)]


def test_company_mismatch_unknown_name_and_bounded_queries(db):
    db[0].add(Company(ticker="MSFT", name="Microsoft Corporation", cik="0000789019", exchange="NASDAQ"))
    db[0].commit()
    add(db)
    queries = []
    def track(conn, cursor, statement, params, context, many):
        if statement.lstrip().upper().startswith("SELECT"):
            queries.append(statement)
    event.listen(db[0].bind, "before_cursor_execute", track)
    try:
        mismatch = ask("What was Microsoft's revenue?")
        assert mismatch["status"] == "company_mismatch" and mismatch["observation"] is None
        assert len(queries) == 2  # version + catalog; never load other company facts
        queries.clear()
        assert ask("What was UnknownCorp's revenue?")["status"] == "not_matched"
        queries.clear()
        assert ask("latest quarterly revenue")["status"] == "available"
        assert len(queries) == 3  # version + catalog + facts
    finally:
        event.remove(db[0].bind, "before_cursor_execute", track)


@pytest.mark.parametrize("value,unit,expected", [
    ("-109417000000", "USD", "-$109.42B"), ("0", "USD", "$0.00"), ("12345678901234", "USD", "$12.35T"),
    ("0.12345", "ratio", "12.34%"), ("-0.025", "ratio", "-2.50%"), ("1.235", "USD/share", "$1.24 per share"),
])
def test_decimal_human_formatting(value, unit, expected):
    assert format_value(Decimal(value), unit) == expected


def test_request_validation_and_unknown_company(db):
    client = TestClient(main.app)
    for question in ("", " " * 3, "x" * 2001):
        assert client.post("/companies/TEST/research-answer", json={"question": question}).status_code == 422
    assert client.post("/companies/TEST/research-answer", json={"question": "revenue", "extra": "ignore"}).status_code == 422
    assert client.post("/companies/NOPE/research-answer", json={"question": "revenue"}).status_code == 404
