# Item 8 — FinLens Research Mode

Status: completed
Roadmap phase: Item 8; Research Mode frontend, optional AI

## Objective

Expose stored financial snapshots, period-specific histories/charts, provenance and filing evidence without an OpenAI key. Retain optional grounded answers. Verify representative real data, themes and responsive interactions.

## Current architecture and context

Follow [instructions](../../../AGENTS.md), [plan rules](../../../.agent/PLANS.md), [product spec](../../product-spec.md), [metrics](../../financial-metrics.md) and [architecture](../../architecture.md). Item 7 is committed; starting worktree contains only a pre-existing generated `frontend/next-env.d.ts` change, which must be preserved. Current page is answer-first; browser audit at port 3000 confirms styled navy/teal UI and 35 Ready companies. Existing summary/history/context APIs are read-only. Recharts is already installed; no new dependency is needed.

## Constraints

No data mutation, SEC acquisition, OpenAI calls, indexing, financial-semantic/ranking/threshold changes, commit or push. Use real API values only. Preserve original company and filing behavior, safety and lineage. Do not begin comparisons or multi-filing work.

## Non-goals

Authentication, billing, market prices, additional data coverage, AI acceptance, architecture rewrite.

## Implementation stages

1. Audit real UI/API contracts and capture immutable data fingerprints.
2. Add safe configuration-only capability metadata; typed frontend contracts and cancellation.
3. Build company research/snapshot/history/provenance and evidence-first workspace, optional AI, theme controls.
4. Tests, lint/build, real browser checks for AAPL/JPM/JNJ/XOM/COST, 1440/1280/768/390 widths and Light/Dark/System; fix integration defects.
5. Update existing documentation, preservation/reference checks, self-review; complete this plan only after acceptance.

## Decisions

- Separate company metrics (selected period) from the selected narrative filing; do not imply they describe the same accession/date.
- Reuse GET context and existing SOURCE boundaries for excerpts; no second retrieval implementation or threshold.
- Capability means configured, not provider health. No external probe. AI is an explicit action and failure retains evidence.
- Use existing Recharts with discrete bars/text table; period types stay separate and missing observations remain gaps.

## Discovered issues

The original UI encouraged key configuration and had no metrics/theme/evidence-only result; resolved in this milestone. During implementation, a missing helper brace produced a dev compilation error; it was corrected before final tests/build and browser acceptance. The pre-existing privileged port 3000 process could not be restarted, so production acceptance used port 3001 with a separate no-key backend at 8020. Shared dev output was avoided through the existing production output directory. Browser inspection found narrow mobile source disclosures; expanded metric cards now span the grid width, and long evidence has a preview/full disclosure. No backend financial or retrieval integration defect was found.

## Progress

- [x] Repository/instruction/API audit and current browser visual inspection.
- [x] 2026-10-05: Read-only baseline fingerprints, configuration-only capability endpoint and typed/cancellable clients.
- [x] 2026-10-05: Company research, real charts/provenance, evidence/optional AI, themes and async guards.
- [x] 2026-10-05: Automated checks and real browser acceptance completed; provider failure used a controlled local fixture, never OpenAI.
- [x] 2026-10-05: Existing docs/roadmap updated, final data preservation and scope self-review completed. References and diff checks recorded in the acceptance report.

## Test and validation strategy

Focused backend capability/no-provider tests only. Frontend API/format/period/evidence tests, npm test/lint/build. Browser checks real data and interactions, empty evidence, optional AI availability and request patterns. Read-only full-row database fingerprints before/after; no healthy-data test writes. Check internal documentation references and git diff --check. Record exact results below.

## Completion criteria

All no-key research paths work; correct source/scope/period labels and inspectable provenance; real charts with text equivalents; stale requests cannot cross company/filing boundaries; AI cannot erase evidence; themes/mobile/keyboard usable; tests/lint/build/browser pass; data unchanged and docs current.

## Final outcome

