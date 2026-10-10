"""Exact dormant proposal: offline reads only, isolated permissions, no DB writes.

Set FINLENS_REVIEW_SEC_ORIGINAL_STORE for real-original acceptance cases. Without
that explicitly supplied external store those cases skip; invariant tests still run.
No original artifact/receipt is copied, reconstructed or modified.
"""
from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime
from decimal import Decimal
import importlib
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import aapl_net_margin_proposal as proposal
from app import revenue_scope_authorizations as auth, sec_evidence_adapter as adapter
from app.financial_metric_registry import REVENUE_EQUIVALENCES
from app.financial_metrics_service import FinancialMetrics
from app.models import FinancialFact


def assert_inactive():
    assert auth.REVENUE_SELECTION_AUTHORIZATIONS == ()
    assert auth.DENOMINATOR_AUTHORIZATIONS == ()
    assert auth.AUTHORIZATION_WITHDRAWALS == ()
    assert adapter.PRODUCTION_EVIDENCE_POLICIES == ()
    assert REVENUE_EQUIVALENCES == frozenset()


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    assert_inactive()  # Inspect shipped registries BEFORE any test patches.
    from app.database import engine
    import socket
    monkeypatch.setattr(engine, "connect", lambda *a, **k: pytest.fail("Database access forbidden"))
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: pytest.fail("Network access forbidden"))


def row(identity, number):
    return FinancialFact(
        id=number, company_cik=identity.cik, metric=identity.concept,
        source="SEC Company Facts API: " + identity.concept, value=identity.value,
        unit=identity.unit, period_start=identity.start, period_end=identity.end,
        period_type=identity.kind, fiscal_year=2026, fiscal_period="Q3", frame=None,
        accession_number=identity.accession, form=identity.form, filed=identity.filed,
        created_at=datetime(2026, 10, 11),
    )


@pytest.fixture
def local_evidence():
    configured = os.environ.get("FINLENS_REVIEW_SEC_ORIGINAL_STORE")
    if not configured:
        pytest.skip("Explicit external original store required for exact-pair acceptance")
    root = Path(configured)
    assert root.is_absolute() and root.is_dir()
    state = SimpleNamespace(company_cik=proposal.REVENUE.cik, data_version=1, facts_version=0, evidence_version=1)
    common = dict(company_cik=proposal.REVENUE.cik,
                  configuration="parser-v1/chunk-2500-overlap-250/sentence-transformers/all-MiniLM-L6-v2")
    publications = [
        SimpleNamespace(**common, accession_number="0000320193-25-000079", form="10-K",
            filed=date(2025, 10, 31), filename="aapl-20250927.htm", chunk_count=92,
            content_digest="8fafe74d5952ed4c7820fd0531c8a3a387c8b4d1422f70ded9dc5121d8092a81", data_version=1),
        SimpleNamespace(**common, accession_number=proposal.REVENUE.accession, form="10-Q",
            filed=proposal.REVENUE.filed, filename=proposal.ARTIFACT.filename, chunk_count=37,
            content_digest="5fcca79f7e4f27d26cf769f2c6604ebae6ea35e3bba45e7762fe0c13bd429eda", data_version=0),
    ]
    snapshot = adapter.snapshot_digest(state, publications)
    assert snapshot == proposal.PROPOSED_EVIDENCE_POLICY.snapshot_sha256
    facts = [row(proposal.REVENUE, 1853), row(proposal.NET_INCOME, 1976)]
    session = SimpleNamespace(
        get_bind=lambda: SimpleNamespace(dialect=SimpleNamespace(name="postgresql")),
        scalar=lambda stmt: "repeatable read" if str(stmt) == "SHOW transaction_isolation" else "on",
        get=lambda *args: state, scalars=lambda *args: publications,
    )
    fixture = SimpleNamespace(root=root, state=state, publications=publications, snapshot=snapshot,
        facts=facts, session=session, raw=(proposal.REVENUE, proposal.NET_INCOME))
    # Establish validity before each adversarial mutation: never pass because an
    # unrelated stale pin already made the proposed policy unusable.
    assert len(verify(fixture)) == 2
    return fixture


def verify(s):
    return adapter._verify_policy(proposal.PROPOSED_EVIDENCE_POLICY,
        proposal.PROPOSED_DENOMINATOR_AUTHORIZATION, s.raw, s.root, s.snapshot, s.publications)


def install_isolated(monkeypatch, s):
    # Test-only process-local substitution; no installer exists in application code.
    monkeypatch.setattr(auth, "DENOMINATOR_AUTHORIZATIONS", (proposal.PROPOSED_DENOMINATOR_AUTHORIZATION,))
    monkeypatch.setattr(adapter, "PRODUCTION_EVIDENCE_POLICIES", (proposal.PROPOSED_EVIDENCE_POLICY,))
    monkeypatch.setenv("FINLENS_SEC_ORIGINAL_STORE", str(s.root))


