"""Pure synthetic declarations, never transport, authentication or authority.

Bytes are representation-body bytes after declared transfer framing, not a TLS
wire transcript. Logical offsets are supplied observations from one operation
origin, not measurements or enforcement. Every capture remains historical and
unverified, including replay and successful synthetic final-delivery decisions.
"""

from dataclasses import dataclass, replace
import hashlib
import json
import re

from app import research_contracts as c
from app import sec_identity_source as s


MAX_ISSUERS = MAX_REQUESTS = MAX_CONCURRENCY = 1
MAX_RETRIES = MAX_REDIRECTS = 0
MAX_BODY_BYTES = 4_194_304
MAX_BLOCK_BYTES = 65_536
MAX_BLOCKS = 1_024
MAX_HEADERS = 64
MAX_HEADER_NAME_BYTES = 128
MAX_HEADER_VALUE_BYTES = 2_048
MAX_HEADER_BYTES = MAX_RECEIPT_BYTES = 16_384
MAX_USER_AGENT_BYTES = 256
NS = 1_000_000_000
MAX_CONNECTION_NS = MAX_WRITE_NS = MAX_READ_INACTIVITY_NS = 5 * NS
MAX_POOL_NS = NS
MAX_HEADER_PHASE_NS = 10 * NS
MAX_OPERATION_NS = 30 * NS
MAX_CLEANUP_NS = 2 * NS
MIN_START_SPACING_NS = NS
CAPTURE_KIND = "synthetic"
RECEIPT_SCHEMA = "fl-ucr-01b2.synthetic.v1"
RETAINED_HEADERS = frozenset((
    "content-length", "transfer-encoding", "content-encoding", "content-type",
    "date", "etag", "last-modified",
))
CRITICAL_HEADERS = RETAINED_HEADERS | {"location", "content-range", "trailer"}


