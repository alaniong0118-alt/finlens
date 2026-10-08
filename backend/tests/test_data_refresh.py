"""Real coordinator/ORM/API regressions; all source/provider access forbidden."""
from datetime import date, timedelta
from decimal import Decimal
import json
from threading import Thread, Event
from unittest.mock import Mock

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import main, sec_client
from app.database import Base
from app.models import Company, FinancialFact, FilingChunk, CompanyRefreshState, RefreshAttempt, FilingPublication
from app.refresh_contracts import RefreshRequest, StreamState, utcnow
from app.refresh_service import refresh, coordinator, bootstrap_publications, manifest
from app.freshness_service import freshness, schema_ready

CIK = "0000320193"
ACC = "0000320193-25-000001"


def facts(cik=CIK, value="100", *, filed="2025-02-01", accession=ACC, year=2024, start=None, end=None, concept="Revenues"):
    return {"cik": int(cik), "facts": {"us-gaap": {concept: {"units": {"USD": [{
        "val": Decimal(value), "start": start or f"{year}-01-01", "end": end or f"{year}-12-31",
        "filed": filed, "accn": accession, "form": "10-K", "fy": year, "fp": "FY", "frame": f"CY{year}",
    }]}}}}}


def metadata(cik=CIK, accession=ACC, form="10-Q"):
    return sec_client.FilingMetadata(cik, accession, form, date(2025, 5, 1), "fixture.htm")


def raw(cik, accession):
    return '<DOCUMENT>\n<TYPE>10-Q\n<FILENAME>fixture.htm\n<TEXT><html><p>Fixture reported revenue increased. ' + 'Stored evidence. ' * 260 + '</p></html></TEXT>\n</DOCUMENT>'


def encoder(texts):
    return [[0.5] * 384 for _ in texts]


