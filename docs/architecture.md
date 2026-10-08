# System architecture

## Scope and modules

Ingestion and answering are separate. Questions read stored chunks scoped by company CIK and accession; they do not download filings or recreate embeddings.

| Responsibility | Implementation |
|---|---|
| API and error mapping | `backend/app/main.py` |
| SEC / metric import | `sec_client.py`, `sec_importer.py`, `financial_sync_service.py`; `scripts/sync_financial_facts.py` |
| Canonical financial metrics | `financial_metric_registry.py`, `financial_metrics_service.py`, `financial_metric_schemas.py` |
| Document extraction / cleanup / chunking | `sec_parser.py` |
| Persistence / embeddings | `sec_filing_service.py`, `embedding_service.py` |
| Retrieval / evidence | `filing_search_service.py`, `evidence_policy.py` |
| Context / answers | `rag_context_service.py`, `answer_service.py` |
| ORM / migrations | `models.py`, `backend/migrations/` |
| Workspace / typed client | `frontend/app/page.tsx`, `frontend/lib/finlens-api.ts` |
| Research presentation | `frontend/components/company-overview.tsx`, `financial-research.tsx`, `filing-research.tsx`; `frontend/lib/research.ts` |
| Application theme | `frontend/components/theme-control.tsx`, `frontend/app/layout.tsx`, `globals.css` |

Backend module filenames are relative to `backend/app` unless stated otherwise.

## Data paths

