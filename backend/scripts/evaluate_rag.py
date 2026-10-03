"""Read-only API/retrieval acceptance; real provider calls require --real-answers."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from time import perf_counter
from types import SimpleNamespace
from urllib.parse import urlparse

from fastapi.testclient import TestClient
from sqlalchemy import select

from app import answer_service
from app.config import openai_model
from app.database import SessionLocal
from app.evidence_policy import evidence_reason
from app.filing_search_service import hybrid_search_filing_chunks, search_filing_chunks_semantic
from app.main import app
from app.models import FilingChunk

QUERIES = [
    "What drove revenue growth?",
    "What were the main drivers of services revenue?",
    "What was the gross margin?",
    "What supply constraints were discussed?",
    "How did artificial intelligence affect the business?",
]
KEYWORD_QUERIES = [
    "revenue growth", "services revenue", "gross margin",
    "supply constraints", "artificial intelligence",
]
NEGATIVE_QUERY = "What clinical trial results did Apple report?"


def snapshot():
    with SessionLocal() as session:
        rows = session.scalars(select(FilingChunk).order_by(FilingChunk.id)).all()
        serialized = [{col.name: str(getattr(row, col.name))
                       for col in FilingChunk.__table__.columns} for row in rows]
        return {
            "chunk_count": len(rows),
            "embedding_count": sum(row.embedding is not None for row in rows),
            "sha256": hashlib.sha256(json.dumps(serialized, sort_keys=True).encode()).hexdigest(),
        }


@contextmanager
def observe_provider_calls():
    """Pass through to the real SDK; capture only model/input, never credentials.

    No model response is replaced or fabricated. Counts represent actual SDK
    call attempts, including attempts that time out or fail upstream.
    """
    original_factory = answer_service._get_openai_client
    calls = []

    def factory():
        provider = original_factory()

        def parse(**kwargs):
            calls.append({"model": kwargs["model"],
                          "input": json.loads(kwargs["input"][1]["content"])})
            return provider.responses.parse(**kwargs)

        return SimpleNamespace(responses=SimpleNamespace(parse=parse))

    answer_service._get_openai_client = factory
    try:
        yield calls
    finally:
        answer_service._get_openai_client = original_factory


def source_lineage(citations, context, rows):
    """Verify stored metadata and candidate text, not claim entailment or HTTP reachability."""
    checks = []
    for citation in citations:
        row = rows[citation["chunk_id"]]
        fields = ("chunk_id", "accession_number", "form", "filed", "filename",
                  "start_char", "end_char", "sec_url")
        metadata_matches = all(str(citation[key]) == str(getattr(row, key)) for key in fields)
        source_text = "\n".join(f"  {line}" for line in row.text.splitlines())
        checks.append({
            "citation_id": citation["citation_id"], "chunk_id": row.chunk_id,
            "metadata_matches_database": metadata_matches,
            "text_matches_database": source_text in context,
            "official_sec_url": urlparse(row.sec_url).hostname == "www.sec.gov",
            "sec_url": row.sec_url,
            "official_page_verification": "not_run",
        })
    return checks


def evaluate_query(client, company, filing, query, real_answers, key_configured, calls):
    base = f"/companies/{company['ticker']}/filings/{filing['accession_number']}"
    response = client.get(f"{base}/context", params={"q": query, "limit": 5})
    response.raise_for_status()
    context = response.json()
    with SessionLocal() as session:
        ranked = hybrid_search_filing_chunks(session, company["cik"], filing["accession_number"], query, 5)
        semantic = search_filing_chunks_semantic(session, company["cik"], filing["accession_number"], query, 1)
        rows = {row.chunk_id: row for row in session.scalars(select(FilingChunk).where(
            FilingChunk.company_cik == company["cik"],
            FilingChunk.accession_number == filing["accession_number"],
        )).all()}
        results = [{
            "chunk_id": item.chunk.chunk_id,
            "semantic_similarity": item.semantic_similarity,
            "lexical_score": item.lexical_score,
            "hybrid_score": item.hybrid_score,
            "evidence_reason": evidence_reason(item.semantic_similarity, item.lexical_score),
            "excerpt": item.chunk.text[:650],
        } for item in ranked]
        lineage = source_lineage(context["citations"], context["context"], rows)

    entry = {
        "query": query, "question": query, "company": company, "filing": filing,
        "ticker": company["ticker"], "accession_number": filing["accession_number"],
        "form": filing["form"], "retrieval_status": "completed",
        "retrieved_chunks": [item["chunk_id"] for item in results],
        "model": openai_model(), "semantic_baseline_top": semantic[0][0].chunk_id if semantic else None,
        "results": results, "evidence_status": context["evidence_status"],
        "citations": context["citations"], "candidate_context": context["context"],
        "source_lineage_audit": lineage, "real_llm": False,
        "real_request_count": 0, "sent_source_context": None,
        "claim_audit": {"status": "not_run", "claims": [], "unsupported_claims": None},
    }
    # A missing key is exercised through the formal endpoint. With a key present,
    # retrieval-only mode never accidentally spends API credits.
    if real_answers or not key_configured or context["evidence_status"] == "insufficient":
        before = len(calls)
        start = perf_counter()
        answer = client.post(f"{base}/answer", json={"question": query, "limit": 5})
        entry.update(api_latency_ms=round((perf_counter() - start) * 1000, 2),
                     http_status=answer.status_code,
                     error_code=answer.headers.get("X-FinLens-Error-Code"),
                     response=answer.json(), real_request_count=len(calls) - before,
                     real_llm=len(calls) > before)
        if len(calls) > before:
            entry["sent_source_context"] = calls[-1]["input"]["context"]
        entry["answer_status"] = (
            "blocked" if not key_configured and answer.status_code == 503
            else "failed" if answer.status_code != 200
            else "completed" if entry["real_llm"] else "not_run"
        )
        if answer.status_code == 200 and entry["real_llm"]:
            # Valid citation identity does not establish factual support.
            entry["claim_audit"] = {
                "status": "pending_manual_review",
                "claims": [{**claim, "verdict": None} for claim in answer.json()["claims"]],
                "allowed_verdicts": ["SUPPORTED", "PARTIALLY_SUPPORTED", "NOT_SUPPORTED"],
                "unsupported_claims": None,
            }
    else:
        entry["answer_status"] = "not_run"
    entry["llm_status"] = entry["answer_status"]
    entry["claim_audit_status"] = entry["claim_audit"]["status"]
    entry["blocker"] = "missing_openai_api_key" if entry["answer_status"] == "blocked" else None
    entry["success"] = entry.get("http_status") == 200 if "http_status" in entry else None
    first = results[0] if results else {}
    print(query, first.get("chunk_id"), context["evidence_status"], entry["answer_status"], flush=True)
    return entry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--real-answers", action="store_true", help="Allow real, billable OpenAI requests.")
    args = parser.parse_args()
    key_configured = bool(os.getenv("OPENAI_API_KEY", "").strip())
    before = snapshot()
    with TestClient(app) as client, observe_provider_calls() as calls:
        companies = client.get("/companies")
        companies.raise_for_status()
        company = next(item for item in companies.json() if item["ticker"] == "AAPL")
        sources = client.get("/companies/AAPL/sources")
        sources.raise_for_status()
        filing = next(item for item in sources.json() if item["has_filing_chunks"])
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "accession_number": filing["accession_number"],
            "ticker": company["ticker"], "company": company, "form": filing["form"],
            "selection": "GET /companies/AAPL/sources: first indexed filing",
            "retrieval_kind": "real_database", "mock_results": [],
            "queries": [evaluate_query(client, company, filing, query, args.real_answers,
                                       key_configured, calls) for query in QUERIES],
        }
        # Keep the historical short-query retrieval baseline; never call the
        # answer API for it, so the real evaluation has exactly five candidates.
        report["keyword_baseline"] = [client.get(
            f"/companies/AAPL/filings/{filing['accession_number']}/context",
            params={"q": query, "limit": 5},
        ).json() for query in KEYWORD_QUERIES]
        report["negative_control"] = evaluate_query(
            client, company, filing, NEGATIVE_QUERY, False, key_configured, calls,
        )
        failed = any(item["answer_status"] == "failed" for item in report["queries"])
        report["llm_evaluation"] = {
            "kind": "real" if calls else "not_run",
            "real_llm": bool(calls),
            "llm_status": "blocked" if not key_configured else "failed" if failed
                          else "completed" if calls else "not_run",
            "blocker": "missing_openai_api_key" if not key_configured else None,
            "status": "blocked" if not key_configured else "failed" if failed
                      else "completed" if calls else "not_run",
            "reason": "missing OPENAI_API_KEY" if not key_configured else None,
            "real_request_count": len(calls),
            "count_definition": "real SDK call attempts, including timeout/upstream failure",
            "configured_model": openai_model(),
            "claim_audit_status": "pending_manual_review" if calls else "not_run",
        }
    after = snapshot()
    report.update(chunk_count=after["chunk_count"], embedding_count=after["embedding_count"],
                  database_unchanged=before == after, database_sha256=after["sha256"])
    path = Path(__file__).resolve().parents[1] / "reports" / "rag_evaluation.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    if before != after:
        raise RuntimeError("Database fingerprint changed during evaluation")
    print("Saved", path)


if __name__ == "__main__":
    main()
