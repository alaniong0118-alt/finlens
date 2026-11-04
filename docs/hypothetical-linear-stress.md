# Hypothetical linear price stress development candidate

This is a bounded educational calculation on explicit user assumptions, alongside
[historical hypothetical risk](hypothetical-portfolio-risk.md). It does not provide
observed market scenarios, probabilities, forecasts, advice, source admission or
completed requirement 11b acceptance. No holdings, source data or external services
are fetched, and no inputs/results are persisted by the product.

## Enable locally

The existing Risk Lab process flags remain default-off:
`FINLENS_HYPOTHETICAL_RISK=1` on a development backend and
`FINLENS_HYPOTHETICAL_RISK_UI=1` on the frontend. Visit
`/hypothetical-risk/stress`, or follow the new Risk Lab workflow link. Both pages
are evaluated dynamically. Removing either flag withdraws its corresponding
candidate surface. A visible UI never grants backend permission.

`POST /hypothetical-stress` shares the historical route's admission, bounded JSON
stream handling and the **same process-wide worker slot**. Restricted profiles
`sec_readonly` and `sec_reader` do not admit this route; no release allowlist or
capability changed. Before worker entry, cancelled queued work releases/revokes its
slot; a late callback cannot calculate or release a reused slot. After entry,
only the worker releases on exit, including exceptions. Requests while either
route owns the slot get 429 and require an explicit retry.

## Model, units and limits

Method: `hypothetical-linear-price-stress-v1`. For fixed signed initial notional
`E` in reporting currency and explicit price shock `s` in percentage points:

```text
contribution P&L = E * s / 100
contribution loss = -contribution P&L
scenario total P&L = sum(contribution P&L)
scenario total loss = -scenario total P&L
common-shock P&L change per +1 percentage point = net exposure / 100
```

Positive notional means long, negative means short. Zero amounts and zero shocks
are valid and explicit. A shock of `-10` means minus ten percent, not a ratio of
minus ten. Positive P&L means gain; positive loss means loss. Negative losses are
preserved. A -100% price shock is supported, including the corresponding short
position gain; lower values reject. No fees, financing, rebalancing, dividends,
corporate actions, time scaling, correlations or causal/economic mappings exist.

Only `linear_price_notional` exposures are supported. Share counts, options,
derivatives, duration/credit/FX exposure types and unknown types reject. All
exposures explicitly declare the identical reporting currency. The currency must
be three uppercase ASCII letters: symbols such as `$`, fuzzy labels, missing
currency and mixed declarations reject. This syntax is a user assertion, not an
ISO registry lookup or FX/source authorization. Asset IDs are labels, not verified
instrument identities; exposure dates are user assertions, not market pins.

| Input | Bound |
|---|---|
| Exposures | 1..8 distinct IDs |
| Named scenarios | 1..12 distinct IDs; exactly every exposed asset in each shock map |
| Common shocks | 1..21 distinct exact values, sorted in the receipt |
| Shock | -100..+1000 percent inclusive; upper bound is computational, not a suggestion |
| IDs | 1..64 ASCII characters, initial alphanumeric then alphanumerics or `._:-` |
| Decimal input | Ordinary string, at most 24 coefficient digits, 12 fractional places, 26 total characters |
| HTTP request / response | 128 KiB / 1 MiB |

No binary JSON numbers, booleans, exponent notation, nonfinite values, leading
plus signs or padded decimal strings are accepted. Duplicate JSON keys, unknown
fields, duplicate assets/scenarios or common shock values reject. Numeric aliases
such as `0` and `-0.0` count as duplicate common values. Complete input validation
precedes arithmetic: even a zero position must have a valid explicit shock.
Missing does not mean zero. There are at most 264 contribution calculations
(8 exposures times 12 named plus 21 common scenarios), with bounded decimal inputs.

Common shocks apply the same explicit percentage to every original position,
**independently of named scenarios**; they are not added to named shocks. Named
scenario order stays as entered; contributions use canonical asset-ID order.
Common rows sort by exact percentage, without silently adding a zero baseline.
Zero net exposure can cancel a parallel common move while differently shocked
assets still produce loss. There is no probability or no-risk inference.

## Entering inputs and API schema

The form requires exposure date and currency. Exposure rows are
`exposure_id signed_notional`; all explicitly use the declared currency and the
single displayed linear price exposure type. Named scenario rows are
`scenario_id shock_for_first_exposure shock_for_second_exposure ...` in the
**entered exposure order**. Reordering rows must not reassign shocks: the submitted
object binds every shock to an asset ID. Common shocks are whitespace-separated
ordinary decimal strings. The form supplies no suggested scenario data.

`POST /hypothetical-stress` accepts application/json and identity content encoding.
Exact top-level fields:

