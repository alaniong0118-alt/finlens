# ML-FAIL-01: historical aggregate failure analysis

Status: active; implementation/offline verification complete, independent review pending.
Roadmap phase: bounded private academic ML demonstration; no next milestone.

## Objective

Extend the existing ML-PB-02 historical evaluation disclosure with accessible,
static class metrics, confusion matrix, one-vs-rest error counts, reproducibility
identity and honest limitations. No new evaluation or individual-error explanation.

## Current architecture and context

2026-10-21: main, HEAD `3490036d84b022bb4ef76272fd8690aa6e9ec736`, empty
index. The only existing worktree exceptions are frontend/next-env.d.ts and the
two original untracked backend AAPL reports. All 328 inventoried fingerprints
match the prior post-push baseline, including private ignored/untracked
backend/.env (fingerprint-only; contents never read or displayed).

The standalone demo already displays historical headline metrics. The evaluator,
server, worker, prediction UI and lifecycle remain unchanged. Source:
[evaluation record](../../news-sentiment-baseline.md), frozen ML-PB-01 commit
`0a042f91232182fa13503066ece8c21f494a2158`. Before writing, the complete recorded
evaluation block matched that immutable commit exactly; SHA256 of its LF text:
`b1d7425ced08a3f7724f559717f35dcfc6de597e14806f6adbfadd4b6ba09bd1`.
No aggregate tables already existed. The original aggregate JSON is not a
repository artifact; this presentation uses the committed aggregate record.

## Constraints and non-goals

Exactly three allowed paths:

- backend/scripts/news_sentiment_demo.html
- backend/tests/test_news_sentiment_demo.py
- docs/exec-plans/active/2026-10-21-ml-fail-01-aggregate-analysis.md

No corpus access, training, model loading, inference, acquisition, database,
services, browser acceptance, dependencies, server/routes/worker edits, extra
requests, JavaScript behavior, Git writes or deployment. No corpus passages,
row-linked predictions, vocabulary, weights, confidence or export controls.
Private nonprofit academic limits and existing attribution remain. DEP-01A3
remains BLOCKED. No reconstruction of missing evaluation artifacts.

## Implementation stages

1. Verify baseline, preservation and immutable aggregate evidence (complete).
2. Extend static disclosure and scoped styles; preserve script bytes.
3. Add aggregate/source/semantic tests and extend existing mocked DOM coverage.
4. Run only focused offline tests, inspect diff and compare all file fingerprints.
5. Record results and stop for independent Astra High implementation review.

## Decisions

- Historical reproduction date is 2026-10-19; evaluation identifier is
  news-sentiment-tfidf-svc-v1. Results never describe the current submitted input
  or prove this launch reproduced held-out performance.
- Matrix rows are actual and columns predicted, ordered negative/neutral/positive:
  [[53,17,14],[6,400,23],[8,31,139]]. Supports 84/429/178; total 691;
  592 correct and 99 incorrect. Class FP/FN are 14/31, 48/29, 37/39.
- FP/FN are one-vs-rest counts. Each misclassification contributes once to each
  sum; adding the sums does not create 198 distinct errors.
- Derive metric checks from the immutable matrix; compare six-decimal class
  scores and macro-F1, four-decimal percentage accuracy and majority baseline.
- Static analysis remains available independently of worker state. Native
  disclosure and labelled scroll regions preserve bounded mobile table overflow.
- No causal explanation of individual errors or synthetic explanatory examples.

## Discovered issues

None at pre-write verification. Existing plans contain historical acceptance
checklists; this task does not reopen completed ML-PB evaluation/browser gates.

## Progress

- [x] Pre-write Git, fingerprint, immutable source and absence checks.
- [x] Static presentation and focused tests.
- [x] Focused offline execution and exact scope/preservation reconciliation.
- [ ] Independent Astra High implementation review (separate coordinator step).

## Test and validation strategy

