# Source-linked balance-sheet proportions

Status: active; product and two-case synthetic browser reviews passed. The integrated thirteen-file candidate is pending final review; real-data acceptance has not run.

## Objective and context

Add total liabilities / total assets and cash and equivalents / total liabilities to the existing normalized summary response and financial snapshot. Starting HEAD is `1e77745cf3d0f6f17c6ac413e7c5ce0b6c6e628a`, index empty. Five unrelated exceptions (next-env, two reports, annual export plan and completed personal-site plan) are preserved and excluded.

## Constraints and decisions

- No new financial inputs, source admission, authorization, DB writes, acquisition, services, external calls, model, installation or Git delivery.
- Reuse admitted canonical USD instant observations and the Decimal engine. A ratio uses the latest admitted date from its two operand inventories, independently of the revenue anchor. Both operands must exist on that exact date; no older common-date fallback.
- Require the same company, currency, date and selected filing accession/form/filed vintage. Conflicting values within that selected filing refuse calculation. This is observed source compatibility, not proof of dimensional/consolidated coverage.
- Negative numerators and nonpositive denominators are unavailable; zero cash (or zero total liabilities numerator) remains valid. No scores, thresholds, rankings, advice, debt alias or current-ratio label.
- Keep the fifteen existing metrics, histories, annual facade, fiscal guides and calculations unchanged. The public summary route opts into an additive `balance_sheet_ratios` field; other summary callers retain their serialized contract.
- Frontend validates company/date/unit/source identity, SEC archive path and complete operand lineage without recalculating the ratio. It uses the existing summary publication/cancellation ownership, with no new requests.
- The engine keeps source projections opaque. Its existing trusted DB adapter adds a narrow captured-projection consistency operation; unsupported adapters refuse these calculations. This changes no source-admission/access policy and grants no session-source authority.
- Both numerators may be zero; proportions above one are retained. Decimal division uses local precision 28 without float arithmetic or quantization. Each pair may have its own latest admitted date; the UI discloses that it is independent of the selected income interval.

## Implementation stages

1. Add two narrowly scoped engine calculations, summary opt-in/projection and optional serialization.
2. Add validated ratio cards with formula, shared operand date, exact input/source disclosures and honest unavailable states.
3. Test Decimal arithmetic, refusal controls, existing-engine parity and mounted ownership at zero/nonzero publications. Run scoped lint/types and freeze reviewed bytes.

## Validation plan

Use existing guarded Python and Node runners with synthetic detached records only. Cover missing operands, dates/currencies/company/filing mismatch, conflicts, zero/negative inputs, Decimal precision, canonical payload acceptance, malformed lineage/source URLs and stale/ignored-abort/company-switch behavior. Preserve immutable C5 golden serialization, annual/quarter/coverage behavior and the 39 existing latest templates.

Initial browser proposal before execution: two small cases at 1440px and 390px using the existing fixture/harness, checking available and unavailable ratios, dates/formulas/operands/SEC disclosure, keyboard access and contained text, plus company/publication invalidation and no extra ratio request. No new runner infrastructure or browser execution in the initial implementation stage.

For each width, use one already pinned summary response at publication zero, expose the ratio disclosure and sources with native keyboard navigation, then switch company/publication to a nonzero pin and reject a delayed old summary. Include zero cash and a missing same-date input; capture the actual reading/focus geometry and screenshots. Reuse the existing fixture request ledger and CI server isolation. Do not infer visibility from JSDOM or claim a browser pass before those cases run.

## Progress and evidence

