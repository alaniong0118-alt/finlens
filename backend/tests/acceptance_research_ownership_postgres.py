"""Dormant real-PG worker and standalone new OFFLINE checks; not pytest-discovered.

Default/help/import never load application or DB packages. --offline runs only
new fake-adapter/refusal checks under positive operational guards. The private
worker entry is composed by the reviewed launcher, not a public DSN entrypoint.
"""
import argparse
import builtins
from contextlib import contextmanager
import hashlib
import importlib.abc
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import sys
import threading
import time
from uuid import uuid4
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[2]


class AcceptanceFailure(AssertionError):
    pass


def check(value, code):
    if not value:
        raise AcceptanceFailure(code)


def launcher_module():
    name = "ucr_ownership_pg_launcher"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, ROOT / "backend/scripts/accept_research_ownership_postgres.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


def protect_env_files():
    def wrap(original):
        def guarded(path, *args, **kwargs):
            if isinstance(path, (str, bytes, os.PathLike)):
                name = os.fsdecode(os.fspath(path)).replace("\\", "/").rsplit("/", 1)[-1]
                check(name != ".env" and not name.startswith(".env."), "environment_file_forbidden")
            return original(path, *args, **kwargs)
        return guarded
    builtins.open, io.open, os.open = wrap(builtins.open), wrap(io.open), wrap(os.open)