Use only immutable Git documentation, standard-library aggregate arithmetic,
HTML parsing and the existing mocked jsdom harness. Check metrics, matrix axes,
supports, FP/FN, totals, negative misses, historical/source identity, attribution,
limitations, semantic tables and unique IDs. Test disclosure toggling adds no
requests in starting/ready/failed/stopped states; retain Classify/Clear/Stop
regressions, stale-response rejection and terminal navigation behavior. Run no
native-worker, fitting, corpus evaluation or browser tests. Disable bytecode,
pytest cache and unrelated plugin autoload. Final checks include unchanged script
SHA256 `c2afb84d03548edfd28c44dfee9f2e53dbcc5a75b4c191230c293652f8dbc4bb`,
git diff --check, empty index and all out-of-scope fingerprints.

## Completion criteria

Exactly the three approved files change. Frozen values and arithmetic agree,
focused offline checks pass, existing page script/lifecycle is preserved and all
protected/private fingerprints match. No live/mobile geometry or production,
licensing expansion, linguistic/generalization or server-cancellation acceptance
is implied. Independent review and any later Git step remain separately controlled.

## Final outcome

Implementation verdict: PASS for the authorized static/offline scope.

The historical disclosure now includes source/date identity, headline/baseline
metrics, semantic class/error and actual-versus-predicted tables, the negative
miss breakdown, reproducibility metadata and limitations. All displayed metrics
and rounding agree with immutable recorded counts. FP/FN are explicitly
one-vs-rest; 99 errors are not doubled to 198. No individual-error explanation or
corpus example was introduced. Attribution/license and private-use copy remain.

2026-10-21, cwd `D:\Projects\finlens-foundation\backend`:

```powershell
& '.\.venv\Scripts\python.exe' -I -B -c "import os,sys; os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD']='1'; sys.path.insert(0,os.getcwd()); import pytest; raise SystemExit(pytest.main(['-q','-p','no:cacheprovider','--tb=short','tests/test_news_sentiment_demo.py','-k','ml_fail or ui_dom_readiness_results_clear_stale_and_verified_shutdown or ui_status_poll_cannot_overwrite_confirmed_stop or ui_terminal_stop_survives_persisted_navigation']))"
```

Result: **21 passed, 87 deselected in 16.39s**, zero failures/skips. This includes
five new aggregate/source/static tests and 16 existing mocked DOM cases, with
the Classify/Clear/Stop test extended to toggle the static disclosure in
starting/ready/failed/terminal states without adding requests. Existing late
status, stale response and persisted-navigation regressions passed. No listener,
worker, original corpus, model fitting or inference was used.

After self-review added an explicit class-table column-label assertion, ran the
same command with only `-k ml_fail`: **5 passed, 103 deselected in 0.16s**.
This is a targeted follow-up, not five additional unique acceptance cases.

Scoped AST comparison preserved all 46 original top-level test/helper functions;
only the named DOM test was extended. Original assertions remain, with the
request allowlist strengthened to the three existing API paths. The page's
original JavaScript matches the baseline exactly (SHA256 above); no controls,
asset surface, server, worker, evaluator or route changes. Both original edited
files and current copies use LF, so no script newline conversion occurred.

Preservation reconciliation: exactly two existing authorized files modified and
this one authorized plan added. All 326 other original inventory fingerprints
match, including all protected files and ignored private backend/.env. Index
empty; branch/HEAD unchanged; git diff --check passed. Git's informational future
LF-to-CRLF conversion notices did not indicate whitespace errors. No unrelated
file or model/corpus/report artifact was introduced.

Limits: no actual browser/mobile geometry, screen-reader, live inference or
PostgreSQL/performance/cancellation acceptance. Existing historical results are
not new measurements or proof of this launch's model, generalized performance,
licensing expansion, SEC/market suitability or deployment readiness. DEP-01A3
remains BLOCKED.

Ready for targeted independent Astra High implementation review of immutable
source binding, arithmetic/matrix orientation, privacy/statistical wording,
static accessibility and lifecycle/scope preservation. Keep this plan active for
that separate coordinator-controlled checkpoint; no next milestone started.
No staging, commit, push or deployment occurred. Suggested later commit:
`feat(ml): explain frozen news sentiment evaluation errors`.
