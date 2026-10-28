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
from app import evidence_latency as latency

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
    latest = session.execute(select(FilingPublication.accession_number, FilingPublication.form,
                                   FilingPublication.filed).where(FilingPublication.company_cik == company.cik)
                            .order_by(FilingPublication.filed.desc(), FilingPublication.accession_number.desc()).limit(1))
    latest = latest.first()
    if latest:
        result.latest_indexed_filing = FilingIdentity(accession_number=latest.accession_number, form=latest.form, filed=latest.filed)
    return result


@contextmanager
def read_session(factory):
    with latency.span("session_factory"):
        session = factory()
    connection = None
    try:
        if session.get_bind().dialect.name == "postgresql":
            # Composite interval: pool wait, physical setup and SQLAlchemy work may
            # all occur here. It is not a pure pool-checkout measurement.
            with latency.span("connection_acquire_composite"):
                connection = session.connection()
            with latency.span("transaction_setup"):
                session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        scope = request_scope.get()
        if scope and scope.get("ticker"):
            version = None
            with latency.span("version_pin_read"):
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
        with latency.span("session_cleanup"):
            try:
                with latency.span("session_close"):
                    session.close()
            except BaseException:
                with latency.span("session_invalidation"):
                    _invalidate_read_session(session, connection)
        raise
    else:
        with latency.span("session_cleanup"):
            try:
                with latency.span("session_close"):
                    session.close()
            except BaseException:
                with latency.span("session_invalidation"):
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


MAX_COMPANY_FILINGS = 20
MAX_COMPANY_CHUNKS = 4000
MAX_COMPANY_CHUNK_CHARS = 3000
MAX_STORED_TEXT_CHARS = 12000000
CHUNK_IDENTITY_FIELDS = (
    "id", "company_cik", "accession_number", "chunk_index", "chunk_id",
    "form", "filed", "filename", "start_char", "end_char", "sec_url",
)


def validate_research_input(query, limit=5):
    """Validate decoded input before normalization, sessions or retrieval work."""
    if not isinstance(query, str) or not 1 <= len(query) <= 2000 or not query.strip():
        raise HTTPException(422, "query must contain 1–2000 characters and non-whitespace text")
    if type(limit) is not int or not 1 <= limit <= 50:
        raise HTTPException(422, "limit must be an integer between 1 and 50")


def scope_too_large():
    return HTTPException(409, "Research scope exceeds its resource limit. Use a smaller scope.",
                         headers={"X-FinLens-Error-Code": "SEARCH_SCOPE_TOO_LARGE"})


def inconsistent_evidence():
    return HTTPException(409, "Stored evidence changed or is incomplete. Refresh the research scope.",
                         headers={"X-FinLens-Error-Code": "EVIDENCE_PENDING"})


def validate_research_chunks(chunks):
    """Also protect directly callable ranking helpers with already loaded bodies."""
    if len(chunks) > MAX_COMPANY_CHUNKS or any(
            c.text is None or len(c.text) > MAX_COMPANY_CHUNK_CHARS for c in chunks):
        raise scope_too_large()


def research_chunk_inventory(session, *predicates):
    # Never select text or vectors in admission; the sentinel covers ALL scoped
    # chunks, including missing embeddings and passages that would rank last.
    with latency.span("chunk_inventory_read"):
        inventory = list(session.execute(select(
            *(getattr(FilingChunk, field) for field in CHUNK_IDENTITY_FIELDS),
            func.length(FilingChunk.text).label("text_length"),
        ).where(*predicates).order_by(
            FilingChunk.company_cik, FilingChunk.accession_number, FilingChunk.chunk_index, FilingChunk.id,
        ).limit(MAX_COMPANY_CHUNKS + 1)))
    if len(inventory) > MAX_COMPANY_CHUNKS or any(
            r.text_length is None or r.text_length > MAX_COMPANY_CHUNK_CHARS for r in inventory):
        raise scope_too_large()
    if len({r.id for r in inventory}) != len(inventory):
        raise inconsistent_evidence()
    return inventory


