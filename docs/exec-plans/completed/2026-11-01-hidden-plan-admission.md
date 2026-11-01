# Dormant hidden-plan admission

Status: completed
Roadmap phase: scoped development-only enabling task

## Objective

Create a backend-only, non-displayable boundary that lets an untrusted JSON plan
select one existing canonical Insights result for one company/metric and two
explicit fiscal years. No model invocation, routes, answers or release admission.

## Current architecture and context

Baseline HEAD: `c8449703e3f8aa62868cfe1cc2993ff6cbcfb973` (main).
`financial_insights_service.build_insights` owns complete bounded fact inventory,
financial calculation, statement validation and F/D reference closure. Its empty
authorization/evidence registry guard must remain unchanged. Existing guarded
runner: `backend/tests/run_financial_insights.py`; see repository engineering
standards and `.agent/PLANS.md`. No `.agents/skills` exists in this checkout or
its D:/Projects parent; root AGENTS.md and .agent/PLANS.md were read.

Initial Git changes are four protected exceptions (untouched): frontend/next-env.d.ts,
two untracked backend/reports JSONs and the untracked annual-comparison Markdown
export plan. Before SHA256 (same order):

- `F4E8976C19FC926644D72610BF1058BD6BF52ADD97E46A02BC0B912A751625C0`
- canary-aapl_guarded_live_20261010_111844_3580610-publication.json: `A783517D2875E39DF4C831C410265D0126FBF6A9D3DDBA1103F7BD61B057844C`
- refresh-discovery-aapl_sec_discovery_20261010_002323_0671678.json: `F8DF96C8890C0ECE1E1701B25BC5C43B879C359ECEB96ACB451A2A0DAA58BF7C`
- annual export plan: `018323260C0FD778346DD397CD419E0F2376018DC2FBE3570BFAD37781B16051`

Authorized synthetic evaluation records outside Git are preserved:
question-results.json `5E8DA765FBB86BC6A856C406F1931ADB22CA325AC348365A06D6B1F156FB41B4`;
semantic-review-and-summary.json `C0083AC5E32BA6BE3FD6EF4868404D7E9095FF6EF95763DD1AA5C4CEA0FE3D5C`.
Original score remains 6/16; S11 violates missing-unit abstention policy and S13
emits an unsupported financial claim from instruction text. Legacy-schema replay
is compatibility evidence only, not a model score or semantic safety evaluation.

## Constraints

No existing-file edits are planned or justified. New module, focused tests,
small labeled fixture and this plan only. No network, services, inference, live
DB, credentials/private env, installs, Git writes, uploads or destructive cleanup.
Canonical preparation retains 10,000 facts / 8 MiB input / 2,000,000 work /
20 seconds cooperative budget. Snapshot projection <=16 KiB, <=4 result cells,
128 nodes, 256 edges, inherited depth 6. Plan <=4 KiB, JSON depth 4, one selection.
Admission <=10,000 visits / 1 second cooperative budget. These are checkpoint
budgets, never hard interruption guarantees for DB/native work.

## Non-goals

Natural language expansion, arbitrary source support, schema/policy changes,
model training, answer coverage, external evaluation or production integration.

## Implementation stages

1. Inspect canonical ownership, safety guards and original evaluation provenance.
2. Implement trusted factory with validated constraints and opaque owned state;
   complete canonical preparation, bounded projection and strict plan admission.
3. Add synthetic positive/negative tests plus honest old-schema rejection replay.
4. Run guarded focused/regression suites, review changes and verify hashes.
Rollback is omission of new files; no runtime/data migration exists.

## Decisions

- 2026-11-01: Reuse build_insights instead of duplicating financial formulas.
- 2026-11-01: Plans can select only VALUE, CHANGE or PERCENT_CHANGE by canonical
  statement key. Snapshot correlation IDs grant no authority. Callers supply a
  controlled read session and explicit constraints, never facts/authorization.
- 2026-11-01: Keep full financial and diagnostic closure server-side, separately;
  preserve canonical limitations. Later consumers must revalidate with a current
  controlled read session before any new handoff. No display consumer is added.

## Discovered issues

