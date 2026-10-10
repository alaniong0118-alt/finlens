"""Production CLI/coordinator regressions with frozen sources and SQLite only."""
from dataclasses import replace
from datetime import date
import json
from unittest.mock import Mock

import pytest
from pydantic import ValidationError
from sqlalchemy import event, select

from app.models import FinancialFact, FilingChunk, FilingPublication, CompanyRefreshState, RefreshAttempt, Company
from app.refresh_contracts import RefreshRequest, StreamState, utcnow
from app.refresh_scope import CIK, EXISTING, TARGET, SCOPE
from app.refresh_service import refresh, manifest
from app.sec_importer import merge_company_facts
from app.sec_client import build_filing_url
from app.sec_parser import chunk_filing_text
from test_data_refresh import factory, facts, encoder  # Existing isolated, forbidden-network fixture.


def source():
    return {**facts(), "entityName": "Apple Inc."}


def inventory():
    return {"complete": True, "filings": [TARGET, EXISTING]}


def raw_submission(cik=CIK, accession=TARGET.accession_number):
    return f'''<SEC-DOCUMENT>{accession}.txt : 20251031
<SEC-HEADER>{accession}.hdr.sgml : 20251031
ACCESSION NUMBER: {accession}
CONFORMED SUBMISSION TYPE: 10-K
FILED AS OF DATE: 20251031
FILER:
 COMPANY DATA:
  COMPANY CONFORMED NAME: Apple Inc.
  CENTRAL INDEX KEY: {cik}
</SEC-HEADER>
<DOCUMENT>
<TYPE>10-K
<FILENAME>aapl-20250927.htm
<TEXT><html><p>Apple annual source evidence. {'Exact stored source. ' * 220}</p></html></TEXT>
</DOCUMENT>
</SEC-DOCUMENT>'''


@pytest.fixture
def guarded_factory(factory):
    with factory() as s, s.begin():
        merge_company_facts(s, CIK, source(), publish=False)
        s.add(CompanyRefreshState(company_cik=CIK, data_version=0, facts_version=0,
            evidence_version=0, facts=StreamState().model_dump(mode="json"), evidence=StreamState().model_dump(mode="json")))
        chunks = [FilingChunk(company_cik=CIK, accession_number=EXISTING.accession_number,
            form=EXISTING.form, filed=EXISTING.filed, filename=EXISTING.primary_document,
            chunk_index=i, sec_url=build_filing_url(CIK, EXISTING.accession_number),
            embedding=[0.5] * 384, **c) for i, c in enumerate(chunk_filing_text("Original quarterly source. " * 20))]
        s.add_all(chunks)
        manifest(s, chunks, 0)
    return factory


def request(**changes):
    return RefreshRequest(tickers=["AAPL"], publication_scope=SCOPE, stream="both",
        max_filings=1, max_seconds=300, max_run_seconds=600, **changes)


def run(factory, *, payload=None, inv=None, **overrides):
    loaders = dict(facts_loader=Mock(return_value=payload if payload is not None else source()),
                   inventory_loader=Mock(return_value=inv if inv is not None else inventory()),
                   raw_loader=Mock(side_effect=raw_submission), encoder=Mock(side_effect=encoder))
    loaders.update(overrides)
    report = refresh(factory, request(), **loaders)
    return report, loaders


MODELS = (Company, FinancialFact, FilingChunk, FilingPublication, CompanyRefreshState, RefreshAttempt)


def snapshot(factory):
    with factory() as s:
        return {m.__tablename__: json.dumps([dict(r._mapping) for r in s.execute(select(m.__table__))],
                    sort_keys=True, default=str) for m in MODELS}


