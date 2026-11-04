# Local hypothetical receipt replay

Risk Lab and Stress Lab support an explicit local JSON download of a current
validated calculation. The same default-off UI flag, backend flags, route
admission, arithmetic and resource protections apply. This is portable replay of
user assumptions and derived hypothetical outputs only. It is not real-source
export acceptance, observed market history, a forecast, probability or advice.

## User workflow

1. Enter assumptions and calculate in the appropriate lab. Review the result and
   audit. **Download current receipt (JSON)** is enabled only for a current result.
2. The browser downloads `finlens-hypothetical-risk-v1.json` or
   `finlens-hypothetical-stress-v1.json`. The product makes no server file request
   and stores no receipt in localStorage, sessionStorage, IndexedDB or cloud.
   The file is deliberately saved on your device by the browser; retain or delete
   it using your normal local file controls.
3. Later, open that same lab and explicitly choose **Import local … receipt**.
   Import validates the untrusted file, restores editable assumptions only,
   clears any displayed result and cancels/invalidate pending calculations.
   **Supplied outputs are discarded.** Review the inputs and explicitly calculate
   again. Import makes no calculation/API request and never automatically retries.
4. Other methods/versions reject; there is no conversion. Invalid files preserve
   the existing draft and any still-current validated result. Cancellation,
   edits, newer imports, submits and unmount prevent late file reads or aborted
   requests from publishing stale state. **Cancel local import** discards the read;
   it does not need to terminate the browser's bounded underlying file operation.

Labels, native file selection and buttons support keyboard operation. Both labs
retain responsive forms and keyboard audit disclosures. Selecting the same file
again is supported because the file input is cleared after selection. Selection
is local reading, not an HTTP file upload; the file control is outside the
calculation form.

## Portable format and limits

The file is the existing complete receipt envelope, with exactly `schema_id`,
`inputs` and `result`. Download is deterministic UTF-8 compact `JSON.stringify`
output in receipt property order plus one LF (no BOM), with MIME
`application/json;charset=utf-8`. Decimal assumptions remain exact strings;
no number conversion, input reordering, factor/shock reassignment or rounding is
performed. Fractions retain exact string numerators and denominators. Object
URLs are revoked after the download click and on failures/unmount. A download
request does not attest that the user retained the file or that browser policy
allowed it.

The Risk schema is `hypothetical-risk-v1`, method `historical-loss-es-v1`;
Stress is `hypothetical-linear-stress-v1`, method
`hypothetical-linear-price-stress-v1`. Both require precision ID
`exact-rational-display18-half-even-v1` and their existing explicit hypothetical
authority labels. This version accepts only its own complete receipt contract.

Import limits: 1 MiB before reading and after reading, strict UTF-8, no BOM,
JSON with no duplicate (including escaped duplicate) keys, nesting at most 16,
at most 50,000 JSON values. Unknown envelope/input/output fields and unsupported
method, precision, authority and schema IDs reject. The declared file size must
match actual bytes. Neither extension nor MIME type grants trust. No markup or
instructions in a file execute or render as HTML.

The editable input contract is validated before restoration: exact shapes,
ASCII IDs/currency, valid Gregorian dates, ordinary bounded decimal strings,
original per-asset mappings, asset/scenario uniqueness, count bounds and the
128 KiB calculation input cap. Risk also requires 0 < confidence < 1, horizon
1..20, strictly positive factors and chronological contiguous intervals, without
filling missing observations. Stress requires the supported explicit linear
exposure type, identical currency, complete explicit shocks including zero,
-100..+1000 percent, and exact-distinct common shocks. See
[hypothetical risk](hypothetical-portfolio-risk.md) and
[linear stress](hypothetical-linear-stress.md) for full model assumptions.

The existing receipt validators check supported output shape/identities/display
and integrity invariants as a format gate. This does **not** certify imported
financial results or authenticate a file. All imported results are discarded,
and the existing backend must calculate fresh outputs from restored assumptions.

## Offline verification

With existing dependencies, from `frontend`:

```powershell
node --test tests/hypothetical-replay.test.mjs tests/hypothetical-risk.test.mjs tests/hypothetical-stress.test.mjs
node node_modules/typescript/bin/tsc --noEmit --incremental false
npm run lint
```

The replay suite captures actual Python receipts from both adapters under the
maintained offline guard, tests exact byte downloads and input round trips,
malicious/oversized/wrong-method files, precision and lifecycle races. It changes
no backend implementation. These fixtures certify synthetic contracts only.

For real-browser checks, use the existing isolated frontend build procedure on
the same drive as its dependency junction. Start only owned loopback enabled
3139 and disabled 3138 production frontends, without a backend. Then run:

```powershell
$env:FINLENS_REPLAY_BROWSER_CHANNEL = 'chrome'
node scripts/verify-hypothetical-replay.mjs
```

Use an already installed browser; no install/download is required. Optional
`FINLENS_REPLAY_BROWSER_URL` and `FINLENS_REPLAY_DISABLED_URL` must be loopback
origins. `FINLENS_REPLAY_LEDGER_PATH` selects a new JSONL artifact; by default every
invocation writes a unique frontend/test-results file. Existing ledgers are never
overwritten. Optional `FINLENS_REPLAY_SCREENSHOT_DIR` retains screenshots. The
ledger records source/receipt hashes, guarded Python outputs, all browser requests
and intercepted API replies, observed assertions, download byte hashes, input
snapshots, revoked URLs, late delivery abort flags, keyboard and geometry checks.
Both widths (1440 and 390) and both labs use actual browser downloads and local
file selection; API replies are synthetic interception, not a live API acceptance
run. All external/unexpected API traffic is denied. Clean only owned processes,
download contexts and verified temporary source copies after unlinking junctions.

## Acceptance limits

Independent review remains required. This frontend-only workflow does not satisfy
source licensing/custody, authorized real holdings/history, calendar/action/FX
verification, live API/DB/provider commissioning, financial/statistical suitability,
cross-browser/device/screen-reader acceptance, release or deployment gates.
No roadmap acceptance status changes. The active ExecPlan records actual checks.
