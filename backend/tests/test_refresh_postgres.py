"""Opt-in disposable PostgreSQL tests. Never use the development database.

FINLENS_REFRESH_TEST_DSN must name the isolated localhost test instance/database.
Each case creates its own UUID-named database and removes only that database.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
import psycopg
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

from app import main
from app.database import Base
from app.models import Company, FinancialFact, FilingChunk, FilingPublication, CompanyRefreshState, RefreshAttempt
from app.refresh_service import COORDINATOR_LOCK, refresh
from app.refresh_contracts import RefreshRequest
from app.sec_importer import merge_company_facts
from test_data_refresh import facts, CIK, run, count


@pytest.fixture
def isolated_database():
    dsn = os.getenv("FINLENS_REFRESH_TEST_DSN", "")
    if not dsn:
        pytest.skip("Disposable PostgreSQL opt-in is not configured")
    url = make_url(dsn)
    if url.host != "127.0.0.1" or url.port != 55439 or url.database != "finlens_refresh_test":
        pytest.fail("Refusing a DSN outside the dedicated disposable refresh test instance")
    name = "finlens_refresh_test_" + uuid4().hex
    assert re.fullmatch(r"finlens_refresh_test_[0-9a-f]{32}", name)
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.exec_driver_sql(f'CREATE DATABASE "{name}"')
    engine = create_engine(url.set(database=name), pool_pre_ping=True)
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE EXTENSION vector")
    try:
        yield engine
    finally:
        engine.dispose()
        with admin.connect() as connection:
            connection.exec_driver_sql(f'DROP DATABASE "{name}" WITH (FORCE)')
        admin.dispose()


@pytest.fixture
def pg_factory(isolated_database, monkeypatch):
    Base.metadata.create_all(isolated_database)
    factory = sessionmaker(bind=isolated_database, autoflush=False, autocommit=False)
    with factory() as session, session.begin():
        session.add(Company(cik=CIK, ticker="AAPL", name="Apple Inc.", exchange="NASDAQ"))
    monkeypatch.setattr(main, "SessionLocal", factory)
    monkeypatch.setattr("app.sec_client._sec_get", lambda *a: pytest.fail("Forbidden live SEC"))
    monkeypatch.setattr("app.answer_service._get_openai_client", lambda: pytest.fail("Forbidden OpenAI"))
    return factory


def test_postgres_concurrent_supported_merges_one_observation_one_version(pg_factory):
    def insert(_):
        with pg_factory() as session, session.begin():
            return merge_company_facts(session, CIK, facts())["facts_inserted"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(insert, range(2))) == [0, 1]
    with pg_factory() as session:
        assert len(list(session.scalars(select(FinancialFact)))) == 1
        assert session.get(CompanyRefreshState, CIK).data_version == 1
        assert len(list(session.scalars(select(RefreshAttempt)))) == 1


def test_postgres_cross_process_admission_lock_blocks_without_source_access(pg_factory):
    # A distinct connection simulates another process; no Python local lock held.
    with pg_factory.kw["bind"].connect() as connection:
        connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": COORDINATOR_LOCK})
        try:
            result = refresh(pg_factory, RefreshRequest(tickers=["AAPL"], stream="facts"), facts_loader=lambda cik: pytest.fail("Must not fetch"))
            assert result["error"] == "refresh_busy_or_lock_lost"
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": COORDINATOR_LOCK})


def test_postgres_repeatable_read_pins_answer_and_version(pg_factory):
    request = RefreshRequest(tickers=["AAPL"], stream="facts")
    refresh(pg_factory, request, facts_loader=facts)
    fired = []
    def publish_between_reads(conn, cursor, statement, params, context, many):
        if not fired and statement.startswith("SELECT company_refresh_state.data_version"):
            fired.append(True)
            result = refresh(pg_factory, request, facts_loader=lambda cik: facts(cik, "110", filed="2026-02-01", accession="0000320193-26-000002"))
            assert result["companies"][0]["version_after"] == 2
    event.listen(pg_factory.kw["bind"], "after_cursor_execute", publish_between_reads)
    try:
        response = TestClient(main.app).post('/companies/AAPL/research-answer', json={"question": "2024 revenue"})
    finally:
        event.remove(pg_factory.kw["bind"], "after_cursor_execute", publish_between_reads)
    assert fired and response.status_code == 200
    assert response.headers["X-FinLens-Data-Version"] == "1"
    assert response.json()["observation"]["value"] == "100.0000"


def test_additive_migration_preserves_original_rows_and_is_alembic_clean(isolated_database):
    env = dict(os.environ, DATABASE_URL=isolated_database.url.render_as_string(hide_password=False))
    cwd = Path(__file__).resolve().parents[1]
    def alembic(*args):
        result = subprocess.run([sys.executable, '-B', '-m', 'alembic', *args], cwd=cwd, env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        return result
    alembic('upgrade', 'd7b834408ba8')
    with isolated_database.begin() as connection:
        connection.execute(text("INSERT INTO companies (ticker,name,cik,exchange) VALUES ('AAPL','Original fixture',:cik,'NASDAQ')"), {"cik": CIK})
        connection.execute(text("INSERT INTO financial_facts (company_cik,metric,value,unit,source,created_at) VALUES (:cik,'Revenues',100,'USD','Original fixture',CURRENT_TIMESTAMP)"), {"cik": CIK})
        connection.execute(text("""INSERT INTO filing_chunks
            (company_cik,accession_number,form,filed,filename,chunk_index,chunk_id,text,start_char,end_char,sec_url,embedding,created_at)
            VALUES (:cik,'0000320193-25-000001','10-Q','2025-05-01','fixture.htm',0,'chunk_0000',
            'Original evidence',0,17,:url,CAST(:vector AS vector),CURRENT_TIMESTAMP)"""),
            {"cik": CIK, "url": "https://www.sec.gov/Archives/edgar/data/320193/000032019325000001/0000320193-25-000001-index.html",
             "vector": "[" + ",".join(["0.5"]*384) + "]"})
        before = {t: list(connection.exec_driver_sql(f"SELECT row_to_json(x)::text FROM (SELECT * FROM {t} ORDER BY id) x").scalars()) for t in ('companies', 'financial_facts', 'filing_chunks')}
    alembic('upgrade', 'head')
    alembic('check')
    with isolated_database.connect() as connection:
        after = {t: list(connection.exec_driver_sql(f"SELECT row_to_json(x)::text FROM (SELECT * FROM {t} ORDER BY id) x").scalars()) for t in before}
        assert before == after
        assert connection.scalar(text("SELECT count(*) FROM company_refresh_state")) == 0
    # Version-zero bootstrap publishes metadata without inventing source checks.
    from app.refresh_service import bootstrap_publications
    from app.freshness_service import freshness
    factory = sessionmaker(bind=isolated_database)
    with factory() as session, session.begin():
        assert bootstrap_publications(session)["registered"] == 1
    with factory() as session:
        state = freshness(session, "AAPL")
        assert state.status == "unknown" and state.data_version == 0
        assert state.latest_indexed_filing.accession_number == "0000320193-25-000001"
        assert state.evidence.last_checked_at is None
    with isolated_database.connect() as connection:
        assert before == {t: list(connection.exec_driver_sql(f"SELECT row_to_json(x)::text FROM (SELECT * FROM {t} ORDER BY id) x").scalars()) for t in before}
    # No destructive downgrade is needed to validate this additive migration.


@pytest.mark.parametrize("phase", ["publication_begin", "before_commit"])
def test_displaced_coordinator_connection_cannot_publish(pg_factory, phase):
    """Terminate A after its probe; B owns admission while A tries to commit."""
    engine = pg_factory.kw["bind"]
    holder = engine.connect()
    holder.execute(text("SET lock_timeout = '5s'")); holder.commit()
    locks, displaced = [], []
    def displace():
        pid = holder.scalar(text("SELECT pid FROM pg_locks WHERE locktype='advisory' AND database=(SELECT oid FROM pg_database WHERE datname=current_database()) AND classid=:hi AND objid=:lo AND granted"),
                            {"hi": COORDINATOR_LOCK >> 32, "lo": COORDINATOR_LOCK & 0xffffffff})
        assert pid is not None
        assert holder.scalar(text("SELECT pg_terminate_backend(:pid)"), {"pid": pid})
        holder.execute(text("SELECT pg_advisory_lock(:key)"), {"key": COORDINATOR_LOCK})
        holder.commit()
        displaced.append(pid)
    def before_sql(conn, cursor, statement, params, context, many):
        if "pg_advisory_xact_lock" in statement:
            locks.append(True)
            if phase == "publication_begin" and len(locks) == 2:
                displace()
    def before_commit(session):
        if phase == "before_commit" and not displaced and any(
            isinstance(a, RefreshAttempt) and a.status == "updated" for a in session.identity_map.values()
        ):
            session.flush()
            # Rows and version exist inside A's transaction, but are not committed.
            assert session.scalar(select(FinancialFact.id)) is not None
            displace()
    event.listen(engine, "before_cursor_execute", before_sql)
    event.listen(Session, "before_commit", before_commit)
    try:
        report = run(pg_factory)
        assert displaced
        assert count(pg_factory, FinancialFact) == 0
        with pg_factory() as s:
            assert s.get(CompanyRefreshState, CIK).data_version == 0
            assert not list(s.scalars(select(RefreshAttempt).where(RefreshAttempt.published_version.is_not(None))))
        assert report["error"] == "refresh_busy_or_lock_lost"
        blocked_source = []
        blocked = refresh(pg_factory, RefreshRequest(tickers=["AAPL"], stream="facts"),
                          facts_loader=lambda cik: blocked_source.append(cik))
        assert blocked["error"] == "refresh_busy_or_lock_lost" and not blocked_source
    finally:
        event.remove(engine, "before_cursor_execute", before_sql)
        event.remove(Session, "before_commit", before_commit)
        holder.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": COORDINATOR_LOCK})
        holder.commit(); holder.close()
    # A new worker recovers the abandoned attempt and publishes exactly once.
    assert run(pg_factory)["companies"][0]["status"] == "updated"
    assert run(pg_factory)["companies"][0]["status"] == "no_change"
    assert count(pg_factory, FinancialFact) == 1
    with pg_factory() as s:
        assert s.get(CompanyRefreshState, CIK).data_version == 1
        assert len(list(s.scalars(select(RefreshAttempt).where(RefreshAttempt.published_version == 1)))) == 1


@pytest.mark.parametrize("stream", ["facts", "evidence"])
@pytest.mark.parametrize("phase", ["before_commit", "after_commit"])
def test_publication_commit_failure_reconciles_durable_truth(pg_factory, stream, phase):
    fired, publication_connections, reconciliation_connections = [], [], []
    def fail(session):
        if not fired and any(isinstance(a, RefreshAttempt) and a.status == "updated" for a in session.identity_map.values()):
            fired.append(True)
            raise OSError("private simulated commit acknowledgment error")
    def remember(session):
        if any(isinstance(a, RefreshAttempt) and a.status == "updated" for a in session.identity_map.values()):
            publication_connections.append(session.connection().scalar(text("SELECT pg_backend_pid()")))
    def observe(conn, cursor, statement, params, context, many):
        if fired and statement == "SET TRANSACTION READ ONLY":
            reconciliation_connections.append(conn.scalar(text("SELECT pg_backend_pid()")))
    event.listen(Session, "before_commit", remember)
    event.listen(Session, phase, fail)
    event.listen(pg_factory.kw["bind"], "before_cursor_execute", observe)
    try:
        report = run(pg_factory, stream)
    finally:
        event.remove(Session, "before_commit", remember)
        event.remove(Session, phase, fail)
        event.remove(pg_factory.kw["bind"], "before_cursor_execute", observe)
    assert fired
    row = report["companies"][0]
    committed = phase == "after_commit"
    assert row["status"] == ("updated" if committed else "failed")
    assert row["commit_outcome"] == ("committed" if committed else "rolled_back")
    assert row["version_after"] == int(committed)
    assert row["facts_inserted"] == int(committed and stream == "facts")
    assert row["filings_published"] == int(committed and stream == "evidence")
    assert all(n == (int(committed) if metric == "Revenues" else 0) for metric, n in row["inserted_by_metric"].items())
    assert reconciliation_connections and publication_connections
    assert reconciliation_connections[0] != publication_connections[0]
    with pg_factory() as s:
        attempt = s.scalar(select(RefreshAttempt).where(RefreshAttempt.run_id == report["run_id"]))
        assert attempt.status == row["status"] and attempt.details == row
        assert s.get(CompanyRefreshState, CIK).data_version == int(committed)
    assert "private simulated" not in str(report)
    retry = run(pg_factory, stream)["companies"][0]
    assert retry["status"] == ("no_change" if committed else "updated")
    with pg_factory() as s:
        assert s.get(CompanyRefreshState, CIK).data_version == 1


def test_unknown_commit_outcome_has_null_counters_and_stops_later_stream(pg_factory, monkeypatch):
    from app import refresh_service as service
    fired = []
    def lost_ack(session):
        if not fired and any(isinstance(a, RefreshAttempt) and a.status == "updated" for a in session.identity_map.values()):
            fired.append(True)
            raise OSError("simulated lost acknowledgment")
    original = service.reconcile_publication
    monkeypatch.setattr(service, "reconcile_publication", lambda *args: (_ for _ in ()).throw(ConnectionError("unreachable")))
    calls = []
    event.listen(Session, "after_commit", lost_ack)
    try:
        report = run(pg_factory, "both", inventory_loader=lambda cik: calls.append(cik))
    finally:
        event.remove(Session, "after_commit", lost_ack)
        monkeypatch.setattr(service, "reconcile_publication", original)
    row = report["companies"][0]
    assert row["status"] == row["commit_outcome"] == "indeterminate"
    assert row["facts_inserted"] is row["filings_published"] is row["version_after"] is None
    assert all(n is None for n in row["inserted_by_metric"].values())
    assert report["error"] == "commit_outcome_indeterminate_use_database_ledger"
    assert not calls and report["not_processed"] == [{"ticker": "AAPL", "stream": "evidence"}]
    with pg_factory() as s:
        attempt = s.scalar(select(RefreshAttempt).where(RefreshAttempt.run_id == report["run_id"]))
        assert attempt.status == "updated" and attempt.details["facts_inserted"] == 1
        assert s.get(CompanyRefreshState, CIK).data_version == 1
    assert run(pg_factory)["companies"][0]["status"] == "no_change"


def test_nested_admission_probe_cannot_commit_a_publication_early(pg_factory):
    from app.refresh_service import coordinator, publication_session
    with pytest.raises(RuntimeError, match="rollback fixture"):
        with coordinator(pg_factory) as owned:
            with publication_session(pg_factory, owned) as session, session.begin():
                merge_company_facts(session, CIK, facts(), publish=False)
                with coordinator(pg_factory):
                    assert session.scalar(select(FinancialFact.id)) is not None
                raise RuntimeError("rollback fixture")
    assert count(pg_factory, FinancialFact) == 0


@pytest.mark.parametrize("stream", ["facts", "evidence"])
@pytest.mark.parametrize("phase", ["before_io", "after_io"])
def test_failed_rollback_discards_physical_owner_and_recovers_once(pg_factory, monkeypatch, stream, phase):
    """The actual DBAPI rollback fails, not a mocked refresh result."""
    assert pg_factory.kw["autoflush"] is False
    engine = pg_factory.kw["bind"]
    assert engine.pool._pre_ping is True
    original_rollback = engine.dialect.do_rollback
    armed, owner, invalidated, checked_out = [], [], [], []

    def fail_commit(session):
        if not owner and any(isinstance(a, RefreshAttempt) and a.status == "updated" for a in session.identity_map.values()):
            connection = session.connection()
            driver = connection.connection.driver_connection
            owner.append((driver, driver.info.backend_pid))
            # Flush already happened in the real merge/persist helper. Do not
            # flush pending version/ledger changes here: match the review case.
            model = FinancialFact if stream == "facts" else FilingChunk
            assert session.scalar(select(model.id)) is not None
            armed.append(True)
            raise OSError("injected private precommit failure")

    def fail_rollback(driver):
        if armed:
            armed.clear()
            if phase == "after_io":
                original_rollback(driver)
            raise psycopg.OperationalError("injected private rollback failure")
        return original_rollback(driver)

    def on_invalidate(driver, record, exception):
        invalidated.append(driver)

    def on_checkout(driver, record, proxy):
        checked_out.append(driver)

    monkeypatch.setattr(engine.dialect, "do_rollback", fail_rollback)
    event.listen(Session, "before_commit", fail_commit)
    event.listen(engine, "invalidate", on_invalidate)
    event.listen(engine, "checkout", on_checkout)
    try:
        report = run(pg_factory, stream)
        row = report["companies"][0]
        assert row["status"] == "failed" and row["commit_outcome"] == "rolled_back"
        assert row["facts_inserted"] == row["filings_published"] == row["version_after"] == 0
        assert all(n == 0 for n in row["inserted_by_metric"].values())
        assert row["would_insert"] == 1  # Explicitly provisional diagnostics survive.
        assert report["error"] == "refresh_busy_or_lock_lost"
        assert "private" not in str(report)
        assert owner and owner[0][0].closed and owner[0][0] in invalidated
        json_report = json.dumps(report)
        assert '"rolled_back"' in json_report
        assert count(pg_factory, FinancialFact) == count(pg_factory, FilingChunk) == count(pg_factory, FilingPublication) == 0
        with pg_factory() as session:
            state = session.get(CompanyRefreshState, CIK)
            assert state.data_version == state.facts_version == state.evidence_version == 0
            assert not list(session.scalars(select(RefreshAttempt).where(RefreshAttempt.published_version.is_not(None))))
            assert session.scalar(text("SELECT count(*) FROM pg_stat_activity WHERE pid=:pid"), {"pid": owner[0][1]}) == 0
        # A distinct physical session can now own admission; no stale lock leaks.
        with engine.connect() as contender:
            assert contender.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": COORDINATOR_LOCK})
            contender.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": COORDINATOR_LOCK})
        assert run(pg_factory, stream)["companies"][0]["status"] == "updated"
        assert run(pg_factory, stream)["companies"][0]["status"] == "no_change"
        assert count(pg_factory, FinancialFact if stream == "facts" else FilingPublication) == 1
        with pg_factory() as session:
            state = session.get(CompanyRefreshState, CIK)
            assert state.data_version == 1
            events = list(session.scalars(select(RefreshAttempt).where(RefreshAttempt.published_version.is_not(None))))
            assert len(events) == 1 and events[0].published_version == 1
            assert any(a.status == "interrupted" for a in session.scalars(select(RefreshAttempt)))
        assert sum(driver is owner[0][0] for driver in checked_out) == 1
    finally:
        event.remove(Session, "before_commit", fail_commit)
        event.remove(engine, "invalidate", on_invalidate)
        event.remove(engine, "checkout", on_checkout)


def test_coordinator_cleanup_never_commits_a_failed_external_session_rollback(pg_factory, monkeypatch):
    """Cleanup itself must be safe even when Session has lost transaction state."""
    from app.refresh_service import coordinator
    engine = pg_factory.kw["bind"]
    original = engine.dialect.do_rollback
    armed, owner = [], []

    def fail_commit(session):
        if armed:
            raise OSError("injected before commit")

    def fail_rollback(driver):
        if armed:
            armed.clear()
            raise psycopg.OperationalError("injected before rollback I/O")
        return original(driver)

    monkeypatch.setattr(engine.dialect, "do_rollback", fail_rollback)
    event.listen(Session, "before_commit", fail_commit)
    try:
        with coordinator(pg_factory) as owned:
            owner.append(owned.connection.connection.driver_connection)
            with pytest.raises(DBAPIError):
                with pg_factory(bind=owned.connection) as session, session.begin():
                    merge_company_facts(session, CIK, facts(), publish=False)
                    armed.append(True)
            # SQLAlchemy thinks this ended, but PostgreSQL still has the INSERT.
            assert not owned.connection.in_transaction()
    finally:
        event.remove(Session, "before_commit", fail_commit)
    assert count(pg_factory, FinancialFact) == 0
    assert owner[0].closed
    assert run(pg_factory)["companies"][0]["facts_inserted"] == 1
    assert run(pg_factory)["companies"][0]["facts_inserted"] == 0


@pytest.mark.parametrize("stream", ["facts", "evidence"])
def test_driver_commit_lost_ack_recovers_durable_ledger_on_new_connection(pg_factory, monkeypatch, stream):
    engine = pg_factory.kw["bind"]
    original = engine.dialect.do_commit
    owner, armed, reconciled = [], [], []

    def remember(session):
        if not owner and any(isinstance(a, RefreshAttempt) and a.status == "updated" for a in session.identity_map.values()):
            driver = session.connection().connection.driver_connection
            owner.append((driver, driver.info.backend_pid))
            armed.append(True)

    def lost_ack(driver):
        original(driver)  # PostgreSQL committed all rows/version/ledger.
        if armed:
            armed.clear()
            raise psycopg.OperationalError("injected lost commit acknowledgment")

    def observe(connection, cursor, statement, params, context, many):
        if owner and statement == "SET TRANSACTION READ ONLY":
            reconciled.append(connection.connection.driver_connection.info.backend_pid)

    monkeypatch.setattr(engine.dialect, "do_commit", lost_ack)
    event.listen(Session, "before_commit", remember)
    event.listen(engine, "before_cursor_execute", observe)
    try:
        report = run(pg_factory, stream)
    finally:
        event.remove(Session, "before_commit", remember)
        event.remove(engine, "before_cursor_execute", observe)
    row = report["companies"][0]
    assert report["error"] is None
    assert row["status"] == "updated" and row["commit_outcome"] == "committed"
    assert row["facts_inserted"] == int(stream == "facts")
    assert row["filings_published"] == int(stream == "evidence")
    assert row["version_after"] == 1
    assert owner[0][0].closed and reconciled and reconciled[0] != owner[0][1]
    with pg_factory() as session:
        attempt = session.scalar(select(RefreshAttempt).where(RefreshAttempt.run_id == report["run_id"]))
        assert attempt.status == "updated" and attempt.details == row
        assert session.get(CompanyRefreshState, CIK).data_version == 1
    assert run(pg_factory, stream)["companies"][0]["status"] == "no_change"