def runtime_guard(payload):
    protect_env_files()
    allowed = {"app", "app.account_auth", "app.research_ownership", "app.models", "app.orm_base", "app.research_contracts",
               "app.private_workspace_http"}

    class Guard(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if (fullname.startswith("app.") and fullname not in allowed
                    or fullname.split(".")[0] in {"dotenv", "fastapi", "uvicorn", "openai", "httpx", "requests",
                                                  "torch", "sentence_transformers", "sqlite3"}
                    or fullname == "urllib.request"):
                raise AcceptanceFailure("operational_import_forbidden")
    sys.meta_path.insert(0, Guard())

    def audit(event, args):
        if event.startswith("subprocess.") or event in {"os.system", "sqlite3.connect"}:
            raise AcceptanceFailure("worker_process_forbidden")
        if event == "socket.connect":
            address = args[1]
            check(isinstance(address, tuple) and address[:2] == ("127.0.0.1", payload["port"]), "foreign_socket_forbidden")
        if event == "socket.getaddrinfo":
            check(args[0] == "127.0.0.1" and int(args[1]) == payload["port"], "dns_forbidden")
    sys.addaudithook(audit)


def emit(event, **values):
    print(json.dumps(dict(event=event, **values), separators=(",", ":")), flush=True)


def validate_payload(p):
    check(type(p) is dict and set(p) == {"nonce", "port", "database", "admin", "service", "admin_password",
                                       "service_password", "system_identifier", "container_id", "migration_directory"}, "worker_payload_invalid")
    check(type(p["nonce"]) is str and re.fullmatch(r"[0-9a-f]{32}", p["nonce"]), "worker_nonce_invalid")
    for key, prefix in (("database", "ucr_db_"), ("admin", "ucr_admin_"), ("service", "ucr_svc_")):
        check(p[key] == prefix + p["nonce"], "worker_target_invalid")
    check(type(p["port"]) is int and 1024 <= p["port"] <= 65535 and p["port"] != 5432, "worker_port_invalid")
    for key in ("admin_password", "service_password"):
        check(type(p[key]) is str and re.fullmatch(r"[A-Za-z0-9_-]{40,64}", p[key]), "worker_credentials_invalid")
    check(re.fullmatch(r"[0-9a-f]{64}", p["container_id"]) and re.fullmatch(r"[0-9]+", p["system_identifier"]),
          "worker_cluster_binding_invalid")
    local = os.environ.get("LOCALAPPDATA", "")
    check(bool(local) and Path(p["migration_directory"]) == Path(local) / "FinLens/ownership-acceptance" / p["nonce"] / "migration",
          "worker_migration_directory_invalid")


CHAIN = ("e4dda2eedbb0", "36134e0d3560", "77068e51af12", "d7b834408ba8", "f94c6f41e0cb", "a7c730103001", "b8d741104001")


class PostgreSQLAcceptance:
    """Real service tests only. No replacement repositories or asserted principals."""
    def __init__(self, payload):
        self.p, self.launcher = payload, launcher_module()
        self.observer, self.engine, self.bootstrap = None, None, None
        self.local, self.hook = threading.local(), None
        self.flush_hook, self.commit_hook, self.session_patch = None, None, None
        self.pids, self.drivers, self.invalidated, self.index = {}, [], [], 0
        self.checkouts = 0

    def connect_parameters(self, user):
        p = self.p
        return dict(host="127.0.0.1", hostaddr="127.0.0.1", port=p["port"], dbname=p["database"], user=p[user],
                    password=p[user + "_password"], connect_timeout=2, sslmode="disable",
                    application_name="ucr_" + p["nonce"] + "_" + user,
                    options="-c statement_timeout=2000 -c lock_timeout=1000 -c idle_in_transaction_session_timeout=5000")

    def setup(self):
        import psycopg
        from psycopg import sql
        from sqlalchemy import create_engine, event, text
        from sqlalchemy.engine import URL
        from sqlalchemy.orm import Session, sessionmaker
        from app import account_auth, research_ownership
        from app.research_contracts import KeyRef, DatabasePublicationRef, TimePoint, encode
        from app.private_workspace_http import PrivateWorkspace
        from cryptography.hazmat.primitives.asymmetric import rsa
        import jwt
        self.pg, self.sql, self.event, self.text, self.auth, self.own = psycopg, sql, event, text, account_auth, research_ownership
        self.KeyRef, self.jwt = KeyRef, jwt
        self.workspace_type = PrivateWorkspace
        self.source = DatabasePublicationRef(entity_key=KeyRef("sec_cik", "0000000001"), origin="sec", owner_key=None,
            session_key=None, source_descriptor_key=None, source_revision_key=None, rights_policy_key=None,
            admission_record_key=None, public_available_at=TimePoint.unknown(), retrieved_at=TimePoint.unknown(),
            accession="0000000001-24-000001", publication_data_version=7, evidence_version=7, data_version=7,
            manifest_sha256="a" * 64, chunk_id=None)
        self.source_wire = json.loads(encode(self.source))
        self.original_connect = psycopg.Connection.connect.__func__

        def guarded_connect(cls, conninfo="", **kwargs):
            check(conninfo == "", "conninfo_forbidden")
            permitted = self.connect_parameters("service" if kwargs.get("user") == self.p["service"] else "admin")
            for key in ("host", "hostaddr", "port", "user", "password", "connect_timeout", "sslmode", "options", "application_name"):
                check(str(kwargs.get(key)) == str(permitted[key]), "driver_destination_or_bounds_changed")
            check(kwargs.get("dbname") in {self.p["database"], "postgres", "template1"}
                  and set(kwargs) <= set(permitted) | {"autocommit", "context", "row_factory", "cursor_factory", "prepare_threshold"},
                  "driver_override_forbidden")
            return self.original_connect(cls, **kwargs)
        psycopg.Connection.connect = classmethod(guarded_connect)
        psycopg.connect = psycopg.Connection.connect

        def engine(user):
            params = self.connect_parameters(user)
            url = URL.create("postgresql+psycopg", username=params.pop("user"), password=params.pop("password"),
                             host=params.pop("host"), port=params.pop("port"), database=params.pop("dbname"))
            return create_engine(url, connect_args=params, pool_size=2 if user == "service" else 1,
                                 max_overflow=0, pool_timeout=1, pool_pre_ping=False, use_native_hstore=False, echo=False)

        self.bootstrap = engine("admin")
        migration_deadline = time.monotonic() + 60
        from alembic import command
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        folder = Path(self.p["migration_directory"])
        check(not folder.is_symlink() and (folder / "env.py").read_bytes() == self.launcher.MIGRATION_ENV.encode(),
              "migration_environment_changed")
        with self.bootstrap.connect() as connection:
            check(str(connection.exec_driver_sql("SELECT system_identifier FROM pg_control_system()").scalar_one())
                  == self.p["system_identifier"], "prewrite_cluster_identity_mismatch")
            check(int(connection.exec_driver_sql("SHOW server_version_num").scalar_one()) // 10000 == 16
                  and connection.exec_driver_sql("SELECT current_database()").scalar_one() == self.p["database"]
                  and connection.exec_driver_sql("SELECT current_user").scalar_one() == self.p["admin"], "prewrite_target_mismatch")
            config = Config()
            config.set_main_option("script_location", str(folder))
            config.set_main_option("version_locations", str(ROOT / "backend/migrations/versions"))
            config.set_main_option("path_separator", "os")
            script = ScriptDirectory.from_config(config)
            check(tuple(reversed([r.revision for r in script.walk_revisions()])) == CHAIN, "migration_graph_changed")
            connection.exec_driver_sql("CREATE EXTENSION vector")
            connection.commit()
            config.attributes["connection"] = connection
            command.upgrade(config, CHAIN[-2])
            before = self.snapshot(connection)
            connection.commit()
            command.upgrade(config, CHAIN[-1])
            check(self.snapshot(connection) == before, "legacy_migration_preservation_failed")
            check(connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one() == CHAIN[-1],
                  "migration_revision_wrong")
            self.schema(connection)
            connection.commit()
            command.upgrade(config, CHAIN[-1])
            check(self.snapshot(connection) == before, "migration_repeat_changed_legacy")
            check(not list(connection.exec_driver_sql("SELECT 1 FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid "
                "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND a.attacl IS NOT NULL")),
                  "unexpected_pregrant_column_acl")
            for statement in self.launcher.grants(self.p["database"], self.p["service"]):
                connection.exec_driver_sql(statement)
            connection.execute(text("ALTER ROLE " + self.launcher.identifier(self.p["service"]) + " PASSWORD "
                                    + sql.Literal(self.p["service_password"]).as_string()))
            connection.commit()
            self.legacy_baseline = self.snapshot(connection)
        check(time.monotonic() < migration_deadline, "migration_stage_timeout")
        self.bootstrap.dispose()
        self.observer = psycopg.connect(**self.connect_parameters("admin"), autocommit=True)
        check(str(self.one("SELECT system_identifier FROM pg_control_system()")) == self.p["system_identifier"],
              "tcp_cluster_identity_mismatch")
        check(int(self.one("SHOW server_version_num")) // 10000 == 16, "postgres_16_required")
        check(self.one("SELECT current_database()") == self.p["database"] and self.one("SELECT current_user") == self.p["admin"],
              "bootstrap_identity_mismatch")
        check(self.one("SELECT count(*) FROM pg_hba_file_rules WHERE error IS NOT NULL") == 0, "hba_reload_invalid")
        self.engine = engine("service")

        class AcceptanceSession(Session):
            pass
        self.Session = AcceptanceSession
        self.maker = sessionmaker(bind=self.engine, class_=AcceptanceSession, autoflush=False,
                                 autocommit=False, close_resets_only=False)

        def factory():
            session = self.maker()
            if self.session_patch:
                self.session_patch(session)
            return session
        self.factory = factory

        @event.listens_for(self.engine, "checkout")
        def checkout(driver, record, proxy):
            check(driver not in self.invalidated and not driver.closed, "invalidated_connection_reused")
            self.checkouts += 1
            self.pids[getattr(self.local, "label", "main")] = driver.info.backend_pid
            if driver not in self.drivers:
                self.drivers.append(driver)

        @event.listens_for(self.engine, "invalidate")
        def invalidate(driver, record, error):
            if driver is not None:
                self.invalidated.append(driver)

        @event.listens_for(self.engine, "after_cursor_execute")
        def after_sql(conn, cursor, statement, params, context, many):
            if self.hook:
                self.hook(getattr(self.local, "label", "main"), statement, conn.connection.driver_connection)

        @event.listens_for(AcceptanceSession, "after_flush")
        def after_flush(session, context):
            if self.flush_hook:
                self.flush_hook(session)

        @event.listens_for(AcceptanceSession, "after_commit")
        def after_commit(session):
            if self.commit_hook:
                self.commit_hook(session)

        self.private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.policy = account_auth.IssuerPolicy("https://ucr.invalid/", "ucr-api", "ucr-client", "https://ucr.invalid/keys")
        self.verifier = account_auth.SingleIssuerVerifier(self.policy, self.snapshot_key(1))
        self.service = research_ownership.OwnershipService(self.verifier, factory)

    def snapshot_key(self, revision):
        public = json.loads(self.jwt.algorithms.RSAAlgorithm.to_jwk(self.private.public_key()))
        public.update(kid="test", alg="RS256", use="sig", key_ops=["verify"])
        now = int(time.time())
        return self.auth.KeySnapshot(self.policy.jwks_uri, revision, now, now + 900, json.dumps({"keys": [public]}).encode())

    def token(self, subject, **changes):
        now = int(time.time())
        claims = dict(iss=self.policy.issuer, aud=self.policy.audience, sub=subject, client_id=self.policy.client_id,
                      jti=uuid4().hex, iat=now, exp=now + 900)
        claims.update(changes)
        return self.jwt.encode(claims, self.private, algorithm="RS256", headers={"typ": "at+jwt", "kid": "test"})

    def subject(self):
        self.index += 1
        return "synthetic_" + str(self.index)

    def account_session(self):
        subject = self.subject()
        token = self.token(subject)
        return subject, token, self.service.create_session(token, "parent")

    def rows(self, query, params=()):
        return self.observer.execute(query, params).fetchall()

    def one(self, query, params=()):
        return self.rows(query, params)[0][0]

    def snapshot(self, connection):
        result = {}
        for table in self.launcher.LEGACY[:-1]:
            check(connection.exec_driver_sql("SELECT count(*) FROM public." + table).scalar_one() == 0, "legacy_data_present")
            result[table] = list(connection.exec_driver_sql("SELECT a.attname, format_type(a.atttypid,a.atttypmod), a.attnotnull, "
                "pg_get_expr(d.adbin,d.adrelid) FROM pg_attribute a LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid "
                "AND d.adnum=a.attnum WHERE a.attrelid='public." + table + "'::regclass AND a.attnum>0 "
                "AND NOT a.attisdropped ORDER BY a.attnum"))
            result[table + "_constraints"] = list(connection.exec_driver_sql("SELECT conname, pg_get_constraintdef(oid) "
                "FROM pg_constraint WHERE conrelid='public." + table + "'::regclass ORDER BY conname"))
            result[table + "_indexes"] = list(connection.exec_driver_sql("SELECT indexname,indexdef FROM pg_indexes "
                "WHERE schemaname='public' AND tablename='" + table + "' ORDER BY indexname"))
        for (sequence,) in connection.exec_driver_sql("SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                                                      "WHERE n.nspname='public' AND c.relkind='S' ORDER BY c.relname"):
            check(re.fullmatch(r"[a-z_]+", sequence), "unexpected_sequence_name")
            result[sequence] = list(connection.exec_driver_sql("SELECT last_value,is_called FROM public." + sequence))
        return result

    def schema(self, connection):
        from sqlalchemy import inspect
        from app.models import ResearchAccount, ResearchSession, ResearchArtifact, ResearchNote
        inspector = inspect(connection)
        expected_names = set(self.launcher.OWNED + self.launcher.LEGACY)
        check(set(inspector.get_table_names(schema="public")) == expected_names, "migration_table_set_wrong")
        for model in (ResearchAccount, ResearchSession, ResearchArtifact, ResearchNote):
            table = model.__table__
            columns = inspector.get_columns(table.name, schema="public")
            check({c["name"] for c in columns} == set(table.columns.keys()), "migration_columns_wrong")
            for actual in columns:
                expected = table.columns[actual["name"]]
                check(actual["nullable"] == expected.nullable
                      and str(actual["type"]).split(" COLLATE")[0] == str(expected.type).split(" COLLATE")[0]
                      and getattr(actual["type"], "length", None) == getattr(expected.type, "length", None),
                      "migration_column_type_wrong")
                if expected.type.__class__.__name__ == "String" and expected.type.collation == "C":
                    value = connection.execute(self.text("SELECT co.collname FROM pg_attribute a JOIN pg_collation co ON co.oid=a.attcollation "
                        "WHERE a.attrelid=CAST(:name AS regclass) AND a.attname=:column"), {"name": "public." + table.name,
                                                                                     "column": actual["name"]}).scalar_one()
                    check(value == "C", "migration_collation_wrong")
            expected_pk = [column.name for column in table.primary_key.columns]
            check(inspector.get_pk_constraint(table.name)["constrained_columns"] == expected_pk, "migration_pk_wrong")
            expected_unique = {c.name: list(c.columns.keys()) for c in table.constraints if c.__class__.__name__ == "UniqueConstraint"}
            check({c["name"]: c["column_names"] for c in inspector.get_unique_constraints(table.name)} == expected_unique,
                  "migration_uniques_wrong")
            expected_checks = {c.name: str(c.sqltext) for c in table.constraints if c.__class__.__name__ == "CheckConstraint"}
            actual_checks = inspector.get_check_constraints(table.name)
            check({c["name"] for c in actual_checks} == set(expected_checks), "migration_checks_wrong")
            for actual in columns:
                expected = table.columns[actual["name"]].server_default
                if expected is None:
                    check(actual["default"] is None, "migration_unexpected_default")
                else:
                    # PostgreSQL adds type casts/quotes; compare scalar defaults.
                    scalar = str(expected.arg).strip("'")
                    check(str(actual["default"]).split("::")[0].strip("'") == scalar, "migration_default_wrong")
        fks = inspector.get_foreign_keys("research_artifacts")
        check(any(f["name"] == "fk_research_artifact_owned_session" and f["constrained_columns"] == ["owner_id", "session_id"]
                  and f["referred_table"] == "research_sessions" and f["referred_columns"] == ["owner_id", "id"] for f in fks),
              "migration_composite_fk_wrong")
        note_fks = inspector.get_foreign_keys("research_notes")
        check(any(f["name"] == "fk_research_note_owned_session" and f["constrained_columns"] == ["owner_id", "session_id"]
                  and f["referred_table"] == "research_sessions" and f["referred_columns"] == ["owner_id", "id"]
                  for f in note_fks), "note_composite_fk_wrong")
        check(any(f["constrained_columns"] == ["artifact_id"] and f["referred_table"] == "research_artifacts"
                  for f in note_fks), "note_artifact_fk_wrong")
        check(inspector.get_pk_constraint("research_notes")["constrained_columns"] == ["artifact_id"], "note_primary_key_wrong")

    def denied(self, call, code="OWNERSHIP_DENIED", state="not_issued", cleanup="closed"):
        try:
            call()
        except self.own.OwnershipFailure as error:
            check(error.code == code and error.commit_state == state and error.cleanup == cleanup, "wrong_service_failure")
            return error
        raise AcceptanceFailure("service_failure_missing")

    def auth_denied(self, call, code):
        before = self.checkouts
        try:
            call()
        except self.auth.AuthFailure as error:
            check(type(error) is self.auth.AuthFailure and error.code == code, "wrong_authentication_failure")
            check(self.checkouts == before, "authentication_reached_checkout")
            return error
        raise AcceptanceFailure("authentication_failure_missing")

    def sql_denied(self, statement, state="42501"):
        # Reuse the two-connection service pool: a third service connection would
        # test CONNECTION LIMIT rather than the intended object privilege.
        with self.engine.connect() as connection:
            try:
                check(connection.exec_driver_sql("SHOW transaction_read_only").scalar_one() == "off", "probe_transaction_not_writable")
                try:
                    connection.exec_driver_sql(statement)
                except Exception as error:
                    original = getattr(error, "orig", error)
                    check(isinstance(original, self.pg.Error) and original.sqlstate == state,
                          "wrong_sqlstate_" + str(getattr(original, "sqlstate", None)))
                    return
                raise AcceptanceFailure("authorization_or_constraint_probe_succeeded")
            finally:
                connection.rollback()

    def privileges(self):
        role = self.p["service"]
        row = self.rows("SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls,rolinherit,rolcanlogin,rolconnlimit "
                        "FROM pg_roles WHERE rolname=%s", (role,))[0]
        check(row == (False, False, False, False, False, False, True, 2), "role_attributes_wrong")
        check(self.one("SELECT count(*) FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname=%s)", (role,)) == 0,
              "role_membership_present")
        for privilege, expected in (("CONNECT", True), ("CREATE", False), ("TEMPORARY", False)):
            check(self.one("SELECT has_database_privilege(%s,%s,%s)", (role, self.p["database"], privilege)) is expected,
                  "effective_database_privilege_wrong")
        check(self.one("SELECT datdba <> (SELECT oid FROM pg_roles WHERE rolname=%s) FROM pg_database WHERE datname=%s",
                       (role, self.p["database"])) is True, "service_owns_database")
        check(self.one("SELECT count(*) FROM pg_database d, LATERAL aclexplode(d.datacl) a WHERE d.datname=%s AND a.grantee=0",
                       (self.p["database"],)) == 0, "public_database_acl_present")
        check(self.one("SELECT has_schema_privilege(%s,'public','USAGE')", (role,)) is True, "schema_usage_missing")
        check(self.one("SELECT count(*) FROM pg_namespace WHERE has_schema_privilege(%s,oid,'CREATE') OR "
                       "nspowner=(SELECT oid FROM pg_roles WHERE rolname=%s)", (role, role)) == 0, "service_schema_authority")
        check(self.one("SELECT count(*) FROM pg_namespace n,LATERAL aclexplode(n.nspacl) a WHERE n.nspname='public' AND a.grantee=0") == 0,
              "public_schema_acl_present")
        for table in self.launcher.OWNED + self.launcher.LEGACY:
            for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"):
                expected = table in self.launcher.OWNED and privilege in {"SELECT", "INSERT"}
                check(self.one("SELECT has_table_privilege(%s,%s,%s)", (role, "public." + table, privilege)) is expected,
                      "effective_table_privilege_wrong")
            columns = self.rows("SELECT attname FROM pg_attribute WHERE attrelid=%s::regclass AND attnum>0 AND NOT attisdropped",
                                ("public." + table,))
            for (column,) in columns:
                for privilege in ("SELECT", "INSERT", "UPDATE", "REFERENCES"):
                    expected = (table in self.launcher.OWNED and (privilege in {"SELECT", "INSERT"}
                        or privilege == "UPDATE" and column in self.launcher.UPDATES[table])
                        or privilege == "SELECT" and column in self.launcher.CATALOG_READS.get(table, ()))
                    check(self.one("SELECT has_column_privilege(%s,%s,%s,%s)", (role, "public." + table, column, privilege)) is expected,
                          "effective_column_privilege_wrong")
        check(self.one("SELECT count(*) FROM pg_class c WHERE c.relowner=(SELECT oid FROM pg_roles WHERE rolname=%s)", (role,)) == 0,
              "service_owns_relation")
        check(self.one("SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' "
                       "AND c.relkind='S' AND (has_sequence_privilege(%s,c.oid,'SELECT') OR has_sequence_privilege(%s,c.oid,'USAGE') "
                       "OR has_sequence_privilege(%s,c.oid,'UPDATE'))", (role, role, role)) == 0, "sequence_authority_present")
        check(self.one("SELECT count(*) FROM information_schema.role_table_grants WHERE grantee=%s AND is_grantable='YES'", (role,)) == 0
              and self.one("SELECT count(*) FROM information_schema.role_column_grants WHERE grantee=%s AND is_grantable='YES'", (role,)) == 0,
              "grant_option_present")
        for name, statement in self.launcher.privilege_probes(role, self.p["admin"], self.p["nonce"]):
            self.sql_denied(statement)
        for database in ("postgres", "template1"):
            params = self.connect_parameters("service")
            params["dbname"] = database
            try:
                connection = self.pg.connect(**params)
            except self.pg.Error as error:
                check(error.sqlstate == "28000", "other_database_failure_not_hba")
            else:
                connection.close()
                raise AcceptanceFailure("other_database_login_allowed")
        emit("detail", detail={"privilege_probes": len(self.launcher.privilege_probes(role, self.p["admin"], self.p["nonce"])),
                               "required_sqlstate": "42501", "other_database_sqlstate": "28000"})

    def overlap(self, first, second, *, first_insert=False):
        from concurrent.futures import ThreadPoolExecutor
        held, release = threading.Event(), threading.Event()
        started = time.monotonic()
        witnessed = False

        def hook(label, statement, driver):
            matches = "research_accounts" in statement and (statement.lstrip().startswith("INSERT") if first_insert else "FOR UPDATE" in statement)
            if label == "A" and matches and not held.is_set():
                held.set()
                check(release.wait(0.75), "overlap_release_deadline")

        def invoke(label, function):
            self.local.label = label
            try:
                return function()
            except self.own.OwnershipFailure as error:
                return error

        self.hook = hook
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                a = pool.submit(invoke, "A", first)
                check(held.wait(0.4), "first_worker_did_not_hold_lock")
                b = pool.submit(invoke, "B", second)
                try:
                    while time.monotonic() - started < 0.65:
                        if "A" in self.pids and "B" in self.pids:
                            rows = self.rows("SELECT b.pid,b.backend_xid::text,b.wait_event_type,b.wait_event,b.backend_start::text,"
                                "a.pid,a.backend_xid::text,a.backend_start::text,pg_blocking_pids(b.pid) FROM pg_stat_activity b "
                                "JOIN pg_stat_activity a ON a.pid=%s WHERE b.pid=%s AND b.datname=%s AND a.datname=%s",
                                (self.pids["A"], self.pids["B"], self.p["database"], self.p["database"]))
                            if rows and self.pids["A"] in rows[0][-1] and rows[0][2] == "Lock":
                                row = rows[0]
                                emit("witness", detail=dict(b_pid=row[0], b_xid=row[1], wait_type=row[2], wait=row[3],
                                     b_backend_start=row[4], a_pid=row[5], a_xid=row[6], a_backend_start=row[7], blockers=row[8]))
                                witnessed = True
                                break
                        time.sleep(0.005)
                finally:
                    release.set()
                results = a.result(timeout=5), b.result(timeout=5)
                check(witnessed, "postgres_overlap_witness_missing")
                return results
        finally:
            release.set()
            self.hook = None
            self.pids.pop("A", None)
            self.pids.pop("B", None)

    def success(self, result):
        check(type(result) is self.own.OwnedMetadata, "expected_success")
        return result

    def failure(self, result, code):
        check(isinstance(result, self.own.OwnershipFailure) and result.code == code and result.commit_state == "not_issued",
              "unexpected_race_failure")

    def auth_boundary(self):
        subject = self.subject()
        token = self.token(subject)
        before = self.checkouts
        unavailable = self.own.OwnershipService(session_factory=lambda: (_ for _ in ()).throw(AcceptanceFailure("factory_reached")))
        self.auth_denied(lambda: unavailable.create_session(token, "none"), "AUTH_UNAVAILABLE")
        parts = token.split(".")
        parts[-1] = ("A" if parts[-1][0] != "A" else "B") + parts[-1][1:]
        self.auth_denied(lambda: self.service.create_session(".".join(parts), "bad"), "AUTH_INVALID")
        check(self.checkouts == before, "authentication_reached_checkout")
        self.service.create_session(token, "valid")

    def first_creation(self, same):
        token = self.token(self.subject())
        a, b = self.overlap(lambda: self.service.create_session(token, "first"),
                            lambda: self.service.create_session(token, "first" if same else "second"), first_insert=True)
        a, b = self.success(a), self.success(b)
        check(a.owner_key == b.owner_key and (a.key == b.key) is same, "first_creation_identity_wrong")
        check(self.one("SELECT count(*) FROM research_accounts WHERE id=%s", (a.owner_key.id,)) == 1
              and self.one("SELECT count(*) FROM research_sessions WHERE owner_id=%s", (a.owner_key.id,)) == (1 if same else 2),
              "first_creation_persistence_wrong")

    def quota(self, artifacts):
        _, token, parent = self.account_session()
        if artifacts:
            for n in range(99):
                self.service.reserve_artifact(token, parent.key, 1, "seed_" + str(n))
            action = lambda key: self.service.reserve_artifact(token, parent.key, 1, key)
            table, expected = "research_artifacts", 100
        else:
            for n in range(18):
                self.service.create_session(token, "seed_" + str(n))
            action = lambda key: self.service.create_session(token, key)
            table, expected = "research_sessions", 20
        a, b = self.overlap(lambda: action("last_a"), lambda: action("last_b"))
        self.success(a)
        self.failure(b, "OWNERSHIP_QUOTA_EXCEEDED")
        check(self.one("SELECT count(*) FROM " + table + " WHERE owner_id=%s", (parent.owner_key.id,)) == expected, "quota_persistence_wrong")
        check(action("last_a") == a, "quota_boundary_replay_denied")
        if not artifacts:
            self.service.revoke_session(token, parent.key, 1)
            self.denied(lambda: action("after_revoke"), "OWNERSHIP_QUOTA_EXCEEDED")
        else:
            self.service.revoke_session(token, parent.key, 1)
            new_parent = self.service.create_session(token, "new_parent")
            self.denied(lambda: self.service.reserve_artifact(token, new_parent.key, 1, "after_revoke"),
                        "OWNERSHIP_QUOTA_EXCEEDED")

    def replay(self):
        _, token, parent = self.account_session()
        action = lambda: self.service.reserve_artifact(token, parent.key, 1, "same")
        a, b = self.overlap(action, action)
        a, b = self.success(a), self.success(b)
        check(a == b and self.one("SELECT count(*) FROM research_artifacts WHERE owner_id=%s", (parent.owner_key.id,)) == 1,
              "artifact_replay_duplicated")
        other = self.service.create_session(token, "other")
        self.denied(lambda: self.service.reserve_artifact(token, other.key, 1, "same"), "OWNERSHIP_IDEMPOTENCY_CONFLICT")
        _, other_token, other_parent = self.account_session()
        separate = self.service.reserve_artifact(other_token, other_parent.key, 1, "same")
        check(separate.owner_key != a.owner_key and separate.key != a.key, "owner_request_keys_collapsed")

    def foreign_constraints(self):
        _, alice, a = self.account_session()
        _, bob, b = self.account_session()
        artifact = self.service.reserve_artifact(alice, a.key, 1, "owned")
        self.denied(lambda: self.service.resolve_session(bob, a.key, 1))
        self.denied(lambda: self.service.revoke_session(bob, a.key, 1))
        self.denied(lambda: self.service.reserve_artifact(bob, a.key, 1, "foreign"))
        self.denied(lambda: self.service.resolve_artifact(bob, b.key, 1, artifact.key, 1))
        literal = lambda value: self.sql.Literal(value).as_string()
        self.sql_denied("INSERT INTO research_artifacts(id,owner_id,session_id,request_key,session_revision) VALUES ("
            + ",".join(literal(x) for x in (str(uuid4()), a.owner_key.id, b.key.id, "bad_fk", 1)) + ")", "23503")
        account = self.rows("SELECT issuer,subject FROM research_accounts WHERE id=%s", (a.owner_key.id,))[0]
        self.sql_denied("INSERT INTO research_accounts(id,issuer,subject) VALUES ("
            + ",".join(literal(x) for x in (str(uuid4()), *account)) + ")", "23505")
        self.sql_denied("INSERT INTO research_artifacts(id,owner_id,session_id,request_key,session_revision,state) VALUES ("
            + ",".join(literal(x) for x in (str(uuid4()), a.owner_key.id, a.key.id, "bad_state", 1, "invalid")) + ")", "23514")
        for assignment in ("revision=0", "token_cutoff=-2"):
            self.sql_denied("UPDATE research_accounts SET " + assignment + " WHERE id=" + literal(a.owner_key.id), "23514")
        self.sql_denied("UPDATE research_sessions SET state='invalid' WHERE id=" + literal(a.key.id), "23514")
        self.sql_denied("UPDATE research_sessions SET revision=0 WHERE id=" + literal(a.key.id), "23514")
        self.sql_denied("UPDATE research_artifacts SET revision=0 WHERE id=" + literal(artifact.key.id), "23514")
        self.sql_denied("INSERT INTO research_artifacts(id,owner_id,session_id,request_key,session_revision) VALUES ("
            + ",".join(literal(x) for x in (str(uuid4()), a.owner_key.id, a.key.id, "bad_parent_revision", 0)) + ")", "23514")
        self.sql_denied("INSERT INTO research_sessions(id,owner_id,request_key) VALUES ("
            + ",".join(literal(x) for x in (str(uuid4()), a.owner_key.id, "parent")) + ")", "23505")
        self.sql_denied("INSERT INTO research_artifacts(id,owner_id,session_id,request_key,session_revision) VALUES ("
            + ",".join(literal(x) for x in (str(uuid4()), a.owner_key.id, a.key.id, "owned", 1)) + ")", "23505")

    def exact_identity(self):
        subject = self.subject()
        a, b = self.service.create_session(self.token(subject), "Key"), self.service.create_session(self.token(subject.upper()), "Key")
        check(a.owner_key != b.owner_key, "case_distinct_subjects_merged")
        c = self.service.create_session(self.token(subject), "key")
        check(a.key != c.key, "case_distinct_requests_merged")

    def revisions(self):
        _, token, parent = self.account_session()
        artifact = self.service.reserve_artifact(token, parent.key, 1, "item")
        self.denied(lambda: self.service.resolve_session(token, parent.key, 2), "OWNERSHIP_REVISION_CHANGED")
        self.denied(lambda: self.service.resolve_artifact(token, parent.key, 1, artifact.key, 2), "OWNERSHIP_REVISION_CHANGED")
        self.denied(lambda: self.service.reserve_artifact(token, parent.key, 2, "item"), "OWNERSHIP_REVISION_CHANGED")
        revoked = self.service.revoke_session(token, parent.key, 1)
        check(revoked.revision == 2 and self.service.revoke_session(token, parent.key, 1) == revoked, "revocation_replay_wrong")
        self.denied(lambda: self.service.resolve_artifact(token, parent.key, 1, artifact.key, 1))

    def revocation_order(self, revoke_first, read=False):
        _, token, parent = self.account_session()
        reserve = (lambda: self.service.resolve_session(token, parent.key, 1)) if read else (
            lambda: self.service.reserve_artifact(token, parent.key, 1, "race"))
        revoke = lambda: self.service.revoke_session(token, parent.key, 1)
        a, b = self.overlap(revoke if revoke_first else reserve, reserve if revoke_first else revoke)
        self.success(a)
        if revoke_first:
            self.failure(b, "OWNERSHIP_DENIED")
        else:
            self.success(b)
        check(self.one("SELECT revision FROM research_sessions WHERE id=%s", (parent.key.id,)) == 2, "revocation_not_persisted")
        self.denied(reserve)

    def invalidation_order(self, invalidate_first):
        _, token, parent = self.account_session()
        reserve = lambda: self.service.reserve_artifact(token, parent.key, 1, "race")
        invalidate = lambda: self.service.invalidate_account_tokens(token)
        a, b = self.overlap(invalidate if invalidate_first else reserve, reserve if invalidate_first else invalidate)
        self.success(a)
        if invalidate_first:
            self.failure(b, "OWNERSHIP_DENIED")
        else:
            self.success(b)
        self.denied(reserve)

    def cutoff(self):
        subject, token, parent = self.account_session()
        account = self.service.invalidate_account_tokens(token)
        self.denied(lambda: self.service.create_session(token, "parent"))
        end = time.monotonic() + 33
        while self.one("SELECT extract(epoch FROM clock_timestamp())") < account.token_cutoff - 29:
            check(time.monotonic() < end, "cutoff_boundary_wait_timeout")
            time.sleep(0.05)
        for issued in (account.token_cutoff - 1, account.token_cutoff):
            self.denied(lambda issued=issued: self.service.create_session(self.token(subject, iat=issued, exp=issued + 900), "parent"))
        while int(self.one("SELECT extract(epoch FROM clock_timestamp())")) <= account.token_cutoff:
            check(time.monotonic() < end, "fresh_token_wait_timeout")
            time.sleep(0.05)
        fresh = self.token(subject)
        check(self.service.create_session(fresh, "parent").key == parent.key, "fresh_token_replay_wrong")
        next_account = self.service.invalidate_account_tokens(fresh)
        check(next_account.token_cutoff >= account.token_cutoff, "cutoff_regressed")

    @contextmanager
    def faults(self):
        original_commit, original_rollback = self.engine.dialect.do_commit, self.engine.dialect.do_rollback
        original_execute = self.engine.dialect.do_execute
        try:
            yield
        finally:
            self.hook = self.flush_hook = self.commit_hook = self.session_patch = None
            self.engine.dialect.do_commit, self.engine.dialect.do_rollback = original_commit, original_rollback
            self.engine.dialect.do_execute = original_execute

    def precommit(self):
        subject = self.subject()
        token = self.token(subject)
        cancellation = self.own.Cancellation()
        with self.faults():
            self.flush_hook = lambda session: cancellation.cancel()
            self.denied(lambda: self.service.create_session(token, "cancel", cancellation=cancellation), "OWNERSHIP_CANCELLED")
        check(self.one("SELECT count(*) FROM research_accounts WHERE subject=%s", (subject,)) == 0,
              "precommit_account_not_rolled_back")
        result = self.service.create_session(token, "cancel")
        check(self.one("SELECT count(*) FROM research_sessions WHERE owner_id=%s", (result.owner_key.id,)) == 1,
              "precommit_rollback_failed")

    def confirmed(self, rotate):
        subject, token, parent = self.account_session()
        cancellation = self.own.Cancellation()
        with self.faults():
            self.commit_hook = (lambda session: self.verifier.install_snapshot(self.snapshot_key(self.verifier._snapshot.revision + 1))) if rotate else (lambda session: cancellation.cancel())
            self.denied(lambda: self.service.reserve_artifact(token, parent.key, 1, "confirmed", cancellation=cancellation),
                        "AUTH_CONFIGURATION_CHANGED" if rotate else "OWNERSHIP_CANCELLED", state="confirmed")
        check(self.one("SELECT count(*) FROM research_artifacts WHERE owner_id=%s", (parent.owner_key.id,)) == 1, "confirmed_write_missing")
        reconciled = self.service.reserve_artifact(self.token(subject), parent.key, 1, "confirmed")
        check(reconciled.state == "reserved", "confirmed_reconciliation_failed")

    def indeterminate(self, after):
        _, token, parent = self.account_session()
        original = self.engine.dialect.do_commit
        with self.faults():
            def fault(driver):
                if after:
                    original(driver)
                raise self.pg.OperationalError("injected_commit_boundary")
            self.engine.dialect.do_commit = fault
            self.denied(lambda: self.service.reserve_artifact(token, parent.key, 1, "unknown"),
                        "OWNERSHIP_COMMIT_INDETERMINATE", state="indeterminate")
        count = self.one("SELECT count(*) FROM research_artifacts WHERE owner_id=%s", (parent.owner_key.id,))
        check(count == int(after), "injected_commit_ground_truth_wrong")
        first = self.service.reserve_artifact(token, parent.key, 1, "unknown")
        check(self.service.reserve_artifact(token, parent.key, 1, "unknown") == first
              and self.one("SELECT count(*) FROM research_artifacts WHERE owner_id=%s", (parent.owner_key.id,)) == 1,
              "indeterminate_reconciliation_duplicated")
        emit("detail", detail={"fault": "injected_after_real_commit" if after else "injected_before_real_commit", "durable_before_replay": count})

    def denied_reconciliation(self):
        for invalidate in (False, True):
            _, token, parent = self.account_session()
            original = self.engine.dialect.do_commit
            with self.faults():
                def fault(driver):
                    original(driver)
                    raise self.pg.OperationalError("injected_ack_loss")
                self.engine.dialect.do_commit = fault
                self.denied(lambda: self.service.reserve_artifact(token, parent.key, 1, "uncertain"),
                            "OWNERSHIP_COMMIT_INDETERMINATE", state="indeterminate")
            if invalidate:
                self.service.invalidate_account_tokens(token)
            else:
                self.service.revoke_session(token, parent.key, 1)
            self.denied(lambda: self.service.reserve_artifact(token, parent.key, 1, "uncertain"))

    def terminate(self, driver):
        check(isinstance(driver, self.pg.Connection), "termination_requires_psycopg_driver")
        pid = driver.info.backend_pid
        check(type(pid) is int and pid > 0, "termination_pid_invalid")
        row = self.rows("SELECT datname,usename,application_name,backend_start::text FROM pg_stat_activity WHERE pid=%s", (pid,))
        check(len(row) == 1 and row[0][:3] == (self.p["database"], self.p["service"], "ucr_" + self.p["nonce"] + "_service"),
              "backend_ownership_unverified")
        check(type(row[0][3]) is str and bool(row[0][3]), "backend_start_unverified")
        killed = self.rows("SELECT pg_terminate_backend(pid, 500) FROM pg_stat_activity WHERE pid=%s AND backend_start::text=%s "
                           "AND datname=%s AND usename=%s AND application_name=%s",
                           (pid, row[0][3], self.p["database"], self.p["service"], row[0][2]))
        check(killed == [(True,)], "backend_termination_unverified")
        absent = self.one("SELECT NOT EXISTS(SELECT 1 FROM pg_stat_activity WHERE pid=%s AND backend_start::text=%s)",
                          (pid, row[0][3]))
        check(absent is True, "terminated_backend_still_present")
        witness = dict(pid=pid, backend_start=row[0][3], database=row[0][0], role=row[0][1], application=row[0][2],
                       terminated=True, backend_absent=True)
        emit("detail", detail={"fault": "genuine_backend_termination", "pid": pid, "backend_start": row[0][3]})
        return witness

    def verify_termination(self, driver, pid, witness, failure):
        check(isinstance(driver, self.pg.Connection) and type(pid) is int and pid > 0,
              "terminated_driver_unverified")
        check(type(witness) is dict and set(witness) == {"pid", "backend_start", "database", "role", "application",
                                                       "terminated", "backend_absent"}, "termination_witness_missing")
        check(witness["pid"] == pid and witness["database"] == self.p["database"] and witness["role"] == self.p["service"]
              and witness["application"] == "ucr_" + self.p["nonce"] + "_service"
              and type(witness["backend_start"]) is str and bool(witness["backend_start"])
              and witness["terminated"] is True and witness["backend_absent"] is True, "termination_witness_invalid")
        check(isinstance(failure, self.pg.OperationalError), "termination_driver_failure_missing")
        state = failure.sqlstate
        check(state is None or state == "57P01" or state.startswith("08"), "termination_driver_failure_unrelated")
        check(driver in self.invalidated and driver.closed, "terminated_driver_cleanup_unverified")
        emit("detail", detail={"fault": "observed_termination_driver_failure", "pid": pid, "sqlstate": state})

    def backend_failure(self, at_commit):
        _, token, parent = self.account_session()
        original = self.engine.dialect.do_commit
        original_execute = self.engine.dialect.do_execute
        target = dict(driver=None, pid=None, witness=None, failure=None)

        def terminate_driver(driver):
            target["driver"], target["pid"] = driver, driver.info.backend_pid
            target["witness"] = self.terminate(driver)

        with self.faults():
            if at_commit:
                def fail(proxy):
                    terminate_driver(proxy.driver_connection)
                    try:
                        original(proxy)  # Preserve the real dialect/proxy call shape.
                    except self.pg.OperationalError as error:
                        target["failure"] = error
                        raise
                self.engine.dialect.do_commit = fail
            else:
                self.flush_hook = lambda session: terminate_driver(session.connection().connection.driver_connection)

                def execute(cursor, statement, parameters, context=None):
                    try:
                        return original_execute(cursor, statement, parameters, context)
                    except self.pg.OperationalError as error:
                        if cursor.connection is target["driver"]:
                            target["failure"] = error
                        raise
                self.engine.dialect.do_execute = execute
            self.denied(lambda: self.service.reserve_artifact(token, parent.key, 1, "terminated"),
                        "OWNERSHIP_COMMIT_INDETERMINATE" if at_commit else "OWNERSHIP_DATABASE_FAILURE",
                        state="indeterminate" if at_commit else "not_issued")
        self.verify_termination(target["driver"], target["pid"], target["witness"], target["failure"])
        check(self.one("SELECT count(*) FROM research_artifacts WHERE owner_id=%s", (parent.owner_key.id,)) == 0,
              "terminated_transaction_persisted")
        self.service.reserve_artifact(token, parent.key, 1, "terminated")

    def cleanup_failure(self, close):
        _, token, parent = self.account_session()
        with self.faults():
            if close:
                def patch(session):
                    def bad_close():
                        raise RuntimeError("injected_close_failure")
                    session.close = bad_close
                self.session_patch = patch
            else:
                def flush(session):
                    raise RuntimeError("injected_precommit_failure")
                def rollback(driver):
                    raise self.pg.OperationalError("injected_rollback_failure")
                self.flush_hook, self.engine.dialect.do_rollback = flush, rollback
            self.denied(lambda: self.service.reserve_artifact(token, parent.key, 1, "cleanup"),
                        "OWNERSHIP_CLEANUP_UNVERIFIED", state="confirmed" if close else "not_issued", cleanup="unverified")
        check(self.one("SELECT count(*) FROM research_artifacts WHERE owner_id=%s", (parent.owner_key.id,)) == int(close),
              "cleanup_fault_persistence_wrong")
        self.service.reserve_artifact(token, parent.key, 1, "cleanup")

    @contextmanager
    def catalog_fixture(self):
        """Only the fresh run-owned target; never read/restore real catalog data."""
        cik, accession = "0000000001", "0000000001-24-000001"
        for table in ("companies", "company_refresh_state", "filing_publications"):
            check(self.one("SELECT count(*) FROM " + table) == 0, "catalog_fixture_target_not_empty")
        with self.observer.transaction():
            self.observer.execute("INSERT INTO companies(id,ticker,name,cik,exchange) VALUES (1,'SYNTH','Synthetic fixture',%s,'TEST')", (cik,))
            self.observer.execute("INSERT INTO company_refresh_state(company_cik,data_version,facts_version,evidence_version,facts,evidence) "
                                  "VALUES (%s,7,0,7,'{}','{}')", (cik,))
            self.observer.execute("INSERT INTO filing_publications(company_cik,accession_number,form,filed,filename,chunk_count,"
                                  "content_digest,cleaned_text,configuration,published_at,data_version) "
                                  "VALUES (%s,%s,'10-K','2025-01-01','synthetic.htm',1,%s,NULL,'synthetic',now(),7)",
                                  (cik, accession, "a" * 64))
        try:
            yield
        finally:
            with self.observer.transaction():
                self.observer.execute("DELETE FROM filing_publications WHERE company_cik=%s AND accession_number=%s", (cik, accession))
                self.observer.execute("DELETE FROM company_refresh_state WHERE company_cik=%s", (cik,))
                self.observer.execute("DELETE FROM companies WHERE id=1 AND cik=%s AND ticker='SYNTH'", (cik,))

    def workspace_call(self, client, method, path, body=None):
        path, _, query = path.partition("?")
        headers = [(b"host", b"finlens.test"), (b"cookie", client["cookie"].encode()), (b"sec-fetch-site", b"same-origin")]
        if method == "POST":
            headers += [(b"origin", b"https://finlens.test"), (b"content-type", b"application/json"),
                        (b"x-finlens-csrf", client["csrf"].encode())]
        messages, received = [], False
        async def receive():
            nonlocal received
            check(not received, "workspace_repeated_receive")
            received = True
            return {"type": "http.request", "body": json.dumps(body or {}).encode(), "more_body": False}
        async def send(event):
            check(len(messages) < 2, "workspace_response_unbounded")
            messages.append(event)
        async def invoke():
            await client["app"]({"type": "http", "scheme": "https", "method": method,
                "path": "/private-research" + path, "root_path": "/private-research",
                "query_string": query.encode(), "headers": headers}, receive, send)
        self.loop.run_until_complete(invoke())
        check(len(messages) == 2 and messages[0]["type"] == "http.response.start"
              and messages[1]["type"] == "http.response.body" and len(messages[1]["body"]) <= 65536,
              "workspace_response_shape_wrong")
        response_headers = dict(messages[0]["headers"])
        check(response_headers.get(b"cache-control") == b"private, no-store", "workspace_cache_policy_wrong")
        return messages[0]["status"], json.loads(messages[1]["body"]), response_headers

    def workspace_client(self):
        token = self.token(self.subject())  # Real ephemeral signed API token, never a provider identity.
        app = self.workspace_type(self.service, origin="https://finlens.test")
        cookie = app.establish(token).split(";", 1)[0]
        client = dict(app=app, cookie=cookie, csrf="", token=token)
        status, state, _ = self.workspace_call(client, "GET", "/state")
        check(status == 200 and state["status"] == "authenticated", "workspace_establishment_failed")
        client.update(csrf=state["csrf"], owner=state["owner_key"],
                      root=app._sessions[cookie.split("=", 1)[1]].investigation)
        return client

    def note_counts(self, owner):
        return self.rows("SELECT (SELECT count(*) FROM research_artifacts WHERE owner_id=%s),"
                         "(SELECT count(*) FROM research_notes WHERE owner_id=%s)", (owner, owner))[0]

    def workspace_notes(self):
        with self.catalog_fixture():
            alice, bob = self.workspace_client(), self.workspace_client()
            status, catalog, _ = self.workspace_call(alice, "GET", "/sources?cik=0000000001")
            check(status == 200 and catalog["sources"] == [self.source_wire]
                  and catalog["source_verification"] == "unverified_reference"
                  and catalog["original_availability"] == "not_checked", "workspace_catalog_pin_wrong")
            payload = dict(request_key="workspace-note", body="Synthetic private investigation", source=catalog["sources"][0])
            status, note, _ = self.workspace_call(alice, "POST", "/notes", payload)
            check(status == 200 and note["owner_key"] == {"namespace": "principal", "id": alice["owner"]}
                  and note["body"] == payload["body"] and note["source"] == self.source_wire
                  and note["source_verification"] == "unverified_reference"
                  and note["original_availability"] == "not_checked", "workspace_saved_note_wrong")
            check(self.workspace_call(alice, "POST", "/notes", payload)[:2] == (200, note), "workspace_replay_changed_note")
            conflict = self.workspace_call(alice, "POST", "/notes", {**payload, "body": "Conflicting synthetic draft"})
            check(conflict[0] == 409 and "body" not in conflict[1], "workspace_conflict_disclosed_or_succeeded")
            for _ in range(2):
                status, listing, _ = self.workspace_call(alice, "GET", "/notes")
                check(status == 200 and listing["owner_key"] == alice["owner"] and len(listing["items"]) == 1
                      and listing["items"][0]["artifact_key"] == note["artifact_key"]["id"], "workspace_reload_wrong")
            query = urlencode(dict(session=note["session_key"]["id"], session_revision=note["session_revision"],
                artifact=note["artifact_key"]["id"], artifact_revision=note["artifact_revision"]))
            for route in ("/note?", "/export?"):
                status, reopened, headers = self.workspace_call(alice, "GET", route + query)
                check(status == 200 and reopened == note, "workspace_reopen_export_changed_note")
                if route == "/export?":
                    check(b"attachment" in headers.get(b"content-disposition", b""), "workspace_export_not_attachment")
                denied = self.workspace_call(bob, "GET", route + query)
                check(denied[0] == 404 and "body" not in denied[1] and "source" not in denied[1], "workspace_foreign_note_disclosed")
            status, listing, _ = self.workspace_call(bob, "GET", "/notes")
            check(status == 200 and listing["items"] == [], "workspace_foreign_inventory_disclosed")
            check(self.note_counts(alice["owner"]) == (1, 1) and self.note_counts(bob["owner"]) == (0, 0),
                  "workspace_note_pair_not_atomic")
            self.service.revoke_session(alice["token"], alice["root"].key, alice["root"].revision)
            self.service.invalidate_account_tokens(bob["token"])
            for client, route in ((alice, "/note?" + query), (bob, "/notes")):
                denied = self.workspace_call(client, "GET", route)
                check(denied[0] == 401 and "body" not in denied[1] and "source" not in denied[1], "workspace_revocation_disclosed")
            check(self.note_counts(alice["owner"]) == (1, 1), "workspace_revocation_erased_persisted_note")

    def note_atomicity(self):
        _, token, parent = self.account_session()
        owner, body = parent.owner_key.id, "Synthetic atomic note"
        for text, pin in (("", self.source), (body, None)):
            self.denied(lambda: self.service.save_new_note(token, parent.key, 1, "atomic", text, pin), "OWNERSHIP_NOTE_INVALID")
            check(self.note_counts(owner) == (0, 0), "invalid_note_consumed_quota")
        cancellation = self.own.Cancellation()
        with self.faults():
            self.flush_hook = lambda session: cancellation.cancel()
            self.denied(lambda: self.service.save_new_note(token, parent.key, 1, "atomic", body, self.source,
                        cancellation=cancellation), "OWNERSHIP_CANCELLED")
        check(self.note_counts(owner) == (0, 0), "cancelled_note_left_orphan")
        first = self.service.save_new_note(token, parent.key, 1, "atomic", body, self.source)
        check(self.note_counts(owner) == (1, 1), "atomic_note_pair_missing")
        results = self.overlap(lambda: self.service.save_new_note(token, parent.key, 1, "race", body, self.source),
                               lambda: self.service.save_new_note(token, parent.key, 1, "race", body, self.source))
        check(all(type(note) is self.own.SavedNote for note in results) and results[0] == results[1], "concurrent_note_replay_wrong")
        self.denied(lambda: self.service.save_new_note(token, parent.key, 1, "atomic", body + " changed", self.source),
                    "OWNERSHIP_IDEMPOTENCY_CONFLICT")
        check(self.note_counts(owner) == (2, 2) and self.service.reopen_note(token, parent.key, 1, first.artifact_key, 1) == first,
              "note_conflict_changed_pair")
        literal = lambda value: self.sql.Literal(value).as_string()
        # Both inserts roll back together in sql_denied; these are not service reservations.
        for revision, text in (("0", "'synthetic'"), ("1", "repeat(chr(8364),6000)")):
            statement = ("WITH a AS (INSERT INTO research_artifacts(id,owner_id,session_id,request_key,session_revision) VALUES ("
                "'00000000-0000-0000-0000-000000000123'," + literal(owner) + "," + literal(parent.key.id)
                + ",'note-constraint-fixture',1) RETURNING id,owner_id,session_id,revision) "
                "INSERT INTO research_notes(artifact_id,owner_id,session_id,session_revision,artifact_revision,body,source_pin) "
                "SELECT id,owner_id,session_id," + revision + ",revision," + text + ",'{}' FROM a")
            self.sql_denied(statement, "23514")
        check(self.note_counts(owner) == (2, 2), "note_constraint_probe_left_rows")

    def note_indeterminate(self, after):
        _, token, parent = self.account_session()
        original = self.engine.dialect.do_commit
        with self.faults():
            def fault(driver):
                if after:
                    original(driver)
                raise self.pg.OperationalError("injected_note_commit_boundary")
            self.engine.dialect.do_commit = fault
            self.denied(lambda: self.service.save_new_note(token, parent.key, 1, "unknown-note", "Synthetic uncertain note", self.source),
                        "OWNERSHIP_COMMIT_INDETERMINATE", state="indeterminate")
        check(self.note_counts(parent.owner_key.id) == (int(after), int(after)), "uncertain_note_pair_ground_truth_wrong")
        first = self.service.save_new_note(token, parent.key, 1, "unknown-note", "Synthetic uncertain note", self.source)
        check(self.service.save_new_note(token, parent.key, 1, "unknown-note", "Synthetic uncertain note", self.source) == first
              and self.note_counts(parent.owner_key.id) == (1, 1), "uncertain_note_reconciliation_duplicated")
        self.service.revoke_session(token, parent.key, 1)
        self.denied(lambda: self.service.reopen_note(token, parent.key, 1, first.artifact_key, 1))
        check(self.note_counts(parent.owner_key.id) == (1, 1), "denied_note_reconciliation_changed_storage")
        emit("detail", detail={"note_commit_fault": "after_real_commit" if after else "before_real_commit",
                               "durable_before_replay": int(after), "automatic_retry": False})

    def case_cleanup(self):
        check(self.engine.pool.checkedout() == 0, "service_connection_leaked")
        check(all(driver.closed for driver in self.invalidated), "invalidated_driver_not_closed")
        check(self.one("SELECT count(*) FROM pg_stat_activity WHERE datname=%s AND usename=%s AND "
                       "(state LIKE 'idle in transaction%%' OR wait_event_type='Lock')", (self.p["database"], self.p["service"])) == 0,
              "transaction_or_blocker_leaked")
        counts = {table: self.one("SELECT count(*) FROM " + table) for table in self.launcher.OWNED}
        check(all(counts[t] <= bound for t, bound in zip(self.launcher.OWNED, (64, 256, 512, 512))), "aggregate_row_budget_exceeded")
        check(self.one("SELECT count(*) FROM research_notes n LEFT JOIN research_artifacts a ON a.id=n.artifact_id "
                       "WHERE a.id IS NULL OR n.owner_id<>a.owner_id OR n.session_id<>a.session_id") == 0,
              "note_owner_or_artifact_corrupted")
        for table in self.launcher.LEGACY[:-1]:
            check(self.one("SELECT count(*) FROM " + table) == 0, "legacy_table_written")
        emit("detail", detail={"retained_rows": counts, "checked_out": 0})

    def close(self):
        if self.engine is not None:
            self.engine.dispose()
        if self.bootstrap is not None:
            self.bootstrap.dispose()
        if self.observer is not None:
            try:
                end = time.monotonic() + 1
                while self.one("SELECT count(*) FROM pg_stat_activity WHERE datname=%s AND usename=%s",
                               (self.p["database"], self.p["service"])):
                    check(time.monotonic() < end, "final_service_connections_unverified")
                    time.sleep(0.01)
            finally:
                self.observer.close()

    def run(self):
        cases = [("privileges", self.privileges), ("authentication_boundary", self.auth_boundary),
                 ("first_distinct", lambda: self.first_creation(False)), ("first_replay", lambda: self.first_creation(True)),
                 ("session_last_slot", lambda: self.quota(False)), ("artifact_last_slot", lambda: self.quota(True)),
                 ("artifact_replay_conflict", self.replay), ("foreign_constraints", self.foreign_constraints),
                 ("exact_identity", self.exact_identity), ("revisions", self.revisions),
                 ("reservation_before_revocation", lambda: self.revocation_order(False)),
                 ("revocation_before_reservation", lambda: self.revocation_order(True)),
                 ("read_before_revocation", lambda: self.revocation_order(False, read=True)),
                 ("revocation_before_read", lambda: self.revocation_order(True, read=True)),
                 ("reservation_before_invalidation", lambda: self.invalidation_order(False)),
                 ("invalidation_before_reservation", lambda: self.invalidation_order(True)), ("token_cutoff", self.cutoff),
                 ("precommit_rollback", self.precommit), ("confirmed_cancellation", lambda: self.confirmed(False)),
                 ("confirmed_rotation", lambda: self.confirmed(True)),
                 ("injected_before_commit", lambda: self.indeterminate(False)),
                 ("injected_after_commit", lambda: self.indeterminate(True)), ("denied_reconciliation", self.denied_reconciliation),
                 ("backend_before_commit", lambda: self.backend_failure(False)), ("backend_at_dispatch", lambda: self.backend_failure(True)),
                 ("rollback_failure", lambda: self.cleanup_failure(False)), ("close_failure", lambda: self.cleanup_failure(True)),
                 ("workspace_notes", self.workspace_notes), ("note_atomicity", self.note_atomicity),
                 ("note_before_commit", lambda: self.note_indeterminate(False)),
                 ("note_after_commit", lambda: self.note_indeterminate(True))]
        passed = 0
        check(("migration_and_provisioning",) + tuple(name for name, _ in cases) == self.launcher.CASE_NAMES,
              "worker_matrix_changed")
        try:
            emit("case_start", case="migration_and_provisioning")
            self.setup()
            emit("case_pass", case="migration_and_provisioning")
            passed += 1
            for name, function in cases:
                emit("case_start", case=name)
                start = time.monotonic()
                function()
                self.case_cleanup()
                check(time.monotonic() - start < 90, "scenario_deadline")
                emit("case_pass", case=name)
                passed += 1
            with self.bootstrap.connect() as connection:
                check(self.snapshot(connection) == self.legacy_baseline, "final_legacy_preservation_failed")
        finally:
            self.close()
        # No complete event until all DB/transaction resources have closed.
        emit("complete", passed=passed, transport_lost_ack="NOT_TESTED")


def worker_entry():
    """Private launcher-to-child pipe; fixed target fields, never arbitrary DSNs."""
    loop, status = None, 1
    try:
        data = sys.stdin.buffer.read(16385)
        check(len(data) <= 16384, "worker_input_limit")
        payload = json.loads(data)
        validate_payload(payload)
        # Own stdlib wake-up machinery before the strict destination audit guard.
        # No listener remains; application/driver network access stays target-only.
        import asyncio
        from concurrent.futures import ThreadPoolExecutor
        loop = asyncio.new_event_loop()
        loop.set_default_executor(ThreadPoolExecutor(max_workers=2))
        runtime_guard(payload)
        backend = ROOT / "backend"
        # -I -S avoids site initialization/.pth execution; existing packages only.
        sys.path[:0] = [str(backend), str(backend / ".venv/Lib/site-packages")]
        acceptance = PostgreSQLAcceptance(payload)
        acceptance.loop = loop
        acceptance.run()
        status = 0
    except BaseException as error:
        emit("failure", code=str(error) if isinstance(error, AcceptanceFailure) else type(error).__name__)
    finally:
        if loop is not None:
            try:
                try:
                    loop.run_until_complete(loop.shutdown_default_executor(timeout=5))
                finally:
                    loop.close()
            except BaseException:
                emit("failure", code="workspace_loop_cleanup_failed")
                status = 1
    return status


def offline_checks():
    """Only this candidate's new checks; no existing unit/review groups imported."""
    import ast
    import copy
    import socket
    import subprocess
    import unittest
    from types import MethodType, SimpleNamespace
    from unittest.mock import patch

    attempts = {"process": 0, "network": 0, "import": 0, "env": 0, "write": 0}

    def forbidden_process(*args, **kwargs):
        attempts["process"] += 1
        raise AcceptanceFailure("offline_process_forbidden")

    def forbidden_network(*args, **kwargs):
        attempts["network"] += 1
        raise AcceptanceFailure("offline_network_forbidden")

    class ImportGuard(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in {"app", "psycopg", "sqlalchemy", "alembic", "jwt", "cryptography",
                                          "dotenv", "fastapi", "uvicorn", "openai", "torch", "sentence_transformers", "sqlite3"}:
                attempts["import"] += 1
                raise AcceptanceFailure("offline_operational_import_forbidden")
    sys.meta_path.insert(0, ImportGuard())

    def audit(event, args):
        if event.startswith("subprocess.") or event in {"os.system", "sqlite3.connect"}:
            forbidden_process()
        if event.startswith("socket."):
            forbidden_network()
        if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
            name = os.fsdecode(os.fspath(args[0])).replace("\\", "/").rsplit("/", 1)[-1]
            if name == ".env" or name.startswith(".env."):
                attempts["env"] += 1
                raise AcceptanceFailure("offline_env_forbidden")
            mode, flags = args[1], args[2]
            if mode is not None and any(c in mode for c in "wax+") or flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC):
                attempts["write"] += 1
                raise AcceptanceFailure("offline_filesystem_write_forbidden")

    sys.addaudithook(audit)
    subprocess.Popen = forbidden_process
    os.system = forbidden_process
    socket.create_connection = socket.getaddrinfo = forbidden_network
    socket.socket.connect = socket.socket.connect_ex = forbidden_network
    module = launcher_module()
    # Offline adapter checks must never create even unused credential material.
    module.secrets.token_urlsafe = forbidden_process
    import_guard_counts = dict(attempts)
    valid = ["--execute", "--docker-context", "desktop-linux", "--expected-context-endpoint", "npipe:////./pipe/dockerDesktopLinuxEngine",
             "--image", "pgvector/pgvector@sha256:" + "a" * 64, "--expected-head", module.BACKEND_BASELINE,
             "--candidate-sha256", "b" * 64]

    def config(**changes):
        value = module.parse(valid)
        for key, item in changes.items():
            setattr(value, key, item)
        return value

    def record(run, kind):
        if kind == "network":
            return dict(id="a" * 64, name=run.network_name, labels={"finlens.ucr.run": run.nonce}, containers={}, driver="bridge")
        host = dict(ReadonlyRootfs=True, LogConfig={"Type": "none"}, Memory=768 * module.MIB, MemorySwap=768 * module.MIB,
                    NanoCpus=2_000_000_000, PidsLimit=128, ShmSize=64 * module.MIB, Privileged=False,
                    IpcMode="private", CgroupnsMode="private", Binds=None,
                    Tmpfs={p: "rw,nosuid,nodev,size=" + str(n) for p, n in module.MOUNTS.items() if p not in {"/dev", "/dev/shm"}},
                    PortBindings={"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": ""}]})
        return dict(id="b" * 64, name="/" + run.container_name, labels={"finlens.ucr.run": run.nonce},
                    image=run.image_id, host=host, mounts=[], networks={run.network_name: {"NetworkID": "a" * 64}},
                    ports={"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": "55499"}]}, running=False)

    class FakeDocker:
        def __init__(self):
            self.resources, self.calls = {}, []
            self.creation, self.fail_remove, self.fail_stop = "success", False, False
            self.run_object = None

        def run(self, argv, **kwargs):
            check(argv[:3] == ["docker", "--context", "desktop-linux"], "unexpected_fake_command")
            self.calls.append((argv[3:], kwargs))
            args, run = argv[3:], self.run_object
            kind, operation = args[:2]
            check(kind in {"container", "network"}, "unplanned_fake_operation")
            if operation == "ls":
                value = self.resources.get(kind)
                return module.Output((value["id"] + "\n").encode() if value else b"", b"", 0)
            if operation == "create":
                if self.creation != "timeout_before":
                    self.resources[kind] = record(run, kind)
                if self.creation.startswith("timeout"):
                    raise module.CommandFailure("command_timeout", uncertain=True)
                return module.Output((self.resources[kind]["id"] + "\n").encode(), b"", 0)
            if operation == "inspect":
                if kind not in self.resources or args[-1] != self.resources[kind]["id"]:
                    return module.Output(b"", b"fake_missing_id", 1)
                return module.Output(json.dumps(self.resources[kind]).encode(), b"", 0)
            if operation == "stop":
                if self.fail_stop:
                    raise module.CommandFailure("command_timeout", uncertain=True)
                check(args[-1] == self.resources[kind]["id"], "fake_stop_wrong_target")
                self.resources[kind]["running"] = False
                return module.Output(b"", b"", 0)
            if operation == "rm":
                check(args[-1] == self.resources[kind]["id"], "fake_remove_wrong_target")
                if self.fail_remove:
                    raise module.CommandFailure("command_timeout", uncertain=True)
                del self.resources[kind]
                return module.Output(b"", b"", 0)
            raise AcceptanceFailure("unplanned_fake_operation")

    def new_run():
        adapter = FakeDocker()
        run = module.Run(config(), ROOT, adapter, nonce="c" * 32, clock=lambda: 0)
        run.image_id = "sha256:" + "d" * 64
        adapter.run_object = run
        return run, adapter

    def created_pair():
        run, adapter = new_run()
        run.create("network", ["network", "create", run.network_name])
        run.create("container", module.container_command(run, config().image, run.ids["network"]))
        return run, adapter

    def mountinfo():
        lines = [f"1 0 0:0 / {p} ro - overlay overlay ro" for p in ("/", "/etc/hosts", "/etc/hostname", "/etc/resolv.conf")]
        lines += [f"1 0 0:0 / {p} rw - tmpfs tmpfs rw,size={size}" for p, size in module.MOUNTS.items()]
        return ("\n".join(lines) + "\n").encode()

    class FakeChild:
        def __init__(self, out=b"ok", err=b"", *, hang=False, unkillable=False, bad_input=False):
            self.stdout, self.stderr = io.BytesIO(out), io.BytesIO(err)
            class Input(io.BytesIO):
                def write(inner, data):
                    if bad_input:
                        raise OSError("fake_input_failure")
                    return super().write(data)
            self.stdin = Input()
            self.hang, self.unkillable, self.killed = hang, unkillable, False
            self.returncode = None if hang else 0

        def poll(self):
            return self.returncode

        def kill(self):
            self.killed = True
            if not self.unkillable:
                self.returncode = -9

        def wait(self, timeout):
            if self.returncode is None:
                raise subprocess.TimeoutExpired("fake", timeout)
            return self.returncode

    class Tick:
        def __init__(self):
            self.value = 0
        def __call__(self):
            self.value += 0.02
            return self.value

    def exception_contract(relative, name):
        # Compile the exact committed exception class only. No application/JWT/
        # database imports, signature tests or completed test modules are loaded.
        tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
        node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name)
        scope = {"__name__": "ucr_offline_exception_contract"}
        exec(compile(ast.Module(body=[node], type_ignores=[]), relative, "exec"), scope)
        return scope[name]

    def auth_fixture():
        auth_error = exception_contract("backend/app/account_auth.py", "AuthFailure")
        ownership_error = exception_contract("backend/app/research_ownership.py", "OwnershipFailure")
        harness = PostgreSQLAcceptance.__new__(PostgreSQLAcceptance)
        harness.auth = SimpleNamespace(AuthFailure=auth_error)
        token = "synthetic.header.signature"
        harness.checkouts, harness.subject, harness.token = 0, lambda: "synthetic", lambda subject: token

        class Dormant:
            def __init__(self, session_factory):
                self.factory = session_factory
            def create_session(self, token, request):
                raise auth_error("AUTH_UNAVAILABLE")

        class Active:
            def create_session(self, supplied, request):
                if supplied != token:
                    raise auth_error("AUTH_INVALID")
                harness.checkouts += 1
        harness.own = SimpleNamespace(OwnershipFailure=ownership_error, OwnershipService=Dormant)
        harness.service = Active()
        return harness

    def backend_fixture(**options):
        """Synthetic dialect/proxy/driver shapes, not a fake PG acceptance result."""
        class DriverError(Exception):
            def __init__(self, state="57P01"):
                self.sqlstate = state

        class Driver:
            def __init__(self):
                self.info, self.closed = SimpleNamespace(backend_pid=6401), False

        driver = Driver()
        proxy = SimpleNamespace(info={}, driver_connection=driver)
        harness = PostgreSQLAcceptance.__new__(PostgreSQLAcceptance)
        harness.p = dict(database="ucr_db_" + "c" * 32, service="ucr_svc_" + "c" * 32, nonce="c" * 32)
        harness.pg = SimpleNamespace(Connection=Driver, OperationalError=DriverError)
        harness.own = SimpleNamespace(OwnershipFailure=exception_contract("backend/app/research_ownership.py", "OwnershipFailure"))
        harness.hook = harness.flush_hook = harness.commit_hook = harness.session_patch = None
        harness.invalidated, events = [], []
        application = "ucr_" + harness.p["nonce"] + "_service"
        metadata = (harness.p["database"], harness.p["service"], application, "2026-10-30 00:00:00+00")

        def rows(query, params):
            if "pg_terminate_backend" in query:
                check("pg_terminate_backend(pid, 500)" in query and params == (6401, metadata[3], *metadata[:3]),
                      "synthetic_termination_selector_wrong")
                events.append("termination_query")
                return options.get("termination_result", [(True,)])
            check("backend_start::text FROM pg_stat_activity" in query and params == (6401,), "unplanned_synthetic_query")
            events.append("target_lookup")
            return options.get("metadata", [metadata])

        def one(query, params):
            if query.startswith("SELECT NOT EXISTS"):
                check(params == (6401, metadata[3]), "synthetic_absence_selector_wrong")
                events.append("backend_absence")
                return options.get("absent", True)
            check(query.startswith("SELECT count(*) FROM research_artifacts"), "unplanned_synthetic_count")
            return options.get("durable_rows", 0)

        harness.rows, harness.one = rows, one
        parent = SimpleNamespace(key="synthetic_session", owner_key=SimpleNamespace(id="synthetic_owner"))
        harness.account_session = lambda: ("subject", "synthetic_token", parent)

        def driver_failure(kind):
            events.append(kind)
            error = options.get("driver_failure", DriverError())
            if error is not None:
                raise error

        def commit(supplied):
            check(supplied is proxy, "dialect_proxy_shape_changed")
            driver_failure("driver_commit")

        def execute(cursor, statement, parameters, context=None):
            check(cursor.connection is driver, "cursor_driver_shape_changed")
            driver_failure("driver_execute")

        harness.engine = SimpleNamespace(dialect=SimpleNamespace(do_commit=commit, do_execute=execute, do_rollback=lambda d: None))

        class Service:
            def reserve_artifact(self, *args):
                if harness.flush_hook is None and harness.engine.dialect.do_commit is commit:
                    events.append("reconciled")
                    return
                at_dispatch = harness.engine.dialect.do_commit is not commit
                try:
                    if harness.flush_hook:
                        harness.flush_hook(SimpleNamespace(connection=lambda: SimpleNamespace(connection=proxy)))
                        harness.engine.dialect.do_execute(SimpleNamespace(connection=driver), "synthetic_query", ())
                    harness.engine.dialect.do_commit(proxy)
                except BaseException as error:
                    events.append(("service_wrapped", type(error).__name__))
                    driver.closed = True
                    harness.invalidated.append(driver)
                    raise harness.own.OwnershipFailure("OWNERSHIP_COMMIT_INDETERMINATE" if at_dispatch else "OWNERSHIP_DATABASE_FAILURE",
                                                      commit_state="indeterminate" if at_dispatch else "not_issued") from None
        harness.service = Service()
        return harness, driver, proxy, events

    def workspace_fixture():
        """Scripted observations, not a replacement ownership/store implementation."""
        h = PostgreSQLAcceptance.__new__(PostgreSQLAcceptance)
        h.source_wire = {"synthetic_pin": 7}
        note = dict(owner_key={"namespace": "principal", "id": "alice"}, session_key={"id": "session"},
            artifact_key={"id": "artifact"}, session_revision=1, artifact_revision=1,
            body="Synthetic private investigation", source=h.source_wire,
            source_verification="unverified_reference", original_availability="not_checked")
        clients = [dict(owner=owner, token=owner, root=SimpleNamespace(key=owner, revision=1)) for owner in ("alice", "bob")]
        h.workspace_client = lambda: clients.pop(0)
        events = []
        @contextmanager
        def catalog():
            events.append("catalog_enter")
            try: yield
            finally: events.append("catalog_exit")
        h.catalog_fixture = catalog
        query = urlencode(dict(session="session", session_revision=1, artifact="artifact", artifact_revision=1))
        listing = dict(owner_key="alice", items=[dict(artifact_key="artifact")])
        script = [("alice", "GET", "/sources?cik=0000000001", 200, dict(sources=[h.source_wire],
                source_verification="unverified_reference", original_availability="not_checked")),
            ("alice", "POST", "/notes", 200, note), ("alice", "POST", "/notes", 200, note),
            ("alice", "POST", "/notes", 409, {}), ("alice", "GET", "/notes", 200, listing),
            ("alice", "GET", "/notes", 200, listing), ("alice", "GET", "/note?" + query, 200, note),
            ("bob", "GET", "/note?" + query, 404, {}), ("alice", "GET", "/export?" + query, 200, note),
            ("bob", "GET", "/export?" + query, 404, {}), ("bob", "GET", "/notes", 200, {"items": []}),
            ("alice", "GET", "/note?" + query, 401, {}), ("bob", "GET", "/notes", 401, {})]
        responses = [(*item[:4], copy.deepcopy(item[4])) for item in script]
        def call(client, method, path, body=None):
            owner, expected_method, expected_path, status, data = responses.pop(0)
            check((client["owner"], method, path) == (owner, expected_method, expected_path), "scripted_workspace_schedule_wrong")
            if method == "POST":
                check(body["source"] == h.source_wire and body["request_key"] == "workspace-note", "scripted_submission_wrong")
            return status, data, {b"content-disposition": b"attachment"}
        h.workspace_call = call
        counts = [("alice", (1, 1)), ("bob", (0, 0)), ("alice", (1, 1))]
        def count(owner):
            expected, value = counts.pop(0)
            check(owner == expected, "scripted_note_owner_wrong")
            return value
        h.note_counts = count
        h.service = SimpleNamespace(revoke_session=lambda token, key, revision: events.append(("revoke", token, key, revision)),
            invalidate_account_tokens=lambda token: events.append(("invalidate", token)))
        return h, responses, counts, events

    def note_fixture():
        h = PostgreSQLAcceptance.__new__(PostgreSQLAcceptance)
        failure = exception_contract("backend/app/research_ownership.py", "OwnershipFailure")
        h.own = SimpleNamespace(OwnershipFailure=failure, SavedNote=SimpleNamespace)
        saves, counts, events = [], [], []
        class Cancel:
            def cancel(self): events.append("cancel")
        h.own.Cancellation = Cancel
        h.source = object()
        h.hook = h.flush_hook = h.commit_hook = h.session_patch = None
        parent = SimpleNamespace(owner_key=SimpleNamespace(id="owner"), key=SimpleNamespace(id="session"))
        h.account_session = lambda: ("subject", "synthetic_token", parent)
        note = SimpleNamespace(artifact_key="artifact")
        revoked = [False]
        def reopen(*args):
            if revoked[0]: raise failure("OWNERSHIP_DENIED")
            return note
        def save(*args, **kwargs):
            events.append((args, kwargs))
            if kwargs.get("cancellation") is not None and h.flush_hook:
                h.flush_hook(None)
            result = saves.pop(0)
            if result == "commit":
                try: h.engine.dialect.do_commit(object())
                except h.pg.OperationalError:
                    raise failure("OWNERSHIP_COMMIT_INDETERMINATE", commit_state="indeterminate") from None
                raise AcceptanceFailure("scripted_commit_did_not_fail")
            if isinstance(result, BaseException): raise result
            return result
        h.service = SimpleNamespace(save_new_note=save, reopen_note=reopen,
                                    revoke_session=lambda *a: revoked.__setitem__(0, True))
        h.note_counts = lambda owner: counts.pop(0)
        def overlap(first, second):
            events.append("overlap")
            return first(), second()
        h.overlap = overlap
        h.engine = SimpleNamespace(dialect=SimpleNamespace(do_commit=lambda driver: events.append("real_commit"),
                                    do_rollback=None, do_execute=None))
        h.pg = SimpleNamespace(OperationalError=type("SyntheticDriverError", (Exception,), {}))
        h.sql = SimpleNamespace(Literal=lambda value: SimpleNamespace(as_string=lambda: "'" + value + "'"))
        h.sql_denied = lambda statement, state: events.append(("constraint_probe", statement, state))
        return h, note, saves, counts, events

    class OfflineChecks(unittest.TestCase):
        def test_01_positive_guards(self):
            for name in ("app.database", "psycopg", "sqlalchemy", "alembic", "dotenv", "jwt", "sqlite3"):
                with self.subTest(import_name=name), self.assertRaises(AcceptanceFailure):
                    __import__(name)
            with self.assertRaises(AcceptanceFailure): module.secrets.token_urlsafe(32)
            for effect in (lambda: sys.audit("subprocess.Popen", "docker", [], None, None),
                           lambda: sys.audit("socket.connect", None, ("127.0.0.1", 5432)),
                           lambda: sys.audit("sqlite3.connect", "ignored"),
                           lambda: sys.audit("open", str(ROOT / "backend/.env"), "r", 0),
                           lambda: sys.audit("open", "offline_write_probe", "w", os.O_WRONLY)):
                with self.subTest(effect=effect.__code__.co_firstlineno), self.assertRaises(AcceptanceFailure):
                    effect()
            self.assertTrue(all(attempts[key] > 0 for key in attempts))

        def test_02_import_is_inert(self):
            before = dict(attempts)
            self.assertIs(launcher_module(), module)
            self.assertNotIn("app", sys.modules)
            self.assertNotIn("psycopg", sys.modules)
            self.assertEqual(before, attempts)
            self.assertTrue(all(count == 0 for count in import_guard_counts.values()))
            spec = importlib.util.spec_from_file_location("ucr_fresh_inert_acceptance", Path(__file__))
            fresh = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(fresh)
            self.assertEqual(before, attempts)

        def test_03_default_refuses_before_effects(self):
            before = dict(attempts)
            with patch("sys.stdout", new=io.StringIO()):
                self.assertEqual(module.main([]), 2)
                self.assertEqual(main([]), 2)
            self.assertEqual(before, attempts)

        def test_04_help_is_inert(self):
            before = dict(attempts)
            for entry in (module.main, main):
                with self.subTest(entry=entry.__module__), patch("sys.stdout", new=io.StringIO()), self.assertRaises(SystemExit) as raised:
                    entry(["--help"])
                self.assertEqual(raised.exception.code, 0)
            self.assertEqual(before, attempts)

        def test_05_partial_and_unreviewed_cli_refuses(self):
            for args in (["--execute"], valid[:-2], valid[:-1] + ["bad"], [x if x != module.BACKEND_BASELINE else "G" * 40 for x in valid]):
                with self.subTest(args_count=len(args)), self.assertRaises(module.Refusal):
                    module.parse(args)

        def test_06_no_existing_target_options(self):
            for flag in ("--dsn", "--database-url", "--container", "--volume", "--cleanup-target"):
                with self.subTest(flag=flag), patch("sys.stderr", new=io.StringIO()), self.assertRaises(SystemExit):
                    module.parse(valid + [flag, "untrusted"])

        def test_07_context_and_image_bounds(self):
            for field, bad in (("--docker-context", "--other"), ("--expected-context-endpoint", "tcp://127.0.0.1:2375"),
                               ("--expected-context-endpoint", "unix:///tmp/../docker.sock"), ("--image", "pgvector/pgvector:pg16"),
                               ("--image", "other/image@sha256:" + "a" * 64)):
                args = valid.copy()
                args[args.index(field) + 1] = bad
                with self.subTest(field=field, bad=bad), patch("sys.stderr", new=io.StringIO()), self.assertRaises((module.Refusal, SystemExit)):
                    module.parse(args)
            self.assertFalse(module.parse(valid).allow_pull)

        def test_08_digest_refusal_before_any_process(self):
            before = dict(attempts)
            with patch("sys.stdout", new=io.StringIO()):
                self.assertEqual(module.main(valid), 2)
            self.assertEqual(before, attempts)

        def test_09_length_framed_candidate_digest(self):
            accesses = []
            content = {p: p.encode() for p in module.FILES}
            class File:
                def __init__(self, name): self.name = name
                def read_bytes(self):
                    accesses.append(self.name)
                    return content[self.name]
            class Root:
                def __truediv__(self, name): return File(name)
            before = module.candidate_digest(Root())
            self.assertEqual(accesses, list(module.FILES))
            for name in module.FILES:
                content[name] += b"changed"
                self.assertNotEqual(before, module.candidate_digest(Root()))

        def test_10_environment_has_no_operational_selectors(self):
            with patch.dict(os.environ, DATABASE_URL="forbidden", PGSERVICE="forbidden", DOCKER_HOST="forbidden", PYTHONPATH="forbidden"):
                env = module.clean_environment()
            self.assertTrue(set(env) <= {"SystemRoot", "WINDIR", "PATH", "TEMP", "TMP", "LOCALAPPDATA", "USERPROFILE"})

        def test_11_container_command_complete_bounds(self):
            run, _ = new_run()
            argv = module.container_command(run, config().image, "a" * 64)
            for item in ("--read-only", "--log-driver=none", "--memory=768m", "--memory-swap=768m", "--cpus=2", "--pids-limit=128",
                         "--shm-size=64m", "--pull=never", "127.0.0.1::5432", "/var/lib/postgresql/data:rw,nosuid,nodev,size=268435456"):
                self.assertIn(item, argv)
            self.assertNotIn("--volume", argv)
            self.assertNotIn("--privileged", argv)
            self.assertNotIn("--env-file", argv)
            self.assertIn("POSTGRES_PASSWORD", argv)
            self.assertFalse(any(x.startswith("POSTGRES_PASSWORD=") for x in argv))

        def test_12_privilege_grants_exact(self):
            statements = module.grants("ucr_db_test", "ucr_svc_test")
            text = "\n".join(statements)
            self.assertIn('REVOKE ALL ON DATABASE "ucr_db_test" FROM PUBLIC, "ucr_svc_test"', text)
            self.assertIn('REVOKE ALL ON SCHEMA public FROM PUBLIC, "ucr_svc_test"', text)
            self.assertIn("NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT CONNECTION LIMIT 2", text)
            actual = [s for s in statements if s.startswith("GRANT UPDATE")]
            self.assertEqual(actual, [f'GRANT UPDATE ({", ".join(module.UPDATES[t])}) ON TABLE public.{t} TO "ucr_svc_test"' for t in module.OWNED])
            for grant in (s for s in statements if s.startswith("GRANT")):
                self.assertNotIn("PUBLIC", grant)
                self.assertNotIn("SEQUENCE", grant)
                self.assertNotIn("DELETE", grant)
                self.assertNotIn("TRUNCATE", grant)
                self.assertNotIn("CREATE", grant)
                self.assertNotIn("TEMP", grant)

        def test_13_identifiers_reject_injection(self):
            for value in ("public;drop", "role\"name", "", "x" * 64, "../role"):
                with self.subTest(value=value), self.assertRaises(module.Refusal):
                    module.identifier(value)

        def test_14_privilege_probes_are_authorization_specific(self):
            probes = dict(module.privilege_probes("ucr_svc_test", "ucr_admin_test", "a" * 32))
            self.assertEqual(probes["truncate"], "TRUNCATE public.research_artifacts")
            self.assertIn("CREATE TEMP TABLE", probes["temp"])
            self.assertIn("CREATE ROLE", probes["role"])
            self.assertFalse(any("CREATE DATABASE" in s for s in probes.values()))
            for name, sql in probes.items():
                if name.startswith(("insert_", "update_", "delete_")):
                    self.assertIn("WHERE false", sql)
            self.assertEqual(len({name for name in probes}), len(probes))

        def test_15_hba_is_target_specific(self):
            value = module.hba("ucr_db_test", "ucr_admin_test", "ucr_svc_test").decode().splitlines()
            self.assertEqual(value[-2:], ["local all all reject", "host all all all reject"])
            self.assertIn("host ucr_db_test ucr_svc_test all scram-sha-256", value)
            self.assertFalse(any(line == "host all all all trust" for line in value))

        def test_16_valid_mount_layout(self):
            module.validate_mountinfo(mountinfo())

        def test_17_mount_failures_close(self):
            raw = mountinfo()
            variants = (raw.replace(b"/ / ro", b"/ / rw"), raw.replace(b"size=268435456", b"size=536870912"),
                        raw.replace(b"size=16777216", b"nosize", 1), raw + b"1 0 0:0 / /other rw - ext4 disk rw\n",
                        b"\n".join(x for x in raw.splitlines() if b"/dev/shm" not in x),
                        raw.replace(b"/etc/hosts ro", b"/etc/hosts rw"))
            for value in variants:
                with self.subTest(digest=hashlib.sha256(value).hexdigest()[:8]), self.assertRaises(module.Refusal):
                    module.validate_mountinfo(value)

        def test_18_create_and_cleanup_only_owned_ids(self):
            run, fake = created_pair()
            self.assertTrue(run.cleanup())
            removals = [args for args, _ in fake.calls if args[1] == "rm"]
            self.assertEqual(removals, [["container", "rm", "b" * 64], ["network", "rm", "a" * 64]])
            self.assertFalse(fake.resources)

        def test_19_timeout_after_creation_reconciles(self):
            run, fake = new_run()
            fake.creation = "timeout_after"
            with self.assertRaises(module.CommandFailure):
                run.create("network", ["network", "create", run.network_name])
            self.assertIn("network", run.pending)
            self.assertTrue(run.cleanup())
            self.assertTrue(any(r.get("event") == "creation_reconciled" for r in run.receipts))
            self.assertEqual(sum(args[1] == "create" for args, _ in fake.calls), 1)

        def test_20_timeout_then_empty_lookup_is_unverified(self):
            run, fake = new_run()
            fake.creation = "timeout_before"
            with self.assertRaises(module.CommandFailure):
                run.create("network", ["network", "create", run.network_name])
            self.assertFalse(run.cleanup())
            self.assertIn("network", run.pending)
            self.assertFalse(any(args[1] == "rm" for args, _ in fake.calls))

        def test_21_wrong_ownership_never_removes(self):
            for mutation in ("label", "id", "image", "network"):
                run, fake = created_pair()
                if mutation == "label": fake.resources["container"]["labels"] = {}
                if mutation == "id": fake.resources["container"]["id"] = "e" * 64
                if mutation == "image": fake.resources["container"]["image"] = "sha256:" + "e" * 64
                if mutation == "network": fake.resources["container"]["networks"] = {}
                fake.resources["network"]["containers"] = {"b" * 64: {}}
                with self.subTest(mutation=mutation):
                    self.assertFalse(run.cleanup())
                    self.assertFalse(any(args[:2] == ["container", "rm"] for args, _ in fake.calls))

        def test_22_wrong_configuration_blocks_acceptance(self):
            mutations = {"ReadonlyRootfs": False, "LogConfig": {"Type": "json-file"}, "Memory": 0, "MemorySwap": -1,
                         "NanoCpus": 0, "PidsLimit": 0, "ShmSize": 128 * module.MIB, "Privileged": True,
                         "IpcMode": "host", "Binds": ["existing:/data"]}
            for name, value in mutations.items():
                run, fake = created_pair()
                value_record = copy.deepcopy(fake.resources["container"])
                value_record["host"][name] = value
                with self.subTest(field=name), self.assertRaises(module.Refusal):
                    run.owned("container", value_record)

        def test_23_ports_volumes_and_tmpfs_are_checked(self):
            for field in ("port", "volume", "size", "extra_mount"):
                run, fake = created_pair()
                value = copy.deepcopy(fake.resources["container"])
                if field == "port": value["host"]["PortBindings"]["5432/tcp"][0]["HostIp"] = "0.0.0.0"
                if field == "volume": value["mounts"] = [{"Type": "volume", "Destination": "/data"}]
                if field == "size": value["host"]["Tmpfs"]["/tmp"] = "rw,size=99999999"
                if field == "extra_mount": value["host"]["Tmpfs"]["/extra"] = "size=1"
                with self.subTest(field=field), self.assertRaises(module.Refusal):
                    run.owned("container", value)

        def test_24_unowned_network_member_blocks_removal(self):
            run, fake = created_pair()
            fake.resources["network"]["containers"] = {"f" * 64: {}}
            self.assertFalse(run.cleanup())
            self.assertFalse(any(args[:2] == ["network", "rm"] for args, _ in fake.calls))

        def test_25_remove_timeout_is_not_cleanup(self):
            run, fake = created_pair()
            fake.fail_remove = True
            self.assertFalse(run.cleanup())
            self.assertTrue(fake.resources)

        def test_26_stop_timeout_is_not_cleanup(self):
            run, fake = created_pair()
            fake.resources["container"]["running"] = True
            fake.resources["network"]["containers"] = {"b" * 64: {}}
            fake.fail_stop = True
            self.assertFalse(run.cleanup())
            self.assertFalse(any(args[:2] == ["container", "rm"] for args, _ in fake.calls))

        def test_27_no_cleanup_without_creation_intent(self):
            run, fake = new_run()
            self.assertTrue(run.cleanup())
            self.assertEqual(fake.calls, [])
            with self.assertRaises(module.Refusal):
                run.owned("network", record(run, "network"))

        def test_28_preexisting_name_is_not_adopted(self):
            run, fake = new_run()
            fake.resources["network"] = record(run, "network")
            with self.assertRaises(module.Refusal):
                run.create("network", ["network", "create", run.network_name])
            self.assertFalse(run.intents)
            self.assertTrue(run.cleanup())
            self.assertIn("network", fake.resources)

        def test_29_command_deadline_and_environment(self):
            run, fake = new_run()
            run.lookup("network")
            _, kwargs = fake.calls[-1]
            self.assertEqual(kwargs["seconds"], 5)
            self.assertNotIn("DATABASE_URL", kwargs["env"])
            run.cleanup_deadline = -1
            with self.assertRaises(module.CommandFailure):
                run.lookup("network")

        def test_30_bounded_process_success_and_shell_false(self):
            calls = []
            def popen(*args, **kwargs):
                calls.append((args, kwargs))
                return FakeChild(out=b"ok", err=b"diagnostic")
            result = module.BoundedProcess(popen).run(["fake"], seconds=1, data=b"input")
            self.assertEqual((result.stdout, result.stderr, result.returncode), (b"ok", b"diagnostic", 0))
            self.assertIs(calls[0][1]["shell"], False)

        def test_31_combined_output_overflow(self):
            for out, err in ((b"a" * 8193, b""), (b"a" * 5000, b"b" * 5000)):
                with self.subTest(stdout=len(out), stderr=len(err)), self.assertRaises(module.CommandFailure) as raised:
                    module.BoundedProcess(lambda *a, **k: FakeChild(out, err)).run(["fake"], seconds=1, cap=8192)
                self.assertEqual(raised.exception.code, "output_limit")

        def test_32_process_timeout_and_uncertain_termination(self):
            for unkillable in (False, True):
                process = FakeChild(hang=True, unkillable=unkillable)
                with self.subTest(unkillable=unkillable), self.assertRaises(module.CommandFailure) as raised:
                    module.BoundedProcess(lambda *a, **k: process, Tick()).run(["fake"], seconds=0.1)
                self.assertTrue(process.killed)
                self.assertTrue(raised.exception.uncertain)

        def test_33_input_failure(self):
            with self.assertRaises(module.CommandFailure):
                module.BoundedProcess(lambda *a, **k: FakeChild(bad_input=True)).run(["fake"], seconds=1, data=b"x")

        def test_34_invalid_process_limits_refuse(self):
            for arguments in (dict(seconds=0), dict(seconds=901), dict(seconds=1, cap=module.CHILD_CAP + 1),
                              dict(seconds=1, data=b"x" * 65537)):
                with self.subTest(arguments=list(arguments)), self.assertRaises(module.Refusal):
                    module.BoundedProcess(forbidden_process).run(["fake"], **arguments)

        def test_35_progress_is_streamed_but_bounded(self):
            seen = []
            data = b'{"event":"case_start","case":"one"}\n'
            module.BoundedProcess(lambda *a, **k: FakeChild(data)).run(["fake"], seconds=1, progress=lambda value: seen.append(value) or True)
            self.assertEqual(seen, [{"event": "case_start", "case": "one"}])
            with self.assertRaises(module.CommandFailure):
                module.BoundedProcess(lambda *a, **k: FakeChild(b"x" * 8193)).run(["fake"], seconds=1, progress=lambda value: True)

        def test_36_evidence_cap_before_retention(self):
            run, _ = new_run()
            with self.assertRaises(module.Refusal):
                run.receipt(detail="x" * module.EVIDENCE_CAP)
            self.assertFalse(run.receipts)

        def test_37_private_worker_rejects_arbitrary_target_shape(self):
            for value in ({}, {"dsn": "postgresql://existing"}, {"container_id": "existing"}):
                with self.subTest(keys=list(value)), self.assertRaises(AcceptanceFailure):
                    validate_payload(value)

        def test_38_real_path_has_pinned_migrations_and_no_placeholders(self):
            source = Path(__file__).read_text(encoding="utf-8")
            tree = ast.parse(source)
            runtime = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "PostgreSQLAcceptance")
            segment = ast.get_source_segment(source, runtime)
            self.assertNotIn("create_all", segment)
            self.assertNotIn("pytest.skip", segment)
            self.assertNotIn("unittest.skip", segment)
            self.assertIn("pg_blocking_pids", segment)
            self.assertIn("pg_terminate_backend", segment)
            self.assertIn("self.original_connect(cls, **kwargs)", segment)
            self.assertTrue("research_ownership.OwnershipService(self.verifier, factory)" in segment)
            self.assertEqual(CHAIN[-3:], ("f94c6f41e0cb", "a7c730103001", "b8d741104001"))
            self.assertNotIn("app.database", module.MIGRATION_ENV)
            self.assertIn('context.config.attributes["connection"]', module.MIGRATION_ENV)

        def test_39_failed_bound_does_not_strand_identified_container(self):
            run, fake = created_pair()
            fake.resources["container"]["host"]["ReadonlyRootfs"] = False
            with self.assertRaises(module.Refusal):
                run.owned("container", fake.resources["container"])
            self.assertTrue(run.cleanup())
            self.assertFalse(fake.resources)

        def test_40_progress_uses_available_bytes_not_full_buffer(self):
            class Stream(io.BytesIO):
                def read(self, size=-1):
                    raise AssertionError("blocking_read_used")
            child = FakeChild()
            child.stdout = Stream(b'{"event":"case_start","case":"short"}\n')
            seen = []
            module.BoundedProcess(lambda *a, **k: child).run(["fake"], seconds=1,
                                                            progress=lambda event: seen.append(event) or 60)
            self.assertEqual(len(seen), 1)

        def test_41_kernel_bounds_must_be_observable(self):
            raw = f"{768 * module.MIB}\n0\n200000 100000\n128\n".encode()
            module.validate_cgroup(raw)
            for value in (raw.replace(b"0\n200000", b"max\n200000"), raw.replace(b"200000", b"max"),
                          raw.replace(b"128", b"max"), raw.replace(str(768 * module.MIB).encode(), b"max"), b""):
                with self.subTest(raw=value), self.assertRaises(module.Refusal):
                    module.validate_cgroup(value)

        def test_42_worker_matrix_is_exact_and_migration_is_prewrite_bound(self):
            self.assertEqual(len(module.CASE_NAMES), 32)
            self.assertEqual(len(set(module.CASE_NAMES)), 32)
            source = Path(__file__).read_text(encoding="utf-8")
            tree = ast.parse(source)
            cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "PostgreSQLAcceptance")
            setup = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "setup")
            segment = ast.get_source_segment(source, setup)
            self.assertLess(segment.index("prewrite_cluster_identity_mismatch"), segment.index("CREATE EXTENSION vector"))

        def test_43_failed_evidence_sink_still_allows_owned_cleanup(self):
            run, fake = created_pair()
            run.report_durable = False
            with self.assertRaises(module.Refusal):
                run.lookup("network")
            self.assertTrue(run.cleanup())
            self.assertFalse(fake.resources)

        def test_44_overflow_preserves_cleanup_reserve(self):
            run, fake = created_pair()
            with self.assertRaises(module.Refusal):
                run.receipt(detail="x" * module.EVIDENCE_CAP)
            self.assertTrue(run.evidence_overflow)
            self.assertTrue(run.cleanup())
            self.assertFalse(fake.resources)

        def test_45_actual_auth_exception_contract_and_no_checkout(self):
            harness = auth_fixture()
            harness.auth_boundary()
            self.assertEqual(harness.checkouts, 1)  # Only the final successful control.

        def test_46_auth_refusal_is_strict_about_reason_type_and_checkout(self):
            harness = auth_fixture()
            for code in ("AUTH_UNAVAILABLE", "AUTH_INVALID"):
                with self.subTest(code=code):
                    error = harness.auth.AuthFailure(code)
                    self.assertIs(harness.auth_denied(lambda: (_ for _ in ()).throw(error), code), error)
            with self.assertRaises(AcceptanceFailure):
                harness.auth_denied(lambda: (_ for _ in ()).throw(harness.auth.AuthFailure("AUTH_OTHER")), "AUTH_INVALID")
            for error in (AttributeError("unrelated"), RuntimeError("unrelated"), harness.own.OwnershipFailure("AUTH_INVALID")):
                with self.subTest(type=type(error).__name__), self.assertRaises(type(error)):
                    harness.auth_denied(lambda error=error: (_ for _ in ()).throw(error), "AUTH_INVALID")
            def checkout_then_refuse():
                harness.checkouts += 1
                raise harness.auth.AuthFailure("AUTH_INVALID")
            with self.assertRaisesRegex(AcceptanceFailure, "authentication_reached_checkout"):
                harness.auth_denied(checkout_then_refuse, "AUTH_INVALID")
            with self.assertRaisesRegex(AcceptanceFailure, "authentication_failure_missing"):
                harness.auth_denied(lambda: None, "AUTH_INVALID")

        def test_47_auth_regression_rejects_old_ownership_only_helper(self):
            # Controlled in-memory old behavior, not an edit to committed auth.
            for code in ("AUTH_UNAVAILABLE", "AUTH_INVALID"):
                harness = auth_fixture()
                with patch.object(PostgreSQLAcceptance, "auth_denied", PostgreSQLAcceptance.denied):
                    with self.subTest(code=code), self.assertRaises(harness.auth.AuthFailure):
                        harness.auth_denied(lambda: (_ for _ in ()).throw(harness.auth.AuthFailure(code)), code)

        def test_48_backend_proxy_and_precommit_paths_require_driver_witness(self):
            for dispatch in (False, True):
                harness, driver, proxy, events = backend_fixture()
                self.assertIsInstance(proxy.info, dict)
                with self.subTest(dispatch=dispatch), patch("sys.stdout", new=io.StringIO()):
                    harness.backend_failure(dispatch)
                self.assertEqual(events.count("termination_query"), 1)
                self.assertEqual(events.count("backend_absence"), 1)
                self.assertIn("driver_commit" if dispatch else "driver_execute", events)
                self.assertIn(driver, harness.invalidated)
                self.assertTrue(driver.closed)
                self.assertIn("reconciled", events)

        def test_49_prequery_python_error_cannot_pass_as_termination(self):
            harness, _, _, events = backend_fixture()
            def before_query(driver):
                raise AttributeError("synthetic_prequery_failure")
            harness.terminate = before_query
            with self.assertRaises(AcceptanceFailure):
                harness.backend_failure(True)
            self.assertIn(("service_wrapped", "AttributeError"), events)
            self.assertNotIn("termination_query", events)
            self.assertNotIn("reconciled", events)

        def test_50_missing_or_unsuccessful_termination_witness_fails(self):
            for options in (dict(termination_result=[]), dict(termination_result=[(False,)]), dict(absent=False)):
                harness, _, _, events = backend_fixture(**options)
                with self.subTest(options=options), patch("sys.stdout", new=io.StringIO()), self.assertRaises(AcceptanceFailure):
                    harness.backend_failure(True)
                self.assertNotIn("reconciled", events)
            harness, _, _, events = backend_fixture()
            harness.terminate = lambda driver: None
            with self.assertRaisesRegex(AcceptanceFailure, "termination_witness_missing"):
                harness.backend_failure(True)
            self.assertNotIn("termination_query", events)

        def test_51_wrong_target_cannot_reach_termination_query(self):
            for column in range(4):
                metadata = ["ucr_db_" + "c" * 32, "ucr_svc_" + "c" * 32, "ucr_" + "c" * 32 + "_service", "start"]
                metadata[column] = "" if column == 3 else "wrong_target"
                harness, _, _, events = backend_fixture(metadata=[tuple(metadata)])
                with self.subTest(column=column), self.assertRaises(AcceptanceFailure):
                    harness.backend_failure(True)
                self.assertNotIn("termination_query", events)

        def test_52_driver_failure_and_closed_invalidation_are_required(self):
            harness, driver, _, _ = backend_fixture()
            with patch("sys.stdout", new=io.StringIO()):
                witness = harness.terminate(driver)
                driver.closed = True
                harness.invalidated.append(driver)
                for error in (None, AttributeError("unrelated"), harness.pg.OperationalError("57014")):
                    with self.subTest(error=type(error).__name__), self.assertRaises(AcceptanceFailure):
                        harness.verify_termination(driver, 6401, witness, error)
                error = harness.pg.OperationalError()
                harness.verify_termination(driver, 6401, witness, error)
                for field, value in (("pid", 999), ("database", "wrong"), ("role", "wrong"), ("application", "wrong"),
                                     ("backend_start", ""), ("terminated", False), ("backend_absent", False)):
                    with self.subTest(field=field), self.assertRaises(AcceptanceFailure):
                        harness.verify_termination(driver, 6401, dict(witness, **{field: value}), error)
                harness.invalidated.clear()
                with self.assertRaises(AcceptanceFailure):
                    harness.verify_termination(driver, 6401, witness, error)
                harness.invalidated.append(driver)
                driver.closed = False
                with self.assertRaises(AcceptanceFailure):
                    harness.verify_termination(driver, 6401, witness, error)

        def test_53_backend_regression_rejects_original_proxy_false_positive(self):
            tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
            cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "PostgreSQLAcceptance")
            method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "backend_failure")
            class OldProxy(ast.NodeTransformer):
                def visit_Attribute(self, node):
                    if isinstance(node.value, ast.Name) and node.value.id == "proxy" and node.attr == "driver_connection":
                        return ast.copy_location(ast.Name(id="proxy", ctx=ast.Load()), node)
                    return self.generic_visit(node)
            scope = dict(globals())
            exec(compile(ast.fix_missing_locations(ast.Module(body=[OldProxy().visit(method)], type_ignores=[])),
                         "<in-memory-old-proxy>", "exec"), scope)
            harness, _, _, events = backend_fixture()
            harness.backend_failure = MethodType(scope["backend_failure"], harness)
            with self.assertRaises(AcceptanceFailure):
                harness.backend_failure(True)
            self.assertIn(("service_wrapped", "AttributeError"), events)
            self.assertNotIn("termination_query", events)
            # Without the new witness requirement the old zero-row/indeterminate
            # check would pass; the same negative regression must reject that.
            harness, _, _, events = backend_fixture()
            harness.backend_failure = MethodType(scope["backend_failure"], harness)
            with patch.object(PostgreSQLAcceptance, "verify_termination", lambda *args: None):
                with self.assertRaises(self.failureException):
                    with self.assertRaises(AcceptanceFailure):
                        harness.backend_failure(True)
            self.assertIn("reconciled", events)

        def test_54_reader_errors_are_supervised_even_with_zero_exit(self):
            class Broken(io.BytesIO):
                def __init__(self, partial):
                    super().__init__()
                    self.partial = partial
                def read1(self, size=-1):
                    if self.partial:
                        self.partial = False
                        return b"partial_output"
                    raise OSError("private_stream_diagnostic")
            for stream in ("stdout", "stderr"):
                for exited in (False, True):
                    for partial in (False, True):
                        child = FakeChild(hang=not exited)
                        setattr(child, stream, Broken(partial))
                        with self.subTest(stream=stream, exited=exited, partial=partial), self.assertRaises(module.CommandFailure) as raised:
                            module.BoundedProcess(lambda *a, **k: child).run(["fake"], seconds=1)
                        self.assertEqual(raised.exception.code, "capture_read_failure")
                        self.assertTrue(raised.exception.uncertain)
                        self.assertNotIn("private_stream", str(raised.exception))
                        if not exited:
                            self.assertTrue(child.killed)

        def test_55_verified_eof_success_and_non_eof_rejection(self):
            control = module.BoundedProcess(lambda *a, **k: FakeChild(b"complete", b"diagnostic")).run(["fake"], seconds=1)
            self.assertEqual((control.stdout, control.stderr, control.returncode), (b"complete", b"diagnostic", 0))
            class NotEOF(io.BytesIO):
                def read1(self, size=-1):
                    return None
            child = FakeChild()
            child.stdout = NotEOF()
            with self.assertRaises(module.CommandFailure):
                module.BoundedProcess(lambda *a, **k: child).run(["fake"], seconds=1)

        def test_56_capture_failure_reconciles_only_positive_created_resource(self):
            class Broken(io.BytesIO):
                def read1(self, size=-1):
                    raise OSError("synthetic_capture_failure")
            for created in (False, True):
                run, fake = new_run()
                ordinary = fake.run
                def adapter(argv, **kwargs):
                    if argv[3:5] == ["network", "create"]:
                        if created:
                            ordinary(argv, **kwargs)  # Daemon created it before capture failed.
                        else:
                            fake.calls.append((argv[3:], kwargs))
                        child = FakeChild()
                        child.stdout = Broken()
                        return module.BoundedProcess(lambda *a, **k: child).run(argv, seconds=1)
                    return ordinary(argv, **kwargs)
                fake.run = adapter
                with self.subTest(created=created), self.assertRaises(module.CommandFailure) as raised:
                    run.create("network", ["network", "create", run.network_name])
                self.assertTrue(raised.exception.uncertain)
                self.assertIn("network", run.pending)
                self.assertEqual(run.cleanup(), created)
                self.assertEqual(sum(args[:2] == ["network", "create"] for args, _ in fake.calls), 1)
                if not created:
                    self.assertIn("network", run.pending)
                    self.assertFalse(any(args[1] == "rm" for args, _ in fake.calls))

        def test_57_cleanup_capture_failure_is_not_confirmed_removal(self):
            run, fake = created_pair()
            ordinary = fake.run
            class Broken(io.BytesIO):
                def read1(self, size=-1):
                    raise OSError("synthetic_cleanup_capture_failure")
            def adapter(argv, **kwargs):
                if argv[3:5] == ["container", "rm"]:
                    ordinary(argv, **kwargs)
                    child = FakeChild()
                    child.stderr = Broken()
                    return module.BoundedProcess(lambda *a, **k: child).run(argv, seconds=1)
                return ordinary(argv, **kwargs)
            fake.run = adapter
            self.assertFalse(run.cleanup())
            self.assertTrue(any(r.get("event") == "cleanup_unverified" and r.get("kind") == "container" for r in run.receipts))
            self.assertEqual(sum(args[:2] == ["container", "rm"] for args, _ in fake.calls), 1)
            self.assertFalse(any(args[:2] == ["network", "rm"] for args, _ in fake.calls))

        def test_58_capture_regression_rejects_ignored_reader_failure_variant(self):
            tree = ast.parse((ROOT / module.FILES[0]).read_text(encoding="utf-8"))
            cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "BoundedProcess")
            class IgnoreReaderFailure(ast.NodeTransformer):
                def visit_Call(self, node):
                    if (isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)
                            and node.func.value.id == "reader_failed" and node.func.attr == "is_set"):
                        return ast.copy_location(ast.Constant(False), node)
                    return self.generic_visit(node)
                def visit_If(self, node):
                    if any(isinstance(n, ast.Name) and n.id == "reader_eof" for n in ast.walk(node.test)):
                        node.test = ast.Constant(False)
                    return self.generic_visit(node)
            scope = dict(vars(module))
            exec(compile(ast.fix_missing_locations(ast.Module(body=[IgnoreReaderFailure().visit(cls)], type_ignores=[])),
                         "<in-memory-ignored-reader-failure>", "exec"), scope)
            class Broken(io.BytesIO):
                def read1(self, size=-1):
                    raise OSError("synthetic_read_error")
            child = FakeChild()
            child.stdout = Broken()
            with self.assertRaises(self.failureException):
                with self.assertRaises(module.CommandFailure):
                    scope["BoundedProcess"](lambda *a, **k: child).run(["fake"], seconds=1)

        def test_59_workspace_scenario_requires_exact_schedule_and_revocation(self):
            h, replies, counts, events = workspace_fixture()
            h.workspace_notes()
            self.assertEqual((replies, counts), ([], []))
            self.assertEqual(events, ["catalog_enter", ("revoke", "alice", "alice", 1), ("invalidate", "bob"), "catalog_exit"])

        def test_60_workspace_scenario_rejects_wrong_pins_labels_and_disclosure(self):
            for index, key, value in [(0,"source_verification","verified"), (0,"sources",[]),
                    (1,"source",{"different_pin":8}), (1,"body","wrong draft"), (2,"body","wrong replay"),
                    (5,"items",[]), (8,"body","wrong export"), (7,"body","foreign note"),
                    (9,"source",{"private":True}), (10,"items",[{}]), (11,"body","revoked note"), (12,"source",{})]:
                with self.subTest(index=index, key=key):
                    h, replies, _, events = workspace_fixture()
                    replies[index][4][key] = value
                    with self.assertRaises(AcceptanceFailure): h.workspace_notes()
                    self.assertEqual(events[-1], "catalog_exit")
            h, _, counts, events = workspace_fixture(); counts[0] = ("alice", (1,0))
            with self.assertRaises(AcceptanceFailure): h.workspace_notes()
            self.assertEqual(events[-1], "catalog_exit")

        def test_61_note_atomicity_adapter_checks_validation_cancel_race_and_conflict(self):
            h, note, saves, counts, events = note_fixture(); error = h.own.OwnershipFailure
            race = SimpleNamespace(artifact_key="race")
            saves.extend([error("OWNERSHIP_NOTE_INVALID"), error("OWNERSHIP_NOTE_INVALID"),
                error("OWNERSHIP_CANCELLED"), note, race, race, error("OWNERSHIP_IDEMPOTENCY_CONFLICT")])
            counts.extend([(0,0),(0,0),(0,0),(1,1),(2,2),(2,2)])
            h.note_atomicity()
            self.assertEqual((saves, counts), ([], [])); self.assertIn("cancel", events); self.assertIn("overlap", events)
            self.assertIsNone(h.flush_hook)
            probes = [event for event in events if isinstance(event,tuple) and event[0] == "constraint_probe"]
            self.assertEqual(len(probes),2); self.assertTrue(all(event[2] == "23514" for event in probes))
            self.assertIn("repeat(chr(8364),6000)",probes[1][1])
            h, _, saves, counts, _ = note_fixture()
            saves.append(h.own.OwnershipFailure("OWNERSHIP_NOTE_INVALID")); counts.append((1,0))
            with self.assertRaisesRegex(AcceptanceFailure, "invalid_note_consumed_quota"): h.note_atomicity()

        def test_62_note_commit_adapters_require_paired_ground_truth_and_explicit_replay(self):
            for after in (False, True):
                with self.subTest(after=after):
                    h, note, saves, counts, events = note_fixture()
                    saves.extend(["commit",note,note]); counts.extend([(int(after),int(after)),(1,1),(1,1)])
                    with patch("sys.stdout", new=io.StringIO()): h.note_indeterminate(after)
                    self.assertEqual((saves,counts),([],[])); self.assertEqual(events.count("real_commit"),int(after))
                    h, _, saves, counts, _ = note_fixture(); saves.append("commit"); counts.append((1,0))
                    with self.assertRaisesRegex(AcceptanceFailure, "uncertain_note_pair_ground_truth_wrong"):
                        h.note_indeterminate(after)

        def test_63_asgi_message_driver_binds_client_and_bounds_response(self):
            class Loop:
                def run_until_complete(self, coroutine):
                    try: coroutine.send(None)
                    except StopIteration as result: return result.value
                    finally: coroutine.close()
                    raise AcceptanceFailure("scripted_coroutine_suspended")
            seen = []
            async def app(scope, receive, send):
                seen.append((scope, await receive()))
                await send({"type":"http.response.start", "status":200, "headers":[(b"cache-control",b"private, no-store")]})
                await send({"type":"http.response.body", "body":b'{"synthetic":true}'})
            h = PostgreSQLAcceptance.__new__(PostgreSQLAcceptance); h.loop = Loop()
            client = dict(app=app,cookie="synthetic-cookie",csrf="synthetic-csrf")
            self.assertEqual(h.workspace_call(client,"POST","/notes?after=marker",{"body":"synthetic"})[:2],(200,{"synthetic":True}))
            scope, request = seen[0]
            self.assertEqual(scope["query_string"],b"after=marker")
            self.assertEqual(dict(scope["headers"])[b"x-finlens-csrf"],b"synthetic-csrf")
            self.assertEqual(dict(scope["headers"])[b"origin"],b"https://finlens.test")
            self.assertEqual(json.loads(request["body"]),{"body":"synthetic"})
            for body, cache in ((b"x"*65537,b"private, no-store"),(b"{}",b"public")):
                async def invalid(scope, receive, send):
                    await send({"type":"http.response.start","status":200,"headers":[(b"cache-control",cache)]})
                    await send({"type":"http.response.body","body":body})
                with self.assertRaises(AcceptanceFailure): h.workspace_call({**client,"app":invalid},"GET","/notes")

        def test_64_catalog_fixture_cleans_exact_synthetic_selectors_on_failure(self):
            for fail in (False,True):
                events = []
                @contextmanager
                def transaction():
                    events.append("begin")
                    try: yield
                    finally: events.append("end")
                h = PostgreSQLAcceptance.__new__(PostgreSQLAcceptance); h.one = lambda query: 0
                h.observer = SimpleNamespace(transaction=transaction,execute=lambda statement,params:events.append((statement,params)))
                try:
                    with h.catalog_fixture():
                        if fail: raise RuntimeError("synthetic body failure")
                except RuntimeError: self.assertTrue(fail)
                statements = [event for event in events if isinstance(event,tuple)]
                self.assertEqual(len(statements),6)
                self.assertTrue(all(sql.startswith("INSERT INTO ") for sql,_ in statements[:3]))
                self.assertEqual([params for _,params in statements[3:]],[('0000000001','0000000001-24-000001'),('0000000001',),('0000000001',)])
                self.assertTrue(all(sql.startswith("DELETE FROM ") and " WHERE " in sql for sql,_ in statements[3:]))
                self.assertEqual(events.count("begin"),2); self.assertEqual(events.count("end"),2)

        def test_65_note_grants_guard_destinations_and_worker_loop_are_explicit(self):
            grants = module.grants("ucr_db_test","ucr_svc_test")
            self.assertEqual(module.UPDATES["research_notes"],("artifact_revision",))
            self.assertEqual([s for s in grants if s.startswith("GRANT SELECT (")],[
                'GRANT SELECT (company_cik, accession_number, data_version, content_digest) ON TABLE public.filing_publications TO "ucr_svc_test"',
                'GRANT SELECT (company_cik, evidence_version, data_version) ON TABLE public.company_refresh_state TO "ucr_svc_test"'])
            probes = dict(module.privilege_probes("ucr_svc_test","ucr_admin_test","a"*32))
            self.assertEqual(probes["facts_read"],"SELECT value FROM public.financial_facts WHERE false")
            self.assertIn("cleaned_text",probes["filing_text_read"]); self.assertIn("body=",probes["note_body"])
            self.assertEqual(len(module.PROTECTED),5)
            self.assertEqual(module.BACKEND_BASELINE,"1706418959e0b5909ab7b1f86f1311714db1a8e6")
            source = Path(__file__).read_text(encoding="utf-8"); tree = ast.parse(source)
            entry = ast.get_source_segment(source,next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="worker_entry"))
            self.assertLess(entry.index("validate_payload(payload)"),entry.index("asyncio.new_event_loop()"))
            self.assertLess(entry.index("asyncio.new_event_loop()"),entry.index("runtime_guard(payload)"))
            self.assertIn("shutdown_default_executor(timeout=5)",entry); self.assertIn("loop.close()",entry)
            self.assertIn("ThreadPoolExecutor(max_workers=2)",entry)
            audits = []
            with patch.object(sys,"meta_path",list(sys.meta_path)), patch.object(sys,"addaudithook",side_effect=audits.append), \
                    patch.dict(runtime_guard.__globals__,{"protect_env_files":lambda:None}):
                runtime_guard({"port":65432})
                self.assertIsNone(sys.meta_path[0].find_spec("app.private_workspace_http"))
                with self.assertRaises(AcceptanceFailure): sys.meta_path[0].find_spec("app.main")
            audits[0]("socket.connect",(None,("127.0.0.1",65432)))
            with self.assertRaises(AcceptanceFailure): audits[0]("socket.connect",(None,("127.0.0.1",5432)))
            with self.assertRaises(AcceptanceFailure): audits[0]("subprocess.Popen",())

        def test_66_worker_loop_cleanup_failure_cannot_return_success(self):
            import concurrent.futures
            nonce = "1" * 32
            payload = dict(nonce=nonce,port=65432,database="ucr_db_"+nonce,admin="ucr_admin_"+nonce,
                service="ucr_svc_"+nonce,admin_password="A"*43,service_password="B"*43,
                system_identifier="123",container_id="2"*64,
                migration_directory=str(Path(os.environ["LOCALAPPDATA"])/"FinLens/ownership-acceptance"/nonce/"migration"))
            for failure in (None,"run","shutdown","payload"):
                with self.subTest(failure=failure):
                    events = []
                    class Loop:
                        def set_default_executor(self, executor): events.append("executor")
                        def shutdown_default_executor(self, *, timeout):
                            self.timeout = timeout
                            if failure == "shutdown": raise RuntimeError("synthetic shutdown failure")
                            return "shutdown"
                        def run_until_complete(self, value): events.append(value)
                        def close(self): events.append("close")
                    loop = Loop()
                    class Acceptance:
                        def run(self):
                            events.append("run")
                            if failure == "run": raise AcceptanceFailure("synthetic_run_failure")
                    data = {} if failure == "payload" else payload
                    with patch.dict(sys.modules,{"asyncio":SimpleNamespace(new_event_loop=lambda:loop)}), \
                            patch.object(concurrent.futures,"ThreadPoolExecutor",side_effect=lambda **kw:events.append(kw)), \
                            patch.object(sys,"stdin",SimpleNamespace(buffer=io.BytesIO(json.dumps(data).encode()))), \
                            patch.object(sys,"path",list(sys.path)), patch("sys.stdout",new=io.StringIO()) as output, \
                            patch.dict(worker_entry.__globals__,{"PostgreSQLAcceptance":lambda p:Acceptance(),
                                                                 "runtime_guard":lambda p:events.append("guard")}):
                        self.assertEqual(worker_entry(),0 if failure is None else 1)
                        if failure is not None: self.assertIn('"event":"failure"',output.getvalue())
                    if failure == "payload": self.assertEqual(events,[])
                    else:
                        self.assertIn({"max_workers":2},events)
                        self.assertEqual(events[-1],"close")
                        self.assertEqual(loop.timeout,5)

        def test_67_schema_inspector_accepts_note_artifact_pk_and_rejects_malformed_keys(self):
            from types import ModuleType
            class Kind:
                def __str__(self): return "TEXT"
            metadata = {}
            models = ModuleType("app.models")
            for class_name, table_name, names, primary in (
                    ("ResearchAccount","research_accounts",["id"],["id"]),
                    ("ResearchSession","research_sessions",["id","owner_id"],["id"]),
                    ("ResearchArtifact","research_artifacts",["id","owner_id","session_id"],["id"]),
                    ("ResearchNote","research_notes",["artifact_id","owner_id","session_id"],["artifact_id"])):
                columns = {name:SimpleNamespace(name=name,nullable=False,type=Kind(),server_default=None) for name in names}
                table = SimpleNamespace(name=table_name,columns=columns,constraints=[],
                    primary_key=SimpleNamespace(columns=[columns[name] for name in primary]))
                metadata[table_name] = table
                setattr(models,class_name,SimpleNamespace(__table__=table))
            class Inspector:
                def get_table_names(self, **kwargs): return list(module.OWNED+module.LEGACY)
                def get_columns(self, name, **kwargs):
                    return [dict(name=c.name,nullable=c.nullable,type=c.type,default=None) for c in metadata[name].columns.values()]
                def get_pk_constraint(self, name):
                    return {"constrained_columns":bad_keys if name==bad_table else [c.name for c in metadata[name].primary_key.columns]}
                def get_unique_constraints(self, name): return []
                def get_check_constraints(self, name): return []
                def get_foreign_keys(self, name):
                    owned = dict(name="fk_research_artifact_owned_session" if name=="research_artifacts" else "fk_research_note_owned_session",
                        constrained_columns=["owner_id","session_id"],referred_table="research_sessions",referred_columns=["owner_id","id"])
                    return [owned] if name=="research_artifacts" else [owned,dict(constrained_columns=["artifact_id"],referred_table="research_artifacts")]
            h = PostgreSQLAcceptance.__new__(PostgreSQLAcceptance); h.launcher = module
            connection = object()
            sqlalchemy = ModuleType("sqlalchemy")
            def inspect(supplied):
                self.assertIs(supplied,connection)
                return Inspector()
            sqlalchemy.inspect = inspect
            app = ModuleType("app"); app.models = models
            cases = [(None,None),("research_notes",["id"]),("research_notes",[]),
                     ("research_notes",["artifact_id","owner_id"]),("research_notes",["artifact_id","artifact_id"]),
                     ("research_accounts",["subject"]),("research_sessions",["id","id"])]
            with patch.dict(sys.modules,{"app":app,"app.models":models,"sqlalchemy":sqlalchemy}):
                for bad_table,bad_keys in cases:
                    with self.subTest(table=bad_table, keys=bad_keys):
                        if bad_table is None: h.schema(connection)
                        else:
                            with self.assertRaisesRegex(AcceptanceFailure,"migration_pk_wrong"): h.schema(connection)

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(OfflineChecks)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps({"offline_only": True, "tests": result.testsRun, "failures": len(result.failures),
                      "errors": len(result.errors), "skips": len(result.skipped), "positive_guard_hits": attempts,
                      "postgres_cases": "NOT_RUN"}, sort_keys=True))
    return 0 if result.wasSuccessful() and not result.skipped else 1


