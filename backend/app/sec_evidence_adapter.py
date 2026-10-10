"""Offline original-filing evidence producer. No permissions are activated here.

Only reviewed server-side policies and an operator-configured store are trusted.
HTTP callers cannot provide paths, proofs or a production flag. Capture receipts
are local provenance anchors, not SEC signatures. No cleaned chunks are proof.
"""
from dataclasses import asdict, dataclass
from datetime import date, datetime
from decimal import Decimal, localcontext
import hashlib
import io
import json
import os
from pathlib import Path
import re
from xml.etree import ElementTree as ET
from xml.parsers import expat

from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError

from app import revenue_scope_authorizations as auth
from app.financial_metric_registry import METRICS
from app.models import CompanyRefreshState, FilingPublication
from app.sec_parser import classify_period

IX = "http://www.xbrl.org/2013/inlineXBRL"
XBRLI = "http://www.xbrl.org/2003/instance"
XBRLDI = "http://xbrl.org/2006/xbrldi"
XHTML = "http://www.w3.org/1999/xhtml"
ISO = "http://www.xbrl.org/2003/iso4217"
IXT = "http://www.xbrl.org/inlineXBRL/transformation/2020-02-12"
PARSER_VERSION = "sec-inline-v2"
MAX_ARTIFACT_BYTES = 20_000_000


class EvidenceRejected(ValueError):
    """A verification failure supplies no financial evidence."""


@dataclass(frozen=True)
class ArtifactPin:
    cik: str
    accession: str
    filename: str
    form: str
    filed: date
    period_end: date
    sha256: str
    byte_length: int
    receipt_filename: str
    receipt_sha256: str
    gaap_namespace: str
    dei_namespace: str


@dataclass(frozen=True)
class ObservationReview:
    identity: auth.SourceIdentity
    filename: str
    fact_id: str
    context_id: str
    table_ordinal: int
    statement_sha256: str
    economic_scope: str
    review_note: str


@dataclass(frozen=True)
class EvidencePolicy:
    ref: auth.ApprovalRef
    approval_sha256: str
    snapshot_sha256: str
    artifacts: tuple[ArtifactPin, ...]
    observations: tuple[ObservationReview, ...]
    parser_version: str = PARSER_VERSION

    def __post_init__(self):
        if not isinstance(self.artifacts, tuple) or not isinstance(self.observations, tuple):
            raise TypeError("Reviewed policies must be immutable tuples.")


# Independent review must pin policy AND financial permission in separate records.
# No real or synthetic production records, paths or amounts are shipped.
PRODUCTION_EVIDENCE_POLICIES: tuple[EvidencePolicy, ...] = ()


def _require(condition, reason):
    if not condition:
        raise EvidenceRejected(reason)


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _digest(value):
    return _sha(json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode())


def approval_digest(record):
    """Pin all permission content, including reviewed scope and evidence bindings."""
    return _digest(asdict(record))


def _policy_digest(policy):
    # Exclude only the approval digest to avoid a circular fingerprint. Every
    # other reviewed pin (including receipts, versions and inventory) is bound
    # into SourceEvidence and therefore the immutable financial approval.
    payload = asdict(policy)
    del payload["approval_sha256"]
    return _digest(payload)


def _statement_location(policy, review):
    return (f"table[{review.table_ordinal}]/{review.fact_id}: {review.review_note}; "
            f"verified-policy-sha256={_policy_digest(policy)}")


def snapshot_digest(state, publications):
    """Complete issuer publication inventory and all three published versions."""
    _require(state is not None, "missing_data_version")
    inventory = sorted((p.company_cik, p.accession_number, p.form, str(p.filed), p.filename,
                        p.chunk_count, p.content_digest, p.configuration, p.data_version)
                       for p in publications)
    return _digest((state.company_cik, state.data_version, state.facts_version,
                    state.evidence_version, inventory))


def _qname(value, namespaces):
    _require(isinstance(value, str) and bool(re.fullmatch(r"[A-Za-z_][\w.-]*:[A-Za-z_][\w.-]*", value)),
             "unresolved_qname")
    prefix, local = value.split(":")
    _require(prefix in namespaces, "unresolved_namespace")
    return namespaces[prefix], local


