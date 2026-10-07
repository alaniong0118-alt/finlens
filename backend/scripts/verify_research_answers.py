"""Local read-only HTTP/source acceptance; no SEC/provider acquisition.

Run against the new guarded local backend. Writes a separate milestone report,
never replaces historical financial/research verification artifacts.
"""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import engine
from app.models import FinancialFact
from app.research_answer_service import ResearchAnswer, answer_research_question
from scripts.verify_financial_metrics import fingerprint, verify_source

REPORT = Path(__file__).resolve().parents[1] / "reports/deterministic_answers_verification.json"
CASES = [
    ("AAPL", "What was Apple's latest quarterly revenue?"),
    ("JPM", "What is JPMorgan's latest quarterly revenue?"),
    ("COST", "What was Costco's latest quarterly revenue growth?"),
    ("JNJ", "What was JNJ's latest quarterly net income?"),
    ("XOM", "What was XOM's latest quarterly revenue?"),
    ("XOM", "What was XOM's annual revenue?"),
    ("AAPL", "What was Apple's annual net income?"),
    ("AAPL", "What is Apple's latest available revenue?"),
    ("JNJ", "What is JNJ's latest diluted EPS?"),
    ("AAPL", "What is Apple's main product?"),
    ("AAPL", "What clinical trial results did Apple report?"),
    ("AAPL", "What drove revenue growth?"),
    ("AAPL", "What was Microsoft's revenue?"),
]


def run(api_url):
    assert urlparse(api_url).hostname in {"127.0.0.1", "localhost"}
    with engine.connect() as connection, httpx.Client(base_url=api_url, timeout=120) as client:
        connection.exec_driver_sql("SET TRANSACTION READ ONLY")
        before = fingerprint(connection)
        baseline = json.loads((REPORT.parent / "deterministic_answers_baseline.json").read_text())
        assert before == baseline, "Database changed since task baseline"
        with Session(bind=connection) as session:
            facts = {row.id: row for row in session.scalars(select(FinancialFact))}
            results = []
            for ticker, question in CASES:
                response = client.post(f"/companies/{ticker}/research-answer", json={"question": question})
                response.raise_for_status()
                actual = ResearchAnswer.model_validate(response.json())
                expected = answer_research_question(session, ticker, question)
                assert actual == expected
                point = actual.observation
                if point is not None:
                    verify_source(point, facts)
                results.append({"ticker": ticker, "question": question, "http_status": response.status_code,
                                "elapsed_ms": round(response.elapsed.total_seconds() * 1000, 2),
                                "result": actual.model_dump(mode="json")})
            assert Decimal(results[0]["result"]["observation"]["value"]) == Decimal("109417000000")
            assert results[0]["result"]["observation"]["period"]["end"] == "2026-06-27"
            assert results[1]["result"]["observation"]["revenue_basis"] == "net_interest"
            assert results[2]["result"]["status"] == "unavailable"
            assert "economic bases" in results[2]["result"]["explanation"]
            assert results[3]["result"]["status"] == "available"
            assert results[5]["result"]["status"] == "unavailable"
            assert all(results[i]["result"]["status"] == "not_matched" for i in (9, 10, 11))
            assert results[12]["result"]["status"] == "company_mismatch"
            capabilities = client.get("/capabilities").json()
            assert capabilities["ai_analysis_configured"] is False
            sources = client.get("/companies/AAPL/sources").json()
            accession = next(source["accession_number"] for source in sources if source["has_filing_chunks"])
            evidence = []
            for query in (CASES[0][1], CASES[9][1], CASES[10][1]):
                response = client.get(f"/companies/AAPL/filings/{accession}/context", params={"q": query, "limit": 5})
                response.raise_for_status()
                data = response.json()
                assert data["ticker"] == "AAPL" and data["accession_number"] == accession
                evidence.append({"query": query, "evidence_status": data["evidence_status"], "citation_count": len(data["citations"])})
            assert evidence[2]["evidence_status"] == "insufficient"
        after = fingerprint(connection)
        assert after == before
        connection.rollback()
    report = {"verified_at": datetime.now(timezone.utc).isoformat(), "api_url": api_url,
              "source_validation": "Exact typed HTTP results equal existing FinancialMetrics; every selected/alternative source and derived input checked against stored rows.",
              "capabilities": capabilities, "http_cases": results, "evidence": evidence,
              "database_before": before, "database_after": after, "database_unchanged": True,
              "external_sec_calls": 0, "external_ai_calls": 0,
              "guard": "Acceptance server forbids SEC transport/OpenAI client construction; no AI answer POST sent."}
    REPORT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"cases": len(results), "database_unchanged": True,
                      "results": [{"ticker": r["ticker"], "question": r["question"], "status": r["result"]["status"], "value": r["result"]["formatted_value"], "period": r["result"]["observation"]["period"] if r["result"]["observation"] else None} for r in results]}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default="http://127.0.0.1:8021")
    run(parser.parse_args().api_url)
