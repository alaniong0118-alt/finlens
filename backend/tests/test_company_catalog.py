"""Offline catalog verification, insert-only seeding, and DB-derived availability."""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock

from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import main
from app.database import Base
from app.models import Company, CompanyRefreshState, FilingChunk, FilingPublication, FinancialFact, RefreshAttempt
from app.refresh_contracts import RefreshRequest
from seed_companies import COMPANIES, seed_companies


LEGACY_CIKS = {
    "AAPL": "0000320193", "AMZN": "0001018724", "GOOGL": "0001652044",
    "JPM": "0000019617", "META": "0001326801", "MSFT": "0000789019",
    "NVDA": "0001045810", "TSLA": "0001318605", "V": "0001403161", "WMT": "0000104169",
}
ADDED_TICKERS = set("BAC GS MS MA AXP COST HD KO PEP MCD DIS JNJ LLY MRK ABBV UNH XOM CVX COP CAT GE HON UPS GM F".split())
EXPECTED_TICKERS = set(LEGACY_CIKS) | ADDED_TICKERS | {"AMD"}
AMD_IDENTITY = {
    "ticker": "AMD", "name": "ADVANCED MICRO DEVICES INC",
    "cik": "0000002488", "exchange": "NASDAQ",
}
EVIDENCE_MODELS = (FinancialFact, FilingChunk, FilingPublication, CompanyRefreshState, RefreshAttempt)


