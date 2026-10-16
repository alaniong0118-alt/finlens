"""New history composition boundary; existing parser/return suites are not repeated."""
from copy import deepcopy
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import socket

import pytest

from app.market_data_contracts import MarketContractError
from app.market_history import MAX_CONTEXT_BYTES, MAX_RESPONSE_BYTES, inspect_raw_history


FIXTURES = Path(__file__).parent / "fixtures"
CONTEXT = FIXTURES / "market_history" / "synthetic-context.json"


def payload(name="ordinary"):
    return (FIXTURES / "tiingo_eod" / f"{name}.json").read_bytes()


def context(data=None, body=None):
    data = deepcopy(data) if data is not None else json.loads(CONTEXT.read_bytes())
    if body is not None:
        data["request"]["source"]["response_sha256"] = hashlib.sha256(body).hexdigest()
    return json.dumps(data).encode()


def test_exact_projection_currency_three_bindings_and_no_source_promotion():
    body = payload().replace(b'"close":105', b'"close":105.000000000000000001')
    raw_context = context(body=body)
    history = inspect_raw_history(body, raw_context)
    output = history.to_dict()
    assert [row["unadjusted_close"] for row in output["rows"]] == ["100", "105.000000000000000001"]
    assert {row["declared_currency"] for row in output["rows"]} == {"USD"}
    assert output["value_label"] == "Unadjusted close" and output["adjustment_basis"] == "raw"
    provenance = output["provenance"]
    assert provenance["source"]["response_sha256"] == hashlib.sha256(body).hexdigest()
    assert provenance["context_sha256"] == hashlib.sha256(raw_context).hexdigest()
    assert len({provenance["source"]["response_sha256"], provenance["normalized_content_sha256"],
                provenance["publication_manifest_sha256"]}) == 3
    for row in output["rows"]:
        assert provenance["normalized_content_sha256"] in row["observation_ids"][0]
    assert output["provenance_state"] == "unverified" and output["trusted_custody"] is False
    assert output["normalization_state"] == "blocked" and output["return_state"] == "unavailable"
    assert output["publication_state"] == "unsupported"  # continuity remains unresolved
    assert output["freshness_state"] == "unknown" and output["market_data_version"] == 0
    assert output["provenance"]["source"]["available_at"] is None
    assert output["declared_identity"]["listing"]["continuity"] == "unresolved"
    assert "authenticated evidence" in output["declaration_notice"]


@pytest.mark.parametrize("name,closes,reason", [
    ("ordinary", ["100", "105"], "missing_corporate_action_coverage"),
    ("split", ["100", "50"], "unverified_split_event"),
    ("dividend", ["100", "99"], "unclassified_cash_distribution"),
])
def test_fictional_action_fixtures_never_substitute_adjusted_or_publish_returns(name, closes, reason):
    body = payload(name)
    output = inspect_raw_history(body, context(body=body)).to_dict()
    assert [row["unadjusted_close"] for row in output["rows"]] == closes
    assert reason in output["reasons"] and "missing_corporate_action_coverage" in output["reasons"]
    assert output["normalization_state"] == "blocked"
    assert output["publication_state"] == "unsupported"
    assert output["return_state"] == output["adjusted_series_state"] == "unavailable"
    assert all(set(row) == {"session_date", "close_at", "observation_state", "unadjusted_close",
                            "declared_currency", "observation_ids"} for row in output["rows"])


def test_missing_and_empty_rows_are_explicit_without_fill_or_calendar_inference():
    rows = json.loads(payload())
    for selected in ([rows[0]], []):
        body = json.dumps(selected).encode()
        history = inspect_raw_history(body, context(body=body))
        assert len(history.rows) == 2
        assert history.rows[-1].session_date == "2026-01-06"
        assert history.rows[-1].observation_state == "missing"
        assert history.rows[-1].unadjusted_close is None and history.rows[-1].observation_ids == ()
        assert "missing_session_observations" in history.reasons
    data = json.loads(CONTEXT.read_bytes())
    data["request"]["calendar"]["sessions"] = data["request"]["calendar"]["sessions"][:1]
    body = json.dumps(rows[:1]).encode()
    history = inspect_raw_history(body, context(data, body))
    assert len(history.rows) == 1  # no Tuesday invented despite the coverage range
    assert "missing_session_observations" not in history.reasons


