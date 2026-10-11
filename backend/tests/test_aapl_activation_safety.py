"""Reversible synthetic-only operator/bootstrap tests. No real activation or I/O."""
import asyncio
from contextlib import contextmanager
from dataclasses import replace
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from threading import Event, Thread
from types import SimpleNamespace

import pytest

from app import activation_lifecycle as lifecycle, aapl_net_margin_launcher as launcher
from app import aapl_operator_policy as operators, aapl_net_margin_activation as activation
from app import aapl_net_margin_proposal as proposal, revenue_scope_authorizations as auth
from app import sec_evidence_adapter as adapter, financial_metric_registry as registry
from app import financial_analysis, research_answer_service, financial_sync_service, database
from app.financial_metrics_service import FinancialMetrics, load_financial_metrics
from test_sec_evidence_adapter import scenario
from test_aapl_net_margin_activation import wire_isolated


def inactive():
    assert activation._ACTIVATION_ENABLED is False
    assert auth.REVENUE_SELECTION_AUTHORIZATIONS == auth.DENOMINATOR_AUTHORIZATIONS == ()
    assert auth.AUTHORIZATION_WITHDRAWALS == adapter.PRODUCTION_EVIDENCE_POLICIES == ()
    assert registry.REVENUE_EQUIVALENCES == frozenset()


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    inactive()  # Check shipped state BEFORE clearing/substituting any registry.
    assert lifecycle._controller is None and lifecycle._readers == 0
    import socket
    with monkeypatch.context() as patch:
        patch.setattr(database.engine, "connect", lambda *a, **k: pytest.fail("Live DB forbidden"))
        patch.setattr(socket, "create_connection", lambda *a, **k: pytest.fail("Network forbidden"))
        patch.setattr(lifecycle, "_controller", None)
        patch.setattr(launcher, "_abort_process", lambda: None)  # Process termination tested in children only.
        patch.setattr(auth, "DENOMINATOR_AUTHORIZATIONS", ())
        patch.setattr(auth, "REVENUE_SELECTION_AUTHORIZATIONS", ())
        patch.setattr(auth, "AUTHORIZATION_WITHDRAWALS", ())
        patch.setattr(adapter, "PRODUCTION_EVIDENCE_POLICIES", ())
        patch.setattr(registry, "REVENUE_EQUIVALENCES", frozenset())
        for key in tuple(os.environ):
            if key.startswith("UVICORN_") or key in {"WEB_CONCURRENCY", "LISTEN_FDS", "LISTEN_PID", "LISTEN_FDNAMES"}:
                patch.delenv(key)
        yield patch
    inactive()
    assert lifecycle._controller is None and lifecycle._readers == 0


