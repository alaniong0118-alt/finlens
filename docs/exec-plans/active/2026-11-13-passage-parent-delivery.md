# Filing passage comparison parent delivery

Status: active; bounded complete candidate validated and frozen for independent review
Roadmap phase: complete an existing evidence workflow; no feature expansion

## Objective

Deliver one exact HEAD-relative candidate that exposes the existing explicit
two-excerpt wording comparison through public filing research. Preserve original
passages, accession-scoped sources, source offsets and literal text. Comparison
must require deliberate pairing, bounded local computation and a current settled
two-filing search; edits, errors and publication changes must revoke old results.

## Current architecture and context

Read AGENTS.md, ROADMAP.md, .agent/PLANS.md, engineering standards, delivery
assessment and the report/passage parent plans. HEAD is
17be7b5ba856a6b881a79c2c778bb6bf85eca297. Entry read-only status succeeded and
showed extensive modified/untracked files; nothing was staged by this task.
Existing A-D/F and standalone G candidates are immutable predecessors. G's
independent acceptance is at D:/Projects/finlens-G-independent-review-20261113/review-report.txt.
The current dual-filing component also contains indexed-filing discovery; the
stylesheet contains many unrelated features. Neither whole current file is a
delivery candidate. Existing parent code is already implemented: reconstruct its
passage-only hunks and prove the complete integration before changing behavior.

## Constraints

No database, provisioning, network, installation, settings, credentials, Git
stage/commit/push, ownership workaround or C5 retry. After the entry status use
only raw metadata for preservation. Preserve all existing dirty files and prior
evidence. No private environment values are read. Use installed Node/Python and
offline mocked transport only; label synthetic source fixtures explicitly.

## Non-goals

Report export, indexed-filing finder, private persistence, full-document redline,
semantic change claims, chronological inference, AI, source acquisition, release
and publication. Do not promote the roadmap or treat partial reconstruction as
permission to stage mixed files.

## Implementation stages

1. Capture repository/prior-evidence/raw-Git hashes; reconstruct HEAD from the
   accepted archive and overlay exact accepted F/G dependency closure.
2. Add only the existing passage component/kernel/test, its small parent mount
   hunk and its stylesheet rules. Keep F/G partial reconstructions exact.
3. Run dedicated comparison and relevant compatibility/lifecycle suites; add a
   maintained public-parent journey only if needed to cover inventory-to-pair
   composition. Verify TypeScript, scoped lint and source import closure.
4. Freeze exact manifest, complete HEAD-relative patch, preimages, candidates,
   command/failure receipts, preservation and replay. Self-review and report
   remaining independent/native-browser/build/live/release gates.

## Decisions

2026-11-13: Select passage comparison because it reuses public HEAD filing
research and the accepted F lossless source parser. Include the full exact F/G
dependency closure in the review snapshot; clearly distinguish inherited paths
from this parent's own paths. Keep the existing native filing selects. Discovery
and report/private workflows are separate parents.

## Discovered issues

The shell has no rg binary; use native file reads/searches. No action denial has
occurred. C5 is inherited UNEXECUTED and must remain so. Prior browser/build
receipts describe different dirty candidates and cannot certify this reconstruction.

## Progress

- [x] Read governing instructions, roadmap, assessment and accepted G review.
- [x] Define bounded passage-only dependency reconstruction.
- [x] Exact candidate tests, parent journey, types/lint and source closure.
- [x] Freeze/replay/preservation and self-review.
- [ ] Separate independent candidate review (outside this author task).

## Test and validation strategy

Use E:/node.exe --test --test-isolation=none --test-reporter=tap on the exact
snapshot. Dedicated passage tests cover lossless alignment, non-color labels,
explicit selectors, source provenance, Strict Mode, errors/insufficient evidence,
resource refusal and ignored-abort ownership. Relevant F/G suites remain exact
accepted bytes. Record cwd/argv/start/end/exit/stdout/stderr; retain failures.
No native browser/build/live transport or backend/DB/provider claim follows from
JSDOM. New tests must deny unexpected fixture transports even if product code
catches their rejected fetch. Run installed no-emit TypeScript and scoped ESLint.

## Completion criteria

Complete local candidate means exact dependency closure; substantive maintained
comparison plus public-parent journey passing; provenance/error/accessibility
semantics checked; relevant compatibility/type/lint checks passing; exact patch
replay and preservation verified. Independent review and broader native/live/
release gates remain explicit, and do not prevent reporting bounded author work.

## Final outcome

The existing implementation works on the isolated HEAD-relative reconstruction;
no new application behavior change was necessary. Repository additions are this
plan and `frontend/tests/passage-parent-journey.test.mjs`. Existing runtime,
tests, plans and reviewed predecessor bytes remain unchanged. Reviewable runtime
integration is in the external exact candidate, not a replacement of dirty files.
Suggested eventual commit, after exact review and delivery authorization:
`feat(research): integrate explicit filing passage comparison`.

## Executed validation — 2026-11-13

Evidence root: `D:/Projects/finlens-passage-parent-20261113/`. All Node commands
run via the retained `run_case.py` using installed `E:/node.exe`. Exact snapshots
live under `snapshots/<group>/frontend`; receipt JSON records literal argv/cwd,
UTC start/end, exit and raw stdout/stderr hashes. No dependency installation ran.

