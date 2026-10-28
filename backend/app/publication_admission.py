"""Complete publication integrity within an existing caller-owned read snapshot.

Preserves the established Tone admission policy, not a strict Reader resource
policy. Never manages sessions, acquires data, caches evidence or selects a
passage. The digest detects stored inconsistency; it does not authenticate
privileged database writers or replace financial authorization.
"""
from dataclasses import dataclass
from datetime import date
import re

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select

from app.freshness_service import (
    MAX_COMPANY_CHUNKS, admitted_research_chunks, chunk_digest,
    inconsistent_evidence, research_chunk_inventory, schema_ready, scope_too_large,
    valid_document_filename, validate_chunks,
)
from app.models import Company, CompanyRefreshState, FilingChunk, FilingPublication
from app.refresh_contracts import StreamState


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
    if (type(ticker) is not str
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]{0,15}", ticker) is None
            or type(accession) is not str
            or re.fullmatch(r"[0-9]{10}-[0-9]{2}-[0-9]{6}", accession) is None
            or type(expected) is not int or not 0 <= expected <= MAX_SAFE_VERSION):
        raise HTTPException(422, "Invalid publication selector or version pin.")
    company = session.scalar(select(Company).where(Company.ticker == ticker.upper()))
    if company is None:
        raise HTTPException(404, "Unknown company")
    if (company.ticker != ticker.upper() or not isinstance(company.cik, str)
            or re.fullmatch(r"[0-9]{10}", company.cik) is None):
        raise inconsistent_evidence()
    if not schema_ready(session.connection()):
        raise inconsistent_evidence()
    state = session.get(CompanyRefreshState, company.cik)
    if state is None:
        raise inconsistent_evidence()
    if type(state.data_version) is not int or state.data_version != expected:
        raise _version_changed()
    if (state.company_cik != company.cik or type(state.evidence_version) is not int
            or not 0 <= state.evidence_version <= state.data_version):
        raise inconsistent_evidence()
    if not isinstance(state.evidence, dict):
        raise inconsistent_evidence()
    try:
        pending = StreamState.model_validate(state.evidence).pending_targets
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