@pytest.fixture
def synthetic(tmp_path, isolated):
    s = scenario(tmp_path)
    # Exercise the exact version distinction using a completely synthetic issuer.
    s.state.facts_version = 0
    s.publications[0].data_version = 0
    s.snapshot = adapter.snapshot_digest(s.state, s.publications)
    s.policy = replace(s.policy, snapshot_sha256=s.snapshot)
    s.evidence = tuple(replace(e, statement_location=adapter._statement_location(s.policy, r))
                       for e, r in zip(s.evidence, s.policy.observations))
    bindings = tuple(auth.EvidenceBinding(e.identity, e.fingerprint()) for e in s.evidence)
    s.record = replace(s.record, revenue=bindings[0], numerator=bindings[1], candidates=bindings)
    s.policy = replace(s.policy, approval_sha256=adapter.approval_digest(s.record))
    assert len(adapter._verify_policy(s.policy, s.record, s.raw, s.root, s.snapshot, s.publications)) == 2
    for name, value in dict(REF=s.record.ref, REVIEWED_TICKER="TEST", REVENUE=s.raw[0],
                            NET_INCOME=s.raw[1], PROPOSED_DENOMINATOR_AUTHORIZATION=s.record,
                            PROPOSED_EVIDENCE_POLICY=s.policy).items():
        isolated.setattr(proposal, name, value)
    wire_isolated(isolated, s)  # Detached synthetic session only, never PostgreSQL.
    s.events = []
    s.pid = os.getpid()
    s.sid = "S-1-5-21-111-222-333-444"  # Synthetic test identity, never an installed allowlist.
    isolated.setattr(operators, "_process_token_sid", lambda: s.sid)
    isolated.setattr(operators, "_verify_protected_profile", lambda path: None)
    isolated.setattr(operators, "_verify_deployment_integrity", lambda policy: None)
    file = tmp_path / "synthetic-deployment.txt"
    file.write_text("synthetic fixture only", encoding="utf-8")
    s.profile = tmp_path / "synthetic-profile.json"
    s.profile_data = dict(version=2, deployment_id="synthetic-reviewed-deployment", operator_sids=[s.sid],
        approval={"permission": s.record.ref.permission, "id": s.record.ref.approval_id, "version": 1},
        approval_sha256=s.policy.approval_sha256, evidence_policy_sha256=adapter._policy_digest(s.policy),
        python_executable=sys.executable, import_roots=[str(tmp_path)], original_store=str(s.root),
        protected_files=[dict(path=str(file), sha256=hashlib.sha256(file.read_bytes()).hexdigest())],
        code_root=str(Path(operators.__file__).resolve().parents[1]),
        runtime_roots=[sys.prefix, sys.base_prefix], configuration_files=[],
        custodian_sids=sorted(operators._CUSTODIANS), custodian_access="full_control")
    s.profile.write_text(json.dumps(s.profile_data), encoding="utf-8")
    s.maintenance = False

    @contextmanager
    def maintenance(policy):
        assert policy.original_store == s.root and not s.maintenance
        s.maintenance = True
        s.events.append("maintenance_enter")
        def held():
            if not s.maintenance:
                raise lifecycle.LaunchRejected("maintenance_lease_lost")
        def subscribe(callback):
            s.loss_handler = callback
        try:
            yield SimpleNamespace(assert_held=held, subscribe_loss=subscribe)
        finally:
            s.maintenance = False
            s.events.append("maintenance_exit")

    isolated.setattr(operators, "maintenance_exclusion", maintenance)

    async def application(scope, receive, send):
        if scope["type"] == "lifespan":
            assert (await receive())["type"] == "lifespan.startup"
            s.events.append("application_startup")
            assert lifecycle._controller.phase is lifecycle.Phase.PUBLISHING
            await send({"type": "lifespan.startup.complete"})
            assert (await receive())["type"] == "lifespan.shutdown"
            assert not lifecycle._controller.admits()
            await send({"type": "lifespan.shutdown.complete"})
        elif scope["type"] == "http":
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})
        else:
            await send({"type": "websocket.accept"})

    isolated.setattr(launcher, "_load_application", lambda: application)

    def server(app):
        assert os.getpid() == s.pid and s.maintenance
        assert auth.DENOMINATOR_AUTHORIZATIONS == (s.record,)
        s.events.append("server_enter")
        asyncio.run(drive_server(app, s))
        s.events.append("server_exit")

    isolated.setattr(launcher, "_run_server", server)
    return s


async def request(app, kind="http"):
    messages = []
    async def receive(): return {"type": "http.request" if kind == "http" else "websocket.connect"}
    async def send(message): messages.append(message)
    await app({"type": kind}, receive, send)
    return messages


async def drive_server(app, s):
    assert (await request(app))[0]["status"] == 503
    assert (await request(app, "websocket"))[0] == {"type": "websocket.close", "code": 1013}
    queue, ready = asyncio.Queue(), asyncio.Event()
    async def send(message):
        if message["type"] == "lifespan.startup.complete": ready.set()
    await queue.put({"type": "lifespan.startup"})
    task = asyncio.create_task(app({"type": "lifespan"}, queue.get, send))
    try:
        await asyncio.wait_for(ready.wait(), 2)
        assert app.controller.admits()
        assert (await request(app))[0]["status"] == 200
        assert (await request(app, "websocket"))[0]["type"] == "websocket.accept"
        assert load_financial_metrics(s.session, "TEST").summary().metrics["net_margin"].value == s.raw[1].value / s.raw[0].value
        await queue.put({"type": "lifespan.shutdown"})
        await task
    finally:
        if not task.done():
            task.cancel()
            with pytest.raises(asyncio.CancelledError): await task
    assert (await request(app))[0]["status"] == 503


