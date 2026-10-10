"""Offline parsing and trusted-loader tests; no production policy activation."""
from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
import hashlib
import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import revenue_scope_authorizations as auth
from app import sec_evidence_adapter as adapter
from app.financial_metrics_service import FinancialMetrics, load_financial_metrics
from app.models import FinancialFact

CIK = "0000000001"
ACCESSION = "0000000001-25-000001"
CUSTOMER = "RevenueFromContractWithCustomerExcludingAssessedTax"
COMPANY = SimpleNamespace(cik=CIK, ticker="TEST", name="Synthetic issuer")
XML = f'''<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="{adapter.XHTML}" xmlns:ix="{adapter.IX}" xmlns:xbrli="{adapter.XBRLI}"
 xmlns:xbrldi="{adapter.XBRLDI}" xmlns:us-gaap="http://fasb.org/us-gaap/2025"
 xmlns:dei="http://xbrl.sec.gov/dei/2025" xmlns:iso4217="{adapter.ISO}" xmlns:ixt="{adapter.IXT}">
<head/><body><h1>Synthetic parser fixture only</h1><ix:header><ix:resources>
<xbrli:context id="c-q"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">{CIK}</xbrli:identifier></xbrli:entity>
<xbrli:period><xbrli:startDate>2025-01-01</xbrli:startDate><xbrli:endDate>2025-03-31</xbrli:endDate></xbrli:period></xbrli:context>
<xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>
</ix:resources></ix:header>
<ix:nonNumeric id="dei-cik" name="dei:EntityCentralIndexKey" contextRef="c-q">{CIK}</ix:nonNumeric>
<ix:nonNumeric id="dei-form" name="dei:DocumentType" contextRef="c-q">10-Q</ix:nonNumeric>
<ix:nonNumeric id="dei-end" name="dei:DocumentPeriodEndDate" contextRef="c-q">2025-03-31</ix:nonNumeric>
<ix:nonNumeric id="dei-amend" name="dei:AmendmentFlag" contextRef="c-q">false</ix:nonNumeric>
<table><tr><td>Consolidated net sales</td><td><ix:nonFraction id="f-rev" name="us-gaap:{CUSTOMER}"
 contextRef="c-q" unitRef="usd" decimals="-6" scale="6" format="ixt:num-dot-decimal">100</ix:nonFraction></td></tr>
<tr><td>Consolidated net income</td><td><ix:nonFraction id="f-ni" name="us-gaap:NetIncomeLoss"
 contextRef="c-q" unitRef="usd" decimals="-6" scale="6" format="ixt:num-dot-decimal">20</ix:nonFraction></td></tr></table>
</body></html>'''


def sha(data):
    return hashlib.sha256(data).hexdigest()


def pin_for(data, **changes):
    pin = adapter.ArtifactPin(CIK, ACCESSION, "fixture.htm", "10-Q", date(2025, 5, 1),
        date(2025, 3, 31), sha(data), len(data), "capture.json", "0" * 64,
        "http://fasb.org/us-gaap/2025", "http://xbrl.sec.gov/dei/2025")
    return replace(pin, **changes)


def parse(xml=XML, **changes):
    data = xml.encode()
    return adapter._parse_artifact(pin_for(data, **changes), data)


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    # Assert shipped inactivity BEFORE any synthetic policy/registry monkeypatch.
    for name in ("REVENUE_SELECTION_AUTHORIZATIONS", "DENOMINATOR_AUTHORIZATIONS", "AUTHORIZATION_WITHDRAWALS"):
        assert getattr(auth, name) == ()
    assert adapter.PRODUCTION_EVIDENCE_POLICIES == ()
    from app.database import engine
    import socket
    monkeypatch.setattr(engine, "connect", lambda *a, **k: pytest.fail("Database access forbidden"))
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: pytest.fail("Network access forbidden"))


