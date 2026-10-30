"""Dormant ownership transactions. No engine factory, configuration, HTTP or financial I/O.

The trusted server supplies a dedicated PostgreSQL session factory and verifier at
composition time. Entry points accept raw tokens, never caller-approved principals.
Repository injection is deliberately not a public authorization extension point.
"""
from dataclasses import dataclass
import json
import math
import re
from threading import RLock
import time
from uuid import uuid4

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert

from app.account_auth import AuthFailure, SKEW, SingleIssuerVerifier
from app.models import ResearchAccount, ResearchArtifact, ResearchSession
from app.research_contracts import KeyRef


MAX_SESSIONS = 20
MAX_ARTIFACTS = 100
MAX_OUTPUT = 64 * 1024
MAX_REVISION = 2**63 - 1
OPERATION_SECONDS = 5


class OwnershipFailure(ValueError):
    def __init__(self, code, *, commit_state="not_issued", cleanup="closed"):
        self.code, self.commit_state, self.cleanup = code, commit_state, cleanup
        super().__init__(code)


def _require(condition, code="OWNERSHIP_DENIED"):
    if not condition:
        raise OwnershipFailure(code)


def _key(key, namespace):
    _require(type(key) is KeyRef and key.namespace == namespace, "OWNERSHIP_SELECTOR_INVALID")
    # Reconstruct as a shape check; the key's presence is never authority.
    try:
        KeyRef(namespace, key.id)
    except ValueError:
        raise OwnershipFailure("OWNERSHIP_SELECTOR_INVALID") from None
    return key.id


def _request(value):
    _require(type(value) is str and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", value) is not None,
             "OWNERSHIP_SELECTOR_INVALID")
    return value


def _revision(value):
    _require(type(value) is int and 0 < value <= MAX_REVISION, "OWNERSHIP_SELECTOR_INVALID")
    return value


class Cancellation:
    """Non-clearable latch; the same lock orders cancellation and COMMIT dispatch."""
    def __init__(self):
        self._lock, self._cancelled = RLock(), False

    def cancel(self):
        with self._lock:
            self._cancelled = True


class _Operation:
    def __init__(self, cancellation, monotonic):
        _require(cancellation is None or type(cancellation) is Cancellation, "OWNERSHIP_SELECTOR_INVALID")
        self.cancellation = cancellation if cancellation is not None else Cancellation()
        self.clock, self.started = monotonic, monotonic()
        self.last = self.started
        self.commit_state = "not_issued"

    def checkpoint(self, reserve=0):
        now = self.clock()
        _require(type(now) in (int, float) and math.isfinite(now) and now >= self.last,
                 "OWNERSHIP_CLOCK_INVALID")
        self.last = now
        with self.cancellation._lock:
            _require(not self.cancellation._cancelled, "OWNERSHIP_CANCELLED")
        _require(now - self.started + reserve < OPERATION_SECONDS, "OWNERSHIP_DEADLINE")

    def dispatch_commit(self):
        with self.cancellation._lock:
            self.checkpoint(reserve=1)
            # From here, even a driver exception before acknowledgement cannot
            # prove COMMIT was not sent. Never promise rollback of this outcome.
            self.commit_state = "indeterminate"


@dataclass(frozen=True, slots=True)
class OwnedMetadata:
    key: KeyRef
    owner_key: KeyRef
    session_key: KeyRef | None
    revision: int
    state: str
    token_cutoff: int | None = None

    def encode(self):
        def key(value):
            return None if value is None else {"namespace": value.namespace, "id": value.id}
        data = json.dumps(dict(key=key(self.key), owner_key=key(self.owner_key),
            session_key=key(self.session_key), revision=self.revision, state=self.state,
            token_cutoff=self.token_cutoff), sort_keys=True, separators=(",", ":")).encode()
        _require(len(data) <= MAX_OUTPUT, "OWNERSHIP_RESOURCE_LIMIT")
        return data


def _metadata(row):
    if type(row) is ResearchAccount:
        key = KeyRef("principal", row.id)
        return OwnedMetadata(key, key, None, row.revision, "active" if row.enabled else "disabled", row.token_cutoff)
    namespace = "session" if type(row) is ResearchSession else "artifact"
    _require(type(row) in (ResearchSession, ResearchArtifact), "OWNERSHIP_CONTRACT_INVALID")
    return OwnedMetadata(KeyRef(namespace, row.id), KeyRef("principal", row.owner_id),
        KeyRef("session", row.id if namespace == "session" else row.session_id), row.revision, row.state)


