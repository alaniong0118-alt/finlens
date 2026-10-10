# SEC evidence adapter blocking review corrections

Status: completed
Roadmap phase: bounded correction of the inactive financial evidence adapter

## Objective
Resolve Astra's three findings: omitted unsupported Inline facts/ancestry, invalid
DEI/target-instance semantics, and unrelated withdrawn scopes blocking active proofs.
All four production registries remain empty; no authorization activation.

## Current architecture and context
Verified main / 7918c24c9457ab4fe39759a06cb749087c9924a9. The adapter, tests,
documentation and loader hook are uncommitted. Preserve all existing changes,
including frontend/next-env.d.ts and the two backend runtime reports. Root
[instructions](../../../AGENTS.md) and [plan standard](../../../.agent/PLANS.md)
apply. The adapter consumes locally pinned originals; the evaluator owns approval
lineage and raw manifests. No formula or evaluator change is planned.

## Constraints and non-goals
No network/models, production data writes, acquisition/ingestion, migrations,
refresh/scheduler, restarts, raw artifact/receipt changes, authorization, commit/push,
redesign or full audit. Source changes limited to adapter and adapter tests; update
the adapter contract only for these behavior corrections. Preserve unrelated files
by comparing their starting hashes at completion.

## Implementation stages
1. Add full-loader adversarial fixtures with matching artifact, receipt, policy and
   approval fingerprints; demonstrate the three defects before source changes.
2. Preflight supported Inline namespaces/structures/ancestry and default-instance
   semantics before building candidates. Strictly validate DEI identity attributes.
3. Skip only scopes the existing evaluator classifies as fully withdrawn; retain
   invalid/ambiguous active-lineage rejection and global successor checks.
4. Run focused adapter/authorization/financial regressions, conditional read-only
   AAPL parity, whitespace checks, registry and preservation checks; self-review.

## Decisions and discovered issues
- Real AAPL markup contains ancillary narrative continuations. The correction must
  reject unsupported ancestry for financial/identity observations without treating
  unrelated narrative continuations as verified financial inputs or breaking the
  already supported original filing.
- The evaluator already distinguishes approval_withdrawn from invalid lineage;
  reuse that distinction rather than pre-filtering withdrawn records out of lineage.
- No active policy may return partial evidence after another active policy fails.
- Namespace/structure preflight occurs before context and candidate construction.
  Numeric facts inside supported TextBlock/continuation ancestry remain in the raw
  inventory (including conflicting values). TextBlock naming is a structural bound,
  never accounting scope authorization. Identity facts cannot use such ancestry.
- The preflight distinguishes normal XHTML header markup from Inline headers and
  requires contexts/units inside default header/resources. Unsupported/nil attributes
  on relevant narrative containers are rejected rather than silently interpreted.

## Progress
- [x] Instructions, Git, relevant code and original Inline containers inspected.
- [x] Adversarial regressions: 38 failures reproduced before source correction;
  five existing safety cases passed in the same selected run.
- [x] Bounded corrections and contract update. Parser revision is sec-inline-v2;
  previous policy revisions cannot silently reuse the corrected parser contract.
- [x] Focused tests, conditional parity attempt, self-review and final checks.

## Test and validation strategy
Tests use only temporary synthetic artifacts and monkeypatched trusted test records;
production emptiness is asserted before isolation. Repin changed bytes and all
fingerprints without calling the parser on invalid fixture construction, ensuring
rejections come from the complete loader, not stale hashes. Cover old/mixed Inline
namespaces, tuples/unsupported ancestry, each nil identity, identity targets,
targeted resources, active plus unrelated withdrawal, moved-period supersession,
withdrawn successors, ambiguity and missing supersession. Reuse existing positive
original-artifact, manifest, isolation, permission and Gross Margin regressions.
The optional database check uses existing repeatable-read/read-only infrastructure
only; never start services. git diff --check and new-file whitespace checks required.

