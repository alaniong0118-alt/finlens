# Offline market contracts and deterministic returns

Status: completed (including bounded Astra correction)
Roadmap phase: bounded quantitative foundation; no acquisition or activation

## Objective

Implement immutable offline security/listing/publication contracts and Decimal
split-neutral price / gross ex-date total returns, including Astra's A-F guards.

### 2026-10-12 narrow correction plan

Baseline reverified: main/2c6526508f51f625525898a6aed34187bb719820;
the four task files are untracked. Preserve next-env.d.ts and both runtime reports.
Fix only exact final rounding/compounding, exact immediate-predecessor digest pins,
and dataset publication-ID uniqueness. Keep prior financial/calendar/ML semantics.

- [x] Replace intermediate Decimal split/return/growth arithmetic with exact bounded
  rationals and integer HALF_EVEN rounding; certify logarithm rounding or abstain.
- [x] Bind predecessor ID/version/digest; reject duplicate publication IDs.
- [x] Add Astra reproductions, adversarial ties/lineage regressions and rerun offline
  market tests, narrow financial regressions, syntax/whitespace/inactivity checks.
- [x] Self-review, record actual results and complete correction. No commit/push.

The existing plan was marked active in place during this correction, rather than
creating/moving a fifth file, to respect the explicitly restricted task-file scope.

## Current architecture and context

Main HEAD 2c6526508f51f625525898a6aed34187bb719820. No market contracts exist.
Use pure frozen dataclasses and standard-library Decimal alongside existing
project conventions. Preserve next-env.d.ts and both untracked runtime reports.

## Constraints and non-goals

No provider/SEC/model calls, SQL schema, real DB writes, acquisition/refresh,
API/frontend, training, services, configuration, activation, commit or push.
No annualized statistics or implicit security continuity. No new dependencies.

## Implementation stages

1. Define immutable security, listing, effective-dated symbols, calendars,
   provenance, prices/actions, complete manifests and publication lineage.
2. Implement explicit Decimal policy and adjacent-session returns; normalize
   cash entitlement at its referenced share basis, not the final split factor.
3. Align already computed returns on full intervals and compatible calendars/
   close conventions/currencies. Add minimal knowledge-time/label-window guards.
4. Focused synthetic tests, relevant financial regression, syntax/whitespace,
   self-review and inactive registry/preserved-file verification.

## Decisions

- Raw closes only; vendor-adjusted input never enters this engine.
- Corporate-action coverage is explicit per expected interval. Missing coverage
  cannot mean an action-free day.
- Multiple same-day actions require unique explicit sequence. Post-split cash
  references a specific preceding split; earlier/later factors cannot be assumed.
- Frozen tuples and canonical digests bind complete datasets; conflicting raw
  duplicates fail. Identical duplicates retain provenance references.
- Retrospective vintages cannot pass point-in-time checks. No survivorship-free
  claim is supported by a present-day curated universe.

## Discovered issues

Self-review tightened reused observation IDs, contradictory same-version calendar
schedules, immediate-predecessor body validation and publication-pinned inputs.
Alignment and reinvestment own their calculations instead of accepting stale series.
Forward labels may start at prediction time but must end later and be available by
the training cutoff. Source availability for raw closing prices cannot predate the
session close. Synthetic fixture retrieval time was moved after its last close.
One initial test incorrectly compared preserved raw inventory order rather than
deterministic calculation output; it now checks manifest and interval equality.

## Progress

- [x] Request, baseline and relevant conventions inspected.
- [x] Contracts and engine (2026-10-12).
- [x] Required synthetic cases and relevant regression (2026-10-12).
- [x] Self-review and final checks (2026-10-12).

## Test and validation strategy

Pure fixtures only: splits/dividends/share bases, precision/domain, raw-basis
isolation, missing/holiday/half-day sessions, full-interval alignment, mapping
ambiguity, immutable manifests/revisions, action completeness, vintage/provider
isolation, knowledge cutoffs and forward-label overlap. Run focused pytest,
existing financial regression, in-memory syntax and git/new-file whitespace checks.

## Completion criteria

A-F requirements covered; explicit unavailable states; deterministic outputs;
no external/storage side effects or existing financial changes; inactive gate and
empty production registries preserved. Record actual commands/results below.

## Final outcome

Created only backend/app/market_data_contracts.py, backend/app/market_returns.py,
backend/tests/test_market_returns.py and this plan. Inline deterministic fixtures
were sufficient; no fixture files or dependencies were added.