class _Repository:
    def __init__(self, session, operation):
        self.session, self.operation = session, operation

    def execute(self, statement):
        self.operation.checkpoint()
        result = self.session.execute(statement)
        self.operation.checkpoint()
        return result

    def prepare(self):
        _require(self.session.get_bind().dialect.name == "postgresql", "OWNERSHIP_DATABASE_UNSUPPORTED")
        self.execute(text("SET TRANSACTION ISOLATION LEVEL READ COMMITTED, READ WRITE"))
        self.execute(text("SET LOCAL lock_timeout = '1s'"))
        self.execute(text("SET LOCAL statement_timeout = '2s'"))
        self.execute(text("SET LOCAL idle_in_transaction_session_timeout = '5s'"))

    def now(self):
        return float(self.execute(select(func.extract("epoch", func.clock_timestamp()))).scalar_one())

    def account(self, identity, create=False):
        if create:
            self.execute(insert(ResearchAccount).values(id=str(uuid4()), issuer=identity.issuer,
                subject=identity.subject, enabled=True, token_cutoff=-1, revision=1)
                .on_conflict_do_nothing(index_elements=["issuer", "subject"]))
        return self.execute(select(ResearchAccount).where(ResearchAccount.issuer == identity.issuer,
            ResearchAccount.subject == identity.subject).with_for_update()).scalar_one_or_none()

    def session_row(self, owner, identifier=None, request=None):
        condition = (ResearchSession.id == identifier if identifier is not None
                     else ResearchSession.request_key == request)
        return self.execute(select(ResearchSession).where(ResearchSession.owner_id == owner, condition)
                            .with_for_update()).scalar_one_or_none()

    def artifact(self, owner, *, session=None, identifier=None, request=None):
        conditions = [ResearchArtifact.owner_id == owner]
        conditions.append(ResearchArtifact.id == identifier if identifier is not None
                          else ResearchArtifact.request_key == request)
        if session is not None:
            conditions.append(ResearchArtifact.session_id == session)
        return self.execute(select(ResearchArtifact).where(*conditions).with_for_update()).scalar_one_or_none()

    def count(self, model, owner):
        return self.execute(select(func.count()).select_from(model).where(model.owner_id == owner)).scalar_one()

    def add(self, row):
        self.operation.checkpoint()
        self.session.add(row)


