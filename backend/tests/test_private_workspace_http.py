"""Offline ASGI + real JWT + maintained ownership fake store, never DB acceptance."""
import asyncio
import ast
import json
from pathlib import Path
import sys
from unittest.mock import patch
import unittest
from urllib.parse import urlencode

BACKEND = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(BACKEND / ".venv/Lib/site-packages"), str(BACKEND), str(BACKEND / "tests")]
# Construct only asyncio's local wake-up machinery before installing the existing
# strict socket audit guard. No listener, HTTP client or external socket is used.
LOOP = asyncio.new_event_loop()
from app.private_workspace_http import COOKIE, PrivateWorkspace
from test_research_ownership import CryptoFixtures, FakeDatabase, FakeRepository, own, KeyRef, ResearchArtifact
from app.models import CompanyRefreshState, FilingPublication


class HttpTests(CryptoFixtures):
    def setUp(self):
        super().setUp()
        self.db = FakeDatabase(self.clock)
        self.repository_patch = patch.object(own, "_Repository", FakeRepository)
        self.repository_patch.start(); self.addCleanup(self.repository_patch.stop)
        self.service = own.OwnershipService(self.verifier, self.db.factory, monotonic=lambda: self.clock.mono)
        self.app = PrivateWorkspace(self.service, origin="https://finlens.test", clock=lambda: self.clock.wall,
                                    monotonic=lambda: self.clock.mono)
        self.alice, self.bob = self.token(), self.token(sub="offline-bob")
        self.cookie = self.app.establish(self.alice).split(";", 1)[0]
        self.db.publications = [(FilingPublication(company_cik="0000000001", accession_number="0000000001-25-000001",
            data_version=0, content_digest="a" * 64), CompanyRefreshState(company_cik="0000000001", data_version=0, evidence_version=0))]
        self.csrf = self.call("GET", "/state")[1]["csrf"]

    def call(self, method, path, body=None, *, cookie=None, headers=None, app=None, raw=None):
        received, response = False, []
        path, _, query = path.partition("?")
        request_headers = [(b"cookie", (self.cookie if cookie is None else cookie).encode())]
        if method == "POST":
            request_headers += [(b"origin", b"https://finlens.test"), (b"content-type", b"application/json"),
                                (b"x-finlens-csrf", self.csrf.encode())]
        if headers is not None:
            request_headers = [(key.encode(), value.encode()) for key, value in headers]
        async def receive():
            nonlocal received
            if received:
                return {"type": "http.disconnect"}
            received = True
            return {"type": "http.request", "body": raw if raw is not None else json.dumps(body or {}).encode(), "more_body": False}
        async def send(event):
            response.append(event)
        LOOP.run_until_complete((app or self.app)({"type": "http", "method": method, "path": "/private-research" + path,
            "root_path": "/private-research", "query_string": query.encode(), "headers": request_headers}, receive, send))
        return response[0]["status"], json.loads(response[1]["body"]), dict(response[0]["headers"])

    def sources(self):
        result = self.call("GET", "/sources?cik=0000000001")
        self.assertEqual(result[0], 200)
        return result[1]["sources"][0]

    def save(self, request="note-1"):
        return self.call("POST", "/notes", dict(request_key=request, body="My private investigation", source=self.sources()))

    @staticmethod
    def query(note):
        return urlencode(dict(session=note["session_key"]["id"], session_revision=note["session_revision"],
            artifact=note["artifact_key"]["id"], artifact_revision=note["artifact_revision"]))

    def test_default_unavailable_before_any_store_access_and_no_login_route(self):
        self.db.events.clear()
        self.assertEqual(self.call("GET", "/state", app=PrivateWorkspace())[0], 503)
        self.assertEqual(self.db.events, [])
        self.assertEqual(self.call("POST", "/login", {"token": self.alice})[0], 400)
        with self.assertRaises(ValueError):
            PrivateWorkspace(self.service, origin="http://finlens.test")

    def test_connected_save_discover_reload_reopen_and_exact_export(self):
        status, note, _ = self.save()
        self.assertEqual(status, 200)
        repeated = self.save()[1]
        self.assertEqual(repeated, note)
        for _ in range(2):
            self.assertEqual(self.call("GET", "/state")[0], 200)
            listing = self.call("GET", "/notes")[1]
            self.assertEqual(len(listing["items"]), 1)
            self.assertEqual(listing["items"][0]["artifact_key"], note["artifact_key"]["id"])
        query = self.query(note)
        self.assertEqual(self.call("GET", "/note?" + query)[1], note)
        exported = self.call("GET", "/export?" + query)
        self.assertEqual(exported[1], note)
        self.assertIn(b"attachment", exported[2][b"content-disposition"])
        self.assertEqual(exported[1]["source_verification"], "unverified_reference")
        self.assertEqual(exported[1]["original_availability"], "not_checked")

    def test_two_user_discovery_and_guessed_selectors_are_isolated(self):
        alice_note = self.save()[1]
        self.cookie = self.app.establish(self.bob).split(";", 1)[0]
        self.csrf = self.call("GET", "/state")[1]["csrf"]
        self.assertEqual(self.call("GET", "/notes")[1]["items"], [])
        for path in ("/note?", "/export?"):
            self.assertEqual(self.call("GET", path + self.query(alice_note))[0], 404)
        bob_note = self.save()[1]
        self.assertNotEqual(alice_note["owner_key"], bob_note["owner_key"])

    def test_csrf_and_cross_origin_fail_before_ownership_store(self):
        valid = [("cookie", self.cookie), ("origin", "https://finlens.test"), ("content-type", "application/json"),
                 ("x-finlens-csrf", self.csrf)]
        for index, value in ((1, "https://attacker.test"), (3, "forged")):
            headers = list(valid); headers[index] = (headers[index][0], value)
            self.db.events.clear()
            self.assertEqual(self.call("POST", "/logout", headers=headers)[0], 403)
            self.assertEqual(self.db.events, [])
        self.assertEqual(self.call("POST", "/logout", headers=valid + [("x-finlens-csrf", self.csrf)])[0], 403)
        self.assertEqual(self.call("GET", "/notes", headers=[("cookie", self.cookie), ("sec-fetch-site", "cross-site")])[0], 403)

    def test_cookie_flags_fixation_rotation_and_bearer_confidentiality(self):
        old = self.cookie
        cookie = self.app.establish(self.alice)
        for flag in ("Secure", "HttpOnly", "SameSite=Strict", "Path=/", "Max-Age="):
            self.assertIn(flag, cookie)
        self.assertNotIn("Domain=", cookie)
        self.cookie = cookie.split(";", 1)[0]
        self.csrf = self.call("GET", "/state")[1]["csrf"]
        self.assertNotEqual(old, self.cookie)
        self.assertEqual(self.call("GET", "/state", cookie=old)[0], 401)
        self.assertEqual(self.call("GET", "/state", cookie=COOKIE + "=" + "a" * 43)[0], 401)
        for response in (self.call("GET", "/state"), self.call("GET", "/sources?cik=0000000001"), self.save()):
            raw = repr(response)
            for secret in (self.alice, self.bob, self.policy.issuer, "offline-alice"):
                self.assertNotIn(secret, raw)
            self.assertEqual(response[2][b"cache-control"], b"private, no-store")

    def test_logout_revokes_handle_and_preserves_saved_investigation(self):
        note = self.save()[1]
        response = self.call("POST", "/logout", {})
        self.assertEqual(response[0], 200)
        self.assertIn(b"Max-Age=0", response[2][b"set-cookie"])
        self.assertEqual(self.call("GET", "/notes")[0], 401)
        self.cookie = self.app.establish(self.alice).split(";", 1)[0]
        self.assertEqual(self.call("GET", "/note?" + self.query(note))[1], note)

    def test_expiry_account_invalidation_and_revocation_remove_access(self):
        self.clock.advance(301)
        self.assertEqual(self.call("GET", "/state")[0], 401)
        self.alice = self.token()
        self.cookie = self.app.establish(self.alice).split(";", 1)[0]
        self.service.invalidate_account_tokens(self.alice)
        self.assertEqual(self.call("GET", "/notes")[0], 401)

    def test_revoked_investigation_rejects_browser_session(self):
        handle = self.cookie.split("=", 1)[1]
        root = self.app._sessions[handle].investigation
        self.service.revoke_session(self.alice, root.key, root.revision)
        self.assertEqual(self.call("GET", "/state")[0], 401)
        self.assertNotIn(handle, self.app._sessions)

    def test_source_inventory_caps_and_unknown_internal_errors_fail_closed(self):
        self.db.publications *= 51
        self.assertEqual(self.call("GET", "/sources?cik=0000000001")[0], 503)
        with patch.object(self.service, "list_notes", side_effect=RuntimeError("private internal diagnostic")):
            response = self.call("GET", "/notes")
            self.assertEqual(response[0], 503)
            self.assertNotIn("diagnostic", repr(response))

    def test_rejected_note_payloads_never_consume_artifact_quota(self):
        from app.research_contracts import EntityRef, encode
        source = self.sources()
        other_reference = json.loads(encode(EntityRef(key=KeyRef("sec_cik", "0000000001"),
            legal_name="Synthetic issuer", jurisdiction=None, cik="0000000001", authority_ids=())))
        for number, (body, reference) in enumerate((("", source), (" \n\t", source), (123, source),
                ("invalid\x00text", source), ("\ud800", source), ("A note", other_reference))):
            with self.subTest(number=number):
                result = self.call("POST", "/notes", dict(request_key=f"rejected-{number}", body=body, source=reference))
                self.assertEqual(result[0], 400)
                self.assertEqual(self.db.rows[ResearchArtifact], {})
        self.assertEqual(self.save("valid-after-rejections")[0], 200)

    def test_atomic_http_save_uncertain_commit_has_no_orphan_and_same_request_recovers(self):
        from app.models import ResearchNote
        source = self.sources()
        for point, persisted in (("commit_before", 0), ("commit_after", 1)):
            before_artifacts, before_notes = set(self.db.rows[ResearchArtifact]), set(self.db.rows[ResearchNote])
            commits = 0
            def fail_note_commit():
                nonlocal commits
                commits += 1
                if commits == 2:  # Initial session authorization is a separate read transaction.
                    raise RuntimeError("synthetic note COMMIT failure")
            self.db.hooks[point] = fail_note_commit
            payload = dict(request_key=point, body="Atomic note", source=source)
            result = self.call("POST", "/notes", payload)
            self.assertEqual(result[0], 503)
            self.assertEqual(result[1]["commit_state"], "indeterminate")
            artifacts = set(self.db.rows[ResearchArtifact]) - before_artifacts
            notes = set(self.db.rows[ResearchNote]) - before_notes
            self.assertEqual(artifacts, notes)
            self.assertEqual(len(notes), persisted)
            self.db.hooks.clear()
            first = self.call("POST", "/notes", payload)
            self.assertEqual(first[0], 200)
            self.assertEqual(self.call("POST", "/notes", payload)[1], first[1])
            self.assertEqual(len(set(self.db.rows[ResearchArtifact]) - before_artifacts), 1)
            self.assertEqual(len(set(self.db.rows[ResearchNote]) - before_notes), 1)

    def test_final_authorization_read_failure_reports_confirmed_note_write_without_content(self):
        from app.models import ResearchNote
        source = self.sources()
        locks = 0
        def fail_final_authorization():
            nonlocal locks
            locks += 1
            if locks == 3:
                raise RuntimeError("synthetic final authorization read failure")
        self.db.hooks["account_lock"] = fail_final_authorization
        payload = dict(request_key="confirmed-before-read-failure", body="Private saved content", source=source)
        result = self.call("POST", "/notes", payload)
        self.assertEqual(result[0], 503)
        self.assertEqual(len(self.db.rows[ResearchArtifact]), 1)
        self.assertEqual(len(self.db.rows[ResearchNote]), 1)
        self.assertEqual(result[1], {"code": "PRIVATE_WORKSPACE_UNAVAILABLE", "commit_state": "confirmed"})
        self.assertNotIn(payload["body"], repr(result))
        self.db.hooks.clear()
        recovered = self.call("POST", "/notes", payload)
        self.assertEqual(recovered[0], 200)
        self.assertEqual(self.call("POST", "/notes", payload)[1], recovered[1])
        self.assertEqual(len(self.db.rows[ResearchArtifact]), 1)
        self.assertEqual(len(self.db.rows[ResearchNote]), 1)

    def test_final_authorization_denial_withholds_content_but_preserves_confirmed_write(self):
        from app.models import ResearchNote
        for code in ("OWNERSHIP_DENIED", "AUTH_INVALID"):
            source = self.sources()
            before_artifacts, before_notes = set(self.db.rows[ResearchArtifact]), set(self.db.rows[ResearchNote])
            locks = 0
            def deny_final_authorization():
                nonlocal locks
                locks += 1
                if locks == 3:
                    raise own.OwnershipFailure(code)
            self.db.hooks["account_lock"] = deny_final_authorization
            payload = dict(request_key=code, body="Do not disclose this note", source=source)
            result = self.call("POST", "/notes", payload)
            self.assertEqual(result[0], 401)
            self.assertEqual(result[1], {"code": "AUTH_REQUIRED", "commit_state": "confirmed"})
            self.assertIn(b"Max-Age=0", result[2][b"set-cookie"])
            self.assertNotIn(payload["body"], repr(result))
            self.assertEqual(len(set(self.db.rows[ResearchNote]) - before_notes), 1)
            self.db.hooks.clear()
            self.assertEqual(self.call("GET", "/notes")[0], 401)
            self.cookie = self.app.establish(self.alice).split(";", 1)[0]
            self.csrf = self.call("GET", "/state")[1]["csrf"]
            recovered = self.call("POST", "/notes", payload)
            self.assertEqual(recovered[0], 200)
            self.assertEqual(self.call("POST", "/notes", payload)[1], recovered[1])
            self.assertEqual(len(set(self.db.rows[ResearchArtifact]) - before_artifacts), 1)
            self.assertEqual(len(set(self.db.rows[ResearchNote]) - before_notes), 1)

    def test_confirmed_write_cleanup_failure_is_not_replaced_with_not_issued(self):
        from app.models import ResearchNote
        source = self.sources()
        closes = 0
        def fail_note_cleanup():
            nonlocal closes
            closes += 1
            if closes == 2:
                raise RuntimeError("synthetic post-write cleanup failure")
        self.db.hooks["close"] = fail_note_cleanup
        payload = dict(request_key="cleanup-confirmed", body="Private cleanup note", source=source)
        result = self.call("POST", "/notes", payload)
        self.assertEqual(result[0], 503)
        self.assertEqual(result[1], {"code": "PRIVATE_WORKSPACE_UNAVAILABLE", "commit_state": "confirmed"})
        self.assertNotIn(payload["body"], repr(result))
        self.assertEqual(len(self.db.rows[ResearchNote]), 1)
        self.db.hooks.clear()
        self.assertEqual(self.call("POST", "/notes", payload)[0], 200)
        self.assertEqual(len(self.db.rows[ResearchArtifact]), 1)
        self.assertEqual(len(self.db.rows[ResearchNote]), 1)

    def test_untyped_save_failure_remains_unknown_and_reconciliation_is_explicit(self):
        from app.models import ResearchNote
        source = self.sources()
        actual_save = self.service.save_new_note
        for persisted in (False, True):
            before_artifacts, before_notes = set(self.db.rows[ResearchArtifact]), set(self.db.rows[ResearchNote])
            def unknown(*args, **kwargs):
                if persisted:
                    actual_save(*args, **kwargs)
                raise RuntimeError("synthetic lost write outcome")
            payload = dict(request_key=f"unknown-{persisted}", body="Private uncertain note", source=source)
            with patch.object(self.service, "save_new_note", side_effect=unknown):
                result = self.call("POST", "/notes", payload)
            self.assertEqual(result[0], 503)
            self.assertEqual(result[1], {"code": "PRIVATE_WORKSPACE_UNAVAILABLE", "commit_state": "indeterminate"})
            self.assertNotIn(payload["body"], repr(result))
            self.assertEqual(len(set(self.db.rows[ResearchNote]) - before_notes), int(persisted))
            recovered = self.call("POST", "/notes", payload)
            self.assertEqual(recovered[0], 200)
            self.assertEqual(self.call("POST", "/notes", payload)[1], recovered[1])
            self.assertEqual(len(set(self.db.rows[ResearchArtifact]) - before_artifacts), 1)
            self.assertEqual(len(set(self.db.rows[ResearchNote]) - before_notes), 1)

    def test_validation_and_precommit_rollback_keep_write_not_issued_and_retry_safe(self):
        from app.models import ResearchNote
        source = self.sources()
        for stage in ("validation", "rollback"):
            before_artifacts, before_notes = set(self.db.rows[ResearchArtifact]), set(self.db.rows[ResearchNote])
            def fail_before_commit():
                raise RuntimeError("synthetic pre-commit failure")
            if stage == "rollback":
                self.db.hooks["note_lock"] = fail_before_commit
            payload = dict(request_key=stage, body="" if stage == "validation" else "Private precommit note", source=source)
            result = self.call("POST", "/notes", payload)
            self.assertEqual(result[0], 400 if stage == "validation" else 503)
            self.assertEqual(result[1]["commit_state"], "not_issued")
            self.assertEqual(set(result[1]), {"code", "commit_state"})
            self.assertEqual(set(self.db.rows[ResearchArtifact]), before_artifacts)
            self.assertEqual(set(self.db.rows[ResearchNote]), before_notes)
            self.db.hooks.clear()
            payload["body"] = "Corrected or retried note"
            recovered = self.call("POST", "/notes", payload)
            self.assertEqual(recovered[0], 200)
            self.assertEqual(self.call("POST", "/notes", payload)[1], recovered[1])
            self.assertEqual(len(set(self.db.rows[ResearchArtifact]) - before_artifacts), 1)
            self.assertEqual(len(set(self.db.rows[ResearchNote]) - before_notes), 1)

    def test_postwrite_receipt_encoding_failure_reports_confirmed_without_private_content(self):
        from app.models import ResearchNote
        source = self.sources()
        actual_encode, encodes = own.SavedNote.encode, 0
        def fail_after_commit(note):
            nonlocal encodes
            encodes += 1
            if encodes == 2:
                raise ValueError("synthetic post-write serialization failure")
            return actual_encode(note)
        payload = dict(request_key="encoding-confirmed", body="Private serialization note", source=source)
        with patch.object(own.SavedNote, "encode", fail_after_commit):
            result = self.call("POST", "/notes", payload)
        self.assertEqual(encodes, 2)
        self.assertEqual(result[0], 503)
        self.assertEqual(result[1], {"code": "PRIVATE_WORKSPACE_UNAVAILABLE", "commit_state": "confirmed"})
        self.assertNotIn(payload["body"], repr(result))
        self.assertEqual(self.call("POST", "/notes", payload)[0], 200)
        self.assertEqual(len(self.db.rows[ResearchArtifact]), 1)
        self.assertEqual(len(self.db.rows[ResearchNote]), 1)

    def test_raw_verifier_rejection_at_write_entry_is_not_issued(self):
        source = self.sources()
        with patch.object(self.service, "save_new_note", side_effect=own.AuthFailure()):
            result = self.call("POST", "/notes", dict(request_key="auth-entry", body="Do not save", source=source))
        self.assertEqual(result[0], 401)
        self.assertEqual(result[1], {"code": "AUTH_REQUIRED", "commit_state": "not_issued"})
        self.assertEqual(len(self.db.rows[ResearchArtifact]), 0)

    def test_note_write_outcome_does_not_leak_into_a_later_read_request(self):
        self.assertEqual(self.save()[0], 200)
        with patch.object(self.service, "list_notes", side_effect=RuntimeError("synthetic read failure")):
            result = self.call("GET", "/notes")
        self.assertEqual(result[0], 503)
        self.assertEqual(result[1], {"code": "PRIVATE_WORKSPACE_UNAVAILABLE", "commit_state": "not_issued"})

    def test_missing_origin_bearer_override_and_duplicate_cookie_are_rejected(self):
        valid = [("cookie", self.cookie), ("origin", "https://finlens.test"), ("content-type", "application/json"),
                 ("x-finlens-csrf", self.csrf)]
        self.assertEqual(self.call("POST", "/logout", headers=[row for row in valid if row[0] != "origin"])[0], 403)
        self.assertEqual(self.call("GET", "/state", headers=[("cookie", self.cookie), ("authorization", "Bearer forged")])[0], 403)
        self.assertEqual(self.call("GET", "/state", cookie=self.cookie + "; " + self.cookie)[0], 401)

    def test_invalid_json_duplicates_size_and_selectors_are_bounded(self):
        self.assertEqual(self.call("POST", "/notes", raw=b'{"body":1,"body":2}')[0], 400)
        self.assertEqual(self.call("POST", "/notes", raw=b"x" * (48 * 1024 + 1))[0], 413)
        self.assertEqual(self.call("GET", "/notes?after=x&after=y")[0], 400)
        self.assertEqual(self.call("POST", "/notes", {"owner_key": "forged"})[0], 400)

    def test_indeterminate_authorization_read_before_save_does_not_claim_a_note_write(self):
        source = self.sources()
        self.db.commit_error = "after"
        response = self.call("POST", "/notes", dict(request_key="uncertain", body="A note", source=source))
        self.assertEqual(response[0], 503)
        self.assertEqual(response[1]["commit_state"], "not_issued")
        self.assertEqual(len(self.db.rows[ResearchArtifact]), 0)  # Initial authorization transaction failed first.
        self.db.commit_error = None
        recovered = self.call("POST", "/notes", dict(request_key="uncertain", body="A note", source=source))
        self.assertEqual(recovered[0], 200)
        self.assertEqual(self.call("POST", "/notes", dict(request_key="uncertain", body="A note", source=source))[1], recovered[1])
        self.assertEqual(len(self.db.rows[ResearchArtifact]), 1)

    def test_readonly_allowlists_remain_closed_and_main_mount_is_unconfigured(self):
        tree = ast.parse((BACKEND / "app/release_policy.py").read_text())
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in {
                    "READONLY_ROUTES", "FINANCIAL_ONLY_ROUTES"} for t in node.targets):
                self.assertFalse(any("private" in path for _, path in ast.literal_eval(node.value.args[0])))
        main = ast.parse((BACKEND / "app/main.py").read_text())
        mounts = [n for n in ast.walk(main) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                  and n.func.attr == "mount" and n.args and isinstance(n.args[0], ast.Constant)
                  and n.args[0].value == "/private-research"]
        self.assertEqual(len(mounts), 1)
        self.assertIsInstance(mounts[0].args[1], ast.Call)
        self.assertEqual(mounts[0].args[1].func.id, "PrivateWorkspace")
        self.assertEqual(mounts[0].args[1].args, [])
        self.assertEqual(mounts[0].args[1].keywords, [])


if __name__ == "__main__":
    try:
        unittest.main()
    finally:
        LOOP.run_until_complete(LOOP.shutdown_default_executor())
        LOOP.close()
