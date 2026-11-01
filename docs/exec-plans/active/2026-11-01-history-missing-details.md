# History missing-detail disclosure

Status: active — synthetic acceptance complete; manual Git handoff pending.
Roadmap phase: Research Mode evidence and accessibility.

## Objective and context

When a verified History response has observations but no available values, retain each observation's period, reason and provenance rather than hiding the rows. An empty history stays empty; malformed or unverified responses fail closed. The chart remains absent without available values. Source selection, calculation and publication pins remain server-owned.

Baseline: main `a5f09dbd61fdcd362d8b7da153654681489eb41b`. Preserve the pre-existing modified `frontend/next-env.d.ts`, two untracked backend reports and the separate blocked annual Markdown export plan. No provider, database, credentials, dependency installation or Git publication is authorized by this plan.

## Decisions and progress

- History rows and provenance disclosures are retained when no values are available. History-only inset focus outlines preserve native keyboard navigation and the 44px minimum targets.
- Two UX-01B test cases now account for the specific annual discovery request and StrictMode replay without dropping pin, cancellation, recovery or stale-response checks; this changes test accounting, not product policy.
- The synthetic browser spec used for the earlier accepted run was retained in `frontend/e2e/history-missing-detail.spec.ts`, then extended with source-column width and whole-word checks. Those assertions passed in the corrected run below. Its helper checks are retained under `frontend/tests/`, with local package and spec resolution replacing external scratch paths.
- [x] Focused synthetic browser execution; [x] focused offline checks, lint and TypeScript; [x] independent review of the supplied tracked diff, browser spec, offline checks and focused reveal helper; [x] narrow-column readability correction and synthetic browser verification.

## Validation actually performed

From `frontend`: `node --test --test-name-pattern='^(History missing-detail|UX-01B )' tests/research-interactions.test.mjs` passed 40/40; `node --test tests/history-focus.test.mjs tests/history-request-accounting.test.mjs tests/ux01a-presentation.test.mjs` passed eight Node test entries, including 12 geometry and 22 request-accounting checks; `npm run lint` and `node_modules\\.bin\\tsc.cmd --noEmit --incremental false` passed. Playwright list discovered two cases without running a browser.

Synthetic local Chromium acceptance, artifact nonce `062fdc3bd3454487833fc58b0519c252`, passed desktop 1440x1000 and narrow 390x844, one case each, with 7 and 8 focus screenshot/geometry pairs respectively. All 29 indexed exports matched their recorded hashes. The receipt records owned cleanup, absent container, closed test ports and reaped host CLIs. Six optional WASM-support dependencies remain unverified. This is not live SEC, real-device touch or full accessibility acceptance.

Prior attempts and failed receipts remain preserved, including the temporary-file EACCES, focus clipping, aborted-request accounting, and preflight worktree-binding failures. The successful run does not prove the original Linux EACCES cause. The retained native focus tolerance is strictly less than 0.5 physical pixels with DPR and clipping checks.

## Open findings and completion

At 390px the source column was about 80px wide and long labels broke within words. The History-only third-column minimum is now 220px and summaries use normal word wrapping. A floating circular N-mark partially obscured the region outline in a screenshot. The development runtime includes Next.js developer tooling, but the retained evidence does not establish the marker's identity or production presence; do not claim an unobscured ring at that point. The remaining screenshots and measured geometry passed their recorded checks.

The subsequent readability run `ddef6cec01da4193a486dc265bc67a82` passed desktop but failed narrow when the focused source summary extended 101px past the horizontal scroll region. Owned cleanup was recorded as verified. History now reveals focused provenance summaries and links by moving only that region horizontally to the nearest needed edge. A mounted regression covers focus identity, both directions, already-visible and oversized targets, the region itself, unrelated descendants and no additional requests; the expanded History/UX-01B selection passed 41/41.

The corrected synthetic run `8186f848322e4adeb5063ce390f20aae` passed one desktop and one 390px Chromium case with no retry or skip. The source-column width and whole-word checks passed; all 15 focus geometry records met their clipping and DPR gates, and the keyboard path and request-accounting assertions passed. All 29 indexed exports matched; the receipt reports verified owned cleanup, closed ports and no remaining owned container. Visual inspection confirmed readable source summaries and links. The circular N-mark still obscured a small part of the narrow table-region ring; its identity and production presence remain unverified. This does not establish that every focus indicator was unobscured or that real-device touch was tested.

Independent review was limited to supplied source and snippets; it did not certify every external artifact. Manual Git review remains. Suggested commit: `Show unavailable history observations and sources`.
