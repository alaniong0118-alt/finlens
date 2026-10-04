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

After env configuration and `alembic upgrade head`, run `python -m scripts.setup_demo` from backend. See the root [Quick Start](../README.md#quick-start). No database dump or manual internal service calls are needed.

The command validates schema and Alembic head, reuses company seeding, and prepares the fixed official AAPL 10-Q `0000320193-26-000020`. It filters Company Facts by accession before reusing the existing metric normalizer/deduplicator, inserts only this filing's absent facts, then calls the existing chunk ingestion and embedding services. It does not invoke the replacing company importer.

Complete chunks/vectors are validated with no network/model call. Missing vectors are backfilled within the company/accession scope. Missing or invalid SEC contact is rejected before SEC requests; OpenAI credentials are never required. The first encoder use may download MiniLM. Errors do not reset the database; reruns resume from stored chunks.

The existing parser, retrieval thresholds, answer API, embedding model, and vector dimensions are unchanged. The setup is a single public filing fixture, not multi-company ingestion.

## Catalog filing indexing

`backend/scripts/index_catalog.py` delegates to `catalog_indexing_service.py`. It reads the stored company catalog, validates existing chunks/vectors, skips complete coverage without network/model calls, and resumes missing embeddings. For companies without chunks, `sec_client.py` discovers an exact 10-Q/10-K through official submissions metadata. The existing `sec_filing_service.py` accepts that metadata and a non-replacing persistence option, reusing the same parser and chunker. Existing legacy callers retain their original interface.

Chunks commit per filing before scoped embedding work. A company failure rolls back its current transaction and is classified in the report; subsequent companies continue. Committed chunks can be resumed without re-downloading. No financial fact import, schema change, OpenAI dependency, availability override, or new ingestion store is involved. Invalid persisted metadata/vectors are reported rather than replaced. The database is the recovery source of truth; report files describe each run.

`/sources` merges metadata from facts and chunks in three bounded queries (company, facts, distinct chunk metadata), exposing indexed filings even without financial facts. Financial period fields remain unknown in that case. `/companies` retains its one-query distinct-accession availability aggregation. See [indexing usage](../README.md#catalog-filing-indexing) and [source selection policy](data-sources.md#baseline-catalog-indexing).

## Verification boundary

Recorded: 41 backend tests, 6 frontend tests, lint/build passing, Alembic clean, 37 chunks/37 vectors, and citation lineage checked. Provider mocks test deterministic behavior. Real requests encountered exhausted credits; no successful real claim audit is claimed.

Fresh Docker data directories run `docker/postgres/init-pgvector.sql` to enable pgvector before the existing Alembic revisions. Existing volumes are not reinitialized or removed.
