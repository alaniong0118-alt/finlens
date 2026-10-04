# FinLens engineering roadmap

FinLens must remain useful without an LLM. AI enhances evidence-based financial research rather than being the product's only source of value.

This is the authoritative milestone/status document. [Product spec](docs/product-spec.md) defines product contracts; [architecture](docs/architecture.md) describes implementation. Complex work requires an [ExecPlan](.agent/PLANS.md). Start only the phase or scoped task requested by the user.

## Current baseline — 2026-10-04

Completed foundations: Item 1 fresh-clone demo setup, Item 2 database-derived indexed availability, and Item 3 research-interface polish (commits `5566344`, `004cdc5`, `641febb`).

Current read-only DB/API inspection: 10 companies, 3,251 financial facts, 37 filing chunks and 37 embeddings; AAPL is the only Ready company, with one distinct indexed accession. Financial history/summary/snapshot and filing search/context APIs exist without OpenAI. The frontend currently centers on single-filing AI Q&A; a complete Research Mode UI, broad normalized metrics, and charts/comparisons remain planned.

OpenAI integration and citation identity checks exist. [Recorded acceptance](backend/reports/final_verification.md) and [evaluation](backend/reports/rag_evaluation.json) show exhausted API credits and no completed real claim audit. Historical test results are scoped evidence, not proof across future companies or filings. This documentation setup does not begin any feature phase.

## Phases and exit gates

All phases below are **planned**. Preserve working foundations; prioritize usable data and research before broader AI features.

| Phase | Deliverable | Completion gate |
|---|---|---|
| 1. Curated catalog and baseline filing coverage | Approximately 30–40 curated SEC-reporting public companies, then at least one usable indexed SEC filing for every visible company. Record inclusion criteria, verified ticker/CIK identity, coverage, and ingestion failures. | Every visible company is Ready by the DB-derived definition; reruns are safe, failures isolated, and source lineage checked. Transitional Not indexed states remain honest. |
| 2. Financial Metrics Layer | A stable metric vocabulary and API over SEC concepts; deterministic metrics, ratios, period alignment, and provenance. | Representative company/industry fixtures verify units, fiscal periods, missing values, restatements, and formulas. Raw XBRL concepts are retained as provenance rather than the public API contract. |
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

Establish evaluation fixtures and baselines as data expands, not only at the end of Phase 4. Record dataset/version, question classes, expected evidence, scope, quality thresholds, failure examples, and runtime. A valid citation ID proves identity, not factual support. Preserve reports instead of overwriting historical outcomes.

### AI audit and release

Schedule billable real-LLM acceptance only when API credits are intentionally available and the evaluation budget is explicit. Audit every factual claim against supplied SOURCE blocks, stored chunks, accession/company, and official SEC evidence; check numbers, percentages, fiscal period, YoY versus sequential comparison, and causality. Rate each SUPPORTED, PARTIALLY_SUPPORTED, or NOT_SUPPORTED. Mock responses and failed SDK attempts cannot satisfy this gate. The current credit blocker does not block Research Mode engineering.

Security, data integrity, accessibility, and reproduction apply throughout; Phase 6 consolidates formal hardening. [Engineering standards](docs/engineering-standards.md) and [AI decision](docs/decisions/003-ai-is-optional.md) govern all phases.