def test_disabled_launcher_import_and_invocation_have_zero_extra_io(isolated):
    isolated.setattr(operators, "authenticate_operator", lambda *a: pytest.fail("Disabled authentication I/O"))
    isolated.setattr(database, "SessionLocal", lambda: pytest.fail("Disabled database I/O"))
    isolated.setattr(adapter, "_read", lambda *a: pytest.fail("Disabled evidence I/O"))
    isolated.setattr(launcher, "_run_server", lambda *a: pytest.fail("Disabled server started"))
    importlib.reload(launcher)
    assert activation.activate_aapl_net_margin(operator_authorized=True, reviewed_ref=proposal.REF) is False
    with pytest.raises(lifecycle.LaunchRejected, match="production_activation_disabled"):
        launcher.launch("no-profile")
    assert lifecycle._controller.phase is lifecycle.Phase.FAILED


def test_enabled_helper_bool_and_approval_cannot_replace_launcher(isolated):
    isolated.setattr(activation, "_ACTIVATION_ENABLED", True)
    with pytest.raises(lifecycle.LaunchRejected, match="trusted_launcher_required"):
        activation.activate_aapl_net_margin(operator_authorized=True, reviewed_ref=proposal.REF)
    lifecycle._claim_launch()  # A claimed lifecycle still supplies no authority.
    with pytest.raises(lifecycle.LaunchRejected, match="authenticated_operator_required"):
        activation.activate_aapl_net_margin(operator_authorized=True, reviewed_ref=proposal.REF)


def test_actual_process_token_reader_ignores_claimed_environment_identity(isolated):
    if os.name != "nt":
        with pytest.raises(lifecycle.LaunchRejected, match="windows_process_token_required"):
            operators._process_token_sid()
        return
    before = operators._process_token_sid()
    isolated.setenv("USERNAME", "caller-spoof")
    isolated.setenv("FINLENS_OPERATOR_SID", "S-1-5-21-999")
    assert re.fullmatch(r"S-1-[0-9]+(?:-[0-9]+)+", before)
    assert operators._process_token_sid() == before  # Never print or allowlist it.


@pytest.mark.parametrize("spoof", ["username", "claimed_sid", "operator_authorized", "reviewed_ref", "workers", "reload"])
def test_caller_identity_and_server_options_are_not_interfaces(spoof):
    with pytest.raises(TypeError): launcher.launch("unused", **{spoof: True})


def test_same_interpreter_synthetic_success_exact_registry_and_terminal_shutdown(synthetic):
    s = synthetic
    assert launcher.launch(s.profile) == 0
    assert s.events.index("session_closed") < s.events.index("server_enter")
    assert s.events[0] == "maintenance_enter" and s.events[-1] == "maintenance_exit"
    assert lifecycle._controller.phase is lifecycle.Phase.SHUTDOWN
    assert auth.DENOMINATOR_AUTHORIZATIONS == (s.record,)
    assert adapter.PRODUCTION_EVIDENCE_POLICIES == (s.policy,)
    assert auth.REVENUE_SELECTION_AUTHORIZATIONS == auth.AUTHORIZATION_WITHDRAWALS == ()
    assert registry.REVENUE_EQUIVALENCES == frozenset()
    with pytest.raises(lifecycle.LaunchRejected): launcher.launch(s.profile)


@pytest.mark.parametrize("sid", [None, "", "claimed-user", "S-1-5-21-999"])
def test_wrong_or_unverifiable_token_identity(synthetic, isolated, sid):
    isolated.setattr(operators, "_process_token_sid", lambda: sid)
    with pytest.raises(lifecycle.LaunchRejected): launcher.launch(synthetic.profile)
    assert "fresh_session" not in synthetic.events and "server_enter" not in synthetic.events


@pytest.mark.parametrize("field,value", [
    ("version", True), ("operator_sids", []), ("approval", {"permission": "denominator:gross_margin"}),
    ("approval_sha256", "0" * 64), ("evidence_policy_sha256", "0" * 64),
    ("python_executable", "relative.exe"), ("import_roots", []), ("original_store", "relative"),
    ("protected_files", []), ("claimed_sid", "S-1-5-21-999"),
])
def test_unsafe_modified_or_spoofed_profile(synthetic, field, value):
    synthetic.profile_data[field] = value
    synthetic.profile.write_text(json.dumps(synthetic.profile_data), encoding="utf-8")
    with pytest.raises(lifecycle.LaunchRejected): launcher.launch(synthetic.profile)
    assert "fresh_session" not in synthetic.events


