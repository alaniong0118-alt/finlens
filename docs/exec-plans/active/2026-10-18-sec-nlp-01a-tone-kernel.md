# SEC-NLP-01A: deterministic filing-tone kernel

Status: active; bounded implementation authorized, independent review pending.
Roadmap phase: independent SEC NLP foundation; no market-data work.

## Objective

Implement `score_filing_tone(text: str) -> ToneResult` as a deterministic,
standard-library-only lexical proxy over caller-supplied plain text. Return exact
Fraction scores and auditable input-local matches without fetching or authenticating
filings. Stop for coordinator/Astra High review before integration.

## Current architecture and context

Starting main/HEAD: `371e0d48bed96abac20dd1b91b541236ec6569e8`; empty index.
Existing status: modified frontend/next-env.d.ts and two untracked protected reports.
Protected SHA256 values:

- frontend/next-env.d.ts: F4E8976C19FC926644D72610BF1058BD6BF52ADD97E46A02BC0B912A751625C0
- backend/reports/canary-aapl_guarded_live_20261010_111844_3580610-publication.json: A783517D2875E39DF4C831C410265D0126FBF6A9D3DDBA1103F7BD61B057844C
- backend/reports/refresh-discovery-aapl_sec_discovery_20261010_002323_0671678.json: F8DF96C8890C0ECE1E1701B25BC5C43B879C359ECEB96ACB451A2A0DAA58BF7C

Private backend/.env was fingerprinted without displaying its contents/hash.
Retrieval tokenization normalizes text and imports application dependencies;
reuse its conventions, not its implementation. Existing chunking strips payload
text while retaining pre-strip window offsets. No global offset arithmetic is safe
without a separately verified mapping.

## Constraints and non-goals

Only this plan, backend/app/filing_tone.py and backend/tests/test_filing_tone.py
may change. No API/UI, database, configuration, external models, encoder, network,
dependencies, services, market data or deployment. No staging, commit or push.
MD-02A remains NO-GO and DEP-01A3 remains BLOCKED. No integration or broad audit.

## Implementation stages

1. Verify baseline/protected hashes and write this plan.
2. Implement immutable kernel and explicit bounded contract.
3. Add focused controlled-sentence tests and Python isolation guards.
4. Run only the new test module, self-review, and recheck preservation.
5. Stop with an unstaged coordinator/Astra handoff. Leave this plan active.

## Decisions and contract

- 2026-10-18: method `sec-filing-tone-v1`, lexicon `authored-finance-tone-v1`.
- Positive terms: favorable, improved, improvement, profitable, resilient,
  strengthened, strong, successful. Negative: adverse, declined, deterioration,
  impairment, loss, losses, unfavorable, weak. Exact authored vocabulary only.
- Actual str only; no coercion. Preserve original text. Tokens are maximal runs
  of Unicode L/M/N/Pc characters, with internal straight/curly apostrophes.
  Lookup permits ASCII only after curly-apostrophe replacement, then lowercases.
  No stemming, compatibility folding, HTML parsing or language detection.
- Half-open offsets are Python string indices into the exact supplied input,
  never bytes, JavaScript UTF-16 indices or filing-global offsets.
- Negators: no, not, never, without, cannot, can't (including curly apostrophe).
  Suppress the next three tokens, never invert polarity. Internal apostrophes
  do not reset scope; other Unicode punctuation, CR/LF, Unicode line/paragraph
  separators and contrast tokens but/however/yet do. Nearest applicable cue wins;
  multiple cues never cancel. `not only` with no intervening reset does not start
  a cue. Numeric and unmatched word tokens consume window positions.
- Count all matched occurrences; preserve negated matches and cue offsets.
  Active P/N counts produce Fraction(P-N, P+N). Balanced active matches are scored
  zero. No tokens/no lexicon matches/all matches negated are distinct unscorable
  reasons with score None.
- Frozen dataclasses and immutable tuple/frozenset values. Versions, counts,
  status/reason, exact score and all ordered matches are returned.