@pytest.mark.parametrize("kind", ["synthetic", "unverified_local"])
def test_labels_are_declarations_and_unknown_availability_stays_null(kind):
    data = json.loads(CONTEXT.read_bytes())
    data["input_kind"] = kind
    data["request"]["listing"]["continuity"] = "same_security_verified"
    output = inspect_raw_history(payload(), context(data)).to_dict()
    assert output["input_kind"] == kind
    assert output["provenance_state"] == "unverified" and output["trusted_custody"] is False
    assert output["publication_state"] == "missing" and output["return_state"] == "unavailable"
    assert output["provenance"]["source"]["available_at"] is None


@pytest.mark.parametrize("mutate", [
    lambda d: d.update(input_kind="trusted"),
    lambda d: d.update(adjustment_basis="split_adjusted"),
    lambda d: d.update(adjustment_basis=["raw", "total_return_adjusted"]),
    lambda d: d.update(trusted_custody=True),
    lambda d: d["request"].update(state="complete"),
    lambda d: d["request"].update(security=[d["request"]["security"]]),
    lambda d: d["request"]["listing"].update(security_id="other"),
    lambda d: d["request"]["listing"].update(currency="USD/EUR"),
    lambda d: d["request"]["security"].update(company_id=True),
    lambda d: d["request"]["mappings"][0].update(identity_resolved="true"),
    lambda d: d["request"]["mappings"][0].update(symbol="OTHER"),
    lambda d: d["request"]["mappings"].append(deepcopy(d["request"]["mappings"][0])),
    lambda d: d["request"]["source"].update(response_sha256="0" * 64),
    lambda d: d["request"]["source"].update(source_id="secret\n\x1b[31m"),
    lambda d: d["request"]["source"].update(available_at="2026-01-09"),
    lambda d: d["request"]["format"].update(dividend_share_basis="verified"),
    lambda d: d["request"]["calendar"]["sessions"].append(deepcopy(d["request"]["calendar"]["sessions"][0])),
])
def test_invalid_or_ambiguous_context_cannot_bypass_existing_validation(mutate):
    data = json.loads(CONTEXT.read_bytes())
    mutate(data)
    with pytest.raises(MarketContractError):
        inspect_raw_history(payload(), context(data))


def test_duplicate_payload_and_incompatible_row_basis_fail_closed():
    rows = json.loads(payload())
    for changed in (rows + [rows[0]], [dict(rows[0], adjustment_basis="adjusted"), rows[1]]):
        body = json.dumps(changed).encode()
        with pytest.raises(MarketContractError):
            inspect_raw_history(body, context(body=body))


def test_stale_raw_normalized_manifest_and_context_bindings():
    original = inspect_raw_history(payload(), CONTEXT.read_bytes()).to_dict()
    data = json.loads(CONTEXT.read_bytes())
    data["expected_bindings"] = {key: original["provenance"][key] for key in
                                 ("normalized_content_sha256", "publication_manifest_sha256")}
    assert inspect_raw_history(payload(), context(data)).rows[0].unadjusted_close == "100"
    for old, new in ((b'"volume":1000', b'"volume":1001'), (b'"adjHigh":101', b'"adjHigh":102')):
        changed_body = payload().replace(old, new)
        with pytest.raises(MarketContractError, match="response_fingerprint_mismatch"):
            inspect_raw_history(changed_body, context(data))
        with pytest.raises(MarketContractError, match="stale_history_binding"):
            inspect_raw_history(changed_body, context(data, changed_body))
    for section, key, value in (("source", "source_id", "different-receipt"),
                                ("listing", "continuity", "same_security_verified"),
                                ("calendar", "version", "different-calendar")):
        changed = deepcopy(data)
        changed["request"][section][key] = value
        with pytest.raises(MarketContractError, match="stale_history_binding"):
            inspect_raw_history(payload(), context(changed))
    changed = deepcopy(data)
    changed.pop("expected_bindings")
    changed["input_kind"] = "unverified_local"
    assert inspect_raw_history(payload(), context(changed)).context_sha256 != original["provenance"]["context_sha256"]


