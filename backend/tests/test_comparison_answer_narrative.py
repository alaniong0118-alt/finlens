"""Self-contained comparison text over synthetic records; run via offline guard."""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app import research_answer_service as answers
from app.models import Company, FinancialFact


def fact(year, value, identifier, concept="Revenues", unit="USD"):
    return FinancialFact(id=identifier, company_cik="0000000001", metric=concept,
        value=Decimal(value), unit=unit, period_start=date(year, 1, 1),
        period_end=date(year, 12, 31), period_type="annual", fiscal_year=year,
        fiscal_period="FY", form="10-K", filed=date(year + 1, 2, 1),
        accession_number=f"0000000001-{(year + 1) % 100:02d}-{identifier:06d}",
        source="SEC Company Facts API: " + concept,
        created_at=datetime(year + 1, 2, 1, tzinfo=timezone.utc))


class Records:
    def __init__(self, rows):
        self.company = Company(id=1, ticker="TEST", name="Synthetic Issuer",
                               cik="0000000001", exchange="TEST")
        self.rows = rows
        self.reads = []

    def scalars(self, statement):
        entity = statement.column_descriptions[0]["entity"]
        self.reads.append(entity)
        if entity is Company:
            return iter([self.company])
        assert entity is FinancialFact
        return iter(self.rows)


def answer(question, rows):
    records = Records(rows)
    result = answers.answer_research_question(records, "TEST", question)
    assert records.reads == [Company, FinancialFact]
    return result


@pytest.mark.parametrize("earlier,later,absolute,pct,direction", [
    ("100", "120", "+$20.00", "+20.00%", "increase"),
    ("100", "80", "-$20.00", "-20.00%", "decrease"),
    ("100", "100", "$0.00", "0.00%", "no_change"),
    ("0", "10", "+$10.00", None, "increase"),
    ("-10", "-5", "+$5.00", None, "increase"),
    ("-10", "-20", "-$10.00", None, "decrease"),
    ("-10", "5", "+$15.00", None, "increase"),
])
def test_level_answer_states_absolute_change_and_percentage_policy(earlier, later, absolute, pct, direction):
    result = answer("how much did net income change from FY2024 to FY2025?", [
        fact(2024, earlier, 1, "NetIncomeLoss"), fact(2025, later, 2, "NetIncomeLoss")])
    comparison = result.comparison
    assert result.status == "available" and result.observation is None
    assert result.formatted_absolute_change == absolute
    assert result.formatted_percentage_change == pct
    assert f"Absolute change: {absolute}." in result.answer_text
    assert comparison.direction == direction
    assert comparison.absolute_change == Decimal(later) - Decimal(earlier)
    assert [p.fact_id for p in comparison.earlier.provenance] == [1]
    assert [p.fact_id for p in comparison.later.provenance] == [2]
    assert "FY2024" in result.answer_text and "FY2025" in result.answer_text
    if pct is None:
        assert comparison.percentage_status == "unavailable"
        assert comparison.percentage_reason in result.answer_text
    else:
        assert comparison.percentage_status == "available"
        assert f"({pct})" in result.answer_text


@pytest.mark.parametrize("metric,concept", [
    ("gross margin", "GrossProfit"), ("operating margin", "OperatingIncomeLoss"),
    ("net margin", "NetIncomeLoss"),
])
@pytest.mark.parametrize("income,expected", [("25", "+5.00 percentage points"),
                                          ("15", "-5.00 percentage points"),
                                          ("20", "0.00 percentage points")])
def test_margin_answer_labels_point_difference_without_relative_growth(metric, concept, income, expected):
    # Same accession for each year's revenue/numerator, retaining filing scope.
    rows = [fact(2024, "100", 1), fact(2024, "20", 2, concept),
            fact(2025, "100", 3), fact(2025, income, 4, concept)]
    rows[1].accession_number = rows[0].accession_number
    rows[3].accession_number = rows[2].accession_number
    result = answer(f"compare FY2024 and FY2025 {metric}", rows)
    assert result.status == "available"
    assert result.formatted_value == expected
    assert f"Absolute change: {expected}." in result.answer_text
    assert result.comparison.percentage_reason in result.answer_text
    assert result.comparison.percentage_change is None
    assert result.comparison.percentage_status == "not_applicable"
    assert {p.fact_id for p in result.comparison.earlier.provenance} == {1, 2}
    assert {p.fact_id for p in result.comparison.later.provenance} == {3, 4}


