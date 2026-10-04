"""Resumable filing indexing, with no Company Facts import or LLM dependency."""
from dataclasses import asdict
from datetime import datetime, timezone

import httpx
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.embedding_service import embed_filing_chunks, validate_embedding
from app.models import Company, FilingChunk
from app.sec_client import FilingMetadata, build_filing_url, discover_filing
from app.sec_filing_service import ingest_filing_chunks


def filing_chunks(session: Session, cik: str, accession: str | None = None):
    statement = select(FilingChunk).where(FilingChunk.company_cik == cik)
    if accession is not None:
        statement = statement.where(FilingChunk.accession_number == accession)
    return list(session.scalars(statement.order_by(FilingChunk.accession_number, FilingChunk.chunk_index)).all())


def validate_filing(chunks, *, require_embeddings=False):
    if not chunks:
        raise ValueError("No persisted chunks.")
    first = chunks[0]
    for index, chunk in enumerate(chunks):
        if (chunk.chunk_index != index or chunk.chunk_id != f"chunk_{index:04d}"
                or not chunk.text.strip() or not chunk.filename or not chunk.filed
                or chunk.form not in {"10-Q", "10-K"}
                or chunk.start_char < 0 or chunk.end_char <= chunk.start_char
                or len(chunk.text) > chunk.end_char - chunk.start_char
                or any(getattr(chunk, field) != getattr(first, field) for field in
                       ("company_cik", "accession_number", "form", "filed", "filename"))
                or chunk.sec_url != build_filing_url(chunk.company_cik, chunk.accession_number)):
            raise ValueError("Persisted filing metadata/text is invalid; no automatic replacement.")
        if chunk.embedding is None:
            if require_embeddings:
                raise ValueError("Embeddings are incomplete.")
        else:
            validate_embedding(chunk.embedding)


def filing_record(metadata, chunks, action):
    record = asdict(metadata)
    record["filed"] = metadata.filed.isoformat()
    return {**record, "sec_url": build_filing_url(metadata.company_cik, metadata.accession_number),
            "chunk_count": len(chunks), "embedding_count": sum(c.embedding is not None for c in chunks),
            "status": action}


