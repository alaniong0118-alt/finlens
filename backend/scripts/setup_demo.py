"""Prepare one public SEC demo filing. Run from backend: python -m scripts.setup_demo."""
from copy import deepcopy
from datetime import date
import json
import math
import os
import sys

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
import httpx
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import SQLAlchemyError

from app.config import BACKEND_ROOT

# Reproducible public SEC fixture, not fabricated data or a "latest filing" alias.
# Other filings can still be ingested through the existing ingestion services.
DEMO_TICKER = "AAPL"
DEMO_CIK = "0000320193"
DEMO_ACCESSION = "0000320193-26-000020"
DEMO_FORM = "10-Q"
SCHEMA_HELP = "Database schema is incomplete or outdated. Run: python -m alembic upgrade head"


class DemoSetupError(RuntimeError):
    """A safe, actionable CLI error; never includes credentials/provider bodies."""


def check_schema(session) -> None:
    from app.database import Base
    from app import models  # noqa: F401 -- register ORM tables

    connection = session.connection()
    connection.execute(text("SELECT 1"))
    inspector = inspect(connection)
    for table in Base.metadata.sorted_tables:
        if not inspector.has_table(table.name):
            raise DemoSetupError(SCHEMA_HELP)
        columns = {column["name"] for column in inspector.get_columns(table.name)}
        if not set(table.columns.keys()).issubset(columns):
            raise DemoSetupError(SCHEMA_HELP)
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    expected = set(ScriptDirectory.from_config(config).get_heads())
    if set(MigrationContext.configure(connection).get_current_heads()) != expected:
        raise DemoSetupError(SCHEMA_HELP)
    if connection.dialect.name == "postgresql":
        if not connection.scalar(text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname='vector')")):
            raise DemoSetupError(SCHEMA_HELP)


def demo_chunks(session):
    from app.models import FilingChunk
    return list(session.scalars(select(FilingChunk).where(
        FilingChunk.company_cik == DEMO_CIK,
        FilingChunk.accession_number == DEMO_ACCESSION,
    ).order_by(FilingChunk.chunk_index)).all())


def validate_chunks(chunks, *, require_embeddings=False) -> None:
    from app.embedding_service import EMBEDDING_DIMENSION
    from app.sec_client import build_filing_url

    if not chunks:
        raise DemoSetupError("The demo filing produced no chunks. No demo is ready; check SEC access and retry.")
    for index, chunk in enumerate(chunks):
        if (
            chunk.chunk_index != index or chunk.chunk_id != f"chunk_{index:04d}"
            or not chunk.text.strip() or not chunk.filename or not chunk.filed
            or chunk.form != DEMO_FORM or chunk.start_char < 0
            or chunk.end_char <= chunk.start_char
            or chunk.sec_url != build_filing_url(DEMO_CIK, DEMO_ACCESSION)
        ):
            raise DemoSetupError("Existing demo chunk metadata is incomplete; inspect it before re-ingesting. No automatic replacement performed.")
        if chunk.embedding is None:
            if require_embeddings:
                raise DemoSetupError("Demo embeddings are incomplete. Run setup_demo again to resume.")
        elif (len(chunk.embedding) != EMBEDDING_DIMENSION
              or not all(math.isfinite(float(v)) for v in chunk.embedding)
              or not any(float(v) != 0 for v in chunk.embedding)):
            raise DemoSetupError("An existing demo embedding is invalid; inspect it before replacement.")


def ensure_filing_metadata(session) -> bool:
    """Insert only this accession's real facts; never use the replacing importer."""
    from app.models import FinancialFact
    from app.sec_client import get_company_facts
    from app.sec_importer import METRIC_SOURCES, build_metric_data

    existing = session.scalar(select(FinancialFact).where(
        FinancialFact.company_cik == DEMO_CIK,
        FinancialFact.accession_number == DEMO_ACCESSION,
    ))
    if existing is not None:
        if existing.form != DEMO_FORM or existing.filed is None:
            raise DemoSetupError("Existing demo filing metadata is invalid; inspect it before replacing anything.")
        return False
    facts = get_company_facts(DEMO_CIK)
    if str(facts.get("cik", "")).zfill(10) != DEMO_CIK:
        raise DemoSetupError("SEC Company Facts did not match the demo company's CIK.")
    # Filter BEFORE deduplication: later filings must not displace our fixed fixture.
    scoped = deepcopy(facts)
    for concept in scoped.get("facts", {}).get("us-gaap", {}).values():
        for unit, items in concept.get("units", {}).items():
            concept["units"][unit] = [item for item in items
                                     if item.get("accn") == DEMO_ACCESSION
                                     and item.get("form") == DEMO_FORM]
    added = 0
    for metric, source in METRIC_SOURCES.items():
        for item in build_metric_data(scoped, metric, source["facts"], source["unit"]):
            for field in ("period_start", "period_end", "filed"):
                item[field] = date.fromisoformat(item[field]) if item[field] else None
            if item["filed"] is None:
                raise DemoSetupError("SEC demo facts are missing the filing date.")
            session.add(FinancialFact(company_cik=DEMO_CIK, **item))
            added += 1
    if not added:
        raise DemoSetupError("The fixed demo accession was not found in SEC Company Facts. No alternative or fabricated filing was used.")
    session.commit()
    return True


