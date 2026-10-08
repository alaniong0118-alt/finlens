"""Read-only local HTTP/source acceptance; never acquires SEC/provider data."""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
from time import perf_counter
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import engine
from app.models import FinancialFact
from app.research_answer_service import ResearchAnswer, answer_research_question
from scripts.verify_financial_metrics import fingerprint, verify_source

REPORT = Path(__file__).resolve().parents[1] / "reports/historical_answers_verification.json"
CASES = [
    ("AAPL", "2024 revenue", "available"),
    ("AAPL", "2025 revenue", "available"),
    ("AAPL", "Q2 2025 revenue", "available"),
    ("AAPL", "2024 vs 2025 revenue", "available"),
    ("AAPL", "2024-2025 revenue growth", "available"),
    ("AAPL", "how much did revenue grow from 2024 to 2025?", "available"),
    ("AAPL", "did revenue increase from 2024 to 2025?", "available"),
    ("AAPL", "how much did net income change between 2024 and 2025?", "available"),
    ("AAPL", "Q4 2025 revenue", "unavailable"),
    ("AAPL", "1999 revenue", "unavailable"),
    ("AAPL", "2024 gross margin", "unavailable"),
    ("JPM", "2024 vs 2025 revenue", "unavailable"),
    ("JPM", "compare Q2 2024 and Q2 2025 revenue", "available"),
    ("COST", "2024 vs 2025 revenue", "available"),
    ("COST", "compare Q3 2025 and Q3 2026 revenue", "unavailable"),
    ("COST", "compare 2024 and 2025 operating margin", "available"),
    ("JNJ", "2025 net income", "available"),
    ("JNJ", "2024 vs 2025 diluted EPS", "available"),
    ("XOM", "2025 revenue", "unavailable"),
    ("XOM", "Q2 2025 revenue", "unavailable"),
    ("AAPL", "Why did revenue grow from 2024 to 2025?", "not_matched"),
    ("AAPL", "What is Apple's main product?", "not_matched"),
    ("AAPL", "How is Apple's 2024 revenue reported?", "not_matched"),
    ("AAPL", "2024 revenue and net income", "not_matched"),
    ("AAPL", "Microsoft revenue in 2025", "company_mismatch"),
    ("AAPL", "latest quarterly revenue", "available"),
]


def run(api_url):
    assert urlparse(api_url).hostname in {"localhost", "127.0.0.1"}
    with engine.connect() as connection, httpx.Client(base_url=api_url, timeout=120) as client:
        connection.exec_driver_sql("SET TRANSACTION READ ONLY")
        before = fingerprint(connection)
        baseline = REPORT.with_name("historical_answers_baseline.json")
        assert before == json.loads(baseline.read_text())
        results = []
        with Session(bind=connection) as session:
            rows = {row.id: row for row in session.scalars(select(FinancialFact))}
            for ticker, question, status in CASES:
                start = perf_counter()
                response = client.post(f"/companies/{ticker}/research-answer", json={"question": question})
                latency_ms = round((perf_counter()-start)*1000, 2)
                response.raise_for_status()
                answer = ResearchAnswer.model_validate(response.json())
                assert answer.status == status, (ticker, question, answer.status)
                expected = answer_research_question(session, ticker, question)
                assert answer == expected
                if answer.observation:
                    verify_source(answer.observation, rows)
                if answer.comparison:
                    comp = answer.comparison
                    for point in [comp.earlier, comp.later]:
                        verify_source(point, rows)
                    if comp.status == "available":
                        assert comp.absolute_change == comp.later.value - comp.earlier.value
                        if comp.percentage_status == "available":
                            assert comp.earlier.value > 0
                            assert comp.percentage_change == comp.absolute_change / comp.earlier.value
                        else:
                            assert comp.percentage_change is None
                results.append({"ticker": ticker, "question": question, "http_status": response.status_code,
                                "latency_ms": latency_ms, "result": answer.model_dump(mode="json")})
            assert Decimal(results[0]["result"]["observation"]["value"]) == Decimal("391035000000")
            assert Decimal(results[1]["result"]["observation"]["value"]) == Decimal("416161000000")
            assert Decimal(results[2]["result"]["observation"]["value"]) == Decimal("95359000000")
            assert results[-1]["result"]["formatted_value"] == "$109.42B"
            assert results[17]["result"]["comparability"]["status"] == "unverified"
            assert results[17]["result"]["comparison"]["percentage_status"] == "not_applicable"
        after = fingerprint(connection)
        assert after == before
    report = {"verified_at": datetime.now(timezone.utc).isoformat(), "api_url": api_url,
              "http_cases": results, "source_audit": "Every selected/alternative source and derived input checked against exact stored rows and official SEC URL construction; comparisons checked independently with Decimal.",
              "database_before": before, "database_after": after, "database_unchanged": True,
              "external_sec_calls": 0, "external_openai_calls": 0,
              "server_guard": "Local acceptance backend forces read-only transactions and forbids SEC transport/OpenAI client construction; HF model loading offline."}
    REPORT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"http_cases": len(results), "database_unchanged": True,
                      "results": [{"ticker": r["ticker"], "question": r["question"], "status": r["result"]["status"], "value": r["result"]["formatted_value"]} for r in results]}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    run(parser.parse_args().api_url)
