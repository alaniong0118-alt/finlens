"""Typed operation handoff through the real API, isolated DB, forbidden clients."""
from dataclasses import replace
from decimal import Decimal

import pytest

from app import research_answer_service as answers
from app.financial_metric_schemas import FiscalPeriodRequest
from app.models import Company
from test_financial_metrics import db
from test_historical_research_answers import annual
from test_research_answers import ask


def typography(question, style):
    if style == "caps":
        return question.upper()
    if style == "spaced":
        return "  " + question.replace(" ", "   ") + "  "
    if style == "punctuation":
        return "(" + question.replace("-", "–").replace("'", "’") + ")?"
    return question


@pytest.fixture
def operations(db):
    # Levels rise 10%, while the independent YoY observations fall 100% -> 10%.
    for year, revenue in [(2022, "40"), (2023, "50"), (2024, "100"), (2025, "110")]:
        annual(db, year, revenue)
    annual(db, 2024, "20", "OperatingIncomeLoss")
    annual(db, 2025, "27.5", "OperatingIncomeLoss")
    return db


@pytest.mark.parametrize("style", ["plain", "caps", "spaced", "punctuation"])
@pytest.mark.parametrize("question", [
    "Compare 2024 revenue growth and 2025 revenue growth",
    "Compare 2024 vs 2025 revenue growth rates",
    "2024 revenue growth versus 2025 revenue growth",
    "Compare FY2024 YoY growth with FY2025 YoY growth",
    "Compare 2025 revenue growth with 2024 revenue growth",
    "Compare revenue growth in FY2024 versus FY2025",
    "FY2025 revenue growth, compared with FY2024 revenue growth",
    "Did revenue's growth decrease from 2024 to 2025?",
])
def test_handoff_independent_growth_operands_reject(operations, question, style):
    assert Decimal(ask("2024 revenue growth")["observation"]["value"]) == 1
    assert Decimal(ask("2025 revenue growth")["observation"]["value"]) == Decimal("0.1")
    result = ask(typography(question, style))
    assert result["status"] == "not_matched" and not result["matched"]
    assert result["comparison"] is None and result["formatted_value"] is None


@pytest.mark.parametrize("slash", ["/", "／", "∕", "⁄"])
@pytest.mark.parametrize("denominator", ["year", "(year)", "fiscal-year", " ( fiscal year ) "])
def test_handoff_unicode_annualization_reject(operations, slash, denominator):
    result = ask(f"2022-2025 revenue growth (% {slash} {denominator})")
    assert result["status"] == "not_matched" and result["comparison"] is None


@pytest.mark.parametrize("percent", ["%", "％"])
@pytest.mark.parametrize("verb", ["grew", "grow", "change", "increased"])
def test_handoff_unicode_relative_margin_reject(operations, percent, verb):
    result = ask(f"2024-2025 operating margin {verb} ({percent})")
    assert result["status"] == "not_matched" and result["formatted_value"] is None


@pytest.mark.parametrize("notation", ["÷ year", "⧸ year", "× year", "‰", "‱", "٪", "/ quarter", "^ 2", "* 2", "= 5"])
def test_handoff_unknown_math_fails_closed(operations, notation):
    assert ask(f"2022-2025 revenue growth ({notation})")["status"] == "not_matched"


@pytest.mark.parametrize("question", ["２０２４ revenue", "2024² revenue", "2024⁻2025 revenue growth"])
def test_handoff_unknown_numeric_notation_cannot_become_latest_or_interval(operations, question):
    assert ask(question)["status"] == "not_matched"


