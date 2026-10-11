"""One-shot process-local bootstrap admission; no activation on import.

This constrains maintained financial entry points, not arbitrary Python execution
or unlocked mutation by trusted code. Ordinary inactive processes stay concurrent.
"""
from contextlib import contextmanager
from enum import Enum
from functools import wraps
from threading import RLock, current_thread


class LaunchRejected(RuntimeError):
    pass


class Phase(Enum):
    VALIDATING = "validating"
    PUBLISHING = "publishing"
    READY = "ready"
    FAILED = "failed"
    SHUTDOWN = "shutdown"


_lock = RLock()
_controller = None
_readers = 0


class _Controller:
    def __init__(self):
        self.phase = Phase.VALIDATING
        self.owner = current_thread()
        self.validation_depth = 0
        self.verified = False
        self._policy = None
        self._lease = None
        self._poisoned = False
        self.lease_failure = None
        self.quarantine_failure = None

    def require_owner(self, phase):
        if (_controller is not self or current_thread() is not self.owner
                or self.phase is not phase or self._poisoned):
            raise LaunchRejected("invalid_launch_lifecycle")

    def bind_operator(self, policy, lease):
        # Private launcher wiring, not authentication by Python object/boolean.
        # Only the real OS/deployment verifier may produce policy/lease authority.
        with _lock:
            self.require_owner(Phase.VALIDATING)
            if (self._policy is not None or policy is None
                    or not callable(getattr(lease, "assert_held", None))
                    or not callable(getattr(lease, "subscribe_loss", None))):
                raise LaunchRejected("unverified_operator_boundary")
            self._policy, self._lease = policy, lease
            # Subscribe before the first check to close the subscription gap.
            # Notifications must run outside the provider's ownership lock.
            if lease.subscribe_loss(self._lease_lost) is not None:
                self._lease_lost(LaunchRejected("unverifiable_lease_subscription"))
            self.require_authority()

    def _lease_lost(self, error):
        from app.aapl_net_margin_launcher import _abort_process
        if not isinstance(error, BaseException):
            error = LaunchRejected("maintenance_lease_lost")
        try:
            with _lock:
                # Independent irreversible latch/state: a throwing/overridden
                # fail() must not leave a previously READY lifecycle admissible.
                if self.lease_failure is None:
                    self.lease_failure = error
                self._poisoned = True
                self.phase = Phase.FAILED
            self.fail()
        except BaseException as marking_error:
            self.quarantine_failure = marking_error
        finally:
            _abort_process()
        raise self.lease_failure or error  # No continuation if a terminator returns.

    def require_authority(self):
        with _lock:
            if self._poisoned:
                raise LaunchRejected("financial_service_not_ready") from self.lease_failure
            if self._policy is None or self._lease is None:
                raise LaunchRejected("authenticated_operator_required")
            try:
                # Only None signifies success. A False/True claim is not the
                # authoritative no-exception ownership contract.
                if self._lease.assert_held() is not None:
                    raise LaunchRejected("unverifiable_maintenance_ownership")
            except BaseException as error:
                self._lease_lost(error)

    @contextmanager
    def validation_reads(self):
        with _lock:
            self.require_owner(Phase.VALIDATING)
            self.validation_depth += 1
        try:
            yield
        finally:
            with _lock:
                self.validation_depth -= 1

    def publishing(self):
        with _lock:
            self.require_owner(Phase.VALIDATING)
            if _readers:
                raise LaunchRejected("financial_readers_present")
            self.phase = Phase.PUBLISHING

    def seal(self):
        with _lock:
            self.require_owner(Phase.PUBLISHING)
            if self.verified:
                raise LaunchRejected("publication_already_sealed")
            self.verified = True

    def ready(self):
        with _lock:
            self.require_owner(Phase.PUBLISHING)
            if not self.verified:
                raise LaunchRejected("unverified_publication")
            self.require_authority()
            self.phase = Phase.READY

    def fail(self):
        with _lock:
            self._poisoned = True
            self.phase = Phase.FAILED

    def shutdown(self):
        with _lock:
            if self.phase is not Phase.FAILED:
                if self._lease is not None and not self._poisoned:
                    self.require_authority()
                self.phase = Phase.SHUTDOWN

    def admits(self):
        with _lock:
            if _controller is not self or self.phase is not Phase.READY or self._poisoned:
                return False
            self.require_authority()
            return True


def _claim_launch():
    global _controller
    with _lock:
        if _controller is not None:
            raise LaunchRejected("launch_already_initialized")
        _controller = _Controller()
        if _readers:
            _controller.fail()
            raise LaunchRejected("financial_readers_present")
        return _controller


def require_validation_owner():
    with _lock:
        if _controller is None:
            raise LaunchRejected("trusted_launcher_required")
        _controller.require_owner(Phase.VALIDATING)
        _controller.require_authority()
        return _controller


@contextmanager
def _financial_read():
    global _readers
    with _lock:
        controller = _controller
        if controller is not None:
            validating = (not controller._poisoned and controller.phase is Phase.VALIDATING
                          and controller.validation_depth > 0 and current_thread() is controller.owner)
            if validating:
                controller.require_authority()
            elif not controller.admits():
                raise LaunchRejected("financial_service_not_ready")
        _readers += 1
    try:
        yield
    finally:
        with _lock:
            try:
                # Check on both success and error exits, before a computed return
                # can escape. Already constructed metrics objects are constrained.
                if controller is not None:
                    if controller._poisoned or controller.phase not in {Phase.READY, Phase.VALIDATING}:
                        raise LaunchRejected("financial_service_not_ready") from controller.lease_failure
                    controller.require_authority()
            finally:
                _readers -= 1


def financial_reader(function):
    @wraps(function)
    def guarded(*args, **kwargs):
        with _financial_read():
            return function(*args, **kwargs)
    return guarded
