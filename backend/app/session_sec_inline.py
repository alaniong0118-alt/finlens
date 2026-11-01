"""Bounded original-SEC cash-flow inventory; parsing does not grant admission."""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import hashlib
import re
import time
from xml.parsers import expat

from app import sec_evidence_adapter as sec
from app.financial_metric_registry import METRICS
from app.sec_parser import classify_period

MAX_BYTES = 4 * 1024 * 1024
MAX_NODES = 100_000
MAX_DEPTH = 64
MAX_CONTEXTS = 4096
MAX_UNITS = 256
MAX_FACTS = 4096
MAX_ATTRIBUTES = 32
MAX_TOKEN_BYTES = 4096
MAX_NAMESPACES = 256
PROFILE = "sec-inline-cash-flow-v1"
_CONCEPTS = (METRICS["operating_cash_flow"].concepts + METRICS["capital_expenditures"].concepts)


class InventoryRejected(ValueError):
    pass


def _require(condition, reason):
    if not condition:
        raise InventoryRejected(reason)


@dataclass(frozen=True, slots=True)
class DocumentIdentity:
    """Structural expected metadata, not a source-authority decision."""
    cik: str
    accession: str
    form: str
    filed: date
    period_end: date
    gaap_namespace: str
    dei_namespace: str


@dataclass(frozen=True, slots=True)
class CashFact:
    concept: str
    fact_id: str
    context_id: str
    start: date
    end: date
    kind: str
    value: Decimal
    dimensions: tuple


@dataclass(frozen=True, slots=True)
class CashInventory:
    sha256: str
    profile: str
    facts: tuple[CashFact, ...]


def _preflight(data, checkpoint):
    _require(type(data) is bytes and 0 < len(data) <= MAX_BYTES, "artifact_size")
    _require(b"\x00" not in data, "unsupported_encoding")
    try:
        data.decode("utf-8", errors="strict")
    except UnicodeError:
        raise InventoryRejected("unsupported_encoding") from None
    parser = expat.ParserCreate(namespace_separator="}")
    parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    counts = {"nodes": 0, "depth": 0, "contexts": 0, "units": 0, "facts": 0, "namespaces": 0}

    def reject(*_args):
        raise InventoryRejected("unsafe_xml")

    def declaration(_version, encoding, _standalone):
        _require(encoding is None or encoding.lower() in {"utf-8", "ascii", "us-ascii"}, "unsupported_encoding")

    def namespace(prefix, uri):
        checkpoint()
        counts["namespaces"] += 1
        _require(counts["namespaces"] <= MAX_NAMESPACES and len((prefix or "").encode()) <= MAX_TOKEN_BYTES
                 and len((uri or "").encode()) <= MAX_TOKEN_BYTES, "namespace_limit")

    def start(name, attributes):
        checkpoint()
        counts["nodes"] += 1
        counts["depth"] += 1
        _require(counts["nodes"] <= MAX_NODES and counts["depth"] <= MAX_DEPTH, "xml_limit")
        _require(len(name.encode()) <= MAX_TOKEN_BYTES and len(attributes) <= MAX_ATTRIBUTES
                 and all(len(k.encode()) <= MAX_TOKEN_BYTES and len(v.encode()) <= MAX_TOKEN_BYTES
                         for k, v in attributes.items()), "attribute_limit")
        if name == sec.XBRLI + "}context":
            counts["contexts"] += 1
        elif name == sec.XBRLI + "}unit":
            counts["units"] += 1
        elif name.startswith(sec.IX + "}") and name.split("}", 1)[1] in {"nonFraction", "nonNumeric", "fraction"}:
            counts["facts"] += 1
        _require(counts["contexts"] <= MAX_CONTEXTS and counts["units"] <= MAX_UNITS
                 and counts["facts"] <= MAX_FACTS, "inventory_limit")

    def end(_name):
        counts["depth"] -= 1

    parser.StartElementHandler, parser.EndElementHandler = start, end
    parser.StartNamespaceDeclHandler, parser.XmlDeclHandler = namespace, declaration
    parser.StartDoctypeDeclHandler = parser.EntityDeclHandler = parser.ExternalEntityRefHandler = reject
    try:
        for offset in range(0, len(data), 65536):
            checkpoint()
            parser.Parse(data[offset:offset + 65536], False)
        parser.Parse(b"", True)
    except expat.ExpatError:
        raise InventoryRejected("invalid_xml") from None


