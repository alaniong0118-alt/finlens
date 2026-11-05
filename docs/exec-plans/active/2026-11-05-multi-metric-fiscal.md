# Bounded multi-metric fiscal answers

Status: scratch implementation complete; independent review pending.

## Objective and scope

Support a closed whole-question grammar for two or three distinct existing
metrics for one selected company and one explicit fiscal year. Reuse the
canonical fiscal-observation engine and source provenance, read facts once, and
retain per-metric unavailable/not-applicable states. Preserve single-metric
behavior and independent filing-evidence failure handling.

## Context and constraints

Starting main `b05f59d706b4e840ebcbebf34c796628000fe0eb`; ten sign-in files and
five protected exceptions are unchanged. All work is scratch-only. No network,
database, Docker, providers, credentials, Git writes, deployment, new formulas,
ingestion or AI. English whole-question grammar is intentionally finite.

## Stages and decisions

1. Bind original source and preservation snapshot.
2. Add an explicit multi-metric response item and bounded recognizer, with
   individual canonical fiscal observations and a single fact read.
3. Render each metric, status and provenance without changing single answers.
4. Test rejection before fact reads, mixed availability, source parity, existing
   contracts and frontend cancellation/switching where affected; package hashes.

## Validation and progress

- [x] Inspected current service, wire shape and UI.
- [x] Captured primary and protected-file snapshot.
- [x] Six synthetic backend tests and 13 existing guarded Chinese regression
  tests pass against the candidate service; fact loading is forbidden for rejects.
- [x] Two static React renderer tests pass. Two mounted lifecycle tests use the candidate renderer with the existing
  primary UI wiring and a synthetic request ledger.
- [x] Four synthetic ASGI route/response tests cover single-answer JSON, mixed
  results, refusal and unknown company. The route AST and decorator come from
  the candidate; session, validation helper and worker are substituted, and
  production middleware and actual application startup are not exercised.
- [x] Scoped TypeScript check and lint pass; lint assumes latest React version.
- [ ] Independent review; real database, live data and browser acceptance.

## Contract and limitations

Whole-question grammar accepts selected-company English requests for exactly two
or three distinct names from revenue, gross profit, operating income, net income,
total assets, total liabilities, operating cash flow and diluted EPS, with an
explicit `FY2024` or `fiscal year 2024`. It does not support company mentions,
other aliases, calendar years, quarters, causality, negation or qualifiers.
The API returns `multi_metric` with separate existing historical-answer items;
all single-answer fields remain unchanged. Aggregate availability means at least
one item is available; consumers must inspect each item's own status. Each item
carries canonical observation, explanation, and full provenance. The current
renderer discloses these individually. Tests use synthetic in-memory records;
no network HTTP server, production middleware, browser, production facts or provider were exercised.

## Completion criteria

Explicit unsupported inputs fail closed; existing single answers remain stable;
multi-metric results preserve canonical provenance and partial availability;
UI and evidence-search behavior remain correct. No claim of real-data acceptance.

## Review corrections

The response flags differing available reporting dates as incompatible; matching
dates remain explicitly unverified, including mixed instant and duration metrics.
Each item retains its own observation and provenance. The renderer shows actual
period dates, revenue basis, and the compatibility notice, and rejects malformed
child company, metric, period or duplicate bindings. Tests resolve repository
fixtures relative to the checkout or an explicit scratch overlay path. Seven
backend and four synthetic route tests, 13 existing Chinese regressions, three
renderer tests and two mounted interaction tests passed. A synthetic backend copy
in a path containing spaces passed the seven backend tests. The customer-contract
basis check is a synthetic renderer fixture; real SEC data remains unverified.
Independent review remains required.

## Malformed response hardening

The multi-response includes the selected CIK, and the filing view passes the
currently selected company CIK for binding. The renderer refuses malformed or
non-array children, mismatched selected/response/provenance company, and
observation fiscal-year/end-year mismatch. It accepts null fiscal labels for
instant observations and does not equate a source filing year with the
observation year. The existing single-answer wire shape is unchanged. All tests
remain offline and this candidate requires independent review.

## Selected-source validation

For the finite direct-metric grammar, available observations must have exactly
one selected source. The renderer checks selected-source metric, exact value,
unit and dates against the observation; SEC URLs must match the producer's
issuer/accession URL construction. Source filing fiscal labels may differ from
the observation year. Unavailable observations retain their reason and sources.
Because the client cannot safely verify server-formatted prose or rounded display,
the multi-item view displays the exact observation value and unit, or its
unavailable reason. Independent review and real-data acceptance remain pending.

## Immutable single-answer parity regression

The previous test resolved both sides to the working service in the primary
checkout. Its four complete canonical JSON SHA-256 values and read counts now
come from the immutable `be3be0c0191d6d7214caf36b66f4dd559cf70b00` service
blob `b9009befe3c1e128422295bf511d6abfd7b9924e` (SHA-256
`23e9c94311ca2e08c754b4206813ce2f8dd6352407826e3e11e2633f349a456a`), using
the existing synthetic fixture and sorted compact JSON encoding. This test needs
no Git process or database at runtime. The four cases do not prove general
single-answer parity; the correction requires independent review.
