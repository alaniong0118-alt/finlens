# Answer Presentation & Evidence Highlighting

Status: completed
Roadmap phase: scoped Research Mode presentation milestone

## Objective

Answer first, highlight the proof, details on demand. Compact direct answers and query-focused, safely highlighted evidence previews; two ranked cards initially, full original passages and remaining results on demand.

## Current architecture and context

Follow [instructions](../../../AGENTS.md), [plan standard](../../../.agent/PLANS.md), [product](../../product-spec.md) and [architecture](../../architecture.md). Starting Git status is clean. Existing FilingSearch independently settles direct answer/context with scope guards; EvidenceResults renders all cards with first-650-character previews. Financial truth and recognition remain backend-owned. Existing mounted React/Node/jsdom tests are reusable.

## Constraints

Frontend presentation only. No SEC/OpenAI calls, data writes, financial/recognition/retrieval/policy changes, dependencies, commit or push. Preserve warnings, provenance, ranking, original stored text and async boundaries.

## Non-goals

Semantic summarization, new retrieval/ranking, Partial Evidence, company-wide research, later milestones.

## Implementation stages

1. Audit real UI/contracts and capture read-only fingerprints.
2. Add bounded excerpt/highlight utilities and compact disclosures.
3. Add helper and real mounted presentation regressions; run tests/lint/build.
4. Browser acceptance, responsive/themes/keyboard; preservation/self-review/docs.

## Decisions

Presentation chooses a window within each already-ranked passage, never reorders sources. Numeric highlights require exact decimal equality and explicit unit scale, otherwise keyword fallback. Highlights mean text matches, not verified claim support.

## Discovered issues

Flattened AAPL chunk_0006 contains the revenue row but omits its millions header. Chunk_0005 overlaps the exact row with an explicit Note 2 declaration: safe exact-row overlap transfer supplies display scaling without inventing a unit. Method previews initially favored generic accounting headings; weighted local phrase matching now prefers the actual disaggregated-sales statement. A duplicate React sibling key introduced during presentation work was corrected before final tests. No backend/data bug or semantic change was needed.

## Progress

- [x] Instructions, milestone, relevant current components/tests read.
- [x] Implementation and regressions: pure frontend excerpts, React marks, two cards/disclosures, preserved warnings.
- [x] Validation and browser acceptance: 6 helper/19 mounted/45 total tests, lint/build; 4 widths/themes, actual amount/method/topics/unavailable/keyboard/switching.
- [x] Documentation and final outcome: product/architecture/roadmap/report, preservation, scope review and closure checks.

## Test and validation strategy

Helper edge cases (units/signs/unsafe text/unknown scaling), mounted amount/method/unavailable/show-more/scope regressions, complete frontend tests, lint/build, actual local product at four widths and themes. Backend unchanged: no backend rerun. Compare read-only whole-row fingerprints before/after. Run git diff --check.

## Completion criteria

Concise direct answer, relevant excerpts and semantic marks, bounded default cards, working expansion/collapse, untouched source/rank/financial semantics, retained warnings and independent async errors, tests/lint/build/browser pass, data unchanged, accurate docs.

## Final outcome

2026-10-08 focused review corrections: fixed two P2 numeric-mark defects by retaining full signed/currency notation before exact comparison. Balanced accounting negatives and single leading/post-dollar negatives are supported; opposite signs, foreign-dollar prefixes and ambiguous notation cannot validate an amount. Added permanent signed/currency/EPS/fallback regressions, retaining original source text and phrase highlighting. Focused helper/mounted tests: 27 passed; final full frontend tests: 47 passed; lint, no-emit TypeScript and `git diff --check` passed. No backend/dependency/data change or SEC/OpenAI request. Existing generated next-env churn was not touched. See the dated section in the [acceptance record](../../answer-presentation-verification.md) for details. This small correction does not reopen the completed architecture or begin another milestone.

Completed within frontend presentation scope. [Acceptance record](../../answer-presentation-verification.md) records exact commands, observed cases, screenshots, count/hash preservation and limitations.

Actual validation: frontend focused tests 25 passed, full npm test 45 passed, lint passed. Final npm run build/type checking passed in identical disposable source copy at D:/Projects/finlens-presentation-validation-20261007 with existing dependencies; next-env hash unchanged. Backend unchanged, so no backend suite rerun. Real 3000/8000 browser verified AAPL $109.42B with $ 109,417 marked, reporting-method evidence only, revenue growth/gross margin/supply constraints, COST unavailable reason, scopes, native keyboard disclosures/show-more/collapse, Light/Dark/System, 1440/1280/768/390 with no overflow. Mobile evidence height reduced from 1887 to 734px by the default two-card view. Controlled mounted AI/evidence failures retain independent results.

Read-only before/after fingerprints match: 35 companies / 58,881 facts / 3,175 chunks and embeddings. No financial/recognition/retrieval/backend/dependency/data change; no SEC/OpenAI call, commit/push or future milestone. Git status contains only scoped frontend/docs/tests/screenshots. Internal references and git diff --check passed at closure (ordinary CRLF notices only).

Limitations: excerpt matching is not summarization/entailment; ambiguous units/rounded values receive no exact-value mark, underlying source/ranking/coverage limits remain. Manual representative accessibility checks are not an exhaustive audit. Suggested commit: `Improve Research Answer presentation and highlight SEC evidence`.
