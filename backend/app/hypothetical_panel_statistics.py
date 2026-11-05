"""Separate synthetic diagnostic receipt; the v1 risk/replay format is unchanged."""
import json

from app.factor_panel_statistics import calculate_panel_statistics
from app.hypothetical_risk import parse_inputs, encode, require, MAX_RESPONSE_BYTES

SCHEMA_ID = 'hypothetical-panel-statistics-v1'


def calculate_request(value):
    result = calculate_panel_statistics(**parse_inputs(value))
    return {'schema_id': SCHEMA_ID, 'inputs': value, 'result': encode(result)}


def response_bytes(value):
    payload = json.dumps(calculate_request(value), ensure_ascii=True, separators=(',', ':')).encode('utf-8')
    require(len(payload) <= MAX_RESPONSE_BYTES, 'response_resource_limit')
    return payload