def decision(s, proofs, metric="net_margin", revenue=None, numerator=None, raw=None):
    return auth.authorize_denominator(metric, revenue or proposal.REVENUE,
        numerator or proposal.NET_INCOME, s.raw if raw is None else raw, proofs)


def test_import_is_disabled_by_default_and_performs_no_evidence_io(monkeypatch):
    monkeypatch.setattr(adapter, "_read", lambda *args: pytest.fail("Import must not read evidence"))
    monkeypatch.setattr(Path, "read_bytes", lambda *args: pytest.fail("Import must not read originals"))
    before = os.environ.get("FINLENS_SEC_ORIGINAL_STORE")
    importlib.reload(proposal)
    assert_inactive()
    assert os.environ.get("FINLENS_SEC_ORIGINAL_STORE") == before
    assert not auth.authorize_denominator("net_margin", proposal.REVENUE, proposal.NET_INCOME,
        (proposal.REVENUE, proposal.NET_INCOME), ()).accepted
    # Empty production registries must bypass even session, path and config access.
    assert adapter.load_production_evidence(object(), proposal.REVENUE.cik, []) == ()


def test_literal_record_integrity_and_permission_boundary():
    record, policy = proposal.PROPOSED_DENOMINATOR_AUTHORIZATION, proposal.PROPOSED_EVIDENCE_POLICY
    assert record.ref == policy.ref == proposal.REF
    assert record.ref.permission == "denominator:net_margin" and record.ref.version == 1
    assert record.metric == "net_margin"
    assert record.candidates == (record.revenue, record.numerator)
    assert {b.identity for b in record.candidates} == {proposal.REVENUE, proposal.NET_INCOME}
    assert adapter.approval_digest(record) == policy.approval_sha256
    assert policy.parser_version == adapter.PARSER_VERSION
    assert policy.artifacts == (proposal.ARTIFACT,)
    assert [(r.fact_id, r.context_id, r.table_ordinal) for r in policy.observations] == [
        ("f-56", "c-18", 12), ("f-104", "c-18", 12)]
    assert proposal.REVENUE_BASIS == "customer_contract"
    with pytest.raises(FrozenInstanceError):
        record.metric = "gross_margin"


@pytest.mark.parametrize("missing", ["permission", "policy", "configuration", "absolute_root"])
def test_activation_requires_all_independent_inputs(local_evidence, monkeypatch, missing):
    s = local_evidence
    install_isolated(monkeypatch, s)
    if missing == "permission":
        monkeypatch.setattr(auth, "DENOMINATOR_AUTHORIZATIONS", ())
    elif missing == "policy":
        monkeypatch.setattr(adapter, "PRODUCTION_EVIDENCE_POLICIES", ())
    elif missing == "configuration":
        monkeypatch.delenv("FINLENS_SEC_ORIGINAL_STORE", raising=False)
    else:
        monkeypatch.setenv("FINLENS_SEC_ORIGINAL_STORE", "relative-untrusted-store")
    monkeypatch.setattr(adapter, "_read", lambda *args: pytest.fail("Incomplete activation must not read evidence"))
    assert adapter.load_production_evidence(s.session, proposal.REVENUE.cik, s.facts) == ()


def test_another_issuer_cannot_load_the_pair(local_evidence, monkeypatch):
    install_isolated(monkeypatch, local_evidence)
    monkeypatch.setattr(adapter, "_read", lambda *args: pytest.fail("Wrong issuer must not read evidence"))
    assert adapter.load_production_evidence(object(), "0001018724", local_evidence.facts) == ()


def test_original_full_policy_and_loader_validate_exact_pair_only(local_evidence, monkeypatch):
    s = local_evidence
    proofs = verify(s)  # Unregistered verification, before any permission substitution.
    assert_inactive()
    assert tuple(p.fingerprint() for p in proofs) == tuple(
        b.fingerprint for b in proposal.PROPOSED_DENOMINATOR_AUTHORIZATION.candidates)
    assert all(p.dimensions == () and p.context_id == "c-18" for p in proofs)
    with monkeypatch.context() as isolated:
        install_isolated(isolated, s)
        loaded = adapter.load_production_evidence(s.session, proposal.REVENUE.cik, s.facts)
        assert set(loaded) == set(proofs) and decision(s, loaded).accepted
        assert not auth.authorize_selection(proposal.REVENUE.period_scope(), (proposal.REVENUE,), loaded).accepted
        company = SimpleNamespace(cik=proposal.REVENUE.cik, ticker="AAPL", name="Apple Inc.")
        snap = FinancialMetrics(company, s.facts, authorization_evidence=loaded).summary()
        assert snap.metrics["net_margin"].value == Decimal("29789000000") / Decimal("109417000000")
        assert snap.metrics["net_margin"].scope_authorization.approval_id == proposal.REF.approval_id
        assert snap.metrics["revenue"].revenue_basis == "customer_contract"
        assert snap.metrics["revenue"].scope_authorization is None
    assert_inactive()