@pytest.fixture
def session(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(main, "HttpSessionLocal", sessionmaker(bind=engine))
    with Session(engine) as session:
        yield session
    engine.dispose()


def snapshot(session, model):
    return [
        {column.name: str(getattr(row, column.name)) for column in model.__table__.columns}
        for row in session.scalars(select(model).order_by(model.id))
    ]


def test_catalog_exact_set_unique_identities_and_verified_sec_records():
    assert len(COMPANIES) == 36
    assert {row["ticker"] for row in COMPANIES} == EXPECTED_TICKERS
    assert len({row["ticker"] for row in COMPANIES}) == 36
    assert len({row["cik"] for row in COMPANIES}) == 36
    assert all(len(row["cik"]) == 10 and row["cik"].isdigit() for row in COMPANIES)
    assert {row["ticker"]: row["cik"] for row in COMPANIES[:10]} == LEGACY_CIKS

    evidence = json.loads((Path(__file__).parents[1] / "reports/company_catalog_verification.json").read_text(encoding="utf-8"))
    original = [
        {field: row[field] for field in ("ticker", "name", "cik", "exchange")}
        for row in evidence["after_first_seed"]["all_companies"]
    ]
    assert len(original) == 35
    assert COMPANIES[:35] == original  # Preserve every identity and its order.
    # Phase 2B metadata was verified in the operator-approved conversation,
    # not in the historical 25-addition report. See docs/ai-cov01-amd-catalog.md.
    assert COMPANIES[35:] == [AMD_IDENTITY]
    assert evidence["source_url"] == "https://www.sec.gov/files/company_tickers_exchange.json"
    assert evidence["http_status"] == 200
    verified = {item["sec_record"]["ticker"]: item["sec_record"] for item in evidence["added_companies"]}
    assert set(verified) == ADDED_TICKERS
    for company in COMPANIES:
        if company["ticker"] in verified:
            source = verified[company["ticker"]]
            assert company["name"] == source["name"]
            assert company["cik"] == str(source["cik"]).zfill(10)
            assert company["exchange"] == source["exchange"].upper()


def test_empty_seed_and_repeated_seed_are_idempotent(session):
    seed_companies(session, quiet=True)
    before = snapshot(session, Company)
    assert len(before) == 36
    seed_companies(session, quiet=True)
    assert snapshot(session, Company) == before
    for model in EVIDENCE_MODELS:
        assert session.scalar(select(func.count()).select_from(model)) == 0
    assert session.scalar(select(func.count()).select_from(FilingChunk).where(FilingChunk.embedding.is_not(None))) == 0


def test_legacy_rows_and_evidence_preserved_and_no_fabricated_readiness(session):
    for company in COMPANIES[:10]:
        # Local names must survive; the seed must not replace an existing record.
        session.add(Company(**{**company, "name": "Preserve this name" if company["ticker"] == "MSFT" else company["name"]}))
    session.add(FinancialFact(
        company_cik=LEGACY_CIKS["AAPL"], metric="Revenues", value=Decimal("100"),
        unit="USD", period_start=date(2026, 3, 29), period_end=date(2026, 6, 27),
        period_type="quarter", fiscal_year=2026, fiscal_period="Q3", form="10-Q",
        filed=date(2026, 7, 31), accession_number="test-accession", source="Synthetic test fixture",
    ))
    for index in range(37):
        session.add(FilingChunk(
            company_cik=LEGACY_CIKS["AAPL"], accession_number="test-accession", form="10-Q",
            filename="fixture.htm", chunk_index=index, chunk_id=f"chunk_{index:04d}",
            text="Synthetic test evidence.", start_char=index * 100, end_char=index * 100 + 24,
            sec_url="https://www.sec.gov/Archives/fixture.htm", embedding=[0.1] * 384,
        ))
    session.commit()
    old_companies = snapshot(session, Company)
    facts = snapshot(session, FinancialFact)
    chunks = snapshot(session, FilingChunk)
    seed_companies(session, quiet=True)
    first_run = snapshot(session, Company)
    assert len(first_run) == 36
    assert first_run[:10] == old_companies
    seed_companies(session, quiet=True)
    assert snapshot(session, Company) == first_run
    assert snapshot(session, FinancialFact) == facts
    assert snapshot(session, FilingChunk) == chunks

    from app.models import FilingPublication
    from app.refresh_contracts import utcnow
    session.add(FilingPublication(company_cik=LEGACY_CIKS["AAPL"], accession_number="test-accession", form="10-Q",
        filed=date(2026, 7, 31), filename="fixture.htm", chunk_count=37, content_digest="0"*64,
        configuration="fixture", published_at=utcnow(), data_version=0))
    session.commit()
    queries = []
    def record_select(_conn, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().lower().startswith("select"):
            queries.append(statement)
    event.listen(session.bind, "before_cursor_execute", record_select)
    try:
        companies = {row.ticker: row for row in main.get_companies()}
    finally:
        event.remove(session.bind, "before_cursor_execute", record_select)
    assert len(queries) == 1
    assert set(companies) == EXPECTED_TICKERS
    assert companies["AAPL"].has_indexed_filing is True
    assert companies["AAPL"].indexed_filing_count == 1
    assert all(not companies[ticker].has_indexed_filing and companies[ticker].indexed_filing_count == 0
               for ticker in ADDED_TICKERS | {"AMD"})


@pytest.mark.parametrize("ticker,cik", [
    ("AAPL", "9999999999"), ("OTHER", "0000886982"),
    ("AMD", "9999999999"), ("OTHER", "0000002488"),
])
def test_identity_conflicts_fail_before_catalog_mutation(session, ticker, cik):
    session.add(Company(ticker=ticker, name="Existing issuer", cik=cik, exchange="NYSE"))
    session.commit()
    before = snapshot(session, Company)
    with pytest.raises(ValueError, match="Catalog .* conflict"):
        seed_companies(session, quiet=True)
    assert not session.new
    assert snapshot(session, Company) == before


def test_seed_preserves_unrelated_local_company(session):
    session.add(Company(ticker="CUSTOM", name="Local fixture", cik="9999999999", exchange="NYSE"))
    session.commit()
    before = snapshot(session, Company)[0]
    seed_companies(session, quiet=True)
    assert snapshot(session, Company)[0] == before
    assert session.scalar(select(func.count()).select_from(Company)) == 37


def test_existing_amd_name_and_all_original_rows_survive_repeated_seed(session):
    session.add_all(Company(**row) for row in COMPANIES[:35])
    session.add(Company(**{**AMD_IDENTITY, "name": "Preserve local AMD name"}))
    session.commit()
    before = snapshot(session, Company)
    for _ in range(2):
        seed_companies(session, quiet=True)
        assert snapshot(session, Company) == before
        for model in EVIDENCE_MODELS:
            assert session.scalar(select(func.count()).select_from(model)) == 0


def test_amd_membership_does_not_borrow_nvda_evidence_or_publication_pin(session):
    seed_companies(session, quiet=True)
    # Synthetic NVDA observation and verified version zero: no issuer data is fetched.
    session.add(FinancialFact(
        company_cik=LEGACY_CIKS["NVDA"], metric="Revenues", value=Decimal("100"),
        unit="USD", period_start=date(2025, 1, 1), period_end=date(2025, 12, 31),
        period_type="annual", fiscal_year=2025, fiscal_period="FY", form="10-K",
        filed=date(2026, 2, 1), accession_number="0001045810-26-000001",
        source="SEC Company Facts API: Revenues",
    ))
    session.add(CompanyRefreshState(company_cik=LEGACY_CIKS["NVDA"], data_version=0,
                                   facts_version=0, evidence_version=0, facts={}, evidence={}))
    session.commit()
    before = {model: list(session.execute(select(model.__table__)).all()) for model in EVIDENCE_MODELS}
    client = TestClient(main.app)
    catalog = {row["ticker"]: row for row in client.get("/companies").json()}
    assert catalog["AMD"]["cik"] == AMD_IDENTITY["cik"]
    assert catalog["AMD"]["has_indexed_filing"] is False
    assert catalog["AMD"]["indexed_filing_count"] == 0
    assert client.get("/companies/AMD/sources").json() == []

    nvda_freshness = client.get("/companies/NVDA/freshness")
    assert nvda_freshness.status_code == 200
    assert nvda_freshness.json()["data_version"] == 0
    assert nvda_freshness.headers["X-FinLens-Data-Version"] == "0"
    amd_freshness = client.get("/companies/AMD/freshness")
    assert amd_freshness.status_code == 503
    assert amd_freshness.headers["X-FinLens-Error-Code"] == "FRESHNESS_UNAVAILABLE"
    assert "data_version" not in amd_freshness.json()
    assert "X-FinLens-Data-Version" not in amd_freshness.headers
    assert amd_freshness.headers["Cache-Control"] == "no-store"
    invented_pin = client.get("/companies/AMD/financials/annual", headers={"X-FinLens-Data-Version": "0"})
    assert invented_pin.status_code == 409
    assert invented_pin.headers["X-FinLens-Error-Code"] == "DATA_VERSION_CHANGED"
    assert "X-FinLens-Data-Version" not in invented_pin.headers

    discovery = client.get("/companies/AMD/financials/annual")
    assert discovery.status_code == 200
    assert discovery.json()["fiscal_years"] == [] and discovery.json()["metrics"] == {}
    amd = client.get("/companies/AMD/financials/annual?fiscal_year=2025")
    assert amd.status_code == 200 and amd.json()["company_cik"] == AMD_IDENTITY["cik"]
    assert amd.json()["period"] is None and len(amd.json()["metrics"]) == 11
    assert all(metric["status"] == "unavailable" and metric["value"] is None
               and not metric["provenance"] and not metric["inputs"] for metric in amd.json()["metrics"].values())
    nvda = client.get("/companies/NVDA/financials/annual?fiscal_year=2025",
                      headers={"X-FinLens-Data-Version": "0"})
    assert nvda.status_code == 200 and nvda.json()["company_cik"] == LEGACY_CIKS["NVDA"]
    assert nvda.json()["metrics"]["revenue"]["status"] == "available"
    assert Decimal(nvda.json()["metrics"]["revenue"]["value"]) == Decimal("100")
    assert nvda.json()["metrics"]["gross_margin"]["status"] == "unavailable"
    for model in EVIDENCE_MODELS:
        assert list(session.execute(select(model.__table__)).all()) == before[model]


def test_refresh_request_limit_stays_35():
    original_tickers = [row["ticker"] for row in COMPANIES[:35]]
    assert RefreshRequest(tickers=original_tickers).tickers == original_tickers
    with pytest.raises(ValidationError) as rejected:
        RefreshRequest(tickers=[row["ticker"] for row in COMPANIES])
    assert any(error["loc"] == ("tickers",) and error["type"] == "too_long"
               and error["ctx"]["max_length"] == 35 for error in rejected.value.errors())


@pytest.mark.parametrize("arguments", [["--all", "--allow-network"], ["--all", "--bootstrap"]])
def test_36_company_all_selection_rejects_before_refresh_or_bootstrap(session, monkeypatch, capsys, arguments):
    from app import database, refresh_service, sec_client
    from scripts import refresh_data, setup_demo, sync_financial_facts

    seed_companies(session, quiet=True)
    session_factory = Mock(side_effect=AssertionError("CLI denial must precede DB access"))
    schema_check = Mock(side_effect=AssertionError("CLI denial must precede schema access"))
    monkeypatch.setattr(database, "SessionLocal", session_factory)
    monkeypatch.setattr(setup_demo, "check_schema", schema_check)
    request_factory = Mock(wraps=RefreshRequest)
    monkeypatch.setattr(refresh_data, "RefreshRequest", request_factory)
    forbidden = []
    for module, name in ((refresh_service, "coordinator"), (refresh_service, "refresh"),
                         (refresh_service, "bootstrap_publications"), (sec_client, "get_sec_headers"),
                         (sync_financial_facts, "report_path"), (sync_financial_facts, "write_report")):
        call = Mock(side_effect=AssertionError("Validation must precede operational execution"))
        monkeypatch.setattr(module, name, call)
        forbidden.append(call)
    with pytest.raises(SystemExit) as rejected:
        refresh_data.main(arguments)
    assert rejected.value.code == 2
    assert "Full-catalog refresh and bootstrap are prohibited" in capsys.readouterr().err
    session_factory.assert_not_called()
    schema_check.assert_not_called()
    request_factory.assert_not_called()
    for call in forbidden:
        call.assert_not_called()
    for model in EVIDENCE_MODELS:
        assert session.scalar(select(func.count()).select_from(model)) == 0
