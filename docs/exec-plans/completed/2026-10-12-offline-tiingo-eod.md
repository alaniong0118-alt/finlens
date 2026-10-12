# Offline Tiingo EOD normalization

Status: completed
Roadmap phase: bounded market-data normalization; no acquisition or persistence

## Objective

Normalize synthetic documented-field EOD JSON bytes into immutable raw/adjusted
OHLCV sidecars and sealed existing market publications. No available returns may
be inferred from EOD-only corporate-action information.

## Current architecture and context

Verified main/50e4d40d9d8565abb78d04400c9a7a2baa9caf5a. Existing market contracts
and exact return engine are committed and remain unchanged. Canonical prices
are raw-close-only. Preserve modified next-env.d.ts, both untracked backend
runtime reports, original SEC evidence and inactive financial authorization.

## Constraints and non-goals

Pure offline functions and synthetic fixtures only. No network, credentials,
database/persistence, service/configuration, API/frontend, financial authorization,
provider entitlement claims, external model calls, commit or push. No new dependency.

## Implementation stages

1. Strict bounded byte/JSON/numeric/date/provider validation and immutable OHLCV
   records, with deterministic normalized content digests.
2. Explicit request identity/calendar/symbol/provenance/publication pins; build
   raw-close publications and validate with the existing canonical validator.
3. Fail closed for EOD-only actions/completeness/adjustment ambiguity. Never create
   completeness attestations or interpret cash as a verified ordinary dividend.
4. Synthetic/adversarial tests, market regression, syntax/whitespace/preserved-file
   checks, inactive registry assertion and self-review.

## Decisions

- Date is a UTC-midnight session label, not a trading close timestamp; the supplied
  exchange calendar provides the latter. Noncanonical time/offset labels reject.
- Split new-shares/old-share direction requires an explicit format declaration;
  dividend share basis remains unverified. Declarations are not authentication.
  No EOD-only action is installed as a canonical verified corporate action.
- All normalization results are blocked for missing independent corporate-action
  coverage; unsupported/ambiguous actions and adjustments add explicit reasons.
- Raw bytes SHA-256, normalized content SHA-256 and publication ID/version/manifest
  are distinct. Normalized observations bind the full OHLCV/indicator sidecar.
- Reordered JSON changes its raw receipt hash, but not normalized content/order.

## Discovered issues

Tiingo response fields provided in this task cannot establish complete corporate
actions, special-distribution treatment or same-day order/share entitlement. There
is deliberately no switch that promotes EOD-only output to complete/available.
Live provider semantics/entitlements are not externally verified in this task.

## Progress

- [x] Repository instructions, Git baseline and canonical interfaces inspected.
- [x] Adapter and synthetic fixtures implemented (2026-10-12).
- [x] Focused regressions, preservation checks and self-review complete (2026-10-12).

## Test and validation strategy

Synthetic ordinary/split/dividend payloads; strict number semantics, all required
fields, duplicate keys/observations, byte/record bounds, timestamps/sessions,
OHLC/volume validity, symbol/company/calendar isolation, provenance fingerprints,
publication/supersession pins and deterministic normalized output. Assert all
EOD-only return intervals unavailable. Run existing market tests; no full audits.

## Completion criteria

Accepted normalized publications all pass canonical validation; no adjusted price
or unverified corporate action becomes a return input; explicit blocked outcomes;
all focused tests/checks pass and unrelated files/activation remain unchanged.

## Final outcome

Created only backend/app/tiingo_eod_normalizer.py,
backend/tests/test_tiingo_eod_normalizer.py, three JSON fixtures and their README
under backend/tests/fixtures/tiingo_eod/, and this plan (moved to completed).
Committed canonical contracts/return engine and all other existing sources remain
unchanged. No SQL schema, provider client, new dependency or activation path.

### Provider-to-canonical mapping and trust boundary

- date -> immutable session_date/provider_timestamp sidecar; UTC-midnight labels
  must match an eligible supplied exchange-calendar date. Calendar close timestamps
  remain authoritative for observation availability; never convert date labels
  to the previous New York date or treat midnight as the trading close.
- open/high/low/close/volume -> raw Ohlcv; adjOpen/adjHigh/adjLow/adjClose/adjVolume
  -> separate adjusted Ohlcv. Only raw.close -> canonical PriceObservation.close
  with adjustment_basis=raw. Positive coherent OHLC, nonnegative volumes, integral
  raw volume; adjusted volume may be fractional. All values parsed directly from
  JSON numeric tokens into bounded exact Decimal, including exponent notation.
