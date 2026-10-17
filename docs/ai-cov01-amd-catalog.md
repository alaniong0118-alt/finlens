# AI-COV01 Phase 3A: AMD catalog identity only

AMD is appended as the 36th configured issuer in `backend/seed_companies.py`.
The original 35 identities and their order are preserved. The identity uses the
existing uppercase exchange convention:

| Ticker | SEC issuer name | CIK | Exchange |
|---|---|---|---|
| AMD | ADVANCED MICRO DEVICES INC | 0000002488 | NASDAQ |

## Evidence provenance and limits

The operator-approved AI-COV01 Phase 2B conversation records official metadata
verification on 2026-10-16 at approximately 23:13 Asia/Macau. Both
`https://www.sec.gov/files/company_tickers_exchange.json` and
`https://data.sec.gov/submissions/CIK0000002488.json` returned HTTP 200 and agreed
on ticker, name, CIK and Nasdaq association. Those responses were inspected in
memory; no original response artifact or independently pinned receipt was retained.
This note records that prior verification, not a new SEC check or financial proof.
Historical 35-company reports remain unchanged.

The separately authorized read-only PostgreSQL check at 23:22 on 2026-10-16 found
no AMD identity, CIK owner, facts, chunks, publications, refresh state or attempts.
That is a dated observation, not a current database guarantee. Phase 3A makes no
live connection and does not admit AMD into the running database.

AMD's FY2025 annual metadata includes base 10-K `0000002488-26-000018` and
10-K/A `0000002488-26-000021`, both filed 2026-02-04 for report date 2025-12-27
with document name `amd-20251227.htm`. Their financial effect and source
compatibility remain unresolved; distinct accessions must not be conflated.

## Catalog-only and operational boundaries

- Configured membership establishes neither numeric coverage nor filing research
  readiness. Seeding creates identities only; it must not implicitly create facts,
  chunks/vectors, filing publications, refresh states or refresh attempts.
- Missing refresh metadata remains `FRESHNESS_UNAVAILABLE`; the research pin stays
  unknown/null. It must not become an invented version-zero publication or borrow
  NVDA's data or verified pin.
- The existing refresh request maximum remains 35 tickers. Once 36 companies are
  stored, `refresh_data --all --allow-network` and
  `refresh_data --all --bootstrap` fail request validation before refresh/bootstrap
  execution. The CLI still reads the catalog/schema first. Without
  `--allow-network`, ordinary refresh is already rejected by its network gate.
- Do not default to `index_catalog` or `sync_financial_facts`: omitting their ticker
  selection targets the stored catalog and can acquire/write evidence. Neither
  command, nor refresh/bootstrap, is permitted by catalog-only authorization.
- No batching, truncation, raised limits, new financial aliases, financial
  authorization, UI changes or publication exceptions are introduced.

## Later gates

The operator reports Astra's Phase 2 conditional GO; Phase 3A still awaits its own
independent diff/test review. Live seeding requires separate authorization and a
fresh identity-conflict check. Company Facts/original-filing acquisition, immutable
custody, amendment/financial-semantic review, financial publication, and indexing
each remain separate gates. No coverage percentage or research-readiness claim is
made. DEP-01A3 remains BLOCKED; no dependency or model work is included.

Phase 3A validation (2026-10-17): focused catalog/demo tests and the existing
release-profile seed-denial case passed in disposable SQLite with dotenv disabled
and external-connection/encoder guards. The existing mounted failed-initial-
freshness test also passed with mocked fetch. These are offline checks, not live
database, source, browser E2E or publication acceptance.
