# MD-WIKI increment 1: bounded offline observation adapter

Status: active
Roadmap phase: scoped offline enabling task; no next milestone authorization.

## Objective

Validate supplied WIKI/PRICES original response and operator receipt bytes and
project immutable, explicitly unverified raw-close observations. No publication,
financial eligibility, adjusted series, returns or performance calculations.

## Current architecture and context

Read [repository instructions](../../../AGENTS.md), [roadmap](../../../ROADMAP.md)
and [plan rules](../../../.agent/PLANS.md). Existing market contracts and returns
remain authoritative and unchanged. The Tiingo history inspector cannot accept
WIKI envelopes or multi-year coverage. See [history documentation](../../market-data-history.md).

Starting branch main, HEAD fddbe2e76d314ac9086d2b00dab23558d03672ea; empty index.
Preserve these pre-existing files and SHA256 fingerprints:

- frontend/next-env.d.ts: F4E8976C19FC926644D72610BF1058BD6BF52ADD97E46A02BC0B912A751625C0
- backend/reports/canary-aapl_guarded_live_20261010_111844_3580610-publication.json: A783517D2875E39DF4C831C410265D0126FBF6A9D3DDBA1103F7BD61B057844C
- backend/reports/refresh-discovery-aapl_sec_discovery_20261010_002323_0671678.json: F8DF96C8890C0ECE1E1701B25BC5C43B879C359ECEB96ACB451A2A0DAA58BF7C

backend/.env is ignored; its private fingerprint is recorded only in tool-session
state for comparison, without reading or printing its contents.

## Constraints

Only four authorized paths: this active plan, backend/app/nasdaq_wiki_adapter.py,
backend/tests/test_nasdaq_wiki_adapter.py and docs/market-data-history.md.
Keep this plan in active by explicit user instruction. No staging, commits,
pushes, deployments, dependencies, configuration, services or database access.
Do not read, transform or modify operator originals. Tests use only fictional
response/receipt bytes constructed inside the new module's test file.

## Non-goals

No CLI/filesystem reader, provider acquisition, numeric change diagnostic,
calendar inference, identity fabrication, action approval, MarketPublication,
adjusted-price display, return engine changes or performance calculation.

## Implementation stages

1. Verify baseline, protected fingerprints, empty index and ignored environment.
2. Implement strict bounded original-byte/receipt/request/schema validation and
   frozen observation projection using existing market error/numeric conventions.
3. Add focused synthetic tests and public contract documentation.
4. Run only the new test module, necessary syntax checks and git diff --check;
   self-review financial boundaries and verify preservation before handoff.

## Decisions

- 2026-10-19: No canonical publication: ticker data and operator declarations do
  not establish security/listing/currency/calendar/corporate-action authority.
- 2026-10-19: Preserve capture timestamp text, including seven fractional digits;
  it is a run timestamp, never a per-response retrieval/availability receipt.
- 2026-10-19: Full acquisition validation precedes narrower selection; all hashes
  remain separate from publication manifests or version pins.
- 2026-10-19: Real-byte schema compatibility is unexercised. Synthetic acceptance
  proves behavior for the explicitly supported schema only.
- 2026-10-19: Require explicit expected run identity and acquisition dates as well
  as the response pin and selection. Support an optional independent receipt pin.
  One response per call; other receipt records are structurally checked only.

## Discovered issues

- Known coordinator-supplied blocker: missing AAPL dividends on 2017-11-10 and
  2018-02-09. Preserve this warning; do not repair original indicators.
- No backend/tests/conftest.py exists; focused tests follow existing standalone
  offline test imports. No application test harness is needed.
- First focused run: 152 passed, 1 failed. The invalid-empty-receipt test failed
  inside its fixture helper before reaching the adapter. Fixed the test to mutate
  already-bound synthetic metadata; added adjacent receipt/digest boundary cases.

## Progress

- [x] 2026-10-19: baseline and protected fingerprints verified; scope reconciled.
- [x] Adapter and synthetic tests implemented; history documentation appended.
- [x] Focused checks, self-review and final integrity verification recorded.
- [ ] Coordinator independent review (outside this implementation task).

### Increment 1B compatibility repair and retained-original acceptance

- [x] Baseline rechecked: main at the expected HEAD, empty index, all three
  protected hashes match; five existing market files/scripts unchanged. Ignored
  backend/.env fingerprint agrees with the preceding increment's fingerprint.
- [x] Correct the confirmed volume declaration from BigDecimal(37,0) to
  BigDecimal(37,15), preserving exact schema validation and shared Decimal bounds.
- [x] Run the existing focused synthetic module plus targeted schema regression.
- [x] Independently pin response/receipt bytes, then invoke the public adapter on
  all three retained originals and require counts, dates, missingness and blockers.
- [x] Verify original/receipt and protected/environment integrity; syntax and
  diff checks; record the consolidated handoff. Keep this plan in active.

The coordinator now explicitly authorizes reading only the three named originals
and verification.json in the retained pilot directory for read-only acceptance.
This supersedes increment 1's prohibition on original reads for that acceptance
only. No report files, fixture copies, CLI, network, database or financial admission.
The same four-file edit allowlist applies. Response SHA256 pins are supplied by
the coordinator; receipt pin is
aa9937be47b95b665c8363fe99c004dddbb2b8e5358b416215f7158bccf70134.
Acquisition 2014-06-01 through 2018-03-27; selection 2014-06-10 through 2018-03-27.
Expected acquired/selected counts: AAPL 961/955, MSFT 962/956, COST 961/955.
No earlier market/Tiingo/MD-01 suites or completed manual audits will be repeated.

## Test and validation strategy