Item 8 is complete within the requested single-company research scope. See the [machine-readable acceptance record](../../../backend/reports/research_mode_verification.json) for real company values, HTTP results, browser checks, request boundaries and before/after hashes.

Actual validation (repository root unless stated):

- Frontend directory: `npm test` — 19 passed; `npm run lint` — passed; `npm run build` — passed, including type checking. Page 109 kB / first load 212 kB; existing Recharts reused, no dependency change.
- Backend directory: `.venv/Scripts/python.exe -m pytest tests/test_capabilities.py -q -p no:cacheprovider` — 4 passed; `python -B -c "from app.main import app; print(len(app.routes))"` — 20 routes, import passed. No full unrelated regression or sync rerun.
- Browser: AAPL/JPM/JNJ/XOM/COST snapshots, histories and five evidence passages per representative search; AAPL scoped margin unavailable, JPM net-interest basis, JNJ as-filed EPS warning/annual and instant controls, XOM two quarter points/empty annual, COST incompatible-basis YoY unavailable. AAPL clinical-trial negative showed neutral insufficient evidence and disabled AI.
- Themes: Light/Dark/System (actual OS Dark), persisted Dark after reload, keyboard select with 3px focus. Viewports 1440/1280/768/390 had document scroll width equal to document client width; mobile chart/source disclosures fit. Source and full-passage disclosures worked via Enter. Rapid JPM/JNJ/COST switching cleared old evidence.
- Controlled local provider-failure fixture: configuration true, one explicit answer POST returned 502, OpenAI client forbidden, external provider calls zero. Real evidence text unchanged and neutral fallback visible. Fixture discarded; final backend configuration false restored. No fake answer or provider success claim.
- Real HTTP: health, capability, all 35 Ready companies, summaries/revenue histories/source metadata for five representatives passed. Initial page makes five bounded requests (catalog, capability, summary, selected history, selected-company sources); disclosures do not fetch and evidence/AI are explicit actions.
- Read-only PostgreSQL transaction: 35 companies / 58,881 facts / 3,175 chunks / 3,175 vectors; full-row SHA256 fingerprints including embeddings unchanged from pre-work and Item 7. No data/schema mutation, SEC acquisition or OpenAI call.
- Existing README, product spec, architecture, metric-consumer note and roadmap updated. Actual screenshots are in [screenshots](../../screenshots/). Git/link checks are recorded in the acceptance record.

Known boundaries: no company comparisons, deeper indexing or adjusted-EPS guarantees; existing financial scope/date gaps remain honest. Live AI success/claim audit remains pending historical intentional-credit acceptance. Keyboard/contrast/layout checks are manual, not a comprehensive assistive-technology audit. Original user `frontend/next-env.d.ts` change is retained separately from the milestone. No commit/push.

Suggested commit: `Add evidence-first Research Mode with financial trends and themes`.

## Final-review test coverage follow-up — 2026-10-07

The independent review passed Item 8 and identified one P2 automation gap: helper/API tests did not mount the actual components. Added seven real ReactDOM interaction regressions under the existing Node test runner, using pinned test-only jsdom for the DOM. Only Next routing links and browser layout/media APIs are adapted; the real page, component effects, typed APIs and state guards execute. Synthetic HTTP fixtures are explicitly test-only, with one filing per issuer and no external/backend/database calls.

Coverage: delayed company summary/history/sources; pending evidence across a company switch; failed explicit AI preserving evidence; no-key success; in-place snapshot-period/history-metric races; query-edit invalidation. Deferred fetch responses deliberately ignore cancellation so late delivery is exercised. Existing isolated test names now describe their narrower scope accurately.

Actual checks: seven mounted tests and the complete 26-test frontend suite passed; lint passed; production build passed in an identical disposable frontend copy, preserving the repository's unrelated generated `next-env.d.ts`. Removing financial cleanup, financial response guards, the company remount key or evidence request guards in that disposable copy each caused the relevant regressions to fail. Mutations were restored before the final build. No product bug was discovered and no application/backend/data changes were made. No SEC/OpenAI calls, commit or push.
