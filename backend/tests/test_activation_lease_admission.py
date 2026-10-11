"""Post-READY lease faults with synthetic ownership and fake consumers only."""
import asyncio
from contextlib import contextmanager
from pathlib import Path
import os
import subprocess
import sys
from threading import Barrier, Lock, Thread
from types import SimpleNamespace

import pytest

from app import activation_lifecycle as lifecycle, aapl_net_margin_launcher as launcher
from app import financial_analysis, research_answer_service, financial_sync_service
from app import sec_evidence_adapter as adapter, revenue_scope_authorizations as auth
from app.financial_metrics_service import FinancialMetrics, load_financial_metrics
from test_aapl_activation_safety import isolated, synthetic, inactive


class SyntheticLease:
    """Monotonic authoritative fake; notify outside its own lock to avoid inversion."""
    def __init__(self):
        self.lock = Lock()
        self.failure = None
        self.callbacks = []
        self.checks = 0

    def assert_held(self):
        with self.lock:
            self.checks += 1
            if self.failure is not None:
                raise self.failure

    def subscribe_loss(self, callback):
        with self.lock:
            self.callbacks.append(callback)
            failure = self.failure
        if failure is not None:
            callback(failure)

    def lose(self, failure=None, *, notify=True):
        with self.lock:
            if self.failure is None:
                self.failure = failure or RuntimeError("synthetic lease revoked")
            callbacks, failure = tuple(self.callbacks), self.failure
        if notify:
            for callback in callbacks:
                callback(failure)


@pytest.fixture
def ready(isolated):
    controller = lifecycle._claim_launch()
    lease = SyntheticLease()
    controller.bind_operator(object(), lease)
    controller.publishing()
    controller.seal()
    controller.ready()
    return controller, lease


async def invoke(app, kind="http", messages=None):
    messages = [] if messages is None else messages
    async def receive():
        return {"type": "http.request" if kind == "http" else "websocket.receive"}
    async def send(message): messages.append(message)
    await app({"type": kind}, receive, send)
    return messages


def test_valid_lease_is_checked_on_admission_receive_and_delivery(ready):
    controller, lease = ready
    before = lease.checks
    async def consumer(scope, receive, send):
        await receive()
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"synthetic financial result"})
    messages = asyncio.run(invoke(launcher._AdmissionApp(consumer, controller)))
    assert messages[-1]["body"] == b"synthetic financial result"
    assert lease.checks >= before + 7  # Admission + receive/send before and after.
    assert controller.phase is lifecycle.Phase.READY


@pytest.mark.parametrize("kind", ["http", "websocket"])
def test_loss_after_ready_before_admission(ready, kind):
    controller, lease = ready
    failure = RuntimeError("synthetic revoked before admission")
    lease.lose(failure, notify=False)  # Missing/delayed monitor still fails on poll.
    messages = []
    async def consumer(*args): pytest.fail("Lost lease admitted consumer")
    with pytest.raises(RuntimeError) as caught:
        asyncio.run(invoke(launcher._AdmissionApp(consumer, controller), kind, messages))
    assert caught.value is failure and not messages
    assert controller.phase is lifecycle.Phase.FAILED
    assert controller.lease_failure is failure


@pytest.mark.parametrize("consumer", [
    lambda: FinancialMetrics(SimpleNamespace(cik="0000000001", ticker="TEST"), []),
    lambda: load_financial_metrics(None, "TEST"),
    lambda: financial_analysis.get_financial_summary(None, "0000000001"),
    lambda: research_answer_service.answer_research_question(None, "TEST", "net margin"),
    lambda: financial_sync_service.metric_coverage(None),
    lambda: adapter.load_production_evidence(None, "0000000001", []),
    lambda: auth.authorize_denominator("net_margin", None, None, (), ()),
])
def test_loss_before_maintained_direct_financial_entry(ready, consumer):
    controller, lease = ready
    lease.lose(notify=False)
    with pytest.raises(RuntimeError): consumer()
    assert controller.phase is lifecycle.Phase.FAILED


