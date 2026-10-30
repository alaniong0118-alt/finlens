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
    allowed = {"app", "app.account_auth", "app.research_ownership", "app.models", "app.orm_base", "app.research_contracts"}

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


CHAIN = ("e4dda2eedbb0", "36134e0d3560", "77068e51af12", "d7b834408ba8", "f94c6f41e0cb", "a7c730103001")


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
        from app.research_contracts import KeyRef
        from cryptography.hazmat.primitives.asymmetric import rsa
        import jwt
        self.pg, self.sql, self.event, self.text, self.auth, self.own = psycopg, sql, event, text, account_auth, research_ownership
        self.KeyRef, self.jwt = KeyRef, jwt
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
        from app.models import ResearchAccount, ResearchSession, ResearchArtifact
        inspector = inspect(connection)
        expected_names = set(self.launcher.OWNED + self.launcher.LEGACY)
        check(set(inspector.get_table_names(schema="public")) == expected_names, "migration_table_set_wrong")
        for model in (ResearchAccount, ResearchSession, ResearchArtifact):
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
            check(set(inspector.get_pk_constraint(table.name)["constrained_columns"]) == {"id"}, "migration_pk_wrong")
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
                    expected = table in self.launcher.OWNED and (privilege in {"SELECT", "INSERT"}
                        or privilege == "UPDATE" and column in self.launcher.UPDATES[table])
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

    def case_cleanup(self):
        check(self.engine.pool.checkedout() == 0, "service_connection_leaked")
        check(all(driver.closed for driver in self.invalidated), "invalidated_driver_not_closed")
        check(self.one("SELECT count(*) FROM pg_stat_activity WHERE datname=%s AND usename=%s AND "
                       "(state LIKE 'idle in transaction%%' OR wait_event_type='Lock')", (self.p["database"], self.p["service"])) == 0,
              "transaction_or_blocker_leaked")
        counts = {table: self.one("SELECT count(*) FROM " + table) for table in self.launcher.OWNED}
        check(all(counts[t] <= bound for t, bound in zip(self.launcher.OWNED, (64, 256, 512))), "aggregate_row_budget_exceeded")
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
                 ("rollback_failure", lambda: self.cleanup_failure(False)), ("close_failure", lambda: self.cleanup_failure(True))]
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
    try:
        data = sys.stdin.buffer.read(16385)
        check(len(data) <= 16384, "worker_input_limit")
        payload = json.loads(data)
        validate_payload(payload)
        runtime_guard(payload)
        backend = ROOT / "backend"
        # -I -S avoids site initialization/.pth execution; existing packages only.
        sys.path[:0] = [str(backend), str(backend / ".venv/Lib/site-packages")]
        PostgreSQLAcceptance(payload).run()
        return 0
    except BaseException as error:
        emit("failure", code=str(error) if isinstance(error, AcceptanceFailure) else type(error).__name__)
        return 1


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
    import_guard_counts = dict(attempts)
    valid = ["--execute", "--docker-context", "desktop-linux", "--expected-context-endpoint", "npipe:////./pipe/dockerDesktopLinuxEngine",
             "--image", "pgvector/pgvector@sha256:" + "a" * 64, "--expected-head", module.BASELINE,
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

    class OfflineChecks(unittest.TestCase):
        def test_01_positive_guards(self):
            for name in ("app.database", "psycopg", "sqlalchemy", "alembic", "dotenv", "jwt", "sqlite3"):
                with self.subTest(import_name=name), self.assertRaises(AcceptanceFailure):
                    __import__(name)
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
            for args in (["--execute"], valid[:-2], valid[:-1] + ["bad"], [x if x != module.BASELINE else "0" * 40 for x in valid]):
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
            self.assertEqual(CHAIN[-3:], ("d7b834408ba8", "f94c6f41e0cb", "a7c730103001"))
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
            self.assertEqual(len(module.CASE_NAMES), 28)
            self.assertEqual(len(set(module.CASE_NAMES)), 28)
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

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(OfflineChecks)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps({"offline_only": True, "tests": result.testsRun, "failures": len(result.failures),
                      "errors": len(result.errors), "skips": len(result.skipped), "positive_guard_hits": attempts,
                      "postgres_cases": "NOT_RUN"}, sort_keys=True))
    return 0 if result.wasSuccessful() and not result.skipped else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="Run only new, guarded fake-adapter/refusal checks")
    args = parser.parse_args(argv)
    if not args.offline:
        print("REFUSED: choose --offline; real acceptance is launched only by the reviewed opt-in launcher")
        return 2
    return offline_checks()


if __name__ == "__main__":
    raise SystemExit(main())
