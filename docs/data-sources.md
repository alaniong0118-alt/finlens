# Data sources and provenance

This policy governs data selection and interpretation. [Architecture](architecture.md) describes existing acquisition/parsing; the [product spec](product-spec.md) defines Research Mode and [roadmap](../ROADMAP.md) defines expansion. Listing a source here does not mean it is integrated.

## Source priority and current use

| Source | Role | Repository status |
|---|---|---|
| SEC EDGAR filings | Official narrative, tables, filing identity, and citation destination. | Raw submissions, primary-document extraction, chunks, and stored SEC links implemented. |
| SEC Company Facts | Structured XBRL observations with concepts, units, periods, and accession metadata. | Revenue, net income, diluted EPS import and associated analysis implemented. |
| SEC submissions metadata | Official filing discovery and coverage inventory. | Catalog indexing discovers eligible filings by current CIK. `/sources` merges stored facts and indexed chunk metadata; it is not a complete EDGAR catalog. |
| Company Investor Relations | Supplemental official disclosures and verification where SEC coverage is insufficient. | Allowed after source/format review; no adapter currently implemented. |
| Official government/public datasets, such as FRED | Supplemental macroeconomic context. | Possible later scope; not integrated. |
| Selected stable third-party APIs | A documented gap not served by authoritative sources. | Require necessity, provenance, terms, reproducibility, and failure review before adoption. |

Arbitrary scraped pages, search snippets, and model knowledge are not authoritative financial observations. An LLM is not a data source or calculator.

## Current stored provenance

`FinancialFact` retains company CIK, canonical metric, source string identifying the SEC concept, value/unit, period start/end/type, fiscal year/period, form, filed date, accession, frame, and creation timestamp. Creation time is not a guarantee of source refresh time. The broader normalized metric API and explicit refresh/derivation lineage remain planned.

`FilingChunk` retains company CIK, accession, form, filed date, filename, chunk identity/index, cleaned-text offsets, text, official SEC URL, and optional embedding. Offsets refer to cleaned text, not raw HTML byte positions. Flattened tables can lose numerical-column relationships; extraction success is not proof of interpretation accuracy.

Important future metrics must preserve original concept/source, company identity, unit/currency/scale, fiscal/reporting period, filing and filed date, retrieval/update time where relevant, and all derivation inputs/formula version. Amendments/restatements need an explicit selection policy; never silently merge incompatible observations.

## Acquisition and coverage rules

Verify SEC reporting identity by CIK, ticker, and issuer; do not infer identity from company-name similarity. The current catalog has 35 curated issuers; the 25 additions use canonical SEC names, padded CIKs, and exchange metadata verified in the [catalog source record](../backend/reports/company_catalog_verification.json). Original company rows are preserved. The 8–10 flagship selection and broader filing coverage remain future work. Track form, accession, period, parse/chunk/embedding completion, and failures per filing. One accession counts as one filing regardless of chunk count.

Use the existing SEC client contact User-Agent configuration and review current published SEC access requirements when implementing new acquisition workflows. Prefer caching/reuse, bounded concurrency/retry, resumable stages, and safe reruns; distinguish acquisition from interactive research requests. Preserve persisted chunks/embeddings. New jobs require an ExecPlan and must audit the existing replacing importer before bulk use.

The current reproducible demo prepares one fixed official Apple filing through `backend/scripts/setup_demo.py`; see the [Quick Start](../README.md#quick-start). It is a fixture, not full-catalog coverage. Complete demo data is reused without SEC/model calls. No database dump is distributed.

## Baseline catalog indexing

From backend, `python -m scripts.index_catalog` indexes incomplete stored companies; see [CLI instructions](../README.md#catalog-filing-indexing). Discovery reads `https://data.sec.gov/submissions/CIK{padded_cik}.json`, checking returned registrant identity. It prefers the latest exact 10-Q, consulting official older submission pages if needed, then falls back to the latest exact 10-K. Amendments and other forms are excluded. Existing complete coverage is retained rather than refreshed.

The primary document filename must match submissions metadata. Existing parser/chunker and local MiniLM encoder persist official narrative without importing or modifying Company Facts. Sequential requests use the existing contact User-Agent, at least 250 ms between starts, up to three attempts for transport/403/429/transient server failures, and 2/4-second backoff; 404 is not retried. This remains below the SEC's [published access limit](https://www.sec.gov/about/webmaster-frequently-asked-questions). Do not run concurrent indexing jobs.

Current XOM is CIK `0002115436`, ExxonMobil Holdings Corp. Official submissions list 10-Q `0000034088-26-000093`, filed 2026-08-03, primary document `xom-20260630.htm`, under that current registrant. An accession's prefix identifies the submitting entity, not necessarily the issuer CIK. No substitution to predecessor CIK 34088 is performed; the [official filing](https://www.sec.gov/Archives/edgar/data/2115436/000003408826000093/xom-20260630.htm) documents the succession. See [indexing reports](../backend/reports/catalog_indexing_canaries.json).

## Evidence and source limits

Use server-side official SEC URLs tied to verified company/accession metadata. The frontend consumes those links; generated answers may reference eligible IDs but cannot supply source identities or URLs. Trace claims through actual context blocks to stored chunks and official filings.

Keep source presence, embedding readiness, retrieval relevance, metric correctness, and claim support as separate checks. Non-null embeddings define current company readiness but do not certify every chunk or numerical interpretation. Formal evaluation must test provenance and company/period identity as well as retrieval; see [technical challenges](technical-challenges.md) for existing limitations.

Future source adapters must document their authority, units, timestamps, refresh/revision policy, permissions/attribution, and unavailable-data behavior. Keep private contact/credentials and local dumps out of public documentation and Git.
