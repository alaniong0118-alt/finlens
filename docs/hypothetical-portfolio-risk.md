# Hypothetical portfolio risk development candidate

This opt-in educational workflow uses **user-entered synthetic factors**, not
market history, forecasts or recommendations. It does not complete requirement
10a live-data acceptance. It reuses `backend/app/portfolio_risk.py` without changing
its financial arithmetic. The application does not persist receipts or send them
to providers. Users may explicitly save a hypothetical receipt locally and later
read a selected file on-device. No external source data is fetched.

## Enable locally

Using the existing local development launch process, set
`FINLENS_HYPOTHETICAL_RISK=1` on the backend and
`FINLENS_HYPOTHETICAL_RISK_UI=1` on the frontend process, then visit
`/hypothetical-risk`. Both flags default off. Backend profile must be
`development`; `sec_readonly` and `sec_reader` do not admit the new POST route,
even with the flag. Existing restricted route sets and capabilities are unchanged.
The frontend server flag is evaluated per request and the page is not statically
published. A visible page does not confer backend permission.

Set either flag to `0` or remove it and restart the corresponding process to
withdraw the candidate. No schema or data rollback is needed. All ordinary
Research Mode setup and release gates remain as documented elsewhere.

## Enter inputs

Declare reporting currency, exposure date, exact confidence (default `0.95`),
horizon (default `1`) and optionally a portfolio value. Currency syntax is three
uppercase ASCII letters, not certification of an ISO currency or FX authority.
Exposure date is a user assertion; it does not pin market data.

Each exposure line is `asset_id signed_notional_amount`, in reporting currency.
Positive is long, negative is short; these are fixed initial exposures, not shares
or rebalanced weights. Each interval line is
`interval_id YYYY-MM-DD YYYY-MM-DD gross_factor_for_asset_1 ...`, in exposure order.
Every exposed asset needs one strictly positive exact factor per interval.
Intervals must be chronological and contiguous (`previous.end == next.start`).
A factor of `1` means unchanged. There is no fill, drop, interpolation or bridging.
An empty interval inventory returns insufficient scenarios. The supplied dates
cannot prove exchange-calendar completeness, security identity, actions, dividends,
source rights, vintage or the economic truth of a factor.

The adapter accepts at most 8 assets, 120 intervals and horizon 1..20. Identifiers
are 1..64 ASCII characters, starting alphanumeric and continuing with
alphanumerics or `._:-`. Numbers are ordinary exact decimal **strings**, at most
24 coefficient digits and 12 fractional places (maximum 26 characters including
sign and decimal point). No binary numeric values, booleans, exponent notation,
leading plus, whitespace, nonfinite values or implicit percentages are accepted.
Confidence is strictly between 0 and 1. A missing/nonpositive denominator disables
percentages only; it does not erase valid currency loss measures.

## API and receipt

`POST /hypothetical-risk`, `Content-Type: application/json`, identity content
encoding only. Exact top-level keys:

- `reporting_currency`, `exposure_date`, `confidence`: strings as above.
- `horizon`: JSON integer 1..20.
- `portfolio_value`: exact decimal string or null (key is required).
- `exposures`: array of objects with exactly `asset_id`, `amount`.
- `sessions`: array of objects with exactly `session_id`, `start`, `end`, `factors`;
  `factors` maps each exposed asset ID to its exact decimal factor string.

Duplicate JSON keys and unknown fields reject. The streamed body cap is 128 KiB;
response publication cap is 1 MiB. These application limits do not configure a
proxy ingress cap. One calculation may run per backend process; concurrent
requests get 429 and require an explicit retry. Body validation returns 422,
oversized body 413, unsupported content type/encoding 415, disabled candidate 404,
and restricted profile 403. Responses use `Cache-Control: no-store`.