def test_loss_during_calculation_withholds_computed_return_value(ready):
    controller, lease = ready
    computed, exposed = [], []
    @lifecycle.financial_reader
    def calculate():
        computed.append(42)
        lease.lose(notify=False)
        return 42
    with pytest.raises(RuntimeError): exposed.append(calculate())
    assert computed == [42] and exposed == [] and lifecycle._readers == 0
    assert controller.phase is lifecycle.Phase.FAILED


def test_notification_during_calculation_cannot_be_caught_to_return_value(ready):
    controller, lease = ready
    @lifecycle.financial_reader
    def calculate():
        try: lease.lose()
        except RuntimeError: pass  # A fake terminator returning cannot revive admission.
        return 42
    with pytest.raises(lifecycle.LaunchRejected): calculate()
    assert controller._poisoned and controller.phase is lifecycle.Phase.FAILED


def test_loss_after_calculation_before_delivery(ready):
    controller, lease = ready
    computed, messages = [], []
    @lifecycle.financial_reader
    def calculate(): return 42
    async def consumer(scope, receive, send):
        computed.append(calculate())
        lease.lose(notify=False)
        await send({"type": "http.response.body", "body": b"42"})
    with pytest.raises(RuntimeError):
        asyncio.run(invoke(launcher._AdmissionApp(consumer, controller), messages=messages))
    assert computed == [42] and messages == []