def test_missing_profile_and_changed_deployment_file(synthetic):
    synthetic.profile.unlink()
    with pytest.raises(FileNotFoundError): launcher.launch(synthetic.profile)


def test_changed_deployment_file_rejected(synthetic):
    Path(synthetic.profile_data["protected_files"][0]["path"]).write_text("changed", encoding="utf-8")
    with pytest.raises(lifecycle.LaunchRejected, match="deployment_file_changed"):
        launcher.launch(synthetic.profile)


def test_duplicate_profile_keys_rejected(synthetic):
    raw = synthetic.profile.read_text(encoding="utf-8")
    synthetic.profile.write_text(raw[:-1] + ', "version": 1}', encoding="utf-8")
    with pytest.raises(lifecycle.LaunchRejected, match="ambiguous_launch_profile"):
        launcher.launch(synthetic.profile)


def test_lost_maintenance_lease_before_publication_fails_closed(synthetic, isolated):
    verify = adapter._verify_policy
    def lose(*args, **kwargs):
        result = verify(*args, **kwargs)
        synthetic.maintenance = False
        return result
    isolated.setattr(adapter, "_verify_policy", lose)
    with pytest.raises(lifecycle.LaunchRejected, match="maintenance_lease_lost"):
        launcher.launch(synthetic.profile)
    assert auth.DENOMINATOR_AUTHORIZATIONS == adapter.PRODUCTION_EVIDENCE_POLICIES == ()
    assert "server_enter" not in synthetic.events


@pytest.mark.parametrize("field", ["DENOMINATOR_AUTHORIZATIONS", "AUTHORIZATION_WITHDRAWALS",
    "REVENUE_SELECTION_AUTHORIZATIONS", "PRODUCTION_EVIDENCE_POLICIES", "REVENUE_EQUIVALENCES"])
def test_exact_post_publication_verification_rejects_extra_or_missing_entries(synthetic, isolated, field):
    original = activation.activate_aapl_net_margin
    def changed(**kwargs):
        result = original(**kwargs)
        module = adapter if field == "PRODUCTION_EVIDENCE_POLICIES" else registry if field == "REVENUE_EQUIVALENCES" else auth
        value = ("unexpected synthetic entry",) if field != "DENOMINATOR_AUTHORIZATIONS" else ()
        setattr(module, field, value)
        return result
    isolated.setattr(activation, "activate_aapl_net_margin", changed)
    with pytest.raises(lifecycle.LaunchRejected, match="unexpected_final_registries"):
        launcher.launch(synthetic.profile)
    assert "server_enter" not in synthetic.events


@pytest.mark.parametrize("boundary,reason", [("_verify_protected_profile", "protected_profile_acl"),
    ("_verify_deployment_integrity", "deployment_integrity|protected_profile_acl"), ("maintenance_exclusion", "maintenance_exclusion")])
def test_uncommissioned_security_controls_fail_closed(synthetic, isolated, boundary, reason):
    # Reload only this module to restore the actual rejecting production boundary.
    actual = importlib.reload(operators)
    real_boundary = getattr(actual, boundary)
    isolated.setattr(operators, "_process_token_sid", lambda: synthetic.sid)
    isolated.setattr(operators, "_verify_protected_profile", lambda *a: None)
    isolated.setattr(operators, "_verify_deployment_integrity", lambda *a: None)
    isolated.setattr(operators, boundary, real_boundary)
    with pytest.raises(lifecycle.LaunchRejected, match=reason): launcher.launch(synthetic.profile)
    assert "fresh_session" not in synthetic.events


@pytest.mark.parametrize("key,value", [("WEB_CONCURRENCY", "2"), ("UVICORN_WORKERS", "2"),
    ("UVICORN_RELOAD", "true"), ("UVICORN_FACTORY", "true"), ("UVICORN_FD", "3"),
    ("UVICORN_UDS", "socket"), ("LISTEN_FDS", "1"), ("LISTEN_PID", "123")])
def test_conflicting_server_environment_rejected(synthetic, isolated, key, value):
    isolated.setenv(key, value)
    with pytest.raises(lifecycle.LaunchRejected, match="conflicting_server_environment"):
        launcher.launch(synthetic.profile)
    assert not synthetic.events


