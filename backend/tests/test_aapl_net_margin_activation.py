"""Disabled operator wiring exercised only in reversible offline fixtures.

Reuse the reviewed proposal's real-original fixture; never call an enabled entry
point against PostgreSQL or persist configuration, registry changes or evidence.
"""
from contextlib import contextmanager
from dataclasses import replace
from decimal import Decimal
import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import aapl_net_margin_activation as activation, aapl_net_margin_proposal as proposal
from app import database, revenue_scope_authorizations as auth, sec_evidence_adapter as adapter
from app import financial_metric_registry as registry
from app.financial_metrics_service import FinancialMetrics, load_financial_metrics
from app.freshness_service import request_scope
from test_aapl_net_margin_proposal import assert_inactive, local_evidence, row


def assert_not_registered():
    assert auth.REVENUE_SELECTION_AUTHORIZATIONS == ()
    assert auth.DENOMINATOR_AUTHORIZATIONS == ()
    assert adapter.PRODUCTION_EVIDENCE_POLICIES == ()


@pytest.fixture(autouse=True)
def boundary(monkeypatch):
    # Validate actual production state BEFORE isolation can hide registration.
    assert_inactive()
    assert activation._ACTIVATION_ENABLED is False
    import socket
    with monkeypatch.context() as isolated:
        isolated.setattr(database.engine, "connect", lambda *a, **k: pytest.fail("Live database forbidden"))
        isolated.setattr(socket, "create_connection", lambda *a, **k: pytest.fail("Network forbidden"))
        # Track original tuples so helper assignments are reverted, too.
        isolated.setattr(auth, "DENOMINATOR_AUTHORIZATIONS", ())
        isolated.setattr(adapter, "PRODUCTION_EVIDENCE_POLICIES", ())
        yield isolated
    assert_inactive()
    assert activation._ACTIVATION_ENABLED is False


def wire_isolated(patch, s):
    patch.setattr(activation, "_ACTIVATION_ENABLED", True)
    patch.setenv("FINLENS_SEC_ORIGINAL_STORE", str(s.root))
    s.company = SimpleNamespace(cik=proposal.REVENUE.cik, ticker=proposal.REVIEWED_TICKER, name="Apple Inc.")
    s.events = []
    s.isolation, s.read_only, s.dialect = "repeatable read", "on", "postgresql"

    class Session:
        def get_bind(self):
            return SimpleNamespace(dialect=SimpleNamespace(name=s.dialect))

        def execute(self, stmt):
            assert str(stmt) == "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
            s.events.append("read_only_transaction")

        def scalar(self, stmt):
            sql = str(stmt)
            if sql == "SHOW transaction_isolation": return s.isolation
            if sql == "SHOW transaction_read_only": return s.read_only
            assert "FROM companies" in sql
            return s.company

        def scalars(self, stmt):
            sql = str(stmt)
            if "FROM financial_facts" in sql: return s.facts
            assert "FROM filing_publications" in sql
            return s.publications

        def get(self, *args):
            return s.state

    @contextmanager
    def factory():
        s.events.append("fresh_session")
        try:
            yield Session()
        finally:
            s.events.append("session_closed")

    patch.setattr(database, "SessionLocal", factory)
    s.session = Session()
    return s


def activate():
    return activation.activate_aapl_net_margin(operator_authorized=True, reviewed_ref=proposal.REF)


def registry_references():
    return (auth.REVENUE_SELECTION_AUTHORIZATIONS, auth.DENOMINATOR_AUTHORIZATIONS,
            auth.AUTHORIZATION_WITHDRAWALS, adapter.PRODUCTION_EVIDENCE_POLICIES,
            registry.REVENUE_EQUIVALENCES)


def interrupt_publication(patch, failure, *, stage="before", times=1, observe=None):
    """Interrupt the actual STORE_ATTR, not validation or a replacement publisher."""
    remaining = [times]

    class FaultingAuth(type(auth)):
        def __setattr__(self, name, value):
            if (name == "DENOMINATOR_AUTHORIZATIONS" and value
                    and value[0] is proposal.PROPOSED_DENOMINATOR_AUTHORIZATION and remaining[0]):
                remaining[0] -= 1
                if stage == "after": super().__setattr__(name, value)
                assert activation._activation_lock.locked()
                if observe is not None: observe()
                raise failure
            super().__setattr__(name, value)

    patch.setattr(auth, "__class__", FaultingAuth)