def scenario(tmp_path, xml=XML):
    root = tmp_path / "trusted-store"
    directory = root / CIK / ACCESSION
    directory.mkdir(parents=True)
    artifact = directory / "fixture.htm"
    data = xml.encode()
    artifact.write_bytes(data)
    pin = pin_for(data)
    receipt = dict(source_url=f"https://www.sec.gov/Archives/edgar/data/1/{ACCESSION.replace('-', '')}/fixture.htm",
        cik=CIK, accession=ACCESSION, filename=pin.filename, http_status=200,
        sha256=pin.sha256, byte_length=pin.byte_length, redirects_allowed=False,
        artifact_path=str(artifact), retrieval_started_at_utc="2025-05-01T12:00:00+00:00",
        retrieval_completed_at_utc="2025-05-01T12:00:01+00:00", response_metadata={"content-type": "text/html"})
    receipt["response_url"] = receipt["source_url"]
    receipt_bytes = json.dumps(receipt).encode()
    receipt_path = directory / pin.receipt_filename
    receipt_path.write_bytes(receipt_bytes)
    pin = replace(pin, receipt_sha256=sha(receipt_bytes))
    parsed = adapter._parse_artifact(pin, data)
    a, b = parsed.statement_ranges[0]
    reviews = tuple(adapter.ObservationReview(o.identity, pin.filename, o.fact_id, o.context_id,
        0, sha(parsed.document_text[a:b].encode()),
        "consolidated_revenue" if o.identity.concept == CUSTOMER else "consolidated_net_income",
        "Synthetic reviewed statement location") for o in parsed.observations)
    state = SimpleNamespace(company_cik=CIK, data_version=1, facts_version=1, evidence_version=1)
    publication = SimpleNamespace(company_cik=CIK, accession_number=ACCESSION, form=pin.form, filed=pin.filed,
        filename=pin.filename, chunk_count=1, content_digest="c" * 64, configuration="parser-v1", data_version=1)
    snapshot = adapter.snapshot_digest(state, [publication])
    ref = auth.ApprovalRef("denominator:net_margin", "synthetic-only", 1)
    policy = adapter.EvidencePolicy(ref, "pending", snapshot, (pin,), reviews)
    evidence = tuple(auth.SourceEvidence(o.identity, pin.filename, parsed.document_text,
        adapter._statement_location(policy, r), a, b, o.context_id, (), r.economic_scope)
        for o, r in zip(parsed.observations, reviews))
    bindings = tuple(auth.EvidenceBinding(e.identity, e.fingerprint()) for e in evidence)
    record = auth.DenominatorAuthorization(ref, "net_margin", bindings[0], bindings[1], bindings,
        "Synthetic fixture consolidated scope review")
    policy = replace(policy, approval_sha256=adapter.approval_digest(record))
    publications = [publication]
    facts = [FinancialFact(id=i, company_cik=o.identity.cik, metric=o.identity.concept,
        source="SEC Company Facts API: " + o.identity.concept, value=o.identity.value, unit="USD",
        period_start=o.identity.start, period_end=o.identity.end, period_type="quarter", fiscal_year=2025,
        fiscal_period="Q1", frame=None, accession_number=o.identity.accession, form=o.identity.form,
        filed=o.identity.filed, created_at=datetime(2025, 5, 1)) for i, o in enumerate(parsed.observations, 1)]
    session = SimpleNamespace(get_bind=lambda: SimpleNamespace(dialect=SimpleNamespace(name="postgresql")),
        scalar=lambda stmt: "repeatable read" if str(stmt) == "SHOW transaction_isolation" else "on",
        get=lambda *a: state, scalars=lambda *a: publications)
    return SimpleNamespace(root=root, artifact=artifact, receipt_path=receipt_path, receipt=receipt, pin=pin,
        policy=policy, record=record, facts=facts, session=session, state=state, publications=publications,
        raw=tuple(o.identity for o in parsed.observations), snapshot=snapshot, evidence=evidence)


def verify(s, **changes):
    inputs = dict(policy=s.policy, record=s.record, raw=s.raw, root=s.root,
                  snapshot=s.snapshot, publications=s.publications)
    inputs.update(changes)
    return adapter._verify_policy(**inputs)


def install_test_policy(monkeypatch, s):
    # Only tests replace trusted server constants; there is no caller switch.
    monkeypatch.setattr(auth, "DENOMINATOR_AUTHORIZATIONS", (s.record,))
    monkeypatch.setattr(adapter, "PRODUCTION_EVIDENCE_POLICIES", (s.policy,))
    monkeypatch.setenv("FINLENS_SEC_ORIGINAL_STORE", str(s.root))


def repin_scenario(s, xml=XML, ref=None):
    """Repin test-only bytes without asking the parser to approve malformed XML.

    The ordinary observations remain unchanged. Hashes, receipt, statement span,
    policy and authorization fingerprints all match the adversarial document.
    """
    data = xml.encode()
    s.artifact.write_bytes(data)
    pin = replace(s.pin, sha256=sha(data), byte_length=len(data))
    receipt = dict(s.receipt, sha256=pin.sha256, byte_length=pin.byte_length)
    receipt_bytes = json.dumps(receipt).encode()
    s.receipt_path.write_bytes(receipt_bytes)
    pin = replace(pin, receipt_sha256=sha(receipt_bytes))
    a, b = xml.index('<table>'), xml.index('</table>') + len('</table>')
    reviews = tuple(replace(r, statement_sha256=sha(xml[a:b].encode())) for r in s.policy.observations)
    ref = ref or s.record.ref
    policy = replace(s.policy, ref=ref, artifacts=(pin,), observations=reviews, approval_sha256="pending")
    evidence = tuple(replace(e, document_text=xml, statement_start=a, statement_end=b,
                            statement_location=adapter._statement_location(policy, r))
                     for e, r in zip(s.evidence, reviews))
    bindings = tuple(auth.EvidenceBinding(e.identity, e.fingerprint()) for e in evidence)
    record = replace(s.record, ref=ref, revenue=bindings[0], numerator=bindings[1], candidates=bindings)
    s.pin, s.receipt, s.record = pin, receipt, record
    s.policy, s.evidence = replace(policy, approval_sha256=adapter.approval_digest(record)), evidence
    assert sha(s.artifact.read_bytes()) == s.pin.sha256
    adapter._validate_receipt(s.pin, s.receipt_path.read_bytes(), s.artifact)
    return s


def assert_parser_rejected_by_loader(monkeypatch, s, reason):
    install_test_policy(monkeypatch, s)
    failures = []
    parse_artifact = adapter._parse_artifact

    def checked_parse(*args):
        try:
            return parse_artifact(*args)
        except adapter.EvidenceRejected as error:
            failures.append(str(error))
            raise

    monkeypatch.setattr(adapter, "_parse_artifact", checked_parse)
    assert adapter.load_production_evidence(s.session, CIK, s.facts) == ()
    assert failures == [reason]  # Not a stale hash, receipt or manifest rejection.


