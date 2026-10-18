"""Server-resolved published-passage tone; no acquisition, caching or generation.

Resolve/validate within the caller's read snapshot, then score the detached exact
text after session closure. Publication integrity is not linguistic accuracy.
"""
from dataclasses import asdict, dataclass
from datetime import date
import re
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy import select

from app.filing_tone import ToneInputError, ToneMatch, score_filing_tone
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


def _invalid_request():
    return HTTPException(422, "Invalid filing tone selector or publication pin.",
                         headers={"X-FinLens-Error-Code": "TONE_INVALID_INPUT"})


def validate_tone_request(ticker, accession, chunk_id, pin) -> int:
    """Validate decoded selectors and canonical pin before opening a session."""
    for value, pattern in (
        (ticker, r"[A-Za-z0-9][A-Za-z0-9.-]{0,15}"),
        (accession, r"[0-9]{10}-[0-9]{2}-[0-9]{6}"),
        (chunk_id, r"chunk_[0-9]{4}"),
        (pin, r"(?:0|[1-9][0-9]{0,15})"),
    ):
        if type(value) is not str or re.fullmatch(pattern, value) is None:
            raise _invalid_request()
    version = int(pin)
    if version > MAX_SAFE_VERSION:
        raise _invalid_request()
    return version


def _version_changed():
    return HTTPException(409, "Published data changed. Refresh the research scope.",
                         headers={"X-FinLens-Error-Code": "DATA_VERSION_CHANGED"})


class _ResponseModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ToneFraction(_ResponseModel):
    numerator: int
    denominator: int


class ToneDetails(_ResponseModel):
    method_version: Literal["sec-filing-tone-v1"]
    lexicon_version: Literal["authored-finance-tone-v1"]
    status: Literal["scored", "unscorable"]
    reason: Literal["no_tokens", "no_lexicon_matches", "all_matches_negated"] | None
    score: ToneFraction | None
    token_count: int
    positive_count: int
    negative_count: int
    negated_count: int
    matches: tuple[ToneMatch, ...]


class TonePublication(_ResponseModel):
    accession_number: str
    data_version: int
    content_digest: str


class ToneSource(_ResponseModel):
    chunk_id: str
    form: str
    filed: date
    filename: str
    sec_url: str


class FilingToneResponse(_ResponseModel):
    """Lexical tone proxy over one passage, not investment sentiment, risk or prediction."""
    ticker: str
    company_cik: str
    company_name: str
    data_version: int
    evidence_version: int
    publication: TonePublication
    source: ToneSource
    scope: Literal["published_chunk"] = "published_chunk"
    offsets: Literal["unicode_code_point"] = "unicode_code_point"
    text: str
    tone: ToneDetails


@dataclass(frozen=True)
class PublishedPassage:
    """Detached value only: never retain ORM rows, lazy attributes or a session."""
    ticker: str
    company_cik: str
    company_name: str
    data_version: int
    evidence_version: int
    publication: TonePublication
    source: ToneSource
    text: str


def resolve_published_passage(session, ticker, accession, chunk_id, pin) -> PublishedPassage:
    expected = validate_tone_request(ticker, accession, chunk_id, pin)
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
    selected = [c for c in chunks if c.chunk_id == chunk_id]
    if len(selected) != 1:
        raise HTTPException(404, "Published passage not found in this filing.",
                            headers={"X-FinLens-Error-Code": "TONE_CHUNK_NOT_FOUND"})
    chunk = selected[0]
    return PublishedPassage(
        company.ticker, company.cik, company.name, state.data_version, state.evidence_version,
        TonePublication(accession_number=accession, data_version=publication.data_version,
                        content_digest=digest),
        ToneSource(chunk_id=chunk.chunk_id, form=chunk.form, filed=chunk.filed,
                   filename=chunk.filename, sec_url=chunk.sec_url), chunk.text,
    )


def score_published_passage(passage: PublishedPassage) -> FilingToneResponse:
    """Call only after the resolver's read session has closed successfully."""
    try:
        result = score_filing_tone(passage.text)
    except ToneInputError:
        raise HTTPException(409, "Stored passage is unsupported by this tone method.",
                            headers={"X-FinLens-Error-Code": "TONE_INPUT_UNSUPPORTED"}) from None
    values = asdict(result)
    values["score"] = (ToneFraction(numerator=result.score.numerator,
                                    denominator=result.score.denominator)
                       if result.score is not None else None)
    return FilingToneResponse(
        ticker=passage.ticker, company_cik=passage.company_cik, company_name=passage.company_name,
        data_version=passage.data_version, evidence_version=passage.evidence_version,
        publication=passage.publication, source=passage.source, text=passage.text,
        tone=ToneDetails.model_validate(values),
    )