@pytest.mark.parametrize("failure_type", [KeyboardInterrupt, SystemExit, RuntimeError])
@pytest.mark.parametrize("stage", ["before", "after"])
def test_publication_fault_restores_exact_references_and_retry_succeeds(local_evidence, boundary, failure_type, stage):
    s = wire_isolated(boundary, local_evidence)
    previous = registry_references()
    failure = failure_type("Injected publication interruption")

    def observe():
        assert s.events[-1] == "session_closed"  # All validation completed first.
        assert adapter.PRODUCTION_EVIDENCE_POLICIES == (proposal.PROPOSED_EVIDENCE_POLICY,)

    interrupt_publication(boundary, failure, stage=stage, observe=observe)
    with pytest.raises(failure_type) as caught: activate()
    assert caught.value is failure  # Preserve the original BaseException.
    assert all(old is current for old, current in zip(previous, registry_references()))
    assert activate() is True  # No stranded policy blocks this fresh valid retry.
    assert auth.DENOMINATOR_AUTHORIZATIONS == (proposal.PROPOSED_DENOMINATOR_AUTHORIZATION,)
    assert adapter.PRODUCTION_EVIDENCE_POLICIES == (proposal.PROPOSED_EVIDENCE_POLICY,)
    assert auth.REVENUE_SELECTION_AUTHORIZATIONS is previous[0]
    assert auth.AUTHORIZATION_WITHDRAWALS is previous[2]
    assert registry.REVENUE_EQUIVALENCES is previous[4]


@pytest.mark.parametrize("stage", ["before", "after"])
def test_repeated_interruptions_never_accumulate_partial_registries(local_evidence, boundary, stage):
    wire_isolated(boundary, local_evidence)
    previous = registry_references()
    interrupt_publication(boundary, KeyboardInterrupt("Repeated fault"), stage=stage, times=3)
    for _ in range(3):
        with pytest.raises(KeyboardInterrupt): activate()
        assert all(old is current for old, current in zip(previous, registry_references()))
    assert activate() is True


def test_policy_only_interval_is_visible_but_ordinary_reader_abstains(local_evidence, boundary):
    s = wire_isolated(boundary, local_evidence)

    def observe():
        assert len(adapter.PRODUCTION_EVIDENCE_POLICIES) == 1
        assert auth.DENOMINATOR_AUTHORIZATIONS == ()
        with boundary.context() as reader_guard:
            reader_guard.setattr(adapter, "_read", lambda *args: pytest.fail("Policy-only reader fetched evidence"))
            # A normal loader needs neither database nor evidence in this interval.
            assert adapter.load_production_evidence(object(), proposal.REVENUE.cik, s.facts) == ()

    interrupt_publication(boundary, KeyboardInterrupt(), observe=observe)
    with pytest.raises(KeyboardInterrupt): activate()
    assert_not_registered()


def test_recovery_does_not_replace_foreign_tuple_references(local_evidence, boundary):
    wire_isolated(boundary, local_evidence)
    # Same contents, different ownership: equality must not trigger their removal.
    foreign_policies = tuple([proposal.PROPOSED_EVIDENCE_POLICY])
    foreign_permissions = tuple([proposal.PROPOSED_DENOMINATOR_AUTHORIZATION])

    def foreign_writer():
        # Deliberate unsupported mutation without the lock; recovery must not
        # blindly overwrite these references even though their values are equal.
        adapter.PRODUCTION_EVIDENCE_POLICIES = foreign_policies
        auth.DENOMINATOR_AUTHORIZATIONS = foreign_permissions

    interrupt_publication(boundary, KeyboardInterrupt(), observe=foreign_writer)
    with pytest.raises(KeyboardInterrupt): activate()
    assert adapter.PRODUCTION_EVIDENCE_POLICIES is foreign_policies
    assert auth.DENOMINATOR_AUTHORIZATIONS is foreign_permissions


def test_lock_cooperating_retry_cannot_be_overwritten_by_recovery(local_evidence, boundary):
    from threading import Event, Thread
    wire_isolated(boundary, local_evidence)
    start, ready, done = Event(), Event(), Event()
    results = []

    def peer():
        if not start.wait(5): return
        ready.set()
        try:
            results.append(activate())
        except BaseException as error:
            results.append(error)
        finally:
            done.set()

    def start_peer_while_locked():
        start.set()
        assert ready.wait(5)
        assert not done.is_set()  # The peer cannot publish before recovery releases.

    interrupt_publication(boundary, KeyboardInterrupt(), observe=start_peer_while_locked)
    thread = Thread(target=peer, daemon=True)
    thread.start()
    try:
        with pytest.raises(KeyboardInterrupt): activate()
        assert done.wait(5)
        assert results == [True]
        assert auth.DENOMINATOR_AUTHORIZATIONS == (proposal.PROPOSED_DENOMINATOR_AUTHORIZATION,)
        assert adapter.PRODUCTION_EVIDENCE_POLICIES == (proposal.PROPOSED_EVIDENCE_POLICY,)
    finally:
        start.set()
        thread.join(5)
        assert not thread.is_alive()