Windows restricted-token exec could not start due to split writable roots. The
read-only inspection was rerun via reviewed elevated execution and succeeded.
`rg` is unavailable; used native PowerShell file/text queries. No denial occurred.

The first broad selection used the Insights runner against legacy direct-loader
tests. Its intentional `load_production_evidence = forbidden` stub produced
208 guard failures / 1,142 passes (55.77 s). A narrower attempt exposed the same
entry mismatch in one historical direct-loader test (843 passes / one failure,
49.70 s). These were not application regressions. Split compatible suites and
used the maintained Increment 2 offline guard for synthetic loader tests, with
additional pre-import private-dotenv/model blocking; all separated runs passed.
No safeguards were removed and no live dependency was reached.

## Progress

- [x] Read guidance, current source, test guard/runbook and original evaluations.
- [x] Capture protected/evaluation before hashes; confirm exact baseline.
- [x] Implement isolated module and tests, including canonical limitations' own
  financial closure, separate diagnostic nodes and owned late-result cleanup.
- [x] Run offline validation, scope review and after hashes.

## Test and validation strategy

Use existing runner from backend with `-I -S -B`, disabled plugins/dotenv, blocked
network/DB/model access. Exercise valid canonical selections; wrong company,
metric, period, operation, source/key; malformed/duplicate/deep/oversize plans;
closure completeness; budgets; cancellation; invalid lifecycle; stale data and
configuration; model refusal without inferring missing data; full old-schema
compatibility replay. Relevant regressions: Insights, financial metrics, research
intent/operation handoff and authorization suites. No TS needed (no frontend edits).

### Checks actually run (2026-11-01)

All Python commands used cwd `D:/Projects/finlens-foundation/backend`.
No listener, inference, network, real DB, private env or credential access.

```powershell
.venv/Scripts/python.exe -I -S -B tests/run_financial_insights.py tests/test_hidden_plan_admission.py tests/test_financial_insights.py --tb=short
```

**264 passed** (43.05 s) on the pre-review module: 123 new admission cases and
141 existing Insights cases. Initial new-only run: 117 passed before additional
handoff/cleanup tests. An intermediate focused run passed 263 before adding the
separate limitation-financial-closure case; this is superseded by the final 264.

```powershell
.venv/Scripts/python.exe -I -S -B tests/run_financial_insights.py tests/test_hidden_plan_admission.py tests/test_financial_insights.py tests/test_research_operation_handoff.py tests/test_research_answers.py tests/test_revenue_scope_authorizations.py --tb=short
```

**551 passed** (44.91 s), before the final owned-result cleanup and limitation
closure additions; the final 264 above verify those changes. Existing canonical
financial/intent/authorization modules were never edited.