@pytest.mark.parametrize("change", ["evidence", "manifest", "approval", "versions", "publication", "withdrawal"])
def test_fresh_validation_failures_cannot_serve(synthetic, isolated, change):
    s = synthetic
    if change == "evidence": s.artifact.write_bytes(b"changed synthetic evidence")
    if change == "manifest": s.facts.pop()
    if change == "approval": isolated.setattr(proposal, "PROPOSED_DENOMINATOR_AUTHORIZATION", replace(s.record, reviewed_scope="changed"))
    if change == "versions": s.state.facts_version = 1
    if change == "publication": s.publications[0].data_version = 1
    if change == "withdrawal": isolated.setattr(auth, "AUTHORIZATION_WITHDRAWALS", (auth.AuthorizationWithdrawal(s.record.ref, "revoked", "Synthetic withdrawal"),))
    with pytest.raises((lifecycle.LaunchRejected, adapter.EvidenceRejected)):
        launcher.launch(s.profile)
    assert "server_enter" not in s.events
    assert lifecycle._controller.phase is lifecycle.Phase.FAILED


@pytest.mark.parametrize("stage", ["before", "after"])
@pytest.mark.parametrize("cleanup_failure", [False, True])
@pytest.mark.parametrize("failure_type", [KeyboardInterrupt, RuntimeError, SystemExit])
def test_publication_and_secondary_cleanup_faults_never_serve_or_retry(synthetic, isolated, cleanup_failure, failure_type, stage):
    s = synthetic
    previous = auth.DENOMINATOR_AUTHORIZATIONS, adapter.PRODUCTION_EVIDENCE_POLICIES
    class FaultingAuth(type(auth)):
        def __setattr__(self, name, value):
            if name == "DENOMINATOR_AUTHORIZATIONS":
                if value:
                    if stage == "after": super().__setattr__(name, value)
                    assert lifecycle._controller.phase is lifecycle.Phase.PUBLISHING
                    # Previously constructed and new financial consumers abstain.
                    with pytest.raises(lifecycle.LaunchRejected): FinancialMetrics(s.company, s.facts)
                    raise failure_type("synthetic publication fault")
                if cleanup_failure and getattr(self, name):
                    assert lifecycle._controller.phase is lifecycle.Phase.FAILED
                    raise KeyboardInterrupt("synthetic secondary cleanup fault")
            super().__setattr__(name, value)
    isolated.setattr(auth, "__class__", FaultingAuth)
    with pytest.raises((KeyboardInterrupt, RuntimeError, SystemExit)): launcher.launch(s.profile)
    assert "server_enter" not in s.events and lifecycle._controller.phase is lifecycle.Phase.FAILED
    if not cleanup_failure or stage == "before":
        assert auth.DENOMINATOR_AUTHORIZATIONS is previous[0]
        assert adapter.PRODUCTION_EVIDENCE_POLICIES is previous[1]
    with pytest.raises(lifecycle.LaunchRejected): launcher.launch(s.profile)
    with pytest.raises(lifecycle.LaunchRejected): load_financial_metrics(s.session, "TEST")


def test_concurrent_reader_cannot_see_complete_pair_before_publication_rollback(synthetic, isolated):
    s = synthetic
    outcomes = []
    async def forbidden(*args): pytest.fail("Partial publication reached ASGI application")
    def reader():
        try: load_financial_metrics(s.session, "TEST").summary()
        except lifecycle.LaunchRejected: outcomes.append("financial_rejected")
        app = launcher._AdmissionApp(forbidden, lifecycle._controller)
        outcomes.append(asyncio.run(request(app))[0]["status"])
        outcomes.append(asyncio.run(request(app, "websocket"))[0]["code"])
    class FaultingAuth(type(auth)):
        def __setattr__(self, name, value):
            super().__setattr__(name, value)
            if name == "DENOMINATOR_AUTHORIZATIONS" and value:
                assert adapter.PRODUCTION_EVIDENCE_POLICIES == (s.policy,)
                thread = Thread(target=reader)
                thread.start()
                thread.join(3)
                assert not thread.is_alive()
                raise KeyboardInterrupt("fault after both stores")
    isolated.setattr(auth, "__class__", FaultingAuth)
    with pytest.raises(KeyboardInterrupt): launcher.launch(s.profile)
    assert outcomes == ["financial_rejected", 503, 1013]
    assert auth.DENOMINATOR_AUTHORIZATIONS == adapter.PRODUCTION_EVIDENCE_POLICIES == ()


