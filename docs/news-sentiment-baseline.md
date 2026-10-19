# Offline financial news sentiment baseline

ML-PB-01 is a private, nonprofit, local university experiment in three-class
**financial NEWS sentence sentiment**: negative, neutral, positive. It adds no
application endpoint, frontend behavior, database integration or online service.
Existing SEC filing-tone and financial-return calculations are separate.

## Authorization and licensing

Financial PhraseBank v1.0 is supplied under **CC BY-NC-SA 3.0 Unported**:
<http://creativecommons.org/licenses/by-nc-sa/3.0/>. Preserve attribution, the
license reference and notices of transformations. The source License.txt and
README.txt are read and fingerprinted directly inside the ZIP. The full linked
legal terms have not been fetched in this offline task.

Academic citation, retained as specified by the source README:

Malo, P., Sinha, A., Takala, P., Korhonen, P. and Wallenius, J. (2013):
*Good debt or bad debt: Detecting semantic orientations in economic texts.*
Journal of the American Society for Information Science and Technology.
(in Press, as recorded in the supplied README.)

The source credits support from Emil Aaltonen Foundation and Academy of Finland,
grant 253583. Its authors are Pekka Malo, Ankur Sinha, Pyry Takala, Pekka Korhonen
and Jyrki Wallenius; version 1.0, last modified July 19, 2013.

Authorization covers only private nonprofit academic local evaluation. Do not
publish or redistribute the corpus, original sentences, predictions linked to
original sentences or trained weights. There is no separate clearance for public
redistribution of trained weights, commercial use or an online service. Any
future permitted sharing must satisfy applicable attribution, noncommercial and
ShareAlike obligations. Repository tests contain authored synthetic text only.

## Inputs and supported environment

Operator-owned local input, never copied into the repository:

`D:\FinLens-OperatorReports\sec-ml-01-phrasebank\FinancialPhraseBank-v1.0.zip`

- ZIP SHA256: `0E1A06C4900FDAE46091D031068601E3773BA067C7CECB5B0DA1DCBA5CE989A6`
- Selected member: `FinancialPhraseBank-v1.0/Sentences_75Agree.txt`
- Member SHA256: `A7CA39FB9DC60AED1C323EE635494AED4ACDFC05E0349A9E74367502325303A4`
- License.txt SHA256: `FA4F941EF92F40D55DD34DDEA45D96A20672607D152698BC160F8DB3AF5E36C7`
- README.txt SHA256: `80241DD9639AF987CD87BBB2D8872392C6D45596A488EBEFCA2D425DA46F5809`

Verified installed environment: Windows x64, CPython 3.14.7, Unicode 16.0.0,
scikit-learn 1.9.1, NumPy 2.5.3, SciPy 1.18.1, joblib 1.6.0 and threadpoolctl
3.7.0. The separate [offline inventory pins](../backend/requirements-ml-offline.txt)
are not included by normal application dependencies. No packages are installed
by the runner or authorized by this task. Other environments have not been
accepted; a split/group mismatch fails before training and needs investigation.

## Reproduction command

From repository root, using the already-installed interpreter:

```powershell
& '.\backend\.venv\Scripts\python.exe' -I -B '.\backend\scripts\evaluate_news_sentiment.py' --zip 'D:\FinLens-OperatorReports\sec-ml-01-phrasebank\FinancialPhraseBank-v1.0.zip'
```

The only input option is an explicit absolute local ZIP path. The ZIP/member and
document fingerprints are fixed in source; there is no CLI option to unpin them,
extract data, export a model, choose an output file or change the experiment.
Success prints one JSON object to stdout and exits 0; errors print a stable
sanitized JSON error code and exit 2, without echoing paths or source sentences.
An operator can read stdout; do not redirect it into unauthorized report files.

The CLI disables bytecode generation and installs Python audit hooks before
loading any ML packages. Hooks reject filesystem writes/mutations, socket use
(except local hostname metadata lookup required by NumPy), subprocess creation,
SQLite connection events and application/database/provider/model-hub imports.
Training is single-thread limited. No serialization, extraction, reports,
temporary files or cache creation is implemented. This is scoped Python-level
protection over installed trusted libraries, **not an OS/native-code sandbox**.
Importing the module does not install global audit hooks or load ML dependencies;
the guarded entry point is direct script execution as above.

## Strict source handling

The ZIP is read as a bounded regular local file, at most 1,000,000 bytes; remote
path spellings, nonfixed Windows drives and symlink/reparse path components are
rejected. The archive must contain exactly the original eleven member names,
including three directory entries and two ignored macOS resource-fork files.
Duplicate names, unexpected members, symlinks, encryption/unsupported flags,
comments and malformed/duplicate extra-field metadata are rejected.