@pytest.mark.parametrize("changes", [
    {"cik": "0001018724"}, {"accession": "0000320193-26-000021"},
    {"start": date(2026, 3, 30)}, {"end": date(2026, 6, 28)},
    {"kind": "half_year"}, {"unit": "EUR"}, {"value": Decimal("109417000001")},
    {"filed": date(2026, 8, 1)}, {"form": "10-Q/A"}, {"concept": "SalesRevenueNet"},
    {"source_namespace": "Synthetic source"},
])
def test_wrong_operand_identity_rejected(local_evidence, monkeypatch, changes):
    s = local_evidence
    proofs = verify(s)
    install_isolated(monkeypatch, s)
    wrong = replace(proposal.REVENUE, **changes)
    assert not decision(s, proofs, revenue=wrong, raw=(wrong, proposal.NET_INCOME)).accepted


@pytest.mark.parametrize("metric", ["gross_margin", "operating_margin", "revenue"])
def test_wrong_metric_rejected(local_evidence, monkeypatch, metric):
    proofs = verify(local_evidence)
    install_isolated(monkeypatch, local_evidence)
    assert not decision(local_evidence, proofs, metric=metric).accepted


@pytest.mark.parametrize("change", ["value", "accession", "company", "scope", "document", "context", "dimensions"])
def test_changed_numerator_or_evidence_rejected(local_evidence, monkeypatch, change):
    s = local_evidence
    proofs = verify(s)
    install_isolated(monkeypatch, s)
    identity_changes = {"value": {"value": Decimal("29789000001")},
                        "accession": {"accession": "0000320193-26-000021"},
                        "company": {"cik": "0001018724"}}
    if change in identity_changes:
        wrong = replace(proposal.NET_INCOME, **identity_changes[change])
        assert not decision(s, proofs, numerator=wrong, raw=(proposal.REVENUE, wrong)).accepted
    else:
        changes = {"scope": {"economic_scope": "component_revenue"},
                   "document": {"document_text": proofs[1].document_text + "changed"},
                   "context": {"context_id": "c-19"}, "dimensions": {"dimensions": (("segment", "member"),)}}
        changed = (proofs[0], replace(proofs[1], **changes[change]))
        assert not decision(s, changed).accepted


@pytest.mark.parametrize("failure", ["missing_artifact", "artifact_bytes", "receipt_bytes"])
def test_missing_or_changed_evidence_fails_closed_without_mutating_originals(local_evidence, monkeypatch, failure):
    s = local_evidence
    install_isolated(monkeypatch, s)
    read = adapter._read

    def broken(path, limit):
        if failure == "missing_artifact" and path.name == proposal.ARTIFACT.filename:
            raise FileNotFoundError("Test-only simulated missing original")
        data = read(path, limit)
        if ((failure == "artifact_bytes" and path.name == proposal.ARTIFACT.filename)
                or (failure == "receipt_bytes" and path.name == proposal.ARTIFACT.receipt_filename)):
            return b"changed evidence"
        return data

    monkeypatch.setattr(adapter, "_read", broken)
    assert adapter.load_production_evidence(s.session, proposal.REVENUE.cik, s.facts) == ()


@pytest.mark.parametrize("field", ["data_version", "facts_version", "evidence_version"])
def test_changed_company_version_rejected(local_evidence, monkeypatch, field):
    s = local_evidence
    install_isolated(monkeypatch, s)
    setattr(s.state, field, getattr(s.state, field) + 1)  # Detached fixture only.
    assert adapter.load_production_evidence(s.session, proposal.REVENUE.cik, s.facts) == ()


def test_changed_publication_version_or_new_vintage_rejected(local_evidence, monkeypatch):
    s = local_evidence
    install_isolated(monkeypatch, s)
    s.publications[-1].data_version += 1
    assert adapter.load_production_evidence(s.session, proposal.REVENUE.cik, s.facts) == ()
    s.publications[-1].data_version -= 1
    s.publications.append(SimpleNamespace(**dict(vars(s.publications[-1]),
        accession_number="0000320193-26-000021", form="10-Q/A")))
    assert adapter.load_production_evidence(s.session, proposal.REVENUE.cik, s.facts) == ()


