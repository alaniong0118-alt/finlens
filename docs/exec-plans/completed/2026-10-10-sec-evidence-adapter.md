# Inactive local SEC evidence adapter

Status: completed
Roadmap phase: scoped financial evidence enabling task; no authorization activation

## Objective
Implement an offline, fail-closed producer of independently parsed SourceEvidence.
Production permission and evidence-policy registries remain empty. Empty permissions
must add no file reads or evidence SQL to the existing financial read path.

## Current architecture and context
Baseline: main / 7918c24c9457ab4fe39759a06cb749087c9924a9. Preserve the modified
frontend/next-env.d.ts and two untracked backend runtime reports. The authorization
foundation already implements exact raw manifests, evidence fingerprints, separate
permissions and immutable approval/withdrawal lifecycle. Financial APIs load all
issuer facts inside freshness_service.read_session (repeatable-read/read-only).
Original markup is external to Git; published chunks do not retain XBRL contexts.
See [instructions](../../../AGENTS.md) and [roadmap](../../../ROADMAP.md).

## Constraints
No network, writes to the database, ingestion, models, restart, financial formula
or mapping change, raw artifact copying, authorization activation, commit or push.
Only the explicitly configured local store may supply original bytes. Paths and
proofs are never accepted from HTTP parameters. Existing evidence is read only.

## Non-goals
Activating AAPL Net Margin or historical Revenue, automatic accounting equivalence,
restatement reconciliation, broad coverage audit, acquisition and background jobs.

## Implementation stages
1. Inspect contracts and local original markup; record trust boundaries.
2. Add immutable empty production policy registry, offline parser and internal loader.
3. Connect only the financial dataset loader; preserve empty-registry fast path.
4. Run focused parser/manifest/isolation/legacy regressions; self-review and document.
Rollback is removal of these scoped source changes; no persistent data is changed.

## Decisions
- 2026-10-10: Use standard-library XML parsing; reject DTD/entities, unresolved
  namespaces, unsupported Inline transforms and dimensions. No new dependencies.
- Explicit reviewed policy pins bytes, acquisition receipt, locators, scope, approval
  content/version and local/database inventory. Equality does not authorize scope.
- Initial verification is conservative and uncached. Any failure for the issuer's
  applicable permission set returns no evidence; never partially grant a permission.
- The captured receipt is a local provenance trust anchor, not a SEC digital signature.
  Filed dates must reconcile with pinned publication metadata, not HTTP Last-Modified.
- Policy pins (except the circular approval digest) are included in SourceEvidence
  fingerprints; repinning a receipt/snapshot/parser cannot reuse an older approval.
- Namespace-valued attributes/text resolve in their own element scope. A later
  descendant namespace declaration cannot authorize an earlier unresolved QName.

## Discovered issues
The verified original is well-formed XML without DTD/entity declarations. It uses
2025 us-gaap/dei namespaces and the 2020 Inline num-dot-decimal transformation.
The original contains repeated values in multiple statements; reviewed exact fact
and containing-statement locators are required. Synthetic SourceEvidence is useful
for evaluator tests but is not accepted as input to the production loader.

## Progress
- [x] Baseline/instructions/contracts/artifact inspected.
- [x] Implementation: one adapter module, one internal loader hook, no dependencies.
- [x] Focused tests and unchanged-output verification.
- [x] Self-review: exact provenance, scope, raw manifests, lifecycle, parser security,
  no partial grants, empty fast path, documentation and diff checked.

## Test and validation strategy
Adapter fixtures with network and production DB connection guards; real external artifact parsing
without activation. Negative provenance/context/manifest/version tests. Run existing
revenue authorization and financial metric tests plus git diff --check. Never run
refresh or audit scripts. Record exact executed commands and results below.

## Completion criteria
All production registries empty, no extra empty-path I/O, verified original parsing,
focused failures reject, existing financial regressions pass, diff is scoped/clean.
Independent Astra review is required before future activation, not performed here.

## Final outcome
Implemented the inactive mechanism and [trust-boundary documentation](../../sec-evidence-adapter.md).
All selection/denominator/withdrawal/evidence-policy production registries remain
empty. No real policy, adapter configuration, authorization, acquisition, data write,
refresh, external model, original-artifact copy, service restart or commit occurred.
Existing frontend/next-env.d.ts and both backend runtime reports remain untouched.

Executed from backend:
`.venv/Scripts/python.exe -m pytest -p no:cacheprovider tests/test_sec_evidence_adapter.py tests/test_revenue_scope_authorizations.py tests/test_financial_metrics.py -q`
Final result: **273 passed**, no skips. Existing FastAPI/httpx and datetime.utcnow
deprecation warnings only. Earlier runs exposed one synthetic session-list fixture
mistake (fixed); no production-data failure was hidden. Legacy financial tests use
their existing disposable in-memory SQLite fixtures, never the development database.

The external acceptance fixture verifies the pinned 1,018,326-byte AAPL original
and pinned capture receipt, 860 Inline facts, 161 contexts and 6 units. f-56/f-104
parse to exact USD 109.417B/29.789B, share undimensioned c-18 and primary table 12.
No real approval was constructed or registered. Pure synthetic tests exercise
valid loader/evaluator integration, scale/sign/Decimal, identity/context/units,
namespace scope and unsafe encoding, missing/corrupt evidence, incomplete/new raw
candidates and originals, changed versions/receipts, explicit supersession,
permission separation, absence of public proof/path/flag inputs and no partial grants.

A narrowly scoped PostgreSQL read_session comparison loaded only AAPL company and
facts. Its financial loader executed exactly two SELECTs, no extra evidence query.
Five summaries and twenty histories across five modes exactly matched HEAD 7918c24.
Gross Margin remains 0.5005620698794520047159033788; current Net Margin, FY2018
half-year Revenue and FY2019 half-year Revenue YoY remain unavailable. The two
distinct eligible stored target-quarter Revenue/Net Income identities exactly
match the original's complete relevant undimensioned candidate set. The initial
comparison invocation used an incorrect metric identifier and stopped; the
corrected comparison above passed. No full audit or live-server reload was performed.

`git diff --check` and `git diff --no-index --check -- NUL <new-file>` passed for
new source/test/document whitespace checks. The no-index commands report exit 1
because each new file differs from NUL; they emitted no whitespace errors.
Self-review additionally tightened scalar context
elements, unsupported Inline attributes, per-element QName scope and policy pins.

Activation limitations requiring Astra: independently reviewed capture/filed-date
provenance and accounting scope; local-inventory/legacy-ingestion completeness;
small parser allowlist and original statement locators; lifecycle/permission
isolation and combined-policy abstention; immutable append-only store operation
and filesystem/database snapshot boundaries. No global SEC completeness is claimed.
The first proposed activation remains the separate AAPL Net Margin pair only.

Git remains main / 7918c24, with scoped source/tests/docs changes uncommitted and
the three pre-existing paths preserved. Suggested commit:
`feat: add inactive fail-closed local SEC evidence adapter`.