Total declared expansion is capped at 3,000,000 bytes, any member at 800,000 bytes,
and source documents at 16,384 bytes each. Only License.txt, README.txt and the
selected sentence member are decompressed. No path is extracted.

Sentence parsing is ISO-8859-1, strict `sentence@sentiment`, CRLF records, no
header, at most 5,000 rows and 4,096 bytes per row. Blank text, invalid labels,
extra delimiters and control characters fail. Original text, whitespace and
labels are preserved; no issuer identities or relabeling are introduced.
UTF-8 is not the sentence-file encoding. Source documents are UTF-8.

The README describes 4,840 sentences; the inspected broadest file contains 4,846.
Consensus files are fully nested, including multiplicities, and must not be
concatenated:

| Subset | Negative | Neutral | Positive | Rows |
|---|---:|---:|---:|---:|
| 50Agree | 604 | 2,879 | 1,363 | 4,846 |
| 66Agree | 514 | 2,535 | 1,168 | 4,217 |
| **75Agree, selected** | **420** | **2,146** | **887** | **3,453** |
| AllAgree | 303 | 1,391 | 570 | 2,264 |

75Agree requires **more than 75% annotation agreement**, according to the README.
It retains more training examples than AllAgree while requiring stronger
agreement than 50Agree. This selection was made before the reference evaluation.

## Grouping and split contract

`phrasebank-pinned-latin1-v1` parses source rows. Grouping version
`nfkc-numeric-jaccard-sequence-v1` operates only on grouping keys:

1. NFKC then casefold, Python Unicode `re.findall(r'\w+', text)` tokens, joined
   with one space. Equal normalized keys are joined, covering exact duplicates.
2. Replace each token containing any `str.isdigit()` character with `<num>`;
   equal ordered token skeletons are joined.
3. For every pair with at least eight tokens each, join if the masked token-set
   Jaccard similarity is at least 0.85 **and** ordered token `SequenceMatcher`
   ratio is at least 0.90, with `autojunk=False`.
4. Take transitive connected components, always rooting at the minimum original
   zero-based source-row index. Preserve original source order for splitting.

Numbers, negation and original text are not changed in model input. Grouping can
intentionally place contrasting numeric statements in one mixed-label group;
labels are retained, never reconciled by majority vote.

Reference grouping: 3,349 components; 76 nonsingleton groups covering 180 rows;
largest group nine; 149 fuzzy pairs. Five exact duplicate groups account for
five extra rows; six normalized duplicate groups account for six extra rows.
Neither exact nor normalized duplicates have conflicting labels in 75Agree.
Broader grouping creates two mixed-label groups covering seven rows.

Split uses `StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)` over
all source rows, original labels and component roots. Fold 0 is test, fold 1 is
validation, and folds 2-4 are training. Labels may be used for stratification and
support checks before training; no test performance is used for selection.

| Partition | Negative | Neutral | Positive | Rows | Groups |
|---|---:|---:|---:|---:|---:|
| Training | 252 | 1,287 | 532 | 2,071 | 2,011 |
| Validation | 84 | 430 | 177 | 691 | 669 |
| Test | 84 | 429 | 178 | 691 | 669 |

Assert exact row coverage, all three classes in each partition, and no group,
normalized key, masked skeleton or detected fuzzy pair crossing partitions.
SHA256 input is ASCII `one_based_line:zero_based_component_root:fold` in original
source order, separated by LF with a final LF. Expected split fingerprint:

`93624966453164D93D611CA3E817B85093FD204C2056406F855CE10B4F536948`

Count/group/fingerprint mismatches stop the runner before fitting. Do not modify
labels, reorder rows or force group identities to reach the reference result.

## Learning and evaluation contract

Experiment version: `news-sentiment-tfidf-svc-v1`. Fit TF-IDF on training text
only: word unigrams/bigrams, lowercase, `min_df=2`, `sublinear_tf=True`, L2 norm,
float64, default `(?u)\b\w\w+\b` token pattern, no stop words or accent stripping,
IDF with smoothing, `max_df=1.0`, no feature cap. Expected training vocabulary:
6,866 features, 51,115 nonzero entries across 2,071 training rows.

Fit `LinearSVC` on training features/labels only: balanced class weights, seed
42, `max_iter=10000`, `tol=1e-4`, `dual='auto'`. Evaluate C = 0.1, 1, 10 on
validation macro-F1; tie breaks prefer smaller C. Keep the winning training-only
model without refitting on validation. Only then transform and predict test text.
The majority comparator uses the training-majority label, neutral. Metric label
order is always negative, neutral, positive; undefined precision is zero.