@pytest.mark.parametrize("case", [
    "new_fact", "wrong_accession", "facts_cik", "inventory_cik", "form", "filename", "filed",
    "multiple_missing", "amendment", "known_amendment", "missing_q", "q_reingestion", "q_identity",
    "q_incomplete", "q_digest", "incomplete", "empty", "conflicting_fact", "already_published",
    "partial_target", "source_name", "empty_facts", "catalog_cik", "catalog_name", "unsettled",
])
def test_scope_rejects_before_any_persistent_statement(guarded_factory, case):
    factory = guarded_factory
    payload, inv = source(), inventory()
    if case == "new_fact":
        payload["facts"]["us-gaap"]["Revenues"]["units"]["USD"].append(
            facts(value="200", accession="0000320193-26-000002")["facts"]["us-gaap"]["Revenues"]["units"]["USD"][0])
    if case == "facts_cik": payload["cik"] = 19617
    if case == "source_name": payload["entityName"] = "Another issuer"
    if case == "empty_facts": payload["facts"] = {}
    changes = {"wrong_accession": {"accession_number": "0000320193-25-000080"},
               "inventory_cik": {"company_cik": "0000019617"}, "form": {"form": "10-Q"},
               "filename": {"primary_document": "another.htm"}, "filed": {"filed": date(2025, 11, 1)}}
    if case in changes: inv["filings"][0] = replace(TARGET, **changes[case])
    extra = replace(TARGET, accession_number="0000320193-25-000080", form="10-K/A")
    if case in {"multiple_missing", "amendment", "known_amendment"}:
        inv["filings"].append(replace(extra, form="10-K" if case == "multiple_missing" else "10-K/A"))
    if case == "missing_q": inv["filings"].pop()
    if case == "incomplete": inv["complete"] = False
    if case == "empty": inv["filings"] = []
    if case == "conflicting_fact": payload["facts"]["us-gaap"]["Revenues"]["units"]["USD"][0]["val"] = 200
    with factory() as s, s.begin():
        prior = s.get(FilingPublication, (CIK, EXISTING.accession_number))
        if case == "q_reingestion": s.delete(prior)
        if case == "q_identity": prior.filename = "different.htm"
        if case == "q_digest": prior.content_digest = "0" * 64
        if case == "q_incomplete": s.scalar(select(FilingChunk)).embedding = None
        if case == "already_published":
            s.add(FilingPublication(company_cik=CIK, accession_number=TARGET.accession_number,
                form=TARGET.form, filed=TARGET.filed, filename=TARGET.primary_document,
                chunk_count=1, content_digest="0" * 64, configuration="fixture", published_at=utcnow(), data_version=0))
        if case == "known_amendment":
            s.add(FilingPublication(company_cik=CIK, accession_number=extra.accession_number,
                form=extra.form, filed=extra.filed, filename=extra.primary_document,
                chunk_count=1, content_digest="0" * 64, configuration="fixture", published_at=utcnow(), data_version=0))
        if case == "partial_target":
            s.add(FilingChunk(company_cik=CIK, accession_number=TARGET.accession_number,
                form=TARGET.form, filed=TARGET.filed, filename=TARGET.primary_document, chunk_index=0,
                chunk_id="chunk_0000", text="Partial", start_char=0, end_char=7, sec_url="https://www.sec.gov", embedding=None))
        if case == "catalog_cik": s.scalar(select(Company).where(Company.ticker == "AAPL")).cik = "0000000001"
        if case == "catalog_name": s.scalar(select(Company).where(Company.ticker == "AAPL")).name = "Another issuer"
        if case == "unsettled":
            s.add(RefreshAttempt(id="unsettled", run_id="older", company_cik=CIK, stream="facts", status="running", started_at=utcnow(), details={}))
    before, writes = snapshot(factory), []
    def observe(conn, cursor, sql, *args):
        if sql.lstrip().split()[0].upper() in {"INSERT", "UPDATE", "DELETE", "REPLACE"}: writes.append(sql)
    event.listen(factory.kw["bind"], "before_cursor_execute", observe)
    try:
        report, loaders = run(factory, payload=payload, inv=inv)
    finally:
        event.remove(factory.kw["bind"], "before_cursor_execute", observe)
    assert report["error"] and report["companies"] == []
    assert not writes, "Reject before even attempting persistent DML"
    assert snapshot(factory) == before
    loaders["raw_loader"].assert_not_called()
    loaders["encoder"].assert_not_called()
    json.dumps(report)  # Always machine-readable; no private source body required.