Company Facts contains multiple concepts and filing vintages for a metric. The importer collects the existing reviewed base concepts/units, validates precision/metadata and merges exact source identities without deleting rows or choosing period winners. The sequential catalog sync commits per company under a PostgreSQL transaction lock, reports coverage/failures and resumes from stored identities. Item 6 resolves scope, restatements and compatible periods after ingestion; see [sync policy](data-sources.md#structured-financial-sync). Legacy financial interfaces retain their existing contracts.

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

The UI selects companies/filings from FastAPI. `has_filing_chunks` distinguishes indexed from metadata-only filings. Next.js proxies `/api/finlens`. Company Research reads one standardized summary and one selected history (12 points), using existing Recharts bars plus a source-backed table. Six primary cards share the summary; expanding provenance performs no fetch. Dates, units, availability, revenue basis and EPS warnings follow the server contracts; no financial calculations or period selection are recreated in the browser.

SEC Research reads the selected company's source metadata, then GET context only on submit. Presentation parses the existing SOURCE boundaries, keeps rank/citation identity, and shows exact filing excerpts with compact previews/full disclosures. It does not rerank evidence. An explicit optional AI action POSTs to the existing answer endpoint; success renders answer/claims/stored citations. Its separate state cannot remove evidence on failure. Company/filing keys remount scoped state, requests abort on cleanup, and search/AI generation use monotonic request invalidation to discard late results.

Deterministic Research Answers use typed `POST /companies/{ticker}/research-answer` with a bounded question body. `research_answer_service.py` uses explicit presentation aliases and closed residual vocabularies for latest values and historical/comparison intents, rejecting unsupported qualifiers, arbitrary dates, causes and multiple metrics. Catalog names/tickers establish company mismatch safety; the selected company always owns the response. Financial definitions, units, formulas, period classification, scope and fact selection remain exclusively in the existing registry/FinancialMetrics service. A matched request performs two SELECTs (catalog and selected company facts); rejected questions perform one. No retrieval, provider configuration, embeddings, external call, schema or second metric store is involved.

Explicit quarter/annual resolves the existing summary observation; latest available requests up to one newest normalized history observation per applicable actual kind in memory and selects by end/start dates, including unavailable observations. Instant latest is as-of; explicit reporting-period balance sheets match the summary end. The response wraps the unchanged NormalizedMetric (exact Decimal value, period, reason, provenance, alternatives and derived inputs), display text, match/status/intent, label and EPS comparability metadata. Research Answer UI only presents these server fields.

On submit the frontend starts this answer POST alongside the existing context GET. Each promise updates independent loading/result/error state before aggregate settlement, so cold embeddings or evidence failure cannot delay or erase a direct answer. Version guards, aborts, company/filing remounts and response ticker/question/accession checks prevent stale delivery. Without an indexed filing the same form can request a direct answer alone. Supporting evidence is explicitly selected-filing scope and appears after direct answer/provenance; optional AI appears after evidence and cannot remove either result.

`GET /capabilities` returns typed `research_mode` and `ai_analysis_configured` booleans only. It checks nonempty server configuration without database access, SDK construction or a provider probe. A configured key is not an availability guarantee. Missing/unknown capability disables optional generation, and any generation failure displays neutral copy while preserving research. No external provider call occurs during metrics, history, source selection or context retrieval.

Light/Dark/System preference is stored under `finlens-theme`. A static pre-paint script resolves preference/OS appearance; the client handles later media/storage changes. Semantic CSS variables style the entire workspace, including chart axes/tooltips. No theme library or dependency was added. Responsive layouts stack below 1100px, reflow cards, wrap metadata and contain history-table overflow. Chart tables, labelled controls, native disclosures, skip link, live states and focus-visible outlines supply accessible alternatives.

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

## Standardized financial metrics

The read-only metrics service loads a company's stored facts once, resolves original concepts and revenue economic scope, selects compatible date-based periods and calculates Decimal ratios/FCF with input provenance. Ambiguous years remain null; unapproved revenue bases cannot produce consolidated margins or incompatible YoY growth. EPS history exposes unverified share-basis comparability. Dedicated typed `/financials/summary` and `/financials/metrics/{metric}` routes preserve legacy financial APIs. No normalized table, migration or AI dependency is required. Item 7 supplies structured facts for all 35 issuers while preserving the original observations; normalized metric availability remains separate from filing readiness and source presence. See [metric contracts and limitations](financial-metrics.md) and [current all-company verification](../backend/reports/structured_financial_verification.json).

## Evidence presentation

`frontend/lib/evidence-presentation.ts` chooses a window inside each already-retrieved SOURCE passage. Bounded phrase/value anchors score local windows; method queries favor reporting/accounting phrases, amount queries favor exact numeric matches and nearby metric labels. It does not reorder passages, validate truth, summarize, or change Evidence Policy. React renders text segments with semantic `mark` elements; no raw HTML is interpreted. Full source text remains unaltered behind native disclosures.

Numeric display matching compares decimal strings without floating-point rounding. USD scale requires an explicit amount suffix or a nearby preceding table declaration, bounded by note/page/per-share boundaries. Overlap may carry a missing declaration only through an identical row fragment in another supplied passage with consistent units. Percent and explicit EPS matches preserve their units; unknown scale and rounded-only values fall back to text. This comparison is separate from backend metric selection and provenance. Marks are explicitly labelled as matches, not evidence entailment.

EvidenceResults shows two ranked cards by default, with local expansion state reset by research scope. All preview computation and disclosures use existing responses and make no requests. DirectResearchAnswer retains backend values, reasons, basis and EPS warnings with collapsed provenance. See [presentation acceptance](answer-presentation-verification.md).

## Historical and comparative answers

The same endpoint adds `answer_kind` (`latest_metric`, `historical_metric`, `period_comparison`), requested fiscal labels and an optional typed comparison. Bounded recognition extracts one explicit year/quarter or two with a comparison connector, then rejects residual causal/method/unknown vocabulary. The existing latest grammar and company checks remain intact.

`FinancialMetrics.fiscal_observation` selects one unique normalized fiscal label from shared existing anchors, then calls `observation`; instant metrics match the reporting end. `compare_fiscal` owns aligned dates/durations, units, revenue/input scope and Decimal arithmetic. Annual and same-fiscal-quarter comparisons require chronological years; fiscal calendar shifts, ambiguous labels and mixed kinds produce reasons. Existing latest-filed exact-period source selection and alternatives are retained, not a reconstructed as-of vintage.

The response carries both complete NormalizedMetric operands, exact absolute/percentage changes, percentage status/reason and direction. Ratio differences display as percentage points; nonpositive baselines and unverified EPS do not receive percentage-growth claims. Frontend renders these fields using existing formatting/provenance components and performs no financial selection or calculation. Comparison responses intentionally have no single `observation`; historical/comparison supporting excerpts use phrase highlights only, avoiding false period validation. Existing independent requests, remount keys and response guards are unchanged. See [contracts](financial-metrics.md#historical-values-and-comparisons), [verification](../backend/reports/historical_answers_final_report.md) and [completed plan](exec-plans/completed/2026-10-08-historical-comparative-research-answers.md).

## Verification boundary

Historical MVP: 41 backend tests, 6 frontend tests, lint/build passing, Alembic clean, 37 AAPL chunks/vectors and citation lineage checked. Later Item 7 established current catalog/data coverage; Item 8 adds 19 frontend tests, four focused capability tests and real no-key browser/theme/responsive acceptance. See [Research Mode verification](../backend/reports/research_mode_verification.json). The provider-failure browser fixture is controlled, not a live AI run. Real requests previously encountered exhausted credits; no successful real claim audit is claimed.

Fresh Docker data directories run `docker/postgres/init-pgvector.sql` to enable pgvector before the existing Alembic revisions. Existing volumes are not reinitialized or removed.
