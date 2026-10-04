"""Company availability is derived from embedded filing chunks in one query."""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app import main
from app.models import Company, FilingChunk


def add_chunks(session, cik, accession, count, *, embedded):
    for index in range(count):
        session.add(FilingChunk(
            company_cik=cik,
            accession_number=accession,
            form="10-Q",
            filename="fixture.htm",
            chunk_index=index,
            chunk_id=f"chunk_{index:04d}",
            text="Synthetic filing text.",
            start_char=index * 100,
            end_char=index * 100 + 22,
            sec_url="https://www.sec.gov/Archives/fixture.htm",
            embedding=[0.1] * 384 if embedded else None,
        ))


def test_company_availability_and_single_query(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    monkeypatch.setattr(main, "SessionLocal", sessionmaker(bind=engine))

    with Session(engine) as session:
        session.add_all([
            Company(ticker="AAPL", name="Apple Inc.", cik="0000320193", exchange="NASDAQ"),
            Company(ticker="MSFT", name="Microsoft", cik="0000789019", exchange="NASDAQ"),
            Company(ticker="NVDA", name="NVIDIA", cik="0001045810", exchange="NASDAQ"),
            Company(ticker="V", name="Visa", cik="0001403161", exchange="NYSE"),
        ])
        add_chunks(session, "0000320193", "accession-a", 37, embedded=True)
        add_chunks(session, "0000320193", "accession-b", 2, embedded=True)
        add_chunks(session, "0000789019", "accession-c", 3, embedded=False)
        add_chunks(session, "0001045810", "accession-d", 1, embedded=True)
        session.commit()

    statements = []
    def count_queries(_conn, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().lower().startswith("select"):
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", count_queries)
    try:
        companies = {company.ticker: company for company in main.get_companies()}
    finally:
        event.remove(engine, "before_cursor_execute", count_queries)
        engine.dispose()

    assert len(statements) == 1
    assert list(companies) == ["AAPL", "MSFT", "NVDA", "V"]
    assert companies["AAPL"].has_indexed_filing is True
    assert companies["AAPL"].indexed_filing_count == 2
    assert companies["MSFT"].has_indexed_filing is False
    assert companies["MSFT"].indexed_filing_count == 0
    assert companies["NVDA"].indexed_filing_count == 1
    assert companies["V"].has_indexed_filing is False
    assert companies["V"].indexed_filing_count == 0
    assert companies["AAPL"].model_dump(include={"id", "ticker", "name", "cik", "exchange"}) == {
        "id": 1,
        "ticker": "AAPL",
        "name": "Apple Inc.",
        "cik": "0000320193",
        "exchange": "NASDAQ",
    }


def test_one_accession_with_37_embedded_chunks_counts_once(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    monkeypatch.setattr(main, "SessionLocal", sessionmaker(bind=engine))
    with Session(engine) as session:
        session.add(Company(ticker="AAPL", name="Apple Inc.", cik="0000320193", exchange="NASDAQ"))
        add_chunks(session, "0000320193", "accession-a", 37, embedded=True)
        session.commit()
    try:
        company = main.get_companies()[0]
        assert company.has_indexed_filing is True
        assert company.indexed_filing_count == 1
    finally:
        engine.dispose()