def test_exact_scope_commits_separate_streams_with_pinned_sources(guarded_factory):
    factory = guarded_factory
    before = snapshot(factory)
    payload, inv = source(), inventory()
    def after_facts(report):
        # Mutate the external loader-owned objects AFTER validation. Execution
        # must consume the captured copies, not these now-unauthorized sources.
        payload["facts"]["us-gaap"]["Revenues"]["units"]["USD"][0]["val"] = 999
        inv["filings"] = [replace(TARGET, accession_number="0000320193-25-000099")]
        with factory() as s:
            if len(report["companies"]) == 1:
                assert s.scalar(select(RefreshAttempt)).status == "no_change"
                assert s.get(FilingPublication, (CIK, TARGET.accession_number)) is None
    report, loaders = run(factory, payload=payload, inv=inv, on_progress=after_facts)
    assert report["error"] is None
    assert [(r["status"], r["facts_inserted"], r["filings_published"], r["version_after"])
            for r in report["companies"]] == [("no_change", 0, 0, 0), ("updated", 0, 1, 1)]
    assert report["source_authorization"]["accession_number"] == TARGET.accession_number
    assert len(report["source_authorization"]["facts_sha256"]) == 64
    loaders["facts_loader"].assert_called_once_with(CIK)
    loaders["inventory_loader"].assert_called_once_with(CIK)
    loaders["raw_loader"].assert_called_once_with(CIK, TARGET.accession_number)
    after = snapshot(factory)
    assert before["companies"] == after["companies"] and before["financial_facts"] == after["financial_facts"]
    with factory() as s:
        state = s.get(CompanyRefreshState, CIK)
        assert (state.data_version, state.facts_version, state.evidence_version) == (1, 0, 1)
        assert len(list(s.scalars(select(RefreshAttempt)))) == 2
        assert s.get(FilingPublication, (CIK, TARGET.accession_number)).data_version == 1
        old = s.get(FilingPublication, (CIK, EXISTING.accession_number))
        assert old.data_version == 0
        assert all(len(c.embedding) == 384 for c in s.scalars(select(FilingChunk)))


def test_both_metadata_sources_are_validated_before_first_dml(guarded_factory):
    sequence = []
    def load_facts(cik): sequence.append("facts"); return source()
    def load_inventory(cik): sequence.append("inventory"); return inventory()
    def observe(conn, cursor, sql, *args):
        if sql.lstrip().split()[0].upper() in {"INSERT", "UPDATE", "DELETE"}:
            assert sequence[:2] == ["facts", "inventory"]
            sequence.append("write")
    event.listen(guarded_factory.kw["bind"], "before_cursor_execute", observe)
    try:
        report, _ = run(guarded_factory, facts_loader=load_facts, inventory_loader=load_inventory)
    finally:
        event.remove(guarded_factory.kw["bind"], "before_cursor_execute", observe)
    assert report["error"] is None and "write" in sequence


def test_loader_owned_facts_cannot_change_during_inventory_acquisition(guarded_factory):
    payload = source()
    def load_inventory(cik):
        payload["facts"]["us-gaap"]["Revenues"]["units"]["USD"][0]["val"] = 999
        return inventory()
    report, _ = run(guarded_factory, payload=payload, inventory_loader=load_inventory)
    assert report["error"] is None and report["companies"][0]["facts_inserted"] == 0


def test_post_gate_fact_drift_cannot_insert_facts_or_continue_to_evidence(guarded_factory):
    # An isolated fixture simulates unmanaged removal after gate acceptance.
    # The guarded facts transaction is dry-merge-only even when the DB drifts.
    from sqlalchemy.orm import Session
    fired = []
    def after_attempt(s):
        if not fired and any(isinstance(a, RefreshAttempt) and a.stream == "facts" for a in s.new):
            fired.append(True)
            from sqlalchemy import delete
            s.execute(delete(FinancialFact))
    event.listen(Session, "before_commit", after_attempt)
    try: report, loaders = run(guarded_factory)
    finally: event.remove(Session, "before_commit", after_attempt)
    assert fired and report["error"] == "canary_new_facts_forbidden"
    assert len(report["companies"]) == 1 and report["companies"][0]["facts_inserted"] == 0
    loaders["raw_loader"].assert_not_called()
    with guarded_factory() as s:
        assert not list(s.scalars(select(FinancialFact)))  # No replacement insert.
        assert s.get(FilingPublication, (CIK, TARGET.accession_number)) is None


def test_request_mutation_after_call_cannot_broaden_scope(guarded_factory):
    req = request()
    def load(cik):
        req.tickers.append("JPM"); req.publication_scope = None; req.max_filings = 10
        return source()
    report = refresh(guarded_factory, req, facts_loader=load, inventory_loader=lambda cik: inventory(),
        raw_loader=raw_submission, encoder=encoder)
    assert report["error"] is None
    assert {r["ticker"] for r in report["companies"]} == {"AAPL"}
    assert report["source_authorization"]["scope"] == SCOPE


