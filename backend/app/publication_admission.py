"""Complete publication integrity within an existing caller-owned read snapshot.

Preserves Tone admission and exposes a separate fixed strict Reader entry.
Never manages sessions, acquires data, caches evidence or selects a
passage. The digest detects stored inconsistency; it does not authenticate
privileged database writers or replace financial authorization.
"""
from dataclasses import dataclass
from datetime import date
import re
from numbers import Real

from fastapi import HTTPException
from numpy import ndarray
from pydantic import ValidationError
from sqlalchemy import Text, case, cast, func, select

from app.freshness_service import (
    CHUNK_IDENTITY_FIELDS, MAX_COMPANY_CHUNKS, admitted_research_chunks, chunk_digest,
    inconsistent_evidence, research_chunk_inventory, schema_ready, scope_too_large,
    valid_document_filename, validate_chunks,
)
from app.models import Company, CompanyRefreshState, FilingChunk, FilingPublication
from app.refresh_contracts import StreamState
from app import reader_resource_policy as _reader


MAX_SAFE_VERSION = 9_007_199_254_740_991
PUBLICATION_FIELDS = (
    "company_cik", "accession_number", "form", "filed", "filename",
    "chunk_count", "content_digest", "data_version",
)


@dataclass(frozen=True)
class PublicationManifest:
    company_cik: str
    accession_number: str
    form: str
    filed: date
    filename: str
    chunk_count: int
    content_digest: str
    data_version: int


@dataclass(frozen=True)
class PublicationChunk:
    """Scalar evidence only; validated embeddings and ORM state are not retained."""
    id: int
    company_cik: str
    accession_number: str
    chunk_index: int
    chunk_id: str
    form: str
    filed: date
    filename: str
    start_char: int
    end_char: int
    sec_url: str
    text: str


@dataclass(frozen=True)
class CompletePublication:
    ticker: str
    company_cik: str
    company_name: str
    data_version: int
    evidence_version: int
    publication: PublicationManifest
    chunks: tuple[PublicationChunk, ...]


def _version_changed():
    return HTTPException(409, "Published data changed. Refresh the research scope.",
                         headers={"X-FinLens-Error-Code": "DATA_VERSION_CHANGED"})


def admit_complete_publication(session, ticker, accession, expected) -> CompletePublication:
    """Admit every scoped chunk before returning any detached evidence.

    The caller supplies and closes an existing read snapshot. Only the current
    4000-chunk/3000-character inventory bounds apply; no Reader limits are implied.
    A zero pin is valid and older intact manifests survive unrelated facts updates.
    """
    return _admit_publication(session, ticker, accession, expected, reader=False)


def admit_reader_publication(session, ticker, accession, expected) -> CompletePublication:
    """Fixed strict policy; caller owns the snapshot, cleanup and cancellation.

    No trusted input, policy override, digest bypass or legacy fallback exists.
    This inert helper does not activate a Reader capability or acquire a session.
    """
    try:
        with session.no_autoflush:
            return _admit_publication(session, ticker, accession, expected, reader=True)
    except _reader.ResourceExcess:
        raise scope_too_large() from None
    except _reader.InvalidPayload:
        raise inconsistent_evidence() from None


def _reader_company(session, ticker):
    rows = list(session.execute(select(Company.ticker, Company.cik, Company.name)
                               .where(Company.ticker == ticker.upper()).limit(2)))
    if not rows:
        return None
    if len(rows) != 1:
        raise inconsistent_evidence()
    row = rows[0]
    for field, value in (('ticker', row.ticker), ('company_cik', row.cik), ('company_name', row.name)):
        _reader.scalar(field, value)
    return row


