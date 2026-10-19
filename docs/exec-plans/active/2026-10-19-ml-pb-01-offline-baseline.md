# ML-PB-01: reproduce the offline financial news sentiment baseline

Status: completed on 2026-10-19; retained at the explicitly authorized active path.
Roadmap phase: scoped offline enabling task, no subsequent milestone authorized.

## Objective

Implement an aggregate-only, memory-only evaluation runner and synthetic tests.
Reproduce the previously assessed Financial PhraseBank 75Agree experiment once
against the retained original ZIP. This is financial NEWS sentence sentiment.

## Current architecture and context

Read [AGENTS.md](../../../AGENTS.md), [ROADMAP.md](../../../ROADMAP.md),
[engineering standards](../../engineering-standards.md), and
[plan rules](../../../.agent/PLANS.md). No application integration is needed.
Starting branch main, HEAD 98d2d73438d37688860129b35b078a2cb10eea7a; index empty.
All 311 existing tracked/nonignored files were fingerprinted in memory.
Protected pre-existing paths and SHA256:

- frontend/next-env.d.ts: F4E8976C19FC926644D72610BF1058BD6BF52ADD97E46A02BC0B912A751625C0
- backend/reports/canary-aapl_guarded_live_20261010_111844_3580610-publication.json: A783517D2875E39DF4C831C410265D0126FBF6A9D3DDBA1103F7BD61B057844C
- backend/reports/refresh-discovery-aapl_sec_discovery_20261010_002323_0671678.json: F8DF96C8890C0ECE1E1701B25BC5C43B879C359ECEB96ACB451A2A0DAA58BF7C

Ignored/untracked backend/.env has a private in-memory fingerprint; no values or
private fingerprints are written here. The original ZIP SHA256 matches
0E1A06C4900FDAE46091D031068601E3773BA067C7CECB5B0DA1DCBA5CE989A6.

## Constraints

Only these five NEW files are authorized:

- backend/scripts/evaluate_news_sentiment.py
- backend/tests/test_news_sentiment_baseline.py
- backend/requirements-ml-offline.txt
- docs/news-sentiment-baseline.md
- docs/exec-plans/active/2026-10-19-ml-pb-01-offline-baseline.md

Keep this plan at its explicitly allowlisted active path after completion.
No environment/dependency installation, corpus extraction, raw corpus output,
sentence-linked predictions, model serialization, cache/temp/report writes,
database, service, network, provider, SEC, frontend or financial-engine activity.
No Git staging, commit, push or deployment. Private nonprofit academic use only;
retain CC BY-NC-SA 3.0 attribution and no public weight-license clearance claim.

## Non-goals

No SEC filing/cybersecurity classifier, filing-tone replacement, probabilities,
return/portfolio prediction, issuer inference, online serving or production claim.

## Implementation stages

1. Verify baseline and preserve fingerprints; write this plan.
2. Implement strict pinned archive reader, grouping/splits and lazy local ML runner.
3. Add authored synthetic tests, separate environment pins and methodology docs.
4. Run focused tests, in-memory syntax/scoped checks; debug and retest as needed.
5. Execute the single real-ZIP reproduction after synthetic gates pass.
6. Self-review scope, all preserved fingerprints, original ZIP and Git integrity.

## Decisions

- 2026-10-19: Reproduce original source order and minimum-index component roots;
  changing component identity/order can change StratifiedGroupKFold output.
- 2026-10-19: Only aggregate metrics leave the pipeline. Hash/structure/parser
  errors use stable codes, never archive contents or caller paths.
- 2026-10-19: Model selection uses validation macro-F1 and smaller-C tie breaks;
  no train-plus-validation refit. Test transformation occurs after selection.
- 2026-10-19: CLI enables Python audit guards against writes/network/database
  imports and subprocesses, with only local hostname metadata lookup allowed.
  These guards supplement scoped code inspection; they are not an OS sandbox.

## Discovered issues

None yet. Reference values are comparison evidence, never substituted predictions.

## Progress

- [x] Baseline, protected paths, original ZIP, package inventory and instructions.
- [x] Runner, synthetic tests, separate pins and documentation.
- [x] Focused tests and scoped checks pass: 58 passed, 0 failed/skipped.
- [x] Exactly one real-ZIP reproduction and reference comparison.
- [x] Final preservation checks: exactly five authorized additions, all 311
  existing files/private environment/original ZIP/protected hashes unchanged.