class OwnershipService:
    """Internal composition only; no route, global instance or production trust installed."""
    def __init__(self, verifier=None, session_factory=None, *, monotonic=time.monotonic):
        _require(verifier is None or type(verifier) is SingleIssuerVerifier, "OWNERSHIP_CONFIGURATION_INVALID")
        self._verifier = verifier if verifier is not None else SingleIssuerVerifier()
        self._sessions, self._monotonic = session_factory, monotonic

    def _run(self, token, action, *, cancellation=None, create_account=False):
        operation = _Operation(cancellation, self._monotonic)
        operation.checkpoint()
        identity = self._verifier.verify_principal(token)
        _require(self._sessions is not None, "OWNERSHIP_UNAVAILABLE")
        session = None
        result = None
        failure = None
        cleanup = "closed"
        began = False
        try:
            operation.checkpoint()
            session = self._sessions()
            session.begin()
            began = True
            repo = _Repository(session, operation)
            repo.prepare()
            account = repo.account(identity, create=create_account)
            _require(account is not None and account.enabled)

            def authorize():
                operation.checkpoint()
                database_time = repo.now()
                self._verifier.recheck(identity, database_time=database_time)
                _require(identity.issued_at > account.token_cutoff)
                return database_time

            database_time = authorize()
            row = action(repo, account, database_time)
            operation.checkpoint()
            session.flush()
            result = _metadata(row)
            result.encode()  # Validate detached output before COMMIT.
            # Invalidation deliberately invalidates this token as its own effect.
            if type(row) is ResearchAccount:
                self._verifier.recheck(identity, database_time=repo.now())
            else:
                authorize()
            operation.dispatch_commit()
            session.commit()
            operation.commit_state = "confirmed"
        except BaseException as error:
            if operation.commit_state == "indeterminate":
                failure = OwnershipFailure("OWNERSHIP_COMMIT_INDETERMINATE")
            elif isinstance(error, (OwnershipFailure, AuthFailure)):
                failure = error
            else:
                failure = OwnershipFailure("OWNERSHIP_DATABASE_FAILURE")
            if session is not None and began and operation.commit_state == "not_issued":
                try:
                    session.rollback()
                except BaseException:
                    cleanup = "unverified"
        finally:
            if session is not None:
                if cleanup == "unverified" or operation.commit_state == "indeterminate":
                    try:
                        session.invalidate()
                    except BaseException:
                        cleanup = "unverified"
                try:
                    session.close()
                except BaseException:
                    cleanup = "unverified"
                    try:
                        session.invalidate()
                    except BaseException:
                        pass
        if cleanup != "closed":
            failure = OwnershipFailure("OWNERSHIP_COMMIT_INDETERMINATE" if operation.commit_state == "indeterminate"
                                       else "OWNERSHIP_CLEANUP_UNVERIFIED")
        if failure is not None:
            if isinstance(failure, AuthFailure):
                raise OwnershipFailure(failure.code, commit_state=operation.commit_state, cleanup=cleanup) from None
            failure.commit_state, failure.cleanup = operation.commit_state, cleanup
            raise failure from None
        try:
            operation.checkpoint()
            self._verifier.recheck(identity)
        except (OwnershipFailure, AuthFailure) as error:
            raise OwnershipFailure(error.code, commit_state=operation.commit_state) from None
        return result

    @staticmethod
    def _live(row, expected=None):
        _require(row is not None and row.state in {"active", "reserved"})
        if expected is not None:
            _require(row.revision == expected, "OWNERSHIP_REVISION_CHANGED")
        return row

    def create_session(self, token, request_key, *, cancellation=None):
        request_key = _request(request_key)
        def allocate(repo, account, now):
            row = repo.session_row(account.id, request=request_key)
            if row is not None:
                return self._live(row)
            _require(repo.count(ResearchSession, account.id) < MAX_SESSIONS, "OWNERSHIP_QUOTA_EXCEEDED")
            row = ResearchSession(id=str(uuid4()), owner_id=account.id, request_key=request_key,
                                  state="active", revision=1)
            repo.add(row)
            return row
        return self._run(token, allocate, cancellation=cancellation, create_account=True)

    def resolve_session(self, token, session_key, expected_revision, *, cancellation=None):
        identifier, revision = _key(session_key, "session"), _revision(expected_revision)
        return self._run(token, lambda repo, account, now:
            self._live(repo.session_row(account.id, identifier), revision), cancellation=cancellation)

    def reserve_artifact(self, token, session_key, expected_revision, request_key, *, cancellation=None):
        identifier, revision = _key(session_key, "session"), _revision(expected_revision)
        request_key = _request(request_key)
        def allocate(repo, account, now):
            parent = self._live(repo.session_row(account.id, identifier), revision)
            row = repo.artifact(account.id, request=request_key)
            if row is not None:
                _require(row.session_id == parent.id and row.session_revision == revision,
                         "OWNERSHIP_IDEMPOTENCY_CONFLICT")
                return self._live(row)
            _require(repo.count(ResearchArtifact, account.id) < MAX_ARTIFACTS, "OWNERSHIP_QUOTA_EXCEEDED")
            row = ResearchArtifact(id=str(uuid4()), owner_id=account.id, session_id=parent.id,
                session_revision=revision, request_key=request_key, state="reserved", revision=1)
            repo.add(row)
            return row
        return self._run(token, allocate, cancellation=cancellation)

    def resolve_artifact(self, token, session_key, session_revision, artifact_key, expected_revision, *, cancellation=None):
        parent_id, parent_revision = _key(session_key, "session"), _revision(session_revision)
        identifier, revision = _key(artifact_key, "artifact"), _revision(expected_revision)
        def resolve(repo, account, now):
            self._live(repo.session_row(account.id, parent_id), parent_revision)
            row = self._live(repo.artifact(account.id, session=parent_id, identifier=identifier), revision)
            _require(row.session_revision == parent_revision, "OWNERSHIP_REVISION_CHANGED")
            return row
        return self._run(token, resolve, cancellation=cancellation)

    def revoke_session(self, token, session_key, expected_revision, *, cancellation=None):
        identifier, revision = _key(session_key, "session"), _revision(expected_revision)
        def revoke(repo, account, now):
            row = repo.session_row(account.id, identifier)
            _require(row is not None)
            if row.state == "revoked" and row.revision == revision + 1:
                return row  # Authenticated reconciliation of the same transition.
            self._live(row, revision)
            _require(row.revision < MAX_REVISION, "OWNERSHIP_RESOURCE_LIMIT")
            row.state, row.revision = "revoked", row.revision + 1
            return row
        return self._run(token, revoke, cancellation=cancellation)

    def invalidate_account_tokens(self, token, *, cancellation=None):
        def invalidate(repo, account, now):
            _require(account.revision < MAX_REVISION, "OWNERSHIP_RESOURCE_LIMIT")
            # Use a fresh DB wall-clock sample after taking the account lock;
            # neither transaction-start time nor a caller timestamp is accepted.
            now = repo.now()
            self._verifier.recheck(identity := self._verifier.verify_principal(token), database_time=now)
            _require(identity.issued_at > account.token_cutoff)
            account.token_cutoff = max(account.token_cutoff, math.ceil(now) + SKEW)
            account.revision += 1
            return account
        return self._run(token, invalidate, cancellation=cancellation)