def _unique_json(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "ambiguous_receipt")
        result[key] = value
    return result


def _read(path, limit):
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    _require(len(data) <= limit, "artifact_size_limit")
    return data


def _store_path(root, cik, accession, filename):
    _require(bool(re.fullmatch(r"[0-9]{10}", cik))
             and bool(re.fullmatch(r"[0-9]{10}-[0-9]{2}-[0-9]{6}", accession))
             and bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", filename)), "invalid_store_identity")
    candidate = root / cik / accession / filename
    # resolve() also detects Windows junction/reparse redirection. Check every
    # component so even a symlink resolving back into the store is rejected.
    for node in (root, root / cik, root / cik / accession, candidate):
        _require(not node.is_symlink() and node.absolute() == node.resolve(strict=True), "redirected_store_path")
    _require(candidate.is_file() and candidate.resolve().is_relative_to(root), "invalid_store_path")
    return candidate


def _validate_receipt(pin, receipt_bytes, artifact_path):
    _require(_sha(receipt_bytes) == pin.receipt_sha256, "receipt_changed")
    receipt = json.loads(receipt_bytes, object_pairs_hook=_unique_json)
    _require(isinstance(receipt, dict) and isinstance(receipt.get("response_metadata"), dict), "invalid_receipt")
    url = (f"https://www.sec.gov/Archives/edgar/data/{int(pin.cik)}/"
           f"{pin.accession.replace('-', '')}/{pin.filename}")
    _require(receipt.get("source_url") == url and receipt.get("response_url") == url
             and receipt.get("cik") == pin.cik and receipt.get("accession") == pin.accession
             and receipt.get("filename") == pin.filename and type(receipt.get("http_status")) is int
             and receipt["http_status"] == 200 and receipt.get("sha256") == pin.sha256
             and receipt.get("byte_length") == pin.byte_length
             and receipt.get("redirects_allowed") is False, "receipt_identity_mismatch")
    _require(Path(receipt["artifact_path"]).absolute() == artifact_path, "receipt_path_mismatch")
    start = datetime.fromisoformat(receipt["retrieval_started_at_utc"])
    end = datetime.fromisoformat(receipt["retrieval_completed_at_utc"])
    _require(start.utcoffset() is not None and end.utcoffset() is not None and end >= start,
             "invalid_retrieval_time")
    _require(receipt.get("response_metadata", {}).get("content-type", "").split(";")[0].lower()
             in {"text/html", "application/xhtml+xml"}, "invalid_content_type")


def _context(element, scopes):
    identifier = element.findall(f"./{{{XBRLI}}}entity/{{{XBRLI}}}identifier")
    _require(len(identifier) == 1 and len(identifier[0]) == 0 and identifier[0].get("scheme") == "http://www.sec.gov/CIK"
             and bool(re.fullmatch(r"[0-9]{10}", identifier[0].text or "")), "invalid_context_entity")
    _require([e.tag for e in element] in ([f"{{{XBRLI}}}entity", f"{{{XBRLI}}}period"],
                                        [f"{{{XBRLI}}}entity", f"{{{XBRLI}}}period", f"{{{XBRLI}}}scenario"]),
             "unsupported_context")
    entity = element.find(f"{{{XBRLI}}}entity")
    _require([e.tag for e in entity] in ([f"{{{XBRLI}}}identifier"],
                                       [f"{{{XBRLI}}}identifier", f"{{{XBRLI}}}segment"]), "unsupported_entity")
    dimensions = []
    for container in (entity.find(f"{{{XBRLI}}}segment"), element.find(f"{{{XBRLI}}}scenario")):
        if container is None:
            continue
        _require(len(container) > 0, "unknown_dimensions")
        for member in container:
            axis = _qname(member.get("dimension"), scopes[member])
            if member.tag == f"{{{XBRLDI}}}explicitMember":
                _require(len(member) == 0, "ambiguous_dimension")
                dimensions.append((str(axis), str(_qname(member.text, scopes[member]))))
            elif member.tag == f"{{{XBRLDI}}}typedMember":
                _require(len(member) == 1, "ambiguous_dimension")
                dimensions.append((str(axis), ET.tostring(member[0], encoding="unicode")))
            else:
                raise EvidenceRejected("unsupported_dimension")
    _require(len({axis for axis, _ in dimensions}) == len(dimensions), "ambiguous_dimensions")
    period = element.find(f"{{{XBRLI}}}period")
    _require(all(len(e) == 0 for e in period), "ambiguous_context_period")
    tags = [e.tag for e in period]
    if tags == [f"{{{XBRLI}}}startDate", f"{{{XBRLI}}}endDate"]:
        start, end = (date.fromisoformat(e.text) for e in period)
        _require(start <= end, "invalid_context_period")
    elif tags == [f"{{{XBRLI}}}instant"]:
        start, end = None, date.fromisoformat(period[0].text)
    else:
        raise EvidenceRejected("unsupported_context_period")
    return identifier[0].text, start, end, tuple(dimensions)


def _numeric(element, namespaces):
    _require(element.tag == f"{{{IX}}}nonFraction" and len(element) == 0
             and set(element.attrib) <= {"id", "name", "contextRef", "unitRef", "decimals", "scale", "sign", "format"},
             "unsupported_numeric_fact")
    format_name = element.get("format")
    if format_name:
        _require(_qname(format_name, namespaces) == (IXT, "num-dot-decimal"), "unsupported_numeric_transform")
    value = (element.text or "").strip()
    pattern = r"(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)(?:\.[0-9]+)?" if format_name else r"[0-9]+(?:\.[0-9]+)?"
    _require(len(value) <= 80 and bool(re.fullmatch(pattern, value)), "invalid_numeric_text")
    _require(element.get("sign") in {None, "-"}, "unsupported_sign")
    scale = element.get("scale", "0")
    _require(bool(re.fullmatch(r"-?[0-9]{1,2}", scale)) and -18 <= int(scale) <= 18, "unsupported_scale")
    decimals = element.get("decimals")
    _require(decimals == "INF" or bool(re.fullmatch(r"-?[0-9]{1,2}", decimals or "")), "unresolved_decimals")
    with localcontext() as ctx:
        ctx.prec = 120
        number = Decimal(value.replace(",", "")).scaleb(int(scale))
        return -number if element.get("sign") == "-" else number


@dataclass(frozen=True)
class ParsedObservation:
    identity: auth.SourceIdentity
    fact_id: str
    context_id: str
    dimensions: tuple
    table_ordinal: int | None


@dataclass(frozen=True)
class ParsedArtifact:
    document_text: str
    observations: tuple[ParsedObservation, ...]
    statement_ranges: tuple[tuple[int, int], ...]
    inline_fact_count: int
    context_count: int
    unit_count: int


def _table_ranges(data):
    # Expat supplies original-byte offsets, avoiding reserialization or offsets
    # into cleaned chunks. Entities/DTDs are forbidden before either parser runs.
    parser = expat.ParserCreate(namespace_separator="}")
    ranges, stack = [], []

    def start(name, attrs):
        if name == XHTML + "}table":
            stack.append(len(ranges))
            ranges.append((parser.CurrentByteIndex, None))

    def end(name):
        if name == XHTML + "}table":
            index = stack.pop()
            offset = parser.CurrentByteIndex
            _require(data[offset:offset+2] == b"</", "unsupported_statement_markup")
            ranges[index] = (ranges[index][0], data.index(b">", offset) + 1)

    parser.StartElementHandler, parser.EndElementHandler = start, end
    parser.ExternalEntityRefHandler = lambda *args: 0
    parser.Parse(data, True)
    return tuple((len(data[:a].decode("utf-8")), len(data[:b].decode("utf-8"))) for a, b in ranges)


def _xml_tree(data):
    # QName-valued attributes/text use the namespace scope at their own element,
    # never a global dictionary assembled from later descendant declarations.
    scopes, seen, pending, stack, root = {}, {}, {}, [], None
    for event, item in ET.iterparse(io.BytesIO(data), events=("start-ns", "start", "end")):
        if event == "start-ns":
            prefix, uri = item
            _require(prefix not in seen or seen[prefix] == uri, "namespace_rebinding")
            seen[prefix], pending[prefix] = uri, uri
        elif event == "start":
            scope = dict(stack[-1]) if stack else {}
            scope.update(pending)
            pending.clear()
            scopes[item] = scope
            stack.append(scope)
            if root is None:
                root = item
        else:
            stack.pop()
    return root, scopes


def _validate_inline_structure(root, scopes, dei_namespace):
    """Reject unsupported instance semantics before any candidate can disappear.

    Known narrative text-block/continuation containers do not change a nested
    monetary fact's explicit context. Retain those raw facts rather than dropping
    conflicts. Such containers may never supply or wrap filing-identity facts.
    """
    supported = {"header", "hidden", "references", "resources", "nonFraction", "nonNumeric", "continuation", "exclude"}
    inline_names = supported | {"tuple", "fraction", "footnote", "relationship"}
    for scope in scopes.values():
        for namespace in scope.values():
            if "inlineXBRL" in namespace and "/transformation/" not in namespace:
                _require(namespace == IX, "unsupported_inline_namespace")
    parents = {child: parent for parent in root.iter() for child in parent}
    financial_names = METRICS["revenue"].concepts + METRICS["net_income"].concepts
    identity_names = {"EntityCentralIndexKey", "DocumentType", "AmendmentFlag", "DocumentPeriodEndDate"}
    for element in root.iter():
        namespace, local = element.tag[1:].split("}", 1) if element.tag.startswith("{") else ("", element.tag)
        if namespace != IX:
            _require(local not in inline_names or (namespace == XHTML and local == "header"), "unsupported_inline_namespace")
            if namespace != XBRLI or local not in {"context", "unit"}:
                continue
        else:
            _require(local in supported, "unsupported_inline_construct")
            _require("target" not in element.attrib, "unsupported_inline_target")
        ancestors, ancestor_elements = [], []
        parent = parents.get(element)
        while parent is not None:
            if parent.tag.startswith("{" + IX + "}"):
                ancestors.append(parent.tag.split("}", 1)[1])
                ancestor_elements.append(parent)
            parent = parents.get(parent)
        if namespace == XBRLI:
            _require(ancestors == ["resources", "header"], "unsupported_inline_ancestry")
            continue
        if local == "header":
            _require(not ancestors, "unsupported_inline_ancestry")
        elif local in {"hidden", "references", "resources"}:
            _require(ancestors == ["header"], "unsupported_inline_ancestry")
            if local == "resources":
                _require(set(element.attrib) <= {"id"}, "unsupported_resource_attributes")
        elif local in {"nonFraction", "nonNumeric"}:
            concept_namespace, concept = _qname(element.get("name"), scopes[element])
            identity = concept_namespace == dei_namespace and concept in identity_names
            if concept in financial_names or identity:
                default = ancestors in ([], ["hidden", "header"])
                # TextBlock naming limits structural support, never authorizes
                # economic scope. Each nested numeric fact still needs its own
                # context/unit/value and participates in the complete manifest.
                narrative = (not identity and bool(ancestors) and "nonNumeric" in ancestors
                             and set(ancestors) <= {"nonNumeric", "continuation"}
                             and all(set(a.attrib) <= ({"id", "continuedAt"} if a.tag == f"{{{IX}}}continuation"
                                     else {"id", "name", "contextRef", "escape", "continuedAt", "{http://www.w3.org/XML/1998/namespace}lang"})
                                     and a.get("escape") in {None, "true", "false", "1", "0"}
                                     for a in ancestor_elements)
                             and all(_qname(a.get("name"), scopes[a])[1].endswith("TextBlock")
                                     for a in ancestor_elements if a.tag == f"{{{IX}}}nonNumeric"))
                _require(default or narrative, "unsupported_inline_ancestry")


def _parse_artifact(pin, data):
    """Private verifier; expected identities never supply the parsed amounts."""
    _require(type(pin.byte_length) is int and 0 < pin.byte_length <= MAX_ARTIFACT_BYTES
             and len(data) == pin.byte_length and _sha(data) == pin.sha256, "artifact_changed")
    _require(b"<!DOCTYPE" not in data.upper() and b"<!ENTITY" not in data.upper(), "unsafe_xml")
    _require(b"\x00" not in data, "unsupported_xml_encoding")
    encoding = re.search(br"<\?xml[^>]*encoding\s*=\s*['\"]([^'\"]+)['\"]", data[:256])
    _require(encoding is None or encoding[1].lower() in {b"utf-8", b"ascii", b"us-ascii"}, "unsupported_xml_encoding")
    document = data.decode("utf-8", errors="strict")
    _require(bool(re.fullmatch(r"http://fasb.org/us-gaap/[0-9]{4}", pin.gaap_namespace))
             and bool(re.fullmatch(r"http://xbrl.sec.gov/dei/[0-9]{4}", pin.dei_namespace)), "untrusted_taxonomy")
    root, scopes = _xml_tree(data)
    _require(root.tag == f"{{{XHTML}}}html", "not_sec_inline_document")
    _validate_inline_structure(root, scopes, pin.dei_namespace)
    ids = {}
    for element in root.iter():
        if element.get("id") is not None:
            _require(bool(re.fullmatch(r"[A-Za-z_][\w.-]*", element.get("id")))
                     and element.get("id") not in ids, "ambiguous_xml_id")
            ids[element.get("id")] = element
    contexts = {e.get("id"): _context(e, scopes) for e in root.iter(f"{{{XBRLI}}}context")}
    _require(None not in contexts, "missing_context_id")
    units = {e.get("id"): e for e in root.iter(f"{{{XBRLI}}}unit")}
    _require(None not in units, "missing_unit_id")
    tables = list(root.iter(f"{{{XHTML}}}table"))
    ranges = _table_ranges(data)
    _require(len(tables) == len(ranges), "unresolved_statement")
    table_by_element = {e: i for i, table in enumerate(tables) for e in table.iter()}
    dei, observations, inline_count = {}, [], 0
    names = METRICS["revenue"].concepts + METRICS["net_income"].concepts
    for element in root.iter():
        if element.tag not in {f"{{{IX}}}nonFraction", f"{{{IX}}}nonNumeric", f"{{{IX}}}fraction"}:
            continue
        inline_count += 1
        namespaces = scopes[element]
        namespace, concept = _qname(element.get("name"), namespaces)
        if namespace == pin.dei_namespace and concept in {"EntityCentralIndexKey", "DocumentType", "AmendmentFlag", "DocumentPeriodEndDate"}:
            _require(set(element.attrib) <= {"id", "name", "contextRef", "format"}, "unsupported_identity_attributes")
            _require(element.tag == f"{{{IX}}}nonNumeric" and len(element) == 0
                     and element.get("continuedAt") is None and element.get("contextRef") in contexts,
                     "unresolved_filing_identity")
            context = contexts[element.get("contextRef")]
            _require(context[0] == pin.cik and context[3] == () and context[2] == pin.period_end,
                     "filing_context_mismatch")
            value = (element.text or "").strip()
            if concept == "DocumentPeriodEndDate":
                if element.get("format"):
                    _require(_qname(element.get("format"), namespaces) == (IXT, "date-monthname-day-year-en"),
                             "unsupported_date_transform")
                    months = {name: n for n, name in enumerate(("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"), 1)}
                    match = re.fullmatch(r"([A-Za-z]+)\s+([0-9]{1,2}),\s*([0-9]{4})", value)
                    _require(match is not None and match[1] in months, "invalid_document_date")
                    value = str(date(int(match[3]), months[match[1]], int(match[2])))
                else:
                    value = str(date.fromisoformat(value))
            else:
                _require(element.get("format") is None, "unsupported_identity_transform")
            _require(concept not in dei, "ambiguous_filing_identity")
            dei[concept] = value
        if concept not in names:
            continue
        _require(namespace == pin.gaap_namespace, "concept_namespace_mismatch")
        _require(element.get("contextRef") in contexts and element.get("id") is not None,
                 "missing_observation_context")
        cik, start, end, dimensions = contexts[element.get("contextRef")]
        _require(cik == pin.cik and start is not None, "observation_context_mismatch")
        unit = units.get(element.get("unitRef"))
        _require(unit is not None and len(unit) == 1 and len(unit[0]) == 0 and unit[0].tag == f"{{{XBRLI}}}measure"
                 and _qname(unit[0].text, scopes[unit[0]]) == (ISO, "USD"), "unit_mismatch")
        identity = auth.SourceIdentity(cik, "SEC Company Facts API", "us-gaap", concept, start, end,
                                       classify_period(str(start), str(end)), "USD", _numeric(element, namespaces),
                                       pin.accession, pin.form, pin.filed)
        _require(identity.valid(), "invalid_parsed_identity")
        observations.append(ParsedObservation(identity, element.get("id"), element.get("contextRef"),
                                              dimensions, table_by_element.get(element)))
    _require(dei == {"EntityCentralIndexKey": pin.cik, "DocumentType": pin.form,
                     "AmendmentFlag": "true" if pin.form.endswith("/A") else "false",
                     "DocumentPeriodEndDate": str(pin.period_end)}, "filing_identity_mismatch")
    _require(observations and pin.filed >= pin.period_end, "missing_financial_observations")
    return ParsedArtifact(document, tuple(observations), ranges, inline_count, len(contexts), len(units))


def _verify_policy(policy, record, raw, root, snapshot, publications):
    _require(policy.parser_version == PARSER_VERSION and policy.ref == record.ref
             and policy.approval_sha256 == approval_digest(record), "approval_policy_changed")
    _require(policy.snapshot_sha256 == snapshot, "data_snapshot_changed")
    _require(raw and set(raw) == {b.identity for b in record.candidates}, "candidate_manifest_changed")
    _require(len(set(policy.artifacts)) == len(policy.artifacts) and policy.artifacts, "ambiguous_artifact_manifest")
    expected_files = {(p.accession, p.filename) for p in policy.artifacts}
    _require(len(expected_files) == len(policy.artifacts) and {p.cik for p in policy.artifacts} == {raw[0].cik},
             "artifact_manifest_scope")
    issuer_dir = root / raw[0].cik
    _require(not issuer_dir.is_symlink() and issuer_dir.absolute() == issuer_dir.resolve(strict=True), "redirected_store_path")
    actual_files = set()
    directories = list(issuer_dir.iterdir())
    _require(len(directories) <= 4096, "artifact_inventory_limit")
    for directory in directories:
        _require(not directory.is_symlink() and directory.absolute() == directory.resolve(strict=True), "redirected_store_path")
        _require(directory.is_dir() and bool(re.fullmatch(r"[0-9]{10}-[0-9]{2}-[0-9]{6}", directory.name)), "unreviewed_store_entry")
        files = list(directory.iterdir())
        _require(len(files) <= 4096, "artifact_inventory_limit")
        for file in files:
            _require(not file.is_symlink() and file.absolute() == file.resolve(strict=True), "redirected_store_path")
            if file.suffix.lower() in {".htm", ".html"}:
                actual_files.add((directory.name, file.name))
    _require(actual_files == expected_files, "artifact_inventory_changed")
    documents, parsed_raw = {}, set()
    names = METRICS["revenue"].concepts
    if record.ref.permission == "denominator:net_margin":
        names += METRICS["net_income"].concepts
    kind, end = raw[0].kind, raw[0].end
    for pin in policy.artifacts:
        matches = [p for p in publications if (p.company_cik, p.accession_number, p.filename, p.form, p.filed)
                   == (pin.cik, pin.accession, pin.filename, pin.form, pin.filed)]
        _require(len(matches) == 1, "publication_identity_mismatch")
        artifact_path = _store_path(root, pin.cik, pin.accession, pin.filename)
        receipt_path = _store_path(root, pin.cik, pin.accession, pin.receipt_filename)
        _validate_receipt(pin, _read(receipt_path, 65536), artifact_path)
        parsed = _parse_artifact(pin, _read(artifact_path, MAX_ARTIFACT_BYTES))
        documents[(pin.accession, pin.filename)] = parsed
        parsed_raw.update(o.identity for o in parsed.observations if o.dimensions == ()
                          and o.identity.concept in names and o.identity.kind == kind and o.identity.end == end)
    _require(parsed_raw == set(raw), "original_candidate_manifest_changed")
    _require(len({r.identity for r in policy.observations}) == len(policy.observations)
             and {r.identity for r in policy.observations} == set(raw), "review_manifest_changed")
    evidence = []
    for review in policy.observations:
        _require(review.review_note.strip() and review.economic_scope in {"consolidated_revenue", "consolidated_net_income"},
                 "unreviewed_economic_scope")
        _require(type(review.table_ordinal) is int and review.table_ordinal >= 0, "invalid_statement_locator")
        parsed = documents.get((review.identity.accession, review.filename))
        _require(parsed is not None, "missing_reviewed_document")
        matches = [o for o in parsed.observations if o.fact_id == review.fact_id]
        _require(len(matches) == 1, "missing_or_ambiguous_fact_locator")
        observation = matches[0]
        _require(observation.identity == review.identity and observation.context_id == review.context_id
                 and observation.dimensions == () and observation.table_ordinal == review.table_ordinal,
                 "reviewed_context_mismatch")
        a, b = parsed.statement_ranges[review.table_ordinal]
        _require(_sha(parsed.document_text[a:b].encode()) == review.statement_sha256, "statement_changed")
        evidence.append(auth.SourceEvidence(observation.identity, review.filename, parsed.document_text,
                        _statement_location(policy, review), a, b,
                        observation.context_id, (), review.economic_scope))
    verified, error = auth._validate_manifest(record.candidates, raw, evidence)
    _require(verified is not None, error or "invalid_evidence")
    return tuple(evidence)


def load_production_evidence(session, cik, facts):
    """Internal dataset-loader boundary; no paths/proofs/mode supplied by requests.

    All applicable policies must verify or no evidence is returned. The evaluator
    still owns permission, withdrawal and financial compatibility decisions.
    """
    records = (*auth.REVENUE_SELECTION_AUTHORIZATIONS, *auth.DENOMINATOR_AUTHORIZATIONS)
    if not records:
        return ()  # Before configuration, artifact access or evidence queries.
    records = tuple(r for r in records if (r.selected if hasattr(r, "selected") else r.revenue).identity.cik == cik)
    if not records or not PRODUCTION_EVIDENCE_POLICIES:
        return ()
    try:
        from app.financial_metrics_service import usable, period_kind
        configured_root = os.environ.get("FINLENS_SEC_ORIGINAL_STORE", "")
        _require(configured_root and Path(configured_root).is_absolute(), "unconfigured_original_store")
        root = Path(configured_root)
        _require(not root.is_symlink() and root.absolute() == root.resolve(strict=True), "redirected_store_path")
        # Fail closed even if a new internal caller bypasses read_session.
        _require(session.get_bind().dialect.name == "postgresql", "unsupported_snapshot")
        _require(session.scalar(text("SHOW transaction_isolation")) == "repeatable read"
                 and session.scalar(text("SHOW transaction_read_only")) == "on", "unsafe_database_snapshot")
        state = session.get(CompanyRefreshState, cik)
        publications = list(session.scalars(select(FilingPublication).where(FilingPublication.company_cik == cik)))
        snapshot = snapshot_digest(state, publications)
        proofs = []
        for record in records:
            registry = auth.REVENUE_SELECTION_AUTHORIZATIONS if record.ref.permission == "select:revenue" else auth.DENOMINATOR_AUTHORIZATIONS
            anchor = record.selected.identity if hasattr(record, "selected") else record.revenue.identity
            peers = [r for r in registry if (r.selected if hasattr(r, "selected") else r.revenue).identity.period_scope() == anchor.period_scope()]
            active, error = auth._approval(peers, record.ref.permission, registry)
            if active is None and error == "approval_withdrawn":
                continue  # A retired scope needs no evidence; lineage was checked.
            _require(active is not None, error or "invalid_approval")
            if record != active:
                continue  # Withdrawn records never supply proofs.
            policies = [p for p in PRODUCTION_EVIDENCE_POLICIES if p.ref == record.ref]
            _require(len(policies) == 1, "missing_or_ambiguous_production_policy")
            names = ("revenue",) if record.ref.permission == "select:revenue" else ("revenue", "net_income")
            raw = tuple(auth.SourceIdentity.from_fact(f) for f in facts if f.company_cik == cik
                        and any(usable(f, METRICS[n]) and period_kind(f, METRICS[n]) == anchor.kind
                                and f.period_end == anchor.end for n in names))
            proofs.extend(_verify_policy(policies[0], record, raw, root, snapshot, publications))
        return tuple(set(proofs))
    except (OSError, ValueError, KeyError, TypeError, IndexError, RuntimeError, SQLAlchemyError, ET.ParseError, expat.ExpatError):
        return ()  # No partially verified proofs or financial fallback amounts.