Legacy-compatible runs invoked `run_dep01a2_increment2_offline.py` through an
isolated `-I -S -B` stdlib bootstrap, adding venv site-packages explicitly,
setting `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, guarding builtins/io/os open against
private dotenv, blocking torch/transformers/sentence_transformers/tensorflow
imports, and disabling dotenv discovery/loading before importing the runner.
The runner preserves its physical psycopg/socket bans. Exact bootstrap and target
arguments are retained in the external owned validation/hash record below.

- Targets `test_financial_metrics.py`, `test_sec_evidence_adapter.py`,
  `test_revenue_scope_authorizations.py`: **586 passed** (8.13 s).
- Target `test_historical_research_answers.py`: **293 passed** (5.53 s), including
  the direct-loader case incompatible with the Insights runner.
- Counts overlap across runs; do not add them as distinct cases. Existing
  Starlette/httpx and datetime.utcnow deprecations remain; no installs performed.
- `git diff --check` and no-index checks on each new candidate: no whitespace
  errors. Git reported its usual LF-to-CRLF advisory only.
- All four protected and two original evaluation SHA256s above matched after.
  Canonical Insights service/contract, research intent service and strict runner
  SHA256s also matched their before values.

## Completion criteria

All new cases and relevant regressions pass offline; only four new candidate
files; protected/evaluation hashes unchanged; no runtime wiring or policy change.
Record exact commands/results, candidate hashes, limitations and commit suggestion.

## Final outcome

Four new files only: `backend/app/hidden_plan_admission.py`,
`backend/tests/test_hidden_plan_admission.py`,
`backend/tests/fixtures/hidden_plan_admission.json`, and this completed plan.
No baseline tracked application file was edited. Initial four protected changes
remain unchanged. HEAD remains the pinned baseline; nothing staged/committed/pushed.

The factory accepts only controlled sessions and revalidated ExplicitRequest
constraints. It internally builds Insights, pins company/metric/years/operation,
all three publication versions, development profile and canonical policy identity.
Plans select one canonical statement or abstain; there is no arbitrary prose,
formula, fact, URL, source ID or caller authorization channel. Owned diagnostics
require identity-preserving revalidation with a current controlled session before
any future handoff. Correlation IDs and copied diagnostics provide no authority.

Limits are cooperative, not hard interruptions. Caller-owned read transactions
and successful cleanup remain required; reusing a stale repeatable-read session
cannot prove a newer database publication. This does not authenticate privileged
Python/database writers. Structured selections do not establish natural-language
intent accuracy. No new model evaluation, answer coverage, prose safety, source
authorization or production readiness is claimed. Original Qwen score stays 6/16;
all 16 legacy outputs fail only the new schema compatibility check. S11/S13 retain
their original failure provenance and are never positive admission examples.

Before/after candidate (before = absent), protected, evaluation and canonical-source
hashes, exact legacy bootstrap, test results and final scope are retained in:
`C:/Users/IITSt/AppData/Local/Temp/finlens-hidden-plan-admission-20261101-6f3a2c84-evidence.json`.
Candidate hashes live outside this plan to avoid self-hash recursion. No blocker.
Suggested commit: `feat(backend): add dormant bounded hidden-plan admission`.

## Independent review follow-up: P3 encoding consistency (2026-11-01)

Independent Astra review found that the depth scanner consumed raw bytes while
`json.loads(bytes)` could autodetect UTF-16/32. Interleaved NUL bytes changed the
scanner's escaped-quote interpretation, allowing a 100-level nested array to
reach the native parser in those encodings within the 4 KiB cap. Public admission
still returned limit_exceeded without a selection; no authorization bypass was
found. This was a pre-parse resource-bound consistency defect.

The justified existing-candidate edits are confined to `_decode_plan`, focused
tests and this record. Bytes now decode once with strict UTF-8; str inputs must
also encode strictly as UTF-8. A leading UTF-8 BOM (bytes or str) and literal NUL
are explicitly rejected. Scanner and native parser consume the identical decoded
str, so there is no native encoding autodetection. Literal malformed/surrogate
input rejects before parsing; JSON-escaped unpaired surrogates cannot satisfy
the existing closed selection schema. No accepted contract field was broadened.
Duplicate-field, depth, encoded-byte size, work, cancellation and admission
boundaries remain unchanged. Native work still has no hard-interruption claim.

Focused validation only, from backend:

```powershell
.venv/Scripts/python.exe -I -S -B tests/run_financial_insights.py tests/test_hidden_plan_admission.py --tb=short
```

**155 passed** (49.50 s): all 123 previous admission cases and 32 new encoding
regressions. Positive cases cover escaped contract fields and multibyte/escaped
decoder strings (decoder acceptance does not authorize unknown plan fields).
Spies prove the native parser is never called for ordinary or adversarial deep
UTF-16/32 (with/without BOM), invalid UTF-8, literal NUL/surrogates or a leading
UTF-8 BOM; the equivalent deep UTF-8 input fails the depth gate before parsing.
The native parser receives exactly the decoded str in valid decoder cases.
No broad regression, model, browser, network, listener, live DB, private env,
install, Git write or destructive cleanup was performed for this follow-up.

The legacy fixture is byte-identical (SHA256
`B62176C6F3AA29A112E501FD5DD88B2B11650F0C286210D1DC4F050B97F48AC7`).
Original Qwen score remains 6/16 and legacy replay remains compatibility evidence
only. Protected/evaluation/canonical-source hashes are rechecked against the
original manifest, which is preserved. Before/after follow-up candidate hashes,
targeted evidence and preservation checks are recorded separately in:
`C:/Users/IITSt/AppData/Local/Temp/finlens-hidden-plan-admission-20261101-6f3a2c84-p3-evidence.json`.
No remaining blocker.