@pytest.mark.parametrize("field,old,new", [
    ("accession", TARGET.accession_number, "0000320193-25-000080"),
    ("cik", CIK, "0000019617"), ("form", "CONFORMED SUBMISSION TYPE: 10-K", "CONFORMED SUBMISSION TYPE: 10-Q"),
    ("filed", "FILED AS OF DATE: 20251031", "FILED AS OF DATE: 20251101"),
    ("name", "COMPANY CONFORMED NAME: Apple Inc.", "COMPANY CONFORMED NAME: Other Inc."),
    ("primary", "aapl-20250927.htm", "other.htm"),
    ("envelope", "<SEC-DOCUMENT>", "<OTHER-DOCUMENT>"),
    ("truncated_envelope", "</SEC-DOCUMENT>", ""),
    ("duplicate_primary", "</SEC-DOCUMENT>", "<DOCUMENT>\n<TYPE>10-K\n</DOCUMENT>\n</SEC-DOCUMENT>"),
])
def test_raw_identity_failure_never_publishes_other_filing(guarded_factory, field, old, new):
    raw = raw_submission().replace(old, new)
    original = snapshot(guarded_factory)
    report, loaders = run(guarded_factory, raw_loader=Mock(return_value=raw))
    assert [r["status"] for r in report["companies"]] == ["no_change", "failed"]
    assert report["companies"][1]["filings_published"] == 0
    assert not loaders["encoder"].called
    after = snapshot(guarded_factory)
    for table in ("financial_facts", "filing_chunks", "filing_publications", "companies"):
        assert after[table] == original[table]
    with guarded_factory() as s:
        state = s.get(CompanyRefreshState, CIK)
        assert state.data_version == 0 and state.evidence_version == 0
        assert s.get(FilingPublication, (CIK, TARGET.accession_number)) is None


def test_guarded_evidence_commit_failure_preserves_zero_fact_commit(guarded_factory):
    before = snapshot(guarded_factory)
    flushed = []
    from sqlalchemy.orm import Session
    def fail(s):
        if any(isinstance(a, RefreshAttempt) and a.stream == "evidence" and a.status == "updated" for a in s.dirty):
            flushed.extend(s.scalars(select(FilingChunk.id).where(FilingChunk.accession_number == TARGET.accession_number)))
            raise RuntimeError("Isolated failure before commit")
    event.listen(Session, "before_commit", fail)
    try: report, _ = run(guarded_factory)
    finally: event.remove(Session, "before_commit", fail)
    assert flushed
    assert [r["status"] for r in report["companies"]] == ["no_change", "failed"]
    assert report["companies"][1]["commit_outcome"] == "rolled_back"
    assert report["companies"][1]["version_after"] == 0
    after = snapshot(guarded_factory)
    for table in ("financial_facts", "filing_chunks", "filing_publications"):
        assert before[table] == after[table]


def test_guarded_dry_run_is_readonly_but_not_publication_proof(guarded_factory):
    before = snapshot(guarded_factory)
    report = refresh(guarded_factory, request(dry_run=True), facts_loader=Mock(return_value=source()),
        inventory_loader=Mock(return_value=inventory()), raw_loader=Mock(side_effect=AssertionError("No raw in dry run")))
    assert [r["status"] for r in report["companies"]] == ["no_change", "would_update"]
    assert snapshot(guarded_factory) == before


@pytest.mark.parametrize("changes", [
    {"tickers": ["JPM"]}, {"tickers": ["AAPL", "JPM"]}, {"stream": "evidence"},
    {"max_filings": 2}, {"max_seconds": 301}, {"max_run_seconds": 601},
])
def test_contract_rejects_broadened_canary(changes):
    values = request().model_dump(); values.update(changes)
    with pytest.raises(ValidationError): RefreshRequest.model_validate(values)


def test_preflight_budget_rejects_before_writes(guarded_factory, monkeypatch):
    clock = [0]
    monkeypatch.setattr("app.refresh_service.time.monotonic", lambda: clock[0])
    def slow(cik): clock[0] = 301; return inventory()
    before = snapshot(guarded_factory)
    report, _ = run(guarded_factory, inventory_loader=slow)
    assert report["error"] == "canary_preflight_budget_exceeded"
    assert snapshot(guarded_factory) == before


@pytest.mark.parametrize("stage", ["facts_loader", "inventory_loader"])
def test_acquisition_failure_is_sanitized_without_metadata_writes(guarded_factory, stage):
    before = snapshot(guarded_factory)
    report, loaders = run(guarded_factory, **{stage: Mock(side_effect=RuntimeError("private upstream detail"))})
    assert report["error"] and report["source_authorization"]["status"] == "rejected"
    assert snapshot(guarded_factory) == before and report["companies"] == []
    assert "private upstream detail" not in json.dumps(report)
    loaders["raw_loader"].assert_not_called()