@pytest.mark.parametrize("consumer", [
    lambda s: FinancialMetrics(s.company, s.facts), lambda s: load_financial_metrics(s.session, "TEST"),
    lambda s: research_answer_service.answer_research_question(None, "TEST", "revenue"),
    lambda s: financial_sync_service.metric_coverage(None), lambda s: financial_sync_service.sync_catalog(None),
    lambda s: financial_analysis.get_financial_summary(None, s.company.cik),
    lambda s: adapter.load_production_evidence(None, s.company.cik, s.facts),
    lambda s: auth.authorize_denominator("net_margin", s.raw[0], s.raw[1], s.raw, s.evidence),
])
def test_direct_consumers_rejected_before_and_during_publication(synthetic, consumer):
    s = synthetic
    controller = lifecycle._claim_launch()
    for phase in (lifecycle.Phase.VALIDATING, lifecycle.Phase.PUBLISHING, lifecycle.Phase.FAILED):
        if phase is lifecycle.Phase.PUBLISHING: controller.publishing()
        if phase is lifecycle.Phase.FAILED: controller.fail()
        with pytest.raises(lifecycle.LaunchRejected): consumer(s)


def test_existing_metrics_object_cannot_calculate_during_publication(synthetic):
    service = FinancialMetrics(synthetic.company, synthetic.facts)
    controller = lifecycle._claim_launch()
    controller.publishing()
    with pytest.raises(lifecycle.LaunchRejected): service.summary()
    with pytest.raises(lifecycle.LaunchRejected): service.calculate("net_margin", (), None, ())


def test_normal_import_startup_and_financial_request_do_not_register(synthetic, isolated):
    from fastapi.testclient import TestClient
    from app import main
    isolated.setattr(activation, "activate_aapl_net_margin", lambda **k: pytest.fail("Ordinary request activated"))
    isolated.setattr(operators, "authenticate_operator", lambda *a: pytest.fail("Ordinary startup authenticated"))
    @contextmanager
    def read(*args): yield synthetic.session
    isolated.setattr(main, "read_session", read)
    with TestClient(main.app) as client:
        assert client.get("/healthz").status_code == 200
        response = client.get("/companies/TEST/financials/summary")
        assert response.status_code == 200
        assert response.json()["metrics"]["net_margin"]["status"] == "unavailable"
    assert lifecycle._controller is None
    assert auth.DENOMINATOR_AUTHORIZATIONS == adapter.PRODUCTION_EVIDENCE_POLICIES == ()


def test_active_reader_prevents_bootstrap_and_parallel_reader_cannot_enter():
    entered, release = Event(), Event()
    @lifecycle.financial_reader
    def reader():
        entered.set()
        assert release.wait(3)
    thread = Thread(target=reader)
    thread.start()
    try:
        assert entered.wait(3)
        with pytest.raises(lifecycle.LaunchRejected, match="financial_readers_present"):
            lifecycle._claim_launch()
    finally:
        release.set()
        thread.join(3)
    assert not thread.is_alive() and lifecycle._readers == 0
    with pytest.raises(lifecycle.LaunchRejected): reader()


def test_other_thread_cannot_use_validation_privilege_or_advance_lifecycle():
    controller = lifecycle._claim_launch()
    controller.bind_operator(object(), SimpleNamespace(assert_held=lambda: None, subscribe_loss=lambda callback: None))
    results = []
    @lifecycle.financial_reader
    def reader(): return True
    def worker():
        for call in (reader, controller.publishing, controller.ready):
            try: call()
            except lifecycle.LaunchRejected: results.append("rejected")
    with controller.validation_reads():
        assert reader()
        thread = Thread(target=worker)
        thread.start()
        thread.join(3)
    assert results == ["rejected"] * 3