- Repository instructions, current engine/facade and existing summary request ownership inspected. Existing instant metric periods fall back to the revenue anchor; the new ratios will not use that path.
- Implemented the two fixed engine recipes and optional summary field. Existing callers default to the unchanged payload; only the existing public normalized-summary handler opts in. C5 fingerprints and old annual serialization remain unchanged.
- The new UI disclosure reuses existing cards, percent formatting and source details. Missing/invalid new evidence becomes an unverified block; it does not erase independently verified existing snapshot values. No catalog/history metric or question template was added.
- Final new backend suite: **30 passed**, zero skips, through `-I -S -B tests/run_financial_insights.py tests/test_balance_sheet_ratios.py`.
- C5/core selection: **129 passed, 118 deselected**, including 100 existing C5 controls and the then-29 new cases. The subsequent change only humanized a new missing-input message and added an older-alternative positive case; the final 30-case suite passed afterward. No old fingerprint or assertion was edited.
- Existing reported-quarter, coverage and canonical Insights composition regressions: **81 passed** through the guarded runner.
- Existing actual-ID/ordering/serialization/API checks: **9 passed** through `run_dep01a2_increment2_offline.py`, separately from the ownership/Insights runner. This uses a synthetic in-memory SQLite fixture; no real database was connected or changed. The existing API query-count assertion remains passing.
- Final frontend validator/mounted suite: **31 passed**, zero skips. Includes exact lineage/SEC URL refusal, alternative identity/conflicts, zero cash, publications 0/7, company/period changes, stale response headers and ignored aborts. Existing utility/backend question contracts: **22 passed**; existing snapshot selection: **27 passed**, zero skips.
- Actual guarded Python summary serialization was accepted unchanged by the real TypeScript validator; an operand-value mutation and foreign-company request were rejected. This check performs no client calculation and retains its bounded synthetic JSON outside the repository.
- Scoped ESLint (`lib/finlens-api.ts lib/balance-sheet-ratios.ts components/financial-research.tsx`) and project `tsc --noEmit --incremental false`: passed. No CSS change or broad baseline-green claim.

Exact commands, receipts and stdout/stderr are retained at `D:/Projects/finlens-balance-ratios-offline-20261104/` in `check.py`, `backend-new-final`, `backend-core-final`, `backend-regressions`, `backend-sqlite`, `frontend-new-final`, `frontend-contract`, `frontend-snapshot`, `backend-export`, `canonical-acceptance`, `lint-final` and `tsc-final` records. The existing direct-child supervisor bounds each invocation to 120 seconds and 256 KiB output; Node heaps are 384–768 MiB. All direct children exited; Node preload guards report zero blocked external I/O. Existing typeless-package, TestClient and SQLite datetime deprecation warnings remain.

Initial backend development run: 24 passed and one failed before two remaining cases ran. The new mock test incorrectly required an explicit `session.rollback()`; the unchanged read-session implementation closes its uncommitted session. The test was corrected to assert the actual close/no-commit/read-only-setup contract. This is mock cleanup evidence, not proof of native PostgreSQL enforcement. The production cleanup code was not modified. No browser, service or live acquisition run occurred.

## Completion and limits

Independent final integration review is required before Git delivery. The bounded synthetic browser acceptance described below passed; real-data acceptance remains pending. This is two stored-data proportions, not full financial risk analysis, accounting comparability or external beta.

Matching accession/form/filed vintage does not establish dimensional/consolidated statement completeness; the source-admission rules remain unchanged. The two recipes scan the already loaded canonical company inventory and introduce no additional database requests. These are logical work bounds, not new native memory/deadline guarantees. The frontend limits each ratio to two selected sources/operands and at most 256 diagnostic alternatives, refusing rather than truncating oversized or malformed evidence.

Suggested commit after review and acceptance: `feat(financials): show source-linked balance-sheet proportions`. No staging, commit or push in this phase.

## Independent review repairs

The first review reproduced a malformed-display-metadata render crash (P2) and a tiny-negative-decimal validation gap (P3). The validator now checks point/input `revenue_basis` and selected/alternative source fiscal annotations before returning typed evidence, including unavailable points. Legitimate omitted/null annotations remain accepted. Decimal sign and zero checks inspect the coefficient digits rather than a floating-point conversion, so `-1e-400` cannot become an accepted negative zero; exact signed zero remains valid for a numerator/result and invalid for a denominator. This validates the contract without recalculating financial results.