The following prior assessed reference values were reproduced by the implemented
runner in its single authorized real-ZIP execution on 2026-10-19. They are never
hardcoded predictions:

| C | Validation accuracy | Validation macro-F1 |
|---:|---:|---:|
| 0.1 | 0.845152 | 0.774445 |
| 1 | 0.856729 | 0.790197 |
| **10** | **0.855282** | **0.790790** |

| Method | Test accuracy | Test macro-F1 |
|---|---:|---:|
| Majority neutral | 0.620839 | 0.255357 |
| TF-IDF + LinearSVC, C=10 | 0.856729 | 0.799833 |

Reproduced supervised test precision/recall/F1/support:

| Class | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| Negative | 0.791045 | 0.630952 | 0.701987 | 84 |
| Neutral | 0.892857 | 0.932401 | 0.912201 | 429 |
| Positive | 0.789773 | 0.780899 | 0.785311 | 178 |

Reproduced confusion matrix, rows actual and columns predicted in label order:

```text
53  17  14
 6 400  23
 8  31 139
```

The runner computes actual metrics, per-class scores and both confusion matrices
from predictions. It returns no sentences, vocabulary terms, row assignments,
per-row predictions or trained objects. Hashes and aggregate comparisons are
reproducibility evidence; they are not scientific generalization evidence.

## Focused synthetic verification

From `D:\Projects\finlens-foundation\backend`, with the installed interpreter:

```powershell
& '.\.venv\Scripts\python.exe' -I -B -c "import os,sys; os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD']='1'; sys.path.insert(0,os.getcwd()); import pytest; raise SystemExit(pytest.main(['-q','-p','no:cacheprovider','tests/test_news_sentiment_baseline.py']))"
```

The environment override is process-local and suppresses unrelated installed
pytest plugins. Bytecode and pytest cache are disabled. Tests use in-memory
synthetic archives and authored sentences, instrument real fitting/selection,
and exercise runtime guards in isolated child interpreters. No corpus input is
read during tests. No existing application suites or live services are run.

The final focused run passed **58 tests, 0 failed, 0 skipped** in 2.54 seconds.
Both Python files passed in-memory syntax checks and scoped import/export review.
The one real-ZIP run exited 0 with no stderr; source hashes, all grouping/split
references, selected C, confusion matrix and reported metrics matched exactly.
No test row had an empty feature vector. Model objects ended with the process;
only aggregate stdout was retained in the tool session. Detailed execution and
preservation evidence is recorded in the scoped
[ExecPlan](exec-plans/active/2026-10-19-ml-pb-01-offline-baseline.md).

## Scientific and product boundaries

Neutral dominates the corpus; macro-F1 and negative recall must accompany
accuracy. The reference model misses 31 of 84 negative test rows. Corpus size,
one holdout, agreement filtering and retained duplicate weighting limit claims.
Text heuristics cannot identify every paraphrase or ensure event/company/time
independence. There is no verified issuer/time metadata for those split claims.

The README describes investor-oriented historical sentence annotations. They do
not establish return predictability. This experiment establishes reproduction
only: no calibrated probabilities, cross-company generalization, SEC-filing
suitability, cybersecurity classification, trading signals, portfolio/stock
return predictions or production readiness. No dataset, weights or online
service may be published under this authorization. No second annotator or manual
re-annotation is required or introduced.

Version any subsequent change to source pins, parser, Unicode behavior, grouping,
split algorithm, dependencies, feature extraction or classifier parameters.
Keep model serialization out of scope until separately authorized and reviewed;
any later artifact would require immutable hashes, training/source lineage,
environment metadata and a separate licensing decision.

## ML-PB-02 private interactive demonstrator

Implementation is separate from live acceptance. **Do not execute the real ZIP
evaluation, corpus-backed demonstrator or live browser acceptance until the
coordinator authorizes the next checkpoint.** This implementation phase uses
authored synthetic inputs, in-memory ASGI/DOM tests and harmless native Windows
children. It does not reread the retained ZIP, train on it or open the HTTP demo.

The independent [demo entry point](../backend/scripts/serve_news_sentiment_demo.py)
serves an owned HTML page and four explicit routes. It does not import the main
FinLens API, database, frontend, private configuration or release policy. Normal
FinLens launchers, dependencies, routes and REL-01B behavior are unchanged.

### Eventual operator launch and stop