@pytest.mark.parametrize("fault", ["startup_raise", "startup_failed", "silent_lifespan", "server", "post_registry", "app_import"])
def test_application_and_server_start_failures_are_terminal(synthetic, isolated, fault):
    s = synthetic
    async def failing_app(scope, receive, send):
        await receive()
        if fault == "startup_raise": raise KeyboardInterrupt("synthetic startup fault")
        if fault == "startup_failed": await send({"type": "lifespan.startup.failed", "message": "synthetic"})
        return
    if fault in {"startup_raise", "startup_failed", "silent_lifespan"}:
        isolated.setattr(launcher, "_load_application", lambda: failing_app)
        def runner(app):
            async def receive(): return {"type": "lifespan.startup"}
            async def send(message): pass
            asyncio.run(app({"type": "lifespan"}, receive, send))
        isolated.setattr(launcher, "_run_server", runner)
    elif fault == "server":
        isolated.setattr(launcher, "_run_server", lambda app: (_ for _ in ()).throw(RuntimeError("server fault")))
    elif fault == "app_import":
        isolated.setattr(launcher, "_load_application", lambda: (_ for _ in ()).throw(RuntimeError("import fault")))
    else:
        original = activation.activate_aapl_net_margin
        def changed(**kwargs):
            result = original(**kwargs)
            auth.REVENUE_SELECTION_AUTHORIZATIONS = ("unexpected",)
            return result
        isolated.setattr(activation, "activate_aapl_net_margin", changed)
    with pytest.raises((lifecycle.LaunchRejected, KeyboardInterrupt, RuntimeError)): launcher.launch(s.profile)
    assert lifecycle._controller.phase is lifecycle.Phase.FAILED
    with pytest.raises(lifecycle.LaunchRejected): FinancialMetrics(s.company, s.facts)


@pytest.mark.parametrize("phase", [lifecycle.Phase.VALIDATING, lifecycle.Phase.PUBLISHING,
                                   lifecycle.Phase.FAILED, lifecycle.Phase.SHUTDOWN])
def test_http_websocket_denied_outside_ready(phase):
    controller = lifecycle._claim_launch()
    if phase is lifecycle.Phase.PUBLISHING: controller.publishing()
    elif phase is lifecycle.Phase.FAILED: controller.fail()
    elif phase is lifecycle.Phase.SHUTDOWN: controller.shutdown()
    async def forbidden(*args): pytest.fail("Unready app dispatched")
    wrapped = launcher._AdmissionApp(forbidden, controller)
    assert asyncio.run(request(wrapped))[0]["status"] == 503
    assert asyncio.run(request(wrapped, "websocket"))[0]["code"] == 1013


def test_lifecycle_sealing_and_shutdown_cannot_be_reversed():
    controller = lifecycle._claim_launch()
    controller.bind_operator(object(), SimpleNamespace(assert_held=lambda: None, subscribe_loss=lambda callback: None))
    controller.publishing()
    with pytest.raises(lifecycle.LaunchRejected): controller.ready()
    controller.seal()
    with pytest.raises(lifecycle.LaunchRejected): controller.seal()
    controller.ready()
    with pytest.raises(lifecycle.LaunchRejected): controller.publishing()
    with pytest.raises(lifecycle.LaunchRejected): controller.ready()
    controller.shutdown()
    with pytest.raises(lifecycle.LaunchRejected): controller.ready()


