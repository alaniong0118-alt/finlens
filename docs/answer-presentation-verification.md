# Answer Presentation & Evidence Highlighting — verification

Date: 2026-10-07. Status: completed within frontend presentation scope.

## Scope and implementation

“Answer first, highlight the proof, details on demand.” See [product contract](product-spec.md#answer-presentation-and-evidence-highlighting), [architecture](architecture.md#evidence-presentation), and [completed ExecPlan](exec-plans/completed/2026-10-07-answer-presentation-evidence-highlighting.md).

Changed application files: `frontend/components/filing-research.tsx`, `research-answer.tsx`, `frontend/app/globals.css` and new `frontend/lib/evidence-presentation.ts`. Tests: new `frontend/tests/evidence-presentation.test.mjs` and mounted regressions in `research-interactions.test.mjs`. Documentation: roadmap, product spec, architecture, this record, completed plan and two actual screenshots.

The direct card retains the server's headline, one answer sentence, essential dates/form, revenue basis, unavailable reason and EPS warning, with exact provenance collapsed. A redundant company/source-scope footer was removed; the supporting-evidence boundary still explicitly warns that passages may describe another period/accession.

Excerpt selection scores at most 200 phrase/value anchors within each supplied passage. Windows retain exact original wording and offsets, up to 280 characters, normally 200 around a matched value. Method questions prefer recognition, disaggregation, accounting or presentation language. There is no summary, frontend truth selector, source re-ranking or new Evidence Policy.

React text segments render semantic `mark` elements; terms use word boundaries, longer phrases and stop-word/repetition suppression. Numeric matching compares exact decimal strings, not rounded display amounts. USD scale requires an explicit suffix or preceding nearby table declaration with note/page/per-share boundaries. A missing overlap header can be recovered only through an identical row fragment with consistent declarations across supplied passages. Percent and explicitly labelled EPS retain units. Unknown units, conflicting scales, rounded-only values and unavailable results receive no numeric-match marks. Source text/citations/ranking remain intact.

Two ranked cards are mounted initially. Show more/less reveals the rest in backend order with no requests. Native full-text/retrieval/provenance disclosures remain usable by keyboard. Scope keys reset expansion; existing abort/version/ticker/question/accession guards remain unchanged. Evidence and AI failures retain valid direct answers; AI failure retains evidence.

## Automated validation actually run

From `frontend/`:

- `node --test tests/evidence-presentation.test.mjs` — 6 passed.
- `node --test tests/research-interactions.test.mjs` — 19 passed (five new presentation regressions plus fourteen retained interactions).
- Combined focused helper/mounted command — 25 passed.
- Final `npm test` — 45 passed, zero failures/skips.
- Final `npm run lint` — passed.

The new mounted cases exercise real Home/ResearchAnswer/FilingResearch state: numeric proof and ranked show-more/full-text controls; method fallback; literal unsafe text/keyword fallback; unavailable no-numeric-validation; company/query invalidation and expansion reset. Existing delayed-response and evidence/provider-failure regressions passed with the changed presentation. No snapshots or new dependencies.

`npm run build` with `FINLENS_API_BASE_URL=http://127.0.0.1:8000` passed in identical disposable source copy `D:/Projects/finlens-presentation-validation-20261007`, using the repository's node_modules through a junction. Type checking/static generation passed; final page 113 kB, first-load JS 215 kB. Six changed frontend source/test files were hash-equal to the validated copy. The existing `.next-prod` build convention was retained. This protects the repository's generated `next-env.d.ts`; its SHA256 remained `B6768A2C7FB9A45BEA5D463A4993FDD8590BD50E5FCAB0C6F84921EE981ACC82`.

Backend code was unchanged, so backend regressions were not rerun. Existing Node module-type warnings remain; no unrelated package/config change was made.

## Actual browser and local HTTP acceptance

CUA used the real app at 3000, backend 8000. AAPL indexed accession was discovered from stored `/sources`, not guessed: `0000320193-26-000020`.

| Case | Observed outcome |
|---|---|
| How much revenue did Apple report? | $109.42B; quarter ended June 27, 2026; 10-Q filed July 31. First preview starts at Total net sales; `$ 109,417` marked through the overlapping Note 2 millions declaration. Two initial cards; more gives five in order, less returns two. |
| Exact provenance/full passage | Keyboard Enter opens provenance (109417000000.0000 USD, concept, dates, accession/official URL), and full original 2,500-character first passage. Enter closes them. |
| How does Apple report revenue? | No direct answer. First excerpt is Note 2's disaggregated net-sales/previously deferred presentation statement; relevant phrases marked. It does not invent a recognition policy absent from retrieved text. |
| revenue growth | 16.36% direct result; source net-sales/year-over-year phrases marked. Rounded source 16% is not claimed to equal the exact ratio. |
| gross margin | Backend Unavailable retained; query phrase highlights, no numeric-validation mark. |
| supply constraints | Evidence-only result; concise actual component supply-demand sentence and term highlighting. |
| COST latest quarterly revenue growth | Unavailable; incompatible revenue bases reason retained; no numeric marks. |
| Company/question changes | Old evidence/marks disappear. Mounted deferred fixtures additionally prove late responses cannot restore old state. |
| AI/evidence failures | Permanent mounted controlled fixtures retain direct/provenance/evidence. No live AI call performed. |

Light at 1440 and 390, Dark at 1280 and 390, System at 768 were visually inspected. System resolved to the actual dark OS preference. Semantic text/underline/value outline and focus remain readable. Document scroll widths at 1440/1280/768/390 were 1425/1265/753/375: no page horizontal overflow, including expanded full text at 390. At 390 the default evidence region was 733.72px high versus 1887.31px with all five previews, saving about 1,154px (61%). Native keyboard disclosures, show-more/collapse and official link focus passed. Temporary viewport overrides were reset.

Actual [desktop screenshot](screenshots/answer-evidence-desktop.jpg) and [mobile screenshot](screenshots/answer-evidence-mobile.jpg) show the amount result. No fake product data or stock graphics were used.

## Preservation and request boundary

Before and after: read-only SQL transaction using existing `scripts.verify_financial_metrics.fingerprint`:

| Table/data | Count | Unchanged SHA256 |
|---|---:|---|
| companies | 35 | ace9bd807d59983386906c3e3612bc2b05c262344731ba4421bbf2c6586084f0 |
| financial_facts | 58,881 | ff6dbccc908b0748148f8a01712e40fd469a6ef362b9b3990d6e0ce881f70655 |
| filing_chunks (whole rows include vectors) | 3,175 | ca6ce451d4060723b3c3dcc73c58a623a5dfac37a8246b435f69d8bb4bdf3c12 |
| non-null embeddings | 3,175 | Included in chunk fingerprint |

No backend, database, financial selection, deterministic recognition, retrieval, dependency or schema change. No SEC/OpenAI request, ingestion/embedding generation, commit/push or later milestone. One existing direct POST and one context GET per submitted indexed-filing question remain independent. Show-more/full-text/highlights use no HTTP requests, asserted in mounted tests. A local 1,000-iteration benchmark on five real 2,500-character passages took about 0.53ms per set before the final additional duplicate-declaration guard; this is a local sample, not a production latency guarantee.

## Final review and limitations

### 2026-10-08 numeric-highlighting review fixes

Two P2 defects were reproduced: matching could start at an interior `$`, discarding a leading minus, accounting parentheses around a scaled amount, or an explicit foreign-dollar prefix. The display helper now consumes complete notation before exact decimal comparison. A single minus (ASCII or Unicode) or balanced accounting parentheses supplies the negative sign; conflicting signs, malformed wrappers and unknown currency notation receive no numeric mark. Attached alphabetic dollar prefixes, including `C$` and `A$`, are rejected; detached foreign codes/symbols also fall back conservatively. Query/phrase marks and exact original source text remain available independently.

Permanent tests cover positive/negative USD symmetry, both accounting scale placements, foreign prefixes, malformed/conflicting notation, EPS, unavailable answers and phrase fallback. Existing AAPL exact scaled matching, rounded/ambiguous fallback and mounted presentation/state tests remain passing. New regressions failed against the prior helper before the fix.

Actual validation in `frontend/`: `node --test tests/evidence-presentation.test.mjs tests/research-interactions.test.mjs` passed 27 tests (8 helper, 19 mounted); after additional conservative-prefix cases, `npm test` passed all 47 tests, `npm run lint` passed, and `node node_modules/typescript/bin/tsc --noEmit --incremental false` passed. Node emitted the existing module-type warning; dependencies were not changed. `git diff --check` passed. No backend tests, build or browser acceptance were repeated for this bounded helper fix. No backend/database/external-service access or mutation occurred. The pre-existing generated `frontend/next-env.d.ts` diff was preserved with unchanged SHA-256 `F4E8976C19FC926644D72610BF1058BD6BF52ADD97E46A02BC0B912A751625C0`.

### Original milestone closure (2026-10-07)

All required presentation acceptance gates passed. All 48 internal documentation targets/anchors checked across changed documents resolve; `git diff --check` passed (ordinary LF/CRLF notices only). At that closure, work was uncommitted: seven modified and six untracked scoped files, including two screenshots; no unrelated generated/backend changes. Suggested commit: `Improve Research Answer presentation and highlight SEC evidence`.

Deterministic windows can truncate sentences/tables and cannot recover missing source content, infer unsupported units, assign columns to periods or establish factual entailment. Unknown/ambiguous formats deliberately fall back to phrase marks. Evidence quality/rank remains the existing retrieval's responsibility. Manual representative accessibility/browser checks are not a formal exhaustive audit. Live AI acceptance remains separately blocked by the previously recorded credit limitations; no new AI claim is made here.
