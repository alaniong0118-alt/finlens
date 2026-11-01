"""Offline-only session bridge tests. Synthetic composition grants no production authority."""
from dataclasses import replace
from datetime import date
from decimal import Decimal
import hashlib
from pathlib import Path

import pytest

from app import financial_metric_engine as engine
from app import sec_evidence_adapter as sec
from app import session_financial_research as service
from app import session_sec_inline as inline
from app.research_contracts import KeyRef, SessionArtifactRef, TimePoint


CIK = "0000000001"
IDENTITY = inline.DocumentIdentity(CIK, "0000000001-25-000001", "10-K", date(2026, 2, 1),
                                   date(2025, 12, 31), "http://fasb.org/us-gaap/2025",
                                   "http://xbrl.sec.gov/dei/2025")


def document(extra="", ocf="100", capex="30", end="2025-12-31", start="2025-01-01"):
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="{sec.XHTML}" xmlns:ix="{sec.IX}" xmlns:xbrli="{sec.XBRLI}"
 xmlns:us-gaap="{IDENTITY.gaap_namespace}" xmlns:dei="{IDENTITY.dei_namespace}"
 xmlns:iso4217="{sec.ISO}" xmlns:ixt="{sec.IXT}">
<head/><body><ix:header><ix:resources><xbrli:context id="annual"><xbrli:entity>
<xbrli:identifier scheme="http://www.sec.gov/CIK">{CIK}</xbrli:identifier></xbrli:entity>
<xbrli:period><xbrli:startDate>{start}</xbrli:startDate><xbrli:endDate>{end}</xbrli:endDate></xbrli:period></xbrli:context>
<xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit></ix:resources></ix:header>
<ix:nonNumeric id="cik" name="dei:EntityCentralIndexKey" contextRef="annual">{CIK}</ix:nonNumeric>
<ix:nonNumeric id="form" name="dei:DocumentType" contextRef="annual">10-K</ix:nonNumeric>
<ix:nonNumeric id="end" name="dei:DocumentPeriodEndDate" contextRef="annual">2025-12-31</ix:nonNumeric>
<ix:nonNumeric id="amend" name="dei:AmendmentFlag" contextRef="annual">false</ix:nonNumeric>
<ix:nonFraction id="ocf" name="us-gaap:NetCashProvidedByUsedInOperatingActivities" contextRef="annual" unitRef="usd" decimals="INF">{ocf}</ix:nonFraction>
<ix:nonFraction id="capex" name="us-gaap:PaymentsToAcquirePropertyPlantAndEquipment" contextRef="annual" unitRef="usd" decimals="INF">{capex}</ix:nonFraction>
{extra}</body></html>'''.encode()


def access(data, identity=IDENTITY):
    key = KeyRef
    ref = SessionArtifactRef(entity_key=key("sec_cik", identity.cik), origin="official_sec", owner_key=key("principal", "owner"),
        session_key=key("session", "s1"), artifact_key=key("artifact", "a1"),
        source_descriptor_key=key("source_descriptor", "source"), source_revision_key=key("source_revision", "rev"),
        rights_policy_key=key("rights_policy", "rights"), admission_record_key=key("admission_record", "admission"),
        public_available_at=TimePoint.unknown(), retrieved_at=TimePoint.unknown(),
        artifact_sha256=hashlib.sha256(data).hexdigest())
    return service._ResolvedAccess(ref, 1, 1, identity, ref.source_revision_key, ref.rights_policy_key,
                                   inline.PROFILE, frozenset({"parse", "calculate", "display"}))


class Composition:
    def __init__(self, data, identity=IDENTITY):
        self.data, self.current, self.reads, self.resolves = data, access(data, identity), 0, 0
        self.final = None

    def resolve_access(self, token, session_key, session_revision, artifact_key, artifact_revision, *, cancellation):
        assert token == "synthetic-token"
        self.resolves += 1
        return self.final if self.resolves > 1 and self.final is not None else self.current

    def checkpoint(self, cancellation):
        if cancellation is not None and cancellation():
            raise service.SessionResearchFailure("cancelled")

    def read_original(self, _access):
        self.reads += 1
        return self.data


def calculate(metric="free_cash_flow", year=2025, cancellation=None):
    return service.SessionFinancialResearch().calculate("synthetic-token", KeyRef("session", "s1"), 1,
        KeyRef("artifact", "a1"), 1, metric, year, cancellation=cancellation)


@pytest.fixture
def composed(monkeypatch):
    composition = Composition(document())
    monkeypatch.setattr(service, "_server_composition", lambda: composition)
    return composition


def test_synthetic_original_to_shared_fcf_and_session_receipt(composed, monkeypatch):
    import socket
    from sqlalchemy.orm import Session
    def forbidden(*_args, **_kwargs):
        raise AssertionError("session calculation must not query or write a database")
    for method in ("execute", "scalars", "query", "get", "add", "add_all", "commit", "flush", "delete"):
        monkeypatch.setattr(Session, method, forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    result = calculate()
    assert (result.status, result.value, result.start, result.end) == ("available", Decimal("70"), date(2025, 1, 1), date(2025, 12, 31))
    assert {item.role for item in result.inputs} == {"operating_cash_flow", "capital_expenditures"}
    assert {item.fact_locator for item in result.observations} == {"ocf", "capex"}
    assert all(item.artifact == composed.current.artifact for item in result.observations)
    assert b'"fact_id"' not in result.encode()
    assert composed.reads == 1 and composed.resolves == 2


def test_default_unconfigured_denies_before_read_or_parse(monkeypatch):
    monkeypatch.setattr(service, "_server_composition", lambda: None)
    monkeypatch.setattr(inline, "inventory_original", lambda *_a, **_k: pytest.fail("parser must not run"))
    with pytest.raises(service.SessionResearchFailure, match="^admission_unavailable$"):
        calculate()


@pytest.mark.parametrize("change", ["rights", "source", "mapping", "upload", "revision"])
def test_untrusted_or_changed_admission_denies_before_read(composed, change):
    a = composed.current
    if change == "rights": composed.current = replace(a, operations=frozenset({"parse", "display"}))
    elif change == "source": composed.current = replace(a, source_revision=KeyRef("source_revision", "other"))
    elif change == "mapping": composed.current = replace(a, mapping_revision="other")
    elif change == "upload": composed.current = replace(a, artifact=replace(a.artifact, origin="user_upload"))
    else: composed.current = replace(a, artifact_revision=2)
    with pytest.raises(service.SessionResearchFailure): calculate()
    assert composed.reads == 0


def test_recheck_revocation_and_cancellation(composed):
    composed.final = replace(composed.current, operations=frozenset({"parse"}))
    with pytest.raises(service.SessionResearchFailure, match="^admission_unavailable$"): calculate()
    assert composed.resolves == 2
    composed.resolves = 0
    with pytest.raises(service.SessionResearchFailure, match="^cancelled$"): calculate(cancellation=lambda: True)


@pytest.mark.parametrize("change", ["source", "rights", "mapping", "owner", "revision"])
def test_final_recheck_rejects_changed_authority(composed, change):
    a = composed.current
    if change == "source":
        key = KeyRef("source_revision", "new")
        composed.final = replace(a, source_revision=key, artifact=replace(a.artifact, source_revision_key=key))
    elif change == "rights":
        key = KeyRef("rights_policy", "new")
        composed.final = replace(a, rights_revision=key, artifact=replace(a.artifact, rights_policy_key=key))
    elif change == "mapping": composed.final = replace(a, mapping_revision="other")
    elif change == "owner": composed.final = replace(a, artifact=replace(a.artifact, owner_key=KeyRef("principal", "other")))
    else: composed.final = replace(a, session_revision=2)
    with pytest.raises(service.SessionResearchFailure): calculate()
    assert composed.reads == 1 and composed.resolves == 2


def test_changed_bytes_deny_before_parse(composed):
    composed.data += b" "
    with pytest.raises(service.SessionResearchFailure, match="^artifact_changed$"): calculate()


@pytest.mark.parametrize("metric,value", [("operating_cash_flow", Decimal("100")), ("capital_expenditures", Decimal("30"))])
def test_individual_metrics_use_shared_engine(composed, metric, value):
    assert calculate(metric).value == value


def test_missing_year_does_not_fall_back(composed):
    with pytest.raises(service.SessionResearchFailure, match="^annual_period_unavailable_or_ambiguous$"):
        calculate(year=2024)


def test_missing_capex_preserves_missing_input_reason(monkeypatch):
    fact = b'<ix:nonFraction id="capex" name="us-gaap:PaymentsToAcquirePropertyPlantAndEquipment" contextRef="annual" unitRef="usd" decimals="INF">30</ix:nonFraction>'
    data = document().replace(fact, b'')
    comp = Composition(data); monkeypatch.setattr(service, "_server_composition", lambda: comp)
    result = calculate()
    assert result.status == "unavailable" and result.value is None
    assert "capital expenditures" in result.reason.lower()


def test_distinct_annual_intervals_do_not_combine(monkeypatch):
    context = f'<xbrli:context id="other"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">{CIK}</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:startDate>2024-12-30</xbrli:startDate><xbrli:endDate>2025-12-31</xbrli:endDate></xbrli:period></xbrli:context>'
    data = document().replace(b'</ix:resources>', context.encode() + b'</ix:resources>')
    data = data.replace(b'id="capex" name="us-gaap:PaymentsToAcquirePropertyPlantAndEquipment" contextRef="annual"',
                        b'id="capex" name="us-gaap:PaymentsToAcquirePropertyPlantAndEquipment" contextRef="other"')
    comp = Composition(data); monkeypatch.setattr(service, "_server_composition", lambda: comp)
    with pytest.raises(service.SessionResearchFailure, match="^annual_period_unavailable_or_ambiguous$"): calculate()


def test_negative_capex_is_unavailable_and_negative_operating_cash_flow_preserved(monkeypatch):
    data = document().replace(b'>100</ix:nonFraction>', b' sign="-">100</ix:nonFraction>')
    data = data.replace(b'>30</ix:nonFraction>', b' sign="-">30</ix:nonFraction>')
    comp = Composition(data); monkeypatch.setattr(service, "_server_composition", lambda: comp)
    assert calculate("operating_cash_flow").value == Decimal("-100")
    assert calculate("capital_expenditures").status == "unavailable"
    assert calculate().status == "unavailable"


@pytest.mark.parametrize("data", [b'<!DOCTYPE html><html/>', b'<html>\x00</html>', b'<?xml version="1.0" encoding="UTF-16"?><html/>',
                                  b'<!DOCTYPE html [<!ENTITY e SYSTEM "file:///does-not-exist">]><html>&e;</html>'])
def test_unsafe_original_rejected(data):
    with pytest.raises(inline.InventoryRejected): inline.inventory_original(data, IDENTITY)


def test_standard_xml_references_are_allowed_but_unknown_entities_are_rejected():
    safe = document(extra='<p>Research &amp; evidence &#160; reporting</p>')
    assert len(inline.inventory_original(safe, IDENTITY).facts) == 2
    unsafe = document(extra='<p>&unknown;</p>')
    with pytest.raises(inline.InventoryRejected): inline.inventory_original(unsafe, IDENTITY)


@pytest.mark.parametrize("limit", ["MAX_BYTES", "MAX_NODES", "MAX_DEPTH", "MAX_CONTEXTS", "MAX_UNITS", "MAX_FACTS", "MAX_ATTRIBUTES", "MAX_NAMESPACES"])
def test_inventory_limits_fail_during_preflight(monkeypatch, limit):
    monkeypatch.setattr(inline, limit, 1)
    data = document()
    if limit == "MAX_CONTEXTS":
        extra = f'<xbrli:context id="extra"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">{CIK}</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:instant>2025-12-31</xbrli:instant></xbrli:period></xbrli:context>'
        data = data.replace(b'</ix:resources>', extra.encode() + b'</ix:resources>')
    if limit == "MAX_UNITS":
        data = data.replace(b'</ix:resources>', b'<xbrli:unit id="extra"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit></ix:resources>')
    with pytest.raises(inline.InventoryRejected): inline.inventory_original(data, IDENTITY)


def test_parser_checkpoint_cancellation_is_not_swallowed():
    def cancel(): raise service.SessionResearchFailure("cancelled")
    with pytest.raises(service.SessionResearchFailure, match="^cancelled$"):
        inline.inventory_original(document(), IDENTITY, _checkpoint=cancel)


@pytest.mark.parametrize("exception_type", ["session", "ownership"])
def test_post_tree_checkpoint_preserves_original_failure_identity(monkeypatch, exception_type):
    from app.research_ownership import OwnershipFailure
    error = (service.SessionResearchFailure("cancelled") if exception_type == "session"
             else OwnershipFailure("owner_revoked"))
    parsed = False
    original = sec._xml_tree
    def tree(data):
        nonlocal parsed
        result = original(data)
        parsed = True
        return result
    def checkpoint():
        if parsed: raise error
    monkeypatch.setattr(sec, "_xml_tree", tree)
    with pytest.raises(type(error)) as caught:
        inline.inventory_original(document(), IDENTITY, _checkpoint=checkpoint)
    assert parsed and caught.value is error


def test_nonannual_conflict_is_not_silently_discarded():
    fact = '<ix:nonFraction id="quarter-one" name="us-gaap:NetCashProvidedByUsedInOperatingActivities" contextRef="quarter" unitRef="usd" decimals="INF">100</ix:nonFraction>'
    extra = fact + fact.replace('id="quarter-one"', 'id="quarter-two"').replace('>100<', '>101<')
    quarter = f'<xbrli:context id="quarter"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">{CIK}</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:startDate>2025-01-01</xbrli:startDate><xbrli:endDate>2025-03-31</xbrli:endDate></xbrli:period></xbrli:context>'
    data = document(extra=extra).replace(b'</ix:resources>', quarter.encode() + b'</ix:resources>')
    with pytest.raises(inline.InventoryRejected, match="^conflicting_observations$"):
        inline.inventory_original(data, IDENTITY)


@pytest.mark.parametrize("start,end", [("2025-10-16", "2026-01-15"), ("2027-01-01", "2027-12-31")])
def test_future_relevant_facts_rejected_even_when_requested_year_is_valid(start, end):
    control = inline.inventory_original(document(), IDENTITY)
    assert len(control.facts) == 2
    context = f'<xbrli:context id="future"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">{CIK}</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:startDate>{start}</xbrli:startDate><xbrli:endDate>{end}</xbrli:endDate></xbrli:period></xbrli:context>'
    fact = '<ix:nonFraction id="future-fact" name="us-gaap:NetCashProvidedByUsedInOperatingActivities" contextRef="future" unitRef="usd" decimals="INF">100</ix:nonFraction>'
    data = document(extra=fact).replace(b'</ix:resources>', context.encode() + b'</ix:resources>')
    with pytest.raises(inline.InventoryRejected, match="^observation_after_filing_period$"):
        inline.inventory_original(data, IDENTITY)


def test_reordered_nonannual_dimensions_conflict_but_different_members_remain_distinct():
    def context(name, order, member="SecondMember"):
        dimensions = {
            "a": '<xbrldi:explicitMember dimension="us-gaap:FirstAxis">us-gaap:FirstMember</xbrldi:explicitMember>',
            "b": f'<xbrldi:explicitMember dimension="us-gaap:SecondAxis">us-gaap:{member}</xbrldi:explicitMember>',
        }
        return f'<xbrli:context id="{name}"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">{CIK}</xbrli:identifier><xbrli:segment>{"".join(dimensions[x] for x in order)}</xbrli:segment></xbrli:entity><xbrli:period><xbrli:startDate>2025-01-01</xbrli:startDate><xbrli:endDate>2025-03-31</xbrli:endDate></xbrli:period></xbrli:context>'
    def fact(identifier, ctx, value):
        return f'<ix:nonFraction id="{identifier}" name="us-gaap:NetCashProvidedByUsedInOperatingActivities" contextRef="{ctx}" unitRef="usd" decimals="INF">{value}</ix:nonFraction>'
    def fixture(member):
        raw = document(extra=fact("first", "one", 100) + fact("second", "two", 101))
        raw = raw.replace(b'<html ', f'<html xmlns:xbrldi="{sec.XBRLDI}" '.encode(), 1)
        return raw.replace(b'</ix:resources>', (context("one", "ab") + context("two", "ba", member)).encode() + b'</ix:resources>')
    with pytest.raises(inline.InventoryRejected, match="^conflicting_observations$"):
        inline.inventory_original(fixture("SecondMember"), IDENTITY)
    facts = inline.inventory_original(fixture("DifferentMember"), IDENTITY).facts
    assert len(facts) == 4
    assert [item.context_id for item in facts if item.dimensions] == ["one", "two"]


def test_relevant_malformed_nonannual_fact_is_not_discarded():
    extra = '<ix:nonFraction id="quarter-bad" name="us-gaap:PaymentsToAcquirePropertyPlantAndEquipment" contextRef="quarter" unitRef="usd" decimals="INF">not-a-number</ix:nonFraction>'
    quarter = f'<xbrli:context id="quarter"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">{CIK}</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:startDate>2025-01-01</xbrli:startDate><xbrli:endDate>2025-03-31</xbrli:endDate></xbrli:period></xbrli:context>'
    data = document(extra=extra).replace(b'</ix:resources>', quarter.encode() + b'</ix:resources>')
    with pytest.raises(inline.InventoryRejected): inline.inventory_original(data, IDENTITY)


@pytest.mark.parametrize("wrapper", ["hidden", "narrative"])
def test_hidden_or_nested_relevant_conflict_is_in_inventory(wrapper):
    fact = '<ix:nonFraction id="extra" name="us-gaap:NetCashProvidedByUsedInOperatingActivities" contextRef="annual" unitRef="usd" decimals="INF">101</ix:nonFraction>'
    if wrapper == "hidden":
        data = document().replace(b'</ix:resources></ix:header>',
            b'</ix:resources><ix:hidden>' + fact.encode() + b'</ix:hidden></ix:header>')
    else:
        data = document(extra=f'<ix:nonNumeric id="text" name="us-gaap:CashFlowTextBlock" contextRef="annual">{fact}</ix:nonNumeric>')
    with pytest.raises(inline.InventoryRejected, match="^conflicting_observations$"):
        inline.inventory_original(data, IDENTITY)


def test_dimensional_cash_flow_is_retained_but_not_selected(monkeypatch):
    context = f'''<xbrli:context id="dim"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">{CIK}</xbrli:identifier>
