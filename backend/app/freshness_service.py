"""Read-only freshness, consistent API snapshots and complete evidence gates."""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import timedelta, timezone
import hashlib
import re
from weakref import WeakKeyDictionary

from fastapi import HTTPException
from sqlalchemy import func, inspect, select, text
from sqlalchemy.orm import load_only

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
    row = session.get(CompanyRefreshState, company.cik) if schema_ready(session.connection()) else None
    if row is None:
        # The frontend consumes the body pin. Missing metadata must never use
        # Freshness's numeric defaults, even when no version header is attached.
        raise HTTPException(503, detail="Publication freshness is unavailable. Try again later.",
                            headers={"X-FinLens-Error-Code": "FRESHNESS_UNAVAILABLE"})
    result = Freshness(ticker=company.ticker, data_version=row.data_version,
                       facts_version=row.facts_version, evidence_version=row.evidence_version)
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
    session = factory()
    connection = None
    try:
        if session.get_bind().dialect.name == "postgresql":
            connection = session.connection()
            session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        scope = request_scope.get()
        if scope and scope.get("ticker"):
            version = None
            if schema_ready(session.connection()):
                version = session.scalar(select(CompanyRefreshState.data_version).join(
                    Company, Company.cik == CompanyRefreshState.company_cik).where(Company.ticker == scope["ticker"]))
            if version is not None and (type(version) is not int or version < 0):
                raise ValueError("Invalid publication version metadata.")
            # Zero is a verified publication. Missing metadata is unverified,
            # not an invented version-zero publication.
            scope["version"] = version
            if scope.get("expected") is not None and (version is None or scope["expected"] != str(version)):
                raise HTTPException(409, detail="Published data changed. Refresh the research scope.", headers={"X-FinLens-Error-Code": "DATA_VERSION_CHANGED"})
        yield session
    except BaseException:
        # Cleanup must not replace a primary query/programming/research error.
        # A failed close cannot return a suspect connection to another request.
        try:
            session.close()
        except BaseException:
            _invalidate_read_session(session, connection)
        raise
    else:
        try:
            session.close()
        except BaseException:
            _invalidate_read_session(session, connection)
            raise


def _invalidate_read_session(session, connection):
    # Session.close may detach its transaction before a rollback failure, so
    # keep the already acquired connection and invalidate it directly as well.
    if connection is not None:
        try:
            connection.invalidate()
        except BaseException:
            pass
    try:
        session.invalidate()
    except BaseException:
        # Preserve the original failure after discarding the physical connection.
        pass


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


MAX_COMPANY_FILINGS = 20
MAX_COMPANY_CHUNKS = 4000
MAX_COMPANY_CHUNK_CHARS = 3000


def valid_document_filename(filename):
    """A plain SEC document basename, never a path or source-framing fragment."""
    return (isinstance(filename, str) and filename not in {".", ".."}
            and re.fullmatch(r"[A-Za-z0-9_.-]{1,255}", filename) is not None)


def published_company_chunks(session, cik):
    """Read and verify a bounded whole-publication inventory in the read snapshot.

    No legacy reconstruction or writes. Old intact publications remain searchable
    after an unrelated refresh failure; explicit pending targets are excluded.
    """
    if not schema_ready(session.connection()):
        raise HTTPException(409, "Company-wide search requires publication metadata.",
                            headers={"X-FinLens-Error-Code": "EVIDENCE_PENDING"})
    state = session.get(CompanyRefreshState, cik)
    if state is None:
        raise HTTPException(409, "Company-wide search requires publication version metadata.",
                            headers={"X-FinLens-Error-Code": "EVIDENCE_PENDING"})
    if not 0 <= state.evidence_version <= state.data_version:
        raise HTTPException(409, "Published data changed. Refresh the research scope.",
                            headers={"X-FinLens-Error-Code": "DATA_VERSION_CHANGED"})
    pending = StreamState.model_validate(state.evidence or {}).pending_targets
    publications = list(session.scalars(select(FilingPublication).options(load_only(
        FilingPublication.company_cik, FilingPublication.accession_number,
        FilingPublication.form, FilingPublication.filed, FilingPublication.filename,
        FilingPublication.chunk_count, FilingPublication.content_digest,
        FilingPublication.data_version,
    )).where(FilingPublication.company_cik == cik,
             FilingPublication.accession_number.not_in(pending))
        .order_by(FilingPublication.accession_number).limit(MAX_COMPANY_FILINGS + 1)))
    if len(publications) > MAX_COMPANY_FILINGS:
        raise HTTPException(409, "Company-wide search exceeds its filing limit. Use selected-filing search.",
                            headers={"X-FinLens-Error-Code": "SEARCH_SCOPE_TOO_LARGE"})
    if any(p.data_version < 0 or p.data_version > state.evidence_version for p in publications):
        raise HTTPException(409, "Published data changed. Refresh the research scope.",
                            headers={"X-FinLens-Error-Code": "DATA_VERSION_CHANGED"})
    valid_publications = [p for p in publications if valid_document_filename(p.filename)]
    inventory = list(session.execute(select(
        FilingChunk.id, FilingChunk.accession_number, func.length(FilingChunk.text).label("text_length"),
    ).where(
        FilingChunk.company_cik == cik,
        FilingChunk.accession_number.in_([p.accession_number for p in valid_publications]),
    ).order_by(FilingChunk.accession_number, FilingChunk.chunk_index, FilingChunk.id)
        .limit(MAX_COMPANY_CHUNKS + 1))) if valid_publications else []
    if len(inventory) > MAX_COMPANY_CHUNKS:
        raise HTTPException(409, "Company-wide search exceeds its chunk limit. Use selected-filing search.",
                            headers={"X-FinLens-Error-Code": "SEARCH_SCOPE_TOO_LARGE"})
    oversized = {row.accession_number for row in inventory
                 if row.text_length is None or row.text_length > MAX_COMPANY_CHUNK_CHARS}
    ids = [row.id for row in inventory if row.accession_number not in oversized]
    # Text is selected only after the bounded length projection rejects entire
    # oversized publications. The SQL predicate also prevents a widened body from
    # materializing on non-PostgreSQL callers without repeatable-read isolation.
    rows = list(session.scalars(select(FilingChunk).where(
        FilingChunk.company_cik == cik, FilingChunk.id.in_(ids),
        func.length(FilingChunk.text) <= MAX_COMPANY_CHUNK_CHARS,
    ).order_by(FilingChunk.accession_number, FilingChunk.chunk_index, FilingChunk.id)
        .limit(MAX_COMPANY_CHUNKS + 1))) if ids else []
    groups = {}
    for chunk in rows:
        groups.setdefault(chunk.accession_number, []).append(chunk)
    chunks, eligible = [], []
    for publication in valid_publications:
        group = groups.get(publication.accession_number, [])
        if (len(group) != publication.chunk_count or not group
                or any(c.company_cik != cik or not valid_document_filename(c.filename)
                       or len(c.text) > MAX_COMPANY_CHUNK_CHARS
                       or any(getattr(c, field) != getattr(publication, field)
                              for field in ("form", "filed", "filename")) for c in group)):
            continue
        try:
            validate_chunks(group)
        except (ValueError, TypeError):
            continue
        if chunk_digest(group) != publication.content_digest:
            continue
        eligible.append(publication.accession_number)
        chunks.extend(group)
    return chunks, {
        "data_version": state.data_version, "evidence_version": state.evidence_version,
        "searched_accessions": eligible,
        "excluded_publication_count": len(publications) - len(eligible),
    }