@pytest.mark.parametrize("namespace", ["http://www.xbrl.org/2008/inlineXBRL", "http://www.xbrl.org/2011/inlineXBRL", "urn:unsupported-inline"])
@pytest.mark.parametrize("concept,value", [(CUSTOMER, "101"), ("NetIncomeLoss", "21")])
def test_loader_rejects_conflicting_unsupported_inline_facts_with_matching_pins(tmp_path, monkeypatch, namespace, concept, value):
    extra = f'<old:nonFraction xmlns:old="{namespace}" id="conflict" name="us-gaap:{concept}" contextRef="c-q" unitRef="usd" decimals="-6" scale="6" format="ixt:num-dot-decimal">{value}</old:nonFraction>'
    s = repin_scenario(scenario(tmp_path), XML.replace('</body>', extra + '</body>'))
    assert_parser_rejected_by_loader(monkeypatch, s, "unsupported_inline_namespace")


@pytest.mark.parametrize("wrapper,reason", [
    ('tuple', "unsupported_inline_construct"), ('continuation', "unsupported_inline_ancestry"),
    ('hidden', "unsupported_inline_ancestry"), ('resources', "unsupported_inline_ancestry"),
    ('nonNumeric', "unsupported_inline_ancestry"),
])
def test_loader_rejects_unsupported_inline_ancestry_with_matching_pins(tmp_path, monkeypatch, wrapper, reason):
    attrs = ' id="wrapper" name="us-gaap:DisclosureNarrative" contextRef="c-q"' if wrapper == 'nonNumeric' else ' id="wrapper"'
    xml = XML.replace('<table>', f'<ix:{wrapper}{attrs}><table>').replace('</table>', f'</table></ix:{wrapper}>')
    s = repin_scenario(scenario(tmp_path), xml)
    assert_parser_rejected_by_loader(monkeypatch, s, reason)


def test_loader_rejects_empty_tuple_outside_reviewed_statement(tmp_path, monkeypatch):
    s = repin_scenario(scenario(tmp_path), XML.replace('</body>', '<ix:tuple id="unreviewed" name="us-gaap:DisclosureTuple"/></body>'))
    assert_parser_rejected_by_loader(monkeypatch, s, "unsupported_inline_construct")


@pytest.mark.parametrize("container", ["nonNumeric", "continuation"])
def test_loader_rejects_invalid_narrative_container_attributes(tmp_path, monkeypatch, container):
    xml = XML.replace('<html ', '<html xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" ', 1)
    xml = xml.replace('<table>', '<ix:nonNumeric id="narrative" name="us-gaap:DisclosureTextBlock" contextRef="c-q"><ix:continuation id="narrative-continuation"><table>')
    xml = xml.replace('</table>', '</table></ix:continuation></ix:nonNumeric>')
    marker = 'id="narrative"' if container == "nonNumeric" else 'id="narrative-continuation"'
    s = repin_scenario(scenario(tmp_path), xml.replace(marker, marker + ' xsi:nil="true"'))
    assert_parser_rejected_by_loader(monkeypatch, s, "unsupported_inline_ancestry")


def test_loader_does_not_confuse_xhtml_header_with_inline_header(tmp_path, monkeypatch):
    xml = XML.replace('<table>', '<header><table>').replace('</table>', '</table></header>')
    s = repin_scenario(scenario(tmp_path), xml)
    install_test_policy(monkeypatch, s)
    assert set(adapter.load_production_evidence(s.session, CIK, s.facts)) == set(s.evidence)


@pytest.mark.parametrize("fact_id", ["dei-cik", "dei-form", "dei-end", "dei-amend"])
@pytest.mark.parametrize("attribute", ['xsi:nil="true"', 'xsi:nil="1"', 'xsi="true"'])
def test_loader_rejects_invalid_dei_identity_attributes_with_matching_pins(tmp_path, monkeypatch, fact_id, attribute):
    xml = XML.replace('<html ', '<html xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" ', 1)
    xml = xml.replace(f'id="{fact_id}"', f'id="{fact_id}" {attribute}')
    s = repin_scenario(scenario(tmp_path), xml)
    assert_parser_rejected_by_loader(monkeypatch, s, "unsupported_identity_attributes")


@pytest.mark.parametrize("fact_id", ["dei-cik", "dei-form", "dei-end", "dei-amend"])
@pytest.mark.parametrize("target", ["", "other-instance"])
def test_loader_rejects_targeted_dei_identity_with_matching_pins(tmp_path, monkeypatch, fact_id, target):
    xml = XML.replace(f'id="{fact_id}"', f'id="{fact_id}" target="{target}"')
    s = repin_scenario(scenario(tmp_path), xml)
    assert_parser_rejected_by_loader(monkeypatch, s, "unsupported_inline_target")


@pytest.mark.parametrize("target", ["", "other-instance"])
def test_loader_rejects_targeted_resources_with_matching_pins(tmp_path, monkeypatch, target):
    s = repin_scenario(scenario(tmp_path), XML.replace('<ix:resources>', f'<ix:resources target="{target}">'))
    assert_parser_rejected_by_loader(monkeypatch, s, "unsupported_inline_target")


@pytest.mark.parametrize("resource", ["context", "unit"])
def test_loader_rejects_observation_resources_outside_inline_header(tmp_path, monkeypatch, resource):
    a = XML.index(f'<xbrli:{resource} ')
    b = XML.index(f'</xbrli:{resource}>') + len(f'</xbrli:{resource}>')
    moved = XML[a:b]
    xml = (XML[:a] + XML[b:]).replace('</body>', moved + '</body>')
    s = repin_scenario(scenario(tmp_path), xml)
    assert_parser_rejected_by_loader(monkeypatch, s, "unsupported_inline_ancestry")


