# Product specification

## Product principle

“FinLens must remain useful without an LLM. AI enhances evidence-based financial research rather than being the product’s only source of value.”

FinLens helps users inspect public-company financial information and SEC filings, then trace conclusions to evidence. The [roadmap](../ROADMAP.md) records phase status; [architecture](architecture.md) records current implementation. This specification distinguishes current capabilities from target behavior.

## Current product

- A local Next.js Research Mode workspace exposes company identity/readiness, financial snapshot, selected history chart/table, source provenance, indexed filing selection and hybrid evidence excerpts. All work without OpenAI. AI Analysis is a separate explicit action with answer, claims and citations.
- FastAPI provides company metadata, standardized summary/history, legacy financial APIs, filing sources, keyword/semantic search, hybrid context, optional answers and configuration-only capability metadata. The frontend uses the standardized contracts, not raw XBRL labels.
- Official Company Facts sync covers the reviewed concepts for 35 issuers. The [Metrics Layer](financial-metrics.md) exposes 15 canonical definitions with deterministic calculations, explicit unavailable results and SEC provenance. Source coverage is not universal compatible metric coverage; missing concepts/scopes/periods remain visible.
- Reported revenue carries its economic basis; component-only observations do not establish consolidated margins. Ambiguous fiscal years remain null, and EPS histories explicitly mark share-basis comparability unverified.
- Indexed availability is derived from stored evidence. Recorded coverage and acceptance limitations live in the roadmap and linked reports, not in hardcoded company rules.

## Research Mode

The core journey must work with no LLM or OpenAI key:

`select company → inspect metrics/history → choose indexed filing → search → read evidence excerpt → open official SEC source`

- Standardized metric names conceal concept differences without discarding the original concept or provenance.
- Ratios, growth, trends, charts, and comparisons use deterministic calculations. Labels identify units, fiscal dates, and the comparison basis; absent data is never displayed as zero.
- A chart must be reproducible from stored observations and the documented calculation. Comparisons expose incompatible accounting/industry definitions instead of implying false equivalence.
- Filing discovery distinguishes metadata-only records from usable indexed evidence. Hybrid search and source excerpts remain usable without generation; local embeddings are independent of the optional OpenAI provider.
- Important financial values preserve company, source, unit, period, filing/form, filed date, and relevant update/derivation lineage. Clicking evidence leads to an official source.
- Missing AI credentials, quota exhaustion, or provider outage leave Research Mode usable. Configuration metadata is not a health promise. Failure of explicit AI generation never removes the evidence result.

The Item 8 UI shows six primary metrics and secondary balance-sheet/cash-flow details. One selected history (up to 12 observations) uses discrete bars with an observation/source table. Direct quarters, YTD, annual and instant series are separate; EPS warns that as-filed comparability is unverified. Snapshots and narrative filings can describe different periods/accessions and are explicitly labelled. Values are rounded only for display; disclosures retain exact API values, concepts, dates, forms and official links. Missing values are never plotted as zero. Bounded same-company fiscal comparisons are now supported below; broader comparisons and deeper filing discovery/coverage remain future work.

Light/Dark/System themes persist locally, follow OS preference in System mode, and use semantic colors across charts, controls and evidence. Mobile stacks panels, reflows cards, expands source details to full card width and contains table scrolling. Labels, visible keyboard focus, live async states, source disclosures and chart text equivalents remain part of acceptance.

### Deterministic Research Answers

Clear single-metric questions receive a Research Answer before supporting evidence, without AI. Supported concepts are the 15 existing canonical metrics: revenue/sales, gross profit, operating income, net income, diluted EPS, cash/equivalents, assets, liabilities, operating cash flow, CapEx, FCF, YoY revenue growth, and gross/operating/net margins. Bounded synonyms are explicit; this is not general natural-language answering. Questions about causes, segments, arbitrary calendar dates, forecasts, multiple metrics or ambiguous concepts continue through existing selected-filing evidence research. Explicit fiscal years/quarters and bounded comparisons follow the additional contract below.

Quarterly/annual requests use the existing summary period and cannot substitute another duration or older available value. Latest available chooses the newest normalized metric observation across actual period kinds; equal end dates prefer a direct shorter period. YTD remains labelled as YTD, Q4 is never synthesized, and instant values are labelled as-of. Newest unavailable observations retain their reason. No source coverage or economic-basis rule is relaxed.

The selected company is authoritative. Recognized other catalog names/tickers receive mismatch guidance; unknown wording falls back conservatively without switching company. Answers disclose rounded display value, actual dates and filing metadata, with exact source values/concepts/accessions, alternatives, formulas and operand provenance behind View provenance. Revenue basis and EPS comparability warnings remain visible. Recognized unavailable/not-applicable questions receive an explanation from the metric service, never zero.

Direct answers do not depend on indexed filings or context retrieval. One answer request and one selected-filing context request settle independently; answer/evidence failures and optional AI failure cannot erase the other valid research result. Company/filing changes and question edits invalidate old responses. Narrative supporting passages may concern another period/accession and do not establish validation of the structured answer. No company-wide or multi-filing retrieval is introduced.

### Historical and comparative research answers

`2024 revenue` means FY2024 annual revenue under the existing fiscal-end-year convention; `Q2 2025 revenue` means a directly reported fiscal Q2. Fiscal labels come from normalized reporting boundaries, never SEC filing-context FY/FP. Missing or ambiguous labels return unavailable; no annual/YTD substitution, Q4 synthesis, calendar reinterpretation or wrong-year backfill. Instant metrics use the requested reporting period's exact end date and remain labelled as-of.