def offline_admission_checks():
    """New admission cases only: synthetic bytes/Git, no real writes or processes."""
    import socket
    import subprocess
    import unittest
    from unittest.mock import patch

    attempts = {"process": 0, "network": 0, "import": 0, "env": 0, "write": 0}

    def blocked(kind):
        attempts[kind] += 1
        raise AcceptanceFailure("admission_offline_" + kind + "_forbidden")

    class ImportGuard(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in {"app", "psycopg", "sqlalchemy", "alembic", "jwt", "cryptography",
                                           "dotenv", "fastapi", "uvicorn", "openai", "torch", "sentence_transformers",
                                           "sqlite3", "httpx", "requests"}:
                blocked("import")

    def audit(event, args):
        if event.startswith("subprocess.") or event in {"os.system", "sqlite3.connect"}:
            blocked("process")
        if event.startswith("socket."):
            blocked("network")
        if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
            name = os.fsdecode(os.fspath(args[0])).replace("\\", "/").rsplit("/", 1)[-1]
            if name == ".env" or name.startswith(".env."):
                blocked("env")
            mode, flags = args[1], args[2]
            if mode is not None and any(c in mode for c in "wax+") or flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC):
                blocked("write")

    sys.meta_path.insert(0, ImportGuard())
    sys.addaudithook(audit)
    subprocess.Popen = os.system = lambda *a, **k: blocked("process")
    socket.create_connection = socket.getaddrinfo = lambda *a, **k: blocked("network")
    socket.socket.connect = socket.socket.connect_ex = lambda *a, **k: blocked("network")
    module = launcher_module()
    files = (
        "backend/scripts/accept_research_ownership_postgres.py",
        "backend/tests/acceptance_research_ownership_postgres.py",
        "docs/exec-plans/active/2026-10-30-ucr-ownership-postgres-acceptance.md",
    )
    execution = "e" * 40
    diff = ["diff", "--no-ext-diff", "--no-textconv", "--quiet"]
    calls = {"fixtures": 0, "refusals_before_effects": 0}

    def digest(content, paths=files):
        value = hashlib.sha256()
        for relative in paths:
            for part in (relative.encode(), content[relative]):
                value.update(len(part).to_bytes(8, "big"))
                value.update(part)
        return value.hexdigest()

    class Fixture:
        def __init__(self):
            self.working = {relative: (relative + "\nsynthetic\n").encode() for relative in files}
            self.committed = dict(self.working)
            self.protected = {relative: ("protected:" + relative).encode() for relative in module.PROTECTED}
            self.hashes = {relative: hashlib.sha256(data).hexdigest() for relative, data in self.protected.items()}
            self.digest = digest(self.working)
            self.head, self.branch, self.staged = execution, b"main\n", False
            self.status = b"".join((b" M " if p == "frontend/next-env.d.ts" else b"?? ") + p.encode() + b"\0"
                                   for p in module.PROTECTED)
            self.missing, self.changes, self.worktree_changes = set(), {}, False
            self.entries, self.faults, self.git_calls, self.reads, self.effects, self.receipts = {}, {}, [], [], [], []
            self.paths = files

        def arguments(self):
            return ["--execute", "--docker-context", "desktop-linux", "--expected-context-endpoint",
                    "npipe:////./pipe/dockerDesktopLinuxEngine", "--image", "pgvector/pgvector@sha256:" + "a" * 64,
                    "--expected-head", execution, "--candidate-sha256", self.digest]

        def read(self, path):
            relative = path.relative_to(ROOT).as_posix()
            self.reads.append(relative)
            if relative in self.working:
                return self.working[relative]
            if relative in self.protected:
                return self.protected[relative]
            raise FileNotFoundError("synthetic_missing_file")

        def run(self, argv, **kwargs):
            check(argv[0] == "git" and kwargs == {"seconds": 5, "cwd": str(ROOT), "env": module.clean_environment()},
                  "non_git_or_unbounded_admission_command")
            args = argv[1:]
            self.git_calls.append(args)
            if args[0] in self.faults:
                fault = self.faults[args[0]]
                if isinstance(fault, BaseException):
                    raise fault
                return fault
            output, code = b"", 0
            if args[:2] == ["rev-parse", "--verify"]:
                revision = args[2].removesuffix("^{commit}")
                check(args[2] == revision + "^{commit}" and revision in {module.BACKEND_BASELINE, execution},
                      "wrong_commit_verification")
                output, code = revision.encode() + b"\n", int(revision in self.missing)
            elif args == ["rev-parse", "HEAD"]:
                output = self.head.encode() + b"\n"
            elif args == ["branch", "--show-current"]:
                output = self.branch
            elif args == [*diff, "--cached"]:
                code = int(self.staged)
            elif args == ["status", "--porcelain=v1", "-z", "--untracked-files=all"]:
                output = self.status
            elif args == [*diff, module.BACKEND_BASELINE, execution, "--", *module.BACKEND_INPUTS]:
                code = int(any(any(p == scope or p.startswith(scope + "/") for scope in module.BACKEND_INPUTS)
                               for p in self.changes))
            elif args == [*diff, "HEAD", "--", *module.BACKEND_INPUTS]:
                code = int(self.worktree_changes)
            elif args[:3] == ["ls-tree", "-z", execution] and args[3] == "--":
                relative = args[4]
                data = self.committed.get(relative)
                oid = hashlib.sha1(b"blob " + str(len(data or b"")).encode() + b"\0" + (data or b"")).hexdigest()
                output = self.entries.get(relative, b"100644 blob " + oid.encode() + b"\t" + relative.encode() + b"\0"
                                          if data is not None else b"")
            elif args[:2] == ["cat-file", "blob"]:
                found = [data for data in self.committed.values()
                         if hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest() == args[2]]
                check(len(found) == 1, "synthetic_blob_not_found")
                output = found[0]
            else:
                raise AcceptanceFailure("unexpected_admission_git_command")
            return module.Output(output, b"", code)

        def invoke(self, arguments=None):
            calls["fixtures"] += 1
            fixture = self

            class MemoryRun:
                def __init__(self, args, root, process):
                    fixture.effects.append("run_constructed")
                    self.nonce = "a" * 32

                def receipt(self, **values):
                    fixture.receipts.append(values)

                def execute(self):
                    fixture.effects.append("synthetic_execute")
                    return 0

            def mkdir(path, **kwargs):
                check(path == Path(os.environ["LOCALAPPDATA"]) / "FinLens/ownership-acceptance" / ("a" * 32)
                      and kwargs == {"parents": True, "exist_ok": False}, "unexpected_evidence_write")
                fixture.effects.append("synthetic_mkdir")

            with patch.object(Path, "read_bytes", lambda path: fixture.read(path)), patch.object(Path, "mkdir", mkdir), \
                    patch.object(module, "PROTECTED", self.hashes), patch.object(module, "FILES", self.paths), \
                    patch.object(module, "Run", MemoryRun), patch.dict(os.environ, {"LOCALAPPDATA": "C:/synthetic"}), \
                    patch("sys.stdout", new=io.StringIO()):
                return module.main(self.arguments() if arguments is None else arguments, process=self)

    class AdmissionChecks(unittest.TestCase):
        def refused(self, fixture, arguments=None):
            self.assertEqual(fixture.invoke(arguments), 2)
            self.assertEqual(fixture.effects, [])
            self.assertEqual(fixture.receipts, [])
            self.assertTrue(set(fixture.reads) <= set(files) | set(fixture.paths) | set(module.PROTECTED))
            calls["refusals_before_effects"] += 1

        def test_01_positive_guards(self):
            for name in ("app.database", "psycopg", "sqlalchemy", "alembic", "dotenv", "sqlite3"):
                with self.subTest(name=name), self.assertRaises(AcceptanceFailure):
                    __import__(name)
            for event, args in (("subprocess.Popen", ("docker", [], None, None)),
                                ("socket.connect", (None, ("127.0.0.1", 5432))),
                                ("open", (".env", "r", 0)),
                                ("open", ("synthetic_write", "w", os.O_WRONLY))):
                with self.subTest(event=event), self.assertRaises(AcceptanceFailure):
                    sys.audit(event, *args)
            self.assertTrue(all(attempts.values()))

        def test_02_postcommit_positive_and_receipt(self):
            fixture = Fixture()
            self.assertEqual(module.FILES, files)
            self.assertEqual(module.BACKEND_BASELINE, "1706418959e0b5909ab7b1f86f1311714db1a8e6")
            self.assertNotEqual(execution, module.BACKEND_BASELINE)
            self.assertEqual(fixture.invoke(), 0)
            self.assertEqual(fixture.effects, ["run_constructed", "synthetic_mkdir", "synthetic_execute"])
            record, = fixture.receipts
            self.assertEqual(record["backend_baseline"], module.BACKEND_BASELINE)
            self.assertEqual(record["execution_head"], execution)
            self.assertEqual(record["candidate_sha256"], fixture.digest)
            self.assertEqual(len({record["backend_baseline"], record["execution_head"], record["candidate_sha256"]}), 3)
            self.assertNotIn("head", record)
            self.assertEqual(len([c for c in fixture.git_calls if c[0] == "cat-file"]), 3)

        def test_03_missing_or_malformed_execution_revision(self):
            for value in (None, "", "e" * 39, "e" * 41, "E" * 40, "g" * 40, "main", execution + "\n"):
                fixture = Fixture()
                args = fixture.arguments()
                position = args.index("--expected-head")
                args[position:position + 2] = [] if value is None else ["--expected-head", value]
                with self.subTest(value=value):
                    self.refused(fixture, args)
                    self.assertEqual(fixture.git_calls, [])

        def test_04_head_branch_and_unavailable_commits(self):
            for kind in ("head", "branch", "baseline_missing", "execution_missing"):
                fixture = Fixture()
                if kind == "head": fixture.head = "f" * 40
                elif kind == "branch": fixture.branch = b"other\n"
                else: fixture.missing.add(module.BACKEND_BASELINE if kind == "baseline_missing" else execution)
                with self.subTest(kind=kind): self.refused(fixture)

        def test_05_clean_committed_backend_changes(self):
            for path in ("backend/app/account_auth.py", "backend/migrations/versions/synthetic.py", "backend/requirements.txt"):
                for change in ("content", "addition", "deletion", "mode"):
                    fixture = Fixture()
                    fixture.changes[path] = change
                    with self.subTest(path=path, change=change): self.refused(fixture)

        def test_06_backend_worktree_changes(self):
            fixture = Fixture()
            fixture.worktree_changes = True
            self.refused(fixture)

        def test_07_working_content_and_execplan_edits_refuse_early(self):
            for relative in files:
                fixture = Fixture()
                fixture.working[relative] += b"edit"
                with self.subTest(path=relative):
                    self.refused(fixture)
                    self.assertEqual(fixture.git_calls, [])

        def test_08_harness_order_and_path_changes(self):
            for paths in (tuple(reversed(files)), files[:-1], (files[0] + ".other", *files[1:])):
                fixture = Fixture()
                fixture.paths = paths
                with self.subTest(paths=paths):
                    self.refused(fixture)
                    self.assertEqual(fixture.git_calls, [])

        def test_09_dirty_harness_even_with_matching_new_digest(self):
            for relative in files:
                fixture = Fixture()
                fixture.working[relative] += b"edit"
                fixture.digest = digest(fixture.working)
                fixture.status += b" M " + relative.encode() + b"\0"
                with self.subTest(path=relative): self.refused(fixture)

        def test_10_missing_and_nonregular_committed_entries(self):
            for relative in files:
                for entry in (None, b"120000 blob " + b"a" * 40, b"040000 tree " + b"a" * 40,
                              b"160000 commit " + b"a" * 40, b"100644 tree " + b"a" * 40):
                    fixture = Fixture()
                    if entry is None: del fixture.committed[relative]
                    else: fixture.entries[relative] = entry + b"\t" + relative.encode() + b"\0"
                    with self.subTest(path=relative, entry=entry): self.refused(fixture)

        def test_11_committed_working_mismatch_including_execplan(self):
            for relative in files:
                fixture = Fixture()
                fixture.committed[relative] += b"committed_edit"
                with self.subTest(path=relative): self.refused(fixture)

        def test_12_raw_newline_and_byte_differences(self):
            for change in (lambda data: data.replace(b"\n", b"\r\n"), lambda data: b"\xef\xbb\xbf" + data):
                fixture = Fixture()
                fixture.committed[files[2]] = change(fixture.committed[files[2]])
                self.refused(fixture)

        def test_13_index_and_unrelated_status(self):
            fixture = Fixture()
            fixture.staged = True
            self.refused(fixture)
            for extra in (b" M unrelated.py\0", b"?? unrelated.py\0", b"M  frontend/next-env.d.ts\0",
                          b" M frontend/next-env.d.ts", b"\0", b"?? renamed.py\0old.py\0"):
                fixture = Fixture()
                fixture.status = extra
                with self.subTest(extra=extra): self.refused(fixture)

        def test_14_changed_protected_hashes(self):
            for relative in module.PROTECTED:
                fixture = Fixture()
                fixture.protected[relative] += b"edit"
                with self.subTest(path=relative): self.refused(fixture)

        def test_15_git_failures_at_every_command_family(self):
            for family in ("rev-parse", "branch", "diff", "status", "ls-tree", "cat-file"):
                for failure in (module.Output(b"", b"", 128), OSError("synthetic_failure"),
                                module.CommandFailure("output_limit", uncertain=True)):
                    fixture = Fixture()
                    fixture.faults[family] = failure
                    with self.subTest(family=family, failure=type(failure).__name__): self.refused(fixture)

        def test_16_malformed_and_excessive_git_results(self):
            for result in (None, module.Output("text", b"", 0), module.Output(b"", "text", 0),
                           module.Output(b"", b"", False), module.Output(b"", b"warning", 0),
                           module.Output(b"x" * (module.CLI_CAP + 1), b"", 0),
                           module.Output(b"x" * module.CLI_CAP, b"x", 0),
                           module.Output(execution.encode() + b"\nextra\n", b"", 0)):
                fixture = Fixture()
                fixture.faults["rev-parse"] = result
                with self.subTest(result=type(result).__name__): self.refused(fixture)

        def test_17_malformed_tree_and_status_results(self):
            for value in (b"", b"garbage\0", b"100644 blob " + b"G" * 40 + b"\t" + files[0].encode() + b"\0",
                          b"100644 blob " + b"a" * 40 + b"\twrong.py\0"):
                fixture = Fixture()
                fixture.entries[files[0]] = value
                self.refused(fixture)
            fixture = Fixture()
            fixture.status += fixture.status
            self.refused(fixture)

        def test_18_selector_isolation(self):
            with patch.dict(main.__globals__, {"offline_admission_checks": lambda: 7,
                                              "offline_checks": lambda: blocked("process"),
                                              "worker_entry": lambda: blocked("process")}), \
                    patch("sys.stdout", new=io.StringIO()), patch("sys.stderr", new=io.StringIO()):
                before = dict(attempts)
                self.assertEqual(main(["--offline-admission"]), 7)
                self.assertEqual(main([]), 2)
                for args in (["--offline-admission", "--offline"], ["--execute"]):
                    with self.assertRaises(SystemExit) as raised: main(args)
                    self.assertEqual(raised.exception.code, 2)
                self.assertEqual(attempts, before)

    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(AdmissionChecks))
    print(json.dumps({"offline_admission_only": True, "tests": result.testsRun, "failures": len(result.failures),
                      "errors": len(result.errors), "skips": len(result.skipped), "positive_guard_hits": attempts,
                      **calls, "previous_58_suite": "NOT_RERUN", "postgres_cases": "NOT_RUN"}, sort_keys=True))
    return 0 if result.wasSuccessful() and not result.skipped else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--offline", action="store_true", help="Run guarded launcher and scenario-adapter checks")
    selection.add_argument("--offline-admission", action="store_true", help="Run only new guarded admission checks")
    args = parser.parse_args(argv)
    if args.offline_admission:
        return offline_admission_checks()
    if not args.offline:
        print("REFUSED: choose --offline or --offline-admission; real acceptance requires the reviewed opt-in launcher")
        return 2
    return offline_checks()


if __name__ == "__main__":
    raise SystemExit(main())