Focused repair evidence: **60 validator/mounted tests passed**, zero skips, including guarded actual Python available/unavailable summary serialization, object mutations for every affected renderer field, safe unverified-block rendering, omitted/null/typed metadata controls, and tiny-negative/positive/signed-zero cases with matching operand-source lineage. Existing mounted snapshot regression selection: **27 passed**, zero skips. Scoped ESLint and project TypeScript checks passed. No backend implementation, formula, source policy, API owner or product renderer changed during this repair; the other seven candidate files and all five protected exceptions remain unchanged.

Receipts and bounded output are retained separately at `D:/Projects/finlens-balance-ratios-reviewfix-20261104/` (`frontend-new`, `frontend-snapshot`, `lint-repair`, `tsc-repair`). The Python serialization child has a 15-second/128-KiB bound and blocks private configuration, physical DB connections, network and model imports; it uses synthetic detached records only. All four outer direct children exited, and Node guards recorded zero blocked external-I/O attempts. Original candidate manifest/patch and earlier evidence remain preserved. The updated ten-file candidate is frozen for focused closure review; no browser, real-data or Git delivery action was performed.

## Browser acceptance and final integration

Independent closure accepted both validator repairs, followed by the three-file browser test patch and its narrowly bound existing runner. One isolated invocation passed both cases: desktop 1440×1000 and browser-emulated 390×844; zero failures, skips, not-run cases or retries. The outer wrapper also passed with explicit `exportError: null`, exit 0 and no OOM. This does not upgrade the historical guided-question wrapper failure. No real SEC data, database, provider, model or external tunnel was used.

All 12 screenshots were inspected. Exact ratio/formula/operands/as-of date, zero cash and mismatched-date unavailable reason were retained; page widths equal their 1440/390 viewports. Main disclosure outline pixels and 4.9228:1 contrast passed. Each exact request ledger had 15 completed GETs, 6 declared native cancellations, zero pending or violations, and no POST/retrieval/source-inventory/AI request. AAA publication 0 and held new BBB publication 1 verify that old ratios disappear while the new summary is pending. This is not a browser test of late old-company response delivery; that remains separate mounted-test evidence.

The mobile Next development N badge overlaps some comparative-filing disclaimer text and the start of the cash operand label, plus auxiliary historical-panel text. Sampled exposure checks passed, but they do not establish every edge glyph's visibility. No blanket no-occlusion or full accessibility claim is made. No screen-reader, zoom, forced-colors, native touch or real-data acceptance was performed. The six previously disclosed optional WASM dependency risks remain accepted and unverified.

Retained artifacts: `D:/Projects/finlens-annual-browser-artifacts-fbe1ea895c6d4e71964078942c503d7f/`; final result SHA-256 `05595801A0F635888522695463ED416C06DE25666B71A43771D576922CD8D080`. The separately reviewed inspection manifest at `D:/Projects/finlens-balance-ratios-native-inspection-20261104/native-delivery-manifest.json` has SHA-256 `2F98C23BD63C1B19D9523D0872ED50A9D361E49163DFE891419866D71CE9E5BB`. All 29 original exported artifact entries and 30 extracted attachments were verified. Exact container `98732a181948398b73990593a3ec702162a10444365864e3065fad04b9864118` was removed and independently confirmed absent; owned internal listeners/processes/runtime copies were closed or removed. Existing files, both consumed/historical guards and all prior receipts remain preserved.

Integrated only the reviewed spec, canonical synthetic ratio fixture and mobile project registration alongside the ten-file product candidate. Git's existing CRLF checkout conversion changes the three raw representations; their explicitly normalized LF bytes match the reviewed and browser-executed inputs exactly. Final focused checks and thirteen-file raw/Git-clean source binding are retained at `D:/Projects/finlens-balance-ratios-final-integration-20261104/`. No stage, commit or push occurs before final review.

Final integrated checkout checks passed: 60 ratio validator/mounted tests, 27 existing snapshot regressions, scoped five-file ESLint, project `tsc --noEmit --incremental false`, and exact two-case Playwright discovery with `--reporter=list` (no browser rerun). Zero skips or blocked external-I/O attempts; every bounded direct child exited. Backend bytes remain unchanged from the accepted product review; no broad backend suite was repeated or newly claimed green in this integration step.
