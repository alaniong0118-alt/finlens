# Company-wide SEC evidence search

Status: completed
Roadmap phase: bounded Research Mode retrieval extension

## Objective

Provide an explicit selected-filing (default) / company-wide evidence search choice.
Company-wide search reads only verified complete publications for the selected CIK,
preserves per-passage lineage, embeds once and exposes no generation action.

## Current architecture and context

Baseline main a08cdaeb7436179d5c95878869bac3a64eb6b9fb. Preserve modified
frontend/next-env.d.ts and the two untracked backend runtime reports. Existing
retrieval uses one accession. FilingPublication already pins metadata, chunk count,
content digest and publication version. read_session provides PostgreSQL repeatable
read/read-only and expected-version validation. No persistent schema is required.

## Constraints

No SEC/provider calls, live database writes, migrations, ingestion, refresh, service
changes, deployment changes, activation, commit or push. Original evidence untouched.
Tests use synthetic vectors and disposable in-memory SQLite only. Financial metrics,
authorization registries and the false activation gate remain unchanged.

## Non-goals

Multi-filing generation, new source acquisition, statement/financial computation,
ranking redesign, unbounded catalog search and legacy publication reconstruction.

## Implementation stages

1. Add bounded publication inventory validation and one-embedding hybrid ranking.
2. Add bounded company context/API with exact CIK/version/source metadata.
3. Add scope control and typed client, preserve default filing behavior and stale guards.
4. Add adversarial offline/API and mounted UI regressions, run focused checks/review.

## Decisions

- 2026-10-12: Require existing publication metadata and company version state in the
  new mode. Missing metadata fails closed; legacy selected-filing behavior stays intact.
- Validate whole filing metadata/count/digest/vectors before ranking. Pending targets
  are excluded; a failed refresh does not invalidate unrelated intact publications.
- Bound inventory at 20 publications / 4,000 chunks; reject oversized scopes rather
  than imply complete search after truncation. Bound ranking to 50 and context to
  24,000 characters without cutting source blocks. Shared existing ranking is reused.
- Use cosine similarity over bounded stored vectors in process; this permits complete
  digest validation and offline ORM tests without a pgvector-specific SQL fixture.

## Discovered issues

Existing selected-filing endpoints trust publication presence; the stronger new
read validator is scoped to company-wide search. The existing version guard runs
before endpoint lookup, so unknown/missing-state requests with a nonzero expected
version correctly reject as stale before the endpoint's 404/metadata diagnostic.
Tests use expected version zero to exercise the latter paths without changing
existing guard semantics. No live PostgreSQL/encoder/browser acceptance is claimed.

## Progress

- [x] Instructions, baseline, publication/retrieval/UI/test contracts inspected.
- [x] Backend implementation and adversarial tests.
- [x] Frontend scope control and mounted interactions.
- [x] Focused verification, self-review and final report.

## Test and validation strategy

Offline synthetic ORM/API tests cover exact CIK/publication metadata, count/digest,
pending/unpublished/partial exclusion, version conflicts, embedding count, lineage,
ranking determinism, caps, insufficient evidence and unchanged single-filing context.
Mounted frontend tests cover explicit scopes, company/version/scope invalidation,
lineage labels and zero new generation calls. Run relevant node/pytest suites,
TypeScript no-emit without incremental output, syntax/whitespace checks and lint.
No live service/browser/API or database audit is claimed.

## Completion criteria

Focused regressions pass; no new schema; stable default filing path; bounded company
search and source lineage; no AI action in new mode; source gate false and four
production registries empty; preserved unrelated files and reports.

## Final outcome

Implemented one company-wide retrieval GET and an explicit UI scope control.
Whole-publication validation excludes corrupt/incomplete/pending sources, preserves
exact CIK/source lineage and accepts intact old publications within one current
snapshot. Oversized inventories reject; ranking/context caps preserve whole blocks.
No generation route/action was added. Selected-filing defaults/contracts are retained.
Company-wide highlighting is phrase-only. No financial source files were modified.

Actual checks (2026-10-12):

- From backend: `.venv/Scripts/python.exe -B -m pytest -p no:cacheprovider
  tests/test_company_evidence_search.py tests/test_rag.py
  tests/test_revenue_scope_authorizations.py tests/test_capabilities.py
  tests/test_company_availability.py -q`: **142 passed, 27 subtests passed, zero
  skipped**, 2.61 seconds. Includes 29 new end-to-end/ORM/adversarial cases.
  Only synthetic disposable in-memory SQLite was populated; no live DB access.
- From frontend: `node --test --test-reporter=dot tests/finlens-api.test.mjs
  tests/research.test.mjs tests/research-interactions.test.mjs
  tests/evidence-presentation.test.mjs`: **93 passed, zero skipped**. Includes
  12 new client-scope/version cases and 6 mounted company-wide interactions.
- TypeScript no-emit/nonincremental and eslint passed. Python syntax in-memory,
  whitespace/new-file checks and fresh-process inactive registry checks recorded
  before final reporting. Existing deprecation/Node module-type warnings persist.

Independent Astra High review is recommended for the new publication validator,
snapshot/version boundary and bounded ranking before acceptance. No external model
review was invoked. Real PostgreSQL concurrent-publisher behavior and real cached
encoder latency/parity remain unverified; existing repeatable-read/read-only is reused.

Git remains main/a08cdae, with this implementation/docs/tests uncommitted and all
three baseline unrelated changes preserved. No SEC/provider requests, live writes,
schema/refresh/service/config changes, authorization, original evidence edits or
commit/push. Suggested commit after review: `feat: add bounded company-wide SEC evidence search`.