A success contains exactly `schema_id: hypothetical-risk-v1`, `inputs` (the exact
submitted object) and `result` (the kernel's full normalized receipt). Every exact
number has decimal-string `numerator`, positive decimal-string `denominator`,
and a fixed 18-place HALF_EVEN `display`; no rounded result feeds calculation.
Risk values contain `exact` or null plus `reason`. The receipt includes normalized
exposures and factors, method/precision/authority IDs, dates, confidence, horizon,
net/gross exposure, denominator, scenario count, overlap, rank, tail mass, strict
and tied threshold counts, four measures, all sorted losses, exact per-observation
tail masses and notices. Each scenario has panel/first/last IDs and inclusive
start/exclusive stop interval indices. Tail mass is observation mass, not a
normalized probability. Full replay data is available in the UI disclosure.
Explicit local JSON download and assumption-only import are described in
[local hypothetical replay](hypothetical-receipt-replay.md).

Positive loss means loss; negative VaR/ES remain negative. VaR uses nearest rank;
ES uses the existing exact fractional-tail/tie convention. All overlapping
complete windows are used, without an independence claim. Fewer than two scenarios
makes both measures unavailable; tail mass less than one makes ES unavailable.
These computational minima do not establish statistical adequacy or future
coverage. No fees, financing, FX or calendar certification is supplied.

The client verifies shape, input echo, normalized operands, exact/display
consistency, authority/method IDs, scenario ranges and availability consistency.
It does not implement a second financial estimator or authenticate source truth.
Every edit clears the result immediately. Restart, cancel, 10-second timeout and
unmount abort transport and invalidate request identity, including ignored-abort
late responses. Cancellation does not forcibly terminate already running bounded
Python work. Before actual worker entry, cancellation releases the queued slot
and revokes any late callback. After entry, only worker completion releases it;
request cleanup and worker entry use one locked ownership handoff. There is no
automatic retry or product persistence.

## Reproduce verification without services

From `backend`, use the existing offline guard:

```powershell
.venv/Scripts/python.exe -I -S -B tests/run_financial_insights.py tests/test_hypothetical_risk.py tests/test_portfolio_risk.py
```

From `frontend`:

```powershell
node --test tests/hypothetical-risk.test.mjs
node node_modules/typescript/bin/tsc --noEmit --incremental false
npm run lint
```

The client test freshly runs guarded Python tests and consumes actual adapter
output; it does not rely on hand-authored expected response bodies. On this
Windows sandbox, Node subprocess execution requires execution approval.

For actual browser verification, build an explicit source-only temporary frontend
copy using existing dependencies, preserving protected `next-env.d.ts`. On Windows
keep this copy on the same drive as dependencies: Next's cross-drive dependency
junction resolution failed here. Launch the built temporary copy on loopback
3139 with the UI flag `1`, and 3138 with it `0`. Do not start a backend. Then, from
`frontend`, use an already installed browser (no download/install):

```powershell
$env:FINLENS_RISK_BROWSER_CHANNEL = 'chrome'
node scripts/verify-hypothetical-risk.mjs
```

Optional `FINLENS_RISK_BROWSER_URL` and `FINLENS_RISK_DISABLED_URL` must be
`http://127.0.0.1:port` origins. The script checks default-off 404, 1440/390 widths,
keyboard audit disclosures, no page overflow, exact ties/fractional/sparse-tail
states, malformed/error handling, ignored-abort cancellation/edit invalidation,
retry and missing observations. It captures fresh guarded Python output and
intercepts all candidate API requests; unexpected API/external requests fail.
Each verifier invocation retains a machine-readable JSONL execution/request
ledger, including failed runs, in `frontend/test-results/risk-browser-<UUID>.jsonl`.
Set `FINLENS_RISK_LEDGER_PATH` to an explicit new artifact path to retain it
elsewhere. Existing evidence files are never overwritten. The ledger records
source and Python fixture hashes, captured Python results, requests and intercepted
reply bodies, per-assertion observed values, actual ignored-abort deliveries,
viewport/browser identity and final outcome. Screenshots alone do not prove the
whole execution matrix. `FINLENS_RISK_SCREENSHOT_DIR` remains optional.

Close both owned temporary frontend processes afterward. Browser evidence is
synthetic HTTP interception, not real backend/network or live-data acceptance.

## Remaining acceptance

Independent code/financial review, authenticated ownership, real-market source
rights/custody, exact admitted return operands, real calendar/action/FX/vintage
validation, live-data/API commissioning, statistical evaluation and release/deploy
acceptance remain pending. PostgreSQL/provider commissioning is separate and was
not performed. The opt-in route is a local development candidate without public
hosting, rate limiting across processes or hard worker termination guarantees.
See the active implementation plan for exact results and preservation evidence.
