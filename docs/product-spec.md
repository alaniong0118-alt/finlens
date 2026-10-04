# Product specification

## Product principle

“FinLens must remain useful without an LLM. AI enhances evidence-based financial research rather than being the product’s only source of value.”

FinLens helps users inspect public-company financial information and SEC filings, then trace conclusions to evidence. The [roadmap](../ROADMAP.md) records phase status; [architecture](architecture.md) records current implementation. This specification distinguishes current capabilities from target behavior.

## Current product

- A local Next.js workspace selects a company and indexed filing, accepts a question, and renders optional generated answers with claims and citations. Empty, loading, Not indexed, insufficient-evidence, and error states are explicit.
- FastAPI already provides company metadata, financial summary/snapshot/history, filing sources, keyword/semantic search, hybrid context, and optional answers. Financial/search/context APIs do not require OpenAI; the frontend does not yet expose a complete research workflow without generated answers.
- Financial import supports revenue, net income, and diluted EPS, with existing growth/margin analysis. This is a foundation for the broader standardized Metrics Layer, not its completed contract.
- Indexed availability is derived from stored evidence. Recorded coverage and acceptance limitations live in the roadmap and linked reports, not in hardcoded company rules.

## Target Research Mode

The core journey must work with no LLM or OpenAI key:

`select company → inspect metrics/trends → compare compatible periods/companies → discover filing → search → read evidence excerpt → open official SEC source`

- Standardized metric names conceal concept differences without discarding the original concept or provenance.
- Ratios, growth, trends, charts, and comparisons use deterministic calculations. Labels identify units, fiscal dates, and the comparison basis; absent data is never displayed as zero.
- A chart must be reproducible from stored observations and the documented calculation. Comparisons expose incompatible accounting/industry definitions instead of implying false equivalence.
- Filing discovery distinguishes metadata-only records from usable indexed evidence. Hybrid search and source excerpts remain usable without generation; local embeddings are independent of the optional OpenAI provider.
- Important financial values preserve company, source, unit, period, filing/form, filed date, and relevant update/derivation lineage. Clicking evidence leads to an official source.
- Missing AI credentials, quota exhaustion, or provider outage must leave Research Mode usable. The planned UI explains optional AI availability in user terms, rather than making API configuration its main interaction.

These are future acceptance contracts; this documentation task does not implement them.

## Optional AI Analysis

AI can explain or synthesize retrieved evidence, with bounded context and claim-level citations. It does not calculate deterministic financial values or fill gaps using unsupported model knowledge. Multi-filing and cross-company analysis must wait for mature metric, coverage, and retrieval/evaluation layers. See [ADR 003](decisions/003-ai-is-optional.md).

Each factual claim must be traceable through citation ID, actual supplied SOURCE block, database chunk, company/accession, and official SEC URL. Links/metadata come from trusted server-side records; the frontend does not invent them. Source identity validation is distinct from semantic support auditing. Insufficient evidence is a correct abstention state, not a request failure.

## Availability and state contracts

- Company Ready means at least one matching chunk with a non-null usable embedding. `indexed_filing_count` counts distinct accessions over those chunks, not chunk rows; availability updates automatically when data arrives.
- Preserve the current stable company order and select the first Ready company by default; fall back to the first company only when none is Ready. Do not hide unindexed companies or determine availability with per-company HTTP requests.
- The sources response merges fact-backed and chunk-backed filing metadata. Chunk-only filings have empty metrics and unknown financial period fields. `has_filing_chunks` describes chunk presence, while company Ready also requires embeddings; these fields have different semantics. Catalog indexing validates every selected filing's vectors before reporting completion.
- Not indexed is a data state with a clear recovery action. Ask remains disabled; switching company/filing clears stale answers/errors and guards against late requests. Retain labels, keyboard focus, responsive layouts, and text status indicators.

## Boundaries and acceptance

FinLens provides historical research and education. Personalized investment advice, buy/sell recommendations, price targets, trading, allocation instructions, and unsupported forecasts are outside scope. Source text and questions are untrusted; preserve prompt-injection controls. No fabricated numbers, charts, filings, citations, or model output may appear in the product or portfolio assets.

Acceptance requires evidence appropriate to the changed scope: deterministic metric fixtures, retrieval/data-quality evaluation, no-key research checks, source lineage, accessibility, and reproduction. Real generated answers require real claim audits when credits are deliberately available. Current integration and historical mocks must not be presented as fully verified AI output.