@pytest.mark.parametrize("raw_context", [b"", b"x" * (MAX_CONTEXT_BYTES + 1), b"\xff", b"[" * 1500,
    b'{"schema_version":1,"schema_version":1}', b'{"x":NaN}', b'{"x":1.1}', b'{"x":123456789012345678901}'],
    ids=("empty", "oversize", "utf8", "depth", "duplicate", "nonfinite", "float", "integer"))
def test_context_byte_json_duplicate_and_numeric_bounds(raw_context):
    with pytest.raises(MarketContractError):
        inspect_raw_history(payload(), raw_context)


def test_payload_bound_and_inclusive_day_limit():
    with pytest.raises(MarketContractError, match="invalid_response_bound"):
        inspect_raw_history(b" " * (MAX_RESPONSE_BYTES + 1), CONTEXT.read_bytes())
    data = json.loads(CONTEXT.read_bytes())
    end = (date(2026, 1, 5) + timedelta(days=365)).isoformat()
    data["request"]["coverage_end"] = data["request"]["calendar"]["covered_end"] = end
    assert len(inspect_raw_history(payload(), context(data)).rows) == 2
    end = (date(2026, 1, 5) + timedelta(days=366)).isoformat()
    data["request"]["coverage_end"] = data["request"]["calendar"]["covered_end"] = end
    with pytest.raises(MarketContractError, match="invalid_history_day_bound"):
        inspect_raw_history(payload(), context(data))


def test_session_limit_rejects_before_normalization_and_context_exact_size_is_allowed():
    data = json.loads(CONTEXT.read_bytes())
    data["request"]["calendar"]["sessions"] *= 184
    with pytest.raises(MarketContractError, match="invalid_history_session_bound"):
        inspect_raw_history(payload(), context(data))
    raw_context = CONTEXT.read_bytes()
    padded = raw_context + b" " * (MAX_CONTEXT_BYTES - len(raw_context))
    assert inspect_raw_history(payload(), padded).rows[0].unadjusted_close == "100"


def test_exact_payload_limit_and_chronological_date_labels():
    body = payload()
    padded = body + b" " * (MAX_RESPONSE_BYTES - len(body))
    history = inspect_raw_history(padded, context(body=padded))
    assert [row.session_date for row in history.rows] == ["2026-01-05", "2026-01-06"]
    reversed_body = json.dumps(list(reversed(json.loads(body)))).encode()
    assert inspect_raw_history(reversed_body, context(body=reversed_body)).rows == history.rows


def test_366_explicit_sessions_allowed_and_367_rejected():
    data = json.loads(CONTEXT.read_bytes())
    start = date(2026, 1, 5)
    end = (start + timedelta(days=365)).isoformat()
    # These are fictional supplied sessions, including weekends; no real calendar claim.
    data["request"]["calendar"]["sessions"] = [dict(session_date=(start + timedelta(days=n)).isoformat(),
        close_at=(start + timedelta(days=n)).isoformat() + "T16:00:00-05:00") for n in range(366)]
    data["request"]["coverage_end"] = data["request"]["calendar"]["covered_end"] = end
    data["request"]["source"]["retrieved_at"] = "2027-01-10T22:00:00Z"
    data["request"]["published_at"] = "2027-01-10T23:00:00Z"
    history = inspect_raw_history(payload(), context(data))
    assert len(history.rows) == 366
    assert sum(row.observation_state == "missing" for row in history.rows) == 364
    data["request"]["calendar"]["sessions"].append(dict(session_date="2027-01-06", close_at="2027-01-06T16:00:00-05:00"))
    with pytest.raises(MarketContractError, match="invalid_history_session_bound"):
        inspect_raw_history(payload(), context(data))


def test_pure_projection_never_opens_files_or_network_and_output_mutation_is_isolated(monkeypatch):
    body, raw_context = payload(), CONTEXT.read_bytes()
    def forbidden(*args, **kwargs):
        raise AssertionError("unexpected IO")
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr("builtins.open", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    history = inspect_raw_history(body, raw_context)
    output = history.to_dict()
    output["rows"][0]["unadjusted_close"] = "999"
    output["declared_identity"]["security"]["security_id"] = "changed"
    assert history.to_dict()["rows"][0]["unadjusted_close"] == "100"
    assert history.to_dict()["declared_identity"]["security"]["security_id"] == "synthetic-security"
