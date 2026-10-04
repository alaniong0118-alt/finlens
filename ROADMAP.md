# FinLens engineering roadmap

FinLens must remain useful without an LLM. AI enhances evidence-based financial research rather than being the product's only source of value.

This is the authoritative milestone/status document. [Product spec](docs/product-spec.md) defines product contracts; [architecture](docs/architecture.md) describes implementation. Complex work requires an [ExecPlan](.agent/PLANS.md). Start only the phase or scoped task requested by the user.

## Current baseline — 2026-10-04

Completed foundations: Item 1 fresh-clone demo setup, Item 2 database-derived indexed availability, and Item 3 research-interface polish (commits `5566344`, `004cdc5`, `641febb`).

**Item 4 — Curated Company Catalog: completed.** The existing seed now contains exactly 35 selected SEC-reporting issuers. All 25 additions were verified against official SEC ticker/name/CIK/exchange metadata; the original 10 company rows were retained unchanged. See [catalog verification](backend/reports/company_catalog_verification.json) for source records, preservation fingerprints, seed/rerun results, tests, and HTTP checks.

Current DB/API inspection: 35 companies, 3,251 financial facts, 3,175 filing chunks and 3,175 embeddings; all 35 companies are Ready with one distinct indexed accession each. AAPL's original 37 chunks/vectors and all original company/fact rows are unchanged by full-row fingerprint checks. Financial history/summary/snapshot and filing search/context APIs exist without OpenAI. The frontend currently centers on single-filing AI Q&A; a complete Research Mode UI, broad normalized metrics, and charts/comparisons remain planned.

**Item 5 — Baseline filing indexing: completed.** The resumable `python -m scripts.index_catalog` command discovers official SEC filings, reuses existing ingestion/embedding services, and preserves facts and complete filings. Five cross-industry canaries preceded the remaining 29 companies; there were no failures. Default rerun skipped all 35 with unchanged whole-table hashes. Representative sources/search/hybrid/context lineage passed for AAPL, MSFT, JPM, JNJ, XOM, WMT; company listing still uses one SELECT. See [indexing run](backend/reports/catalog_indexing_batch.json), [rerun](backend/reports/catalog_indexing.json), and [preservation/API verification](backend/reports/catalog_indexing_verification.json). This completes baseline coverage, not formal retrieval evaluation or live AI claim auditing. Item numbers identify delivery milestones and are distinct from the broader phase numbers below.

OpenAI integration and citation identity checks exist. [Recorded acceptance](backend/reports/final_verification.md) and [evaluation](backend/reports/rag_evaluation.json) show exhausted API credits and no completed real claim audit. Historical test results are scoped evidence, not proof across future companies or filings.

**Item 6 — Standardized Financial Metrics Layer: completed within existing-data scope.** Central registry, date-aware selection, Decimal formulas, typed summary/history APIs and input/source provenance are implemented without modifying facts or schema. The real 35-company audit found structured facts for ten companies only: revenue/net income/YoY revenue growth/net margin available for 10/35, EPS for 9/35, remaining definitions unavailable (JPM gross profit/margin not applicable). Conditional primary concepts/formulas have fixture coverage, not claimed issuer data coverage. All original table hashes remain unchanged; 35 focused tests, 137 backend tests and 44 subtests passed. See [contracts](docs/financial-metrics.md) and [coverage/source verification](backend/reports/financial_metrics_verification.json). Research Mode frontend/dashboard work has not started.

## Phases and exit gates

Phases 1 and 2 are **completed** within their documented baseline/existing-data scope; Phases 3–7 remain **planned**. Preserve working foundations; broader structured-data coverage requires a separately scoped acquisition plan.

