"""Orchestration tests: real ORM/parser/services, in-memory DB, mocked networks/encoder."""
from datetime import date
from decimal import Decimal
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Company, FilingChunk, FinancialFact
from app import embedding_service, sec_client, sec_filing_service
from scripts import setup_demo as demo


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)"))
        connection.execute(text("INSERT INTO alembic_version VALUES ('d7b834408ba8')"))
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture(autouse=True)
def external_calls(monkeypatch):
    # Synthetic contact exists only in this isolated test; no SEC traffic is sent.
    monkeypatch.setenv("SEC_CONTACT_EMAIL", "fixture@university.edu")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    calls = {}
    for module, name in [(sec_client, "get_company_facts"),
                         (sec_filing_service, "get_filing_raw_text"),
                         (embedding_service, "embed_texts")]:
        calls[name] = Mock(side_effect=AssertionError("Unexpected external operation"))
        monkeypatch.setattr(module, name, calls[name])
    return calls


def fact(cik=demo.DEMO_CIK, accession=demo.DEMO_ACCESSION):
    return FinancialFact(company_cik=cik, metric="Revenues", value=Decimal("100"),
                         unit="USD", period_start=date(2026, 3, 29),
                         period_end=date(2026, 6, 27), period_type="quarter",
                         fiscal_year=2026, fiscal_period="Q3", form="10-Q",
                         filed=date(2026, 7, 31), accession_number=accession,
                         source="Synthetic unit-test fixture")


def chunk(index=0, embedded=True, cik=demo.DEMO_CIK, accession=demo.DEMO_ACCESSION):
    return FilingChunk(company_cik=cik, accession_number=accession, form="10-Q",
                       filename="fixture.htm", filed=date(2026, 7, 31),
                       chunk_index=index, chunk_id=f"chunk_{index:04d}",
                       text="Synthetic test source text.", start_char=index * 2250,
                       end_char=index * 2250 + 100,
                       sec_url=sec_client.build_filing_url(cik, accession),
                       embedding=[1.0] * 384 if embedded else None)


def existing_demo(session, *, embedded=True):
    session.add(Company(ticker="AAPL", name="Apple Inc.", cik=demo.DEMO_CIK, exchange="NASDAQ"))
    session.add(fact())
    session.add(chunk(embedded=embedded))
    session.commit()


def test_complete_fast_path_no_network_no_model(session, external_calls, monkeypatch):
    existing_demo(session)
    monkeypatch.delenv("SEC_CONTACT_EMAIL")
    result = demo.setup_demo(session)
    assert result["action"] == "already_complete"
    assert result["chunks"] == result["embeddings"] == 1
    assert result["openai_required"] is False
    for call in external_calls.values():
        call.assert_not_called()
    again = demo.setup_demo(session)
    assert again == result


def test_backfill_only_preserves_existing_vector(session, external_calls, monkeypatch):
    existing_demo(session)
    session.add(chunk(index=1, embedded=False))
    session.commit()
    monkeypatch.delenv("SEC_CONTACT_EMAIL")
    encoder = external_calls["embed_texts"]
    encoder.side_effect = lambda texts: [[0.5] * 384 for _ in texts]
    result = demo.setup_demo(session)
    assert result["action"] == "backfilled_embeddings"
    assert result["new_embeddings"] == 1
    rows = demo.demo_chunks(session)
    assert list(rows[0].embedding) == [1.0] * 384
    assert list(rows[1].embedding) == [0.5] * 384
    external_calls["get_company_facts"].assert_not_called()
    external_calls["get_filing_raw_text"].assert_not_called()
    assert len(encoder.call_args.args[0]) == 1


@pytest.mark.parametrize("contact", ["", "not-an-email", "YOUR_EMAIL@example.com", "a@b.invalid", "a@b.com\r\nx: y"])
def test_invalid_contact_fails_before_seed_or_network(session, external_calls, monkeypatch, contact):
    monkeypatch.setenv("SEC_CONTACT_EMAIL", contact)
    with pytest.raises(ValueError, match="SEC_CONTACT_EMAIL is required for SEC requests"):
        demo.setup_demo(session)
    assert session.scalar(select(Company.id)) is None
    for call in external_calls.values():
        call.assert_not_called()


