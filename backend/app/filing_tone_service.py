"""Server-resolved published-passage tone; no acquisition, caching or generation.

Resolve/validate within the caller's read snapshot, then score the detached exact
text after session closure. Publication integrity is not linguistic accuracy.
"""
from dataclasses import asdict, dataclass
from datetime import date
import re
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict

from app.filing_tone import ToneInputError, ToneMatch, score_filing_tone
from app.publication_admission import (
    MAX_SAFE_VERSION, PUBLICATION_FIELDS, admit_complete_publication,
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
    admitted = admit_complete_publication(session, ticker, accession, expected)
    selected = [c for c in admitted.chunks if c.chunk_id == chunk_id]
    if len(selected) != 1:
        raise HTTPException(404, "Published passage not found in this filing.",
                            headers={"X-FinLens-Error-Code": "TONE_CHUNK_NOT_FOUND"})
    chunk = selected[0]
    publication = admitted.publication
    return PublishedPassage(
        admitted.ticker, admitted.company_cik, admitted.company_name,
        admitted.data_version, admitted.evidence_version,
        TonePublication(accession_number=accession, data_version=publication.data_version,
                        content_digest=publication.content_digest),
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