<xbrli:segment><xbrldi:explicitMember dimension="us-gaap:ProductAxis">us-gaap:ProductMember</xbrldi:explicitMember></xbrli:segment></xbrli:entity>
<xbrli:period><xbrli:startDate>2025-01-01</xbrli:startDate><xbrli:endDate>2025-12-31</xbrli:endDate></xbrli:period></xbrli:context>'''
    fact = '<ix:nonFraction id="dim-fact" name="us-gaap:NetCashProvidedByUsedInOperatingActivities" contextRef="dim" unitRef="usd" decimals="INF">999</ix:nonFraction>'
    data = document(extra=fact).replace(b'<html ', f'<html xmlns:xbrldi="{sec.XBRLDI}" '.encode(), 1)
    data = data.replace(b'</ix:resources>', context.encode() + b'</ix:resources>')
    inventory = inline.inventory_original(data, IDENTITY)
    assert len(inventory.facts) == 3 and next(f for f in inventory.facts if f.fact_id == "dim-fact").dimensions
    comp = Composition(data); monkeypatch.setattr(service, "_server_composition", lambda: comp)
    assert calculate().value == Decimal("70")


@pytest.mark.parametrize("value", ["June 31, 2025", "Jun 30, 2025", "2025-12-31", "December 31, 2024"])
def test_identity_date_transform_does_not_infer_invalid_or_mismatched_dates(value):
    data = document().replace(b'name="dei:DocumentPeriodEndDate" contextRef="annual">2025-12-31',
        f'name="dei:DocumentPeriodEndDate" contextRef="annual" format="ixt:date-monthname-day-year-en">{value}'.encode())
    with pytest.raises(inline.InventoryRejected): inline.inventory_original(data, IDENTITY)


def test_nonsec_artifact_representation_does_not_grant_sec_admission(monkeypatch):
    comp = Composition(document())
    ref = replace(comp.current.artifact, entity_key=KeyRef("external_entity", "issuer-a"), origin="official_issuer")
    comp.current = replace(comp.current, artifact=ref)
    monkeypatch.setattr(service, "_server_composition", lambda: comp)
    with pytest.raises(service.SessionResearchFailure, match="^admission_unavailable$"): calculate()
    assert comp.reads == 0


def test_receipt_size_limit_fails_closed(composed):
    result = calculate()
    with pytest.raises(ValueError, match="^receipt_too_large$"):
        replace(result, alternatives=result.observations * 1000).encode()


def test_original_10q_parses_and_session_rejects_missing_annual_2026(monkeypatch):
    path = Path(r"D:\FinLens-OperatorReports\sec-original-evidence\0000320193\0000320193-26-000020\aapl-20260627.htm")
    if not path.is_file(): pytest.skip("verified external original not installed")
    data = path.read_bytes()
    assert len(data) == 1018326 and hashlib.sha256(data).hexdigest() == "ff8ff7fb32493f9ca51b5d3afa6b336adacea503f7e50e53618a6e585e7eac07"
    identity = inline.DocumentIdentity("0000320193", "0000320193-26-000020", "10-Q", date(2026, 7, 31),
        date(2026, 6, 27), "http://fasb.org/us-gaap/2025", "http://xbrl.sec.gov/dei/2025")
    inventory = inline.inventory_original(data, identity)
    assert len(inventory.facts) == 4
    assert {fact.kind for fact in inventory.facts} == {"nine_months"}
    assert not [fact for fact in inventory.facts if fact.kind == "annual" and fact.end.year == 2026]
    comp = Composition(data, identity)
    monkeypatch.setattr(service, "_server_composition", lambda: comp)
    with pytest.raises(service.SessionResearchFailure, match="^annual_period_unavailable_or_ambiguous$"):
        calculate(year=2026)
    assert comp.reads == 1


def test_engine_rejects_mixed_database_and_session_references():
    base = engine.Observation(1, "NetCashProvidedByUsedInOperatingActivities", Decimal("1"), "USD",
        date(2025, 1, 1), date(2025, 12, 31), "annual", date(2026, 2, 1), "10-K", "x", ("operating_cash_flow",))
    session = replace(base, reference=engine.SessionObservationKey("a" * 64, "ocf"))
    with pytest.raises(ValueError, match="Mixed database and session"):
        engine.FinancialMetricEngine((base, session), service._CashPermissions())
