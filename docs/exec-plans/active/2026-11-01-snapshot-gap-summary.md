# Snapshot gap summary

Status: active — bounded implementation, focused review and synthetic browser acceptance complete; manual delivery pending.

## Objective and scope

Expose unavailable, not-applicable and unverified metrics in the current single-company financial snapshot, using the existing response and metric catalog only. This is a bounded D9 increment, not complete coverage planning or evidence acquisition. Baseline HEAD `91c1e69af2f542d3e2dada34f6eaa79e3ee0e3c5`; preserve `frontend/next-env.d.ts`, the two existing backend reports and the separate blocked Markdown export plan.

## Constraints and decisions

No additional API calls, source jobs, provider access, database changes, dependencies or Git writes. Bind display to current company, CIK, selected period, publication version (including zero) and request generation. Missing or malformed items remain unverified; no absent-period or complete-source inference. Expose server reasons without inventing interpretations. Preserve existing cards, independently owned History and source panels.

## Progress and validation

- [x] Inspect existing state ownership, contracts and D9 boundaries.
- [x] Implement bounded classification and accessible summary using the current response and no new requests.
- [x] Verify mixed/empty/malformed/identity cases, version zero, stale requests and scope changes; confirm disclosure does not add requests.
- [x] Run focused tests, lint and TypeScript; obtain independent review and scoped synthetic browser acceptance.

From `frontend`, `node --test --test-name-pattern='Snapshot gaps|mounted cash-flow alternatives|FD-01|snapshot|company switch' tests/research-interactions.test.mjs` passed 56/56, including 15 new gap cases; `npm run lint` and `node_modules\.bin\tsc.cmd --noEmit --incremental false` passed. An earlier selection had three cash-flow failures because its synthetic unavailable points included a provenance object with a null source value, contrary to the source schema. The fixture was corrected to use no provenance for those missing synthetic points; their existing behavioral assertions remain. The selection then passed.

Independent review found that an alternative-period cash-flow hint could claim availability for a structurally unverified source. The hint now uses the same metric validation as the destination card. A regression rejects wrong-company and absent provenance while preserving a valid hint and the existing cache behavior. Focused independent re-review closed this finding; the browser spec received separate focused review.

The current summary reports structural checks only, not independent source authorization or complete SEC coverage. Available values require an expected metric/unit/period, valid source shapes and company, and a trusted SEC URL; missing or malformed items are unverified. No period or source is invented. On scope change the summary is hidden until the current company, period, version and generation match.

One authorized isolated synthetic browser run passed the new case on desktop 1440×1000 and mobile-width 390×844 (one case each; no retries). It checked six mixed gaps including a missing item, publication version zero, native keyboard disclosure, no additional requests during its open/close interval, and company/period switching with held responses. Focus geometry reported DPR 1, a visible 3px outline, a 44px target and viewport containment at both widths. The owned runtime and container cleanup and all preservation gates passed. All 29 indexed artifacts passed independent byte-count and SHA-256 checks; the two screenshots and one geometry attachment in each phase were extracted and inspected. The narrow open screenshot has a floating circular indicator of unconfirmed origin partially covering text near the bottom, and later list content falls below the viewport; it does not prove every expanded line unobscured or real-device accessibility. Six optional WASM dependencies remained unverified, as accepted for this run. Evidence: `D:\Projects\finlens-annual-browser-artifacts-fc358076b1da447383c748db74881189`; attachment copies: `D:\Projects\finlens-snapshot-gap-review-fc358076b1da447383c748db74881189`. This is synthetic browser evidence, not live SEC or complete D9 acceptance.

## Completion

Prepare the scoped manual Git handoff. Suggested commit: `Show current snapshot coverage gaps`. This plan does not authorize live acquisition or deployment.