def setup_demo(session=None) -> dict:
    if session is None:
        from app.database import SessionLocal
        with SessionLocal() as local:
            return setup_demo(local)

    from app.models import Company, FinancialFact
    from app.sec_client import get_sec_headers
    from app.sec_filing_service import ingest_filing_chunks
    from app.embedding_service import embed_filing_chunks
    from seed_companies import seed_companies

    check_schema(session)
    chunks = demo_chunks(session)
    metadata = session.scalar(select(FinancialFact.id).where(
        FinancialFact.company_cik == DEMO_CIK,
        FinancialFact.accession_number == DEMO_ACCESSION,
    ))
    if chunks:
        validate_chunks(chunks)
    if not chunks or metadata is None:
        # Completed/backfill paths need no SEC request and may run offline.
        get_sec_headers()
    seed_companies(session, quiet=True)
    company = session.scalar(select(Company).where(Company.ticker == DEMO_TICKER))
    if company is None or company.cik != DEMO_CIK:
        raise DemoSetupError("AAPL seed identity does not match the SEC demo CIK.")
    downloaded_metadata = ensure_filing_metadata(session)
    action = "already_complete"
    if not chunks:
        print("Preparing the fixed AAPL SEC filing...", flush=True)
        ingest_filing_chunks(session, company, DEMO_ACCESSION)
        chunks = demo_chunks(session)
        validate_chunks(chunks)
        action = "ingested"
    missing = sum(chunk.embedding is None for chunk in chunks)
    embedded = 0
    if missing:
        print("Generating missing MiniLM embeddings (first use may download the model)...", flush=True)
        embedded = embed_filing_chunks(session, DEMO_CIK, DEMO_ACCESSION)
        if action == "already_complete":
            action = "backfilled_embeddings"
    session.expire_all()
    chunks = demo_chunks(session)
    validate_chunks(chunks, require_embeddings=True)
    return {
        "status": "ready", "action": action, "ticker": DEMO_TICKER,
        "accession_number": DEMO_ACCESSION, "form": DEMO_FORM,
        "chunks": len(chunks), "embeddings": len(chunks),
        "new_embeddings": embedded, "metadata_downloaded": downloaded_metadata,
        "openai_required": False,
    }


def main() -> int:
    if not os.getenv("DATABASE_URL", "").strip():
        print("DATABASE_URL is required. Set it in backend/.env.", file=sys.stderr)
        return 1
    try:
        result = setup_demo()
    except DemoSetupError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except ValueError:
        # Contact validation may contain user input in other exception variants;
        # do not echo arbitrary parser/config exceptions or connection URLs.
        from app.sec_client import get_sec_headers
        try:
            get_sec_headers()
        except ValueError:
            print("SEC_CONTACT_EMAIL is required for SEC requests.\nSet it in backend/.env.", file=sys.stderr)
        else:
            print("Demo source/configuration validation failed. Check the configured database and SEC filing; existing rows are preserved.", file=sys.stderr)
        return 1
    except SQLAlchemyError:
        print("Database connection/schema check failed. Check DATABASE_URL, start PostgreSQL, then run python -m alembic upgrade head.", file=sys.stderr)
        return 1
    except httpx.HTTPError:
        print("SEC request failed. Check SEC_CONTACT_EMAIL and network access; wait before retrying. No fake data was substituted.", file=sys.stderr)
        return 1
    except Exception:
        print("Demo setup could not complete. Check dependencies and network access for SEC/MiniLM, then rerun to resume. Credentials were not logged.", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    print("Demo ready. OpenAI API key is only required for live generated answers.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