def test_facts_commit_failure_stops_evidence_without_changing_data(guarded_factory):
    from sqlalchemy.orm import Session
    before = snapshot(guarded_factory)
    def fail(s):
        if any(isinstance(a, RefreshAttempt) and a.stream == "facts" and a.status == "no_change" for a in s.dirty):
            raise RuntimeError("Isolated no-change commit failure")
    event.listen(Session, "before_commit", fail)
    try: report, loaders = run(guarded_factory)
    finally: event.remove(Session, "before_commit", fail)
    assert report["error"] and len(report["companies"]) == 1
    assert report["companies"][0]["commit_outcome"] == "rolled_back"
    loaders["raw_loader"].assert_not_called()
    after = snapshot(guarded_factory)
    for table in ("financial_facts", "filing_chunks", "filing_publications"):
        assert before[table] == after[table]


def test_inventory_drift_after_facts_cannot_publish_or_start_evidence_attempt(guarded_factory):
    def drift(report):
        if len(report["companies"]) == 1:
            with guarded_factory() as s, s.begin():
                s.get(FilingPublication, (CIK, EXISTING.accession_number)).filename = "unmanaged-drift.htm"
    report, loaders = run(guarded_factory, on_progress=drift)
    assert report["error"] == "canary_existing_filing_mismatch" and len(report["companies"]) == 1
    loaders["raw_loader"].assert_not_called()
    with guarded_factory() as s:
        assert len(list(s.scalars(select(RefreshAttempt)))) == 1
        assert s.get(FilingPublication, (CIK, TARGET.accession_number)) is None


def test_unvalidated_stream_call_is_rejected_before_dml(guarded_factory):
    from app.refresh_service import coordinator, refresh_stream
    from app.refresh_scope import SourceScopeError
    before = snapshot(guarded_factory)
    with coordinator(guarded_factory) as owned, pytest.raises(SourceScopeError):
        refresh_stream(guarded_factory, "AAPL", CIK, "facts", request(), "not-a-real-run", owned,
                       lambda c: source(), lambda c: inventory(), raw_submission, encoder)
    assert snapshot(guarded_factory) == before


def test_cli_passes_optin_to_real_coordinator(guarded_factory, monkeypatch, tmp_path):
    from scripts.refresh_data import main as cli
    from app import sec_client, refresh_service
    monkeypatch.setattr("app.database.SessionLocal", guarded_factory)
    monkeypatch.setattr("scripts.setup_demo.check_schema", lambda s: None)
    monkeypatch.setattr("scripts.sync_financial_facts.report_path", lambda p: tmp_path / "report.json")
    monkeypatch.setattr(sec_client, "get_sec_headers", lambda: {})
    seen = []
    def response(url):
        seen.append(url)
        if "companyfacts" in url: return Mock(json=lambda **kwargs: source())
        if "submissions" in url:
            return Mock(json=lambda: {"cik": 320193, "filings": {"recent": {
                "form": [m.form for m in (TARGET, EXISTING)],
                "accessionNumber": [m.accession_number for m in (TARGET, EXISTING)],
                "filingDate": [m.filed.isoformat() for m in (TARGET, EXISTING)],
                "primaryDocument": [m.primary_document for m in (TARGET, EXISTING)]}}})
        assert TARGET.accession_number in url
        return Mock(text=raw_submission())
    monkeypatch.setattr(sec_client, "_sec_get", response)
    real_refresh = refresh_service.refresh
    monkeypatch.setattr(refresh_service, "refresh", lambda *a, **kw: real_refresh(*a, encoder=encoder, **kw))
    assert cli(["--ticker", "AAPL", "--stream", "both", "--allow-network", "--publication-scope", SCOPE,
                "--max-filings", "1", "--max-seconds", "300", "--max-run-seconds", "600"]) == 0
    report = json.loads((tmp_path / "report.json").read_text())
    assert report["source_authorization"]["status"] == "validated"
    assert len(seen) == 3  # Frozen mocked Company Facts, inventory, raw; no refetch.


@pytest.mark.parametrize("args", [["--all"], ["--all", "--bootstrap"], ["--show-run", "old"]])
def test_cli_cannot_silently_ignore_guard(args):
    from scripts.refresh_data import main as cli
    with pytest.raises(SystemExit) as exc:
        cli([*args, "--publication-scope", SCOPE])
    assert exc.value.code == 2