def test_loader_rejects_dei_inside_narrative_textblock(tmp_path, monkeypatch):
    start = '<ix:nonNumeric id="dei-cik"'
    xml = XML.replace(start, '<ix:nonNumeric id="narrative" name="us-gaap:DisclosureTextBlock" contextRef="c-q">' + start)
    xml = xml.replace(f'>{CIK}</ix:nonNumeric>', f'>{CIK}</ix:nonNumeric></ix:nonNumeric>')
    s = repin_scenario(scenario(tmp_path), xml)
    assert_parser_rejected_by_loader(monkeypatch, s, "unsupported_inline_ancestry")


@pytest.mark.parametrize("concept,value", [(CUSTOMER, "101"), ("NetIncomeLoss", "21")])
def test_nested_narrative_conflicts_remain_in_complete_loader_manifest(tmp_path, monkeypatch, concept, value):
    extra = f'<ix:nonNumeric id="narrative" name="us-gaap:DisclosureTextBlock" contextRef="c-q"><ix:continuation id="narrative-continuation"><ix:nonFraction id="nested-conflict" name="us-gaap:{concept}" contextRef="c-q" unitRef="usd" decimals="-6" scale="6" format="ixt:num-dot-decimal">{value}</ix:nonFraction></ix:continuation></ix:nonNumeric>'
    s = repin_scenario(scenario(tmp_path), XML.replace('</body>', extra + '</body>'))
    assert any(o.fact_id == "nested-conflict" for o in adapter._parse_artifact(s.pin, s.artifact.read_bytes()).observations)
    install_test_policy(monkeypatch, s)
    failures = []
    verify_policy = adapter._verify_policy

    def checked_verify(*args):
        try:
            return verify_policy(*args)
        except adapter.EvidenceRejected as error:
            failures.append(str(error))
            raise

    monkeypatch.setattr(adapter, "_verify_policy", checked_verify)
    assert adapter.load_production_evidence(s.session, CIK, s.facts) == ()
    assert failures == ["original_candidate_manifest_changed"]


def withdrawn_period_record(s, ref):
    bindings = tuple(replace(b, identity=replace(b.identity, start=date(2024,1,1), end=date(2024,3,31),
        accession="0000000001-24-000001", filed=date(2024,5,1))) for b in s.record.candidates)
    return replace(s.record, ref=ref, revenue=bindings[0], numerator=bindings[1], candidates=bindings)


@pytest.mark.parametrize("reverse", [False, True])
def test_loader_keeps_active_evidence_with_unrelated_fully_withdrawn_scope(tmp_path, monkeypatch, reverse):
    s = scenario(tmp_path)
    install_test_policy(monkeypatch, s)
    retired = withdrawn_period_record(s, auth.ApprovalRef("denominator:net_margin", "retired-period", 1))
    records = (s.record, retired)
    monkeypatch.setattr(auth, "DENOMINATOR_AUTHORIZATIONS", records[::-1] if reverse else records)
    monkeypatch.setattr(auth, "AUTHORIZATION_WITHDRAWALS", (auth.AuthorizationWithdrawal(retired.ref, "revoked", "retired review"),))
    # No old-period policy/artifact exists; only active evidence needs verification.
    assert set(adapter.load_production_evidence(s.session, CIK, s.facts)) == set(s.evidence)


@pytest.mark.parametrize("reverse", [False, True])
def test_loader_accepts_explicit_supersession_to_different_period(tmp_path, monkeypatch, reverse):
    s = scenario(tmp_path)
    predecessor = withdrawn_period_record(s, s.record.ref)
    s = repin_scenario(s, ref=replace(s.record.ref, version=2))
    install_test_policy(monkeypatch, s)
    records = (predecessor, s.record)
    monkeypatch.setattr(auth, "DENOMINATOR_AUTHORIZATIONS", records[::-1] if reverse else records)
    monkeypatch.setattr(auth, "AUTHORIZATION_WITHDRAWALS", (auth.AuthorizationWithdrawal(predecessor.ref, "superseded", "moved reviewed period", s.record.ref),))
    assert set(adapter.load_production_evidence(s.session, CIK, s.facts)) == set(s.evidence)


@pytest.mark.parametrize("superseded", [False, True])
def test_withdrawn_moved_successor_never_revives_predecessor(tmp_path, monkeypatch, superseded):
    s = scenario(tmp_path)
    predecessor = withdrawn_period_record(s, s.record.ref)
    s = repin_scenario(s, ref=replace(s.record.ref, version=2))
    install_test_policy(monkeypatch, s)
    monkeypatch.setattr(auth, "DENOMINATOR_AUTHORIZATIONS", (s.record, predecessor))
    withdrawals = (auth.AuthorizationWithdrawal(s.record.ref, "revoked", "successor withdrawn"),)
    if superseded:
        withdrawals += (auth.AuthorizationWithdrawal(predecessor.ref, "superseded", "moved scope", s.record.ref),)
    monkeypatch.setattr(auth, "AUTHORIZATION_WITHDRAWALS", withdrawals)
    checked = []
    monkeypatch.setattr(adapter, "_verify_policy", lambda *a: checked.append(a))
    assert adapter.load_production_evidence(s.session, CIK, s.facts) == ()
    assert checked == []  # Neither scope may produce evidence, irrespective of order.