def test_import_and_even_explicit_calls_remain_disabled_without_io(boundary):
    boundary.setattr(database, "SessionLocal", lambda: pytest.fail("Disabled path opened session"))
    boundary.setattr(adapter, "_read", lambda *args: pytest.fail("Disabled path read evidence"))
    boundary.setattr(Path, "read_bytes", lambda *args: pytest.fail("Dormant import read original"))
    importlib.reload(activation)
    importlib.reload(proposal)
    assert activation.activate_aapl_net_margin() is False
    assert activate() is False
    assert adapter.load_production_evidence(object(), proposal.REVENUE.cik, []) == ()
    assert_inactive()


@pytest.mark.parametrize("authorized", [False, None, 1, "true"])
def test_enabled_gate_still_requires_explicit_operator_authorization(boundary, authorized):
    boundary.setattr(activation, "_ACTIVATION_ENABLED", True)
    boundary.setattr(database, "SessionLocal", lambda: pytest.fail("Unauthorized session"))
    with pytest.raises(adapter.EvidenceRejected, match="operator_authorization_required"):
        activation.activate_aapl_net_margin(operator_authorized=authorized, reviewed_ref=proposal.REF)
    assert_not_registered()


@pytest.mark.parametrize("ref", [None, replace(proposal.REF, version=2), replace(proposal.REF, version=True),
    replace(proposal.REF, permission="select:revenue"), replace(proposal.REF, approval_id="unreviewed")])
def test_exact_reviewed_reference_required(boundary, ref):
    boundary.setattr(activation, "_ACTIVATION_ENABLED", True)
    with pytest.raises(adapter.EvidenceRejected, match="reviewed_approval_required"):
        activation.activate_aapl_net_margin(operator_authorized=True, reviewed_ref=ref)
    assert_not_registered()


def test_request_context_cannot_activate(boundary):
    boundary.setattr(activation, "_ACTIVATION_ENABLED", True)
    token = request_scope.set({"ticker": "AAPL"})
    try:
        with pytest.raises(adapter.EvidenceRejected, match="request_context_not_permitted"):
            activate()
    finally:
        request_scope.reset(token)
    assert_not_registered()


def test_successful_wiring_is_isolated_and_fresh(local_evidence, boundary):
    s = wire_isolated(boundary, local_evidence)
    gross = row(replace(proposal.REVENUE, concept="GrossProfit", value=Decimal("54770000000")), 2000)
    s.facts.append(gross)
    before = FinancialMetrics(s.company, s.facts).summary()
    assert before.metrics["net_margin"].status == "unavailable"
    assert activate() is True
    assert s.events == ["fresh_session", "read_only_transaction", "session_closed"]
    assert auth.DENOMINATOR_AUTHORIZATIONS == (proposal.PROPOSED_DENOMINATOR_AUTHORIZATION,)
    assert adapter.PRODUCTION_EVIDENCE_POLICIES == (proposal.PROPOSED_EVIDENCE_POLICY,)
    assert auth.REVENUE_SELECTION_AUTHORIZATIONS == auth.AUTHORIZATION_WITHDRAWALS == ()
    assert registry.REVENUE_EQUIVALENCES == frozenset()
    assert s.publications[-1].data_version == 0  # Legacy publication pin unchanged.
    after = load_financial_metrics(s.session, proposal.REVIEWED_TICKER).summary()
    assert after.metrics["net_margin"].value == proposal.NET_INCOME.value / proposal.REVENUE.value
    assert after.metrics["net_margin"].scope_authorization.version == proposal.REF.version
    for name in before.metrics:
        if name != "net_margin":
            assert before.metrics[name].model_dump() == after.metrics[name].model_dump()
    assert after.metrics["revenue"].revenue_basis == proposal.REVENUE_BASIS
    # Denominator permission cannot defeat the existing Gross Margin raw guard.
    s.facts.append(row(replace(proposal.REVENUE, concept="GrossProfit", value=Decimal("54770000001")), 2001))
    assert load_financial_metrics(s.session, proposal.REVIEWED_TICKER).summary().metrics["gross_margin"].status == "unavailable"


