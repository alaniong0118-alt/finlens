"""Offline real JWT + existing ownership fake/ASGI loop; no provider or DB access."""
import asyncio
import base64
from contextlib import asynccontextmanager
from dataclasses import FrozenInstanceError, replace
import hashlib
import json
from pathlib import Path
import sys
from threading import Event, Thread
from unittest.mock import patch
import unittest
from urllib.parse import parse_qs, urlencode, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Existing maintained harness constructs the local asyncio wakeup loop before its
# strict audit/network/DB/private-environment guard, then installs all those guards.
from test_private_workspace_http import LOOP, CryptoFixtures, FakeDatabase, FakeRepository, own, PrivateWorkspace, COOKIE
from app import private_workspace_login as login
from app.models import ResearchAccount, ResearchSession


class LoginTests(CryptoFixtures):
    def setUp(self):
        super().setUp()
        self.db = FakeDatabase(self.clock)
        self.repository_patch = patch.object(own, "_Repository", FakeRepository)
        self.repository_patch.start(); self.addCleanup(self.repository_patch.stop)
        self.workspace = PrivateWorkspace(own.OwnershipService(self.verifier, self.db.factory,
            monotonic=lambda: self.clock.mono), origin="https://finlens.test",
            clock=lambda: self.clock.wall, monotonic=lambda: self.clock.mono)
        self.cfg = login.LoginConfiguration(self.policy, "https://offline.invalid/authorize",
            "https://offline.invalid/token", "https://finlens.test", ("finlens.private",),
            login.InviteAdmission(self.policy.issuer, frozenset({"offline-alice", "offline-bob"})))
        self.next_token, self.requests, self.exchange_hook = self.token(), [], None
        self.reply = None
        async def exchange(request):
            self.requests.append(request)
            if self.exchange_hook is not None:
                await self.exchange_hook()
            return self.reply or login.TokenReply(200, "application/json", json.dumps(dict(
                access_token=self.next_token, token_type="Bearer", expires_in=300, scope="finlens.private")).encode())
        self.app = login.PrivateWorkspaceLogin(self.workspace, configuration=self.cfg, exchange=exchange,
            clock=lambda: self.clock.wall, monotonic=lambda: self.clock.mono)

    async def request(self, method, path, *, cookie="", body=b"{}", headers=None, app=None, events=None, send_hook=None):
        path, _, query = path.partition("?")
        supplied = [("host", "finlens.test"), ("cookie", cookie)]
        if method == "POST":
            supplied += [("origin", self.cfg.origin), ("sec-fetch-site", "same-origin"),
                         ("content-type", "application/json")]
        else:
            supplied += [("sec-fetch-site", "cross-site"), ("sec-fetch-mode", "navigate"),
                         ("sec-fetch-dest", "document")]
        if headers is not None:
            supplied = headers
        response = []
        async def receive():
            if events is not None:
                return events.pop(0) if events else {"type": "http.disconnect"}
            return {"type": "http.request", "body": body, "more_body": False}
        async def send(event):
            response.append(event)
            if send_hook is not None:
                await send_hook(event)
        await (app or self.app)({"type": "http", "scheme": "https", "method": method,
            "path": "/private-research" + path, "root_path": "/private-research",
            "query_string": query.encode(), "headers": [(k.encode(), v.encode()) for k, v in supplied]}, receive, send)
        return response[0]["status"], response[1]["body"], response[0]["headers"]

    def call(self, *args, **kwargs):
        return LOOP.run_until_complete(self.request(*args, **kwargs))

    @staticmethod
    def cookie(result, name):
        values = [value.decode() for key, value in result[2] if key == b"set-cookie"
                  and value.decode().startswith(name + "=")]
        return values[0].split(";", 1)[0] if values else ""

    def begin(self, cookie=""):
        result = self.call("POST", "/login/start", cookie=cookie)
        self.assertEqual(result[0], 200)
        params = parse_qs(urlsplit(json.loads(result[1])["authorization_url"]).query)
        return params, self.cookie(result, login.CORRELATION_COOKIE), result

    def callback_path(self, state, **extra):
        query = dict(state=state, iss=self.policy.issuer, code="offline-code")
        query.update(extra)
        return "/login/callback?" + urlencode(query)

    def finish(self, params, correlation, **extra):
        return self.call("GET", self.callback_path(params["state"][0], **extra), cookie=correlation)

    def state(self, cookie):
        return self.call("GET", "/state", cookie=cookie, headers=[("host", "finlens.test"),
            ("cookie", cookie), ("sec-fetch-site", "same-origin")])

    @asynccontextmanager
    async def held_lock(self, lock):
        """Identity-owned contender with an independent watchdog for pre-fix hangs."""
        entered, release, released = Event(), Event(), Event()
        def hold():
            with lock:
                entered.set()
                release.wait(1)
            released.set()
        worker = Thread(target=hold, name="offline-login-contention")
        worker.start()
        try:
            self.assertTrue(await asyncio.to_thread(entered.wait, 1))
            yield release, released
        finally:
            release.set()
            await asyncio.to_thread(worker.join, 2)
            self.assertFalse(worker.is_alive())

    async def drain_cleanup(self):
        tasks = list(getattr(self.app, "_cleanup_tasks", ()))
        if tasks:
            await asyncio.wait_for(asyncio.gather(*tasks), 2)
        self.assertEqual(getattr(self.app, "_cleanup_failures", 0), 0)

    def test_contention_start_releases_flow_lock_before_workspace_wait(self):
        params, corr, _ = self.begin()
        previous = self.workspace.establish(self.token()).split(";", 1)[0]
        async def race():
            entered, exchange_release = asyncio.Event(), asyncio.Event()
            async def pause():
                entered.set(); await exchange_release.wait()
            self.exchange_hook = pause
            legitimate = asyncio.create_task(self.request("GET", self.callback_path(params["state"][0]), cookie=corr))
            await asyncio.wait_for(entered.wait(), 2)
            tasks = [legitimate]
            discard_entered, discard_finished = Event(), Event()
            original = self.workspace.discard
            def discard(handle):
                discard_entered.set()
                try:
                    return original(handle)
                finally:
                    discard_finished.set()
            async with self.held_lock(self.workspace._lock) as (release, released):
                try:
                    with patch.object(self.workspace, "discard", discard):
                        start = asyncio.create_task(self.request("POST", "/login/start", cookie=previous))
                        tasks.append(start)
                        self.assertTrue(await asyncio.to_thread(discard_entered.wait, 0.5))
                        invented = asyncio.create_task(self.request("GET", self.callback_path("z" * 43), cookie=corr))
                        tasks.append(invented)
                        async def heartbeat():
                            await asyncio.sleep(0.02)
                            return not released.is_set()
                        self.assertTrue(await asyncio.wait_for(heartbeat(), 0.2), "Heartbeat waited for workspace release")
                        self.assertEqual((await asyncio.wait_for(invented, 0.2))[0], 400)
                        self.assertFalse(released.is_set(), "Invented callback waited behind workspace I/O")
                        legitimate.cancel()
                        with self.assertRaises(asyncio.CancelledError):
                            await asyncio.wait_for(legitimate, 0.2)
                        self.assertFalse(released.is_set(), "Cancellation waited for workspace release")
                finally:
                    release.set(); exchange_release.set()
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
            await self.drain_cleanup()
            self.assertTrue(await asyncio.to_thread(discard_finished.wait, 1))
        LOOP.run_until_complete(race())
        self.assertEqual(self.workspace._sessions, {})
        self.assertEqual(self.app._flows, {})

    def test_contention_pending_callback_cancellation_does_not_wait_for_flow_lock(self):
        params, corr, _ = self.begin()
        async def race():
            async with self.held_lock(self.app._lock) as (release, released):
                task = asyncio.create_task(self.request("GET", self.callback_path(params["state"][0]), cookie=corr))
                try:
                    await asyncio.sleep(0)
                    task.cancel()
                    with self.assertRaises(asyncio.CancelledError):
                        await asyncio.wait_for(task, 0.2)
                    self.assertFalse(released.is_set(), "Cancellation waited for the flow lock watchdog")
                finally:
                    release.set()
                    await asyncio.gather(task, return_exceptions=True)
            await self.drain_cleanup()
        LOOP.run_until_complete(race())
        self.assertEqual(self.requests, []); self.assertEqual(self.db.events, [])
        self.assertNotIn(params["state"][0], self.app._flows)

    def test_contention_exception_cleanup_and_cancellation_leave_loop_responsive(self):
        params, corr, _ = self.begin()
        async def race():
            entered, fail = asyncio.Event(), asyncio.Event()
            cleanup_entered = Event()
            original = self.app._abandon
            def abandon(*args):
                cleanup_entered.set()
                return original(*args)
            async def transport_failure():
                entered.set(); await fail.wait()
                raise RuntimeError("synthetic exchange failure")
            self.exchange_hook = transport_failure
            task = asyncio.create_task(self.request("GET", self.callback_path(params["state"][0]), cookie=corr))
            await asyncio.wait_for(entered.wait(), 2)
            async with self.held_lock(self.app._lock) as (release, released):
                try:
                    with patch.object(self.app, "_abandon", abandon):
                        fail.set()
                        self.assertTrue(await asyncio.to_thread(cleanup_entered.wait, 0.5))
                        await asyncio.wait_for(asyncio.sleep(0.02), 0.2)
                        self.assertFalse(released.is_set(), "Exception cleanup blocked the event loop")
                        task.cancel()
                        with self.assertRaises(asyncio.CancelledError):
                            await asyncio.wait_for(task, 0.2)
                        self.assertFalse(released.is_set(), "Cancellation waited behind error cleanup")
                finally:
                    release.set(); fail.set()
                    await asyncio.gather(task, return_exceptions=True)
            await self.drain_cleanup()
        LOOP.run_until_complete(race())
        self.assertEqual(self.db.events, []); self.assertEqual(self.workspace._sessions, {})
        self.assertNotIn(params["state"][0], self.app._flows)

    def test_unconsumed_callback_error_preserves_cookie_and_successful_session(self):
        params, corr, _ = self.begin()
        wrong = self.call("GET", self.callback_path("z" * 43), cookie=corr)
        self.assertEqual(wrong[0], 400)
        self.assertEqual(self.cookie(wrong, login.CORRELATION_COOKIE), "")
        valid = self.finish(params, corr)
        self.assertEqual(valid[0], 303)
        research = self.cookie(valid, COOKIE)
        replay = self.finish(params, corr)
        self.assertEqual(replay[0], 400)
        self.assertEqual(self.cookie(replay, login.CORRELATION_COOKIE), "")
        self.assertEqual(self.state(research)[0], 200)
        self.assertEqual(len(self.requests), 1)

    def test_failed_invalid_callback_delivery_cannot_revoke_concurrent_login(self):
        for phase in ("http.response.start", "http.response.body"):
            for failure in (RuntimeError, asyncio.CancelledError):
                with self.subTest(phase=phase, failure=failure.__name__):
                    params, corr, _ = self.begin()
                    async def race():
                        entered, release = asyncio.Event(), asyncio.Event()
                        async def fail_invalid(event):
                            if event["type"] == "http.response.start":
                                self.assertEqual(event["status"], 400)
                            if event["type"] == phase:
                                entered.set(); await release.wait()
                                raise failure("synthetic invalid response delivery failure")
                        task = asyncio.create_task(self.request("GET", self.callback_path("z" * 43),
                            cookie=corr, send_hook=fail_invalid))
                        try:
                            await asyncio.wait_for(entered.wait(), 2)
                            result = await self.request("GET", self.callback_path(params["state"][0]), cookie=corr)
                            self.assertEqual(result[0], 303)
                            research = self.cookie(result, COOKIE)
                            async def state():
                                return await self.request("GET", "/state", cookie=research, headers=[
                                    ("host", "finlens.test"), ("cookie", research), ("sec-fetch-site", "same-origin")])
                            self.assertEqual((await state())[0], 200)
                            release.set()
                            with self.assertRaises(failure):
                                await task
                            await self.drain_cleanup()
                            self.assertEqual((await state())[0], 200)
                            self.assertEqual(self.app._flows[params["state"][0]].status, "completed")
                            return research
                        finally:
                            release.set()
                            if not task.done():
                                task.cancel()
                            await asyncio.gather(task, return_exceptions=True)
                            await self.drain_cleanup()
                    research = LOOP.run_until_complete(race())
                    self.assertEqual(self.finish(params, corr)[0], 400)
                    self.assertEqual(self.state(research)[0], 200)
                    self.assertEqual(self.call("POST", "/login/cancel", cookie=corr)[0], 200)
                    self.assertEqual(self.state(research)[0], 401)
        self.assertEqual(len(self.requests), 4)

    def test_failed_replay_delivery_cannot_revoke_login_awaiting_own_delivery(self):
        for phase in ("http.response.start", "http.response.body"):
            for failure in (RuntimeError, asyncio.CancelledError):
                with self.subTest(phase=phase, failure=failure.__name__):
                    params, corr, _ = self.begin()
                    async def race():
                        entered, release = asyncio.Event(), asyncio.Event()
                        published = []
                        async def pause_success(event):
                            if event["type"] == "http.response.start":
                                self.assertEqual(event["status"], 303)
                                published.extend(event["headers"])
                            if event["type"] == phase:
                                entered.set(); await release.wait()
                        async def fail_replay(event):
                            if event["type"] == "http.response.start":
                                self.assertEqual(event["status"], 400)
                            if event["type"] == phase:
                                raise failure("synthetic replay response delivery failure")
                        task = asyncio.create_task(self.request("GET", self.callback_path(params["state"][0]),
                            cookie=corr, send_hook=pause_success))
                        try:
                            await asyncio.wait_for(entered.wait(), 2)
                            research = self.cookie((303, b"", published), COOKIE)
                            async def state():
                                return await self.request("GET", "/state", cookie=research, headers=[
                                    ("host", "finlens.test"), ("cookie", research), ("sec-fetch-site", "same-origin")])
                            self.assertEqual((await state())[0], 200)
                            with self.assertRaises(failure):
                                await self.request("GET", self.callback_path(params["state"][0]),
                                    cookie=corr, send_hook=fail_replay)
                            await self.drain_cleanup()
                            self.assertEqual((await state())[0], 200)
                            release.set()
                            self.assertEqual((await asyncio.wait_for(task, 2))[0], 303)
                            return research
                        finally:
                            release.set()
                            if not task.done():
                                task.cancel()
                            await asyncio.gather(task, return_exceptions=True)
                            await self.drain_cleanup()
                    research = LOOP.run_until_complete(race())
                    self.assertEqual(self.state(research)[0], 200)
                    self.assertEqual(self.call("POST", "/login/cancel", cookie=corr)[0], 200)
                    self.assertEqual(self.state(research)[0], 401)
        self.assertEqual(len(self.requests), 4)

    def test_disabled_and_immutable_configuration_have_no_effects(self):
        for method, path in (("POST", "/login/start"), ("GET", "/login/callback"), ("POST", "/login/cancel")):
            self.assertEqual(self.call(method, path, app=login.PrivateWorkspaceLogin())[0], 503)
        self.assertEqual(self.db.events, []); self.assertEqual(self.requests, [])
        with self.assertRaises(FrozenInstanceError):
            self.cfg.origin = "https://attacker.invalid"
        with self.assertRaises(FrozenInstanceError):
            self.cfg.admission.subjects = frozenset({"attacker"})
        for changes in (dict(origin="http://finlens.test"), dict(token_endpoint="https://bad host/token"),
                        dict(scopes=["finlens.private"]), dict(scopes=("offline_access",)),
                        dict(scopes=("openid",)), dict(authorization_endpoint="https://offline.invalid/a?x=1")):
            with self.subTest(changes=list(changes)), self.assertRaises(login.LoginFailure):
                replace(self.cfg, **changes)
        with self.assertRaises(login.LoginFailure):
            login.PrivateWorkspaceLogin(self.workspace, configuration=replace(self.cfg,
                policy=replace(self.policy, client_id="different-client")), exchange=lambda _: None)

    def test_explicit_login_fails_closed_when_auth_dependencies_are_unavailable(self):
        original = login.import_module
        for missing in ("app.account_auth", "cryptography.hazmat.primitives.asymmetric.rsa"):
            with self.subTest(missing=missing):
                def load(name):
                    if name == missing:
                        raise ModuleNotFoundError("synthetic-sensitive-missing-dependency")
                    return original(name)
                with patch.object(login, "import_module", side_effect=load):
                    # Disabled construction and admission must never ask for auth.
                    disabled = login.PrivateWorkspaceLogin()
                    self.assertIsNone(disabled._auth)
                    result = self.call("POST", "/login/start", app=disabled)
                    self.assertEqual(result[0], 503)
                    self.assertEqual(json.loads(result[1]), {"code": "LOGIN_UNAVAILABLE"})
                    for compose in (lambda: replace(self.cfg), lambda: login.PrivateWorkspaceLogin(
                            self.workspace, configuration=self.cfg, exchange=self.app._exchange)):
                        with self.assertRaises(login.LoginFailure) as failure:
                            compose()
                        self.assertEqual((failure.exception.status, failure.exception.code),
                                         (503, "LOGIN_UNAVAILABLE"))
                        self.assertNotIn("synthetic-sensitive", repr(failure.exception))
                self.assertEqual(self.db.events, []); self.assertEqual(self.requests, [])
                self.assertEqual(self.workspace._sessions, {})

    def test_start_pkce_browser_cookie_and_exchange_contract(self):
        params, correlation, start = self.begin()
        self.assertEqual(set(params), {"response_type", "client_id", "redirect_uri", "scope", "state",
            "code_challenge", "code_challenge_method", "response_mode"})
        self.assertEqual(params["code_challenge_method"], ["S256"])
        self.assertEqual(params["response_type"], ["code"])
        self.assertEqual(params["redirect_uri"], [self.cfg.redirect_uri])
        self.assertEqual(params["response_mode"], ["query"])
        raw = b";".join(v for k, v in start[2] if k == b"set-cookie")
        for flag in (b"HttpOnly", b"Secure", b"Path=/", b"SameSite=Lax", b"Max-Age=180"):
            self.assertIn(flag, raw)
        self.assertNotIn(b"Domain=", raw)
        result = self.finish(params, correlation)  # Strict research cookie intentionally absent.
        self.assertEqual(result[0], 303)
        self.assertEqual(dict(result[2])[b"location"], b"https://finlens.test/investigations")
        self.assertEqual(dict(result[2])[b"referrer-policy"], b"no-referrer")
        self.assertEqual(dict(result[2])[b"cache-control"], b"private, no-store")
        research = self.cookie(result, COOKIE)
        self.assertEqual(self.state(research)[0], 200)
        self.assertEqual(len(self.db.rows[ResearchAccount]), 1)
        request = self.requests[0]
        sent = parse_qs(request.body.decode())
        self.assertEqual(set(sent), {"grant_type", "code", "redirect_uri", "client_id", "code_verifier"})
        challenge = base64.urlsafe_b64encode(hashlib.sha256(sent["code_verifier"][0].encode()).digest()).rstrip(b"=").decode()
        self.assertEqual(params["code_challenge"], [challenge])
        self.assertEqual(request.url, self.cfg.token_endpoint)
        self.assertFalse(request.follow_redirects)
        self.assertEqual(request.timeout_seconds, 5); self.assertEqual(request.max_response_bytes, 32768)
        self.assertIn(b"SameSite=Strict", b";".join(v for k, v in result[2] if k == b"set-cookie"))
        self.assertNotIn(sent["code_verifier"][0], repr(start))
        self.assertNotIn(self.next_token, repr(result))
        for value in (request, self.cfg, self.cfg.admission, *self.app._flows.values()):
            self.assertNotIn(sent["code_verifier"][0], repr(value))
            self.assertNotIn("offline-alice", repr(value))
        self.assertEqual(self.finish(params, correlation)[0], 400)
        self.assertEqual(len(self.requests), 1)

    def test_state_binding_issuer_expiry_and_duplicates_fail_before_exchange(self):
        params, cookie, _ = self.begin()
        state = params["state"][0]
        cases = [(self.callback_path("a" * 43), cookie), (self.callback_path(state), ""),
                 (self.callback_path(state), login.CORRELATION_COOKIE + "=" + "b" * 43),
                 (self.callback_path(state), cookie + "; " + cookie),
                 (self.callback_path(state, iss="https://other.invalid/"), cookie),
                 (self.callback_path(state) + "&state=" + state, cookie),
                 (self.callback_path(state) + "&return_to=https%3A%2F%2Fevil.invalid", cookie),
                 (self.callback_path(state) + "&bad=%ZZ", cookie)]
        for path, supplied in cases:
            with self.subTest(path=path.split("?", 1)[0]):
                self.assertEqual(self.call("GET", path, cookie=supplied)[0], 400)
        self.assertEqual(self.requests, []); self.assertEqual(self.db.events, [])
        self.clock.advance(181)
        self.assertEqual(self.finish(params, cookie)[0], 400)
        self.assertEqual(self.requests, []); self.assertEqual(self.db.events, [])

    def test_start_admission_and_callback_navigation_are_explicit(self):
        valid = [("host", "finlens.test"), ("origin", self.cfg.origin), ("content-type", "application/json"),
                 ("sec-fetch-site", "same-origin")]
        for headers in (valid[1:], valid[:1] + valid[2:], valid + [("authorization", "Bearer untrusted")],
                        valid + [("origin", self.cfg.origin)],
                        [(k, "cross-site" if k == "sec-fetch-site" else v) for k, v in valid]):
            self.assertIn(self.call("POST", "/login/start", headers=headers)[0], (400, 403))
        self.assertEqual(self.call("POST", "/login/start", body=b'{"token":"x"}')[0], 400)
        self.assertEqual(self.requests, []); self.assertEqual(self.db.events, [])
        params, cookie, _ = self.begin()
        self.assertEqual(self.call("GET", self.callback_path(params["state"][0]), headers=[
            ("host", "finlens.test"), ("cookie", cookie), ("sec-fetch-site", "cross-site"),
            ("sec-fetch-mode", "cors"), ("sec-fetch-dest", "empty")])[0], 403)
        self.assertEqual(self.requests, [])

    def test_provider_denial_and_exchange_failures_are_one_time_and_sanitized(self):
        params, cookie, _ = self.begin()
        denied = self.finish(params, cookie, error="access_denied", error_description="private-provider-diagnostic")
        self.assertEqual(denied[0], 400); self.assertNotIn(b"private-provider-diagnostic", denied[1])
        self.assertEqual(self.requests, []); self.assertEqual(self.db.events, [])
        self.assertEqual(self.finish(params, cookie)[0], 400)
        for reply in (login.TokenReply(302, "application/json", b"{}"),
                      login.TokenReply(200, "text/html", b"private-response"),
                      login.TokenReply(200, "application/json", b"x" * 32769),
                      login.TokenReply(200, "application/json", b'{"access_token":"x","access_token":"y"}')):
            params, cookie, _ = self.begin(); self.reply = reply
            result = self.finish(params, cookie)
            self.assertIn(result[0], (400, 503))
            self.assertEqual(set(json.loads(result[1])), {"code"})
            self.assertEqual(self.finish(params, cookie)[0], 400)
        self.assertEqual(self.db.events, [])
        async def timeout():
            raise TimeoutError("private token/code/verifier diagnostic")
        self.reply, self.exchange_hook = None, timeout
        params, cookie, _ = self.begin(); result = self.finish(params, cookie)
        self.assertEqual(result[0], 503); self.assertNotIn(b"private", result[1])
        self.assertEqual(self.db.events, [])

    def test_api_token_profile_and_invites_precede_account_creation(self):
        bad = [self.token(headers={"kid": "offline", "typ": "JWT"}), self.token(aud=self.policy.client_id),
               self.token(client_id="other"), self.token(iss="https://other.invalid/"), self.token(exp=int(self.clock.wall) + 901),
               self.token(sub="not-invited"), self.token(sub="OFFLINE-ALICE"), self.token(key=self.other_key)]
        claims = self.claims(); del claims["jti"]
        bad.append(self.token(claims=claims))
        for token in bad:
            params, cookie, _ = self.begin(); self.next_token = token
            result = self.finish(params, cookie)
            self.assertIn(result[0], (401, 403))
            self.assertNotIn(token, repr(result))
            self.assertEqual(self.db.events, [])
            self.assertEqual(self.db.rows[ResearchAccount], {})
        params, cookie, _ = self.begin()
        self.reply = login.TokenReply(200, "application/json", json.dumps(dict(
            id_token=self.token(), token_type="Bearer", expires_in=300)).encode())
        self.assertEqual(self.finish(params, cookie)[0], 503)
        self.assertEqual(self.db.events, [])

    def test_switching_revokes_prior_browser_and_pending_state(self):
        params, corr, _ = self.begin(); alice = self.cookie(self.finish(params, corr), COOKIE)
        first_state, first_corr, _ = self.begin(alice)
        self.assertEqual(self.state(alice)[0], 401)
        second, second_corr, _ = self.begin(first_corr)
        self.assertNotEqual(first_corr, second_corr)
        self.assertEqual(self.finish(first_state, first_corr)[0], 400)
        self.next_token = self.token(sub="offline-bob")
        bob = self.cookie(self.finish(second, second_corr), COOKIE)
        self.assertEqual(self.state(bob)[0], 200)
        self.assertEqual(len(self.db.rows[ResearchAccount]), 2)
        self.assertNotEqual(alice, bob)

    def test_cancel_and_logout_during_exchange_cannot_resurrect_login(self):
        for action in ("/login/cancel", "/logout", "/login/start"):
            params, corr, _ = self.begin()
            async def race():
                entered, release = asyncio.Event(), asyncio.Event()
                async def pause():
                    entered.set(); await release.wait()
                self.exchange_hook = pause
                task = asyncio.create_task(self.request("GET", self.callback_path(params["state"][0]), cookie=corr))
                await asyncio.wait_for(entered.wait(), 2)
                result = await self.request("POST", action, cookie=corr)
                self.assertIn(result[0], (200, 401))
                release.set()
                callback = await task
                self.assertNotEqual(callback[0], 303)
            LOOP.run_until_complete(race())
            self.exchange_hook = None
            self.assertEqual(self.workspace._sessions, {})
            self.assertEqual(self.db.rows[ResearchAccount], {})

    def test_cancelled_callback_task_has_no_authority_and_no_replay(self):
        params, corr, _ = self.begin()
        async def race():
            entered = asyncio.Event()
            async def pause():
                entered.set(); await asyncio.Future()
            self.exchange_hook = pause
            task = asyncio.create_task(self.request("GET", self.callback_path(params["state"][0]), cookie=corr))
            await asyncio.wait_for(entered.wait(), 2)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        LOOP.run_until_complete(race())
        self.exchange_hook = None
        self.assertEqual(self.workspace._sessions, {}); self.assertEqual(self.db.events, [])
        self.assertEqual(self.finish(params, corr)[0], 400)

    def test_exchange_timeout_cancels_transport_without_account_access(self):
        params, corr, _ = self.begin()
        stopped = []
        async def hang():
            try:
                await asyncio.Future()
            finally:
                stopped.append(True)
        self.exchange_hook = hang
        with patch.object(login, "EXCHANGE_SECONDS", 0.01):
            result = self.finish(params, corr)
        self.assertEqual(result[0], 503); self.assertEqual(stopped, [True])
        self.assertEqual(self.db.events, [])
        self.assertEqual(self.finish(params, corr)[0], 400)

    def test_concurrent_callback_cannot_exchange_same_state_twice(self):
        params, corr, _ = self.begin()
        async def race():
            entered, release = asyncio.Event(), asyncio.Event()
            async def pause():
                entered.set(); await release.wait()
            self.exchange_hook = pause
            path = self.callback_path(params["state"][0])
            first = asyncio.create_task(self.request("GET", path, cookie=corr))
            await asyncio.wait_for(entered.wait(), 2)
            self.assertEqual((await self.request("GET", path, cookie=corr))[0], 400)
            self.assertEqual(len(self.requests), 1); self.assertEqual(self.db.events, [])
            release.set()
            self.assertEqual((await first)[0], 303)
        LOOP.run_until_complete(race())
        self.assertEqual(len(self.requests), 1)

    def test_expiry_during_code_exchange_stops_before_account_creation(self):
        params, corr, _ = self.begin()
        async def advance():
            self.clock.advance(181)
        self.exchange_hook = advance
        self.assertEqual(self.finish(params, corr)[0], 400)
        self.assertEqual(len(self.requests), 1); self.assertEqual(self.db.events, [])

    def test_failed_cookie_publication_discards_handle_without_false_metadata_rollback(self):
        self.next_token = self.token(sub="offline-bob")
        prior, prior_corr, _ = self.begin()
        prior_research = self.cookie(self.finish(prior, prior_corr), COOKIE)
        prior_handles = set(self.workspace._sessions)
        self.next_token = self.token()
        for phase in ("http.response.start", "http.response.body"):
            for failure in (RuntimeError, asyncio.CancelledError):
                with self.subTest(phase=phase, failure=failure.__name__):
                    params, corr, _ = self.begin()
                    published = []
                    async def fail_send(event):
                        if event["type"] == "http.response.start":
                            self.assertEqual(event["status"], 303)
                            published.extend(event["headers"])
                        if event["type"] == phase:
                            raise failure("synthetic ASGI delivery failure")
                    with self.assertRaises(failure):
                        self.call("GET", self.callback_path(params["state"][0]), cookie=corr, send_hook=fail_send)
                    LOOP.run_until_complete(self.drain_cleanup())
                    self.assertEqual(len(self.db.rows[ResearchAccount]), 2)
                    self.assertEqual(set(self.workspace._sessions), prior_handles)
                    self.assertEqual(self.state(prior_research)[0], 200)
                    self.assertNotIn(params["state"][0], self.app._flows)
                    self.assertEqual(self.state(self.cookie((303, b"", published), COOKIE))[0], 401)
                    self.assertEqual(self.finish(params, corr)[0], 400)

    def test_failed_start_delivery_discards_only_its_reserved_flow(self):
        prior, prior_corr, _ = self.begin()
        prior_research = self.cookie(self.finish(prior, prior_corr), COOKIE)
        prior_handles = set(self.workspace._sessions)
        for phase in ("http.response.start", "http.response.body"):
            for failure in (RuntimeError, asyncio.CancelledError):
                with self.subTest(phase=phase, failure=failure.__name__):
                    async def fail_send(event):
                        if event["type"] == "http.response.start":
                            self.assertEqual(event["status"], 200)
                        if event["type"] == phase:
                            raise failure("synthetic start delivery failure")
                    with self.assertRaises(failure):
                        self.call("POST", "/login/start", send_hook=fail_send)
                    LOOP.run_until_complete(self.drain_cleanup())
                    self.assertEqual(set(self.app._flows), {prior["state"][0]})
                    self.assertEqual(set(self.workspace._sessions), prior_handles)
                    self.assertEqual(self.state(prior_research)[0], 200)

    def test_empty_invite_policy_denies_existing_valid_subject_before_account_access(self):
        self.app = login.PrivateWorkspaceLogin(self.workspace,
            configuration=replace(self.cfg, admission=login.InviteAdmission(self.policy.issuer, frozenset())),
            exchange=self.app._exchange, clock=lambda: self.clock.wall, monotonic=lambda: self.clock.mono)
        params, corr, _ = self.begin()
        self.assertEqual(self.finish(params, corr)[0], 403)
        self.assertEqual(self.db.events, []); self.assertEqual(self.db.rows[ResearchAccount], {})

    def test_body_chunk_budget_is_finite_before_start_or_account_access(self):
        events = [{"type": "http.request", "body": b"", "more_body": True} for _ in range(9)]
        self.assertEqual(self.call("POST", "/login/start", events=events)[0], 400)
        self.assertEqual(self.requests, []); self.assertEqual(self.app._flows, {}); self.assertEqual(self.db.events, [])

    def test_late_logout_revokes_completed_handle_even_when_research_cookie_was_strictly_absent(self):
        params, corr, _ = self.begin()
        result = self.finish(params, corr)
        research = self.cookie(result, COOKIE)
        self.assertEqual(self.state(research)[0], 200)
        self.assertEqual(self.call("POST", "/logout", cookie=corr)[0], 401)
        self.assertEqual(self.state(research)[0], 401)
        self.assertEqual(self.finish(params, corr)[0], 400)

    def test_existing_csrf_logout_and_private_session_expiry_remain(self):
        params, corr, _ = self.begin(); research = self.cookie(self.finish(params, corr), COOKIE)
        state = json.loads(self.state(research)[1])
        headers = [("host", "finlens.test"), ("cookie", research), ("origin", self.cfg.origin),
            ("sec-fetch-site", "same-origin"), ("content-type", "application/json")]
        self.assertEqual(self.call("POST", "/logout", headers=headers)[0], 403)
        self.assertEqual(self.state(research)[0], 200)
        self.assertEqual(self.call("POST", "/logout", headers=headers + [("x-finlens-csrf", state["csrf"])])[0], 200)
        self.assertEqual(self.state(research)[0], 401)
        self.next_token = self.token()
        params, corr, _ = self.begin(); research = self.cookie(self.finish(params, corr), COOKIE)
        self.clock.advance(301)
        self.assertEqual(self.state(research)[0], 401)

    def test_cancel_at_account_commit_boundary_creates_no_browser_handle(self):
        params, corr, _ = self.begin()
        flow = self.app._flows[params["state"][0]]
        self.db.hooks["commit_after"] = flow.cancellation.cancel
        result = self.finish(params, corr)
        self.assertEqual(result[0], 503)
        self.assertEqual(len(self.db.rows[ResearchAccount]), 1)  # Committed metadata is not falsely rolled back.
        self.assertEqual(self.workspace._sessions, {})
        self.assertNotIn(self.next_token, repr(result))

    def test_indeterminate_database_outcome_does_not_issue_cookie_or_retry_exchange(self):
        self.db.commit_error = "after"
        params, corr, _ = self.begin(); result = self.finish(params, corr)
        self.assertEqual(result[0], 503)
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(self.workspace._sessions, {})
        self.assertEqual(self.finish(params, corr)[0], 400)
        self.assertEqual(len(self.requests), 1)

    def test_flow_capacity_clock_rollback_and_sensitive_reply_fields_fail_closed(self):
        with patch.object(login, "MAX_FLOWS", 1):
            params, corr, _ = self.begin()
            self.assertEqual(self.call("POST", "/login/start")[0], 503)
            self.clock.wall -= 1; self.clock.mono -= 1
            self.assertEqual(self.finish(params, corr)[0], 503)
        self.assertEqual(self.db.events, [])
        self.clock.wall += 1; self.clock.mono += 1
        for field in ("refresh_token", "id_token"):
            params, corr, _ = self.begin(corr)
            data = dict(access_token=self.token(), token_type="Bearer", expires_in=300)
            data[field] = "synthetic-sensitive-unused-value"
            self.reply = login.TokenReply(200, "application/json", json.dumps(data).encode())
            result = self.finish(params, corr)
            self.assertEqual(result[0], 503)
            self.assertNotIn(b"synthetic-sensitive-unused-value", result[1])
        self.assertEqual(self.db.events, [])


if __name__ == "__main__":
    try:
        unittest.main(verbosity=2)
    finally:
        LOOP.run_until_complete(LOOP.shutdown_default_executor())
        LOOP.close()