def test_loss_between_response_sends_withholds_next_body(ready):
    controller, lease = ready
    messages = []
    async def consumer(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        lease.lose(notify=False)
        await send({"type": "http.response.body", "body": b"undelivered financial result"})
    with pytest.raises(RuntimeError):
        asyncio.run(invoke(launcher._AdmissionApp(consumer, controller), messages=messages))
    assert messages == [{"type": "http.response.start", "status": 200, "headers": []}]


def test_loss_inside_send_cannot_retract_accepted_bytes_but_stops_next_send(ready):
    controller, lease = ready
    accepted, continued = [], []
    async def consumer(scope, receive, send):
        await send({"type": "http.response.body", "body": b"already accepted by transport", "more_body": True})
        continued.append(True)
        await send({"type": "http.response.body", "body": b"next body"})
    async def drive():
        async def receive(): return {"type": "http.request"}
        async def transport(message):
            accepted.append(message)
            lease.lose(notify=False)
        await launcher._AdmissionApp(consumer, controller)({"type": "http"}, receive, transport)
    with pytest.raises(RuntimeError): asyncio.run(drive())
    assert len(accepted) == 1 and not continued


@pytest.mark.parametrize("boundary", ["receive", "send"])
def test_loss_during_established_websocket(boundary, ready):
    controller, lease = ready
    delivered = []
    async def consumer(scope, receive, send):
        await send({"type": "websocket.accept"})
        if boundary == "receive":
            await receive()
        else:
            lease.lose(notify=False)
        await send({"type": "websocket.send", "text": "financial result"})
    async def drive():
        async def receive():
            lease.lose(notify=False)
            return {"type": "websocket.receive", "text": "next question"}
        async def send(message): delivered.append(message)
        await launcher._AdmissionApp(consumer, controller)({"type": "websocket"}, receive, send)
    with pytest.raises(RuntimeError): asyncio.run(drive())
    assert delivered == [{"type": "websocket.accept"}]


@pytest.mark.parametrize("failure", [RuntimeError("expired"), RuntimeError("renewal failed"),
    OSError("ownership unverifiable"), KeyboardInterrupt("ownership probe interrupted")])
def test_expiry_renewal_and_unverifiable_ownership_are_terminal(ready, failure):
    controller, lease = ready
    lease.lose(failure, notify=False)
    with pytest.raises(type(failure)) as caught: controller.admits()
    assert caught.value is failure and controller.lease_failure is failure
    assert not controller.admits()
    with pytest.raises(lifecycle.LaunchRejected): controller.ready()
    with pytest.raises(lifecycle.LaunchRejected): lifecycle._claim_launch()


def test_idle_notification_quarantines_without_new_requests(ready, isolated):
    controller, lease = ready
    terminations = []
    isolated.setattr(launcher, "_abort_process", lambda: terminations.append(78))
    with pytest.raises(RuntimeError): lease.lose()
    assert controller.phase is lifecycle.Phase.FAILED and terminations == [78]


def test_quarantine_marking_fault_preserves_first_cause_and_poison_latch(ready, isolated):
    controller, lease = ready
    failure, marking = OSError("lost owner"), KeyboardInterrupt("marking failed")
    terminations = []
    isolated.setattr(controller, "fail", lambda: (_ for _ in ()).throw(marking))
    isolated.setattr(launcher, "_abort_process", lambda: terminations.append(78))
    lease.lose(failure, notify=False)
    with pytest.raises(OSError) as caught: controller.admits()
    assert caught.value is failure
    assert controller.lease_failure is failure and controller.quarantine_failure is marking
    assert controller._poisoned and controller.phase is lifecycle.Phase.FAILED
    assert not controller.admits() and terminations == [78]
    with pytest.raises(lifecycle.LaunchRejected): controller.ready()
    with pytest.raises(lifecycle.LaunchRejected): controller.publishing()
    with pytest.raises(lifecycle.LaunchRejected): lifecycle._claim_launch()


def test_repeated_notifications_or_attempted_renewal_cannot_revive(ready):
    controller, lease = ready
    first = OSError("first ownership failure")
    for failure in (first, RuntimeError("later failure"), KeyboardInterrupt("repeated interruption")):
        with pytest.raises(OSError): lease.lose(failure)
    # Even a defective fake provider becoming valid again cannot erase the latch.
    lease.failure = None
    assert controller.lease_failure is first and not controller.admits()
    with pytest.raises(lifecycle.LaunchRejected): controller.ready()


def test_loss_and_shutdown_race_is_terminal_and_has_no_deadlock(ready):
    controller, lease = ready
    barrier, outcomes = Barrier(2), []
    def lose():
        barrier.wait(timeout=3)
        try: lease.lose()
        except RuntimeError: outcomes.append("loss")
    thread = Thread(target=lose)
    thread.start()
    barrier.wait(timeout=3)
    try: controller.shutdown()
    except RuntimeError: outcomes.append("shutdown_check_failed")
    thread.join(3)
    assert not thread.is_alive() and outcomes.count("loss") == 1
    assert controller._poisoned and not controller.admits()


def test_already_revoked_lease_cannot_cross_subscription_or_ready_gap():
    controller, lease = lifecycle._claim_launch(), SyntheticLease()
    lease.lose(notify=False)
    with pytest.raises(RuntimeError): controller.bind_operator(object(), lease)
    assert controller._poisoned
    with pytest.raises(lifecycle.LaunchRejected): controller.publishing()


def test_loss_racing_ready_transition_cannot_admit_afterward(isolated):
    controller, lease = lifecycle._claim_launch(), SyntheticLease()
    controller.bind_operator(object(), lease)
    controller.publishing()
    controller.seal()
    checked, revoked = Barrier(2), Barrier(2)
    original = lease.assert_held
    def check():
        original()
        checked.wait(timeout=3)
        revoked.wait(timeout=3)
    isolated.setattr(lease, "assert_held", check)
    outcomes = []
    def lose():
        checked.wait(timeout=3)
        lease.lose(notify=False)
        revoked.wait(timeout=3)
        try: controller._lease_lost(lease.failure)
        except RuntimeError: outcomes.append("lost")
    thread = Thread(target=lose)
    thread.start()
    try:
        controller.ready()  # External state may change after a successful check.
    finally:
        thread.join(3)
    assert not thread.is_alive() and outcomes == ["lost"]
    assert controller.phase is lifecycle.Phase.FAILED and not controller.admits()


def test_error_exit_also_detects_ownership_loss(ready):
    controller, lease = ready
    @lifecycle.financial_reader
    def calculate():
        lease.lose(notify=False)
        raise ValueError("synthetic calculation error")
    with pytest.raises(RuntimeError): calculate()
    assert controller.phase is lifecycle.Phase.FAILED and lifecycle._readers == 0


@pytest.mark.parametrize("value", [False, True, "valid"])
def test_assertion_return_claim_is_not_authoritative_validity(value):
    controller = lifecycle._claim_launch()
    lease = SimpleNamespace(assert_held=lambda: value, subscribe_loss=lambda callback: None)
    with pytest.raises(lifecycle.LaunchRejected, match="unverifiable_maintenance_ownership"):
        controller.bind_operator(object(), lease)


def test_missing_loss_monitor_is_rejected():
    controller = lifecycle._claim_launch()
    with pytest.raises(lifecycle.LaunchRejected, match="unverified_operator_boundary"):
        controller.bind_operator(object(), SimpleNamespace(assert_held=lambda: None))


def test_inactive_financial_entry_exit_needs_no_lease_or_extra_evidence(isolated):
    isolated.setattr(lifecycle._Controller, "require_authority", lambda self: pytest.fail("Inactive lease check"))
    isolated.setattr(adapter, "_read", lambda *a: pytest.fail("Inactive evidence I/O"))
    service = FinancialMetrics(SimpleNamespace(cik="0000000001", ticker="TEST", name="Synthetic"), [])
    assert service.summary().metrics["net_margin"].status == "unavailable"
    assert adapter.load_production_evidence(object(), "0000000001", []) == ()
    inactive()


def test_operator_launch_post_ready_loss_reaches_no_successful_serving(synthetic, isolated):
    lease = SyntheticLease()
    @contextmanager
    def exclusion(policy): yield lease
    from app import aapl_operator_policy as operators
    isolated.setattr(operators, "maintenance_exclusion", exclusion)
    def server(app):
        # Fake successful startup then revoke before a financial request.
        app.controller.ready()
        lease.lose(notify=False)
        async def consumer(*args): pytest.fail("Lease-loss server served")
        asyncio.run(invoke(launcher._AdmissionApp(consumer, app.controller)))
    isolated.setattr(launcher, "_run_server", server)
    with pytest.raises(RuntimeError): launcher.launch(synthetic.profile)
    assert lifecycle._controller._poisoned
    with pytest.raises(lifecycle.LaunchRejected): launcher.launch(synthetic.profile)


@pytest.mark.parametrize("mode", ["check", "notification"])
@pytest.mark.parametrize("marking_fault", [False, True])
def test_post_ready_lease_loss_genuinely_terminates_process(marking_fault, mode):
    # No gate enabling or registry installation, even in the child interpreter.
    script = '''
from types import SimpleNamespace
from app import activation_lifecycle as c, aapl_net_margin_activation as a
from app import revenue_scope_authorizations as r, sec_evidence_adapter as e
assert a._ACTIVATION_ENABLED is False
assert r.DENOMINATOR_AUTHORIZATIONS == r.REVENUE_SELECTION_AUTHORIZATIONS == r.AUTHORIZATION_WITHDRAWALS == e.PRODUCTION_EVIDENCE_POLICIES == ()
state = {"valid": True}
callbacks = []
def held():
    if not state["valid"]: raise OSError("synthetic lost owner")
x = c._claim_launch()
def subscribe(callback): callbacks.append(callback)
x.bind_operator(object(), SimpleNamespace(assert_held=held, subscribe_loss=subscribe))
x.publishing(); x.seal(); x.ready()
if MARKING:
    def fail(): raise KeyboardInterrupt("synthetic quarantine fault")
    x.fail = fail
state["valid"] = False
if NOTIFY:
    callbacks[0](OSError("synthetic idle lease loss"))
else:
    x.admits()
print("UNSAFE CONTINUATION")
'''.replace("MARKING", str(marking_fault)).replace("NOTIFY", str(mode == "notification"))
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    child = subprocess.run([sys.executable, "-B", "-c", script], cwd=Path(__file__).parents[1],
                           env=env, capture_output=True, timeout=15)
    assert child.returncode == 78 and child.stdout == child.stderr == b""
