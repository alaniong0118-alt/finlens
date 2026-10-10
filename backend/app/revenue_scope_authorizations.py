"""Bounded, offline revenue permissions. Production registries are deliberately empty.

Evidence inputs must come from independently verified documents/XBRL contexts,
not from approval records or Company Facts frame/fiscal annotations. This module
does not load documents, write data, reconcile restatements or infer equivalences.
"""
from dataclasses import asdict, dataclass, replace
from datetime import date
from decimal import Decimal
import hashlib
import json
import re
from typing import Literal

from app.financial_metric_registry import METRICS
from app.sec_parser import classify_period

Permission = Literal["select:revenue", "denominator:net_margin"]


def _nonempty(value):
    return isinstance(value, str) and bool(value.strip())


@dataclass(frozen=True)
class SourceIdentity:
    cik: str
    source_namespace: str
    taxonomy_namespace: str
    concept: str
    start: date
    end: date
    kind: str
    unit: str
    value: Decimal
    accession: str
    form: str
    filed: date

    @classmethod
    def from_fact(cls, fact):
        # The existing importer reads only the us-gaap Company Facts namespace.
        prefix = "SEC Company Facts API: "
        return cls(fact.company_cik, "SEC Company Facts API", "us-gaap",
                   fact.source.removeprefix(prefix), fact.period_start, fact.period_end,
                   classify_period(fact.period_start.isoformat(), fact.period_end.isoformat()),
                   fact.unit, fact.value, fact.accession_number, fact.form, fact.filed)

    def period_scope(self):
        return self.cik, self.start, self.end, self.kind, self.unit

    def valid(self):
        return (isinstance(self.cik, str) and bool(re.fullmatch(r"[0-9]{10}", self.cik))
                and self.source_namespace == "SEC Company Facts API" and self.taxonomy_namespace == "us-gaap"
                and self.concept in METRICS["revenue"].concepts + METRICS["net_income"].concepts
                and type(self.start) is date and type(self.end) is date and self.start <= self.end
                and self.kind == classify_period(self.start.isoformat(), self.end.isoformat())
                and self.kind in {"quarter", "half_year", "nine_months", "annual"}
                and self.unit == "USD" and isinstance(self.value, Decimal) and self.value.is_finite()
                and isinstance(self.accession, str) and bool(re.fullmatch(r"[0-9]{10}-[0-9]{2}-[0-9]{6}", self.accession))
                and self.form in {"10-Q", "10-Q/A", "10-K", "10-K/A"}
                and type(self.filed) is date and self.filed >= self.end)


@dataclass(frozen=True)
class SourceEvidence:
    identity: SourceIdentity
    document_identity: str  # Exact accession-relative filename, not a URL from a model.
    document_text: str      # Current independently supplied document content.
    statement_location: str
    statement_start: int
    statement_end: int
    context_id: str
    # None = unknown; () = verified absence of dimensions. First release permits
    # only undimensioned consolidated contexts, never segment/member observations.
    dimensions: tuple[tuple[str, str], ...] | None
    economic_scope: Literal["consolidated_revenue", "component_revenue", "consolidated_net_income"]

    def __post_init__(self):
        if self.dimensions is not None and (not isinstance(self.dimensions, tuple)
                                           or any(not isinstance(d, tuple) for d in self.dimensions)):
            raise TypeError("Dimensions must be immutable tuples or explicitly unknown.")

    def valid(self):
        return (self.identity.valid() and _nonempty(self.document_identity)
                and _nonempty(self.document_text) and _nonempty(self.statement_location)
                and type(self.statement_start) is int and type(self.statement_end) is int
                and 0 <= self.statement_start < self.statement_end <= len(self.document_text)
                and bool(self.document_text[self.statement_start:self.statement_end].strip())
                and _nonempty(self.context_id) and self.dimensions == ()
                and self.economic_scope in {"consolidated_revenue", "component_revenue", "consolidated_net_income"})

    def fingerprint(self):
        payload = asdict(self)
        # Bind the complete document as well as the exact statement/context/scope.
        payload["document_text"] = hashlib.sha256(self.document_text.encode("utf-8")).hexdigest()
        payload["identity"]["value"] = tuple(str(n) for n in self.identity.value.as_integer_ratio())
        return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class EvidenceBinding:
    identity: SourceIdentity
    fingerprint: str