Supported comparisons include `2024 vs 2025 revenue`, `compare 2024 and 2025 operating margin`, `revenue from 2024 to 2025`, `2024–2025 revenue growth`, and bounded amount/direction questions. Explicit revenue-growth pairs compare revenue levels, not a textual growth mention. Two explicit same-quarter labels across years are also supported. Comparisons require matching units/kinds/quarter slots, aligned fiscal boundaries/durations, and compatible revenue/derived-input economic bases. Mixed annual/quarter requests receive an explained unavailable comparison. Reverse `from/to`, missing connectors, extra metrics, causal/method qualifiers and arbitrary dates fall back rather than guess.

Comparison cards show both values, absolute change, optional percentage and both provenance disclosures. A positive earlier value permits `(later - earlier) / earlier`; zero/negative baselines retain valid absolute changes with percentage unavailable. Equal values retain zero. Ratios use percentage-point change; EPS exposes an as-filed absolute difference with an unverified-comparability warning and no percentage-growth claim. No investment significance is implied.

Source selection retains the existing latest-filed compatible vintage for each exact period, including alternatives. This is not an original-filing/as-of snapshot or guaranteed restatement-adjusted series. Structured provenance computes the result independently of evidence. Selected-filing historical/comparison excerpts use phrase marks only, because matching a number does not establish requested-period alignment. See [metric contract](financial-metrics.md#historical-values-and-comparisons) and [acceptance report](../backend/reports/historical_answers_final_report.md).

### Answer presentation and evidence highlighting

“Answer first, highlight the proof, details on demand.” Direct answers show the server's value/sentence, essential period/filing metadata and basis or warnings; exact provenance stays collapsed. Unavailable reasons and EPS warnings stay visible.

Supporting research initially shows the first two backend-ranked passages. Show more/less retains their order. Each preview is an unchanged, query-focused source window (up to 280 characters, normally 200 around matched values); full stored text and citation details remain expandable. Semantic highlights mark metric/query phrases or exact, safely scaled values, not validated factual support. Unknown units, rounded-only matches and unavailable answers receive no numeric-validation highlight. Evidence-only questions favor relevant reporting language or query terms without generating an answer. Existing company/query invalidation and independent answer/evidence/AI state are retained.

## Optional AI Analysis

AI can explain or synthesize retrieved evidence, with bounded context and claim-level citations. It does not calculate deterministic financial values or fill gaps using unsupported model knowledge. Multi-filing and cross-company analysis must wait for mature metric, coverage, and retrieval/evaluation layers. See [ADR 003](decisions/003-ai-is-optional.md).

Each factual claim must be traceable through citation ID, actual supplied SOURCE block, database chunk, company/accession, and official SEC URL. Links/metadata come from trusted server-side records; the frontend does not invent them. Source identity validation is distinct from semantic support auditing. Insufficient evidence is a correct abstention state, not a request failure.

## Availability and state contracts

- Company Ready means at least one completely validated, published filing with usable embeddings. `indexed_filing_count` counts published accessions, not chunk rows. Before refresh metadata migration, a read-only bulk validator recognizes complete legacy accessions; partial chunks never establish readiness.
- Preserve the current stable company order and select the first Ready company by default; fall back to the first company only when none is Ready. Do not hide unindexed companies or determine availability with per-company HTTP requests.
- The sources response merges fact-backed and published-evidence metadata. Evidence-only filings have empty metrics and unknown financial period fields. `has_filing_chunks` means complete published research evidence (validated legacy evidence before migration); metadata-only or partial accessions are not searchable.
- Not indexed is a data state: filing research is unavailable while financial research remains independent. Switching company/filing remounts scoped panels, aborts requests and clears previous results; edits invalidate an in-flight search. Retain labels, keyboard focus, responsive layouts and text status indicators.
- `GET /capabilities` exposes only `research_mode` and `ai_analysis_configured` booleans. Missing/unknown capability disables optional generation; neither company metrics nor filing evidence depend on it. No key, quota or provider exception appears in optional-AI fallback copy.

## Boundaries and acceptance

FinLens provides historical research and education. Personalized investment advice, buy/sell recommendations, price targets, trading, allocation instructions, and unsupported forecasts are outside scope. Source text and questions are untrusted; preserve prompt-injection controls. No fabricated numbers, charts, filings, citations, or model output may appear in the product or portfolio assets.

Acceptance requires evidence appropriate to the changed scope: deterministic metric fixtures, retrieval/data-quality evaluation, no-key research checks, source lineage, accessibility, and reproduction. Real generated answers require real claim audits when credits are deliberately available. Current integration and historical mocks must not be presented as fully verified AI output.

## Data freshness

Research Mode distinguishes stored coverage/readiness from source currency. Selected-company freshness exposes separate financial-fact/evidence states, UTC check/success times, SEC source filed dates and published versions. Unknown, pending, failed and stale are honest states; a recent check is scoped and does not guarantee all SEC data is current. No page request acquires SEC data or schedules work.

A new published version refreshes financial summary/history/source metadata and invalidates direct answer/evidence/AI together, while retaining question, controls and still-available filing selection. Users explicitly research the question again; optional AI is never replayed. Freshness-check failure retains stored research with a disclosure. Refresh implementation has offline acceptance only; development migration and live scheduling are pending. See [contracts, limits and rollout](data-freshness.md).
