"""Offline catalog verification, insert-only seeding, and DB-derived availability."""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker

from app import main
from app.database import Base
from app.models import Company, FilingChunk, FinancialFact
from seed_companies import COMPANIES, seed_companies


LEGACY_CIKS = {
    "AAPL": "0000320193", "AMZN": "0001018724", "GOOGL": "0001652044",
    "JPM": "0000019617", "META": "0001326801", "MSFT": "0000789019",
    "NVDA": "0001045810", "TSLA": "0001318605", "V": "0001403161", "WMT": "0000104169",
}
ADDED_TICKERS = set("BAC GS MS MA AXP COST HD KO PEP MCD DIS JNJ LLY MRK ABBV UNH XOM CVX COP CAT GE HON UPS GM F".split())
EXPECTED_TICKERS = set(LEGACY_CIKS) | ADDED_TICKERS


@pytest.fixture
def session(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    monkeypatch.setattr(main, "SessionLocal", sessionmaker(bind=engine))
    with Session(engine) as session:
        yield session
    engine.dispose()


def snapshot(session, model):
    return [
        {column.name: str(getattr(row, column.name)) for column in model.__table__.columns}
        for row in session.scalars(select(model).order_by(model.id))
    ]


def test_catalog_exact_set_unique_identities_and_verified_sec_records():
    assert len(COMPANIES) == 35
    assert {row["ticker"] for row in COMPANIES} == EXPECTED_TICKERS
    assert len({row["ticker"] for row in COMPANIES}) == 35
    assert len({row["cik"] for row in COMPANIES}) == 35
    assert all(len(row["cik"]) == 10 and row["cik"].isdigit() for row in COMPANIES)
    assert {row["ticker"]: row["cik"] for row in COMPANIES[:10]} == LEGACY_CIKS

    evidence = json.loads((Path(__file__).parents[1] / "reports/company_catalog_verification.json").read_text(encoding="utf-8"))
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
    assert len(before) == 35
    seed_companies(session, quiet=True)
    assert snapshot(session, Company) == before
    assert session.scalar(select(func.count()).select_from(FinancialFact)) == 0
    assert session.scalar(select(func.count()).select_from(FilingChunk)) == 0


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
    assert len(first_run) == 35
    assert first_run[:10] == old_companies
    seed_companies(session, quiet=True)
    assert snapshot(session, Company) == first_run
    assert snapshot(session, FinancialFact) == facts
    assert snapshot(session, FilingChunk) == chunks

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
    assert all(not companies[ticker].has_indexed_filing and companies[ticker].indexed_filing_count == 0 for ticker in ADDED_TICKERS)


@pytest.mark.parametrize("ticker,cik", [("AAPL", "9999999999"), ("OTHER", "0000886982")])
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
    assert session.scalar(select(func.count()).select_from(Company)) == 36