def test_real_runner_uses_app_object_single_worker_no_factory_sockets_or_child(isolated):
    import uvicorn
    captured = {}
    app = object()
    def config(application, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(app=application, **kwargs, fd=None, uds=None)
    class Server:
        started = True
        def __init__(self, configuration): assert configuration.app is app
        def run(self, **kwargs): captured.update(kwargs)
    isolated.setattr(uvicorn, "Config", config)
    isolated.setattr(uvicorn, "Server", Server)
    launcher._run_server(app)
    assert captured == dict(host="127.0.0.1", port=8000, workers=1, reload=False, factory=False,
                            lifespan="on", sockets=None)


@pytest.mark.parametrize("field,value", [("workers", 2), ("reload", True), ("factory", True),
                                       ("fd", 3), ("uds", "inherited"), ("lifespan", "auto")])
def test_runner_rejects_mutated_effective_configuration(isolated, field, value):
    import uvicorn
    def config(application, **kwargs):
        options = dict(app=application, **kwargs, fd=None, uds=None)
        options[field] = value
        return SimpleNamespace(**options)
    isolated.setattr(uvicorn, "Config", config)
    isolated.setattr(uvicorn, "Server", lambda *a: pytest.fail("Unsafe server constructed"))
    with pytest.raises(lifecycle.LaunchRejected, match="conflicting_server_configuration"):
        launcher._run_server(object())


def test_failure_after_ready_prevents_further_response_admission(synthetic, isolated):
    async def application(scope, receive, send):
        await receive()
        await send({"type": "lifespan.startup.complete"})
        raise RuntimeError("synthetic post-startup failure")
    wrapped = []
    def runner(app):
        wrapped.append(app)
        async def receive(): return {"type": "lifespan.startup"}
        async def send(message): pass
        asyncio.run(app({"type": "lifespan"}, receive, send))
    isolated.setattr(launcher, "_load_application", lambda: application)
    isolated.setattr(launcher, "_run_server", runner)
    with pytest.raises(RuntimeError): launcher.launch(synthetic.profile)
    assert asyncio.run(request(wrapped[0]))[0]["status"] == 503
    with pytest.raises(lifecycle.LaunchRejected): FinancialMetrics(synthetic.company, synthetic.facts)


def test_startup_registry_mutation_is_rejected_before_ready(synthetic, isolated):
    async def application(scope, receive, send):
        await receive()
        auth.DENOMINATOR_AUTHORIZATIONS = ()
        await send({"type": "lifespan.startup.complete"})
        pytest.fail("Mutated registry became ready")
    def runner(app):
        async def receive(): return {"type": "lifespan.startup"}
        async def send(message): pytest.fail("Failed startup acknowledged")
        asyncio.run(app({"type": "lifespan"}, receive, send))
    isolated.setattr(launcher, "_load_application", lambda: application)
    isolated.setattr(launcher, "_run_server", runner)
    with pytest.raises(lifecycle.LaunchRejected, match="unexpected_final_registries"):
        launcher.launch(synthetic.profile)
    assert lifecycle._controller.phase is lifecycle.Phase.FAILED


def test_quarantine_marking_fault_cannot_bypass_asgi_termination(isolated):
    controller = lifecycle._claim_launch()
    attempted = []
    isolated.setattr(controller, "fail", lambda: (_ for _ in ()).throw(KeyboardInterrupt("repeated fault")))
    isolated.setattr(launcher, "_abort_process", lambda: attempted.append("terminate"))
    async def bad(*args): raise RuntimeError("application startup")
    async def drive():
        async def receive(): return {"type": "lifespan.startup"}
        async def send(message): pass
        controller.publishing()
        await launcher._AdmissionApp(bad, controller)({"type": "lifespan"}, receive, send)
    with pytest.raises(KeyboardInterrupt): asyncio.run(drive())
    assert attempted == ["terminate"]


def test_failed_operator_cli_terminates_nonzero_without_io_or_listener():
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    process = subprocess.run([sys.executable, "-B", "-m", "app.aapl_net_margin_launcher", "--profile", "unused"],
                             cwd=Path(__file__).parents[1], env=env, capture_output=True, timeout=15)
    assert process.returncode == 78 and process.stdout == process.stderr == b""


def test_secondary_fault_cli_exits_without_retry_or_server_subprocess():
    # Synthetic helper fault in a disposable process; never register real records.
    script = '''
from contextlib import contextmanager
from app import aapl_net_margin_launcher as l, aapl_net_margin_activation as a, aapl_operator_policy as o
a._ACTIVATION_ENABLED = True
o.authenticate_operator = lambda path: object()
from types import SimpleNamespace
@contextmanager
def lease(policy): yield SimpleNamespace(assert_held=lambda: None, subscribe_loss=lambda callback: None)
o.maintenance_exclusion = lease
def failure(**kwargs): raise KeyboardInterrupt("synthetic cleanup failure")
a.activate_aapl_net_margin = failure
l._run_server = lambda app: print("UNSAFE SERVER")
l.main()
print("UNSAFE CONTINUATION")
'''
    env = {k: v for k, v in os.environ.items() if not k.startswith("UVICORN_") and k not in
           {"WEB_CONCURRENCY", "LISTEN_FDS", "LISTEN_PID", "LISTEN_FDNAMES"}}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    process = subprocess.run([sys.executable, "-B", "-c", script, "--profile", "synthetic"],
                             cwd=Path(__file__).parents[1], env=env, capture_output=True, timeout=15)
    assert process.returncode == 78 and process.stdout == process.stderr == b""