@dataclass(frozen=True)
class ApprovalRef:
    permission: Permission
    approval_id: str
    version: int


@dataclass(frozen=True)
class SelectionAuthorization:
    ref: ApprovalRef
    selected: EvidenceBinding
    candidates: tuple[EvidenceBinding, ...]  # Complete reviewed raw-eligible manifest.
    reviewed_scope: str

    def __post_init__(self):
        if not isinstance(self.candidates, tuple):
            raise TypeError("Candidate manifests must be immutable tuples.")


@dataclass(frozen=True)
class DenominatorAuthorization:
    ref: ApprovalRef
    metric: Literal["net_margin"]
    revenue: EvidenceBinding
    numerator: EvidenceBinding
    candidates: tuple[EvidenceBinding, ...]
    reviewed_scope: str

    def __post_init__(self):
        if not isinstance(self.candidates, tuple):
            raise TypeError("Candidate manifests must be immutable tuples.")


@dataclass(frozen=True)
class AuthorizationWithdrawal:
    ref: ApprovalRef
    action: Literal["revoked", "superseded"]
    reason: str
    replacement: ApprovalRef | None = None

    def __post_init__(self):
        if self.action not in {"revoked", "superseded"} or not self.reason.strip():
            raise ValueError("A withdrawal needs an explicit action and reason.")
        if self.action == "superseded" and (self.replacement is None or self.replacement.permission != self.ref.permission):
            raise ValueError("Supersession needs an explicit replacement in the same permission path.")


@dataclass(frozen=True)
class AuthorizationDecision:
    accepted: bool
    reason: str
    ref: ApprovalRef | None = None
    selected: SourceIdentity | None = None


REVENUE_SELECTION_AUTHORIZATIONS: tuple[SelectionAuthorization, ...] = ()
DENOMINATOR_AUTHORIZATIONS: tuple[DenominatorAuthorization, ...] = ()
AUTHORIZATION_WITHDRAWALS: tuple[AuthorizationWithdrawal, ...] = ()


def _reject(reason):
    return AuthorizationDecision(False, reason)


def _approval(records, permission, registry):
    records = set(records)  # Only literally identical immutable records deduplicate.
    if not records:
        return None, "no_authorization"
    if any(r.ref.permission != permission or not _nonempty(r.ref.approval_id)
           or type(r.ref.version) is not int or r.ref.version < 1 or not _nonempty(r.reviewed_scope) for r in records):
        return None, "invalid_approval"
    ids = {r.ref.approval_id for r in records}
    lineage = {r for r in registry if r.ref.permission == permission and r.ref.approval_id in ids}
    # Versions remain immutable even when a successor moves to another scope.
    if any(len({r for r in lineage if r.ref == record.ref}) > 1 for record in records):
        return None, "conflicting_approval_version"
    refs = {r.ref for r in lineage}
    for event in AUTHORIZATION_WITHDRAWALS:
        for ref in (event.ref, event.replacement):
            if ref is not None and ref.permission == permission and ref.approval_id in ids:
                refs.add(ref)
    withdrawals = {event.ref for event in AUTHORIZATION_WITHDRAWALS}
    # Never fall back to an older active version when a newer one was withdrawn.
    for record in records:
        newer = [ref for ref in refs if ref.approval_id == record.ref.approval_id and ref.version > record.ref.version]
        if newer and record.ref not in withdrawals:
            return None, "explicit_supersession_required"
    active = [r for r in records if r.ref not in withdrawals]
    if not active:
        return None, "approval_withdrawn"
    if len(active) != 1:
        return None, "overlapping_approvals"
    record = active[0]
    if any(ref.approval_id == record.ref.approval_id and ref.version > record.ref.version for ref in refs):
        return None, "newer_approval_withdrawn"
    return record, None