def _reader_state(session, cik):
    # PostgreSQL JSON (not JSONB) -> text preserves stored whitespace/escapes.
    # convert_to explicitly measures UTF-8 regardless of database encoding.
    # CASE guards transfer; it does NOT bound PostgreSQL CPU/RSS/elapsed work.
    raw = cast(CompanyRefreshState.evidence, Text)
    size = func.octet_length(func.convert_to(raw, 'UTF8'))
    rows = list(session.execute(select(
        CompanyRefreshState.company_cik, CompanyRefreshState.data_version,
        CompanyRefreshState.evidence_version, size.label('evidence_bytes'),
        case((size <= _reader.LIFECYCLE_BYTES, raw), else_=None).label('evidence_json'),
    ).where(CompanyRefreshState.company_cik == cik).limit(2)))
    if len(rows) > 1:
        raise inconsistent_evidence()
    return rows[0] if rows else None


def _reader_fields(row, names):
    for name in names:
        _reader.scalar(name, getattr(row, name))


def _reader_chunks(session, publication, predicates):
    order = (FilingChunk.company_cik, FilingChunk.accession_number,
             FilingChunk.chunk_index, FilingChunk.id)
    inventory = list(session.execute(select(
        *(getattr(FilingChunk, f) for f in CHUNK_IDENTITY_FIELDS),
        func.length(FilingChunk.text).label('text_length'),
    ).where(*predicates).order_by(*order).limit(_reader.CHUNKS + 1)))
    if len(inventory) > _reader.CHUNKS:
        raise _reader.ResourceExcess()
    for row in inventory:
        _reader_fields(row, CHUNK_IDENTITY_FIELDS)
        _reader.scalar('text_length', row.text_length)
        if row.text_length > _reader.CHUNK_CHARS:
            raise _reader.ResourceExcess()
    if (len(inventory) != publication.chunk_count
            or len({r.id for r in inventory}) != len(inventory)):
        raise inconsistent_evidence()
    chunks = list(session.execute(select(
        *(getattr(FilingChunk, f) for f in CHUNK_IDENTITY_FIELDS),
        FilingChunk.text, FilingChunk.embedding,
    ).where(*predicates, FilingChunk.id.in_([r.id for r in inventory]),
            func.length(FilingChunk.text) <= _reader.CHUNK_CHARS)
        .order_by(*order).limit(_reader.CHUNKS + 1)))
    if len(chunks) != len(inventory):
        raise inconsistent_evidence()
    for chunk, admitted in zip(chunks, inventory):
        _reader_fields(chunk, CHUNK_IDENTITY_FIELDS)
        if type(chunk.text) is not str:
            raise _reader.InvalidPayload()
        if len(chunk.text) > _reader.CHUNK_CHARS:
            raise _reader.ResourceExcess()
        if (len(chunk.text) != admitted.text_length
                or any(getattr(chunk, f) != getattr(admitted, f) for f in CHUNK_IDENTITY_FIELDS)):
            raise inconsistent_evidence()
        vector = chunk.embedding
        if (type(vector) not in (list, tuple, ndarray)
                or (type(vector) is ndarray and vector.ndim != 1)
                or len(vector) != _reader.VECTOR_DIMENSIONS
                or any(isinstance(v, bool) or not isinstance(v, Real) for v in vector)):
            raise inconsistent_evidence()
    return chunks


def _reader_budget(company, state, publication, chunks):
    # Count every output occurrence, including company/accession/manifest data
    # repeated in each chunk. Vectors are validated but never detached.
    non_text = sum(_reader.logical_bytes(v) for v in (
        company.ticker, company.cik, company.name, state.data_version, state.evidence_version,
        *(getattr(publication, f) for f in PUBLICATION_FIELDS),
    ))
    chars = size = components = 0
    for chunk in chunks:
        non_text += sum(_reader.logical_bytes(getattr(chunk, f)) for f in CHUNK_IDENTITY_FIELDS)
        chars += len(chunk.text)
        size += _reader.logical_bytes(chunk.text)
        components += len(chunk.embedding)
        _reader.detached_budget(non_text, chars, size, components)