Only after separate real-ZIP/local-browser approval, from repository root:

```powershell
& '.\backend\.venv\Scripts\python.exe' -I -B '.\backend\scripts\serve_news_sentiment_demo.py' --zip 'D:\FinLens-OperatorReports\sec-ml-01-phrasebank\FinancialPhraseBank-v1.0.zip'
```

Default address is `http://127.0.0.1:8765/`; optional `--port` chooses an explicit
unused port. No host override, alternate-port fallback, reload, auto-browser or
shared startup is provided. The exclusive loopback socket refuses an occupied
port and never terminates another listener. The operator opens the displayed
address, waits for verified readiness, enters their own English-intended sentence
and receives one of negative/neutral/positive. Subsequent submissions reuse the
same in-memory model. Page reload does not retrain it.

Clear removes the current browser input/result and invalidates late UI updates.
The server retains ownership of an abandoned request until its real response or
deadline; new requests receive BUSY immediately. Stop clears input/result at once,
requests owned shutdown and waits for explicit `stopped` status. A mere connection
error does not prove shutdown: the page tells the operator to press Ctrl+C in the
owning terminal if it cannot verify cleanup. Ctrl+C also shuts down the owned job.
No browser history of inputs, model export, sentence echo or confidence/margin is
provided. Historical held-out metrics are explicitly separated from predictions.

### Windows ownership and resource enforcement

Supported tested environment: Windows 10 build 19045, CPython 3.14.7 x64 and the
already installed local package set (FastAPI 0.142.2, Uvicorn 0.54.0 and the pinned
ML packages). No packages or configurations are installed or changed.

Before child creation, create an unnamed non-inheritable Job Object and apply:

- `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`.
- `JOB_OBJECT_LIMIT_JOB_MEMORY`, 1 GiB of job committed memory.
- `JOB_OBJECT_LIMIT_ACTIVE_PROCESS`, one process; no breakaway flags.

`CreateProcessW` uses `STARTUPINFOEXW`, `EXTENDED_STARTUPINFO_PRESENT`,
`PROC_THREAD_ATTRIBUTE_JOB_LIST` (0x2000D) and
`PROC_THREAD_ATTRIBUTE_HANDLE_LIST` (0x20002). Job attachment is part of kernel
process creation; there is no post-spawn `AssignProcessToJobObject`, suspended
attachment substitute or weaker fallback. The inherited handle list contains
only the child sides of the private stdin/stdout pipe pair plus NUL stderr.
Unused pipe ends close immediately; the job handle remains exclusively in the
supervisor. Retain the owned process handle for exit verification. Unsupported
APIs, incompatible nested jobs, inheritance or attachment failures fail closed.

Windows venv python.exe uses a redirector process, which conflicts with the
one-process job. The owned child therefore uses that venv's exact base interpreter
directly with `-I -B` and the explicit prepared venv package directory. This is
process-local module selection, not a change to either environment. The minimal
child environment contains SystemRoot, WINDIR, a restricted PATH and explicit
one-thread BLAS/OpenMP limits. No inherited provider credentials are forwarded.
BLAS thread limits must precede imports: an import-only native probe originally
hit the unchanged memory cap without them; the bounded bootstrap now passes.

The native tests verify actual atomic membership/limits, handle exclusion,
abrupt owner death during startup and simulated inference, spawn/attachment
failure, committed-memory/process denial, interruptible blocked pipe writes,
timeout cleanup and survival of a separate unrelated harmless process. They do
not train a financial model or use the original corpus.

The 1 GiB limit is **not an exact resident-memory ceiling**. Parent monotonic
deadlines are 60 seconds from before child creation through validated readiness,
and two seconds for complete inference IPC and response validation. On timeout,
invalidate the request, terminate the owned job, verify exit and enter a terminal
failed state. No late response, worker respawn, training retry or limit increase
is accepted. Normal shutdown allows a separate five-second grace period, then
owned termination/exit verification bounded to five seconds. Failed verification
remains explicitly unavailable; OS scheduling cannot guarantee exact real-time
termination instants.

### Model reuse and private IPC

The existing runner now exposes shared training-feature and linear-classifier
helpers. Its pinned parser, grouping, split, audit hook, CLI and aggregate contract
remain unchanged. The future demo validates the original 3349 groups and split
fingerprint, fits only the original 2071 training rows with fixed C=10, and never
retunes or predicts on validation/test rows. Function-local corpus, grouping,
partitions and feature matrices are released after preparation; only the fitted
vectorizer/classifier and dependencies remain in the worker. No model object is
transferred to the parent or serialized.