def _validate_manifest(bindings, observations, evidence):
    raw = set(observations)  # Identity excludes DB IDs, fiscal labels and frame annotations.
    if not raw or any(not identity.valid() for identity in raw):
        return None, "invalid_source_identity"
    # Values within the exact source context must be unambiguous regardless of order.
    by_source, by_concept = {}, {}
    for identity in raw:
        by_source.setdefault(replace(identity, value=Decimal(0)), set()).add(identity.value)
        key = identity.period_scope(), identity.source_namespace, identity.taxonomy_namespace, identity.concept
        by_concept.setdefault(key, set()).add(identity.value)
    if any(len(values) > 1 for values in by_source.values()):
        return None, "same_source_conflicting_values"
    if any(len(values) > 1 for values in by_concept.values()):
        return None, "different_vintage_requires_restatement_review"
    reviewed = set(bindings)
    if len({b.identity for b in reviewed}) != len(reviewed):
        return None, "conflicting_evidence_bindings"
    if {b.identity for b in reviewed} != raw:
        return None, "candidate_manifest_changed"
    verified = {}
    for binding in reviewed:
        matches = set(e for e in evidence if e.identity == binding.identity)
        if len(matches) != 1:
            return None, "missing_or_ambiguous_context_evidence"
        item = next(iter(matches))
        if (not item.valid() or not isinstance(binding.fingerprint, str)
                or not re.fullmatch(r"[0-9a-f]{64}", binding.fingerprint)
                or item.fingerprint() != binding.fingerprint):
            return None, "missing_or_changed_context_evidence"
        if ((binding.identity.concept in METRICS["revenue"].concepts
             and item.economic_scope not in {"consolidated_revenue", "component_revenue"})
                or (binding.identity.concept == "NetIncomeLoss" and item.economic_scope != "consolidated_net_income")):
            return None, "economic_scope_mismatch"
        verified[binding.identity] = item
    # When evidence establishes two totals for the same population/period, their
    # values must agree. Equality alone never establishes that economic scope.
    totals = {}
    for identity, item in verified.items():
        if item.economic_scope != "component_revenue":
            totals.setdefault((identity.period_scope(), item.economic_scope), set()).add(identity.value)
    if any(len(values) > 1 for values in totals.values()):
        return None, "conflicting_reviewed_economic_totals"
    return verified, None


def authorize_selection(scope, observations, evidence):
    if not REVENUE_SELECTION_AUTHORIZATIONS or not observations:
        return _reject("no_authorization")
    records = [r for r in REVENUE_SELECTION_AUTHORIZATIONS if r.selected.identity.period_scope() == scope]
    record, error = _approval(records, "select:revenue", REVENUE_SELECTION_AUTHORIZATIONS)
    if error:
        return _reject(error)
    verified, error = _validate_manifest(record.candidates, observations, evidence)
    if error:
        return _reject(error)
    selected = record.selected.identity
    if (record.selected not in record.candidates or selected.concept not in METRICS["revenue"].concepts
            or any(i.period_scope() != scope or i.concept not in METRICS["revenue"].concepts for i in verified)
            or verified[selected].economic_scope != "consolidated_revenue"):
        return _reject("selection_scope_mismatch")
    if selected.filed != max(i.filed for i in verified):
        return _reject("older_observation_not_permitted")
    return AuthorizationDecision(True, "authorized", record.ref, selected)


def authorize_denominator(metric, revenue, numerator, observations, evidence):
    if metric != "net_margin" or not DENOMINATOR_AUTHORIZATIONS:
        return _reject("no_authorization")
    records = [r for r in DENOMINATOR_AUTHORIZATIONS if r.metric == metric
               and r.revenue.identity.period_scope() == revenue.period_scope()]
    record, error = _approval(records, "denominator:net_margin", DENOMINATOR_AUTHORIZATIONS)
    if error:
        return _reject(error)
    verified, error = _validate_manifest(record.candidates, observations, evidence)
    if error:
        return _reject(error)
    if record.revenue.identity != revenue or record.numerator.identity != numerator:
        return _reject("operand_identity_mismatch")
    if (record.revenue not in record.candidates or record.numerator not in record.candidates
            or revenue.concept not in METRICS["revenue"].concepts or numerator.concept != "NetIncomeLoss"
            or numerator.period_scope() != revenue.period_scope()
            or (revenue.accession, revenue.form, revenue.filed) != (numerator.accession, numerator.form, numerator.filed)
            or any(i.period_scope() != revenue.period_scope() for i in verified)
            or verified[revenue].economic_scope != "consolidated_revenue"
            or verified[numerator].economic_scope != "consolidated_net_income"):
        return _reject("denominator_scope_mismatch")
    if any(i.filed > revenue.filed for i in verified):
        return _reject("older_observation_not_permitted")
    return AuthorizationDecision(True, "authorized", record.ref, revenue)
