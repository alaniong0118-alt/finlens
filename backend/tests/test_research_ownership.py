"""Offline ownership/unit and PostgreSQL DDL checks; never database acceptance.

Import the shared test guard before application modules. No real database tests
are invoked or database URLs discovered. All transaction state below is a fake.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_account_auth import CryptoFixtures, auth, forbidden

import ast
import copy
from dataclasses import FrozenInstanceError
import importlib.util
import io
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable, ForeignKeyConstraint, UniqueConstraint

from app import research_ownership as own
from app.models import Base, ResearchAccount, ResearchArtifact, ResearchSession
from app.research_contracts import KeyRef


class FakeDatabase:
    """Unit simulation only: does not implement PostgreSQL locks or constraints."""
    def __init__(self, clock):
        self.clock = clock
        self.rows = {ResearchAccount: {}, ResearchSession: {}, ResearchArtifact: {}}
        self.events, self.hooks = [], {}
        self.offset = 0
        self.commit_error = None
        self.rollback_error = self.close_error = False

    def fire(self, event):
        self.events.append(event)
        if event in self.hooks:
            self.hooks[event]()

    def factory(self):
        self.fire("factory")
        return FakeSession(self)


class FakeSession:
    def __init__(self, db):
        self.db = db

    def begin(self):
        self.db.fire("begin")
        self.rows = copy.deepcopy(self.db.rows)

    def flush(self):
        self.db.fire("flush")

    def commit(self):
        self.db.fire("commit_before")
        if self.db.commit_error == "before":
            raise RuntimeError("private database diagnostic")
        self.db.rows = copy.deepcopy(self.rows)
        self.db.fire("commit_after")
        if self.db.commit_error == "after":
            raise RuntimeError("private database diagnostic")

    def rollback(self):
        self.db.fire("rollback")
        if self.db.rollback_error:
            raise RuntimeError("private rollback diagnostic")

    def invalidate(self):
        self.db.fire("invalidate")

    def close(self):
        self.db.fire("close")
        if self.db.close_error:
            raise RuntimeError("private close diagnostic")


class FakeRepository:
    def __init__(self, session, operation):
        self.session, self.operation = session, operation
        self.db = session.db

    def prepare(self):
        self.db.fire("prepare")

    def now(self):
        self.db.fire("database_time")
        return self.db.clock.wall + self.db.offset

    def account(self, identity, create=False):
        self.db.fire("account_lock")
        rows = self.session.rows[ResearchAccount]
        row = next((r for r in rows.values() if (r.issuer, r.subject) == (identity.issuer, identity.subject)), None)
        if row is None and create:
            row = ResearchAccount(id=str(own.uuid4()), issuer=identity.issuer, subject=identity.subject,
                                  enabled=True, revision=1, token_cutoff=-1)
            rows[row.id] = row
        return row

    def session_row(self, owner, identifier=None, request=None):
        self.db.fire("session_lock")
        return next((r for r in self.session.rows[ResearchSession].values() if r.owner_id == owner
            and (r.id == identifier if identifier is not None else r.request_key == request)), None)

    def artifact(self, owner, *, session=None, identifier=None, request=None):
        self.db.fire("artifact_lock")
        return next((r for r in self.session.rows[ResearchArtifact].values() if r.owner_id == owner
            and (session is None or session == r.session_id)
            and (r.id == identifier if identifier is not None else r.request_key == request)), None)

    def count(self, model, owner):
        self.db.fire("count")
        return sum(r.owner_id == owner for r in self.session.rows[model].values())

    def add(self, row):
        self.db.fire("add")
        self.session.rows[type(row)][row.id] = row


class OwnershipTests(CryptoFixtures):
    def setUp(self):
        super().setUp()
        self.db = FakeDatabase(self.clock)
        self.repository_patch = patch.object(own, "_Repository", FakeRepository)
        self.repository_patch.start()
        self.addCleanup(self.repository_patch.stop)
        self.service = own.OwnershipService(self.verifier, self.db.factory, monotonic=lambda: self.clock.mono)
        self.alice = self.token()
        self.bob = self.token(sub="offline-bob")

    def fails(self, callback, code, state="not_issued"):
        with self.assertRaises((own.OwnershipFailure, auth.AuthFailure)) as caught:
            callback()
        self.assertEqual(caught.exception.code, code)
        if isinstance(caught.exception, own.OwnershipFailure):
            self.assertEqual(caught.exception.commit_state, state)
        return caught.exception

    def create(self, request="session-1", token=None, **kwargs):
        return self.service.create_session(token or self.alice, request, **kwargs)

    def test_dormant_configuration_denies_before_factory(self):
        service = own.OwnershipService(session_factory=forbidden)
        self.fails(lambda: service.create_session(self.alice, "request"), "AUTH_UNAVAILABLE")
        self.fails(lambda: self.create(token="invalid"), "AUTH_INVALID")
        self.assertEqual(self.db.events, [])

    def test_account_identity_stable_and_email_is_not_identity(self):
        a = self.create()
        b = self.create("second", self.token(email="untrusted@example.invalid"))
        c = self.create("third", self.token(sub="offline-bob", email="untrusted@example.invalid"))
        self.assertEqual(a.owner_key, b.owner_key)
        self.assertNotEqual(a.owner_key, c.owner_key)
        self.assertEqual(len(self.db.rows[ResearchAccount]), 2)

    def test_chain_detached_metadata_and_lock_order(self):
        session = self.create()
        self.db.events.clear()
        artifact = self.service.reserve_artifact(self.alice, session.key, 1, "artifact-1")
        locks = [e for e in self.db.events if e.endswith("_lock")]
        self.assertEqual(locks, ["account_lock", "session_lock", "artifact_lock"])
        result = self.service.resolve_artifact(self.alice, session.key, 1, artifact.key, 1)
        self.assertEqual(artifact, result)
        self.assertIsInstance(json.loads(result.encode()), dict)
        with self.assertRaises(FrozenInstanceError):
            result.state = "trusted"
        self.db.rows[ResearchArtifact][artifact.key.id].state = "revoked"
        self.assertEqual(result.state, "reserved")
        self.assertFalse(set(json.loads(result.encode())) & {"value", "fact_id", "body", "admitted", "token"})

    def test_foreign_and_missing_session_artifact_denials_match(self):
        session = self.create()
        artifact = self.service.reserve_artifact(self.alice, session.key, 1, "artifact-1")
        bob = self.create("bob-session", self.bob)
        calls = [lambda: self.service.resolve_session(self.bob, session.key, 1),
                 lambda: self.service.resolve_session(self.bob, KeyRef("session", "missing"), 1),
                 lambda: self.service.reserve_artifact(self.bob, session.key, 1, "guess"),
                 lambda: self.service.resolve_artifact(self.bob, bob.key, 1, artifact.key, 1),
                 lambda: self.service.resolve_artifact(self.bob, bob.key, 1, KeyRef("artifact", "missing"), 1)]
        for call in calls:
            self.fails(call, "OWNERSHIP_DENIED")

    def test_revision_namespace_and_request_validation(self):
        session = self.create()
        self.fails(lambda: self.service.resolve_session(self.alice, session.key, 2), "OWNERSHIP_REVISION_CHANGED")
        for key, rev in ((KeyRef("artifact", "x"), 1), (session.key, True), (session.key, 0)):
            self.fails(lambda: self.service.resolve_session(self.alice, key, rev), "OWNERSHIP_SELECTOR_INVALID")
        for value in ("", "x" * 129, "path/name", None):
            self.fails(lambda: self.create(value), "OWNERSHIP_SELECTOR_INVALID")

    def test_allocation_replay_owner_operation_session_and_revision(self):
        a = self.create()
        self.assertEqual(self.create(), a)
        b = self.create(token=self.bob)
        self.assertNotEqual(a.owner_key, b.owner_key)
        artifact = self.service.reserve_artifact(self.alice, a.key, 1, "same-key")
        self.assertEqual(artifact, self.service.reserve_artifact(self.alice, a.key, 1, "same-key"))
        other = self.create("second")
        self.fails(lambda: self.service.reserve_artifact(self.alice, other.key, 1, "same-key"),
                   "OWNERSHIP_IDEMPOTENCY_CONFLICT")
        # The same request spelling for a different operation has a separate namespace.
        self.create("same-key")
        self.assertEqual(len(self.db.rows[ResearchArtifact]), 1)

    def test_quota_exact_limit_replay_and_revoked_records_still_count(self):
        sessions = [self.create(f"session-{i}") for i in range(20)]
        self.assertEqual(self.create("session-0"), sessions[0])
        self.service.revoke_session(self.alice, sessions[-1].key, 1)
        self.fails(lambda: self.create("one-over"), "OWNERSHIP_QUOTA_EXCEEDED")
        artifacts = [self.service.reserve_artifact(self.alice, sessions[0].key, 1, f"artifact-{i}") for i in range(100)]
        self.assertEqual(self.service.reserve_artifact(self.alice, sessions[0].key, 1, "artifact-0"), artifacts[0])
        self.fails(lambda: self.service.reserve_artifact(self.alice, sessions[0].key, 1, "one-over"),
                   "OWNERSHIP_QUOTA_EXCEEDED")

    def test_revocation_replay_and_access_after_revocation(self):
        session = self.create()
        artifact = self.service.reserve_artifact(self.alice, session.key, 1, "artifact")
        revoked = self.service.revoke_session(self.alice, session.key, 1)
        self.assertEqual((revoked.state, revoked.revision), ("revoked", 2))
        self.assertEqual(self.service.revoke_session(self.alice, session.key, 1), revoked)
        for call in (lambda: self.create(), lambda: self.service.resolve_session(self.alice, session.key, 1),
                     lambda: self.service.resolve_artifact(self.alice, session.key, 1, artifact.key, 1),
                     lambda: self.service.reserve_artifact(self.alice, session.key, 1, "artifact")):
            self.fails(call, "OWNERSHIP_DENIED")

    def test_invalidation_rejects_future_skew_and_requires_new_token_for_replay(self):
        session = self.create()
        future_token = self.token(iat=int(self.clock.wall) + 30)
        account = self.service.invalidate_account_tokens(self.alice)
        self.assertEqual(account.token_cutoff, int(self.clock.wall) + 30)
        for token in (self.alice, future_token):
            self.fails(lambda: self.create(token=token), "OWNERSHIP_DENIED")
        self.clock.advance(31)
        fresh = self.token()
        self.assertEqual(self.create(token=fresh), session)
        self.clock.wall -= 1  # Small wall adjustment; monotonic time never rewinds.
        self.fails(lambda: self.create(token=self.token()), "OWNERSHIP_DENIED")
        self.assertEqual(self.db.rows[ResearchAccount][account.key.id].token_cutoff, account.token_cutoff)

    def test_database_clock_skew_failure_rolls_back_first_account(self):
        self.db.offset = 31
        self.fails(lambda: self.create(), "AUTH_CLOCK_INVALID")
        self.assertEqual(self.db.rows[ResearchAccount], {})
        self.assertIn("rollback", self.db.events)

    def test_cancellation_before_commit_rolls_back_all_pending_rows(self):
        cancel = own.Cancellation()
        self.db.hooks["flush"] = cancel.cancel
        self.fails(lambda: self.create(cancellation=cancel), "OWNERSHIP_CANCELLED")
        self.assertEqual(self.db.rows[ResearchAccount], {})
        self.assertEqual(self.db.rows[ResearchSession], {})
        self.assertNotIn("commit_before", self.db.events)

    def test_cancellation_after_commit_persists_and_reconciles_same_allocation(self):
        cancel = own.Cancellation()
        self.db.hooks["commit_after"] = cancel.cancel
        self.fails(lambda: self.create(cancellation=cancel), "OWNERSHIP_CANCELLED", "confirmed")
        self.assertEqual(len(self.db.rows[ResearchSession]), 1)
        self.assertNotIn("rollback", self.db.events)
        self.db.hooks.clear()
        result = self.create()
        self.assertEqual(len(self.db.rows[ResearchSession]), 1)
        self.assertIn(result.key.id, self.db.rows[ResearchSession])

    def test_commit_failure_before_or_after_ack_is_indeterminate_without_rollback_claim(self):
        for point, persisted in (("before", False), ("after", True)):
            with self.subTest(point=point):
                self.db.commit_error = point
                self.db.events.clear()
                self.fails(lambda: self.create(point), "OWNERSHIP_COMMIT_INDETERMINATE", "indeterminate")
                self.assertEqual(any(r.request_key == point for r in self.db.rows[ResearchSession].values()), persisted)
                self.assertNotIn("rollback", self.db.events)
                self.assertIn("invalidate", self.db.events)
        self.db.commit_error = None
        self.create("after")
        self.assertEqual(len(self.db.rows[ResearchSession]), 1)

    def test_indeterminate_allocation_retry_still_checks_invalidation(self):
        self.db.commit_error = "after"
        self.fails(lambda: self.create(), "OWNERSHIP_COMMIT_INDETERMINATE", "indeterminate")
        self.db.commit_error = None
        self.service.invalidate_account_tokens(self.alice)
        self.fails(lambda: self.create(), "OWNERSHIP_DENIED")
        self.assertEqual(len(self.db.rows[ResearchSession]), 1)

    def test_cancellation_during_commit_failure_remains_indeterminate(self):
        cancel = own.Cancellation()
        self.db.hooks["commit_before"] = cancel.cancel
        self.db.commit_error = "after"
        self.fails(lambda: self.create(cancellation=cancel), "OWNERSHIP_COMMIT_INDETERMINATE", "indeterminate")

    def test_cleanup_failure_withholds_confirmed_result_and_no_private_error(self):
        self.db.close_error = True
        error = self.fails(lambda: self.create(), "OWNERSHIP_CLEANUP_UNVERIFIED", "confirmed")
        self.assertEqual(error.cleanup, "unverified")
        self.assertNotIn("private", str(error))
        self.assertEqual(len(self.db.rows[ResearchSession]), 1)
        self.assertIn("invalidate", self.db.events)

    def test_rollback_cleanup_failure_is_not_success(self):
        self.db.rollback_error = True
        self.db.hooks["flush"] = lambda: (_ for _ in ()).throw(RuntimeError("private"))
        self.fails(lambda: self.create(), "OWNERSHIP_CLEANUP_UNVERIFIED")
        self.assertEqual(len(self.db.rows[ResearchSession]), 0)
        self.assertIn("invalidate", self.db.events)

    def test_token_expiry_at_final_check_and_configuration_loss_after_commit(self):
        self.db.hooks["flush"] = lambda: self.clock.advance(331)
        self.fails(lambda: self.create(), "OWNERSHIP_DEADLINE")
        self.db.hooks.clear()
        self.alice = self.token()
        self.db.hooks["close"] = lambda: self.verifier.install_snapshot(self.make_snapshot(revision=2))
        self.fails(lambda: self.create(), "AUTH_CONFIGURATION_CHANGED", "confirmed")

    def test_token_expiry_within_operation_deadline_prevents_commit(self):
        self.alice = self.token(iat=int(self.clock.wall) - 300, exp=int(self.clock.wall) - 29)
        self.db.hooks["flush"] = lambda: self.clock.advance(1)
        self.fails(lambda: self.create(), "AUTH_INVALID")
        self.assertEqual(self.db.rows[ResearchSession], {})
        self.assertNotIn("commit_before", self.db.events)

    def test_confirmed_artifact_survives_withheld_delivery_and_replay_is_bounded(self):
        session = self.create()
        cancel = own.Cancellation()
        self.db.hooks["commit_after"] = cancel.cancel
        self.fails(lambda: self.service.reserve_artifact(self.alice, session.key, 1, "artifact", cancellation=cancel),
                   "OWNERSHIP_CANCELLED", "confirmed")
        self.assertEqual(len(self.db.rows[ResearchArtifact]), 1)
        self.db.hooks.clear()
        self.service.revoke_session(self.alice, session.key, 1)
        self.fails(lambda: self.service.reserve_artifact(self.alice, session.key, 1, "artifact"), "OWNERSHIP_DENIED")

    def test_monotone_cutoff_never_restores_invalidated_tokens(self):
        self.create()
        # A previously stored cutoff ahead of the local wall clock stays binding.
        account = next(iter(self.db.rows[ResearchAccount].values()))
        account.token_cutoff = int(self.clock.wall) + 10
        self.fails(lambda: self.service.invalidate_account_tokens(self.alice), "OWNERSHIP_DENIED")
        self.assertEqual(self.db.rows[ResearchAccount][account.id].token_cutoff, account.token_cutoff)
        self.clock.advance(11)
        cutoff = self.service.invalidate_account_tokens(self.token()).token_cutoff
        self.assertGreater(cutoff, account.token_cutoff)

    def test_database_clock_bounds_include_exact_skew_and_reject_nonfinite(self):
        for offset in (30, -30):
            self.db.offset = offset
            self.create(f"offset-{offset}")
        self.db.offset = float("nan")
        self.fails(lambda: self.create("not-finite"), "AUTH_CLOCK_INVALID")

    def test_unit_transaction_order_and_no_implicit_account_for_resolve(self):
        self.fails(lambda: self.service.resolve_session(self.bob, KeyRef("session", "missing"), 1),
                   "OWNERSHIP_DENIED")
        self.assertEqual(self.db.rows[ResearchAccount], {})
        self.db.events.clear()
        self.create()
        events = self.db.events
        for first, second in (("begin", "prepare"), ("account_lock", "session_lock"),
                              ("add", "flush"), ("flush", "commit_before"), ("commit_after", "close")):
            self.assertLess(events.index(first), events.index(second))
        self.assertNotIn("rollback", events)

    def test_limits_cancellation_latch_and_no_clock_callback_from_request(self):
        cancel = own.Cancellation()
        cancel.cancel()
        self.fails(lambda: self.create(cancellation=cancel), "OWNERSHIP_CANCELLED")
        self.assertEqual(self.db.events, [])
        self.fails(lambda: self.create(cancellation=SimpleNamespace()), "OWNERSHIP_SELECTOR_INVALID")
        result = self.create()
        size = len(result.encode())
        with patch.object(own, "MAX_OUTPUT", size):
            self.assertEqual(len(result.encode()), size)
        with patch.object(own, "MAX_OUTPUT", size - 1):
            self.fails(result.encode, "OWNERSHIP_RESOURCE_LIMIT")

    def test_no_raw_token_or_subject_in_detached_output(self):
        output = self.create().encode().decode()
        for private in (self.alice, "offline-alice", self.policy.issuer):
            self.assertNotIn(private, output)


class SchemaAndSQLTests(unittest.TestCase):
    def test_new_migration_compiles_without_environment_or_database(self):
        path = Path(__file__).resolve().parents[1] / "migrations/versions/a7c730103001_add_research_ownership.py"
        spec = importlib.util.spec_from_file_location("ownership_migration", path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        output, tables = io.StringIO(), []
        context = MigrationContext.configure(dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output})
        class RecordingOperations(Operations):
            def create_table(self, *args, **kwargs):
                table = super().create_table(*args, **kwargs)
                tables.append(table)
                return table
        with patch.object(migration, "op", RecordingOperations(context)):
            migration.upgrade()
            with self.assertRaises(RuntimeError):
                migration.downgrade()
        self.assertEqual(migration.down_revision, "f94c6f41e0cb")
        self.assertEqual({t.name for t in tables}, {"research_accounts", "research_sessions", "research_artifacts"})
        for table in tables:
            model = Base.metadata.tables[table.name]
            self.assertEqual([c.name for c in table.columns], [c.name for c in model.columns])
            # DDL comparison covers defaults, nullability, keys, checks and types.
            actual = " ".join(str(CreateTable(table).compile(dialect=postgresql.dialect())).split())
            expected = " ".join(str(CreateTable(model).compile(dialect=postgresql.dialect())).split())
            self.assertEqual(actual, expected)
        self.assertNotIn("DROP", output.getvalue())
        self.assertNotIn("ALTER", output.getvalue())
        self.assertNotIn("app.database", sys.modules)

    def test_composite_owner_foreign_key_and_unique_identity(self):
        artifact = ResearchArtifact.__table__
        pairs = [tuple((e.parent.name, e.target_fullname) for e in c.elements)
                 for c in artifact.constraints if isinstance(c, ForeignKeyConstraint)]
        self.assertIn((("owner_id", "research_sessions.owner_id"), ("session_id", "research_sessions.id")), pairs)
        identity = [tuple(c.columns.keys()) for c in ResearchAccount.__table__.constraints if isinstance(c, UniqueConstraint)]
        self.assertIn(("issuer", "subject"), identity)
        for model in (ResearchAccount, ResearchSession, ResearchArtifact):
            for name in ("id", "owner_id", "session_id", "request_key", "issuer", "subject"):
                if name in model.__table__.columns:
                    self.assertEqual(model.__table__.columns[name].type.collation, "C")
        self.assertFalse(set(artifact.columns.keys()) & {"body", "value", "fact_id", "source", "admitted"})

    def test_migration_graph_single_additive_head(self):
        versions = Path(__file__).resolve().parents[1] / "migrations/versions"
        graph = {}
        for path in versions.glob("*.py"):
            assignments = {}
            for node in ast.parse(path.read_text(encoding="utf-8")).body:
                if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                    assignments[node.target.id] = node.value
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            assignments[target.id] = node.value
            graph[ast.literal_eval(assignments["revision"])] = ast.literal_eval(assignments["down_revision"])
        self.assertEqual(set(graph) - {v for v in graph.values() if v is not None}, {"a7c730103001"})
        seen, cursor = set(), "a7c730103001"
        while cursor is not None:
            self.assertNotIn(cursor, seen)
            seen.add(cursor)
            cursor = graph[cursor]
        self.assertEqual(seen, set(graph))

    def test_repository_queries_bind_owner_and_fixed_transaction_controls(self):
        statements = []
        class Session:
            def get_bind(self):
                return SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))
            def execute(self, statement):
                statements.append(statement)
                return SimpleNamespace(scalar_one_or_none=lambda: None, scalar_one=lambda: 0)
        repo = own._Repository(Session(), own._Operation(None, __import__("time").monotonic))
        repo.prepare()
        repo.account(SimpleNamespace(issuer="https://offline.invalid/", subject="user"), create=True)
        repo.session_row("owner", "session")
        repo.artifact("owner", session="session", identifier="artifact")
        repo.count(ResearchArtifact, "owner")
        repo.now()
        sql = [str(s.compile(dialect=postgresql.dialect())) for s in statements]
        self.assertEqual(sql[:4], ["SET TRANSACTION ISOLATION LEVEL READ COMMITTED, READ WRITE",
            "SET LOCAL lock_timeout = '1s'", "SET LOCAL statement_timeout = '2s'",
            "SET LOCAL idle_in_transaction_session_timeout = '5s'"])
        self.assertIn("ON CONFLICT (issuer, subject) DO NOTHING", sql[4])
        for query in sql[5:8]:
            self.assertIn("FOR UPDATE", query)
        self.assertIn("research_sessions.owner_id =", sql[6])
        self.assertIn("research_artifacts.owner_id =", sql[7])
        self.assertIn("research_artifacts.session_id =", sql[7])
        self.assertIn("clock_timestamp()", sql[9])


if __name__ == "__main__":
    unittest.main(verbosity=2)
