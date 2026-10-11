"""Disabled, explicit operator bootstrap. Never imported/called by app.main.

The launcher cannot configure or enable authorization. Deployment ACL/integrity
and maintenance verification are uncommissioned and reject real launches.
"""
import os

from app import activation_lifecycle as lifecycle


def _abort_process():
    os._exit(78)


def _verify_registries():
    from app import aapl_net_margin_proposal as proposal
    from app import revenue_scope_authorizations as auth, sec_evidence_adapter as evidence
    from app import financial_metric_registry as registry
    if (auth.REVENUE_SELECTION_AUTHORIZATIONS != () or auth.AUTHORIZATION_WITHDRAWALS != ()
            or auth.DENOMINATOR_AUTHORIZATIONS != (proposal.PROPOSED_DENOMINATOR_AUTHORIZATION,)
            or evidence.PRODUCTION_EVIDENCE_POLICIES != (proposal.PROPOSED_EVIDENCE_POLICY,)
            or registry.REVENUE_EQUIVALENCES != frozenset()):
        raise lifecycle.LaunchRejected("unexpected_final_registries")
    record = proposal.PROPOSED_DENOMINATOR_AUTHORIZATION
    active, error = auth._approval((record,), record.ref.permission, (record,))
    if active != record or error is not None:
        raise lifecycle.LaunchRejected(error or "invalid_final_approval")


class _AdmissionApp:
    def __init__(self, app, controller):
        self.app, self.controller = app, controller

    async def __call__(self, scope, receive, send):
        controller = self.controller
        kind = scope["type"]
        if kind == "lifespan":
            started, stopped = False, False

            async def lifecycle_receive():
                nonlocal stopped
                message = await receive()
                if message["type"] == "lifespan.shutdown":
                    stopped = True
                    controller.shutdown()  # Deny admission before application cleanup.
                return message

            async def lifecycle_send(message):
                nonlocal started
                event = message["type"]
                if event == "lifespan.startup.complete":
                    controller.require_authority()
                    _verify_registries()
                    controller.ready()
                    started = True
                elif event in {"lifespan.startup.failed", "lifespan.shutdown.failed"}:
                    try:
                        controller.fail()
                    finally:
                        _abort_process()
                elif event == "lifespan.shutdown.complete":
                    controller.shutdown()
                await send(message)

            try:
                controller.require_owner(lifecycle.Phase.PUBLISHING)
                await self.app(scope, lifecycle_receive, lifecycle_send)
                if not started or not stopped:
                    raise lifecycle.LaunchRejected("incomplete_application_lifespan")
            except BaseException:
                try:
                    controller.fail()
                finally:
                    # Lifespan runs in a background task: raising alone need not
                    # stop Uvicorn after startup has completed.
                    _abort_process()
                raise
            return
        if kind not in {"http", "websocket"}:
            controller.fail()
            raise lifecycle.LaunchRejected("unsupported_asgi_scope")
        if not controller.admits():
            if kind == "http":
                await send({"type": "http.response.start", "status": 503,
                            "headers": [(b"content-type", b"application/json")]})
                await send({"type": "http.response.body", "body": b'{"detail":"Financial service not ready"}'})
            else:
                await send({"type": "websocket.close", "code": 1013})
            return

        async def admitted_send(message):
            if not controller.admits():
                raise lifecycle.LaunchRejected("financial_service_not_ready")
            await send(message)
            # Transport bytes already accepted cannot be retracted. Rechecking
            # catches ownership loss inside an awaited send before further work.
            if not controller.admits():
                raise lifecycle.LaunchRejected("financial_service_not_ready")

        async def admitted_receive():
            if not controller.admits():
                raise lifecycle.LaunchRejected("financial_service_not_ready")
            message = await receive()
            if not controller.admits():
                raise lifecycle.LaunchRejected("financial_service_not_ready")
            return message

        try:
            await self.app(scope, admitted_receive, admitted_send)
        except BaseException:
            try:
                controller.fail()
            finally:
                _abort_process()
            raise


def _server_environment():
    # Reject ambient Uvicorn/process-manager overrides instead of interpreting
    # booleans, worker counts, app import strings or inherited socket descriptors.
    forbidden = {"WEB_CONCURRENCY", "LISTEN_FDS", "LISTEN_PID", "LISTEN_FDNAMES"}
    if any(k.startswith("UVICORN_") or k in forbidden for k in os.environ):
        raise lifecycle.LaunchRejected("conflicting_server_environment")


def _load_application():
    from app.main import app
    return app


def _run_server(application):
    from uvicorn import Config, Server
    configuration = Config(application, host="127.0.0.1", port=8000, workers=1,
                           reload=False, factory=False, lifespan="on")
    if (configuration.app is not application or configuration.workers != 1
            or configuration.reload is not False or configuration.factory is not False
            or configuration.lifespan != "on" or configuration.fd is not None
            or configuration.uds is not None):
        raise lifecycle.LaunchRejected("conflicting_server_configuration")
    server = Server(configuration)
    server.run(sockets=None)  # In this interpreter; never uvicorn's multiprocess CLI.
    if not server.started:
        raise lifecycle.LaunchRejected("server_did_not_start")


def launch(profile_path):
    """Explicit process-local entry, no caller identity/options/trust injections."""
    controller = None
    try:
        controller = lifecycle._claim_launch()
        from app import aapl_net_margin_activation as activation
        if activation._ACTIVATION_ENABLED is not True:
            raise lifecycle.LaunchRejected("production_activation_disabled")
        _server_environment()
        from app import aapl_operator_policy as operators, aapl_net_margin_proposal as proposal
        policy = operators.authenticate_operator(profile_path)
        # Hold independently verified exclusion through application readiness.
        # Publication remains before any server is constructed or run.
        with operators.maintenance_exclusion(policy) as lease:
            controller.bind_operator(policy, lease)
            with controller.validation_reads():
                if activation.activate_aapl_net_margin(operator_authorized=True, reviewed_ref=proposal.REF) is not True:
                    raise lifecycle.LaunchRejected("activation_not_published")
            _verify_registries()
            controller.require_authority()
            controller.seal()
            application = _AdmissionApp(_load_application(), controller)
            _run_server(application)
            if controller.phase is not lifecycle.Phase.SHUTDOWN:
                raise lifecycle.LaunchRejected("incomplete_server_lifecycle")
        return 0
    except BaseException:
        # A second initialization also quarantines the existing process. No
        # cleanup, logging, fallback app or retry may make it ready again.
        current = controller or lifecycle._controller
        if current is not None:
            current.fail()
        raise


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Disabled reviewed AAPL operator launcher")
    parser.add_argument("--profile", required=True)
    try:
        args = parser.parse_args()
        return launch(args.profile)
    except BaseException:
        # Hard fail-stop, including secondary cleanup/KeyboardInterrupt/SystemExit.
        # No exception text/profile/credentials are logged; diagnostics cannot
        # interrupt exit. Supervisors require fresh-process operator-owned retries.
        _abort_process()
        raise SystemExit(78)  # Still terminal if a broken terminator returns.


if __name__ == "__main__":
    raise SystemExit(main())