@pytest.fixture
def factory(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    schema_ready(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as s, s.begin():
        s.add_all([Company(ticker="AAPL", cik=CIK, name="Apple Inc.", exchange="NASDAQ"),
                   Company(ticker="JPM", cik="0000019617", name="JPMorgan Chase & Co", exchange="NYSE")])
    monkeypatch.setattr(main, "SessionLocal", factory)
    monkeypatch.setattr(sec_client, "_sec_get", Mock(side_effect=AssertionError("Forbidden SEC")))
    monkeypatch.setattr("app.answer_service._get_openai_client", Mock(side_effect=AssertionError("Forbidden OpenAI")))
    yield factory
    engine.dispose()


def run(factory, stream="facts", **kwargs):
    options = {k: kwargs.pop(k) for k in list(kwargs) if k in {"dry_run", "max_filings", "tickers", "max_seconds", "max_run_seconds"}}
    return refresh(factory, RefreshRequest(tickers=options.pop("tickers", ["AAPL"]), stream=stream, **options),
                   facts_loader=kwargs.pop("facts_loader", facts), inventory_loader=kwargs.pop("inventory_loader", lambda cik: {"filings": [metadata(cik)], "complete": True}),
                   raw_loader=kwargs.pop("raw_loader", raw), encoder=kwargs.pop("encoder", encoder), **kwargs)


def count(factory, model):
    with factory() as s:
        return s.scalar(select(func.count()).select_from(model))


def test_fact_publication_noop_versions_and_http_latest_historical(factory):
    first = run(factory)["companies"][0]
    assert first["status"] == "updated" and first["facts_inserted"] == 1 and first["version_after"] == 1
    assert first["inserted_by_metric"]["Revenues"] == 1
    second = run(factory)["companies"][0]
    assert second["status"] == "no_change" and second["version_after"] == 1 and second["facts_inserted"] == 0
    assert count(factory, FinancialFact) == 1
    with factory() as s:
        state = freshness(s, "AAPL")
        assert state.facts.status == "current" and state.status == "unknown"
        assert state.facts.last_checked_at and state.facts.last_successful_sync_at
        assert state.facts.latest_source_filing_date == date(2025, 2, 1)
    client = TestClient(main.app)
    for q in ("2024 revenue", "latest annual revenue"):
        response = client.post('/companies/AAPL/research-answer', json={"question": q}, headers={"X-FinLens-Data-Version": "1"})
        assert response.status_code == 200 and response.json()["observation"]["value"] == "100.0000"
        assert response.headers["X-FinLens-Data-Version"] == "1"
    assert client.get('/companies/AAPL/financials/summary', headers={"X-FinLens-Data-Version": "0"}).status_code == 409


def test_restated_observation_preserves_original_provenance(factory):
    run(factory)
    with factory() as s:
        old = s.scalar(select(FinancialFact))
        original = (old.id, old.value, old.accession_number, old.created_at)
    result = run(factory, facts_loader=lambda cik: facts(cik, "110", filed="2026-02-01", accession="0000320193-26-000002"))
    assert result["companies"][0]["version_after"] == 2
    point = TestClient(main.app).post('/companies/AAPL/research-answer', json={"question": "2024 revenue"}).json()["observation"]
    assert point["value"] == "110.0000" and point["provenance"][0]["accession_number"] == "0000320193-26-000002"
    assert any(p["fact_id"] == original[0] for p in point["alternatives"])
    with factory() as s:
        old = s.get(FinancialFact, original[0])
        assert (old.id, old.value, old.accession_number, old.created_at) == original


@pytest.mark.parametrize("variant", ["same_context", "frame", "fiscal_metadata"])
def test_ambiguous_corrections_do_not_win_by_id(factory, variant):
    run(factory)
    revised = facts(value="200")
    obs = revised["facts"]["us-gaap"]["Revenues"]["units"]["USD"][0]
    if variant == "frame": obs["frame"] = "CY2024Q4"
    if variant == "fiscal_metadata": obs["fy"] = 2025
    result = run(factory, facts_loader=lambda cik: revised)["companies"][0]
    assert result["status"] == "failed" and result["error"] == "ambiguous_source_revision"
    assert result["version_after"] == 1 and result["facts_inserted"] == 0
    assert all(n == 0 for n in result["inserted_by_metric"].values())
    assert count(factory, FinancialFact) == 1


def test_commit_failure_after_flush_rolls_back_rows_versions_and_counts_next_company(factory):
    flushed = []
    def fail(s):
        if any(isinstance(r, RefreshAttempt) and r.company_cik == CIK and r.status == "updated" for r in s.dirty):
            ids = list(s.scalars(select(FinancialFact.id).where(FinancialFact.company_cik == CIK)))
            if ids:
                flushed.extend(ids)
                raise RuntimeError("private failure must not leak")
    event.listen(Session, "before_commit", fail)
    try:
        result = run(factory, tickers=["AAPL", "JPM"])
    finally:
        event.remove(Session, "before_commit", fail)
    assert flushed
    failed, healthy = result["companies"]
    assert failed["status"] == "failed" and failed["facts_inserted"] == failed["version_after"] == 0
    assert all(n == 0 for n in failed["inserted_by_metric"].values())
    assert healthy["status"] == "updated" and healthy["facts_inserted"] == 1
    with factory() as s:
        assert not list(s.scalars(select(FinancialFact).where(FinancialFact.company_cik == CIK)))
        assert s.get(CompanyRefreshState, CIK).data_version == 0
        assert not list(s.scalars(select(RefreshAttempt).where(RefreshAttempt.company_cik == CIK, RefreshAttempt.published_version.is_not(None))))
    assert "private failure" not in json.dumps(result)


def test_evidence_is_complete_atomic_and_noop_is_stable(factory):
    first = run(factory, "evidence")["companies"][0]
    assert first["status"] == "updated" and first["filings_published"] == 1 and first["version_after"] == 1
    chunks = count(factory, FilingChunk)
    assert chunks > 1 and count(factory, FilingPublication) == 1
    second = run(factory, "evidence", raw_loader=Mock(side_effect=AssertionError("No redownload")), encoder=Mock(side_effect=AssertionError("No re-embedding")))["companies"][0]
    assert second["status"] == "no_change" and second["version_after"] == 1
    client = TestClient(main.app)
    assert client.get('/companies').json()[0]["indexed_filing_count"] == 1
    assert client.get(f'/companies/AAPL/filings/{ACC}/text').status_code == 200
    stored = client.get(f'/companies/AAPL/filings/{ACC}/chunks').json()
    assert stored["chunk_count"] == chunks
    assert stored["chunks"][0]["ticker"] == "AAPL" and stored["chunks"][0]["company_name"] == "Apple Inc."
    assert client.get('/companies/AAPL/sources').json()[0]["has_filing_chunks"]


def test_embedding_failure_keeps_old_publication_and_next_retry(factory):
    run(factory, "evidence")
    new = metadata(accession="0000320193-25-000002")
    inventory = lambda cik: {"filings": [metadata(cik), new], "complete": True}
    failed = run(factory, "both", inventory_loader=inventory, encoder=lambda texts: [[0.0]*384 for _ in texts])
    assert [r["status"] for r in failed["companies"]] == ["updated", "failed"]
    with factory() as s:
        state = freshness(s, "AAPL")
        assert state.data_version == 2 and state.evidence_version == 1
        assert state.evidence.status == "failed" and state.facts.status == "current"
        assert s.get(FilingPublication, (CIK, ACC))
        assert not s.get(FilingPublication, (CIK, new.accession_number))
    assert count(factory, FilingPublication) == 1
    assert run(factory, "evidence", inventory_loader=inventory)["companies"][0]["status"] == "updated"
    assert count(factory, FilingPublication) == 2


def test_evidence_commit_failure_does_not_publish_vectors_or_version(factory):
    flushed = []
    def fail(s):
        if any(isinstance(r, RefreshAttempt) and r.stream == "evidence" and r.status == "updated" for r in s.dirty):
            flushed.extend(s.scalars(select(FilingChunk.id)))
            raise RuntimeError("fail publication commit")
    event.listen(Session, "before_commit", fail)
    try:
        result = run(factory, "evidence")["companies"][0]
    finally:
        event.remove(Session, "before_commit", fail)
    assert flushed  # Indexing and flush succeeded before the failed commit.
    assert result["status"] == "failed" and result["filings_published"] == result["version_after"] == 0
    assert result["pending_targets"] == [ACC]
    assert count(factory, FilingChunk) == count(factory, FilingPublication) == 0
    with factory() as s:
        assert freshness(s, "AAPL").evidence.pending_targets == [ACC]


@pytest.mark.parametrize("complete,max_filings", [(False, 2), (True, 1)])
def test_bounded_inventory_never_fabricates_current(factory, complete, max_filings):
    inv = lambda cik: {"filings": [metadata(cik), metadata(cik, "0000320193-25-000002")], "complete": complete}
    result = run(factory, "evidence", inventory_loader=inv, max_filings=max_filings)["companies"][0]
    assert result["status"] == "pending"
    with factory() as s:
        state = freshness(s, "AAPL")
        assert state.evidence.status == "pending" and state.status == "pending"
        assert state.evidence.last_successful_sync_at is None


def test_dry_run_does_not_write_any_metadata_or_generate_embeddings(factory):
    for stream in ("facts", "evidence"):
        result = run(factory, stream, dry_run=True, encoder=Mock(side_effect=AssertionError("No model in dry run")))["companies"][0]
        assert result["status"] == "would_update" and result["version_after"] == 0
    for model in (FinancialFact, FilingChunk, CompanyRefreshState, RefreshAttempt, FilingPublication):
        assert count(factory, model) == 0


def test_concurrent_request_busy_no_network(factory):
    entered, release = Event(), Event()
    def hold():
        with coordinator(factory):
            entered.set(); release.wait(5)
    thread = Thread(target=hold); thread.start(); assert entered.wait(5)
    try:
        source = Mock(side_effect=AssertionError("Must not fetch when busy"))
        assert run(factory, facts_loader=source)["error"] == "refresh_busy_or_lock_lost"
        source.assert_not_called()
    finally:
        release.set(); thread.join(5)


def test_interruption_checkpoint_and_rerun(factory):
    result = run(factory, facts_loader=Mock(side_effect=KeyboardInterrupt()))
    assert result["error"] == "interrupted" and result["companies"][0]["status"] == "interrupted"
    assert count(factory, FinancialFact) == 0
    assert run(factory)["companies"][0]["version_after"] == 1


def test_stale_and_failed_checks_preserve_success_dates(factory):
    run(factory)
    with factory() as s, s.begin():
        row = s.get(CompanyRefreshState, CIK)
        old = StreamState.model_validate(row.facts)
        old.last_checked_at = utcnow() - timedelta(days=2)
        row.facts = old.model_dump(mode="json")
    with factory() as s:
        assert freshness(s, "AAPL").facts.status == "stale"
    run(factory, facts_loader=Mock(side_effect=TimeoutError()))
    with factory() as s:
        state = freshness(s, "AAPL")
        assert state.facts.status == "failed" and state.facts.last_successful_sync_at
        assert state.facts.last_checked_at < utcnow()-timedelta(days=1)


def test_no_interactive_network_and_unpublished_accession_gate(factory):
    client = TestClient(main.app)
    for path in ("text", "chunks", "search?q=revenue", "semantic-search?q=revenue", "context?q=revenue"):
        response = client.get(f'/companies/AAPL/filings/{ACC}/{path}')
        assert response.status_code == 409
    response = client.post(f'/companies/AAPL/filings/{ACC}/answer', json={"question": "revenue"})
    assert response.status_code == 409
    assert client.get('/companies/AAPL/freshness').json()["status"] == "unknown"
    assert client.post('/companies/AAPL/refresh').status_code == 404


def test_bootstrap_is_offline_metadata_only_and_unknown_currency(factory):
    run(factory, "evidence")
    with factory() as s, s.begin():
        publication = s.get(FilingPublication, (CIK, ACC))
        s.delete(publication)  # Isolated fixture simulates pre-migration baseline.
        state = s.get(CompanyRefreshState, CIK)
        state.data_version = state.evidence_version = 0
        state.evidence = {}
    before = count(factory, FilingChunk)
    with factory() as s, s.begin():
        assert bootstrap_publications(s)["registered"] == 1
    assert count(factory, FilingChunk) == before
    with factory() as s, s.begin():
        assert bootstrap_publications(s)["registered"] == 0
    with factory() as s:
        assert freshness(s, "AAPL").evidence.status == "unknown"


def test_invalid_observation_and_unavailable_metric_are_honest(factory):
    broken = facts(value="1.00001")
    assert run(factory, facts_loader=lambda cik: broken)["companies"][0]["status"] == "failed"
    assert count(factory, FinancialFact) == 0
    run(factory)
    response = TestClient(main.app).post('/companies/AAPL/research-answer', json={"question": "2024 diluted EPS"}).json()
    assert response["status"] != "available" and response["observation"]["value"] is None


def test_cli_and_scheduler_are_disabled_by_default(factory):
    from scripts.refresh_data import main as cli
    assert cli(["--ticker", "AAPL"]) == 2
    assert cli(["--ticker", "AAPL", "--dry-run"]) == 2


def test_unknown_company_rejects_before_network(factory):
    source = Mock(side_effect=AssertionError("No network"))
    assert run(factory, tickers=["UNKNOWN"], facts_loader=source)["error"]
    source.assert_not_called()


@pytest.mark.parametrize("period,question", [("annual", "2025 revenue"), ("quarter", "Q1 2025 revenue")])
def test_new_period_is_append_only_and_preserves_explicit_duration(factory, period, question):
    run(factory)
    source = facts(year=2025, value="125", filed="2026-02-01", accession="0000320193-26-000002",
                   end="2025-03-31" if period == "quarter" else "2025-12-31")
    obs = source["facts"]["us-gaap"]["Revenues"]["units"]["USD"][0]
    obs["form"], obs["fp"] = ("10-Q", "Q1") if period == "quarter" else ("10-K", "FY")
    if period == "quarter":
        # Explicit fiscal-quarter labels require an observed annual boundary.
        # Refresh must preserve that existing selection rule, not infer a calendar FY.
        anchor = facts(year=2025, value="1000", filed="2026-02-01",
                       accession="0000320193-26-000003", end="2025-12-31")
        source["facts"]["us-gaap"]["Revenues"]["units"]["USD"].extend(
            anchor["facts"]["us-gaap"]["Revenues"]["units"]["USD"])
    assert run(factory, facts_loader=lambda cik: source)["companies"][0]["version_after"] == 2
    result = TestClient(main.app).post('/companies/AAPL/research-answer', json={"question": question}).json()
    assert result["status"] == "available" and result["observation"]["period"]["kind"] == period
    assert result["observation"]["value"] == "125.0000"
    assert count(factory, FinancialFact) == (3 if period == "quarter" else 2)


def test_empty_source_is_pending_not_current_and_keeps_published_facts(factory):
    run(factory)
    result = run(factory, facts_loader=lambda cik: {"cik": int(cik), "facts": {"us-gaap": {}}})["companies"][0]
    assert result["status"] == "pending" and result["version_after"] == 1
    assert count(factory, FinancialFact) == 1
    with factory() as s:
        assert freshness(s, "AAPL").facts.status == "pending"


def test_failed_report_checkpoint_preserves_committed_ledger(factory):
    result = run(factory, on_progress=Mock(side_effect=OSError("private path")))
    assert result["error"] == "report_checkpoint_failed_use_database_ledger"
    assert result["companies"][0]["facts_inserted"] == 1
    with factory() as s:
        event_row = s.scalar(select(RefreshAttempt).where(RefreshAttempt.run_id == result["run_id"]))
        assert event_row.status == "updated" and event_row.published_version == 1
        assert event_row.details["facts_inserted"] == 1
    assert "private path" not in json.dumps(result)


def test_fatal_facts_checkpoint_stops_evidence_and_retry_is_idempotent(factory):
    inventory, download, encode = Mock(), Mock(), Mock()
    checkpoint = Mock(side_effect=[OSError("private report path"), None])
    report = run(factory, "both", on_progress=checkpoint,
                 inventory_loader=inventory, raw_loader=download, encoder=encode)
    assert report["error"] == "report_checkpoint_failed_use_database_ledger"
    assert [(r["stream"], r["status"], r["facts_inserted"]) for r in report["companies"]] == [("facts", "updated", 1)]
    assert report["not_processed"] == [{"ticker": "AAPL", "stream": "evidence"}]
    inventory.assert_not_called(); download.assert_not_called(); encode.assert_not_called()
    assert count(factory, FilingPublication) == count(factory, FilingChunk) == 0
    assert count(factory, FinancialFact) == 1
    with factory() as s:
        attempt = s.scalar(select(RefreshAttempt).where(RefreshAttempt.run_id == report["run_id"]))
        assert attempt.status == "updated" and attempt.details["facts_inserted"] == 1
    retry = run(factory, "both")
    assert [(r["stream"], r["status"]) for r in retry["companies"]] == [("facts", "no_change"), ("evidence", "updated")]
    assert count(factory, FinancialFact) == count(factory, FilingPublication) == 1


def test_abandoned_attempt_recovered_without_duplicate_publication(factory):
    run(factory)
    from uuid import uuid4
    with factory() as s, s.begin():
        s.add(RefreshAttempt(id=str(uuid4()), run_id=str(uuid4()), company_cik=CIK, stream="facts",
                             status="running", started_at=utcnow(), details={}))
    assert run(factory)["companies"][0]["status"] == "no_change"
    with factory() as s:
        attempts = list(s.scalars(select(RefreshAttempt)))
        assert sum(a.status == "interrupted" for a in attempts) == 1
        assert sum(a.published_version is not None for a in attempts) == 1


def test_discovery_selects_latest_q_and_k_and_amendments_without_q_preference(factory, monkeypatch):
    payload = {"cik": 320193, "filings": {"recent": {
        "form": ["10-Q", "10-Q", "10-K", "10-K/A", "8-K"],
        "accessionNumber": [f"0000320193-25-00000{i}" for i in range(1, 6)],
        "filingDate": ["2025-05-01", "2025-08-01", "2025-10-01", "2025-10-02", "2025-10-03"],
        "primaryDocument": ["fixture.htm"]*5,
    }}}
    monkeypatch.setattr(sec_client, "_sec_get", Mock(return_value=Mock(json=lambda: payload)))
    inventory = sec_client.discover_refresh_filings(CIK)
    assert inventory["complete"]
    assert [(m.form, m.accession_number[-1]) for m in inventory["filings"]] == [("10-Q", "2"), ("10-K", "3"), ("10-K/A", "4")]


@pytest.mark.parametrize("url", ['http://data.sec.gov/submissions/x', 'https://evil.test/submissions/x',
    'https://data.sec.gov.evil.test/submissions/x', 'https://data.sec.gov/submissions/x?token=private',
    'https://data.sec.gov:444/submissions/x', 'https://data.sec.gov/untrusted/x'])
def test_sec_client_rejects_untrusted_urls_before_contact(url, monkeypatch):
    contact = Mock(side_effect=AssertionError("Must not read private contact for untrusted URL"))
    monkeypatch.setattr(sec_client, "get_sec_headers", contact)
    with pytest.raises(ValueError, match="Untrusted SEC source URL"):
        sec_client._sec_get(url)
    contact.assert_not_called()


def test_readiness_ignores_partial_or_unpublished_rows(factory):
    run(factory, "evidence")
    with factory() as s, s.begin():
        original = s.scalar(select(FilingChunk))
        s.add(FilingChunk(company_cik=CIK, accession_number="0000320193-26-000099", form=original.form,
            filed=original.filed, filename=original.filename, chunk_index=0, chunk_id="chunk_0000",
            text=original.text, start_char=original.start_char, end_char=original.end_char,
            sec_url=sec_client.build_filing_url(CIK, "0000320193-26-000099"), embedding=original.embedding))
    client = TestClient(main.app)
    assert client.get('/companies').json()[0]["indexed_filing_count"] == 1
    assert client.get('/companies/AAPL/filings/0000320193-26-000099/chunks').status_code == 409


def test_refresh_resumes_missing_vectors_without_replacing_stored_evidence(factory):
    run(factory, "evidence")
    with factory() as s, s.begin():
        s.delete(s.get(FilingPublication, (CIK, ACC)))
        chunks = list(s.scalars(select(FilingChunk).order_by(FilingChunk.chunk_index)))
        original = [(c.id, c.text, c.start_char, c.end_char) for c in chunks]
        retained_vector = list(chunks[0].embedding)
        chunks[-1].embedding = None
    forbidden_download = Mock(side_effect=AssertionError("Resume must use stored chunks"))
    encoded = Mock(side_effect=encoder)
    result = run(factory, "evidence", raw_loader=forbidden_download, encoder=encoded)["companies"][0]
    assert result["status"] == "updated" and result["filings_published"] == 1
    forbidden_download.assert_not_called()
    assert sum(len(call.args[0]) for call in encoded.call_args_list) == 1
    with factory() as s:
        chunks = list(s.scalars(select(FilingChunk).order_by(FilingChunk.chunk_index)))
        assert [(c.id, c.text, c.start_char, c.end_char) for c in chunks] == original
        assert list(chunks[0].embedding) == retained_vector
        assert all(c.embedding is not None for c in chunks)


@pytest.mark.parametrize("kind", ["redirect", "oversize", "retry"])
def test_sec_streaming_bounds_redirects_and_retry_after_are_offline(monkeypatch, kind):
    import httpx
    original_get = sec_client._sec_get
    client_class = httpx.Client
    contacted, delays = [], []
    def respond(request):
        contacted.append(str(request.url))
        if kind == "redirect":
            return httpx.Response(302, headers={"Location": "https://evil.test/private"})
        if kind == "oversize":
            return httpx.Response(200, content=b"123456")
        if len(contacted) < 3:
            return httpx.Response(429, headers={"Retry-After": "300"})
        return httpx.Response(200, json={"ok": True})
    monkeypatch.setattr(sec_client, "get_sec_headers", lambda: {})
    monkeypatch.setattr(sec_client.httpx, "Client", lambda **kw: client_class(transport=httpx.MockTransport(respond), **kw))
    monkeypatch.setattr(sec_client.time, "sleep", delays.append)
    monkeypatch.setattr(sec_client, "MAX_RESPONSE_BYTES", 5 if kind == "oversize" else 1024)
    url = "https://data.sec.gov/submissions/CIK0000320193.json"
    if kind == "redirect":
        with pytest.raises(httpx.HTTPStatusError): original_get(url)
    elif kind == "oversize":
        with pytest.raises(ValueError, match="size bound"): original_get(url)
    else:
        assert original_get(url).json() == {"ok": True}
        assert len(contacted) == 3 and delays.count(30) == 2
    assert set(contacted) == {url}


def test_unmigrated_read_only_api_keeps_valid_evidence_and_unknown_freshness(factory):
    run(factory, "evidence")
    # Only the isolated fixture schema is changed, simulating an older deployment.
    FilingPublication.__table__.drop(factory.kw["bind"])
    RefreshAttempt.__table__.drop(factory.kw["bind"])
    CompanyRefreshState.__table__.drop(factory.kw["bind"])
    from app.freshness_service import _schemas
    _schemas.pop(factory.kw["bind"], None)
    writes = []
    def observe(conn, cursor, statement, *args):
        if statement.lstrip().split()[0].upper() in {"INSERT", "UPDATE", "DELETE", "CREATE", "ALTER"}:
            writes.append(statement)
    event.listen(factory.kw["bind"], "before_cursor_execute", observe)
    try:
        client = TestClient(main.app)
        assert client.get('/companies').json()[0]["indexed_filing_count"] == 1
        assert client.get(f'/companies/AAPL/filings/{ACC}/chunks').status_code == 200
        state = client.get('/companies/AAPL/freshness').json()
        assert state["migration_required"] and state["status"] == "unknown"
        assert state["facts"]["last_checked_at"] is None
        assert client.get('/companies/AAPL/sources').json()[0]["has_filing_chunks"]
        assert not writes
    finally:
        event.remove(factory.kw["bind"], "before_cursor_execute", observe)


def test_run_budget_prevents_publication_after_a_slow_source_and_stops_remaining_work(factory, monkeypatch):
    import app.refresh_service as service
    clock = [0.0]
    monkeypatch.setattr(service.time, "monotonic", lambda: clock[0])
    def slow(cik):
        clock[0] = 2.0
        return facts(cik)
    report = run(factory, tickers=['AAPL','JPM'], max_run_seconds=1, facts_loader=slow)
    assert report['companies'][0]['status'] == 'failed'
    assert report['companies'][0]['facts_inserted'] == report['companies'][0]['version_after'] == 0
    assert report['error'] == 'run_budget_reached_resume_remaining'
    assert report['not_processed'] == [{'ticker':'JPM','stream':'facts'}]
    assert count(factory, FinancialFact) == 0
