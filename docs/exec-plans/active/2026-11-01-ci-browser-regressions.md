# Browser regression repair

Status: active — focused synthetic acceptance passed; final delivery and CI verification remain.
Roadmap phase: research and annual comparison regression repair.

## Objective and context

Restore the alternative-observation display and annual comparison request accounting exercised by CI, while retaining strict validation of selected financial data and the existing evidence and accessibility requirements. The starting commit is `d11cfd87adb368c9b35bdec42d9e7a25f22c490e`. Existing unrelated session-financial work and the four previously protected working-tree exceptions are outside this repair and must be preserved.

CI run 41278486247, job 124765395926, reported 91 passed and four failed: the desktop and narrow alternative-observation cases and two desktop annual-period cases. These are observed CI results; this local repair has not yet been verified by a new CI run.

## Decisions and changes

- Keep selected metric, company, period, and source verification strict. Treat alternative observations as diagnostic display data: unknown or malformed alternative dates use the existing unknown-period display, and unsafe source URLs remain unlinked. Alternatives are not admitted as calculation operands.
- Record annual requests when observed, separately bind intercepted routes, and preserve terminal outcomes. Permit only an explicitly expected, bodyless same-company freshness or pinned annual-discovery cancellation paired with a distinct routed successful request in the same capture generation. Enforce endpoint, pin, response version, terminal state and exact counts; cross-request notification order is not treated as browser start order. Selected-year unbound requests and other unexpected events remain failures. Use observed request sequence boundaries for scope changes.
- Use scoped, padded inset focus outlines for metric-card provenance controls. The browser geometry calculation handles inset outlines and retains viewport, ancestor clipping and strict physical-pixel checks. The browser tests still use native keyboard navigation.

## Validation and evidence

- Focused interaction cases: 25 passed. Annual lifecycle offline cases: 10 passed. D10 focus geometry and static presentation cases: 12 passed. Frontend lint and TypeScript checks passed. These are focused checks, not a full-suite claim.
- An earlier local six-case attempt stopped at the desktop D10 focus check: its outward ring exceeded the viewport by approximately 0.859 CSS pixels. Its evidence remains at `D:\Projects\finlens-annual-browser-artifacts-789e1c75d017424e80894f03c6827a99`; it is not retroactively a pass.
- The reviewed successor ran once using `D:\Projects\finlens-ci-focus-gate-7c4f620da0c149c3aeb4670f8f254d77\launch-once.ps1`, manifest SHA-256 `D069FB38F72F579D06B655AD4C8FADA79650D192F65085A0548FCE264BF1B46B`. Synthetic desktop cases passed 5/5 and the narrow case passed 1/1, without skipped cases or retries. They cover both D10 viewports, both previously failing annual cases, and desktop/narrow snapshot-gap controls.
- The recorded annual ledger includes a pre-interception cancelled freshness request and a distinct subsequent routed 200 response. Its raw attachment uses a conservative default unbound classification when no expected-cancellation list is supplied; the test's explicit expected ledger permits only the checked cancellation and verifies the remaining outcomes.
- All 29 indexed exports passed size and SHA-256 verification. D10 focus evidence includes seven screenshots and seven geometry records at each width, including the four alternative links and return to the disclosure. Screenshots show the focused controls and inset rings; a floating development indicator is visible elsewhere in some images and limits claims about unrelated content beneath it.
- Artifact root: `D:\Projects\finlens-annual-browser-artifacts-2a824c8a084442a0b4edf1baeb438f07`. The receipt reports owned container absence, host CLI reaping, artifact and source preservation, with no errors. Six optional WASM dependencies remain unverified; the run accepted that existing diagnostic risk. This is local synthetic evidence, not live-data or full CI acceptance.
- Subsequent CI run 41280573810 on `9e6a8b4daa373d3ec4f2b993ee39c7e5b8e5c971` reported 93 passes and two failures. Its annual trace contained an unbound, bodyless annual-discovery cancellation at pin 1 and a distinct routed 200 completion at version 1. Its History trace showed cross-request notification ordering different from browser start ordering; its cancellation terminal events were before the recorded baseline. Neither failure is retroactively a pass.
- The follow-up test-only correction partitions annual pairing by scope generation, accepts either legal cross-request notification order while retaining individual request event order, and waits for observed History startup requests to settle before the interaction baseline. History now attaches a bounded request audit on success and failure. Offline checks passed: 13 annual lifecycle tests, 25 History accounting checks, lint and TypeScript. The annual permutation test exercises ten legal interleavings across freshness and annual pins 0/1 with routed and pre-route cancellations.
- The reviewed successor ran once using `D:\Projects\finlens-ci-order-gate-439cadb108b1777fc4563c2fd9efa2c7\launch-once.ps1`, manifest SHA-256 `2B2DF382080BD47B1F8B852D17DC95A3896B5C06DA28D536E8B2DA44E063F4A5`. Seven desktop and one mobile-project synthetic cases passed, without retries or skips. The cases include both previously failing tests, both D10 viewports, both History viewports, an additional annual case and desktop/mobile snapshot controls. Both annual ledgers had no unbound requests in this run, so the specific CI pre-interception race did not recur. The two History audits contained the expected cancellations and completed peers before their baseline, with no violations; 15 focus geometry records passed. All 29 indexed exports passed size and SHA-256 verification. The receipt confirms owned container absence, host CLI reaping, artifact and source preservation; six optional WASM dependencies remain unverified. Artifact root: `D:\Projects\finlens-annual-browser-artifacts-6d38a021e7ba40c3bf4b31efa74a586c`. CI for a resulting commit remains unverified.

## Constraints, progress and next action

No live provider, production database, network access, dependency download, Git write, or modification of the paused session-financial work is part of this repair. Existing failed artifacts are retained.

- [x] Diagnose the two distinct CI failures and apply focused corrections.
- [x] Complete independent focused review and bounded local browser acceptance.
- [ ] Verify the final repair-only diff and deliver it separately from unrelated work.
- [ ] After authorized delivery, observe CI for the resulting exact commit; investigate any failure without weakening the assertions.

## Final outcome

Pending final delivery and CI. Suggested commit: `fix(research): preserve provenance and browser request accounting`.