def inventory_original(data, identity, *, deadline_seconds=5, _checkpoint=None):
    """Parse the complete fixed profile. Returned values are still unadmitted."""
    _require(type(identity) is DocumentIdentity, "document_identity")
    _require(type(identity.cik) is str and re.fullmatch(r"[0-9]{10}", identity.cik)
             and type(identity.accession) is str and re.fullmatch(r"[0-9]{10}-[0-9]{2}-[0-9]{6}", identity.accession)
             and identity.accession.startswith(identity.cik + "-")
             and identity.form in {"10-K", "10-K/A", "10-Q", "10-Q/A"}
             and type(identity.filed) is date and type(identity.period_end) is date
             and identity.filed >= identity.period_end
             and re.fullmatch(r"http://fasb.org/us-gaap/[0-9]{4}", identity.gaap_namespace)
             and re.fullmatch(r"http://xbrl.sec.gov/dei/[0-9]{4}", identity.dei_namespace), "document_identity")
    _require(type(deadline_seconds) in (int, float) and 0 < deadline_seconds <= 5, "deadline")
    deadline = time.monotonic() + deadline_seconds
    callback_failure = None

    def checkpoint():
        nonlocal callback_failure
        _require(time.monotonic() < deadline, "deadline")
        if _checkpoint is not None:
            try:
                _checkpoint()
            except Exception as error:
                callback_failure = error
                raise

    _preflight(data, checkpoint)
    try:
        root, scopes = sec._xml_tree(data)
        _require(root.tag == f"{{{sec.XHTML}}}html", "not_sec_inline_document")
        sec._validate_inline_structure(root, scopes, identity.dei_namespace, cash_flow_profile=True)
        ids = {}
        for element in root.iter():
            checkpoint()
            identifier = element.get("id")
            if identifier is not None:
                _require(bool(re.fullmatch(r"[A-Za-z_][\w.-]*", identifier)) and identifier not in ids, "ambiguous_xml_id")
                ids[identifier] = element
        contexts = {e.get("id"): sec._context(e, scopes) for e in root.iter(f"{{{sec.XBRLI}}}context")}
        units = {e.get("id"): e for e in root.iter(f"{{{sec.XBRLI}}}unit")}
        _require(None not in contexts and None not in units, "missing_context_or_unit_id")
        dei, facts, conflicts = {}, [], {}
        for element in root.iter():
            checkpoint()
            if element.tag not in {f"{{{sec.IX}}}nonFraction", f"{{{sec.IX}}}nonNumeric", f"{{{sec.IX}}}fraction"}:
                continue
            namespace, concept = sec._qname(element.get("name"), scopes[element])
            if namespace == identity.dei_namespace and concept in {"EntityCentralIndexKey", "DocumentType", "AmendmentFlag", "DocumentPeriodEndDate"}:
                _require(set(element.attrib) <= {"id", "name", "contextRef", "format"}
                         and element.tag == f"{{{sec.IX}}}nonNumeric" and len(element) == 0
                         and element.get("contextRef") in contexts and concept not in dei, "filing_identity")
                cik, _start, end, dims = contexts[element.get("contextRef")]
                _require(cik == identity.cik and end == identity.period_end and not dims, "filing_identity")
                value = (element.text or "").strip()
                if concept == "AmendmentFlag" and element.get("format"):
                    _require(sec._qname(element.get("format"), scopes[element]) == (sec.IXT, "fixed-false"), "filing_identity")
                    value = "false"
                elif concept == "DocumentPeriodEndDate" and element.get("format"):
                    _require(sec._qname(element.get("format"), scopes[element]) ==
                             (sec.IXT, "date-monthname-day-year-en"), "unsupported_identity_transform")
                    match = re.fullmatch(r"(January|February|March|April|May|June|July|August|September|October|November|December)[ \u00a0]+([0-9]{1,2}),[ \u00a0]+([0-9]{4})", value)
                    _require(match is not None, "unsupported_identity_transform")
                    months = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")
                    try:
                        value = str(date(int(match[3]), months.index(match[1]) + 1, int(match[2])))
                    except ValueError:
                        raise InventoryRejected("unsupported_identity_transform") from None
                elif element.get("format"):
                    raise InventoryRejected("unsupported_identity_transform")
                dei[concept] = value
            if concept not in _CONCEPTS:
                continue
            _require(namespace == identity.gaap_namespace, "concept_namespace_mismatch")
            fact_id, context_id = element.get("id"), element.get("contextRef")
            _require(fact_id is not None and context_id in contexts, "missing_observation_context")
            cik, start, end, dims = contexts[context_id]
            _require(cik == identity.cik and start is not None, "observation_context_mismatch")
            _require(end <= identity.period_end and end <= identity.filed, "observation_after_filing_period")
            unit = units.get(element.get("unitRef"))
            _require(unit is not None and len(unit) == 1 and len(unit[0]) == 0
                     and unit[0].tag == f"{{{sec.XBRLI}}}measure"
                     and sec._qname(unit[0].text, scopes[unit[0]]) == (sec.ISO, "USD"), "unit_mismatch")
            kind = classify_period(str(start), str(end))
            _require(kind in {"quarter", "half_year", "nine_months", "annual"}, "unsupported_period")
            value = sec._numeric(element, scopes[element])
            key = concept, start, end, tuple(sorted(dims))
            _require(key not in conflicts or conflicts[key] == value, "conflicting_observations")
            conflicts[key] = value
            facts.append(CashFact(concept, fact_id, context_id, start, end, kind, value, dims))
        _require(dei == {"EntityCentralIndexKey": identity.cik, "DocumentType": identity.form,
                         "AmendmentFlag": "true" if identity.form.endswith("/A") else "false",
                         "DocumentPeriodEndDate": str(identity.period_end)}, "filing_identity_mismatch")
        checkpoint()
        return CashInventory(hashlib.sha256(data).hexdigest(), PROFILE, tuple(facts))
    except InventoryRejected:
        raise
    except (sec.EvidenceRejected, ValueError, TypeError, AttributeError, UnicodeError, RecursionError) as error:
        if error is callback_failure:
            raise
        raise InventoryRejected("invalid_document") from None
