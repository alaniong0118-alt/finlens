# Data sources and provenance

This policy governs data selection and interpretation. [Architecture](architecture.md) describes existing acquisition/parsing; the [product spec](product-spec.md) defines Research Mode and [roadmap](../ROADMAP.md) defines expansion. Listing a source here does not mean it is integrated.

## Source priority and current use

| Source | Role | Repository status |
|---|---|---|
| SEC EDGAR filings | Official narrative, tables, filing identity, and citation destination. | Raw submissions, primary-document extraction, chunks, and stored SEC links implemented. |
| SEC Company Facts | Structured XBRL observations with concepts, units, periods, and accession metadata. | Insert-only catalog sync for existing reviewed metric concepts; typed normalization and associated legacy analysis. |
| SEC submissions metadata | Official filing discovery and coverage inventory. | Catalog indexing discovers eligible filings by current CIK. `/sources` merges stored facts and indexed chunk metadata; it is not a complete EDGAR catalog. |
| Company Investor Relations | Supplemental official disclosures and verification where SEC coverage is insufficient. | Allowed after source/format review; no adapter currently implemented. |
| Official government/public datasets, such as FRED | Supplemental macroeconomic context. | Possible later scope; not integrated. |
| Selected stable third-party APIs | A documented gap not served by authoritative sources. | Require necessity, provenance, terms, reproducibility, and failure review before adoption. |

Arbitrary scraped pages, search snippets, and model knowledge are not authoritative financial observations. An LLM is not a data source or calculator.

## Current stored provenance

`FinancialFact` retains company CIK, canonical metric, source string identifying the SEC concept, value/unit, period start/end/type, fiscal year/period, form, filed date, accession, frame, and creation timestamp. Creation time is not a guarantee of source refresh time. The [normalized metric API](financial-metrics.md) exposes selected/alternative source rows and deterministic derivation inputs without modifying stored facts. Filing-context fiscal labels remain separate from normalized observation labels. The sync below adds new source observations without rewriting prior rows.

`FilingChunk` retains company CIK, accession, form, filed date, filename, chunk identity/index, cleaned-text offsets, text, official SEC URL, and optional embedding. Offsets refer to cleaned text, not raw HTML byte positions. Flattened tables can lose numerical-column relationships; extraction success is not proof of interpretation accuracy.

Important future metrics must preserve original concept/source, company identity, unit/currency/scale, fiscal/reporting period, filing and filed date, retrieval/update time where relevant, and all derivation inputs/formula version. Amendments/restatements need an explicit selection policy; never silently merge incompatible observations.

## Acquisition and coverage rules

Verify SEC reporting identity by CIK, ticker, and issuer; do not infer identity from company-name similarity. The current catalog has 35 curated issuers; the 25 additions use canonical SEC names, padded CIKs, and exchange metadata verified in the [catalog source record](../backend/reports/company_catalog_verification.json). Original company rows are preserved. The 8–10 flagship selection and broader filing coverage remain future work. Track form, accession, period, parse/chunk/embedding completion, and failures per filing. One accession counts as one filing regardless of chunk count.

Use the existing SEC client contact User-Agent configuration and review current published SEC access requirements when implementing new acquisition workflows. Prefer caching/reuse, bounded concurrency/retry, resumable stages, and safe reruns; distinguish acquisition from interactive research requests. Preserve persisted chunks/embeddings. New jobs require an ExecPlan. Item 7 audited and replaced the legacy destructive importer; ingestion now preserves alternatives for selection by the Metrics Layer.