@pytest.mark.parametrize("invalid", ["overlap", "version_conflict", "missing_supersession"])
def test_loader_still_rejects_invalid_active_lineage(tmp_path, monkeypatch, invalid):
    s = scenario(tmp_path)
    install_test_policy(monkeypatch, s)
    if invalid == "overlap":
        other = replace(s.record, ref=replace(s.record.ref, approval_id="overlap"))
    elif invalid == "version_conflict":
        other = replace(s.record, reviewed_scope="contradictory reuse of version")
    else:
        other = withdrawn_period_record(s, replace(s.record.ref, version=2))
    monkeypatch.setattr(auth, "DENOMINATOR_AUTHORIZATIONS", (s.record, other))
    assert adapter.load_production_evidence(s.session, CIK, s.facts) == ()


def test_valid_parser_has_independent_exact_values_and_statement_offsets():
    parsed = parse()
    assert (parsed.inline_fact_count, parsed.context_count, parsed.unit_count) == (6, 1, 1)
    assert [o.identity.value for o in parsed.observations] == [Decimal("100000000"), Decimal("20000000")]
    assert all(o.context_id == "c-q" and o.dimensions == () and o.table_ordinal == 0 for o in parsed.observations)
    a, b = parsed.statement_ranges[0]
    assert parsed.document_text[a:b].startswith("<table>") and parsed.document_text[a:b].endswith("</table>")


@pytest.mark.parametrize("shown,scale,sign,expected", [
    ("1,234.56789", "6", None, "1234567890"), ("12.34", "-2", "-", "-0.1234"),
    ("123456789012345678901234567890.1234", "0", None, "123456789012345678901234567890.1234")])
def test_exact_numeric_transform(shown, scale, sign, expected):
    xml = XML.replace('scale="6"', f'scale="{scale}"', 1).replace('>100</ix:nonFraction>', f'>{shown}</ix:nonFraction>')
    if sign:
        xml = xml.replace('id="f-rev"', f'id="f-rev" sign="{sign}"')
    assert parse(xml).observations[0].identity.value == Decimal(expected)


@pytest.mark.parametrize("old,new,reason", [
    ('>100</ix:nonFraction>', '>1,00</ix:nonFraction>', "invalid_numeric_text"),
    ('scale="6"', 'scale="99"', "unsupported_scale"),
    ('id="f-rev"', 'id="f-rev" sign="+"', "unsupported_sign"),
    ('ixt:num-dot-decimal', 'ixt:num-comma-decimal', "unsupported_numeric_transform"),
    ('unitRef="usd"', 'unitRef="missing"', "unit_mismatch"),
    ('iso4217:USD', 'iso4217:EUR', "unit_mismatch"),
    ('xmlns:iso4217="' + adapter.ISO + '"', 'xmlns:iso4217="urn:fake"', "unit_mismatch"),
    ('contextRef="c-q" unitRef="usd"', 'contextRef="missing" unitRef="usd"', "missing_observation_context"),
    ('scheme="http://www.sec.gov/CIK"', 'scheme="urn:fake"', "invalid_context_entity"),
    ('2025-03-31</xbrli:endDate>', '2025-03-30</xbrli:endDate>', "filing_context_mismatch"),
    ('id="f-ni"', 'id="f-rev"', "ambiguous_xml_id"),
    ('xmlns:us-gaap="http://fasb.org/us-gaap/2025"', 'xmlns:us-gaap="urn:fake"', "concept_namespace_mismatch"),
    ('id="f-rev"', 'id="f-rev" continuedAt="other"', "unsupported_numeric_fact"),
    ('>100</ix:nonFraction>', '><span>100</span></ix:nonFraction>', "unsupported_numeric_fact"),
    ('xmlns:xbrldi="' + adapter.XBRLDI + '"', 'xmlns:xbrldi="' + adapter.XBRLDI + '" xmlns:fake="urn:fake"', None),
])
def test_supported_markup_is_strict(old, new, reason):
    if reason is None:
        assert parse(XML.replace(old, new)).observations
    else:
        with pytest.raises(adapter.EvidenceRejected, match=reason):
            parse(XML.replace(old, new))


@pytest.mark.parametrize("changes", [dict(cik="0000000002"), dict(form="10-K"),
    dict(period_end=date(2025, 4, 1)), dict(sha256="0" * 64), dict(byte_length=1)])
def test_wrong_pin_identity_or_bytes_fail(changes):
    with pytest.raises(adapter.EvidenceRejected):
        parse(**changes)


@pytest.mark.parametrize("doctype", ['<!DOCTYPE html [<!ENTITY injected "100">]>',
    '<!DOCTYPE html SYSTEM "https://example.invalid/schema.dtd">'])
def test_no_dtd_entity_or_network_resolution(doctype):
    with pytest.raises(adapter.EvidenceRejected, match="unsafe_xml"):
        parse(XML.replace('<html ', doctype + '<html ', 1))


def test_utf16_cannot_bypass_entity_guard():
    data = XML.replace('encoding="UTF-8"', 'encoding="UTF-16"').encode('utf-16')
    with pytest.raises(adapter.EvidenceRejected, match="unsupported_xml_encoding"):
        adapter._parse_artifact(pin_for(data), data)