def _admit_publication(session, ticker, accession, expected, *, reader):
    """One mandatory integrity pipeline; the public entries fix the read policy."""
    if (type(ticker) is not str
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]{0,15}", ticker) is None
            or type(accession) is not str
            or re.fullmatch(r"[0-9]{10}-[0-9]{2}-[0-9]{6}", accession) is None
            or type(expected) is not int or not 0 <= expected <= MAX_SAFE_VERSION):
        raise HTTPException(422, "Invalid publication selector or version pin.")
    company = (_reader_company(session, ticker) if reader else
               session.scalar(select(Company).where(Company.ticker == ticker.upper())))
    if company is None:
        raise HTTPException(404, "Unknown company")
    if (company.ticker != ticker.upper() or not isinstance(company.cik, str)
            or re.fullmatch(r"[0-9]{10}", company.cik) is None):
        raise inconsistent_evidence()
    if not schema_ready(session.connection()):
        raise inconsistent_evidence()
    state = (_reader_state(session, company.cik) if reader else
             session.get(CompanyRefreshState, company.cik))
    if state is None:
        raise inconsistent_evidence()
    if type(state.data_version) is not int or state.data_version != expected:
        raise _version_changed()
    if (state.company_cik != company.cik or type(state.evidence_version) is not int
            or not 0 <= state.evidence_version <= state.data_version):
        raise inconsistent_evidence()
    if reader:
        _reader_fields(state, ('company_cik', 'data_version', 'evidence_version'))
        evidence = _reader.lifecycle(state.evidence_json, state.evidence_bytes)
    else:
        evidence = state.evidence
    if not isinstance(evidence, dict):
        raise inconsistent_evidence()
    try:
        pending = StreamState.model_validate(evidence).pending_targets
    except ValidationError:
        raise inconsistent_evidence() from None
    if accession in pending:
        raise inconsistent_evidence()

    # Scalar projection only. Even a deferred ORM entity risks accidental full
    # cleaned_text materialization; this reader never obtains that attribute.
    publications = list(session.execute(select(
        *(getattr(FilingPublication, name) for name in PUBLICATION_FIELDS),
    ).where(FilingPublication.company_cik == company.cik,
            FilingPublication.accession_number == accession).limit(2)))
    if len(publications) != 1:
        raise inconsistent_evidence()
    publication = publications[0]
    if reader:
        _reader_fields(publication, PUBLICATION_FIELDS)
    if (publication.company_cik != company.cik or publication.accession_number != accession
            or publication.form not in {"10-K", "10-Q", "10-K/A", "10-Q/A"}
            or type(publication.filed) is not date
            or not valid_document_filename(publication.filename)
            or type(publication.data_version) is not int
            or not 0 <= publication.data_version <= state.evidence_version
            or type(publication.chunk_count) is not int or publication.chunk_count <= 0
            or type(publication.content_digest) is not str
            or re.fullmatch(r"[0-9a-f]{64}", publication.content_digest) is None):
        raise inconsistent_evidence()
    if publication.chunk_count > MAX_COMPANY_CHUNKS:
        raise scope_too_large()
    predicates = (FilingChunk.company_cik == company.cik, FilingChunk.accession_number == accession)
    if reader:
        chunks = _reader_chunks(session, publication, predicates)
        _reader_budget(company, state, publication, chunks)
    else:
        inventory = research_chunk_inventory(session, *predicates)
        if len(inventory) != publication.chunk_count:
            raise inconsistent_evidence()
        chunks = admitted_research_chunks(session, inventory, *predicates)
    if any(c.company_cik != company.cik or c.accession_number != accession
           or any(getattr(c, name) != getattr(publication, name)
                  for name in ("form", "filed", "filename")) for c in chunks):
        raise inconsistent_evidence()
    try:
        validate_chunks(chunks)
        digest = chunk_digest(chunks)
    except (ValueError, TypeError, OverflowError):
        raise inconsistent_evidence() from None
    if digest != publication.content_digest:
        raise inconsistent_evidence()
    return CompletePublication(
        company.ticker, company.cik, company.name, state.data_version, state.evidence_version,
        PublicationManifest(*(getattr(publication, name) for name in PUBLICATION_FIELDS)),
        tuple(PublicationChunk(
            c.id, c.company_cik, c.accession_number, c.chunk_index, c.chunk_id,
            c.form, c.filed, c.filename, c.start_char, c.end_char, c.sec_url, c.text,
        ) for c in chunks),
    )