- Limits: 24,000 characters, 4,000 tokens, 1,000 matches including negated ones.
  Reject, never truncate. Reject Unicode Cc/Cf/Cs except TAB/CR/LF. Errors expose
  only stable codes. Validation order: type, character count, characters, token
  count, match count. No public caller configuration or serialization API.

## Discovered issues and limitations

Context-dependent words, shallow negation, unlisted inflections, non-English
words, lost context at chunk boundaries and overlapping chunks limit interpretation.
No measured sentiment accuracy, financial-risk, market-sentiment or prediction
claims. Raw markup is treated literally, not cleaned, interpreted or executed;
the caller must supply plain text. No automatic multi-chunk aggregation.
Unicode classification follows the interpreter's Unicode database; reproducibility
was checked within Python 3.14.7 / Unicode 16.0.0, not across different databases.

## Progress

- [x] Baseline/index/protected hashes verified before edits.
- [x] Approved scope and contract recorded.
- [x] Kernel and focused tests implemented.
- [x] Focused tests and self-review complete; final integrity checks recorded below.
- [ ] Independent Astra High review and coordinator disposition.

## Test and validation strategy

Controlled sentences only; no fake filing identities. Cover exact arithmetic,
unscorable versus zero, whole words, Unicode/offsets, negation bounds/resets,
immutability, reproducibility, invalid inputs, exact resource limits and overflow.
Static import inspection and fresh-process guards check the Python boundary;
they do not claim OS sandboxing. Disable bytecode, pytest cache and plugin autoload.
Run only tests/test_filing_tone.py from backend using the existing venv.

## Completion criteria

Focused tests pass with exact counts recorded; only authorized files added;
baseline/protected bytes and private environment unchanged; index empty.
Astra High must independently assess text/offset fidelity, arithmetic, bounded
negation, resource rejection, purity, test quality and honest method labels.
Integration remains unapproved even after local checks pass.

## Checks actually run

From backend, with existing interpreter and no installed plugins/cache/bytecode:

```powershell
.\.venv\Scripts\python.exe -B -c "import os; os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD']='1'; import pytest; raise SystemExit(pytest.main(['-p', 'no:cacheprovider', 'tests/test_filing_tone.py', '-q']))"
```

First run: 87 passed, 2 failed. Two separator fixtures incorrectly placed an
apostrophe between letters, where the approved tokenizer retains it inside one
word. Corrected those fixtures to use standalone apostrophes and added explicit
straight/curly internal-apostrophe regressions. Added coverage for every authored
term. No production behavior was changed to accommodate those fixture failures.

Final run: **107 passed, 0 failed, 0 skipped**, 0.23s. Includes two guarded fresh
Python processes with different hash seeds. They deny non-standard/application
imports, network/process/write audit events, and, during scoring, file opens,
environment reads, clock and random calls. Import-time standard-library source
reads remain permitted. These guards are Python-level observations, not OS
containment or security sandbox proof.

In-memory ast.parse passed for both new Python sources; runtime metadata is
Python 3.14.7 / Unicode 16.0.0. No other tests, browser/API, services, database,
provider, SEC, encoder/model or market-data operations were run.

Self-review traced token boundaries, original offsets, cue expiry/reset/selection,
not-only handling, exact Fraction arithmetic, empty/no-match/all-negated versus
zero, immutability, resource bounds and sanitized errors. No integration changed.
Tracked diff remains only the pre-existing protected next-env change; the three
authorized additions are untracked. Index remains empty. Standard git diff --check
exited 0. Each addition's no-index --check exited 1 for a new-file difference,
with only Git LF/CRLF conversion notices and no whitespace-error diagnostics.
An independent read-only check of all three additions found no trailing whitespace
or extra blank lines at EOF. Protected hashes and private backend/.env were compared
again after implementation; final exact preservation results accompany handoff.

## Final outcome

Local implementation/focused verification complete. Only the two new code/test
files and this active plan were added. All three protected files and private
backend/.env retain their baseline hashes. HEAD/main and index are unchanged.
No staging, commit or push. Independent Astra High review/coordinator disposition
remain pending; do not integrate, move the plan or start another milestone.

Suggested later commit: `feat(nlp): add deterministic filing-tone kernel`.