Actual command suffixes after `E:/node.exe`:

    --test --test-isolation=none --test-reporter=tap tests/filing-passage-comparison.test.mjs
    --test --test-isolation=none --test-reporter=tap tests/passage-parent-journey.test.mjs
    --test --test-isolation=none --test-reporter=tap tests/filing-passage-comparison.test.mjs tests/passage-parent-journey.test.mjs tests/dual-filing-evidence.test.mjs tests/dual-filing-lifecycle.test.mjs tests/context-text-fidelity.test.mjs tests/sec-risk.test.mjs tests/sec-risk-comparison.test.mjs
    node_modules/typescript/bin/tsc --noEmit --incremental false
    node_modules/eslint/bin/eslint.js components/dual-filing-evidence.tsx components/filing-passage-comparison.tsx lib/passage-diff.ts tests/filing-passage-comparison.test.mjs tests/passage-parent-journey.test.mjs

Results: dedicated passage 41/41; corrected parent journey 5/5; combined cohort
528/528, zero failures/cancellations/skips/todo; TypeScript and scoped lint exit 0.
Counts overlap: the combined cohort repeats the 61 dual-filing cases three times
through its normal run and the two G lifecycle profiles. Do not add these counts
or describe them as 528 distinct product journeys or a full repository suite.
The existing module-type warning is retained; no package/config workaround ran.

The 5 new maintained cases exercise actual FilingResearch + ResearchFreshness +
dual-filing composition with fixture transports: inventory, version pins 0/7,
ordinary/Strict Mode, both context requests, deliberate selectors, exact originals
and offsets, source links, literal markup, live status/labels, local-only compare,
query invalidation and source-list/error/retry behavior. The dedicated 41-case
suite supplies tampered source/missing-pin/insufficient/late-response/resource
refusal controls. Source import inspection resolves 20 modules inside the snapshot;
no local import is missing or escapes to the dirty repository.

Initial parent test: 1 passed/4 failed, exit 1. The synthetic citation fixture
incorrectly spread source-list-only fields into strict citation objects. The real
validator refused those objects. Restricting that fixture to actual citation
fields fixed the test; no production validator or assertion was weakened.
`parent-initial.test.mjs` and all failed receipts remain frozen.

Two single-defect negative controls use identical tests and change only one product
path each: remove the parent mount; trim alignment spans. Each selected run has
exactly one assertion failure, exit 1, zero skips/cancellations. Initial control
directory preparation failed on cmd's forward-slash junction-target parsing;
original script/partial snapshot/error are retained. Native Path spelling and
distinct successor directories fixed preparation. This was no action denial.

### Actual serializer-to-mounted-parent contract

`backend/.venv/Scripts/python.exe -I -S -B <evidence>/run_capture.py` runs the
unchanged HEAD offline guard before imports, then actual FastAPI/TestClient,
retrieval/evidence policy and accepted F serializer in `snapshots/candidate/backend`.
Two explicit synthetic SQL stores supply distinct accessions for the same issuer;
the original full texts and source identities are recorded independently beside
the raw response bytes, request paths/query/pin, headers, compiled SQL and events.
Both actual responses are 200/sufficient with one passage and one deterministic
embedding call, pin 7, exact offsets/SEC URLs and session-close evidence. Existing
Starlette/httpx deprecation warning is retained. No lifespan, listener, real DB/
SQL execution, model, SEC/provider or credential access ran. This is synthetic
contract evidence, not genuine issuer content or live financial acceptance.

`asgi-parent-command.json` runs the same maintained parent assertions against
those exact base64-decoded response bytes in a separate contract snapshot, using
`--test-name-pattern 'inventory to explicit wording and source reset, strict=(false|true) pin=7'`.
Both cases pass, zero failures/skips/cancellations. The harness changes only
evidence-fixture creation and response delivery, bound by `contract-harness.patch`;
all product bytes and parent assertions remain exact. It verifies the actual
client parser/validator, mounted parent, explicit pairing, lossless alignment,
originals/offsets/links and invalidation. Freshness and inventory still use frontend
fixtures. It is not an actual HTTP frontend proxy or one live browser journey.

## Remaining gates

Separate complete-candidate independent review is pending. Native browser,
responsive/forced-colors/zoom/assistive-technology, production build, live server/
DB/source/provider, actual SQL/storage rights/durability, physical device, release
and publication are NOT_RUN. Prior browser/build results cover different mixed
candidates and cannot close these exact-candidate gates. No E/private/report
parent is closed. C5 stays UNEXECUTED; no ownership failure, denied route or
safe.directory change was retried. No stage/commit/push occurred.

## Exact review boundary and self-review

`delivery-manifest.json` lists seven parent paths and eight inherited F/G paths.
The own dual-filing component and stylesheet are partial reconstructions. The
inherited shared parser and F/G dual-filing test are also partial reconstructions;
none may be replaced with whole current mixed files. The G/F compatibility test
is the declared G successor to F's partial test. Exact accepted final F/G plan
bytes are inherited without editing them; G's final document supersedes its
historical tested-snapshot document only. This plan is a new document successor
to the source-tested candidate, with unchanged tested application/test bytes.

Review only `candidate-final/`, the complete `delivery-final.patch` and manifest.
Raw archive preimages and per-file logical patches are retained. The patch's
explicit CRLF line maps replay to exact raw-byte hashes; the verifier checks the
entire HEAD-plus-declared-overlay snapshot. `review-freeze.json` binds immutable
scripts, source/control snapshots, retained failures, command receipts, captures
and preservation; the freeze verifier uses no Git. Reproduction writes new
sibling evidence and never overwrites original receipts. Prior source/plan/
candidate/review evidence and raw Git metadata are preserved by entry/final hashes.

Self-review found no new production defect. The parent admits only settled,
validated source results; failed/partial results cannot enable a pair. Pairing is
explicit, computation is bounded, original words are preserved and untrusted
markup remains text. Accessibility evidence is limited to native labelled
controls, disabled/status semantics, non-color annotations and DOM behavior.
No physical keyboard/browser/assistive-technology acceptance is inferred.