@pytest.mark.parametrize("change", ["missing", "conflict", "changed_start", "amendment"])
def test_complete_raw_manifest_required(local_evidence, monkeypatch, change):
    s = local_evidence
    install_isolated(monkeypatch, s)
    if change == "missing":
        facts = s.facts[:1]
    else:
        changes = {"conflict": {"value": Decimal("109417000001")},
                   "changed_start": {"start": date(2026, 3, 30)},
                   "amendment": {"accession": "0000320193-26-000021", "form": "10-Q/A"}}
        facts = s.facts + [row(replace(proposal.REVENUE, **changes[change]), 9999)]
    assert adapter.load_production_evidence(s.session, proposal.REVENUE.cik, facts) == ()


def test_withdrawal_stops_loader_before_evidence_io(local_evidence, monkeypatch):
    s = local_evidence
    install_isolated(monkeypatch, s)
    monkeypatch.setattr(auth, "AUTHORIZATION_WITHDRAWALS",
        (auth.AuthorizationWithdrawal(proposal.REF, "revoked", "Test-only withdrawal"),))
    monkeypatch.setattr(adapter, "_read", lambda *args: pytest.fail("Withdrawn scope must not read evidence"))
    assert adapter.load_production_evidence(s.session, proposal.REVENUE.cik, s.facts) == ()
    assert not decision(s, ()).accepted


@pytest.mark.parametrize("moved_period", [False, True])
def test_supersession_never_revives_withdrawn_predecessor(monkeypatch, moved_period):
    first = proposal.PROPOSED_DENOMINATOR_AUTHORIZATION
    successor = replace(first, ref=replace(first.ref, version=2))
    if moved_period:
        successor = replace(successor, revenue=replace(successor.revenue,
            identity=replace(proposal.REVENUE, start=date(2026, 6, 28), end=date(2026, 9, 26))))
    registry = (first, successor)
    monkeypatch.setattr(auth, "DENOMINATOR_AUTHORIZATIONS", registry)
    assert auth._approval((first,), first.ref.permission, registry)[1] == "explicit_supersession_required"
    supersede = auth.AuthorizationWithdrawal(first.ref, "superseded", "Test-only version transition", successor.ref)
    monkeypatch.setattr(auth, "AUTHORIZATION_WITHDRAWALS", (supersede,))
    assert auth._approval((first,), first.ref.permission, registry)[1] == "approval_withdrawn"
    assert auth._approval((successor,), successor.ref.permission, registry)[0] == successor
    monkeypatch.setattr(auth, "AUTHORIZATION_WITHDRAWALS", (supersede,
        auth.AuthorizationWithdrawal(successor.ref, "revoked", "Test-only successor withdrawal")))
    assert auth._approval((first,), first.ref.permission, registry)[1] == "approval_withdrawn"
    assert auth._approval((successor,), successor.ref.permission, registry)[1] == "approval_withdrawn"


def test_permission_isolation_preserves_gross_margin_guard_and_historical_gaps(local_evidence, monkeypatch):
    s = local_evidence
    proofs = verify(s)
    install_isolated(monkeypatch, s)
    company = SimpleNamespace(cik=proposal.REVENUE.cik, ticker="AAPL", name="Apple Inc.")
    gross = row(replace(proposal.REVENUE, concept="GrossProfit", value=Decimal("54770000000")), 2000)
    facts = s.facts + [gross]
    summary = FinancialMetrics(company, facts, authorization_evidence=proofs).summary()
    assert summary.metrics["gross_margin"].value == Decimal("0.5005620698794520047159033788")
    assert summary.metrics["gross_margin"].scope_authorization is None
    assert summary.metrics["operating_margin"].status == "unavailable"
    conflict = row(replace(proposal.REVENUE, concept="GrossProfit", value=Decimal("54770000001")), 2001)
    assert FinancialMetrics(company, facts + [conflict], authorization_evidence=proofs).summary().metrics["gross_margin"].status == "unavailable"
    historical = [
        row(replace(proposal.REVENUE, concept="SalesRevenueNet", value=Decimal("149430000000"),
            start=date(2017, 10, 1), end=date(2018, 3, 31), kind="half_year",
            accession="0000320193-18-000070", filed=date(2018, 5, 2)), 10),
        row(replace(proposal.REVENUE, value=Decimal("149430000000"),
            start=date(2017, 10, 1), end=date(2018, 3, 31), kind="half_year",
            accession="0000320193-19-000066", filed=date(2019, 5, 1)), 11),
        row(replace(proposal.REVENUE, value=Decimal("142325000000"),
            start=date(2018, 9, 30), end=date(2019, 3, 30), kind="half_year",
            accession="0000320193-20-000052", filed=date(2020, 5, 1)), 12),
    ]
    view = FinancialMetrics(company, facts + historical, authorization_evidence=proofs)
    assert view.history("revenue", "half_year").history[0].status == "unavailable"
    assert view.history("revenue_growth_yoy", "half_year").history[-1].status == "unavailable"
    assert auth.REVENUE_SELECTION_AUTHORIZATIONS == () and REVENUE_EQUIVALENCES == frozenset()