- `reporting_currency`: explicit three-uppercase-letter code.
- `exposure_date`: exact ISO date `YYYY-MM-DD`.
- `exposures`: objects with exactly `asset_id`, `amount`, `currency`, `exposure_type`.
- `scenarios`: objects with exactly `scenario_id`, `shocks`; the latter maps every
  and only exposed asset ID to its exact percentage string.
- `common_shocks`: array of explicit percentage strings.

Status handling is shared with Risk Lab: disabled 404, restricted profile 403,
unsupported content/encoding 415, oversized body 413, invalid input 422 and busy
429. Stable API reasons include `incomplete_shock_panel`,
`unsupported_shock_percent`, `unsupported_exposure_type`,
`exposure_currency_mismatch` and `duplicate_common_shock`. Success/errors use
`Cache-Control: no-store` and the existing hypothetical rejection header.

## Exact receipts and UI lifecycle

Success contains `schema_id: hypothetical-linear-stress-v1`, exact submitted
`inputs`, and `result`. The result records method/precision IDs, authority
`unverified_user_assumptions`, currency/date/exposure type, full normalized signed
exposures, net/gross exposure, slope per common percentage point, every named
scenario's contributions and total P&L/loss, every common-shock row with the same
complete contributions/totals, and fixed model notices. Each contribution retains
asset ID, exact initial exposure, exact shock percentage, P&L and loss.

Every number is `{numerator, denominator, display}` with string integers and
positive denominator. Arithmetic is exact Fraction; only display rounds to 18
places HALF_EVEN using the existing historical kernel's display helper, unchanged.
The full receipt preserves tiny values that round to zero. There is no inferred
portfolio denominator or percentage-of-NAV output.

The client reuses bounded JSON transport and exact/display validation. It checks
input echo, normalized identity/currency/type, contribution formula and loss sign,
sums, net/gross, slope, common-shock ordering and notices before displaying actual
backend values. It does not generate client estimates. Every edit clears stale
results immediately. Restart, cancellation, timeout at ten seconds and unmount
abort transport and invalidate request identity, even when transport ignores an
abort. Cancellation does not forcibly terminate already running bounded Python
work. There is no automatic retry, file upload/download or product persistence.
Tables have captions and column/row headers, focusable horizontal scroll regions,
keyboard disclosure controls, explicit status/error states and narrow layouts.

## Offline verification

Use existing dependencies only. From `backend`:

```powershell
.venv/Scripts/python.exe -I -S -B tests/run_financial_insights.py tests/test_hypothetical_stress.py tests/test_hypothetical_risk.py tests/test_portfolio_risk.py
```

From `frontend`:

```powershell
node --test tests/hypothetical-stress.test.mjs tests/hypothetical-risk.test.mjs
node node_modules/typescript/bin/tsc --noEmit --incremental false
npm run lint
```

The stress client suite captures fresh real Python adapter receipts under the
maintained offline guard, including long/short/zero, decimals, boundaries and
permuted exposure order. No hand-authored financial response replaces the backend.

For actual browser verification, use the existing Risk Lab source-only isolated
frontend procedure with installed Chrome and existing dependencies. On Windows,
keep the temporary copy and dependency junction on the same drive. Run owned
loopback production frontends at 3139 (UI flag 1) and 3138 (flag 0), no backend.
Then from `frontend`:

```powershell
$env:FINLENS_STRESS_BROWSER_CHANNEL = 'chrome'
node scripts/verify-hypothetical-stress.mjs
```

Optional `FINLENS_STRESS_BROWSER_URL` / `FINLENS_STRESS_DISABLED_URL` must be
`http://127.0.0.1:port` origins. Every invocation retains a new JSONL execution and
request ledger in frontend/test-results, or an explicit new
`FINLENS_STRESS_LEDGER_PATH`. Existing evidence is not overwritten. It records
source/fixture hashes, Python results, all requests/intercepted replies, observed
assertions, keyboard states, geometry, cancelled deliveries and final outcome.
Optional `FINLENS_STRESS_SCREENSHOT_DIR` retains owned screenshots. All API replies
are synthetic interception, not live API or market acceptance; all external
requests are denied. Close only owned processes and clean only verified temporary
copies after unlinking their dependency junctions. The unchanged historical
browser verifier can also run against that copy as a regression, with a new ledger.

## Remaining gates

Independent financial/engineering review, statistical/economic model suitability,
real data/source/ownership/custody/calendar/action/FX authorization, actual live
API/DB/provider commissioning, cross-browser/device/screen-reader acceptance and
release/deployment remain pending. Application byte caps do not configure proxy
ingress limits, the slot is per process rather than a global rate limit, and
cancellation is not hard worker termination. This candidate changes no roadmap
acceptance status. See the active ExecPlan for checks actually run and exact scope.