def admitted_research_chunks(session, inventory, *predicates, distance=None):
    if not inventory:
        return []
    # Keep the original scope as well as IDs and a length guard. Full admission
    # must match the body read before callers may rank, filter vectors or top-k.
    stmt = select(FilingChunk) if distance is None else select(FilingChunk, distance)
    stmt = stmt.where(*predicates, FilingChunk.id.in_([r.id for r in inventory]),
                      func.length(FilingChunk.text) <= MAX_COMPANY_CHUNK_CHARS)
    stmt = stmt.order_by(FilingChunk.company_cik, FilingChunk.accession_number,
                        FilingChunk.chunk_index, FilingChunk.id) if distance is None else stmt.order_by(distance)
    stmt = stmt.limit(MAX_COMPANY_CHUNKS + 1).execution_options(populate_existing=True)
    with latency.span("chunk_body_read"):
        rows = list(session.scalars(stmt)) if distance is None else list(session.execute(stmt))
    with latency.span("chunk_admission"):
        chunks = rows if distance is None else [row[0] for row in rows]
        expected = {row.id: row for row in inventory}
        if len(chunks) != len(inventory) or len({c.id for c in chunks}) != len(chunks):
            raise inconsistent_evidence()
        for chunk in chunks:
            admitted = expected.get(chunk.id)
            if (admitted is None or chunk.text is None or len(chunk.text) != admitted.text_length
                    or any(getattr(chunk, f) != getattr(admitted, f) for f in CHUNK_IDENTITY_FIELDS)):
                raise inconsistent_evidence()
    return rows


def research_chunks(session, *predicates):
    return admitted_research_chunks(session, research_chunk_inventory(session, *predicates), *predicates)


def stored_research_text(session, cik, accession):
    unavailable = HTTPException(409, "Exact full text is not stored. Published evidence chunks remain available.",
                                headers={"X-FinLens-Error-Code": "STORED_TEXT_UNAVAILABLE"})
    if not schema_ready(session.connection()):
        raise unavailable
    predicates = (FilingPublication.company_cik == cik, FilingPublication.accession_number == accession)
    size = session.scalar(select(func.length(FilingPublication.cleaned_text)).where(*predicates))
    if size is None:
        raise unavailable
    if size > MAX_STORED_TEXT_CHARS:
        raise scope_too_large()
    body = session.scalar(select(FilingPublication.cleaned_text).where(
        *predicates, func.length(FilingPublication.cleaned_text) <= MAX_STORED_TEXT_CHARS))
    if body is None or len(body) != size:
        raise inconsistent_evidence()
    return body


def validate_chunks(chunks):
    from app.embedding_validation import validate_embedding
    from app.sec_urls import build_filing_url
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
        if session.scalar(select(FilingPublication.accession_number).where(
                FilingPublication.company_cik == cik, FilingPublication.accession_number == accession)) is not None:
            return
    else:
        # Unmigrated read-only deployment: validate existing complete evidence,
        # report freshness unknown. No operational metadata writes on reads.
        try:
            validate_chunks(research_chunks(session, FilingChunk.company_cik == cik,
                                            FilingChunk.accession_number == accession))
            return
        except ValueError:
            pass
    raise HTTPException(409, detail="This filing is not completely published for research.", headers={"X-FinLens-Error-Code": "EVIDENCE_PENDING"})


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
    with latency.span("publication_state_read"):
        state = session.get(CompanyRefreshState, cik)
    if state is None:
        raise HTTPException(409, "Company-wide search requires publication version metadata.",
                            headers={"X-FinLens-Error-Code": "EVIDENCE_PENDING"})
    if not 0 <= state.evidence_version <= state.data_version:
        raise HTTPException(409, "Published data changed. Refresh the research scope.",
                            headers={"X-FinLens-Error-Code": "DATA_VERSION_CHANGED"})
    pending = StreamState.model_validate(state.evidence or {}).pending_targets
    with latency.span("publication_read"):
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
    predicates = (
        FilingChunk.company_cik == cik,
        FilingChunk.accession_number.in_([p.accession_number for p in valid_publications]),
    )
    rows = research_chunks(session, *predicates) if valid_publications else []
    with latency.span("publication_eligibility"):
        groups = {}
        for chunk in rows:
            groups.setdefault(chunk.accession_number, []).append(chunk)
        chunks, eligible = [], []
        for publication in valid_publications:
            group = groups.get(publication.accession_number, [])
            with latency.span("publication_validation"):
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
            with latency.span("publication_digest"):
                if chunk_digest(group) != publication.content_digest:
                    continue
            eligible.append(publication.accession_number)
            chunks.extend(group)
    return chunks, {
        "data_version": state.data_version, "evidence_version": state.evidence_version,
        "searched_accessions": eligible,
        "excluded_publication_count": len(publications) - len(eligible),
    }
