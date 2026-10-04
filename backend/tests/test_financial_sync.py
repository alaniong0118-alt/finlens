"""Source identity and recovery with real ORM transactions; no live SEC/AI."""
from copy import deepcopy
from decimal import Decimal
import json
from unittest.mock import Mock
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models import Company, FinancialFact, FilingChunk
from app import financial_sync_service as service, sec_importer as importer
from app.financial_metrics_service import load_financial_metrics

CIKS = {"AAPL": "0000320193", "MSFT": "0000789019", "XOM": "0002115436"}


def payload(cik=CIKS["AAPL"], concept="Revenues", observations=None):
    records = observations if observations is not None else [
        {"start": "2025-01-01", "end": "2025-03-31", "val": 100,
         "accn": "0000320193-25-000001", "filed": "2025-05-01", "form": "10-Q",
         "fy": 2025, "fp": "Q1", "frame": "CY2025Q1"}]
    return {"cik": int(cik), "entityName": "Synthetic fixture issuer",
            "facts": {"us-gaap": {concept: {"units": {"USD": records}}}}}


@pytest.fixture
def factory(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as session:
        session.add_all(Company(ticker=ticker, cik=cik, name=ticker, exchange="NYSE") for ticker, cik in CIKS.items())
        session.add(FilingChunk(company_cik=CIKS["AAPL"], accession_number="0000320193-25-000001",
                                form="10-Q", filename="fixture.htm", chunk_index=0, chunk_id="chunk_0000",
                                text="Fixture evidence", start_char=0, end_char=16,
                                sec_url="https://www.sec.gov/fixture", embedding=[0.5]*384))
        session.commit()
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setattr("app.sec_client._sec_get", Mock(side_effect=AssertionError("Forbidden live SEC")))
    monkeypatch.setattr("app.embedding_service.embed_texts", Mock(side_effect=AssertionError("Forbidden embedding")))
    monkeypatch.setattr("app.answer_service._get_openai_client", Mock(side_effect=AssertionError("Forbidden OpenAI")))
    monkeypatch.setattr(service, "get_company_facts", lambda cik: payload(cik))
    monkeypatch.setattr(importer, "SessionLocal", factory)
    yield factory
    engine.dispose()


def rows(factory, model=FinancialFact):
    with factory() as session:
        return [tuple(str(getattr(row, col.name)) for col in model.__table__.columns)
                for row in session.scalars(select(model).order_by(model.id))]


def test_insert_preserve_noop_and_never_touch_chunks(factory):
    chunk_before = rows(factory, FilingChunk)
    first = service.sync_catalog(factory, ["AAPL"])
    before = rows(factory)
    second = service.sync_catalog(factory, ["AAPL"])
    assert first["facts_before"] == 0 and first["facts_inserted"] == first["facts_after"] == 1
    assert first["updated"] == 1 and second["already_current"] == 1 and second["facts_inserted"] == 0
    assert rows(factory) == before and rows(factory, FilingChunk) == chunk_before
    assert first["normalized_coverage"]["quarter"]["revenue"]["available"] == 1
    assert first["normalized_coverage"]["source_metric_companies"]["Revenues"] == 1


@pytest.mark.parametrize("dimension,changed", [("accn", "0000320193-25-000002"), ("filed", "2025-05-02"),
    ("form", "10-Q/A"), ("val", 101), ("frame", None), ("fy", 2026), ("fp", "Q2")])
def test_source_observation_dimensions_remain_distinct(factory, dimension, changed):
    source = payload()
    record = source["facts"]["us-gaap"]["Revenues"]["units"]["USD"][0]
    source["facts"]["us-gaap"]["Revenues"]["units"]["USD"] += [{**record, dimension: changed}, deepcopy(record)]
    with factory() as session, session.begin():
        result = importer.merge_company_facts(session, CIKS["AAPL"], source)
    assert result["source_observations"] == result["facts_inserted"] == 2
    with factory() as session, session.begin():
        assert importer.merge_company_facts(session, CIKS["AAPL"], source)["facts_inserted"] == 0


def test_concepts_and_later_restatements_reach_item6_selector(factory, monkeypatch):
    source = payload()
    record = source["facts"]["us-gaap"]["Revenues"]["units"]["USD"][0]
    source["facts"]["us-gaap"]["Revenues"]["units"]["USD"].append({**record, "val": 110, "filed": "2025-06-01", "accn": "0000320193-25-000003"})
    source["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"] = {"units": {"USD": [{**record, "val": 60, "filed": "2025-07-01", "accn": "0000320193-25-000004"}]}}
    monkeypatch.setattr(service, "get_company_facts", lambda cik: source)
    assert service.sync_catalog(factory, ["AAPL"])["facts_inserted"] == 3
    with factory() as session:
        point = load_financial_metrics(session, "AAPL").summary().metrics["revenue"]
        assert point.value == 110 and point.revenue_basis == "total_revenue"
        assert len(point.alternatives) == 2


def test_preexisting_unrelated_and_missing_from_source_facts_preserved(factory, monkeypatch):
    service.sync_catalog(factory)
    before = rows(factory)
    source = payload(observations=[{**payload()["facts"]["us-gaap"]["Revenues"]["units"]["USD"][0], "val": 200}])
    monkeypatch.setattr(service, "get_company_facts", lambda cik: source)
    result = service.sync_catalog(factory, ["AAPL"])
    assert result["facts_inserted"] == 1 and rows(factory)[:len(before)] == before


def test_dry_run_and_subset(factory):
    before = rows(factory), rows(factory, FilingChunk)
    result = service.sync_catalog(factory, ["aapl", "AAPL"], dry_run=True)
    assert result["companies_requested"] == ["AAPL"]
    assert result["would_insert"] == 1 and result["facts_inserted"] == result["facts_after"] == 0
    assert result["companies"][0]["status"] == "would_update"
    assert before == (rows(factory), rows(factory, FilingChunk))


def test_unknown_ticker_rejected_before_network(factory, monkeypatch):
    network = Mock(side_effect=AssertionError("No acquisition for bad selection"))
    monkeypatch.setattr(service, "get_company_facts", network)
    result = service.sync_catalog(factory, ["MISSING"])
    assert result["catalog_error"] == "unknown_or_empty_ticker_selection"
    network.assert_not_called()
    assert rows(factory) == []


def test_flush_failure_atomic_rollback_and_later_company_continues(factory):
    def damage(session, *_):
        first = next((f for f in session.new if isinstance(f, FinancialFact) and f.company_cik == CIKS["AAPL"]), None)
        if first:
            first.unit = None  # Real NOT NULL IntegrityError, not a mocked merge.
    event.listen(Session, "before_flush", damage)
    try:
        result = service.sync_catalog(factory, ["AAPL", "MSFT"])
    finally:
        event.remove(Session, "before_flush", damage)
    assert result["failed"] == result["updated"] == 1 and result["catalog_error"] is None
    assert result["facts_inserted"] == result["facts_after"] == 1
    assert result["companies"][0]["facts_after"] == 0
    assert all(count == 0 for count in result["companies"][0]["inserted_by_metric"].values())
    with factory() as session:
        assert [f.company_cik for f in session.scalars(select(FinancialFact))] == [CIKS["MSFT"]]
    retry = service.sync_catalog(factory, ["AAPL", "MSFT"])
    assert retry["updated"] == retry["already_current"] == 1


def test_explicit_rollback_restores_same_session(factory):
    with factory() as session:
        session.add(FinancialFact(company_cik=CIKS["AAPL"], metric="Revenues", unit=None, value=100, source="fixture"))
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()
        importer.merge_company_facts(session, CIKS["AAPL"], payload())
        session.commit()
        assert session.scalar(select(FinancialFact.value)) == 100


def test_commit_failure_reports_zero_inserts_and_next_company_continues(factory, tmp_path):
    from scripts.sync_financial_facts import write_report

    flushed_ids = []
    destination = tmp_path / "sync.json"

    def fail_after_flush(session):
        fact_id = session.scalar(select(FinancialFact.id).where(
            FinancialFact.company_cik == CIKS["AAPL"]))
        if fact_id is not None:
            flushed_ids.append(fact_id)
            raise RuntimeError("Simulated commit failure after successful flush")

    event.listen(Session, "before_commit", fail_after_flush)
    try:
        result = service.sync_catalog(factory, ["AAPL", "MSFT"],
                                      on_progress=lambda report: write_report(destination, report))
    finally:
        event.remove(Session, "before_commit", fail_after_flush)

    assert len(flushed_ids) == 1  # The failed issuer reached commit with a persisted-in-transaction row.
    failed, healthy = result["companies"]
    assert failed["status"] == "failed"
    assert failed["facts_inserted"] == failed["facts_after"] == 0
    assert set(failed["inserted_by_metric"]) == set(importer.METRIC_SOURCES)
    assert all(count == 0 for count in failed["inserted_by_metric"].values())
    assert healthy["status"] == "updated" and healthy["facts_inserted"] == 1
    assert healthy["inserted_by_metric"]["Revenues"] == 1
    with factory() as session:
        assert session.scalar(select(FinancialFact.id).where(
            FinancialFact.company_cik == CIKS["AAPL"])) is None
        assert [fact.company_cik for fact in session.scalars(select(FinancialFact))] == [CIKS["MSFT"]]
    assert result["failed"] == result["updated"] == 1
    assert result["facts_inserted"] == result["facts_after"] == 1
    assert result["catalog_error"] is None and result["not_processed"] == []
    assert result["finished_at"] and "normalized_coverage" in result
    assert json.loads(destination.read_text(encoding="utf-8")) == result


def test_source_failure_is_sanitized_and_other_company_proceeds(factory, monkeypatch):
    def fetch(cik):
        if cik == CIKS["AAPL"]:
            raise RuntimeError("private contact/password/provider body must never appear")
        return payload(cik)
    monkeypatch.setattr(service, "get_company_facts", fetch)
    result = service.sync_catalog(factory, ["AAPL", "MSFT"])
    assert result["failed"] == result["updated"] == 1
    assert "private" not in json.dumps(result)


def test_current_xom_identity_not_predecessor(factory, monkeypatch):
    fetch = Mock(return_value=payload("0000034088"))
    monkeypatch.setattr(service, "get_company_facts", fetch)
    result = service.sync_catalog(factory, ["XOM"])
    fetch.assert_called_once_with(CIKS["XOM"])
    assert result["companies"][0]["error"] == "company_facts_cik_mismatch" and rows(factory) == []


def test_interrupt_keeps_committed_company_and_resume_noop(factory, monkeypatch):
    def fetch(cik):
        if cik == CIKS["MSFT"]:
            raise KeyboardInterrupt()
        return payload(cik)
    monkeypatch.setattr(service, "get_company_facts", fetch)
    result = service.sync_catalog(factory, ["AAPL", "MSFT"])
    assert result["interrupted"] and result["not_processed"] == ["MSFT"] and result["facts_inserted"] == 1
    monkeypatch.setattr(service, "get_company_facts", lambda cik: payload(cik))
    again = service.sync_catalog(factory, ["AAPL", "MSFT"])
    assert again["updated"] == again["already_current"] == 1 and again["facts_after"] == 2


@pytest.mark.parametrize("value", ["NaN", "1.00001", "100000000000000000000"])
def test_unrepresentable_value_fails_without_mutation(factory, value):
    source = payload()
    source["facts"]["us-gaap"]["Revenues"]["units"]["USD"][0]["val"] = value
    with factory() as session, pytest.raises(importer.FinancialSyncError):
        importer.merge_company_facts(session, CIKS["AAPL"], source)
    assert rows(factory) == []


def test_no_source_is_honest_and_preserves_existing(factory, monkeypatch):
    service.sync_catalog(factory, ["AAPL"])
    before = rows(factory)
    monkeypatch.setattr(service, "get_company_facts", lambda cik: payload(cik, observations=[]))
    result = service.sync_catalog(factory, ["AAPL"])
    assert result["no_usable_source"] == 1 and rows(factory) == before


def test_global_outage_stops_and_preserves_report(factory, monkeypatch):
    monkeypatch.setattr(service, "get_company_facts", Mock(side_effect=RuntimeError("fixture failure")))
    original = factory
    calls = 0
    def failing_factory():
        nonlocal calls
        calls += 1
        if calls > 1:
            raise OperationalError("SELECT 1", {}, RuntimeError("private database URL"))
        return original()
    result = service.sync_catalog(failing_factory)
    assert result["catalog_error"] == "database_unavailable" and len(result["companies"]) == 1
    assert result["not_processed"] == ["MSFT", "XOM"]
    assert "private" not in json.dumps(result)


def test_legacy_import_entrypoints_insert_only(factory, monkeypatch):
    monkeypatch.setattr(importer, "get_company_facts", lambda cik: payload(cik))
    assert importer.import_metric(CIKS["AAPL"], payload(), "Revenues") == 1
    before = rows(factory)
    assert importer.import_company(CIKS["AAPL"])["Revenues"] == 0
    assert rows(factory) == before


def test_cli_atomic_report_options_and_exit(factory, monkeypatch, tmp_path, capsys):
    from app import database
    from scripts import sync_financial_facts as cli, setup_demo
    monkeypatch.setattr(database, "SessionLocal", factory)
    monkeypatch.setattr(setup_demo, "check_schema", lambda session: None)
    monkeypatch.setattr(cli, "BACKEND_ROOT", tmp_path)
    destination = tmp_path / "reports/sync.json"
    assert cli.main(["--ticker", "AAPL", "--dry-run", "--report", str(destination)]) == 0
    report = json.loads(destination.read_text())
    assert report["would_insert"] == 1 and report["facts_inserted"] == 0
    assert cli.main(["--ticker", "AAPL", "--report", str(destination)]) == 0
    assert cli.main(["--ticker", "MISSING", "--report", str(destination)]) == 1
    assert not list(destination.parent.glob("*.tmp"))
    assert cli.main(["--report", str(tmp_path / ".env")]) == 1
    assert not (tmp_path / ".env").exists()
    assert "unknown_or_empty_ticker_selection" in capsys.readouterr().err


def test_existing_other_report_cannot_be_overwritten(factory, monkeypatch, tmp_path):
    from scripts import sync_financial_facts as cli
    monkeypatch.setattr(cli, "BACKEND_ROOT", tmp_path)
    path = tmp_path / "reports/baseline.json"
    path.parent.mkdir()
    path.write_text('{"baseline": true}')
    assert cli.main(["--report", str(path)]) == 1
    assert path.read_text() == '{"baseline": true}'


def test_companyfacts_json_keeps_decimal_before_storage(monkeypatch):
    from app import sec_client
    response = httpx.Response(200, text='{"cik":320193,"value":0.1234567890123456789}')
    monkeypatch.setattr(sec_client, "_sec_get", lambda url: response)
    assert sec_client.get_company_facts(CIKS["AAPL"])["value"] == Decimal("0.1234567890123456789")


def test_merge_rejects_stale_snapshot_isolation_before_writes(factory, monkeypatch):
    with factory() as session:
        monkeypatch.setattr(session, "get_bind", lambda: SimpleNamespace(dialect=SimpleNamespace(name="postgresql")))
        monkeypatch.setattr(session, "connection", lambda: SimpleNamespace(get_isolation_level=lambda: "REPEATABLE READ"))
        with pytest.raises(importer.FinancialSyncError, match="merge_requires_read_committed"):
            importer.merge_company_facts(session, CIKS["AAPL"], payload())
    assert rows(factory) == []