def test_dimensioned_fact_cannot_be_consolidated_evidence(tmp_path):
    segment = '<xbrli:segment><xbrldi:explicitMember dimension="us-gaap:StatementBusinessSegmentsAxis">us-gaap:ProductMember</xbrldi:explicitMember></xbrli:segment>'
    context = XML[XML.index('<xbrli:context'):XML.index('</xbrli:context>')+len('</xbrli:context>')]
    dimensioned = context.replace('id="c-q"', 'id="c-dim"').replace('</xbrli:entity>', segment + '</xbrli:entity>')
    xml = XML.replace('</ix:resources>', dimensioned + '</ix:resources>').replace('contextRef="c-q" unitRef="usd"', 'contextRef="c-dim" unitRef="usd"')
    parsed = parse(xml)
    assert all(o.dimensions for o in parsed.observations)
    s = scenario(tmp_path, xml)
    with pytest.raises(adapter.EvidenceRejected, match="original_candidate_manifest_changed"):
        verify(s)


def test_verified_policy_feeds_existing_evaluator(tmp_path, monkeypatch):
    s = scenario(tmp_path)
    assert verify(s) == s.evidence
    install_test_policy(monkeypatch, s)
    proofs = adapter.load_production_evidence(s.session, CIK, s.facts)
    assert set(proofs) == set(s.evidence)
    result = FinancialMetrics(COMPANY, s.facts, authorization_evidence=proofs).summary()
    assert result.metrics["net_margin"].value == Decimal("0.2")
    assert result.metrics["net_margin"].scope_authorization.permission == "denominator:net_margin"


@pytest.mark.parametrize("field,value", [("snapshot_sha256", "0" * 64), ("approval_sha256", "0" * 64),
    ("parser_version", "other"), ("ref", auth.ApprovalRef("denominator:net_margin", "synthetic-only", 2)),
    ("observations", ())])
def test_changed_or_missing_policy_fails(tmp_path, field, value):
    s = scenario(tmp_path)
    with pytest.raises(adapter.EvidenceRejected):
        verify(s, policy=replace(s.policy, **{field: value}))


@pytest.mark.parametrize("field,value", [("fact_id", "absent"), ("context_id", "absent"),
    ("table_ordinal", 1), ("statement_sha256", "0" * 64), ("economic_scope", "component_revenue"),
    ("review_note", "")])
def test_wrong_reviewed_statement_or_scope_fails(tmp_path, field, value):
    s = scenario(tmp_path)
    changed = replace(s.policy.observations[0], **{field: value})
    with pytest.raises(adapter.EvidenceRejected):
        verify(s, policy=replace(s.policy, observations=(changed, s.policy.observations[1])))


@pytest.mark.parametrize("extra", ["missing", "same_value_amendment", "conflict", "changed_start"])
def test_raw_manifest_checks_every_candidate(tmp_path, extra):
    s = scenario(tmp_path)
    raw = s.raw
    if extra == "missing":
        raw = raw[:1]
    else:
        changes = {"same_value_amendment": dict(accession="0000000001-25-000002", form="10-Q/A", filed=date(2025,5,2)),
                   "conflict": dict(value=Decimal("1")), "changed_start": dict(start=date(2025,1,2))}[extra]
        raw += (replace(raw[0], **changes),)
    with pytest.raises(adapter.EvidenceRejected, match="candidate_manifest_changed"):
        verify(s, raw=raw)


def test_identical_database_duplicates_are_not_new_candidates(tmp_path):
    s = scenario(tmp_path)
    assert verify(s, raw=s.raw + s.raw) == s.evidence


def test_original_manifest_detects_fact_not_present_in_database_manifest(tmp_path):
    extra = f'<table><tr><td><ix:nonFraction id="extra" name="us-gaap:SalesRevenueNet" contextRef="c-q" unitRef="usd" decimals="-6" scale="6" format="ixt:num-dot-decimal">100</ix:nonFraction></td></tr></table>'
    s = scenario(tmp_path, XML.replace('</body>', extra + '</body>'))
    record = replace(s.record, candidates=s.record.candidates[:2])
    policy = replace(s.policy, observations=s.policy.observations[:2], approval_sha256=adapter.approval_digest(record))
    with pytest.raises(adapter.EvidenceRejected, match="original_candidate_manifest_changed"):
        verify(s, raw=s.raw[:2], record=record, policy=policy)


def test_repinning_receipt_without_new_approval_fingerprint_is_rejected(tmp_path):
    s = scenario(tmp_path)
    # An innocuous receipt metadata edit still changes the independently pinned
    # policy. The old authorization fingerprints cannot authorize that policy.
    data = json.dumps(dict(s.receipt, operator_note="new capture review")).encode()
    s.receipt_path.write_bytes(data)
    pin = replace(s.pin, receipt_sha256=sha(data))
    with pytest.raises(adapter.EvidenceRejected, match="missing_or_changed_context_evidence"):
        verify(s, policy=replace(s.policy, artifacts=(pin,)))


def test_wrong_filed_date_cannot_be_inferred_from_http_headers(tmp_path):
    s = scenario(tmp_path)
    bad = replace(s.pin, filed=date(2025,5,2))
    with pytest.raises(adapter.EvidenceRejected, match="publication_identity_mismatch"):
        verify(s, policy=replace(s.policy, artifacts=(bad,)))


