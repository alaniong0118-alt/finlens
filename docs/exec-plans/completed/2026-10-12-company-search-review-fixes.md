# Company-wide search: three Astra blocking corrections

Status: completed
Roadmap phase: correction of the uncommitted company-wide retrieval slice

## Objective

Resolve filename/source-boundary injection, evidence publication version bounds,
and oversized Text materialization without changing selected-filing behavior.

## Current architecture and context

Main HEAD a08cdaeb7436179d5c95878869bac3a64eb6b9fb. The complete company-wide
implementation/docs/tests remain uncommitted. Preserve that work, next-env.d.ts,
both runtime reports and original SEC evidence. Existing snapshots are read-only;
publication metadata/count/digest and vectors are verified before retrieval.

## Constraints

No real DB writes, schema changes, SEC/provider calls, ingestion/refresh, services,
configuration, authorization or commit/push. Only synthetic in-memory test stores.

## Non-goals

Ranking redesign, generation, financial changes, production activation, full audits.

## Implementation stages

1. Validate plain SEC document filenames and serialize company metadata as one JSON
   line; parse only the matching company framing and indented stored body.
2. Reject publication versions above evidence_version before any chunk projection.
3. Project bounded chunk IDs/accessions/character lengths first; exclude whole
   oversized publications and load only bounded eligible bodies.
4. Add API-to-actual-frontend-parser/rendering regressions and materialization guards;
   run focused offline suites, syntax/type/lint/whitespace and inactive-state checks.

## Decisions

- Preserve the original selected-filing SOURCE format/parser branch unchanged.
- Company metadata uses JSON escaping and explicit citation identity matching.
- Text length is a character bound, evaluated in SQL before ORM Text selection.
- Raw metadata inventory retains the 4,000 + sentinel row cap; no silent dropping
  of oversized chunks within an otherwise accepted publication.

## Discovered issues

Initial company test incorrectly treated publication version 2 as valid at company
data/evidence versions 2/1; fix that fixture and add the reproduced rejection case.

Self-review found JavaScript's `$` anchor permits a trailing line terminator.
The frontend now rejects every character outside the basename allowlist, with
regressions for trailing LF, CR, U+2028 and U+2029. Evidence-version semantics
match the existing refresh producer: successful evidence publication assigns
evidence_version and the filing publication the same then-current data version;
facts-only advances retain older evidence. No producer changes were needed.

## Progress

- [x] Request/instructions/baseline and relevant contracts inspected.
- [x] Three scoped corrections and adversarial tests (2026-10-12).
- [x] Focused verification and self-review (2026-10-12).

## Test and validation strategy

Use synthetic SQLite stores, patched query embeddings and forbidden external
clients. Invoke the real frontend parser and React static evidence rendering from
the full FastAPI response offline. Inspect SQL selected columns and ORM load events
to prove large Text never materializes. Cover exact 3,000 / 3,001 boundaries and
the 1,000,008-character reproduction; data/evidence/publication 2/1/2 rejection
before chunk SQL or embedding; older/zero evidence; existing scope/ranking/lineage.

## Completion criteria

All focused tests/checks pass, no selected-filing financial/generation changes,
four empty registries and false activation gate, preserved preexisting changes.

## Final outcome

The three Astra reproductions are resolved within the company-wide mode. Matching
digests cannot authorize malformed filenames; JSON metadata cannot frame passage
text; exact body text survives API-to-real-frontend-parser and complete React
passage rendering. Publication 2 at data/evidence 2/1 rejects before any chunk SQL
or embedding. SQL length projection rejects the entire oversized accession before
loading Text, including its bounded companion chunk; ORM load instrumentation
confirms no affected chunk materializes. The 3,000-character boundary is accepted,
3,001 and 1,000,008 rejected. Inventory caps also reject before Text loading.

Actual checks (2026-10-12):

- Backend cwd, `.venv/Scripts/python.exe -B -m pytest -p no:cacheprovider
  tests/test_company_evidence_search.py tests/test_rag.py
  tests/test_revenue_scope_authorizations.py tests/test_capabilities.py
  tests/test_company_availability.py -q`: **165 passed, 27 subtests passed,
  zero skipped**, 12.73 seconds. Synthetic in-memory SQLite only. Added 23
  backend cases plus strengthened existing count/version/lineage assertions.
- Frontend cwd, `node --test --test-reporter=tap tests/finlens-api.test.mjs
  tests/research.test.mjs tests/research-interactions.test.mjs
  tests/evidence-presentation.test.mjs`: **94 passed, zero skipped**. Company
  fixtures follow the corrected serialization; legacy selected fixtures unchanged.
- Frontend `.\node_modules\.bin\tsc.cmd --noEmit --incremental false` and
  `npm run lint`: passed. Python in-memory AST checks passed. Fresh-process
  checks confirm false activation gate, four empty registries and empty global
  Revenue equivalences. Git diff and new-file whitespace checks passed.

Correction files: backend/app/{freshness_service,rag_context_service}.py,
backend/tests/test_company_evidence_search.py, frontend/lib/research.ts,
frontend/tests/{research.test,research-interactions.test,parse-company-evidence}.mjs,
docs/architecture.md and this plan. The earlier uncommitted implementation and
unrelated next-env.d.ts/runtime reports remain preserved.

No live PostgreSQL/service/browser/cached-encoder acceptance was performed;
concurrent publication under PostgreSQL repeatable-read and actual encoder latency
remain live acceptance gates. Astra High should re-review these three corrections
before commit. No external review/model was invoked. No financial formulas,
authorizations, real DB data, SEC evidence, services or configuration changed.
Git remains main/a08cdaeb7436179d5c95878869bac3a64eb6b9fb, uncommitted, no push.
Suggested commit after review: `fix: enforce company evidence integrity and bounds`.
