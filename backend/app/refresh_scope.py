"""One explicitly authorized canary scope; no acquisition or writes on import.

This is an operator safety boundary, not permission for arbitrary Python callers
or unmanaged SQL writers. The coordinator owns admission throughout the handoff.
"""
from copy import deepcopy
from dataclasses import dataclass
from datetime import date
import hashlib
import json
import re

from sqlalchemy import select

from app.models import Company, FilingChunk, FilingPublication, RefreshAttempt
from app.sec_client import FilingMetadata
from app.sec_importer import FinancialSyncError, merge_company_facts
from app.freshness_service import chunk_digest, stored_chunks, validate_chunks
from app.sec_parser import extract_primary_filing_document

SCOPE = "aapl-10k-2025"
CIK = "0000320193"
NAME = "Apple Inc."
TARGET = FilingMetadata(CIK, "0000320193-25-000079", "10-K", date(2025, 10, 31), "aapl-20250927.htm")
EXISTING = FilingMetadata(CIK, "0000320193-26-000020", "10-Q", date(2026, 7, 31), "aapl-20260627.htm")


class SourceScopeError(FinancialSyncError):
    """Only fixed, non-private error codes may be exposed to the operator."""


def require(condition, code):
    if not condition:
        raise SourceScopeError(code)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()


def filing_identity(item):
    return (item.company_cik, item.accession_number, item.form, item.filed, item.primary_document)


@dataclass(frozen=True)
class PinnedCanarySources:
    # Sources are detached from loader-owned objects. Each consumer receives a
    # separate copy, so callbacks cannot mutate a later consumer's source view.
    _facts: dict
    inventory: tuple[FilingMetadata, ...]
    facts_sha256: str
    inventory_sha256: str

    def facts(self):
        require(digest(self._facts) == self.facts_sha256, "canary_pinned_facts_changed")
        return deepcopy(self._facts)

    def filings(self):
        require(digest([filing_identity(m) for m in self.inventory]) == self.inventory_sha256,
                "canary_pinned_inventory_changed")
        return {"filings": list(self.inventory), "complete": True}

    def evidence(self):
        return {"scope": SCOPE, "status": "validated", "facts_would_insert": 0,
                "facts_sha256": self.facts_sha256, "inventory_sha256": self.inventory_sha256,
                "accession_number": TARGET.accession_number, "company_cik": CIK,
                "form": TARGET.form, "filed": TARGET.filed.isoformat(),
                "primary_document": TARGET.primary_document}


def validate_inventory(session, filings):
    """Validate the entire selected inventory, never its count-capped prefix."""
    require(len(filings) == 2 and all(isinstance(m, FilingMetadata) for m in filings), "canary_inventory_changed")
    require(all(m.company_cik == CIK for m in filings), "canary_inventory_cik_mismatch")
    require({filing_identity(m) for m in filings} == {filing_identity(EXISTING), filing_identity(TARGET)},
            "canary_filing_identity_mismatch")
    publications = list(session.scalars(select(FilingPublication).where(FilingPublication.company_cik == CIK)))
    known = {p.accession_number: p for p in publications}
    require(TARGET.accession_number not in known, "canary_target_already_published")
    missing = [m for m in filings if m.accession_number not in known]
    require(missing == [TARGET], "canary_missing_scope_mismatch")
    prior = known.get(EXISTING.accession_number)
    require(prior is not None and (prior.form, prior.filed, prior.filename) ==
            (EXISTING.form, EXISTING.filed, EXISTING.primary_document), "canary_existing_filing_mismatch")
    chunks = stored_chunks(session, CIK, EXISTING.accession_number)
    try:
        validate_chunks(chunks)
    except ValueError:
        raise SourceScopeError("canary_existing_filing_incomplete") from None
    require(prior.chunk_count == len(chunks) and prior.content_digest == chunk_digest(chunks)
            and all((c.form, c.filed, c.filename) == (EXISTING.form, EXISTING.filed, EXISTING.primary_document)
                    for c in chunks), "canary_existing_filing_mismatch")
    require(session.scalar(select(FilingChunk.id).where(FilingChunk.company_cik == CIK,
            FilingChunk.accession_number == TARGET.accession_number).limit(1)) is None,
            "canary_target_has_unpublished_chunks")


def pin_sources(factory, catalog, facts_loader, inventory_loader, observations, reject_conflicts):
    """Read-only preflight before recovery/attempt/state/publication writes."""
    require(catalog.get("AAPL") == CIK, "canary_catalog_cik_mismatch")
    with factory() as session:
        company = session.scalar(select(Company).where(Company.cik == CIK))
        require(company is not None and company.name == NAME, "canary_catalog_name_mismatch")
        require(session.scalar(select(RefreshAttempt.id).where(RefreshAttempt.status == "running").limit(1)) is None,
                "canary_unsettled_attempt")
    payload = deepcopy(facts_loader(CIK))
    require(isinstance(payload, dict) and payload.get("entityName") == NAME, "canary_source_name_mismatch")
    candidates = observations(CIK, payload)  # Existing identity/precision/provenance rules.
    require(bool(candidates), "canary_supported_facts_unavailable")
    inventory = deepcopy(inventory_loader(CIK))
    require(isinstance(inventory, dict) and inventory.get("complete") is True, "canary_inventory_incomplete")
    filings = tuple(inventory.get("filings", ()))
    with factory() as session:
        reject_conflicts(session, CIK, candidates)
        provisional = merge_company_facts(session, CIK, payload, dry_run=True)
        require(provisional["would_insert"] == 0, "canary_new_facts_forbidden")
        validate_inventory(session, filings)
    return PinnedCanarySources(payload, filings, digest(payload), digest([filing_identity(m) for m in filings]))


def validate_raw_submission(raw, cik, accession):
    """Bind the full SEC submission envelope and primary document to the pin."""
    require((cik, accession) == (CIK, TARGET.accession_number), "canary_raw_target_mismatch")
    require(isinstance(raw, str), "canary_raw_identity_mismatch")
    headers = re.findall(r"<SEC-HEADER>(.*?)</SEC-HEADER>", raw, re.S)
    require(len(headers) == 1, "canary_raw_identity_mismatch")
    prefix = raw.split("<DOCUMENT>", 1)[0]
    names = re.findall(r"^<SEC-DOCUMENT>([^\s:]+)", prefix, re.M)
    require(names == [TARGET.accession_number + ".txt"], "canary_raw_identity_mismatch")
    require(raw.count("</SEC-DOCUMENT>") == 1, "canary_raw_identity_mismatch")
    expected = {"ACCESSION NUMBER": TARGET.accession_number, "CONFORMED SUBMISSION TYPE": TARGET.form,
                "FILED AS OF DATE": TARGET.filed.strftime("%Y%m%d"),
                "CENTRAL INDEX KEY": CIK, "COMPANY CONFORMED NAME": NAME}
    for field, value in expected.items():
        values = re.findall(r"^\s*" + re.escape(field) + r":\s*([^\r\n]+)", headers[0], re.M)
        require([v.strip() for v in values] == [value], "canary_raw_identity_mismatch")
    require(len(re.findall(r"^<TYPE>\s*10-K\s*$", raw, re.M)) == 1, "canary_raw_primary_ambiguous")
    primary = extract_primary_filing_document(raw, TARGET.form)
    require(primary["filename"] == TARGET.primary_document, "canary_raw_primary_mismatch")
