# System architecture

## Scope and modules

Ingestion and answering are separate. Questions read stored chunks scoped by company CIK and accession; they do not download filings or recreate embeddings.

| Responsibility | Implementation |
|---|---|
| API and error mapping | `backend/app/main.py` |
| SEC / metric import | `sec_client.py`, `sec_importer.py` |
| Document extraction / cleanup / chunking | `sec_parser.py` |
| Persistence / embeddings | `sec_filing_service.py`, `embedding_service.py` |
| Retrieval / evidence | `filing_search_service.py`, `evidence_policy.py` |
| Context / answers | `rag_context_service.py`, `answer_service.py` |
| ORM / migrations | `models.py`, `backend/migrations/` |
| UI / client | `frontend/app/page.tsx`, `frontend/lib/finlens-api.ts` |

Backend module filenames are relative to `backend/app` unless stated otherwise.

## Data paths

Company Facts contains multiple concepts for a metric. The importer normalizes supported revenue concepts, net income, and diluted EPS; retains units, periods, and provenance; and deduplicates records. Prior-year analysis uses fiscal/period information and date/duration constraints rather than calendar-quarter assumptions.

EDGAR submissions contain multiple documents. The parser selects the primary document for the requested form. BeautifulSoup removes scripts, styles, inline XBRL headers, and hidden elements. Whitespace is normalized. Chunking uses 2,500 characters with 250-character overlap; offsets refer to cleaned text.

Chunks retain company, accession, form, date, filename, identity/index, offsets, text, and SEC URL. MiniLM produces 384-dimensional vectors persisted in pgvector and reused per question.

## Retrieval and evidence

The original question is embedded. Bounded lexical normalization and financial aliases complement cosine similarity with phrase matching and meaningful-term coverage. Ranking is `L + 0.6S`, with stable tie breakers.

The context builder considers up to 50 candidates, removes duplicate identities/text, filters evidence, and applies the requested limit. Company/accession scope prevents cross-company evidence. No qualifying chunks means abstention. Thresholds are heuristics, not confidence or entailment guarantees.

## Context, model input, and validation

Passages have complete SOURCE/END SOURCE boundaries and IDs mapped to stored metadata. Partial overlap remains intact. The answer service verifies matching blocks/metadata and caps input at eight sources and 24,000 characters.

Questions/context are untrusted user-message data beneath policy; no tools are supplied. Responses API uses structured output, `store=false`, 60-second timeout, no automatic retries, and an 8,192-token output budget. Insufficient retrieval and certain advice requests bypass generation.

The model drafts claims with citation IDs. Server checks schema, eligible IDs, nonempty claims, and forbidden generated URLs/markers. It renders markers and returns stored metadata, not model-generated links.

`claim → citation ID → actual SOURCE block → DB chunk → company/accession → official SEC URL`

This proves source identity, not factual support. Real acceptance must compare numbers, percentages, fiscal periods, YoY/sequential comparison, company, and causal wording. Credit failures produced no real claims; the final audit remains incomplete.

## UI, failures, and configuration

The UI selects companies/filings from FastAPI. `has_filing_chunks` distinguishes indexed from metadata-only filings. Next.js proxies `/api/finlens`. Loading, insufficient, and provider-error states are explicit; links use stored SEC URLs.

HTTP 503 indicates unavailable local model configuration, 504 timeout, and 502 upstream or malformed-output failure. Raw provider secrets and model content are not echoed. Search/context remain independent of generation.

SQLAlchemy and Alembic share private `DATABASE_URL`. Compose reads `POSTGRES_PASSWORD` from ignored root `.env` and binds PostgreSQL to loopback. SEC requests use private `SEC_CONTACT_EMAIL`. Public examples have blank AI values. Local credentials and database contents were preserved; real env files, dumps, caches, dependencies, and scratch output are excluded.

## Data preparation on a fresh checkout

No database dump is distributed. Migrations and seeding do not recreate the recorded 37-chunk fixture.

1. Configure private database and SEC contact; start PostgreSQL, apply migrations, and run `backend/seed_companies.py`.
2. Call `app.sec_importer.import_company(company_cik)` from the backend environment. It downloads Company Facts and replaces imported metrics for the selected company.
3. Read `/companies/{ticker}/sources` and choose an actual accession/form. Do not assume the historical AAPL fixture is latest.
4. Load the `Company` in a SQLAlchemy session and call `app.sec_filing_service.ingest_filing_chunks(session, company, accession_number)`. It downloads the filing and replaces its chunks.
5. Call `app.embedding_service.embed_filing_chunks(session, company_cik, accession_number)` to persist vectors.
6. Confirm indexed sources, then use search/context/answer.

These existing functions have network/write effects; use them deliberately. Repository preparation did not run them. There is no automated dataset bootstrap.

## Verification boundary

Recorded: 41 backend tests, 6 frontend tests, lint/build passing, Alembic clean, 37 chunks/37 vectors, and citation lineage checked. Provider mocks test deterministic behavior. Real requests encountered exhausted credits; no successful real claim audit is claimed.