## Completion criteria
All three findings corrected and adversarial regressions pass; unchanged empty I/O,
empty registries and legacy financial outputs; all unrelated hashes preserved.

## Final outcome
Resolved the three blocking findings in the adapter and focused test module only;
updated [adapter contract](../../sec-evidence-adapter.md). No calculator, evaluator,
formula, mapping, economic basis, financial permission or production policy changed.

1. Entire-original namespace/construct/ancestry preflight now rejects legacy/mixed
   Inline namespaces, tuples and unsupported containers before constructing the
   candidate inventory. Legitimate narrative nesting retains its raw observations;
   hidden conflicts cannot disappear. Parser policy revision is sec-inline-v2.
2. DEI identity has strict supported attributes: nil, extra xsi and target semantics
   cannot establish identity. Explicit targets (including empty strings), targeted
   resources and contexts/units outside the default resource structure reject.
3. Only the evaluator's explicit approval_withdrawn result skips a scope. Active
   invalid/ambiguous lineage still aborts evidence; explicit supersession across
   periods works and withdrawn successors cannot revive predecessors.

Validation from backend:
`.venv/Scripts/python.exe -m pytest -p no:cacheprovider tests/test_sec_evidence_adapter.py tests/test_revenue_scope_authorizations.py tests/test_financial_metrics.py -q --tb=short`
Final result: **324 passed**, no skips. This comprises 128 adapter, 79 authorization
and 117 financial metric cases, including 51 new adversarial/safety cases. Existing
FastAPI/httpx and datetime.utcnow deprecation warnings remain. Before correction,
the selected new tests reproduced **38 failures / 5 passes**. The first preflight
attempt rejected valid nested narrative facts in the real filing; the corrected,
bounded ancestry rules retain all 78 relevant observations and the external fixture
passes with the unchanged original and receipt hashes, 860 Inline facts, 161 contexts
and 6 units. Invalid-fixture construction repins bytes, receipts, statement/policy
and authorization fingerprints without asking the parser to approve them. Full
loader assertions also verify the specific rejection stage/reason.

Regression coverage includes mixed 2008/other namespace conflicting Revenue and
Net Income, empty/nested tuples, invalid ancestry, each DEI identity nil/xsi/target,
targeted resources, invalid narrative attributes, supported nested conflicts,
default resources, XHTML-header distinction, both registry orders, moved-period
supersession, withdrawn successors, missing supersession, overlaps/version reuse,
production/synthetic isolation, manifests, hashes, no partial grants and empty I/O.
Existing AAPL Gross Margin and current/historical unavailable fixtures pass.

Live stored-data parity is **unverified** for this correction. A single bounded
existing PostgreSQL connection through read_session raised OperationalError before
the dataset could load. No retry, service start/restart or infrastructure diagnosis
was performed; previous-turn live parity is not claimed as current evidence.

All four production registries were inspected as empty after testing. Starting
hashes preserve the unrelated loader hook, financial documentation, next-env.d.ts,
both runtime reports and prior completed adapter plan. Original artifact and receipt
remain unchanged. Tracked and untracked whitespace checks pass. No SEC/model
calls, production data writes/migrations/refresh, real authorizations, commit or push.

Self-review: the evaluator remains the sole lifecycle authority, retired scopes are
not pre-filtered from its global lineage, invalid active permissions never return
partial proofs, and original bytes/provenance/manifest checks remain intact.
Remaining risks: live DB/HTTP parity unavailable; independent Astra re-review of
these bounded corrections is not performed here. Existing activation trust-anchor,
local-manifest closure and artifact-store limitations remain as documented; no
adapter redesign or financial activation is claimed.

Final Git: main / 7918c24c9457ab4fe39759a06cb749087c9924a9, all work uncommitted.
This correction changes adapter/tests/adapter contract and adds this plan; previous
changes remain preserved. Suggested commit:
`fix: reject unsupported SEC evidence and isolate withdrawn scopes`.
