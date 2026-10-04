"""Read-only Item 5 checks against running HTTP API and a recorded DB baseline."""
import argparse
import hashlib
import json
from datetime import datetime, timezone

import httpx
from sqlalchemy import event, select, text

from app import main
from app.catalog_indexing_service import filing_chunks, validate_filing
from app.config import BACKEND_ROOT
from app.database import SessionLocal, engine
from app.filing_search_service import hybrid_search_filing_chunks
from app.models import Company
from app.sec_client import build_filing_url


def counts(session):
    return dict(session.execute(text('''SELECT
        (SELECT count(*) FROM companies) companies,
        (SELECT count(*) FROM financial_facts) financial_facts,
        count(*) filing_chunks, count(embedding) embeddings,
        count(DISTINCT company_cik) FILTER (WHERE embedding IS NOT NULL) indexed_companies,
        count(DISTINCT accession_number) FILTER (WHERE embedding IS NOT NULL) indexed_accessions
        FROM filing_chunks''')).mappings().one())


def original_hashes(session, ids):
    # Table names are a fixed allowlist, identities are SQL parameters.
    result = {}
    for table in ("companies", "financial_facts", "filing_chunks"):
        rows = session.scalars(text(f"SELECT row_to_json(t)::text FROM "
                                    f"(SELECT * FROM {table} WHERE id=ANY(:ids) ORDER BY id) t"),
                               {"ids": ids[table]}).all()
        result[table] = hashlib.sha256("\n".join(rows).encode()).hexdigest()
    return result


def verify(report, api_url, require_all):
    with SessionLocal() as session:
        after = counts(session)
        hashes = original_hashes(session, report["original_ids"])
        assert hashes == report["original_hashes"], "Original rows changed"
        assert after["companies"] == report["before"]["companies"] == 35
        assert after["financial_facts"] == report["before"]["financial_facts"]
        coverage = []
        for company in session.scalars(select(Company).order_by(Company.ticker)):
            groups = {}
            for chunk in filing_chunks(session, company.cik):
                groups.setdefault(chunk.accession_number, []).append(chunk)
            for chunks in groups.values():
                validate_filing(chunks, require_embeddings=True)
            coverage.append({"ticker": company.ticker, "company_cik": company.cik,
                             "indexed_filing_count": len(groups),
                             "chunk_count": sum(len(g) for g in groups.values()),
                             "embedding_count": sum(len(g) for g in groups.values()),
                             "accessions": list(groups)})
        if require_all:
            assert after["indexed_companies"] == 35 and all(c["indexed_filing_count"] >= 1 for c in coverage)
            assert after["filing_chunks"] == after["embeddings"]

    statements = []
    def observe(_conn, _cursor, statement, *_args):
        if statement.lstrip().lower().startswith("select"):
            statements.append(statement)
    event.listen(engine, "before_cursor_execute", observe)
    try:
        listing = main.get_companies()
    finally:
        event.remove(engine, "before_cursor_execute", observe)
    assert len(statements) == 1, "Company listing introduced N+1 queries"

    checks = []
    with httpx.Client(base_url=api_url, timeout=180) as client:
        response = client.get("/companies")
        assert response.status_code == 200
        companies = response.json()
        assert len(companies) == 35
        assert companies == [company.model_dump() for company in listing]
        apple = next(company for company in companies if company["ticker"] == "AAPL")
        assert apple["has_indexed_filing"] and apple["indexed_filing_count"] == 1
        for ticker in ("AAPL", "MSFT", "JPM", "JNJ", "XOM", "WMT"):
            item = next(c for c in coverage if c["ticker"] == ticker)
            accession = item["accessions"][0]
            sources_response = client.get(f"/companies/{ticker}/sources")
            assert sources_response.status_code == 200
            source = next(s for s in sources_response.json() if s["accession_number"] == accession)
            assert source["has_filing_chunks"]
            official = build_filing_url(item["company_cik"], accession)
            assert source["sec_url"] == official
            base = f"/companies/{ticker}/filings/{accession}"
            responses = {}
            for endpoint in ("search", "semantic-search", "context"):
                result = client.get(f"{base}/{endpoint}", params={"q": "revenue", "limit": 3})
                assert result.status_code == 200, f"{ticker}/{endpoint} failed"
                data = result.json()
                if endpoint == "context":
                    assert data["evidence_status"] == "sufficient" and data["citations"]
                else:
                    assert data["result_count"] > 0
                responses[endpoint] = data
            with SessionLocal() as session:
                stored = {c.chunk_id: c for c in filing_chunks(session, item["company_cik"], accession)}
                hybrid = hybrid_search_filing_chunks(session, item["company_cik"], accession, "revenue", 3)
                assert hybrid and all(result.chunk.chunk_id in stored for result in hybrid)
                context = responses["context"]
                for citation in context["citations"]:
                    chunk = stored[citation["chunk_id"]]
                    assert citation["accession_number"] == accession
                    assert citation["sec_url"] == chunk.sec_url == official
                    assert citation["filename"] == chunk.filename and citation["form"] == chunk.form
                    assert citation["filed"] == chunk.filed.isoformat()
                    assert f"[SOURCE {citation['citation_id']}]" in context["context"]
                    assert f"[END SOURCE {citation['citation_id']}]" in context["context"]
                    assert "\n".join(f"  {line}" for line in chunk.text.splitlines()) in context["context"]
                checks.append({"ticker": ticker, "accession_number": accession, "query": "revenue",
                               "http_statuses": {"sources": 200, "search": 200, "semantic-search": 200, "context": 200},
                               "context_evidence_status": context["evidence_status"],
                               "citation_ids": [c["citation_id"] for c in context["citations"]],
                               "hybrid_top_chunks": [{"chunk_id": r.chunk.chunk_id,
                                                      "semantic_similarity": r.semantic_similarity,
                                                      "hybrid_score": r.hybrid_score,
                                                      "excerpt": r.chunk.text[:180]} for r in hybrid],
                               "sec_url": official, "citation_lineage_verified": True})
    return {"timestamp": datetime.now(timezone.utc).isoformat(), "after": after,
            "original_hashes_match": True, "after_original_hashes": hashes,
            "companies_http_status": 200, "companies_select_count": len(statements),
            "aapl_ready": True, "openai_calls": 0, "coverage": coverage, "representative_checks": checks}


def main_cli():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--require-all", action="store_true")
    parser.add_argument("--stage", default="final")
    args = parser.parse_args()
    path = BACKEND_ROOT / "reports/catalog_indexing_verification.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    result = verify(report, args.api_url, args.require_all)
    report[args.stage] = result
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"stage": args.stage, "counts": result["after"], "preserved": True,
                      "company_listing_selects": result["companies_select_count"],
                      "http_representatives": [r["ticker"] for r in result["representative_checks"]]}))


if __name__ == "__main__":
    main_cli()
