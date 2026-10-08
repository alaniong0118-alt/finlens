"""Read-only freshness, consistent API snapshots and complete evidence gates."""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import timedelta, timezone
import hashlib
from weakref import WeakKeyDictionary

from fastapi import HTTPException
from sqlalchemy import inspect, select, text

from app.models import Company, CompanyRefreshState, FilingChunk, FilingPublication
from app.refresh_contracts import FilingIdentity, Freshness, StreamState, utcnow

_schemas = WeakKeyDictionary()
request_scope = ContextVar("finlens_read_scope", default=None)


def schema_ready(bind):
    """Schema capability only, not data cache. Restart API after migrations."""
    engine = getattr(bind, "engine", bind)
    if engine not in _schemas:
        _schemas[engine] = inspect(bind).has_table("company_refresh_state")
    return _schemas[engine]


def stream_state(raw, now=None):
    state = StreamState.model_validate(raw or {})
    now = now or utcnow()
    if state.status == "current":
        checked = state.last_checked_at
        if checked is None or not state.inventory_complete:
            state.status = "unknown"
        elif now - checked.replace(tzinfo=checked.tzinfo or timezone.utc) > timedelta(hours=36):
            state.status = "stale"
    return state


def freshness(session, ticker):
    company = session.scalar(select(Company).where(Company.ticker == ticker.upper()))
    if company is None:
        raise HTTPException(404, detail="Unknown company")
    if not schema_ready(session.connection()):
        return Freshness(ticker=company.ticker, migration_required=True)
    row = session.get(CompanyRefreshState, company.cik)
    result = Freshness(ticker=company.ticker)
    if row:
        result.data_version, result.facts_version, result.evidence_version = row.data_version, row.facts_version, row.evidence_version
        result.facts, result.evidence = stream_state(row.facts), stream_state(row.evidence)
    result.status = next((status for status in ("failed", "pending", "stale", "unknown", "current")
                          if status in {result.facts.status, result.evidence.status}), "unknown")
    latest = session.scalar(select(FilingPublication).where(FilingPublication.company_cik == company.cik)
                            .order_by(FilingPublication.filed.desc(), FilingPublication.accession_number.desc()).limit(1))
    if latest:
        result.latest_indexed_filing = FilingIdentity(accession_number=latest.accession_number, form=latest.form, filed=latest.filed)
    return result


@contextmanager
def read_session(factory):
    with factory() as session:
        if session.get_bind().dialect.name == "postgresql":
            session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        scope = request_scope.get()
        if scope and scope.get("ticker") and schema_ready(session.connection()):
            version = session.scalar(select(CompanyRefreshState.data_version).join(
                Company, Company.cik == CompanyRefreshState.company_cik).where(Company.ticker == scope["ticker"])) or 0
            scope["version"] = version
            if scope.get("expected") is not None and scope["expected"] != str(version):
                raise HTTPException(409, detail="Published data changed. Refresh the research scope.", headers={"X-FinLens-Error-Code": "DATA_VERSION_CHANGED"})
        yield session


def stored_chunks(session, cik, accession):
    return list(session.scalars(select(FilingChunk).where(FilingChunk.company_cik == cik,
        FilingChunk.accession_number == accession).order_by(FilingChunk.chunk_index)))


def validate_chunks(chunks):
    from app.embedding_service import validate_embedding
    from app.sec_client import build_filing_url
    if not chunks:
        raise ValueError("empty_filing")
    first = chunks[0]
    for i, c in enumerate(chunks):
        if (c.chunk_index != i or c.chunk_id != f"chunk_{i:04d}" or not c.text.strip()
                or c.form not in {"10-Q", "10-K", "10-Q/A", "10-K/A"} or not c.filed or not c.filename
                or c.start_char < 0 or c.end_char <= c.start_char or len(c.text) > c.end_char-c.start_char
                or any(getattr(c, f) != getattr(first, f) for f in ("company_cik", "accession_number", "form", "filed", "filename"))
                or c.sec_url != build_filing_url(c.company_cik, c.accession_number)):
            raise ValueError("invalid_filing")
        if c.embedding is None:
            raise ValueError("incomplete_embeddings")
        validate_embedding(c.embedding)


def chunk_digest(chunks):
    return hashlib.sha256("\n".join(f"{c.chunk_index}:{c.start_char}:{c.end_char}:{c.text}" for c in chunks).encode()).hexdigest()


def require_published(session, cik, accession):
    if schema_ready(session.connection()):
        if session.get(FilingPublication, (cik, accession)) is not None:
            return
    else:
        # Unmigrated read-only deployment: validate existing complete evidence,
        # report freshness unknown. No operational metadata writes on reads.
        try:
            validate_chunks(stored_chunks(session, cik, accession))
            return
        except ValueError:
            pass
    raise HTTPException(409, detail="This filing is not completely published for research.", headers={"X-FinLens-Error-Code": "EVIDENCE_PENDING"})
