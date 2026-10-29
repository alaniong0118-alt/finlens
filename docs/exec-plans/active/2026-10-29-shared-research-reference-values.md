# FL-ALL-1215-W1-C1 — Inert identity and evidence reference values

Status: active for independent review handoff; bounded implementation and local validation complete.
Roadmap phase: scoped shared-contract enabling task; no next milestone authorized.

## Objective

Implement the complete [C1 representation lock](../../shared-research-contracts.md#proposed-c1-representation-lock-for-focused-review)
as immutable standard-library values with closed, bounded v1 byte serialization.
Structural validity must never confer identity, source, rights or ownership authority.

## Current architecture and context

2026-10-29 entry: main, HEAD `791a4c5dd93f5cf92cbc802662027126d5388cee`,
empty index. Only original exceptions: modified frontend/next-env.d.ts and the two
untracked AAPL reports identified in the task. All three SHA-256 values matched
the supplied baselines. No task path had pre-existing changes. Root AGENTS.md,
.agent/PLANS.md, ROADMAP.md, engineering standards, full-feature register and the
complete C1 lock were read. Current user authorization supersedes the historical
pending-review/NO-GO wording for bounded C1 implementation only.

Protected entry/closure SHA-256 values (all matched):

| Repository path | SHA-256 |
|---|---|
| frontend/next-env.d.ts | F4E8976C19FC926644D72610BF1058BD6BF52ADD97E46A02BC0B912A751625C0 |
| backend/reports/canary-aapl_guarded_live_20261010_111844_3580610-publication.json | A783517D2875E39DF4C831C410265D0126FBF6A9D3DDBA1103F7BD61B057844C |
| backend/reports/refresh-discovery-aapl_sec_discovery_20261010_002323_0671678.json | F8DF96C8890C0ECE1E1701B25BC5C43B879C359ECEB96ACB451A2A0DAA58BF7C |

## Constraints

Only research_contracts.py, its focused test file, this plan, and C1 records in
shared-research-contracts.md may change. Never inspect/hash backend/.env. Preserve
the three exceptions. No staging, commit, push, dependency installation, database,
network, services, model loading or operational imports. Keep the plan at this exact
authorized active path for review handoff.

## Non-goals

C2-C9 adapters/production integration; authentication, acquisition, source authority,
financial values/calculation changes, Reader activation, routes or deployment.

## Implementation stages

1. Verify baseline and lock; write this record before implementation.
2. Implement closed immutable values, supplied-context checks and bounded codec.
3. Add offline boundary, negative, mutation and forbidden-effect tests; debug/retest.
4. Record actual checks, self-review, preservation and independent-review handoff.
Recovery is removal/reversion of only the four authorized candidate paths; no data
or production state is touched.

## Decisions

- 2026-10-29: use frozen slotted dataclasses with exact-type validation and tuple
  nesting; full-record equality/hash and separate KeyRef equality remain explicit.
- Use a bounded JSON parser with duplicate detection before dict insertion, lexical
  byte/depth preflight, incremental node counts and bounded integer tokens. The
  closed schema cannot recurse; no generic metadata or operational resolution.
- Time variants have distinct classes; aware text instants normalize only as the
  lock explicitly permits. Date-only values retain their original precision.
- Supplied-context checks require an actual comparable link for every expected
  entity/security/listing key. Null owner/session expectations are explicit public
  context; private references require supplied keys. Success returns None and
  confers no authority. No identity, lookup, source or rights decision is inferred.
- AuthorityIdentifier duplicate identity is (scheme, authority, identifier), so
  changing its evidence/effective metadata cannot bypass duplicate rejection.
  Same-symbol aliases use provider/product/symbol plus half-open disjointness.

## Discovered issues

- First focused run: 45 tests, two failed subtests (575 passed). The test matrix
  incorrectly rejected allowed null jurisdiction; that expectation was fixed.
  Python's ISO parser accepted 24:00:00 and normalized it to the next day; explicit
  RFC3339 hour/minute/second limits now reject it before library normalization.
  Immediate retest: 45 tests, 577 passed subtests, zero failures.
- Self-review found that an expected relationship key alone could otherwise
  compare with itself when no actual link was supplied. Such checks now reject as
  unavailable; supplied full records also compare metadata when checking the root.
- No unresolved contract contradiction or representation deviation. RFC3339 input
  allows lowercase t/z; UTC output always uses the locked uppercase T/Z spelling.
  No datetime/tzinfo input or coercive constructor API was introduced.

## Progress

- [x] Baseline, hashes and exact scope verified; authoritative documents read.
- [x] Value objects and codec implemented.
- [x] Focused tests and side-effect/mutation controls run.
- [x] Final self-review, documentation and preservation checks recorded.
- [ ] Independent Astra High implementation review (external handoff, not run here).

## Test and validation strategy

Planned: isolated standard-library unittest execution with -I -S -B; strict field,
union, context, integer, temporal, string, collection and aggregate boundaries;
immutable-copy and targeted mutation controls; guarded import/construction;
in-memory syntax compilation, whitespace and four-path Git scope verification.
Exact commands/counts/results will be recorded after execution. No real-source,
database, browser, provider, model or deployment tests are applicable to inert C1.

### Checks actually run (2026-10-29, repository root; existing Python 3.14.7)

1. `backend/.venv/Scripts/python.exe -I -S -B backend/tests/test_research_contracts.py`
   — final candidate: **49 tests passed, 609 successful subtests, zero failed
   subtests/errors/skips**. Expanded coverage includes nullable metadata keys,
   every session origin, absent comparable context links and RFC clock ranges.
2. That suite executes eight in-memory semantic mutants: boolean pins, namespace,
   canonical CIK, equal interval, overlapping aliases, duplicate JSON names, owner
   context and hash case. Each original rejects; each mutant reaches and wrongly
   accepts its changed branch. No files are mutated by these controls.
3. Fresh child `python -I -S -B -c <guard probe>` inside the same suite — guarded
   module execution, all eight root fixtures (both entity variants), nested
   constructors, codec and supplied-context checks passed with zero attempted
   forbidden effects. Ten positive sentinel controls detect file, environment,
   socket, ID/entropy, registry and forbidden application/database/model imports;
   caught attempts remain recorded. Source compilation and stdlib dependency
   loading occur before installing sentinels. AST import allowlist also passed.
4. `backend/.venv/Scripts/python.exe -I -S -B -` with an ephemeral stdin validator
   — AST parse and in-memory compile of both new Python files; UTF-8, trailing
   whitespace and exact single-newline EOF for all four paths; exact Git path set;
   main/HEAD/index; all three SHA-256 baselines; C1-only documentation edits and
   local links all passed. Compared HEAD/current contract prefix and C0 suffix,
   and the complete locked tables/normative rules: unchanged. No pyc writes.
5. `git diff --check -- docs/shared-research-contracts.md` — exit 0, no whitespace
   errors. Git's informational LF-to-CRLF notice does not describe a content error.
   The stdin whitespace validator covers the three untracked additions too.
6. `git diff --no-index --check -- NUL <path>` for each of the three new paths
   — no whitespace-error diagnostics (only LF-to-CRLF notices). Exit 1 is the
   expected new-file difference from NUL, not a whitespace failure. Rechecked
   syntax/whitespace/scope/preservation after the final documentation edits.

Exact-boundary evidence: valid whitespace-padded v1 input at 65536 bytes passes,
65537 bytes rejects before string parsing. All applicable string and collection
limits have exact/one-over controls. Generic depth 8 and 2048-node parser fixtures
parse internally but reject as C1 schema; depth 9/2049 nodes reject at their limit.
The closed schema reaches depth 5 and cannot reach a valid 2048-node boundary;
tests do not claim otherwise. Reduced-cap controls prove direct-constructor
byte/node/depth enforcement. No wall-time or RSS acceptance was measured.

Cases not tested: real identity resolution/authority, C7 authentication, rights or
admission resolution, real source custody, database snapshot/publication admission,
financial/market native adapters, application HTTP/browser behavior, operating
resource bounds, cancellation, providers/models and deployment. Existing Reader,
financial coverage and broad browser audits were deliberately not rerun.

## Completion criteria

Complete locked representation and focused checks; protected state unchanged;
four-path scope only; honest limits and later dependencies recorded. GO means ready
for independent Astra High implementation review, never integration approval.

## Final outcome

Local implementation is **GO for independent Astra High implementation review**;
independent verdict is pending. All frozen values, strict structural validation,
bounded v1 codec and context comparisons are in the two new Python files. The
contract document records only the approved C1 representation/candidate evidence.
All three protected hashes match the task baselines. Private backend/.env was
never inspected, hashed or modified. HEAD and empty index remain unchanged.

Final Git scope: modified docs/shared-research-contracts.md; three new authorized
paths; original modified frontend/next-env.d.ts and two untracked reports preserved.
No staging, commit or push. No application module imports the candidate and no
production behavior changed. Keep this exact active plan path for independent
review; local implementation completion does not close that external gate.

Remaining C2-C9 dependencies: authenticated ownership and source/rights/admission
resolvers; reviewed native database/SEC/market identity and pin adapters; retained
artifact/version/locator storage; observation/financial bridge and receipts;
validated generation; bounded jobs, cancellation and retention. Each needs separate
authorization and actual runtime/product acceptance. None was started.

Suggested eventual commit (not authorized):
`feat: add inert research identity and evidence reference contracts`.