@pytest.mark.parametrize("change", ["artifact", "receipt", "missing_artifact", "missing_receipt", "new_original"])
def test_missing_changed_or_new_local_evidence_fails_closed(tmp_path, monkeypatch, change):
    s = scenario(tmp_path)
    install_test_policy(monkeypatch, s)
    if change == "artifact": s.artifact.write_bytes(b"Access denied")
    if change == "receipt": s.receipt_path.write_bytes(b"{}")
    if change == "missing_artifact": s.artifact.unlink()
    if change == "missing_receipt": s.receipt_path.unlink()
    if change == "new_original": (s.artifact.parent / "new.htm").write_bytes(b"unreviewed")
    assert adapter.load_production_evidence(s.session, CIK, s.facts) == ()


@pytest.mark.parametrize("field,value", [("accession", "0000000001-25-000002"), ("cik", "0000000002"),
    ("http_status", 403), ("source_url", "https://unofficial.invalid/fixture.htm"),
    ("response_url", "https://unofficial.invalid/fixture.htm"), ("redirects_allowed", True)])
def test_even_repinned_receipt_must_match_official_capture_identity(tmp_path, field, value):
    s = scenario(tmp_path)
    receipt = dict(s.receipt, **{field: value})
    data = json.dumps(receipt).encode()
    with pytest.raises(adapter.EvidenceRejected):
        adapter._validate_receipt(replace(s.pin, receipt_sha256=sha(data)), data, s.artifact)


@pytest.mark.parametrize("field", ["data_version", "facts_version", "evidence_version"])
def test_changed_database_version_revokes_evidence(tmp_path, monkeypatch, field):
    s = scenario(tmp_path)
    install_test_policy(monkeypatch, s)
    setattr(s.state, field, 2)
    assert adapter.load_production_evidence(s.session, CIK, s.facts) == ()


def test_new_publication_even_without_ingested_facts_invalidates_snapshot(tmp_path, monkeypatch):
    s = scenario(tmp_path)
    install_test_policy(monkeypatch, s)
    s.publications.append(SimpleNamespace(**dict(vars(s.publications[0]), accession_number="0000000001-25-000002", form="10-Q/A")))
    assert adapter.load_production_evidence(s.session, CIK, s.facts) == ()


def test_read_only_repeatable_snapshot_required(tmp_path, monkeypatch):
    s = scenario(tmp_path)
    install_test_policy(monkeypatch, s)
    s.session.scalar = lambda *a: "read committed"
    assert adapter.load_production_evidence(s.session, CIK, s.facts) == ()


def test_revocation_and_permissions_stay_in_evaluator(tmp_path, monkeypatch):
    s = scenario(tmp_path)
    install_test_policy(monkeypatch, s)
    monkeypatch.setattr(auth, "AUTHORIZATION_WITHDRAWALS", (auth.AuthorizationWithdrawal(s.record.ref, "revoked", "test withdrawal"),))
    assert adapter.load_production_evidence(s.session, CIK, s.facts) == ()
    assert not auth.authorize_selection(s.raw[0].period_scope(), s.raw, s.evidence).accepted


def test_new_version_requires_explicit_supersession_and_renewed_fingerprints(tmp_path, monkeypatch):
    s = scenario(tmp_path)
    install_test_policy(monkeypatch, s)
    ref = replace(s.record.ref, version=2)
    policy = replace(s.policy, ref=ref, approval_sha256="pending")
    evidence = tuple(replace(e, statement_location=adapter._statement_location(policy, r))
                     for e, r in zip(s.evidence, s.policy.observations))
    bindings = tuple(auth.EvidenceBinding(e.identity, e.fingerprint()) for e in evidence)
    record = replace(s.record, ref=ref, revenue=bindings[0], numerator=bindings[1], candidates=bindings)
    policy = replace(policy, approval_sha256=adapter.approval_digest(record))
    monkeypatch.setattr(auth, "DENOMINATOR_AUTHORIZATIONS", (s.record, record))
    monkeypatch.setattr(adapter, "PRODUCTION_EVIDENCE_POLICIES", (policy,))
    assert adapter.load_production_evidence(s.session, CIK, s.facts) == ()
    monkeypatch.setattr(auth, "AUTHORIZATION_WITHDRAWALS", (auth.AuthorizationWithdrawal(s.record.ref, "superseded", "test successor", ref),))
    assert set(adapter.load_production_evidence(s.session, CIK, s.facts)) == set(evidence)


def test_no_partial_proofs_when_another_applicable_policy_fails(tmp_path, monkeypatch):
    s = scenario(tmp_path)
    install_test_policy(monkeypatch, s)
    shifted = replace(s.record.revenue.identity, start=date(2025,1,2))
    another = replace(s.record, ref=auth.ApprovalRef("denominator:net_margin", "unreviewed", 1),
                      revenue=replace(s.record.revenue, identity=shifted))
    monkeypatch.setattr(auth, "DENOMINATOR_AUTHORIZATIONS", (s.record, another))
    assert adapter.load_production_evidence(s.session, CIK, s.facts) == ()


def test_other_company_does_not_receive_verified_proofs(tmp_path, monkeypatch):
    s = scenario(tmp_path)
    install_test_policy(monkeypatch, s)
    assert adapter.load_production_evidence(SimpleNamespace(), "0000000002", s.facts) == ()


def test_malformed_receipt_is_rejected_even_if_hash_repinned(tmp_path):
    s = scenario(tmp_path)
    for data in (b'[]', b'{"response_metadata": null}', b'{"source_url":"first","source_url":"second"}'):
        with pytest.raises(adapter.EvidenceRejected):
            adapter._validate_receipt(replace(s.pin, receipt_sha256=sha(data)), data, s.artifact)


