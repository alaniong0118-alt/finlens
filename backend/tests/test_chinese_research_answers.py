"""Finite Chinese amount questions through real dispatch; shared offline fixtures."""
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from app import main, research_answer_service as answers
from app.models import Company
from test_financial_metrics import db, add
from test_historical_research_answers import annual
from test_research_answers import ask


@pytest.fixture
def chinese_values(db):
    annual(db, 2024, "100")
    annual(db, 2025, "110")
    annual(db, 2024, "20", "NetIncomeLoss")
    annual(db, 2024, "30", "NetCashProvidedByUsedInOperatingActivities")
    annual(db, 2024, "8", "PaymentsToAcquirePropertyPlantAndEquipment")
    add(db, "Assets", "500", start=None, end="2024-12-31", filed=date(2025, 2, 1), form="10-K")
    add(db, value="25", start="2025-04-01", end="2025-06-30", filed=date(2025, 8, 1))
    return db


@pytest.fixture
def no_fact_reads(chinese_values):
    reads = []
    def record(conn, cursor, statement, parameters, context, many):
        if statement.lstrip().upper().startswith("SELECT") and "financial_facts" in statement.lower():
            reads.append(statement)
    engine = chinese_values[0].get_bind()
    event.listen(engine, "before_cursor_execute", record)
    try:
        yield chinese_values
        assert reads == []
    finally:
        event.remove(engine, "before_cursor_execute", record)


@pytest.mark.parametrize("term,metric,value", [
    ("營收", "revenue", "100"), ("营收", "revenue", "100"),
    ("營業收入", "revenue", "100"), ("营业收入", "revenue", "100"),
    ("淨利", "net_income", "20"), ("净利", "net_income", "20"),
    ("淨利潤", "net_income", "20"), ("净利润", "net_income", "20"),
    ("總資產", "total_assets", "500"), ("总资产", "total_assets", "500"),
    ("自由現金流", "free_cash_flow", "22"), ("自由现金流", "free_cash_flow", "22"),
])
def test_bounded_chinese_metric_aliases_reuse_exact_english_observation(chinese_values, term, metric, value):
    question = f"2024 財年的{term}是多少？"
    result = ask(question)
    english = ask(f"2024 {answers.QUESTION_TERMS[metric][1][0]}")
    assert result["matched"] and result["status"] == "available" and result["metric"] == metric
    assert result["answer_kind"] == "historical_metric" and result["question"] == question
    assert Decimal(result["observation"]["value"]) == Decimal(value)
    assert result["observation"] == english["observation"]
    assert result["formatted_value"] == english["formatted_value"]
    assert result["observation"]["provenance"]
    assert all(p["company_cik"] == "0000000001" for p in result["observation"]["provenance"])
    if metric == "free_cash_flow":
        assert result["observation"]["formula"] == "operating_cash_flow - capital_expenditures"
    if metric == "total_assets":
        assert result["observation"]["period"]["kind"] == "instant"


@pytest.mark.parametrize("question,kind,value,quarter", [
    ("2024 財年的營收是多少？", "historical_metric", "100", None),
    ("请问2024财年的营收为多少?", "historical_metric", "100", None),
    ("請問　2024財年　營收　為多少？", "historical_metric", "100", None),
    ("2025財年第2季的營收是多少？", "historical_metric", "25", 2),
    ("2025财年第二季度营收为多少", "historical_metric", "25", 2),
    ("最新季度的營收是多少？", "latest_metric", "25", None),
    ("最新一季营收为多少?", "latest_metric", "25", None),
    ("最新財年的營收是多少？", "latest_metric", "110", None),
    ("最新财年营收是多少", "latest_metric", "110", None),
    ("最新的營收是多少？", "latest_metric", "110", None),
])
def test_bounded_chinese_period_and_amount_forms(chinese_values, question, kind, value, quarter):
    result = ask(question)
    assert result["status"] == "available" and result["answer_kind"] == kind
    assert Decimal(result["observation"]["value"]) == Decimal(value)
    if kind == "historical_metric":
        assert result["requested_period"]["quarter"] == quarter


@pytest.mark.parametrize("prefix", [
    "股票代號TEST的", "股票代碼test的", "股票代码test的", "請問股票代號 TEST 的 ", "请问股票代码 test 的 ",
])
def test_bounded_chinese_explicit_ticker_stays_selected(chinese_values, prefix):
    result = ask(prefix + "2024財年的營收是多少？")
    assert result["status"] == "available" and result["ticker"] == "TEST"
    assert result["observation"]["provenance"][0]["company_cik"] == "0000000001"


@pytest.mark.parametrize("ticker", ["BRK.B", "BF-B", "A", "NOT", "OR"])
def test_bounded_chinese_catalog_ticker_spelling(chinese_values, ticker):
    chinese_values[1].ticker = ticker
    chinese_values[0].commit()
    assert ask(f"股票代號{ticker}的2024財年營收是多少？", ticker)["status"] == "available"