def test_eps_answer_states_as_filed_difference_and_share_basis_qualification():
    result = answer("compare FY2024 and FY2025 diluted EPS", [
        fact(2024, "1.23", 1, "EarningsPerShareDiluted", "USD/shares"),
        fact(2025, "1.25", 2, "EarningsPerShareDiluted", "USD/shares")])
    assert result.status == "available"
    assert "Absolute change: +$0.02 per share." in result.answer_text
    assert result.comparison.percentage_reason in result.answer_text
    assert result.comparability.status == "unverified"
    assert result.comparison.percentage_status == "not_applicable"
    assert result.comparison.percentage_change is None


def test_tiny_absolute_change_is_not_rounded_to_zero_in_text():
    result = answer("compare FY2024 and FY2025 revenue", [
        fact(2024, "100.0001", 1), fact(2025, "100.0002", 2)])
    assert result.status == "available"
    assert "Absolute change: +$0.0001." in result.answer_text
    assert "$100.0001 in FY2024" in result.answer_text
    assert "$100.0002 in FY2025" in result.answer_text
    assert result.comparison.absolute_change == Decimal("0.0001")


def test_incompatible_revenue_still_refuses_without_change_claim():
    result = answer("compare FY2024 and FY2025 revenue", [
        fact(2024, "100", 1), fact(2025, "120", 2, "SalesRevenueNet")])
    assert result.status == "unavailable"
    assert result.comparison.absolute_change is None
    assert result.formatted_absolute_change is None
    assert "Absolute change:" not in result.answer_text
    assert "economic bases" in result.explanation


@pytest.mark.parametrize("question,prefix", [
    ("did revenue increase from 2024 to 2025?", "Yes. "),
    ("did revenue decrease from 2024 to 2025?", "No. "),
    ("比較2024財年與2025財年營收", ""),
])
def test_existing_direction_and_chinese_dispatch_keep_complete_change_text(question, prefix):
    result = answer(question, [fact(2024, "100", 1), fact(2025, "120", 2)])
    assert result.status == "available"
    assert result.answer_text.startswith(prefix + "Revenue increased")
    assert "Absolute change: +$20.00." in result.answer_text


@pytest.mark.parametrize("question,qualification", [
    ("2024-2025 YoY revenue growth", "Year-over-year change."),
    ("2022-2025 revenue growth", "Cumulative period-to-period change."),
])
def test_growth_interval_qualification_is_retained(question, qualification):
    result = answer(question, [fact(2022, "50", 1), fact(2024, "100", 2), fact(2025, "120", 3)])
    assert result.status == "available"
    assert "Absolute change:" in result.answer_text
    assert result.answer_text.endswith(qualification)


def test_same_quarter_answer_keeps_requested_fiscal_labels_and_sources():
    rows = [fact(2024, "400", 1), fact(2025, "500", 2),
            fact(2024, "100", 3), fact(2025, "120", 4)]
    for row in rows[2:]:
        row.period_start = date(row.fiscal_year, 4, 1)
        row.period_end = date(row.fiscal_year, 6, 30)
        row.period_type, row.fiscal_period = "quarter", "Q2"
        row.filed = date(row.fiscal_year, 8, 1)
    result = answer("compare Q2 FY2024 and Q2 FY2025 revenue", rows)
    assert result.status == "available"
    assert "$100.00 in Q2 FY2024" in result.answer_text
    assert "$120.00 in Q2 FY2025" in result.answer_text
    assert "Absolute change: +$20.00." in result.answer_text
    assert [p.fact_id for p in result.comparison.earlier.provenance] == [3]
    assert [p.fact_id for p in result.comparison.later.provenance] == [4]