The current reproducible demo prepares one fixed official Apple filing through `backend/scripts/setup_demo.py`; see the [Quick Start](../README.md#quick-start). It is a fixture, not full-catalog coverage. Complete demo data is reused without SEC/model calls. No database dump is distributed.

## Baseline catalog indexing

From backend, `python -m scripts.index_catalog` indexes incomplete stored companies; see [CLI instructions](../README.md#catalog-filing-indexing). Discovery reads `https://data.sec.gov/submissions/CIK{padded_cik}.json`, checking returned registrant identity. It prefers the latest exact 10-Q, consulting official older submission pages if needed, then falls back to the latest exact 10-K. Amendments and other forms are excluded. Existing complete coverage is retained rather than refreshed.

The primary document filename must match submissions metadata. Existing parser/chunker and local MiniLM encoder persist official narrative without importing or modifying Company Facts. Sequential requests use the existing contact User-Agent, at least 250 ms between starts, up to three attempts for transport/403/429/transient server failures, and 2/4-second backoff; 404 is not retried. This remains below the SEC's [published access limit](https://www.sec.gov/about/webmaster-frequently-asked-questions). Do not run concurrent indexing jobs.

Current XOM is CIK `0002115436`, ExxonMobil Holdings Corp. Official submissions list 10-Q `0000034088-26-000093`, filed 2026-08-03, primary document `xom-20260630.htm`, under that current registrant. An accession's prefix identifies the submitting entity, not necessarily the issuer CIK. No substitution to predecessor CIK 34088 is performed; the [official filing](https://www.sec.gov/Archives/edgar/data/2115436/000003408826000093/xom-20260630.htm) documents the succession. See [indexing reports](../backend/reports/catalog_indexing_canaries.json).

## Structured financial sync

Run `python -m scripts.sync_financial_facts` from backend; [README usage](../README.md#structured-financial-sync) covers repeatable `--ticker`, `--dry-run` and `--report`. Source: `https://data.sec.gov/api/xbrl/companyfacts/CIK{padded_cik}.json`, validated against the stored current CIK. One sequential fetch per selected company uses the existing contact, spacing and bounded retries. JSON decimals are parsed precisely before Numeric(24,4) checks. No filing or embedding work is triggered.

`sec_importer.METRIC_SOURCES` reuses the existing Item 6 primary concepts and source units; revenue keeps the legacy stored name `Revenues`, with its original concept retained in `source`. The other nine base definitions use their existing primary concepts. No aliases were added to increase coverage. Only exact observations repeated within a response are deduplicated; no form/latest-filing/scope winner is selected during ingestion. Null values are omitted; malformed or unrepresentable supported observations fail the company atomically rather than being silently rounded or partially imported. Unsupported concepts/units remain unmapped.

Identity comprises **CIK, source concept, unit, start/end, exact value, accession, filed date, form, frame, source fiscal year/period**. Local IDs/timestamps and derived storage labels are excluded. Later comparative filings, amendments, distinct concepts and compatible SEC context/frame variants coexist. New same-vintage conflicting values now fail publication rather than rely on insertion order; see [revision policy](data-freshness.md#financial-revisions). A disappeared source observation does not remove a stored row. Existing duplicates are not automatically deleted; preservation checks expose them. Existing original rows retain their IDs, values and metadata.

Each company uses a fresh SQLAlchemy session/transaction. PostgreSQL supported writers take a transaction advisory lock keyed by CIK before reading identities and inserting missing rows, requiring the standard READ COMMITTED isolation level. This makes the check-and-insert atomic among supported writers without an added schema constraint. Direct SQL writers must follow the same protocol; do not run unmanaged concurrent imports. SQLite tests assume a single writer. Legacy `import_metric`/`import_company` and the fixed demo metadata path share the merge. No DELETE/UPDATE of FinancialFact occurs.

Ordinary errors roll back that company, discard the failed session, check database health and continue. A global outage stops the job with a nonzero result. An interruption retains earlier committed companies; rerun fetches and compares actual stored identities, with no reliance on reports as checkpoints. Company results are atomically checkpointed under backend/reports; exceptions are reduced to safe categories/HTTP status. No private contact, credentials, raw provider bodies or database exception text is recorded. Retry only failed tickers after diagnosis; unchanged complete data reports `already_current` with zero inserts. A successful dry-run may report `would_update` without inserting facts.

Current XOM stays CIK **0002115436**. Its official response supplied **22** supported observations, including comparative periods under that response's current identity. No request to predecessor CIK **0000034088** or independent predecessor merge is performed. Limited annual/history coverage and unknown fiscal labels remain visible; predecessor/successor unification requires a separate decision.

The [rollout](../backend/reports/structured_financial_rollout.json) records staged discovery, five canaries with immediate no-op reruns, the remaining 30 companies and an unchanged full 35-company rerun. The [audit](../backend/reports/structured_financial_verification.json) checks every original fact fingerprint, chunks/vectors, identity uniqueness, orphan absence, metric histories and representative real HTTP contents. This local database grew from 3,251 to 58,881 facts across 35/35 issuers. Source revenue/net-income observations exist for 35/35 and diluted EPS for 34/35; selected metric availability is separately measured by period and compatibility. The [baseline](../backend/reports/structured_financial_baseline.json) is an ID-specific local verification artifact, not a database dump or fresh-clone prerequisite.

## Evidence and source limits

Use server-side official SEC URLs tied to verified company/accession metadata. The frontend consumes those links; generated answers may reference eligible IDs but cannot supply source identities or URLs. Trace claims through actual context blocks to stored chunks and official filings.

Keep source presence, embedding readiness, retrieval relevance, metric correctness, and claim support as separate checks. Validated complete published evidence defines company readiness; partial/non-null vectors alone do not. Publication certifies source completeness/vector validity, not numerical interpretation or claim support. Formal evaluation must test provenance and company/period identity as well as retrieval; see [technical challenges](technical-challenges.md) for existing limitations.

Future source adapters must document their authority, units, timestamps, refresh/revision policy, permissions/attribution, and unavailable-data behavior. Keep private contact/credentials and local dumps out of public documentation and Git.

## Controlled refresh

The [refresh runbook](data-freshness.md) owns incremental discovery, revision/publication rules, source/check timestamps, budgets, operator commands and recovery. Baseline catalog indexing above retains its coverage behavior; refresh separately checks latest 10-Q/10-K and amendments in a capped recent window. Source acquisition is explicit, serialized, bounded and disabled by default in the refresh CLI/wrapper. SEC redirects are disabled, decoded bytes are capped and Retry-After is bounded. Reads never contact SEC. Offline implementation acceptance is complete; current access-policy review, live canary and scheduler activation require later authorization. No LLM is used for freshness or calculations.