@pytest.mark.parametrize("change", ["artifact", "publication", "withdrawal"])
def test_preflight_does_not_cache_authorization_evidence(local_evidence, boundary, change):
    s = wire_isolated(boundary, local_evidence)
    assert activate() is True
    assert load_financial_metrics(s.session, proposal.REVIEWED_TICKER).summary().metrics["net_margin"].status == "available"
    if change == "publication": s.publications[-1].data_version += 1
    if change == "withdrawal":
        boundary.setattr(auth, "AUTHORIZATION_WITHDRAWALS", (auth.AuthorizationWithdrawal(proposal.REF, "revoked", "Post-preflight test withdrawal"),))
    if change == "artifact":
        read = adapter._read
        boundary.setattr(adapter, "_read", lambda path, limit:
            b"changed original" if path.name == proposal.ARTIFACT.filename else read(path, limit))
    assert load_financial_metrics(s.session, proposal.REVIEWED_TICKER).summary().metrics["net_margin"].status == "unavailable"


@pytest.mark.parametrize("config", ["missing", "relative", "nonexistent", "redirected"])
def test_missing_or_unsafe_store_fails_before_registration(local_evidence, boundary, config):
    s = wire_isolated(boundary, local_evidence)
    if config == "missing": boundary.delenv("FINLENS_SEC_ORIGINAL_STORE")
    if config == "relative": boundary.setenv("FINLENS_SEC_ORIGINAL_STORE", "relative-store")
    if config == "nonexistent": boundary.setenv("FINLENS_SEC_ORIGINAL_STORE", str(s.root / "missing-store"))
    if config == "redirected": boundary.setattr(Path, "is_symlink", lambda self: self == s.root)
    with pytest.raises(adapter.EvidenceRejected): activate()
    assert s.events == []
    assert_not_registered()


@pytest.mark.parametrize("failure", ["artifact", "receipt", "missing_artifact"])
def test_evidence_failure_never_partially_registers(local_evidence, boundary, failure):
    s = wire_isolated(boundary, local_evidence)
    read = adapter._read

    def broken(path, limit):
        if path.name == proposal.ARTIFACT.filename:
            if failure == "missing_artifact": raise FileNotFoundError("Test-only missing file")
            if failure == "artifact": return b"wrong original"
        if path.name == proposal.ARTIFACT.receipt_filename and failure == "receipt": return b"wrong receipt"
        return read(path, limit)

    boundary.setattr(adapter, "_read", broken)
    with pytest.raises(adapter.EvidenceRejected): activate()
    assert s.events[-1] == "session_closed"
    assert_not_registered()


@pytest.mark.parametrize("version", ["data_version", "facts_version", "evidence_version", "legacy_publication"])
def test_version_pins_are_exact_including_legacy_zero(local_evidence, boundary, version):
    s = wire_isolated(boundary, local_evidence)
    if version == "legacy_publication": s.publications[-1].data_version = 1
    else: setattr(s.state, version, getattr(s.state, version) + 1)
    with pytest.raises(adapter.EvidenceRejected): activate()
    assert_not_registered()


@pytest.mark.parametrize("kind", ["approval_hash", "metric", "permission", "policy_reference"])
def test_changed_approval_or_policy_not_repinned(local_evidence, boundary, kind):
    wire_isolated(boundary, local_evidence)
    if kind == "approval_hash":
        boundary.setattr(proposal, "PROPOSED_EVIDENCE_POLICY", replace(proposal.PROPOSED_EVIDENCE_POLICY, approval_sha256="0" * 64))
    elif kind == "policy_reference":
        boundary.setattr(proposal, "PROPOSED_EVIDENCE_POLICY", replace(proposal.PROPOSED_EVIDENCE_POLICY, ref=replace(proposal.REF, version=2)))
    else:
        change = {"metric": "gross_margin"} if kind == "metric" else {"ref": replace(proposal.REF, permission="select:revenue")}
        boundary.setattr(proposal, "PROPOSED_DENOMINATOR_AUTHORIZATION", replace(proposal.PROPOSED_DENOMINATOR_AUTHORIZATION, **change))
    with pytest.raises(adapter.EvidenceRejected): activate()
    assert_not_registered()