@pytest.mark.parametrize("question", [
    "不是2024財年的營收是多少？", "請不要回答2024財年的營收是多少？",
    "2024財年的營收不是多少？", "2024财年营收不要给我数字。",
    "請解釋營收的定義，不要給我數字。", "2024財年的營收是什麼？",
    "2024財年調整後營收是多少？", "2024财年不含利息的营业收入是多少？",
    "2024財年的自由現金流以人民幣是多少？", "2024財年的營收和淨利是多少？",
    "2024與2025財年的營收是多少？", "2024財年和2025財年營收是多少？",
    "2024財年的營收比2025財年多多少？", "2024年營收是多少？", "去年營收是多少？",
    "營收是多少？", "最新季度和年度的營收是多少？", "2024財年第五季營收是多少？",
    "２０２４財年的營收是多少？", "1899財年的營收是多少？", "2100財年的營收是多少？",
    "蘋果的2024財年營收是多少？", "TEST和MSFT的2024財年營收是多少？",
    "2024財年的利潤是多少？", "2024財年的營收成長率是多少？",
    "TEST 2024財年的營收是多少？", "TEST的2024財年營收是多少？",
    "股票代號TEST和MSFT的2024財年營收是多少？",
])
def test_bounded_chinese_rejects_complete_unsupported_utterance_without_facts(no_fact_reads, question):
    result = ask(question)
    assert result["status"] == "not_matched" and not result["matched"]
    assert result["observation"] is None and result["comparison"] is None and result["answer_text"] is None


@pytest.mark.parametrize("suffix,status", [
    ("不要給我數字", 200), ("（不含某部門）", 200), ("，請說明定義", 200),
    (" not revenue", 200), (" AND net income", 200), ("\u0301", 200),
    ("<script>alert(1)</script>", 200), ("\u200b", 422), ("\u202e", 422), ("\n", 422),
])
def test_bounded_chinese_adversarial_suffix_cannot_be_dropped(no_fact_reads, suffix, status):
    response = TestClient(main.app).post("/companies/TEST/research-answer",
        json={"question": "2024財年的營收是多少？" + suffix})
    assert response.status_code == status
    if status == 200:
        assert response.json()["status"] == "not_matched" and response.json()["observation"] is None


@pytest.mark.parametrize("ticker,status", [("MSFT", "company_mismatch"), ("UNKNOWN", "not_matched")])
def test_bounded_chinese_wrong_or_unknown_company_never_reads_facts(no_fact_reads, ticker, status):
    no_fact_reads[0].add(Company(ticker="MSFT", name="Microsoft Corp", cik="0000789019", exchange="NASDAQ"))
    no_fact_reads[0].commit()
    assert ask(f"股票代號{ticker}的2024財年的營收是多少？")["status"] == status


@pytest.mark.parametrize("ticker", ["NOT", "IF", "OR"])
def test_bounded_chinese_bare_clause_words_cannot_be_consumed_as_tickers(no_fact_reads, ticker):
    no_fact_reads[1].ticker = ticker
    no_fact_reads[0].commit()
    assert ask(f"{ticker.lower()} 2024財年的營收是多少？", ticker)["status"] == "not_matched"


@pytest.mark.parametrize("question", [
    "2099財年的營收是多少？", "2024財年第4季營收是多少？",
    "2024财年第二季度营收是多少？", "2025財年的自由現金流是多少？",
])
def test_bounded_chinese_missing_period_or_inputs_remain_unavailable(chinese_values, question):
    result = ask(question)
    assert result["matched"] and result["status"] == "unavailable"
    assert result["formatted_value"] is None and result["observation"]["value"] is None


@pytest.mark.parametrize("question,accepted", [
    ("2024財年的營收是多少？", True), ("不是2024財年的營收是多少？", False),
    ("請解釋營收的定義，不要給我數字。", False),
])
def test_bounded_chinese_never_uses_lossy_english_words(monkeypatch, question, accepted):
    company = Company(ticker="TEST", name="某公司", cik="0000000001")
    def forbidden(*args):
        raise AssertionError("Chinese text reached lossy English normalization")
    monkeypatch.setattr(answers, "words", forbidden)
    operation, rejection = answers.recognize_operation(question, company, [company])
    assert (rejection is None) == accepted
    assert answers.operation_agrees(operation) == accepted
    # A whole-utterance exception never widens the English admission boundary.
    assert not answers.supported_question_text(question)
    assert answers.recognize(question, company, [company], math_intent=answers.MathematicalIntent("value"))[2] == "not_matched"
    assert answers.recognize_historical(question, company, [company], math_intent=answers.MathematicalIntent("value")) is None