class SyntheticCaptureError(ValueError):
    """Payload-free structural/operation error; no partial result."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _require(condition, code):
    if not condition:
        raise SyntheticCaptureError(code)


def _integer(value, maximum, code, minimum=0):
    _require(type(value) is int and minimum <= value <= maximum, code)


def _ascii(value, maximum, code, pattern=None):
    _require(type(value) is str and 1 <= len(value) <= maximum, code)
    _require(all(32 <= ord(ch) <= 126 for ch in value), code)
    if pattern is not None:
        _require(re.fullmatch(pattern, value) is not None, code)


def _tuple(value, maximum, code):
    # Do not inspect elements of oversized or non-exact collections.
    _require(type(value) is tuple and len(value) <= maximum, code)


def _clean(value, cls, code):
    _require(type(value) is cls, code)
    try:
        return replace(value)
    except (AttributeError, TypeError):
        raise SyntheticCaptureError(code) from None


def _key(value, namespace):
    key = _clean(value, c.KeyRef, "key_type")
    _require(key.namespace == namespace, "key_namespace")
    return key


@dataclass(frozen=True, slots=True)
class SubmissionsRequest:
    expected_cik: str
    method: str
    url: str
    future_user_agent: str = "FinLens synthetic offline declaration"

    def __post_init__(self):
        c.KeyRef("sec_cik", self.expected_cik)
        _require(type(self.method) is str and self.method == "GET", "request_method")
        expected = f"https://data.sec.gov/submissions/CIK{self.expected_cik}.json"
        _require(type(self.url) is str and self.url == expected, "request_url")
        _ascii(self.future_user_agent, MAX_USER_AGENT_BYTES, "user_agent")


def build_submissions_request(expected_cik):
    """Construct the sole allowed URL; no acquisition or URL argument."""
    return SubmissionsRequest(expected_cik, "GET",
                              f"https://data.sec.gov/submissions/CIK{expected_cik}.json")


@dataclass(frozen=True, slots=True)
class ReplayIdentity:
    operation_uuid: str
    owner_ref: c.KeyRef
    session_ref: c.KeyRef
    request: SubmissionsRequest
    policy_ref: c.KeyRef
    policy_revision: str
    original_start: str
    original_deadline_ns: int = MAX_OPERATION_NS

    def __post_init__(self):
        _ascii(self.operation_uuid, 36, "operation_uuid",
               r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
        _require(self.operation_uuid != "00000000-0000-0000-0000-000000000000",
                 "operation_uuid")
        _key(self.owner_ref, "principal")
        _key(self.session_ref, "session")
        _clean(self.request, SubmissionsRequest, "request_type")
        _key(self.policy_ref, "rights_policy")
        _ascii(self.policy_revision, 64, "policy_revision", r"[A-Za-z0-9._:-]+")
        _require(type(self.original_start) is str and
                 c.InstantTimePoint(self.original_start).value == self.original_start,
                 "operation_start")
        _integer(self.original_deadline_ns, MAX_OPERATION_NS, "deadline", minimum=1)


@dataclass(frozen=True, slots=True)
class SyntheticObservation:
    offset_ns: int
    cancelled: bool = False
    revoked: bool = False

    def __post_init__(self):
        _integer(self.offset_ns, MAX_OPERATION_NS + MAX_CLEANUP_NS, "observation_offset")
        _require(type(self.cancelled) is bool and type(self.revoked) is bool,
                 "observation_flags")


@dataclass(frozen=True, slots=True)
class SyntheticContext:
    identity: ReplayIdentity
    observation: SyntheticObservation

    def __post_init__(self):
        _clean(self.identity, ReplayIdentity, "identity_type")
        _clean(self.observation, SyntheticObservation, "observation_type")


@dataclass(frozen=True, slots=True)
class PhaseCheckpoints:
    """Closed singleton phases, all offsets relative to original_start at zero.

    Pool/connect/write are consecutive intervals; headers allowance starts after
    write. Read inactivity is measured between headers, each block, and body end.
    Cleanup starts at body end; successful delivery still ends at the deadline.
    """

    pool_acquired_ns: int
    connected_ns: int
    write_complete_ns: int
    headers_complete_ns: int
    body_complete_ns: int
    cleanup_complete_ns: int

    def __post_init__(self):
        values = (self.pool_acquired_ns, self.connected_ns, self.write_complete_ns,
                  self.headers_complete_ns, self.body_complete_ns, self.cleanup_complete_ns)
        for offset in values:
            _integer(offset, MAX_OPERATION_NS + MAX_CLEANUP_NS, "phase_offset")
        _require(tuple(sorted(values)) == values, "phase_order")
        _integer(values[0], MAX_POOL_NS, "pool_wait")
        _integer(values[1] - values[0], MAX_CONNECTION_NS, "connection_timeout")
        _integer(values[2] - values[1], MAX_WRITE_NS, "write_timeout")
        _integer(values[3] - values[2], MAX_HEADER_PHASE_NS, "header_timeout")
        _integer(values[4], MAX_OPERATION_NS, "body_deadline")
        _integer(values[5] - values[4], MAX_CLEANUP_NS, "cleanup_timeout")


@dataclass(frozen=True, slots=True)
class BlockObservation:
    index: int
    offset_ns: int

    def __post_init__(self):
        _integer(self.index, MAX_BLOCKS - 1, "block_index")
        _integer(self.offset_ns, MAX_OPERATION_NS, "block_offset")


def validate_body_blocks(blocks):
    """Independent body validator; returns total before any concatenation."""
    _tuple(blocks, MAX_BLOCKS, "body_blocks")
    _require(bool(blocks), "body_blocks_empty")
    total = 0
    for block in blocks:
        _require(type(block) is bytes and 1 <= len(block) <= MAX_BLOCK_BYTES, "body_block")
        total += len(block)
        _require(total <= MAX_BODY_BYTES, "body_size")
    return total


def validate_response_headers(headers):
    """ASCII name + ': ' + value + CRLF per pair, in declaration order.

    Unknown headers are syntax/size checked then discarded. Critical duplicates
    reject even when equal. No redirects, partial responses or trailer fields.
    Returns lowercase sorted allowlisted pairs; neither limit implies the other.
    """
    _tuple(headers, MAX_HEADERS, "header_count")
    retained, critical, total = [], set(), 0
    for pair in headers:
        _require(type(pair) is tuple and len(pair) == 2, "header_pair")
        name, value = pair
        _ascii(name, MAX_HEADER_NAME_BYTES, "header_name", r"[!#$%&'*+.^_`|~0-9A-Za-z-]+")
        _ascii(value, MAX_HEADER_VALUE_BYTES, "header_value")
        total += len(name) + len(value) + 4
        _require(total <= MAX_HEADER_BYTES, "header_size")
        name = name.lower()
        if name in CRITICAL_HEADERS:
            _require(name not in critical, "header_conflict")
            critical.add(name)
        _require(name not in ("location", "content-range", "trailer"), "header_forbidden")
        if name in RETAINED_HEADERS:
            retained.append((name, value))
    return tuple(sorted(retained))


@dataclass(frozen=True, slots=True)
class SyntheticExchange:
    observed_url: str
    status: int
    headers: tuple[tuple[str, str], ...]
    body_blocks: tuple[bytes, ...]
    phases: PhaseCheckpoints
    block_observations: tuple[BlockObservation, ...]
    framing_complete: bool = True
    chunked_complete: bool = False
    synthetic_tls_observed: bool = True
    issuer_count: int = 1
    request_count: int = 1
    retries: int = 0
    redirects: int = 0
    concurrency: int = 1
    start_spacing_ns: int = MIN_START_SPACING_NS

    def __post_init__(self):
        # Bound both collections before traversing either, including bypassed values.
        _tuple(self.body_blocks, MAX_BLOCKS, "body_blocks")
        _tuple(self.block_observations, MAX_BLOCKS, "block_observations")
        _tuple(self.headers, MAX_HEADERS, "header_count")
        _require(len(self.block_observations) == len(self.body_blocks), "block_observation_count")
        _ascii(self.observed_url, 128, "observed_url")
        _integer(self.status, 200, "response_status", minimum=200)
        for value, maximum, minimum, code in (
            (self.issuer_count, MAX_ISSUERS, 1, "issuer_count"),
            (self.request_count, MAX_REQUESTS, 1, "request_count"),
            (self.retries, MAX_RETRIES, 0, "retries"),
            (self.redirects, MAX_REDIRECTS, 0, "redirects"),
            (self.concurrency, MAX_CONCURRENCY, 1, "concurrency"),
        ):
            _integer(value, maximum, code, minimum)
        # No unbounded integer/spacing representation enters a receipt.
        _integer(self.start_spacing_ns, MAX_OPERATION_NS, "start_spacing",
                 MIN_START_SPACING_NS)
        for flag in (self.framing_complete, self.chunked_complete, self.synthetic_tls_observed):
            _require(type(flag) is bool, "exchange_flags")
        _require(self.framing_complete, "incomplete_framing")
        total = validate_body_blocks(self.body_blocks)
        headers = dict(validate_response_headers(self.headers))
        _require(headers.get("content-encoding", "identity") == "identity", "content_encoding")
        _require(headers.get("content-type", "application/json") in
                 ("application/json", "application/json; charset=utf-8"), "content_type")
        length, transfer = headers.get("content-length"), headers.get("transfer-encoding")
        _require((length is None) != (transfer is None), "framing_choice")
        if length is not None:
            _require(re.fullmatch(r"0|[1-9][0-9]{0,6}", length) is not None,
                     "content_length")
            _require(int(length) == total and not self.chunked_complete, "length_mismatch")
        else:
            _require(transfer == "chunked" and self.chunked_complete, "chunked_framing")
        phases = _clean(self.phases, PhaseCheckpoints, "phases_type")
        previous = phases.headers_complete_ns
        for index, observation in enumerate(self.block_observations):
            observation = _clean(observation, BlockObservation, "block_observation_type")
            _require(observation.index == index, "block_observation_index")
            _require(previous <= observation.offset_ns <= phases.body_complete_ns,
                     "block_observation_order")
            _integer(observation.offset_ns - previous, MAX_READ_INACTIVITY_NS,
                     "read_inactivity")
            previous = observation.offset_ns
        _integer(phases.body_complete_ns - previous, MAX_READ_INACTIVITY_NS, "read_inactivity")


def _identity_json(identity):
    def key(value):
        return {"namespace": value.namespace, "id": value.id}

    request = identity.request
    return {
        "operation_uuid": identity.operation_uuid,
        "owner_ref": key(identity.owner_ref), "session_ref": key(identity.session_ref),
        "expected_cik": request.expected_cik,
        "request": {"method": request.method, "url": request.url,
                    "future_user_agent": request.future_user_agent},
        "policy_ref": key(identity.policy_ref), "policy_revision": identity.policy_revision,
        "original_start": identity.original_start,
        "original_deadline_ns": identity.original_deadline_ns,
    }


def validate_receipt_bytes(encoded):
    """Independent byte budget, not a decoder or an authenticity verifier."""
    _require(type(encoded) is bytes and len(encoded) <= MAX_RECEIPT_BYTES, "receipt_size")


def _receipt(context, exchange, artifact, digest, total):
    p = exchange.phases
    observation = context.observation
    # Fixed closed schema and insertion order. No caller dictionaries or extras.
    record = {
        "schema": RECEIPT_SCHEMA, "capture_kind": CAPTURE_KIND, "outcome": "complete",
        "source_identity": s.SOURCE_IDENTITY, "parser_revision": s.PARSER_REVISION,
        "replay_identity": _identity_json(context.identity),
        "untrusted_artifact_ref": {"namespace": artifact.namespace, "id": artifact.id},
        "observed_url": exchange.observed_url, "status": exchange.status,
        "headers": validate_response_headers(exchange.headers),
        "body_bytes": total, "body_sha256": digest,
        "blocks": tuple({"index": i, "length": len(block),
                         "sha256": hashlib.sha256(block).hexdigest(),
                         "offset_ns": exchange.block_observations[i].offset_ns}
                        for i, block in enumerate(exchange.body_blocks)),
        "phases": {"pool_acquired_ns": p.pool_acquired_ns, "connected_ns": p.connected_ns,
                   "write_complete_ns": p.write_complete_ns,
                   "headers_complete_ns": p.headers_complete_ns,
                   "body_complete_ns": p.body_complete_ns,
                   "cleanup_complete_ns": p.cleanup_complete_ns},
        "capture_observation": {"offset_ns": observation.offset_ns,
                                "cancelled": observation.cancelled, "revoked": observation.revoked},
        "framing_complete": exchange.framing_complete,
        "chunked_complete": exchange.chunked_complete,
        "synthetic_tls_observed": exchange.synthetic_tls_observed,
        "issuer_count": exchange.issuer_count, "request_count": exchange.request_count,
        "retries": exchange.retries, "redirects": exchange.redirects,
        "concurrency": exchange.concurrency, "start_spacing_ns": exchange.start_spacing_ns,
    }
    encoded = json.dumps(record, ensure_ascii=False, separators=(",", ":"),
                         allow_nan=False).encode("utf-8")
    validate_receipt_bytes(encoded)
    return encoded


def _authorized(context):
    observation = context.observation
    _require(not observation.cancelled, "cancelled")
    _require(not observation.revoked, "revoked")
    _require(observation.offset_ns <= context.identity.original_deadline_ns, "expired")


def _capture_parts(context, exchange, artifact):
    context = _clean(context, SyntheticContext, "context_type")
    exchange = _clean(exchange, SyntheticExchange, "exchange_type")
    artifact = _key(artifact, "artifact")
    _require(exchange.observed_url == context.identity.request.url, "url_mismatch")
    _require(exchange.phases.body_complete_ns <= context.identity.original_deadline_ns,
             "body_deadline")
    _require(exchange.phases.cleanup_complete_ns <= context.observation.offset_ns,
             "capture_observation_order")
    _authorized(context)
    # Size and collection checks have already run, before concatenation/hash/parser.
    body = b"".join(exchange.body_blocks)
    s.parse_sec_submissions(body, expected_cik=context.identity.request.expected_cik)
    digest = hashlib.sha256(body).hexdigest()
    receipt = _receipt(context, exchange, artifact, digest, len(body))
    return body, digest, receipt, hashlib.sha256(receipt).hexdigest()


@dataclass(frozen=True, slots=True)
class SyntheticCapture:
    context: SyntheticContext
    exchange: SyntheticExchange
    untrusted_artifact_ref: c.KeyRef
    original_bytes: bytes
    body_sha256: str
    receipt_bytes: bytes
    receipt_sha256: str
    capture_kind: str = "synthetic"
    outcome: str = "complete"

    def __post_init__(self):
        _require(type(self.capture_kind) is str and self.capture_kind == CAPTURE_KIND,
                 "capture_kind")
        _require(type(self.outcome) is str and self.outcome == "complete", "capture_outcome")
        _require(type(self.original_bytes) is bytes and len(self.original_bytes) <= MAX_BODY_BYTES,
                 "original_bytes")
        for digest in (self.body_sha256, self.receipt_sha256):
            _ascii(digest, 64, "digest", r"[0-9a-f]{64}")
        validate_receipt_bytes(self.receipt_bytes)
        parts = _capture_parts(self.context, self.exchange, self.untrusted_artifact_ref)
        _require((self.original_bytes, self.body_sha256, self.receipt_bytes, self.receipt_sha256)
                 == parts, "capture_consistency")


def capture_synthetic_submissions(request, *, context, exchange, prior=None):
    """Validate a declaration, or reuse the complete historical prior unchanged.

    Never dispatches anything. A prior is supplied state, not evidence that no
    missing/uncertain attempts exist. No persistent idempotency or quarantine.
    Artifact label is deterministic from operation UUID, still wholly untrusted.
    """
    request = _clean(request, SubmissionsRequest, "request_type")
    context = _clean(context, SyntheticContext, "context_type")
    _require(request == context.identity.request, "request_identity")
    if prior is not None:
        _require(exchange is None, "prior_with_exchange")
        prior = _clean(prior, SyntheticCapture, "prior_type")
        _require(prior.context.identity == context.identity, "replay_identity")
        _require(context.observation.offset_ns >= prior.context.observation.offset_ns,
                 "replay_observation_order")
        _authorized(context)
        return prior
    _authorized(context)
    artifact = c.KeyRef("artifact", "synthetic:" + context.identity.operation_uuid)
    parts = _capture_parts(context, exchange, artifact)
    return SyntheticCapture(context, exchange, artifact, *parts)


@dataclass(frozen=True, slots=True)
class CapturedIdentityInventory:
    capture: SyntheticCapture
    source_bound: s.SourceBoundIdentityInventory

    def __post_init__(self):
        capture = _clean(self.capture, SyntheticCapture, "capture_type")
        bound = _clean(self.source_bound, s.SourceBoundIdentityInventory, "source_bound_type")
        expected = _source_bound(capture)
        _require(bound == expected, "source_bound_substitution")

    @property
    def inventory(self):
        return _clean(self, CapturedIdentityInventory, "captured_inventory_type").source_bound.inventory

    def source_binding_for(self, candidate):
        """Retain BOTH sidecars for current/former-name and CIK matches."""
        clean = _clean(self, CapturedIdentityInventory, "captured_inventory_type")
        clean.source_bound.source_binding_for(candidate)
        return clean


def _source_bound(capture):
    source = s.parse_sec_submissions(capture.original_bytes,
                                     expected_cik=capture.context.identity.request.expected_cik)
    return s.to_identity_inventory(source, untrusted_evidence_key=capture.untrusted_artifact_ref)


def bind_synthetic_capture(capture):
    """Timeless structural validation. Does not issue a delivery decision."""
    capture = _clean(capture, SyntheticCapture, "capture_type")
    return CapturedIdentityInventory(capture, _source_bound(capture))


def _delivery_reason(observation, original_deadline_ns):
    """One synthetic lifecycle policy for construction and final delivery."""
    observation = _clean(observation, SyntheticObservation, "observation_type")
    _integer(original_deadline_ns, MAX_OPERATION_NS, "deadline", minimum=1)
    return ("cancelled" if observation.cancelled else "revoked" if observation.revoked
            else "expired" if observation.offset_ns > original_deadline_ns
            else "synthetic_only")


@dataclass(frozen=True, slots=True)
class SyntheticDeliveryDecision:
    """Self-consistent supplied metadata, never authenticated permission.

    The required original deadline shares the observation's operation origin.
    Construction and replace revalidate it; no implicit global-deadline fallback.
    """

    allowed: bool
    reason: str
    operation_uuid: str
    receipt_sha256: str
    observation: SyntheticObservation
    original_deadline_ns: int
    capture_kind: str = "synthetic"

    def __post_init__(self):
        _require(type(self.capture_kind) is str and self.capture_kind == CAPTURE_KIND,
                 "decision_kind")
        _require(type(self.allowed) is bool and type(self.reason) is str and
                 self.reason in ("synthetic_only", "cancelled", "revoked", "expired") and
                 self.allowed == (self.reason == "synthetic_only"), "decision_shape")
        _ascii(self.operation_uuid, 36, "operation_uuid",
               r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
        _ascii(self.receipt_sha256, 64, "digest", r"[0-9a-f]{64}")
        _require(self.reason == _delivery_reason(self.observation, self.original_deadline_ns),
                 "decision_lifecycle")


def decide_synthetic_delivery(capture, *, context):
    """Fresh supplied decision, neither authenticated permission nor enforcement.

    Call at the simulated final delivery boundary; a past decision is historical,
    not a reusable grant. Structural validation remains possible after expiry.
    """
    capture = _clean(capture, SyntheticCapture, "capture_type")
    context = _clean(context, SyntheticContext, "context_type")
    _require(context.identity == capture.context.identity, "delivery_identity")
    _require(context.observation.offset_ns >= capture.context.observation.offset_ns,
             "delivery_observation_order")
    observation = context.observation
    reason = _delivery_reason(observation, context.identity.original_deadline_ns)
    return SyntheticDeliveryDecision(reason == "synthetic_only", reason,
                                     context.identity.operation_uuid, capture.receipt_sha256,
                                     observation, context.identity.original_deadline_ns)