@pytest.mark.parametrize("change", ["missing", "conflict", "new_start", "new_accession", "source", "period", "company"])
def test_complete_unfiltered_raw_candidates_required(local_evidence, boundary, change):
    from datetime import date
    s = wire_isolated(boundary, local_evidence)
    if change == "missing": s.facts.pop()
    elif change == "source": s.facts[0].source = "Unreviewed: " + proposal.REVENUE.concept
    elif change == "period": s.facts[0].period_end = date(2026, 6, 28)
    elif change == "company": s.company.cik = "0001018724"
    else:
        changes = {"conflict": {"value": proposal.REVENUE.value + 1},
                   "new_start": {"start": date(2026, 3, 30)},
                   "new_accession": {"accession": "0000320193-26-000021", "form": "10-Q/A"}}
        s.facts.append(row(replace(proposal.REVENUE, **changes[change]), 9999))
    with pytest.raises(adapter.EvidenceRejected): activate()
    assert_not_registered()


@pytest.mark.parametrize("mode", ["not_read_only", "not_repeatable", "not_postgres"])
def test_unsafe_database_snapshot_fails_closed(local_evidence, boundary, mode):
    s = wire_isolated(boundary, local_evidence)
    if mode == "not_read_only": s.read_only = "off"
    if mode == "not_repeatable": s.isolation = "read committed"
    if mode == "not_postgres": s.dialect = "sqlite"
    with pytest.raises(adapter.EvidenceRejected): activate()
    assert_not_registered()


@pytest.mark.parametrize("lineage", ["revoked", "superseded", "successor_withdrawn"])
def test_withdrawal_and_supersession_cannot_revive_proposal(local_evidence, boundary, lineage):
    s = wire_isolated(boundary, local_evidence)
    if lineage == "revoked": events = (auth.AuthorizationWithdrawal(proposal.REF, "revoked", "Test withdrawal"),)
    else:
        successor = replace(proposal.REF, version=2)
        events = (auth.AuthorizationWithdrawal(proposal.REF, "superseded", "Test successor", successor),)
        if lineage == "successor_withdrawn":
            events += (auth.AuthorizationWithdrawal(successor, "revoked", "Test successor withdrawal"),)
    boundary.setattr(auth, "AUTHORIZATION_WITHDRAWALS", events)
    with pytest.raises(adapter.EvidenceRejected): activate()
    assert s.events == []
    assert_not_registered()


@pytest.mark.parametrize("conflict", ["denominator", "selection", "policy", "equivalence"])
def test_conflicting_registries_are_never_merged_or_cleared(local_evidence, boundary, conflict):
    s = wire_isolated(boundary, local_evidence)
    if conflict == "denominator": boundary.setattr(auth, "DENOMINATOR_AUTHORIZATIONS", (proposal.PROPOSED_DENOMINATOR_AUTHORIZATION,))
    if conflict == "selection": boundary.setattr(auth, "REVENUE_SELECTION_AUTHORIZATIONS", (object(),))
    if conflict == "policy": boundary.setattr(adapter, "PRODUCTION_EVIDENCE_POLICIES", (proposal.PROPOSED_EVIDENCE_POLICY,))
    if conflict == "equivalence": boundary.setattr(registry, "REVENUE_EQUIVALENCES", frozenset({frozenset({"customer_contract", "total_revenue"})}))
    before = (auth.REVENUE_SELECTION_AUTHORIZATIONS, auth.DENOMINATOR_AUTHORIZATIONS,
              auth.AUTHORIZATION_WITHDRAWALS, adapter.PRODUCTION_EVIDENCE_POLICIES, registry.REVENUE_EQUIVALENCES)
    with pytest.raises(adapter.EvidenceRejected): activate()
    assert s.events == []
    assert before == (auth.REVENUE_SELECTION_AUTHORIZATIONS, auth.DENOMINATOR_AUTHORIZATIONS,
              auth.AUTHORIZATION_WITHDRAWALS, adapter.PRODUCTION_EVIDENCE_POLICIES, registry.REVENUE_EQUIVALENCES)
    assert all(old is current for old, current in zip(before, registry_references()))


@pytest.mark.parametrize("change", ["withdrawal", "configuration", "disabled"])
def test_late_boundary_changes_do_not_register(local_evidence, boundary, change):
    wire_isolated(boundary, local_evidence)
    verify = adapter._verify_policy

    def changed(*args):
        result = verify(*args)
        if change == "withdrawal":
            boundary.setattr(auth, "AUTHORIZATION_WITHDRAWALS", (auth.AuthorizationWithdrawal(proposal.REF, "revoked", "Late test withdrawal"),))
        if change == "configuration": boundary.delenv("FINLENS_SEC_ORIGINAL_STORE")
        if change == "disabled": boundary.setattr(activation, "_ACTIVATION_ENABLED", False)
        return result

    boundary.setattr(adapter, "_verify_policy", changed)
    with pytest.raises(adapter.EvidenceRejected): activate()
    assert_not_registered()
