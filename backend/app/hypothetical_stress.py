"""Exact conditional linear price stress on user assertions; no I/O or history."""
from fractions import Fraction
import json
import re

from app.hypothetical_risk import (
    MAX_ASSETS, MAX_RESPONSE_BYTES, day, encode, number, record, require, token,
)
from app.portfolio_risk import PRECISION_ID

SCHEMA_ID = "hypothetical-linear-stress-v1"
METHOD_ID = "hypothetical-linear-price-stress-v1"
EXPOSURE_TYPE = "linear_price_notional"
MAX_SCENARIOS = 12
MAX_COMMON_SHOCKS = 21
MIN_SHOCK_PERCENT = -100
MAX_SHOCK_PERCENT = 1000
NOTICES = (
    "user_assumptions_not_observed_market_data",
    "conditional_calculation_not_probability_forecast_or_advice",
    "linear_price_notionals_only_no_fx",
    "fixed_exposures_no_fees_financing_or_rebalancing",
    "common_shocks_independent_of_named_scenarios",
)


def shock(value):
    exact = Fraction(number(value))
    require(MIN_SHOCK_PERCENT <= exact <= MAX_SHOCK_PERCENT, "unsupported_shock_percent")
    return exact


def outcome(exposures, shocks):
    contributions, total = [], Fraction(0)
    for exposure in exposures:
        amount = exposure["amount"]
        percentage = shocks[exposure["asset_id"]]
        pnl = amount * percentage / 100
        total += pnl
        contributions.append({"asset_id": exposure["asset_id"], "exposure": amount,
                              "shock_percent": percentage, "pnl": pnl, "loss": -pnl})
    return {"contributions": contributions, "total_pnl": total, "total_loss": -total}


def calculate_request(value):
    record(value, ("reporting_currency", "exposure_date", "exposures", "scenarios", "common_shocks"))
    currency = value["reporting_currency"]
    require(type(currency) is str and re.fullmatch(r"[A-Z]{3}", currency), "invalid_reporting_currency")
    exposure_date = day(value["exposure_date"])
    require(type(value["exposures"]) is list and 1 <= len(value["exposures"]) <= MAX_ASSETS, "invalid_exposures")
    require(type(value["scenarios"]) is list and 1 <= len(value["scenarios"]) <= MAX_SCENARIOS, "scenario_resource_limit")
    require(type(value["common_shocks"]) is list and 1 <= len(value["common_shocks"]) <= MAX_COMMON_SHOCKS, "common_shock_resource_limit")
    exposures = []
    for item in value["exposures"]:
        record(item, ("asset_id", "amount", "currency", "exposure_type"))
        require(type(item["currency"]) is str and item["currency"] == currency, "exposure_currency_mismatch")
        require(type(item["exposure_type"]) is str and item["exposure_type"] == EXPOSURE_TYPE, "unsupported_exposure_type")
        exposures.append({"asset_id": token(item["asset_id"]), "amount": Fraction(number(item["amount"])),
                          "currency": currency, "exposure_type": EXPOSURE_TYPE})
    assets = {e["asset_id"] for e in exposures}
    require(len(assets) == len(exposures), "duplicate_exposure")
    exposures.sort(key=lambda e: e["asset_id"])
    scenarios, seen = [], set()
    for item in value["scenarios"]:
        record(item, ("scenario_id", "shocks"))
        scenario_id = token(item["scenario_id"])
        require(scenario_id not in seen, "duplicate_scenario")
        seen.add(scenario_id)
        require(type(item["shocks"]) is dict and set(item["shocks"]) == assets, "incomplete_shock_panel")
        scenarios.append((scenario_id, {asset: shock(v) for asset, v in item["shocks"].items()}))
    common = tuple(shock(v) for v in value["common_shocks"])
    require(len(set(common)) == len(common), "duplicate_common_shock")
    # Validate every cell before arithmetic; zero exposures cannot hide a gap.
    net = sum((e["amount"] for e in exposures), Fraction(0))
    gross = sum((abs(e["amount"]) for e in exposures), Fraction(0))
    result = {"method_id": METHOD_ID, "precision_id": PRECISION_ID,
        "data_authority": "unverified_user_assumptions", "reporting_currency": currency,
        "exposure_date": exposure_date, "exposure_type": EXPOSURE_TYPE, "exposures": exposures,
        "net_exposure": net, "gross_exposure": gross,
        "common_shock_pnl_per_percentage_point": net / 100,
        "scenarios": [{"scenario_id": sid, **outcome(exposures, shocks)} for sid, shocks in scenarios],
        "common_shock_sensitivity": [{"shock_percent": s, **outcome(exposures, dict.fromkeys(assets, s))}
                                     for s in sorted(common)], "notices": NOTICES}
    # encode handles exact Fractions/dates/tuples; containers here remain ordinary
    # JSON dictionaries/lists, so descend those without rounding or coercion.
    return {"schema_id": SCHEMA_ID, "inputs": value, "result": encode_tree(result)}


def encode_tree(value):
    if type(value) is dict:
        return {key: encode_tree(item) for key, item in value.items()}
    if type(value) is list:
        return [encode_tree(item) for item in value]
    return encode(value)


def response_bytes(value):
    payload = json.dumps(calculate_request(value), ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    require(len(payload) <= MAX_RESPONSE_BYTES, "response_resource_limit")
    return payload
