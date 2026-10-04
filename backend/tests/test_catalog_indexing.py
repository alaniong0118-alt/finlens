"""Real ORM/parser/persistence with synthetic SEC data and mocked encoder/network."""
from datetime import date
from decimal import Decimal
from unittest.mock import Mock

import httpx
import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app import catalog_indexing_service as service, embedding_service, main, sec_client, sec_filing_service
from app.database import Base
from app.models import Company, FilingChunk, FinancialFact


@pytest.fixture
def session(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    monkeypatch.setattr(main, "SessionLocal", sessionmaker(bind=engine))
    with Session(engine) as session:
        session.add_all([
            Company(ticker="AAPL", name="Apple", cik="0000320193", exchange="NASDAQ"),
            Company(ticker="MSFT", name="Microsoft", cik="0000789019", exchange="NASDAQ"),
        ])
        session.commit()
        yield session
    engine.dispose()


def metadata(cik):
    return sec_client.FilingMetadata(cik, f"{cik}-26-000001", "10-Q", date(2026, 8, 1), "fixture.htm")


def add_chunk(session, cik="0000320193", *, embedded=True, accession=None, index=0, filed=None):
    f = metadata(cik)
    accession = accession or f.accession_number
    chunk = FilingChunk(company_cik=cik, accession_number=accession, form=f.form,
                        filename=f.primary_document, filed=filed or f.filed,
                        chunk_index=index, chunk_id=f"chunk_{index:04d}",
                        text="Synthetic revenue source", start_char=index * 2250, end_char=index * 2250 + 24,
                        sec_url=sec_client.build_filing_url(cik, accession),
                        embedding=[1.0] * 384 if embedded else None)
    session.add(chunk)
    session.commit()
    return chunk


@pytest.fixture(autouse=True)
def external(monkeypatch):
    discovery = Mock(side_effect=metadata)
    raw = Mock(return_value="<DOCUMENT>\n<TYPE>10-Q\n<FILENAME>fixture.htm\n<TEXT><html><body>"
               + "Synthetic revenue growth discussion. " * 100 + "</body></html></TEXT>\n</DOCUMENT>")
    encoder = Mock(side_effect=lambda texts: [[1.0] * 384 for _ in texts])
    monkeypatch.setattr(service, "discover_filing", discovery)
    monkeypatch.setattr(sec_filing_service, "get_filing_raw_text", raw)
    monkeypatch.setattr(embedding_service, "embed_texts", encoder)
    # Company Facts and OpenAI must never be dependencies of the workflow.
    monkeypatch.setattr(sec_client, "get_company_facts", Mock(side_effect=AssertionError("Forbidden facts import")))
    monkeypatch.setattr("app.answer_service._get_openai_client", Mock(side_effect=AssertionError("Forbidden LLM")))
    return discovery, raw, encoder


def snapshot(session, model):
    return [{c.name: str(getattr(row, c.name)) for c in model.__table__.columns}
            for row in session.scalars(select(model).order_by(model.id))]


def test_skip_complete_without_network_or_encoder(session, external):
    add_chunk(session)
    report = service.index_catalog(session, ["AAPL"])
    assert report["skipped"] == 1 and report["final_ready"] == 1
    for call in external:
        call.assert_not_called()


def test_index_incomplete_and_repeat_is_idempotent(session, external):
    before_companies = snapshot(session, Company)
    report = service.index_catalog(session)
    assert report["newly_indexed"] == report["final_ready"] == 2
    before = snapshot(session, FilingChunk)
    for call in external:
        call.reset_mock()
    assert service.index_catalog(session)["skipped"] == 2
    assert snapshot(session, FilingChunk) == before
    assert snapshot(session, Company) == before_companies
    for call in external:
        call.assert_not_called()


def test_resume_missing_vectors_without_download(session, external):
    add_chunk(session, embedded=False)
    report = service.index_catalog(session, ["AAPL"])
    assert report["resumed"] == 1 and report["final_ready"] == 1
    external[0].assert_not_called()
    external[1].assert_not_called()
    external[2].assert_called_once()


def test_one_company_failure_does_not_abort_next(session, external):
    external[0].side_effect = [httpx.ConnectError("private credential"), metadata("0000789019")]
    report = service.index_catalog(session)
    assert report["failed"] == 1 and report["newly_indexed"] == 1
    assert report["final_ready"] == 1
    assert "private credential" not in str(report)
    assert report["companies"][0]["error_stage"] == "discovery_network"


def test_persistence_conflict_rolls_back_without_replacing_existing_filing(session, external):
    add_chunk(session)
    before = snapshot(session, FilingChunk)
    apple = metadata("0000320193")
    external[0].side_effect = lambda cik: sec_client.FilingMetadata(
        cik, apple.accession_number, apple.form, apple.filed, apple.primary_document,
    )
    report = service.index_catalog(session)
    assert report["skipped"] == 1 and report["failed"] == 1
    assert report["companies"][1]["error_stage"] == "persistence"
    assert snapshot(session, FilingChunk) == before
    external[2].assert_not_called()


def test_no_supported_filing_clean_failure(session, external):
    external[0].return_value = None
    external[0].side_effect = None
    report = service.index_catalog(session, ["MSFT"])
    assert report["failed"] == 1 and report["final_ready"] == 0
    assert report["companies"][0]["error_stage"] == "no_supported_filing"
    external[1].assert_not_called()


def rows(forms):
    return {"form": forms, "accessionNumber": [f"0000320193-26-{i:06d}" for i in range(len(forms))],
            "filingDate": [f"2026-08-{i+1:02d}" for i in range(len(forms))],
            "primaryDocument": ["fixture.htm"] * len(forms)}


def test_latest_exact_10q_preferred_over_newer_10k():
    selected = sec_client.select_latest_filing("0000320193", rows(["10-Q", "10-Q", "10-Q/A", "10-K"]))
    assert selected.form == "10-Q" and selected.filed == date(2026, 8, 2)


def test_10k_fallback_and_exclude_amendments():
    assert sec_client.select_latest_filing("0000320193", rows(["10-K", "10-K/A"])).form == "10-K"
    assert sec_client.select_latest_filing("0000320193", rows(["8-K", "10-Q/A"])) is None


def test_embedding_failure_not_ready_and_rerun_resumes(session, external):
    external[2].side_effect = RuntimeError("private model token")
    report = service.index_catalog(session, ["MSFT"])
    assert report["failed"] == 1 and report["final_ready"] == 0
    assert report["companies"][0]["chunk_count"] > 0
    assert report["companies"][0]["embedding_count"] == 0
    assert "private model token" not in str(report)
    external[0].reset_mock(); external[1].reset_mock()
    external[2].side_effect = lambda texts: [[1.0] * 384 for _ in texts]
    assert service.index_catalog(session, ["MSFT"])["resumed"] == 1
    external[0].assert_not_called(); external[1].assert_not_called()


def test_report_counts_and_subset(session):
    add_chunk(session)
    report = service.index_catalog(session, ["msft"])
    assert report["catalog_total"] == 2 and report["selected_total"] == 1
    assert report["newly_indexed"] == 1 and report["final_ready"] == 2
    assert report["companies"][0]["ticker"] == "MSFT"
    assert report["openai_calls"] == 0
    with pytest.raises(ValueError):
        service.index_catalog(session, ["unknown"])


def test_existing_financial_facts_and_filing_data_preserved(session):
    session.add(FinancialFact(company_cik="0000320193", metric="Revenues", value=Decimal("123"),
                              unit="USD", source="Synthetic fixture", accession_number="historical"))
    add_chunk(session)
    before_facts = snapshot(session, FinancialFact)
    before_chunk = snapshot(session, FilingChunk)[0]
    service.index_catalog(session)
    assert snapshot(session, FinancialFact) == before_facts
    assert snapshot(session, FilingChunk)[0] == before_chunk


def test_dry_run_no_data_writes(session, external):
    report = service.index_catalog(session, dry_run=True)
    assert report["failed"] == 0 and report["final_ready"] == 0
    assert all(r["status"] == "discovered" for r in report["companies"])
    assert session.scalar(select(func.count()).select_from(FilingChunk)) == 0
    external[1].assert_not_called(); external[2].assert_not_called()


def test_sources_exposes_indexed_filing_without_facts(session):
    add_chunk(session)
    sources = main.get_company_sources("AAPL")
    assert len(sources) == 1 and sources[0].has_filing_chunks
    assert sources[0].metrics == [] and sources[0].period_start is None and sources[0].period_end is None
    assert sources[0].sec_url == sec_client.build_filing_url("0000320193", metadata("0000320193").accession_number)


@pytest.mark.parametrize("bad", ["filename", "text", "embedding"])
def test_invalid_persisted_data_not_replaced(session, external, bad):
    chunk = add_chunk(session)
    setattr(chunk, bad, [0.0] * 384 if bad == "embedding" else "")
    session.commit()
    before = snapshot(session, FilingChunk)
    report = service.index_catalog(session, ["AAPL"])
    assert report["failed"] == 1
    assert report["companies"][0]["chunk_count"] == 1
    assert snapshot(session, FilingChunk) == before
    for call in external:
        call.assert_not_called()


@pytest.mark.parametrize("raw", ["not a primary document", "<DOCUMENT>\n<TYPE>10-Q\n<FILENAME>wrong.htm\n<TEXT><p>text</p></TEXT>\n</DOCUMENT>",
                                   "<DOCUMENT>\n<TYPE>10-Q\n<FILENAME>fixture.htm\n<TEXT><p></p></TEXT>\n</DOCUMENT>"])
def test_invalid_or_empty_primary_document_no_persistence(session, external, raw):
    external[1].return_value = raw
    assert service.index_catalog(session, ["MSFT"])["failed"] == 1
    assert session.scalar(select(func.count()).select_from(FilingChunk)) == 0
    external[2].assert_not_called()


def test_official_discovery_identity_and_archive_fallback(monkeypatch):
    responses = Mock(side_effect=[Mock(json=lambda: {"cik": "0000320193", "filings": {
        "recent": rows(["10-K"]), "files": [{"name": "CIK0000320193-submissions-001.json", "filingTo": "2025-12-31"}]}}),
        Mock(json=lambda: rows(["10-Q"]))])
    monkeypatch.setattr(sec_client, "_sec_get", responses)
    assert sec_client.discover_filing("0000320193").form == "10-Q"
    assert responses.call_count == 2
    responses.side_effect = None
    responses.return_value = Mock(json=lambda: {"cik": "wrong"})
    with pytest.raises(ValueError):
        sec_client.discover_filing("0000320193")


def test_sec_bounded_retry_and_no_retry_404(monkeypatch):
    monkeypatch.setattr(sec_client, "get_sec_headers", lambda: {"User-Agent": "synthetic fixture"})
    monkeypatch.setattr(sec_client.time, "sleep", lambda _: None)
    request = httpx.Request("GET", "https://data.sec.gov/fixture")
    get = Mock(side_effect=[httpx.Response(429, request=request), httpx.Response(503, request=request),
                           httpx.Response(200, request=request)])
    client = Mock(); client.__enter__ = Mock(return_value=client); client.__exit__ = Mock(return_value=False); client.get = get
    monkeypatch.setattr(sec_client.httpx, "Client", lambda **_: client)
    assert sec_client._sec_get(str(request.url)).status_code == 200
    assert get.call_count == 3
    get.reset_mock(); get.side_effect = None; get.return_value = httpx.Response(404, request=request)
    with pytest.raises(httpx.HTTPStatusError):
        sec_client._sec_get(str(request.url))
    assert get.call_count == 1


@pytest.mark.parametrize("failed", [False, True])
def test_cli_subset_report_and_exit_code(session, external, monkeypatch, tmp_path, failed):
    from app import database
    from scripts import index_catalog, setup_demo
    import json

    monkeypatch.setattr(database, "SessionLocal", lambda: Session(session.bind))
    monkeypatch.setattr(setup_demo, "check_schema", lambda _session: None)
    if failed:
        external[0].side_effect = RuntimeError("private upstream body")
    path = tmp_path / "report.json"
    code = index_catalog.main(["--ticker", "MSFT", "--dry-run", "--report", str(path)])
    report = json.loads(path.read_text(encoding="utf-8"))
    assert code == int(failed) and report["failed"] == int(failed)
    assert report["selected_total"] == 1 and report["companies"][0]["ticker"] == "MSFT"
    assert "private upstream body" not in str(report)


def test_zero_vector_fails_not_ready_then_recovers_without_redownload(session, external):
    original = add_chunk(session)
    original_id = original.id
    before = snapshot(session, FilingChunk)[0]
    external[2].side_effect = lambda texts: [[0.0] * 384 for _ in texts]

    report = service.index_catalog(session, ["MSFT"])
    assert report["failed"] == 1 and report["final_ready"] == 1
    persisted = service.filing_chunks(session, "0000789019")
    assert persisted and all(chunk.embedding is None for chunk in persisted)
    microsoft = next(c for c in main.get_companies() if c.ticker == "MSFT")
    assert not microsoft.has_indexed_filing and microsoft.indexed_filing_count == 0
    chunk_ids = [chunk.id for chunk in persisted]
    assert snapshot(session, FilingChunk)[0] == before

    external[0].reset_mock()
    external[1].reset_mock()
    external[2].side_effect = lambda texts: [[1.0] * 384 for _ in texts]
    recovered = service.index_catalog(session, ["MSFT"])
    assert recovered["resumed"] == 1 and recovered["failed"] == 0
    assert recovered["final_ready"] == 2
    persisted = service.filing_chunks(session, "0000789019")
    assert [chunk.id for chunk in persisted] == chunk_ids
    assert all(chunk.embedding is not None for chunk in persisted)
    assert snapshot(session, FilingChunk)[0] == before
    assert session.get(FilingChunk, original_id).embedding is not None
    external[0].assert_not_called()
    external[1].assert_not_called()


@pytest.mark.parametrize("vector", [
    [float("nan")] + [1.0] * 383,
    [float("inf")] + [1.0] * 383,
    [1.0] * 383,
    [1e-50] * 384,  # Positive in float64, zero in pgvector's float32 storage.
], ids=["nan", "infinity", "wrong_dimension", "float32_underflow"])
def test_shared_embedding_boundary_rejects_invalid_output_before_write(session, external, vector):
    add_chunk(session, embedded=False)
    before = snapshot(session, FilingChunk)
    external[2].side_effect = lambda texts: [vector for _ in texts]
    updates = []
    def observe(_conn, _cursor, statement, *_args):
        if statement.lstrip().lower().startswith("update"):
            updates.append(statement)
    event.listen(session.bind, "before_cursor_execute", observe)
    try:
        with pytest.raises(ValueError):
            embedding_service.embed_filing_chunks(session, "0000320193")
    finally:
        event.remove(session.bind, "before_cursor_execute", observe)
    assert updates == []
    assert snapshot(session, FilingChunk) == before


@pytest.mark.parametrize("failure", ["invalid", "exception", "interrupt"])
def test_embedding_failure_after_batch_flush_rolls_back_and_recovers(session, external, failure):
    original = add_chunk(session)
    original.embedding = [0.5] * 384
    for index in range(1, 34):
        session.add(FilingChunk(
            company_cik=original.company_cik, accession_number=original.accession_number,
            form=original.form, filename=original.filename, filed=original.filed,
            chunk_index=index, chunk_id=f"chunk_{index:04d}", text=f"Synthetic source {index}",
            start_char=index * 2250, end_char=index * 2250 + 100, sec_url=original.sec_url,
        ))
    session.commit()
    before = snapshot(session, FilingChunk)
    batches = []
    def encode(texts):
        batches.append(len(texts))
        if len(batches) == 1:
            return [[1.0] * 384 for _ in texts]
        # This SELECT sees the first batch's actual flush, before any commit.
        assert session.scalar(select(func.count(FilingChunk.embedding))) == 33
        if failure == "invalid":
            return [[0.0] * 384 for _ in texts]
        if failure == "interrupt":
            raise KeyboardInterrupt
        raise RuntimeError("Synthetic second-batch failure")
    external[2].side_effect = encode
    expected = {"invalid": ValueError, "exception": RuntimeError, "interrupt": KeyboardInterrupt}[failure]
    with pytest.raises(expected):
        embedding_service.embed_filing_chunks(session, "0000320193")
    assert batches == [32, 1]
    assert snapshot(session, FilingChunk) == before
    assert session.scalar(select(func.count(FilingChunk.embedding))) == 1

    external[2].side_effect = lambda texts: [[1.0] * 384 for _ in texts]
    recovered = service.index_catalog(session, ["AAPL"])
    assert recovered["resumed"] == 1 and recovered["failed"] == 0
    assert session.scalar(select(func.count(FilingChunk.embedding))) == 34
    assert list(session.get(FilingChunk, original.id).embedding) == [0.5] * 384
    external[0].assert_not_called()
    external[1].assert_not_called()


def test_diagnostic_failure_still_processes_next_issuer_and_writes_report(session, external, monkeypatch, tmp_path):
    import json
    from app import database
    from scripts import index_catalog, setup_demo
    original_read = service.filing_chunks
    reads = []
    def read(session, cik, accession=None):
        reads.append(cik)
        if cik == "0000320193" and reads.count(cik) == 2:
            raise OperationalError("private diagnostic statement", {}, Exception("private diagnostic secret"))
        return original_read(session, cik, accession)
    external[0].side_effect = [RuntimeError("private original secret"), metadata("0000789019")]
    monkeypatch.setattr(service, "filing_chunks", read)
    monkeypatch.setattr(database, "SessionLocal", lambda: Session(session.bind))
    monkeypatch.setattr(setup_demo, "check_schema", lambda _: None)
    path = tmp_path / "report.json"
    assert index_catalog.main(["--report", str(path)]) == 1
    report = json.loads(path.read_text(encoding="utf-8"))
    assert report["failed"] == 1 and report["newly_indexed"] == 1 and report["final_ready"] == 1
    apple, microsoft = report["companies"]
    assert apple["status"] == "failed" and apple["diagnostic_status"] == "unavailable"
    assert apple["chunk_count"] is None and apple["embedding_count"] is None
    assert microsoft["status"] == "indexed"
    assert "private" not in json.dumps(report)


def test_global_readiness_outage_retains_results_and_nonzero_cli_exit(session, monkeypatch, tmp_path, capsys):
    import json
    from app import database
    from scripts import index_catalog, setup_demo
    add_chunk(session)
    def scalar(local, statement, *args, **kwargs):
        raise OperationalError("private database URL", {}, Exception("private password"))
    monkeypatch.setattr(Session, "scalar", scalar)
    monkeypatch.setattr(database, "SessionLocal", lambda: Session(session.bind))
    monkeypatch.setattr(setup_demo, "check_schema", lambda _: None)
    path = tmp_path / "outage.json"
    assert index_catalog.main(["--ticker", "AAPL", "--report", str(path)]) == 1
    report = json.loads(path.read_text(encoding="utf-8"))
    assert report["skipped"] == 1 and report["final_ready"] is None
    assert report["catalog_error"] and report["companies"][0]["status"] == "skipped"
    assert "private" not in json.dumps(report) + capsys.readouterr().err


def test_valid_accession_skipped_despite_invalid_sibling(session, external):
    valid = add_chunk(session)
    invalid = add_chunk(session, accession="0000320193-26-000002", filed=date(2026, 8, 2))
    invalid.text = ""
    session.commit()
    before = snapshot(session, FilingChunk)
    report = service.index_catalog(session, ["AAPL"])
    result = report["companies"][0]
    assert report["skipped"] == 1 and report["failed"] == 0
    assert result["accession_number"] == valid.accession_number
    assert result["accession_diagnostics"][0]["accession_number"] == invalid.accession_number
    assert result["accession_diagnostics"][0]["status"] == "invalid"
    assert snapshot(session, FilingChunk) == before
    # Preserve the existing API's non-null, distinct-accession count semantics.
    assert main.get_companies()[0].indexed_filing_count == 2
    for call in external:
        call.assert_not_called()


def test_only_invalid_accessions_do_not_claim_complete_or_replace_data(session, external):
    first = add_chunk(session)
    first.text = ""
    second = add_chunk(session, accession="0000320193-26-000002")
    second.embedding = [0.0] * 384
    session.commit()
    before = snapshot(session, FilingChunk)
    report = service.index_catalog(session, ["AAPL"])
    assert report["failed"] == 1 and report["skipped"] == 0 and report["resumed"] == 0
    assert len(report["companies"][0]["accession_diagnostics"]) == 2
    assert snapshot(session, FilingChunk) == before
    for call in external:
        call.assert_not_called()


def test_multiple_valid_accessions_recognized_without_duplicate_work(session, external):
    add_chunk(session)
    latest = add_chunk(session, accession="0000320193-26-000002", filed=date(2026, 8, 2))
    before = snapshot(session, FilingChunk)
    report = service.index_catalog(session, ["AAPL"])
    assert report["skipped"] == 1 and report["failed"] == 0
    assert report["companies"][0]["accession_number"] == latest.accession_number
    assert main.get_companies()[0].indexed_filing_count == 2
    assert snapshot(session, FilingChunk) == before
    for call in external:
        call.assert_not_called()


def test_complete_coverage_skips_with_incomplete_sibling_diagnostics(session, external):
    add_chunk(session)
    sibling = add_chunk(session, accession="0000320193-26-000002", embedded=False)
    before = snapshot(session, FilingChunk)
    report = service.index_catalog(session, ["AAPL"])
    assert report["skipped"] == 1 and report["failed"] == 0
    assert report["companies"][0]["accession_diagnostics"] == [{
        "accession_number": sibling.accession_number, "status": "incomplete", "missing_embeddings": 1,
    }]
    assert snapshot(session, FilingChunk) == before
    for call in external:
        call.assert_not_called()


def test_valid_incomplete_accession_resumes_despite_invalid_sibling(session, external):
    invalid = add_chunk(session)
    invalid.text = ""
    valid = add_chunk(session, accession="0000320193-26-000002", embedded=False)
    session.commit()
    invalid_before = snapshot(session, FilingChunk)[0]
    report = service.index_catalog(session, ["AAPL"])
    assert report["resumed"] == 1 and report["failed"] == 0
    result = report["companies"][0]
    assert result["accession_number"] == valid.accession_number
    assert len(result["accession_diagnostics"]) == 1
    assert result["accession_diagnostics"][0]["status"] == "invalid"
    assert snapshot(session, FilingChunk)[0] == invalid_before
    external[0].assert_not_called()
    external[1].assert_not_called()