IPC uses private inherited anonymous pipes, four-byte big-endian lengths and
strict JSON, maximum frame 32768 bytes. Validate length before retaining payload,
duplicate JSON keys, exact schemas, protocol version, launch ID, request ID and
allowed labels. Reject stale/duplicate/mismatched responses, disconnects and
partial frames that outlive their deadline. Admit one classification at a time;
no queue. Parent writes run off the event loop and are interrupted by owned job
termination; reads check pipe availability before bounded reads. Ownership is
retained until both write completion and validated response are established.

The worker establishes inherited IPC before installing the unchanged ML-PB-01
audit hook. The parent separately permits only its loopback bind and creates its
event-loop wakeup channel before denying outbound connections. Audit hooks are
not an OS sandbox; Job Objects enforce lifetime/resource limits, not complete
filesystem/network containment. Libraries/operator/host are trusted. Releasing
references and process exit do not guarantee secure memory erasure.

### HTTP, privacy and UI contract

| Route | Contract |
|---|---|
| `GET /` | Owned page with per-launch token and CSP nonce |
| `GET /api/status` | Token required; safe state/phase/elapsed/version/run metadata |
| `POST /api/classify` | Token plus exact Origin; JSON object with only `text` |
| `POST /api/shutdown` | Token plus exact Origin; empty object, then owned shutdown |

Require peer `127.0.0.1`, exact `Host: 127.0.0.1:<port>`, and exact POST
`Origin: http://127.0.0.1:<port>`. Reject duplicate security headers and query
strings. API authentication uses a random per-launch custom-header token, never
a URL parameter or cookie. Proxy trust, CORS, docs, OpenAPI, WebSockets, access
logging and raw exception logging are disabled. Responses include no-store,
no-referrer, nosniff, framing denial and a restrictive nonce CSP. Only local owned
HTML/CSS/JavaScript is served; no remote assets, spellcheck, autocomplete,
telemetry, cookies, storage, user-input history or external resource requests.

Bodies are limited to 16 KiB and five seconds of reading. Sentences are nonblank,
single-line strings of at most 2000 Unicode code points; controls, malformed JSON,
duplicate/extra fields, batches and non-string text are rejected. Accepted input
is not trimmed or normalized before vectorization. English is intended, without
claiming automatic language verification. All-zero features produce
UNSUPPORTED_FEATURES, never an intercept-only classification.

Inference returns only label and safe method/demo/run metadata. Error responses
contain stable codes, with no submitted input, token, path, native stderr,
probability, score or recommendation. Unknown errors are sanitized. The page
uses text-safe DOM APIs, character counting by Unicode code points, labelled
controls, visible focus, accessible status messages and responsive styling.
Input and output clear on shutdown/navigation; stale results are suppressed.
The page includes the original attribution and private/noncommercial restrictions.

### Implementation evidence and remaining acceptance

Focused tests run only the ML-PB-01 and new demo modules with pytest plugin/cache
and bytecode generation disabled. Native tests and ASGI/jsdom tests use synthetic
inputs; ASGI transport/fetch stubs do not open a demo HTTP listener. An additional
in-memory comparison against committed ML-PB-01 code produced exactly equal
synthetic evaluation output. Parser/group/split/pins/audit/CLI orchestration ASTs
were unchanged. This is **synthetic regression evidence**, not a new real-ZIP
reproduction or real browser acceptance.

Final implementation verification passed **140 tests, 0 failed, 0 skipped**
(59 baseline/helper and 81 demo cases), including 11 real harmless Windows native
lifecycle/protocol cases. Source syntax and scoped import/export/configuration
checks passed. No corpus-backed model or live demo/browser was run in this phase.

Before any live demonstration, obtain the separate coordinator checkpoint for
one real-ZIP regression reproduction, actual corpus-backed startup/resource
measurement and local browser acceptance. Verify readiness, repeated inference,
keyboard/mobile behavior, recovery, strict loopback identity, no unexpected
traffic/storage/artifacts and verified shutdown. Do not start REL-01B's services
or query its database to accept this separate tool. No full-corpus generalization,
SEC filing suitability, calibrated probabilities, return prediction, production
readiness, online deployment or weight-redistribution rights are established.

Rollback: stop the owned demonstrator and revert only the seven allowlisted
ML-PB-02 paths. There are no model files, migrations, data copies or application
configuration changes to clean up. Detailed phase evidence is in the
[ML-PB-02 ExecPlan](exec-plans/active/2026-10-20-ml-pb-02-private-news-sentiment-demo.md).