def test_namespace_rebinding_cannot_redefine_fact_meaning():
    xml = XML.replace('id="f-rev"', 'id="f-rev" xmlns:us-gaap="urn:fake"')
    with pytest.raises(adapter.EvidenceRejected, match="namespace_rebinding"):
        parse(xml)


def test_descendant_namespace_cannot_resolve_an_earlier_fact_qname():
    xml = XML.replace(f'name="us-gaap:{CUSTOMER}"', f'name="later:{CUSTOMER}"')
    xml = xml.replace('</body>', '<span xmlns:later="http://fasb.org/us-gaap/2025"/></body>')
    with pytest.raises(adapter.EvidenceRejected, match="unresolved_namespace"):
        parse(xml)


def test_exact_amended_document_identity_requires_both_form_and_flag():
    xml = XML.replace('>10-Q</ix:nonNumeric>', '>10-Q/A</ix:nonNumeric>').replace('>false</ix:nonNumeric>', '>true</ix:nonNumeric>')
    assert parse(xml, form="10-Q/A", accession="0000000001-25-000002").observations
    with pytest.raises(adapter.EvidenceRejected, match="filing_identity_mismatch"):
        parse(xml)


def test_empty_permissions_do_not_read_config_files_or_query_evidence(monkeypatch):
    def forbidden(*a, **k): pytest.fail("Empty permissions must do no evidence I/O")
    monkeypatch.setattr(adapter.os.environ, "get", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    assert adapter.load_production_evidence(SimpleNamespace(), CIK, []) == ()


def test_dataset_loader_uses_only_existing_two_queries_when_empty(tmp_path, monkeypatch):
    s = scenario(tmp_path)
    calls = []
    session = SimpleNamespace(scalar=lambda stmt: (calls.append(str(stmt)), COMPANY)[1],
        scalars=lambda stmt: (calls.append(str(stmt)), s.facts)[1])
    result = load_financial_metrics(session, "TEST").summary()
    expected = FinancialMetrics(COMPANY, s.facts).summary()
    assert result.model_dump(mode="json") == expected.model_dump(mode="json")
    assert len(calls) == 2
    assert result.metrics["net_margin"].status == "unavailable"


def test_synthetic_proofs_and_caller_paths_have_no_production_input_channel(tmp_path, monkeypatch):
    s = scenario(tmp_path)
    assert tuple(inspect.signature(adapter.load_production_evidence).parameters) == ("session", "cik", "facts")
    monkeypatch.setattr(auth, "DENOMINATOR_AUTHORIZATIONS", (s.record,))
    # A synthetic evaluator grant has no trusted production policy; no I/O.
    assert adapter.load_production_evidence(SimpleNamespace(), CIK, s.facts) == ()
    with pytest.raises(TypeError):
        adapter.load_production_evidence(s.session, CIK, s.facts, evidence=s.evidence, path=s.artifact, production=True)


def test_configured_store_has_no_relative_or_escaping_paths(tmp_path, monkeypatch):
    s = scenario(tmp_path)
    install_test_policy(monkeypatch, s)
    monkeypatch.setenv("FINLENS_SEC_ORIGINAL_STORE", "relative-store")
    assert adapter.load_production_evidence(s.session, CIK, s.facts) == ()
    with pytest.raises(adapter.EvidenceRejected):
        adapter._store_path(s.root, CIK, ACCESSION, "../fixture.htm")


def test_real_original_artifact_offline_without_permission_activation():
    # Optional external acceptance fixture. Never acquire/copy it into Git.
    path = Path(r"D:\FinLens-OperatorReports\sec-original-evidence\0000320193\0000320193-26-000020\aapl-20260627.htm")
    if not path.is_file(): pytest.skip("Verified external original artifact not installed")
    pin = adapter.ArtifactPin("0000320193", "0000320193-26-000020", path.name, "10-Q", date(2026,7,31),
        date(2026,6,27), "ff8ff7fb32493f9ca51b5d3afa6b336adacea503f7e50e53618a6e585e7eac07", 1018326,
        "retrieval-20261010T111011020789Z.json", "0d3b3c51c53780ffa7564d57dfa6450d5a5041afb62855619ffcd8c5a3bee62a", "http://fasb.org/us-gaap/2025", "http://xbrl.sec.gov/dei/2025")
    data = path.read_bytes()
    parsed = adapter._parse_artifact(pin, data)
    assert (parsed.inline_fact_count, parsed.context_count, parsed.unit_count) == (860,161,6)
    assert len(parsed.observations) == 78  # Retain facts nested in narrative containers.
    assert any(o.fact_id == "f-401" and o.context_id == "c-18" for o in parsed.observations)
    targets = {o.fact_id: o for o in parsed.observations if o.fact_id in {"f-56", "f-104"}}
    assert targets["f-56"].identity.value == Decimal("109417000000")
    assert targets["f-104"].identity.value == Decimal("29789000000")
    assert all(o.context_id == "c-18" and o.dimensions == () and o.table_ordinal == 12 for o in targets.values())
    assert targets["f-56"].identity.period_scope() == targets["f-104"].identity.period_scope()
    receipt_path = path.parent / pin.receipt_filename
    receipt = receipt_path.read_bytes()
    adapter._validate_receipt(pin, receipt, path)
    assert adapter.PRODUCTION_EVIDENCE_POLICIES == () and auth.DENOMINATOR_AUTHORIZATIONS == ()
