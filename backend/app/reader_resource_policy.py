"""Fixed Reader logical limits, independent of sessions, ranking and runtime budgets.

Logical bytes count UTF-8 strings, decimal ASCII integers and ISO dates, once per
occurrence (including repeated metadata); record/container overhead is excluded.
These are payload limits, not Python RSS, elapsed-time or PostgreSQL work bounds.
"""
from datetime import date
import json


LIFECYCLE_BYTES = 131072
JSON_DEPTH = 2
PENDING_TARGETS = 4096
CHUNKS = 4000
CHUNK_CHARS = 3000
TEXT_CHARS = 12000000
TEXT_BYTES = 48000000
VECTOR_DIMENSIONS = 384
VECTOR_COMPONENTS = 1536000
NON_TEXT_BYTES = 2000000
DETACHED_BYTES = 50000000
LIFECYCLE_FIELDS = frozenset((
    'status', 'last_attempt_at', 'last_checked_at', 'last_successful_sync_at',
    'latest_source_filing_date', 'last_error', 'failure_stage', 'pending_targets',
    'inventory_complete',
))
STRING_WIDTHS = {
    'ticker': 10, 'company_cik': 10, 'company_name': 200,
    'accession_number': 30, 'form': 20, 'filename': 255,
    'content_digest': 64, 'chunk_id': 50, 'sec_url': 500,
}


class ResourceExcess(ValueError):
    pass


class InvalidPayload(ValueError):
    pass


def scalar(name, value):
    """Check exact scalar types/widths before encoding, hashing or detaching."""
    if name in STRING_WIDTHS:
        if type(value) is not str:
            raise InvalidPayload()
        if len(value) > STRING_WIDTHS[name]:
            raise ResourceExcess()
    elif name == 'filed':
        if type(value) is not date:
            raise InvalidPayload()
    elif type(value) is not int:
        raise InvalidPayload()
    elif not 0 <= value <= 9_007_199_254_740_991:
        raise InvalidPayload()


def logical_bytes(value):
    if type(value) is str:
        try:
            return len(value.encode('utf-8'))
        except UnicodeError:
            raise InvalidPayload() from None
    if type(value) is date:
        return 10
    if type(value) is int:
        return len(str(value))
    raise InvalidPayload()


def detached_budget(non_text, text_chars, text_bytes, components):
    if (non_text > NON_TEXT_BYTES or text_chars > TEXT_CHARS
            or text_bytes > TEXT_BYTES or components > VECTOR_COMPONENTS
            or non_text + text_bytes > DETACHED_BYTES):
        raise ResourceExcess()


def lifecycle(raw, measured_bytes):
    """Reject byte/depth excess before parsing; reject duplicate decoded keys.

    Depth counts objects/arrays, ignoring quoted/escaped delimiters. Scan the
    entire bounded representation before syntax validation, so excess wins over
    malformed JSON. Recognized names are a set; raw occurrences are never a
    substitute for duplicate rejection. Pending array occurrences count without
    deduplication. Unknown fields are rejected before Pydantic error creation.
    """
    if type(measured_bytes) is not int or measured_bytes < 0:
        raise InvalidPayload()
    if measured_bytes > LIFECYCLE_BYTES:
        raise ResourceExcess()
    if type(raw) is not str:
        raise InvalidPayload()
    if len(raw) > LIFECYCLE_BYTES:
        raise ResourceExcess()
    actual = logical_bytes(raw)
    if actual > LIFECYCLE_BYTES:
        raise ResourceExcess()
    if actual != measured_bytes:
        raise InvalidPayload()
    depth, quoted, escaped = 0, False, False
    for char in raw:
        if quoted:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in '{[':
            depth += 1
            if depth > JSON_DEPTH:
                raise ResourceExcess()
        elif char in '}]':
            # Syntax is the parser's responsibility; malformed closing tokens
            # must not hide excessive later opening containers.
            depth = max(0, depth - 1)

    duplicate = False

    def pairs(members):
        nonlocal duplicate
        result = {}
        for key, value in members:
            if key == 'pending_targets' and type(value) is list and len(value) > PENDING_TARGETS:
                raise ResourceExcess()
            if key in result:
                duplicate = True
            result[key] = value
        return result

    def number(token):
        # No lifecycle field accepts a JSON number. Avoid unbounded integer or
        # floating conversion. Defer malformed-scalar rejection until pending
        # limits have been checked, including mixed malformed/over-limit cases.
        return numeric_sentinel

    numeric_sentinel = object()
    try:
        value = json.loads(raw, object_pairs_hook=pairs, parse_int=number,
                           parse_float=number, parse_constant=number)
    except (ValueError, RecursionError) as exc:
        if isinstance(exc, ResourceExcess):
            raise
        raise InvalidPayload() from None
    if type(value) is not dict or duplicate or value.keys() - LIFECYCLE_FIELDS:
        raise InvalidPayload()
    for key, member in value.items():
        if key == 'pending_targets':
            if type(member) is not list or any(type(v) is not str for v in member):
                raise InvalidPayload()
        elif key == 'inventory_complete':
            if type(member) is not bool:
                raise InvalidPayload()
        elif member is not None and type(member) is not str:
            raise InvalidPayload()
    return value