From backend, use the existing environment with no bytecode/cache writes:
`.venv/Scripts/python.exe -B -m pytest -p no:cacheprovider tests/test_nasdaq_wiki_adapter.py -q`.
Test strict payload/receipt/schema/request/pagination/numeric/date/resource
boundaries, immutable exact projections, selection versus acquisition, missing
dates, non-promotion of actions/adjustments, capture precision, and pure offline
isolation. Do not rerun completed Tiingo or market-return suites.

## Completion criteria

Only authorized files changed; new focused tests pass; no original data used;
no fabricated financial contracts or numeric diagnostic; protected files and
ignored environment remain unchanged; independent review limitations explicit.

## Increment 1 final outcome (historical)

Implementation and offline synthetic verification complete; this plan stays in
active by user instruction, pending coordinator review. Only the four authorized
paths changed. No originals or actual financial datasets were read, transformed
or modified. No staging, commit, push, installation, service, database, provider
request, deployment or activation occurred.

Actual checks on 2026-10-19:

- From backend, `.venv/Scripts/python.exe -B -m pytest -p no:cacheprovider
  tests/test_nasdaq_wiki_adapter.py -q`: final **172 passed, 0 failed, 0 skipped**
  in 0.32 seconds. Only this new test module ran.
- From repository root, existing Python with `-B` and `compile(source, path,
  'exec')`: both new Python sources passed syntax checks without bytecode output.
- Four authorized files passed a scoped trailing-whitespace check.
- `git diff --check`: passed. No configured scoped lint/formatter was found;
  no tooling or dependencies were installed.
- All three protected worktree hashes and the five existing market-module/script
  hashes match the initial snapshot. backend/.env's private fingerprint is
  unchanged and it remains ignored. Branch/HEAD and empty index are preserved.

Self-review: exact byte/receipt/request/schema/pagination bindings fail closed;
full acquisition validation precedes selection; seven-digit capture text survives;
unknown identity/calendar/currency/actions are never manufactured. Original byte
hashes bind adjusted fields even though adjusted values are not projected. Source
metadata and consistent hashes never become authenticated custody or financial
correctness. No existing return infrastructure was changed or bypassed.

Remaining boundaries: actual original-byte schema compatibility is unexercised;
corporate actions, identity, calendar/currency authority, provider custody and
historical availability remain unverified. Known AAPL dividend incompleteness is
retained as a coordinator-supplied dataset warning, including for synthetic input.
No financial eligibility, adjusted returns, total returns or performance accepted.

Recommend a narrow independent Astra High review of these four files and the
new synthetic test results. Do not expand to prior MD-01/Tiingo/return audits or
read originals without separate authorization. Suggested future commit message:
`Add bounded offline WIKI observation adapter`. Git steps remain unauthorized.

## Increment 1B outcome

The only adapter source correction is the exact volume type declaration:
BigDecimal(37,0) -> BigDecimal(37,15). The remaining 13 column declarations,
strict schema matching, shared Decimal input limits and financial trust model
are unchanged. Synthetic fixture schema and documentation now match; three
targeted cases accept the observed type and reject obsolete/arbitrary alternatives.

Actual verification (2026-10-19):

- From backend, `.venv/Scripts/python.exe -B -m pytest -p no:cacheprovider
  tests/test_nasdaq_wiki_adapter.py -q`: **175 passed, 0 failed, 0 skipped**
  in 0.33 seconds. No other suites ran.
- Read-only inline acceptance, using the same interpreter with `-B`, first read
  each of the four named originals/receipt with explicit byte caps and verified
  every supplied SHA256 pin independently of the adapter. The recorded receipt
  hash was supplied through expected_receipt_sha256 on every public-interface
  request. No report file, fixture copy or CLI was created. A process audit guard
  rejected write-open, file mutation, socket and subprocess events during acceptance.
- AAPL: PASS, 961 acquired / 955 selected; 2017-08-07 absent.
- MSFT: PASS, 962 acquired / 956 selected; 2017-08-07 present.
- COST: PASS, 961 acquired / 955 selected; 2017-08-07 absent.
- For all three: acquisition extrema 2014-06-02 through 2018-03-27;
  selection extrema 2014-06-10 through 2018-03-27. Exact selected source row
  references, dates and Decimal closes matched; no fill, interpolation or
  fabricated sessions. Capture text retained all seven fractional digits.
- All required blockers, including the known AAPL dividend limitation, survived.
  Trusted custody remained false; identity/currency/listing/calendar/actions
  unverified, financial eligibility blocked, publication not created, adjusted
  series and returns unavailable, retrieval/availability timestamps null.
- Fresh reads after acceptance matched the fixed pins and all initial bytes for
  all three originals and verification.json. No other compatibility defect or
  numeric-bound incompatibility was encountered; no limits were relaxed.

Remaining conditions: this is compatibility acceptance for these four local byte
artifacts only. It authenticates neither provider custody nor financial correctness
and does not approve returns or performance. This supersedes increment 1's historical
statement that original-byte compatibility was unexercised. Keep this plan in active.
Final checks passed: both Python sources compiled in memory with `-B`; all four
task files passed whitespace checks; `git diff --check` passed. All three protected
repository hashes, the five existing market-module/script hashes and the ignored
backend/.env fingerprint remain unchanged. main/expected HEAD and empty index
are preserved. A before/after source comparison confirms exactly one adapter
literal changed. Only the same four authorized task files were edited.

Verdict: PASS WITH CONDITIONS for structural compatibility of these pinned local
artifacts; financial admission remains blocked. The final four-file task diff is
ready for narrow independent Astra High review. No unresolved compatibility
error, staging, commit, push, acquisition, database operation or deployment.