@pytest.mark.parametrize("question,category", [
    ("2024-2025 revenue growth", "revenue_level_comparison"),
    ("revenue growth from 2024 to 2025", "revenue_level_comparison"),
    ("2024-2025 YoY revenue growth", "adjacent_year_yoy_growth"),
    ("2024-2025 year-to-year revenue growth", "adjacent_year_yoy_growth"),
    ("compare 2024 and 2025 revenue", "revenue_level_comparison"),
    ("did revenue increase from 2024 to 2025?", "revenue_level_comparison"),
    ("how much did revenue grow between 2024 and 2025?", "revenue_level_comparison"),
    ("2024-2025 revenue % change", "revenue_level_comparison"),
    ("2022-2025 revenue growth", "cumulative_period_growth"),
    ("compare 2024 and 2025 operating margin", "percentage_point_difference"),
])
@pytest.mark.parametrize("style", ["plain", "caps", "spaced", "punctuation"])
def test_handoff_valid_operations_survive_dispatch(operations, monkeypatch, question, category, style):
    # Observe the real dispatcher, then use the unmodified FinancialMetrics path.
    received = []
    original = answers.resolve_historical_answer
    def capture(service, question, intent):
        received.append(intent)
        return original(service, question, intent)
    monkeypatch.setattr(answers, "resolve_historical_answer", capture)
    result = ask(typography(question, style))
    assert result["status"] == "available"
    intent = received[0]
    assert intent.operation == category and intent.operands == "period_interval"
    assert len(intent.periods) == 2 and intent.status == "supported"
    assert result["comparison"]["earlier"]["provenance"]
    assert result["comparison"]["later"]["provenance"]
    if category == "percentage_point_difference":
        assert result["formatted_value"] == "+5.00 percentage points"
    elif category == "cumulative_period_growth":
        assert result["formatted_value"] == "+175.00%"
        assert "Cumulative period-to-period" in result["answer_text"]
        assert "Year-over-year" not in result["answer_text"]
    else:
        assert result["formatted_value"] == "+10.00%"
        assert ("Year-over-year" in result["answer_text"]) == (category == "adjacent_year_yoy_growth")


@pytest.mark.parametrize("corruption", ["operation", "metric", "operands", "math", "periods", "status"])
def test_handoff_dispatch_rejects_contract_disagreement(operations, monkeypatch, corruption):
    # Model a future recognizer regression, rather than relying on today's
    # preflight to make an invalid supported contract unreachable.
    original = answers.recognize_operation
    def broken(question, selected, companies):
        intent, rejection = original(question, selected, companies)
        changes = {
            "operation": {"operation": "percentage_point_difference"},
            "metric": {"metric": "operating_margin"},
            "operands": {"operands": "growth_observations"},
            "math": {"math": answers.MathematicalIntent("annualized")},
            "periods": {"periods": (FiscalPeriodRequest(fiscal_year=2022), intent.periods[1])},
            "status": {"status": "unsupported"},
        }
        return replace(intent, **changes[corruption]), rejection
    monkeypatch.setattr(answers, "recognize_operation", broken)
    result = ask("2024-2025 YoY revenue growth")
    assert result["status"] == "not_matched" and result["comparison"] is None


def test_handoff_single_values_and_company_fallback(operations):
    assert ask("latest annual revenue")["status"] == "available"
    assert Decimal(ask("2024 revenue")["observation"]["value"]) == 100
    for question in ["Why did revenue increase from 2024 to 2025?", "How is 2024 revenue reported?",
                     "2022-2025 YoY revenue growth", "2024 revenue and net income"]:
        assert ask(question)["status"] == "not_matched"
    operations[0].add(Company(ticker="MSFT", name="Microsoft Corp", cik="0000789019", exchange="NASDAQ"))
    operations[0].commit()
    assert ask("Microsoft 2024-2025 revenue growth")["status"] == "company_mismatch"


def test_handoff_rejected_intent_retains_diagnostic_operands(operations, monkeypatch):
    received = []
    original = answers.recognize_operation
    def capture(*args):
        result = original(*args)
        received.append(result[0])
        return result
    monkeypatch.setattr(answers, "recognize_operation", capture)
    assert ask("Compare 2024 revenue growth and 2025 revenue growth")["status"] == "not_matched"
    intent = received[0]
    assert intent.operation == "unsupported_growth_rate_comparison"
    assert intent.metric == "revenue_growth_yoy" and intent.operands == "growth_observations"
    assert [period.fiscal_year for period in intent.periods] == [2024, 2025]
    assert intent.status == "unsupported" and intent.reason


@pytest.mark.parametrize("percent", ["%", "％"])
def test_handoff_unsupported_eps_percentage_is_not_absolute_difference(operations, percent):
    annual(operations, 2024, "2", "EarningsPerShareDiluted", unit="USD/shares")
    annual(operations, 2025, "3", "EarningsPerShareDiluted", unit="USD/shares")
    assert ask(f"2024-2025 diluted EPS {percent} change")["status"] == "not_matched"
    ordinary = ask("compare 2024 and 2025 diluted EPS")
    assert ordinary["status"] == "available"
    assert ordinary["formatted_value"] == "+$1.00 per share"
    assert ordinary["comparison"]["percentage_status"] == "not_applicable"