- divCash/splitFactor -> preserved unverified indicators. Format declarations
  explicitly support new/old shares only; inverse/unknown direction and claimed
  verified dividend basis reject. No inferred canonical CorporateAction records.
- Strict response bound 4 MiB, at most 6,000 rows; explicit calendar/request range
  <=10,000 days; exact source provider/product tiingo/eod; effective-dated request
  symbol, security/listing/unit/calendar and existing canonical source validation.
  Unknown/missing fields, duplicate JSON keys, dates/observations, nonfinite,
  coercible string/boolean numbers and out-of-calendar rows reject explicitly.
- Actual payload bytes must match Source.response_sha256. Normalized content
  digest binds sorted full OHLCV/indicators plus identity/mappings/calendar/format.
  It is embedded in canonical observation IDs, binding the sidecar into the
  existing manifest without a schema change. Publication ID/version/parent pin
  remain distinct and use existing exact predecessor manifest validation.
- Raw byte receipt hashes change when JSON order/lexemes change; normalized
  economic content and observation ordering remain deterministic. Different
  receipt/source/version metadata remains bound in the publication manifest.
  Neither receipt nor content digest, format reference or publication ID proves
  source authenticity. EOD rows do not independently identify their instrument.

### Explicit blocking and remaining prerequisite

Every result has status=blocked and missing_corporate_action_coverage. There is
no completeness boolean, supplied coverage override or supported complete-state
publication path. Neutral divCash/splitFactor values never attest no actions.
Canonical state is missing for otherwise ordinary data; unsupported if split,
unclassified cash, same-day split/cash, raw/adjusted differences or unresolved
continuity add blocking reasons. Missing sessions/empty responses also remain
explicit; no fill, gap bridge, adjusted-price substitution or generated return.

Return readiness needs separately verified instrument/date-bound event inventory
and explicit per-adjacent-session split/cash/other-action completeness; verified
split direction/effective dates; dividend currency/classification/gross treatment
and share basis; named split references/order when applicable; unsupported-action
rejection and verified adjustment policy/history. Live provider format details,
custody of request/response identity, commercial entitlement and production
persistence remain outside this task. Do not infer them from synthetic fixtures.

### Actual focused verification

From backend: `.venv/Scripts/python.exe -B -m pytest -p no:cacheprovider
tests/test_tiingo_eod_normalizer.py tests/test_market_returns.py -q`:
**242 passed, zero skipped**, 0.55s (106 adapter + 136 existing market cases).
Synthetic fixtures only, no DB/application fixture or model/provider connection.
No test failures occurred. Tests cover ordinary/split/dividend/reverse-split and
same-day indicators, raw/adjusted isolation, no false action completeness, field
and numeric adversaries, exact precision/ambient-trap isolation, byte/record/date
bounds, missing sessions, effective symbols/identity/continuity, fingerprint/time
checks, deterministic content/receipt distinction and exact predecessor pins.

Two Python AST checks, git diff --check and all seven new-file whitespace checks
passed. Existing backend/app files and existing market tests have no Git diff.
Fresh-process socket-forbidden assertions confirmed disabled activation, all four
authorization registries empty and empty Revenue equivalences before/after the
normalizer import. SHA-256 matches the starting values for next-env.d.ts and both
untracked runtime reports. No original SEC artifact/receipt was accessed or changed.

### Self-review, review scope and Git status

Self-review verified no financial calculation duplication, raw-price substitution,
unverified event authorization or mutable completion switch. Request validation
reuses canonical identity/source/manifest/lineage checks before and after building
the actual prices. Adapter failures expose stable contract reasons without payload,
credential or secret logging. Unknown provider field extensions require a reviewed
new format rather than silent dropping. Pure byte normalization does not certify
an exchange calendar, instrument mapping, source origin or provider data quality.

Narrow Astra High review should examine number/date semantics, explicit split
declaration and unresolved dividend basis, completeness/adjustment fail-closed
behavior, sidecar-to-publication digest binding and exact request/predecessor pins.
No independent review or external model call was performed in this task.

HEAD unchanged: main/50e4d40d9d8565abb78d04400c9a7a2baa9caf5a. Seven new task
files untracked; pre-existing frontend/next-env.d.ts modification and both runtime
reports preserved. No commit or push. Suggested commit after review:
`feat: add fail-closed offline Tiingo EOD normalization`.