## Test and validation strategy

Run only backend/tests/test_news_sentiment_baseline.py with bytecode, pytest
cache and third-party plugin autoload disabled. Use synthetic in-memory archives
and authored sentences; no licensed fixtures. Check malformed inputs, metadata,
group transitivity, split/fingerprint determinism, fitting/selection boundaries,
metric order, dependency errors and guarded side effects. Syntax checks compile
source in memory. Reproduction uses installed packages only, no model export.
Record exact commands/results below; run git diff --check.

## Completion criteria

Only five allowed additions; original files/private environment/ZIP unchanged;
empty index and expected HEAD; focused tests pass; grouping and split match or
any discrepancy is diagnosed; actual aggregate metrics documented; no artifacts.

## Final outcome

Implemented the five authorized new files only. The focused module passed 58
tests, and exactly one real-ZIP evaluation reproduced the reference split and
all observed metrics. No source sentences, per-row predictions, trained weights,
dataset files or machine-readable report artifacts were exported. No application
modules, database, services, external providers or networks were used.

Self-review confirms immutable source text/labels, deterministic minimum-index
component roots, training-only feature/model fitting, validation-only selection,
delayed test transformation, explicit metric label order, aggregate output and
separate dependency inventory. No source changes followed the final synthetic
test run or the single real-ZIP reproduction; only these documentation records
were updated. Final preservation reconciliation is recorded below after checking.

Verdict: PASS for the bounded offline implementation/reproduction; ready for
targeted Astra High review, not production/domain-generalization acceptance.
No staging, commit, push or deployment. Suggested future commit message:
`feat(ml): add reproducible offline news sentiment baseline`.

## Execution evidence

2026-10-19, cwd `D:\Projects\finlens-foundation\backend`:

```powershell
& '.\.venv\Scripts\python.exe' -I -B -c "import os,sys; os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD']='1'; sys.path.insert(0,os.getcwd()); import pytest; raise SystemExit(pytest.main(['-q','-p','no:cacheprovider','tests/test_news_sentiment_baseline.py']))"
```

Final pre-reproduction focused run: **58 passed in 2.54s**, no failures/skips.
Earlier runs passed 55 and 58 cases while adding targeted coverage; no test
failures occurred. Only this new module was executed. Synthetic child-process
tests completed guarded training with no stderr, rejected real file/socket/import
attempts before effects, and produced no model/corpus artifacts. Changing only
held-out labels left validation selection unchanged. Synthetic tied model
selection chose C=0.1, confirming C=10 is not hardcoded.

Both Python sources compiled and parsed in memory. Scoped AST inspection found
no application/database/provider/model imports or extraction/serialization/file
export calls. `git diff --check` passed. No existing application suite ran.

Exactly one real-ZIP reproduction was executed, cwd
`D:\Projects\finlens-foundation`:

```powershell
& '.\backend\.venv\Scripts\python.exe' -I -B '.\backend\scripts\evaluate_news_sentiment.py' --zip 'D:\FinLens-OperatorReports\sec-ml-01-phrasebank\FinancialPhraseBank-v1.0.zip'
```

Exit 0, no stderr. Actual source/member/document hashes match the pinned hashes.
3453 rows (negative 420, neutral 2146, positive 887); 3349 groups, 76 nonsingleton
groups/180 rows, largest nine, 149 fuzzy pairs, two mixed-label groups/seven rows.
Exact duplicate groups five, normalized groups six; neither has label conflicts.
All defined leakage checks passed. Training/validation/test sizes 2071/691/691;
supports and group counts match the methodology document. Split fingerprint:
93624966453164D93D611CA3E817B85093FD204C2056406F855CE10B4F536948.

Actual Python 3.14.7, Unicode 16.0.0, scikit-learn 1.9.1, NumPy 2.5.3, SciPy
1.18.1, joblib 1.6.0, threadpoolctl 3.7.0. Training vocabulary 6866, nonzero entries
51115. Validation macro-F1 by C: 0.1 -> 0.7744453788844393;
1 -> 0.7901971954721279; 10 -> 0.7907898112994203. Actual winner C=10.

Actual test results:

| Method | Accuracy | Macro-F1 |
|---|---:|---:|
| Majority neutral | 0.6208393632416788 | 0.2553571428571429 |
| TF-IDF + LinearSVC | 0.8567293777134588 | 0.7998327245268925 |

Actual supervised confusion matrix, rows actual/columns predicted, ordered
negative/neutral/positive: [[53,17,14],[6,400,23],[8,31,139]]. No empty test feature
rows. Negative precision/recall/F1: 0.7910447761194029 / 0.6309523809523809 /
0.7019867549668874, support 84. Neutral: 0.8928571428571429 / 0.9324009324009324 /
0.9122006841505131, support 429. Positive: 0.7897727272727273 / 0.7808988764044944 /
0.7853107344632768, support 178. Full aggregate JSON stayed only in tool-session
memory. No corpus rows or model parameters/weights were exported.

Observed references agree exactly; no environment, source, split, model-selection
or metric discrepancy remains. Licensing and scientific limits remain: private
nonprofit academic use only, no redistribution clearance for trained weights,
single small imbalanced corpus/holdout, about 63% negative recall, no company/time
independence, no SEC validation, calibration, returns prediction or serving claim.

Final reconciliation found exactly the five authorized additions and zero changed
or removed pre-existing paths. All 311 initial file fingerprints, the three
protected SHA256 values listed above, ignored/untracked backend/.env and original
ZIP are unchanged. HEAD remains 98d2d73438d37688860129b35b078a2cb10eea7a; index
empty. Existing script/test/pytest cache inventories are unchanged. No unexpected
model, corpus, prediction, temporary or report artifacts appeared. Scoped checks
of all five new files found no trailing whitespace or missing final newline;
`git diff --check` passed. CLI source review, guarded synthetic evaluation and the
guarded real reproduction found no provider/network/database/application calls
or filesystem write paths. Python audit hooks are supplemental, not OS isolation.
No dependency installation, configuration change, service start or unrelated
suite execution occurred. No remaining implementation blocker.

## Resumed final verification — 2026-10-20

Final verification only; no implementation, test suite or corpus evaluation was
repeated. The current five files matched byte-for-byte an in-memory replay of
the original successful patch sequence from this task's local transcript. The
last runner/test edits preceded the recorded 58-pass run at
2026-10-19T14:26:35.914Z and the single real reproduction. Source SHA256:

- Runner: B612CCEB7162635C86517B33887C1B79509C9B5FBCDF965D0C8E980782B591E0
- Synthetic tests: D3E6F21EF9F9B8EA35B38D7C1F8833A3208E19CAB7BBE86420BC3C9BED5FE1A3

Both Python files passed fresh in-memory compile/AST checks. Documentation is
complete and all its local links resolve. Git remains at the expected HEAD with
an empty index. Exactly five task additions remain; the only other status paths
are the original protected frontend file and two protected reports. All three
protected SHA256 values and the original ZIP SHA256 freshly match their recorded
baselines. All 316 tracked/nonignored paths equal the initial 311 plus five.

A metadata-only scan of 406 workspace files, excluding .git, dependency
environments, node_modules and existing Next build directories, found no
unexpected files modified since implementation began and no model/dataset/temp
artifact candidates. Source/test/pytest cache paths within that scan contained
no new files modified during the task. No services, network, database,
dependencies, staging, commits, pushes or deployment were used during resume.

Private environment verification limitation: the original backend/.env SHA256
was deliberately retained only in the interrupted tool runtime and is no longer
available. The prior completed before/after comparison passed, as recorded above
and in the original tool outputs. Fresh checks confirm the file is still ignored
and untracked, its last-write metadata remains 2026-10-17T09:00:12.764462Z, and its
private fingerprint is unchanged throughout this resumed verification. Metadata
and a new resume-only fingerprint do not replace a cryptographic comparison with
the lost original baseline; no such fresh comparison is claimed. No secret or
private fingerprint is printed or persisted.

Final resumed verdict: **PASS WITH CONDITIONS**, solely because the original
private environment fingerprint cannot be compared afresh across the runtime
reset. Implementation, synthetic evidence and corpus reproduction remain passed;
no implementation blocker or source discrepancy was found. Ready for targeted
Astra High review with that explicit preservation-evidence limitation. Tests and
training need not be rerun. Only this authorized plan changed during resume.