### Mandatory Astra contracts implemented

- A: distinct frozen Security/Listing identities; company ID/issuer CIK association,
  share class, MIC/currency/calendar; effective-dated exchange ticker AND provider
  symbol mappings; explicit resolution evidence, overlap/reuse rejection and no
  implicit continuity. Changed security/listing identities cannot be corrections.
- B: positive Decimal new/old split ratio; old-share cash or cash referenced to a
  specifically ordered preceding split. Unique sequence is mandatory for multiple
  same-day actions. Ordinary and explicitly gross-cash special distributions only;
  unsupported/ambiguous actions abstain. Ex-date must equal effective date; no
  record/payment substitution. Explicit split/cash/other-action coverage per interval.
- C: raw closes only; exact finite-Decimal rational economic arithmetic; final
  returns/growth rounded by integer remainder/parity to 18 places, HALF_EVEN.
  Logs use certified outer bounds (80/160/320-digit refinement) or abstain. Public
  gross factors remain unquantized 80-digit Decimal approximations for inspection.
  Price factor S*Pcurrent/Pprevious; total factor (S*Pcurrent+D)/Pprevious. Positive
  log domain; explicit precision underflow/arithmetic bounds. Reinvestment chains
  exact rational total factors with fractional shares; unavailable gaps cannot be bridged.
- D: supplied versioned calendar with aware closes/local dates. Supplied holidays,
  half-days and DST supported without generating an exchange calendar. Missing
  observations invalidate adjacent intervals only; next complete pair may resume.
  Panel computes each security first, matches BOTH UTC-comparable interval bounds,
  requires compatible currencies/calendar/close/provider/calculation contracts and
  noncontradictory overlapping schedules. Expected/valid/aligned counts and exclusions
  are retained. No annualized statistics.
- E: frozen tuples and complete supplied raw-inventory count/digest manifests bind
  identity/mappings/calendar/records/coverage/receipts and versions. Conflicts reject
  before selection; identical candidates merge IDs/receipts without double-counting.
  Corrections require a new ID, next independent market version, later publication,
  and explicit valid immediate predecessor pinned by ID, version and manifest digest.
  Publication IDs are unique throughout each supplied dataset/parent inventory.
  Source fingerprints are NOT truth proofs.
  Missing/stale/conflicting/unsupported states remain distinct. No SEC version coupling,
  SQL models or mixed-provider price/action datasets.
- F: pure exact vintage/universe pin, source-availability/economic-date/cutoff checks,
  retrospective-data rejection and forward-label availability/cutoff checks. No model,
  backtest framework, point-in-time certification or survivorship-free claim.

### Actual verification

The following 289-case result records the initial implementation, superseded by
the correction verification below.

From backend: `.venv/Scripts/python.exe -B -m pytest -p no:cacheprovider
tests/test_market_returns.py tests/test_financial_metrics.py
tests/test_revenue_scope_authorizations.py -q`: **289 passed, zero skipped**, 2.51
seconds. Includes 93 new pure market cases and 196 existing financial/scope cases.
Existing FastAPI/SQLAlchemy deprecation warnings only. Financial regressions use
disposable in-memory SQLite; market tests need neither DB nor application imports.
Syntax is checked in memory (no bytecode files). Git diff/new-file whitespace and
fresh-process inactive registry/equivalence assertions passed. No live acceptance,
provider or external review was performed. No frontend test/build was applicable.

### Assumptions and remaining limitations

The supplied calendar, symbol-resolution evidence, action completeness/classification,
source truth and claimed knowledge times need independent verification by a future
adapter; hashes alone cannot establish those facts. IANA timezone data must be
available in the runtime; missing/unknown timezone fails closed. This v1 is raw
close-only, single listing per publication, exact calendar compatibility, no FX or
class/issuer succession bridging. Other actions and incomplete/ambiguous inputs
remain unavailable. Only immediate predecessor contracts are validated; this is
not a persistent lineage service or archive authentication mechanism. The present
universe remains curated, and historical revised data is not point-in-time.

Astra High should review cash entitlement ordering/bases, Decimal precision and
chaining, calendar/interval isolation, duplicate manifests/lineage, and leakage/pin
checks before committing. No adapter, persistence, API, frontend, training, financial
authorization, original SEC evidence or service/configuration was changed.

Git remains main/2c6526508f51f625525898a6aed34187bb719820. Task files untracked;
unrelated next-env.d.ts and both runtime reports preserved. No commit or push.
Suggested commit after review: `feat: add offline market contracts and Decimal returns`.