def wire_fresh_source(calls):
    record = {"start": "2026-03-29", "end": "2026-06-27", "val": 100,
              "accn": demo.DEMO_ACCESSION, "fy": 2026, "fp": "Q3",
              "form": "10-Q", "filed": "2026-07-31"}
    # A later filing reports the same period: filter by accession BEFORE dedup.
    later = {**record, "accn": "later-filing", "filed": "2026-10-01", "val": 999}
    calls["get_company_facts"].side_effect = None
    calls["get_company_facts"].return_value = {
        "cik": 320193, "facts": {"us-gaap": {"Revenues": {"units": {"USD": [record, later]}}}}}
    calls["get_filing_raw_text"].side_effect = None
    calls["get_filing_raw_text"].return_value = (
        '<DOCUMENT>\n<TYPE>10-Q\n<FILENAME>fixture.htm\n<TEXT><html><body>'
        '<ix:header>hidden metadata</ix:header><p>'
        + "Synthetic services revenue text. " * 120
        + '</p></body></html></TEXT>\n</DOCUMENT>'
    )
    calls["embed_texts"].side_effect = lambda texts: [[0.5] * 384 for _ in texts]


def test_empty_database_no_openai_and_no_model_cache(session, external_calls):
    wire_fresh_source(external_calls)
    result = demo.setup_demo(session)
    assert result["action"] == "ingested"
    assert result["chunks"] == result["embeddings"] > 0
    assert result["openai_required"] is False
    assert len(list(session.scalars(select(Company)))) == 10  # existing seed list only
    facts = list(session.scalars(select(FinancialFact)))
    assert len(facts) == 1 and facts[0].value == 100
    assert facts[0].accession_number == demo.DEMO_ACCESSION
    assert "hidden metadata" not in demo.demo_chunks(session)[0].text
    external_calls["get_company_facts"].assert_called_once_with(demo.DEMO_CIK)
    external_calls["get_filing_raw_text"].assert_called_once_with(demo.DEMO_CIK, demo.DEMO_ACCESSION)
    assert demo.setup_demo(session)["action"] == "already_complete"
    assert external_calls["get_filing_raw_text"].call_count == 1


def test_unrelated_company_and_same_company_other_filing_preserved(session, external_calls):
    wire_fresh_source(external_calls)
    session.add(Company(ticker="V", name="Existing custom name", cik="0001403161", exchange="NYSE"))
    session.add_all([fact("0001403161", "unrelated"), fact(accession="other-apple-filing"),
                     chunk(cik="0001403161", accession="unrelated"),
                     chunk(accession="other-apple-filing")])
    session.commit()
    def snapshot():
        return {model.__name__: [
            tuple(str(getattr(row, c.name)) for c in model.__table__.columns)
            for row in session.scalars(select(model).where(model.accession_number != demo.DEMO_ACCESSION).order_by(model.id))
        ] for model in (FinancialFact, FilingChunk)}
    before = snapshot()
    demo.setup_demo(session)
    assert snapshot() == before
    assert session.scalar(select(Company.name).where(Company.ticker == "V")) == "Existing custom name"


@pytest.mark.parametrize("missing", ["table", "column", "revision"])
def test_schema_missing_is_non_destructive(session, external_calls, missing):
    # Destructive statements are restricted to this test's disposable in-memory DB.
    if missing == "table":
        session.execute(text("DROP TABLE filing_chunks"))
    elif missing == "column":
        session.execute(text("ALTER TABLE filing_chunks DROP COLUMN embedding"))
    else:
        session.execute(text("UPDATE alembic_version SET version_num='77068e51af12'"))
    session.commit()
    with pytest.raises(demo.DemoSetupError, match="alembic upgrade head"):
        demo.setup_demo(session)
    assert session.scalar(select(Company.id)) is None
    for call in external_calls.values():
        call.assert_not_called()


def test_missing_public_fixture_never_substitutes_data(session, external_calls):
    external_calls["get_company_facts"].side_effect = None
    external_calls["get_company_facts"].return_value = {"cik": 320193, "facts": {}}
    with pytest.raises(demo.DemoSetupError, match="fixed demo accession was not found"):
        demo.setup_demo(session)
    external_calls["get_filing_raw_text"].assert_not_called()
    external_calls["embed_texts"].assert_not_called()
    assert session.scalar(select(FinancialFact.id)) is None


def test_resume_after_encoder_download_failure(session, external_calls):
    wire_fresh_source(external_calls)
    external_calls["embed_texts"].side_effect = OSError("model download unavailable")
    with pytest.raises(OSError):
        demo.setup_demo(session)
    assert demo.demo_chunks(session)
    external_calls["embed_texts"].side_effect = lambda texts: [[0.5] * 384 for _ in texts]
    assert demo.setup_demo(session)["action"] == "backfilled_embeddings"
    assert external_calls["get_filing_raw_text"].call_count == 1


def test_cli_missing_database_has_clear_error(monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", "")
    assert demo.main() == 1
    assert "DATABASE_URL is required" in capsys.readouterr().err
