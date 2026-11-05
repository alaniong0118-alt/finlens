"""Bounded synthetic-only transport adapter. No services, storage or market data."""
from dataclasses import fields, is_dataclass
from datetime import date
from decimal import Decimal
from fractions import Fraction
import json
import re

from app.portfolio_risk import (
    AssetExposure, AssetFactor, FactorSession, ExactFactorPanel,
    PortfolioRiskError, calculate_historical_risk, display18,
)

SCHEMA_ID = "hypothetical-risk-v1"
MAX_REQUEST_BYTES = 131072
MAX_RESPONSE_BYTES = 1048576
MAX_ASSETS = 8
MAX_SESSIONS = 120
MAX_HORIZON = 20


def require(condition, reason="invalid_request"):
    if not condition:
        raise PortfolioRiskError(reason)


def record(value, keys):
    require(type(value) is dict and set(value) == set(keys), "invalid_fields")
    return value


def token(value):
    require(type(value) is str and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,63}", value), "invalid_identifier")
    return value


def number(value):
    # No floats, exponent notation, leading '+', whitespace or implicit percent.
    require(type(value) is str and len(value) <= 26
            and re.fullmatch(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]{1,12})?", value)
            and sum(c.isdigit() for c in value) <= 24, "invalid_decimal_string")
    return Decimal(value)


def day(value):
    require(type(value) is str and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value), "invalid_date")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise PortfolioRiskError("invalid_date") from None


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, "duplicate_json_key")
        value[key] = item
    return value


def parse_body(body):
    require(type(body) is bytes and len(body) <= MAX_REQUEST_BYTES, "request_resource_limit")
    try:
        return json.loads(body.decode("utf-8"), object_pairs_hook=unique_object,
                          parse_constant=lambda _: require(False, "invalid_json"))
    except (UnicodeError, ValueError, RecursionError) as exc:
        if isinstance(exc, PortfolioRiskError):
            raise
        raise PortfolioRiskError("invalid_json") from None


def encode(value):
    if type(value) is Fraction:
        return {"numerator": str(value.numerator), "denominator": str(value.denominator),
                "display": format(display18(value), "f")}
    if type(value) is date:
        return value.isoformat()
    if is_dataclass(value):
        return {f.name: encode(getattr(value, f.name)) for f in fields(value)}
    if type(value) is tuple:
        return [encode(item) for item in value]
    return value


def parse_inputs(value):
    record(value, ("reporting_currency", "exposure_date", "exposures", "sessions", "confidence", "horizon", "portfolio_value"))
    currency = value["reporting_currency"]
    require(type(currency) is str and re.fullmatch(r"[A-Z]{3}", currency), "invalid_reporting_currency")
    require(type(value["horizon"]) is int and 1 <= value["horizon"] <= MAX_HORIZON, "unsupported_horizon")
    require(type(value["exposures"]) is list and 1 <= len(value["exposures"]) <= MAX_ASSETS, "invalid_exposures")
    require(type(value["sessions"]) is list and len(value["sessions"]) <= MAX_SESSIONS, "session_resource_limit")
    exposures = []
    for item in value["exposures"]:
        record(item, ("asset_id", "amount"))
        exposures.append(AssetExposure(token(item["asset_id"]), currency, number(item["amount"])))
    sessions = []
    for item in value["sessions"]:
        record(item, ("session_id", "start", "end", "factors"))
        require(type(item["factors"]) is dict and len(item["factors"]) <= MAX_ASSETS, "incomplete_factor_panel")
        factors = tuple(AssetFactor(token(asset), number(factor)) for asset, factor in item["factors"].items())
        sessions.append(FactorSession(token(item["session_id"]), day(item["start"]), day(item["end"]), factors))
    return dict(exposures=tuple(exposures), reporting_currency=currency,
        exposure_date=day(value["exposure_date"]),
        panel=ExactFactorPanel("user-hypothetical", "user-entered-exact-gross-factors-v1", tuple(sessions)),
        horizon=value["horizon"], confidence=number(value["confidence"]),
        portfolio_value=None if value["portfolio_value"] is None else number(value["portfolio_value"]))


def calculate_request(value):
    result = calculate_historical_risk(**parse_inputs(value))
    return {"schema_id": SCHEMA_ID, "inputs": value, "result": encode(result)}


def response_bytes(value):
    payload = json.dumps(calculate_request(value), ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    require(len(payload) <= MAX_RESPONSE_BYTES, "response_resource_limit")
    return payload