def index_company(session, company, *, dry_run=False):
    stage = "validation"
    metadata = None
    chunks = []
    accession_diagnostics = []
    company_cik = company.cik

    def reported(result):
        if accession_diagnostics:
            result["accession_diagnostics"] = accession_diagnostics
        return result

    try:
        # Any fully valid existing accession satisfies baseline coverage. Prefer
        # it over new discovery; do not refresh or overwrite historical data.
        stored = filing_chunks(session, company.cik)
        groups = {}
        for chunk in stored:
            groups.setdefault(chunk.accession_number, []).append(chunk)
        complete = []
        valid = []
        for group in groups.values():
            accession = group[0].accession_number
            try:
                validate_filing(group)
            except ValueError:
                accession_diagnostics.append({
                    "accession_number": accession, "status": "invalid",
                    "error": "Stored metadata/text/vector validation failed; rows were not replaced.",
                })
                continue
            valid.append(group)
            if all(c.embedding is not None for c in group):
                complete.append(group)
            else:
                accession_diagnostics.append({
                    "accession_number": accession, "status": "incomplete",
                    "missing_embeddings": sum(c.embedding is None for c in group),
                })
        if complete:
            chunks = max(complete, key=lambda group: (group[0].filed, group[0].accession_number))
            first = chunks[0]
            metadata = FilingMetadata(company.cik, first.accession_number, first.form, first.filed, first.filename)
            return reported(filing_record(metadata, chunks, "skipped"))
        if valid:
            # Committed chunks survive embedding failure; resume without SEC.
            chunks = max(valid, key=lambda group: (group[0].filed, group[0].accession_number))
            first = chunks[0]
            metadata = FilingMetadata(company.cik, first.accession_number, first.form, first.filed, first.filename)
            action = "resumed"
        elif groups:
            raise ValueError("No valid stored accession; inspect invalid rows before replacement.")
        else:
            stage = "discovery"
            metadata = discover_filing(company.cik)
            if metadata is None:
                return {"status": "failed", "error_stage": "no_supported_filing",
                        "error": "No exact 10-Q or 10-K found for the current SEC registrant.",
                        "chunk_count": 0, "embedding_count": 0}
            action = "indexed"
        if dry_run:
            return reported(filing_record(metadata, chunks, "discovered" if not chunks else "incomplete"))
        if not chunks:
            stage = "ingestion"
            ingest_filing_chunks(session, company, metadata.accession_number,
                                 metadata=metadata, preserve_existing=True)
            chunks = filing_chunks(session, company.cik, metadata.accession_number)
            stage = "validation"
            validate_filing(chunks)
        stage = "embedding"
        embed_filing_chunks(session, company.cik, metadata.accession_number)
        session.expire_all()
        chunks = filing_chunks(session, company.cik, metadata.accession_number)
        stage = "validation"
        validate_filing(chunks, require_embeddings=True)
        accession_diagnostics = [item for item in accession_diagnostics
                                 if item["accession_number"] != metadata.accession_number]
        return reported(filing_record(metadata, chunks, action))
    except Exception as exc:
        # Exception text/SQL/HTTP bodies can expose private configuration. Only
        # controlled category and HTTP status are reported, never arbitrary text.
        error_stage = stage
        if stage == "ingestion":
            error_stage = "persistence" if isinstance(exc, SQLAlchemyError) else "parse_or_primary_document"
        if isinstance(exc, httpx.HTTPError):
            error_stage = "discovery_network" if stage == "discovery" else "primary_document_network"
        result = {"status": "failed", "error_stage": error_stage,
                  "error": f"{type(exc).__name__}: {error_stage} failed; existing rows preserved; inspect and rerun.",
                  "chunk_count": len(chunks), "embedding_count": 0}
        if isinstance(exc, httpx.HTTPStatusError):
            result["http_status"] = exc.response.status_code
        if metadata:
            result.update(filing_record(metadata, [], "failed"))
        # Include actual committed counts even when validation failed before a
        # filing could be selected. Report presence, not fabricated readiness.
        try:
            session.rollback()
            persisted = filing_chunks(session, company_cik, metadata.accession_number if metadata else None)
            result.update(chunk_count=len(persisted), embedding_count=sum(c.embedding is not None for c in persisted))
        except Exception:
            result.update(chunk_count=None, embedding_count=None, diagnostic_status="unavailable")
            try:
                session.rollback()
            except SQLAlchemyError:
                pass  # A final catalog readiness read will report a continuing outage.
        return reported(result)


def index_catalog(session: Session, tickers=None, *, dry_run=False, on_result=None):
    # Immutable scalar identities survive rollback/commit without ORM reloads
    # outside the company-level exception boundary.
    catalog = list(session.execute(select(Company.ticker, Company.cik).order_by(Company.ticker)).all())
    requested = {ticker.upper() for ticker in tickers} if tickers else None
    if requested and requested - {company.ticker for company in catalog}:
        raise ValueError("Requested ticker is not in the stored company catalog.")
    selected = [company for company in catalog if requested is None or company.ticker in requested]
    results = []
    for company in selected:
        ticker, cik = company.ticker, company.cik
        result = {"ticker": ticker, "company_cik": cik, **index_company(session, company, dry_run=dry_run)}
        results.append(result)
        if on_result:
            on_result(result)
    catalog_error = None
    try:
        ready = session.scalar(select(func.count(func.distinct(FilingChunk.company_cik))).where(
            FilingChunk.embedding.is_not(None), FilingChunk.company_cik.in_([c.cik for c in catalog]),
        ))
    except SQLAlchemyError:
        ready = None
        catalog_error = "Database readiness check unavailable; resolve database access and rerun."
        try:
            session.rollback()
        except SQLAlchemyError:
            pass
    report = {"timestamp": datetime.now(timezone.utc).isoformat(), "dry_run": dry_run,
            "catalog_total": len(catalog), "selected_total": len(selected),
            "skipped": sum(r["status"] == "skipped" for r in results),
            "newly_indexed": sum(r["status"] == "indexed" for r in results),
            "resumed": sum(r["status"] == "resumed" for r in results),
            "failed": sum(r["status"] == "failed" for r in results),
            "final_ready": ready, "openai_calls": 0, "companies": results}
    if catalog_error:
        report["catalog_error"] = catalog_error
    return report