## Astra correction outcome (2026-10-12)

Only the same four task files changed. No acquisition, storage, application,
financial authorization, configuration or original evidence changes occurred.

### Exact reproductions and proofs

- Split 21/22 then 22/21, raw closes 1 -> 1.0000000000000000015: available
  price and total returns both **2E-18**. Reduced Fraction arithmetic preserves
  exact split products, share-referenced cash, gross factors and chained growth.
  Final rounding uses divmod(abs(numerator)*10^18, denominator): compare twice
  the remainder with the denominator, and at equality increment only an odd
  retained integer. Signed ties and equivalent decompositions agree exactly.
- Growth never multiplies public Decimal approximations or display returns; it
  recomputes exact factors from validated observations/actions and rounds once.
  The original precision policy ID and public Decimal output contracts remain.
- Log rounding encloses the exact rational argument with directed Decimal division,
  applies correctly rounded ln and adjacent representable outer bounds, and accepts
  only if both bounds round to the same 18-place value. Exact ln(1) and zero signs
  are handled explicitly. No fixed precision is presumed to prove a halfway result.
- Successors include predecessor_market_data_version and predecessor_manifest_sha256,
  alongside supersedes (ID), inside their own manifest payload. Actual predecessor
  bodies/manifests must validate, then the complete pin must match. Initial
  publications forbid parent pins. No self-reference enters the digest.
  Same-ID/version/timestamp parents resealed with prices 100 -> 90, changed
  actions/calendar/source fingerprint all reject with predecessor_pin_mismatch.
- Two securities sharing publication-security-a-0 reject with duplicate_publication_id
  before any return calculation, regardless of version, digest or ordering. Pin
  IDs also must be unique. Alignment and ML cutoff share parent-inventory identity
  validation; ambiguous parent IDs cannot be selected by input order.

### Actual correction validation

From backend: `.venv/Scripts/python.exe -B -m pytest -p no:cacheprovider
tests/test_market_returns.py tests/test_financial_metrics.py
tests/test_revenue_scope_authorizations.py -q`: **332 passed, zero skipped**, 2.73s.
136 market cases (43 added), plus 196 unchanged financial/scope regressions.
Existing deprecation warnings only. The first targeted run exposed one old
expected rejection code superseded by the stricter duplicate-ID check; the
assertion was updated. No test failures remain.

Regressions include positive/negative even/odd ties, exact split decompositions,
chained ties, independent exact-rational economic reference expressions, bounded
precision failures, logarithm uncertifiability/zero/domain limits, caller and
global-default trap isolation, predecessor value/action/calendar/provenance
substitution, pin shape/content/digest determinism, multigeneration lineage,
duplicate dataset/pin/parent IDs and order-independent valid alignment.

Python AST syntax (three files), git diff --check and whitespace checks including
all four untracked task files passed. Fresh-process assertions with network
disabled checked the activation gate false, all four production registries empty
and global Revenue equivalences empty before/after importing both market modules.
Preserved-file SHA-256 values exactly match the starting hashes for next-env.d.ts
and both runtime reports. No live-service or provider verification was attempted.

### Self-review and remaining limitations

Exact rationals are capped at 65,536 numerator/denominator bits per supported
intermediate result; logarithm refinement ends at 320 digits. Limit/uncertifiable
cases abstain with precision_limited (intervals contain no numeric outputs;
standalone growth/log operations raise the explicit contract error). Existing
precision_underflow/arithmetic_out_of_range states remain. Conservative limits
may reject mathematically calculable inputs; they never justify an approximate
available result. Contexts explicitly own traps, rounding, exponent limits and
flags. Public gross factors are approximations and are not compounding inputs.

Formulas, entitlement bases, adjacent-session/no-fill rules, raw-only guards,
interval/calendar alignment and ML cutoff guards remain covered and unchanged.
The existing offline trust limitations and immediate-parent-only validation remain;
no provider truth, persistent archive or point-in-time certification is claimed.
Request narrow Astra High re-review of certified rounding/bounds and publication
identity changes before committing; no external review/model call was made here.

Final Git baseline remains main/2c6526508f51f625525898a6aed34187bb719820;
four task files untracked, pre-existing next-env.d.ts modification and both
untracked reports preserved. No commit/push. Suggested commit after review:
`feat: add exact offline market returns and pinned publication contracts`.