| Phase | Deliverable | Completion gate |
|---|---|---|
| 1. Curated catalog and baseline filing coverage | Completed: 35 curated SEC-reporting public companies, each with one usable indexed SEC filing. Verified identity, coverage, indexing/rerun outcomes are recorded. | 35/35 Ready by the DB-derived definition; safe rerun, failure-isolation tests, original-data preservation, and representative lineage checks passed. |
| 2. Financial Metrics Layer | Completed: canonical registry and typed API over existing SEC facts, period-aware selection, deterministic calculations and source/input provenance. | Unit/period/restatement/formula fixtures, 35-company coverage audit, representative available/missing-source checks, bounded queries and preservation passed. Broader issuer/concept data coverage remains limited and explicit. |
| 3. Complete Research Mode | Metrics, historical trends, charts, comparisons, filing discovery, hybrid search, evidence excerpts, and official SEC links in the frontend. | The end-to-end research workflow is useful with no LLM or OpenAI key. Calculations are deterministic and source-backed; missing data is visible. |
| 4. Flagship depth and formal evaluation | Deeper 10-Q/10-K coverage for 8–10 flagship companies; versioned retrieval and data-quality evaluation across companies and fiscal periods. | Coverage is explicit; measured retrieval relevance, numerical/period accuracy, provenance, and abstention meet documented thresholds, including negative and ambiguous questions. |
| 5. Optional AI Analysis | Retain grounded single-filing Q&A; add multi-filing and cross-company synthesis only after Phases 2–4 provide reliable inputs and evaluated retrieval. | Research Mode survives missing credentials/provider failures. Real claim-level audits pass within the declared scope; no unresolved NOT_SUPPORTED claims. Source/company/period boundaries hold across filings. |
| 6. Engineering hardening | Security, prompt-injection checks, performance, accessibility, fresh-clone reproduction, and professional code review. | Documented risk checks, representative performance measurements, responsive/keyboard checks, isolated clean setup, and review findings are resolved or explicitly bounded. |
| 7. Portfolio release | GitHub packaging, real screenshots, demo video, and university-application materials explaining engineering choices and evidence. | Instructions reproduce the demo, public assets contain no secrets or fabricated output, and limitations/verification claims match recorded evidence. |

## Phase details

### Financial metrics

Target revenue, gross profit, operating income, net income, EPS, cash, assets, liabilities, operating cash flow, capital expenditure, and free cash flow where the issuer reports comparable data. Define formulas for growth, gross/operating/net margins, and cash-flow measures. Preserve units, duration versus instant periods, fiscal dates, and original concepts; do not imply universal comparability across industries. Missing or incompatible operands produce an explained unavailable result.

### Data and evaluation gates

Basic indexing is distinct from deeper coverage. Track both without counting chunks as filings. Bulk jobs must be resumable and protect existing facts/vectors; review the existing replacing importer before using it in a catalog workflow. See [data sources](docs/data-sources.md).

**Item 7 prerequisite — structured-data ingestion safety (not started):** Before expanding FinancialFact coverage from 10/35 to 35/35, audit/fix the current importer's destructive per-metric replacement and early cross-concept deduplication. Preserve original rows and candidate scope/restatement provenance, with idempotency, recovery and fingerprint validation. This is future work; Item 6 review fixes do not invoke or change ingestion. The Item 6 paragraph above records initial validation; current scope-aware coverage and follow-up checks are in the [verification report](backend/reports/financial_metrics_verification.json) and [metric contracts](docs/financial-metrics.md).

Establish evaluation fixtures and baselines as data expands, not only at the end of Phase 4. Record dataset/version, question classes, expected evidence, scope, quality thresholds, failure examples, and runtime. A valid citation ID proves identity, not factual support. Preserve reports instead of overwriting historical outcomes.

### AI audit and release

Schedule billable real-LLM acceptance only when API credits are intentionally available and the evaluation budget is explicit. Audit every factual claim against supplied SOURCE blocks, stored chunks, accession/company, and official SEC evidence; check numbers, percentages, fiscal period, YoY versus sequential comparison, and causality. Rate each SUPPORTED, PARTIALLY_SUPPORTED, or NOT_SUPPORTED. Mock responses and failed SDK attempts cannot satisfy this gate. The current credit blocker does not block Research Mode engineering.

Security, data integrity, accessibility, and reproduction apply throughout; Phase 6 consolidates formal hardening. [Engineering standards](docs/engineering-standards.md) and [AI decision](docs/decisions/003-ai-is-optional.md) govern all phases.
