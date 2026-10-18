# SEC-NLP-01B Increment 1: published-passage tone backend

Status: active; backend implementation authorized, coordinator/Astra High review pending.
Roadmap phase: bounded SEC NLP integration, backend only.

## Objective

Expose GET /companies/{ticker}/filings/{accession_number}/chunks/{chunk_id}/tone
for one server-resolved, completely published chunk. Preserve exact input-local
Unicode offsets and Fraction scoring without modifying the approved kernel.

## Current architecture and context

Baseline: main, HEAD `9ef8a294c97030850e659ffe59ac0b75b467d0ae`, empty index.
Pre-existing state: modified frontend/next-env.d.ts and two untracked reports.
Protected SHA256 values verified before edits:

- frontend/next-env.d.ts: F4E8976C19FC926644D72610BF1058BD6BF52ADD97E46A02BC0B912A751625C0
- backend/reports/canary-aapl_guarded_live_20261010_111844_3580610-publication.json: A783517D2875E39DF4C831C410265D0126FBF6A9D3DDBA1103F7BD61B057844C
- backend/reports/refresh-discovery-aapl_sec_discovery_20261010_002323_0671678.json: F8DF96C8890C0ECE1E1701B25BC5C43B879C359ECEB96ACB451A2A0DAA58BF7C

Private backend/.env and the approved kernel/tests/shared readers were fingerprinted
without disclosing private values. Existing VersionedRoute/read_session establish
version headers, no-store and repeatable-read/read-only transactions. Existing
bounded readers admit a complete inventory before loading text/vectors.
require_published alone is only an existence check on the migrated path.

## Constraints and non-goals

Exactly five authorized paths: backend/app/filing_tone_service.py (new),
backend/app/main.py, backend/app/release_policy.py,
backend/tests/test_filing_tone_integration.py (new), and this plan (new).
No frontend, real DB, service, network, acquisition, installation, migrations,
index/sync, other file changes, caching, Git writes or deployment.
Do not repeat SEC-NLP-01A or REL-01B suites. MD-02A stays NO-GO;
DEP-01A3 stays BLOCKED. No integration into UI is authorized.

## Implementation stages

1. Verify baseline and create this plan.
2. Add selected-publication resolver and typed response adapter.
3. Add versioned route and only its exact GET allowlist entry.
4. Run focused fake-session/compiled-PostgreSQL tests with physical I/O guards.
5. Self-review exact diff, recheck integrity and stop for independent review.

## Decisions

- 2026-10-18: Path values are bounded selectors, not trusted metadata. Require one
  canonical decimal X-FinLens-Data-Version in [0, 9007199254740991]. Reject missing,
  malformed or duplicate headers and unexpected query parameters before sessions.
- Resolve company/state/manifest from storage. No unmigrated fallback. Validate
  current pin, evidence-version relationship, explicit pending targets, selected
  manifest identity/count/version/digest, whole-filing identities and embeddings.
  Reuse bounded inventory/body readers and validate_chunks/chunk_digest; do not
  refactor or relax existing readers. Never select full stored filing text.
- Intact publication version <= evidence version <= current data version remains
  eligible after facts-only advances and unrelated refresh failures.
- Snapshot exact chunk text and server metadata, close read session, then call
  unchanged score_filing_tone. Return scope=published_chunk and
  offsets=unicode_code_point. No global offsets, whole-filing score or aggregation.
- Response contains company data/evidence versions, publication accession/version/
  digest, source chunk/form/filed/filename/official URL, exact text and nested tone
  versions/counts/ordered matches/status/reason. Score is numerator/denominator
  integers or null. Client text/source URL/offset/approval fields are never used.
  Unexpected query fields are rejected; a GET body is ignored and cannot provide
  source identity or text. The API/schema explicitly labels the lexical proxy.
- Typed errors: 422 invalid selectors/pin; 409 DATA_VERSION_CHANGED for stale pins;
  409 EVIDENCE_PENDING for invalid publication; existing SEARCH_SCOPE_TOO_LARGE;
  404 unknown scoped chunk; 409 TONE_INPUT_UNSUPPORTED for kernel input rejection.
  Valid unscorable text is HTTP 200. Diagnostics never echo stored text.
- Only this exact GET is added to the SEC-only allowlist. No alias, method,
  profile-default, AI permission or deployment expansion.

## Discovered issues and limitations

Publication validation requires the selected filing's full bounded chunk inventory
and digest even when only one chunk is scored. No cache or weaker shortcut.
Missing full filing text is irrelevant; missing/invalid chunks are not rebuilt.
Source search serialization can normalize line endings; consumers must use returned
exact text for offsets, never a preview or legacy global chunk window. Lexical
tone is not confidence, investment sentiment, risk, prediction or claim support.
Admission caps the selected filing at 4,000 chunks of 3,000 code points each;
validating one passage can therefore read 12 million text code points plus vectors.
Only the selected chunk reaches the kernel. Its 3,000-character admission cap is
stricter than the kernel's 24,000-character cap; existing kernel limits remain intact.
Lifecycle JSON must be an object, not a falsey malformed value defaulted to {}.
Independent linguistic accuracy, real PostgreSQL runtime and UI acceptance are out
of scope. Python-level guards do not prove OS containment.

## Progress

- [x] Baseline, empty index and protected hashes verified.
- [x] Scope and implementation contract recorded before code changes.
- [x] Backend route/service and focused tests implemented.
- [x] Focused checks and self-review complete; preservation reverified.
- [ ] Independent Astra High review and coordinator disposition.

## Test and validation strategy

Use only new fake-session tests: record/compile production PostgreSQL SELECT/SET
statements; reject physical DB/network/provider/encoder/generation/write work.
Cover source substitution, lifecycle/version zero/staleness, manifest/embedding/
digest failures, bounds before bodies, valid old publications, no full text reads,
session closure before scoring, exact fractions, Unicode/CRLF, unsupported input
and unscorable states. Exercise new exact release admission only.
Existing guarded offline runner disables dotenv and physical database/socket
connections; run it with -B and only the new module, plugin autoload disabled.
Syntax checks operate in memory. Preserve all unrelated/protected bytes and index.

## Completion criteria

Focused results and exact file inventory recorded; only five authorized files
changed/added; approved kernel and shared readers unchanged; protected hashes and
private environment preserved; index empty. Astra High must review source binding,
publication integrity, bounds, lifecycle/pin ownership, serialization, closure before
kernel calls, sanitized errors and the exact allowlist delta before next increment.

## Checks actually run

2026-10-18, from backend, existing interpreter and guarded runner, no installation:

```powershell
.\.venv\Scripts\python.exe -B -c "import os,runpy,sys; os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD']='1'; sys.argv=['tests/run_dep01a2_increment2_offline.py','tests/test_filing_tone_integration.py']; runpy.run_path(sys.argv[0],run_name='__main__')"
```

Initial run: 116 passed, zero failed/skipped. Expanded run: 125 passed, zero
failed/skipped. Final rerun after test-helper cleanup: 125 passed, zero failed,
zero skipped in 2.06 seconds.
Each run emitted one existing Starlette/httpx TestClient deprecation warning.
No SEC-NLP-01A, REL-01B or broad suite was run.

The 125 cases cover pre-session selector/pin/query rejection, duplicate headers,
verified zero and max-safe version, stale/missing pin metadata, selected pending
targets, malformed lifecycle JSON, missing/duplicate/invalid manifests, company/
filing/chunk substitutions, every stored embedding including unselected chunks,
whole-publication digest, inventory/body mismatch, bounds before body reads,
exact 3,000-character/4,000-chunk admission, old publications after facts advances
and unrelated failures, missing full text, unknown scoped chunks, selected nonfirst
overlapping chunks, exact Fraction/zero/null output, Unicode/CRLF/local offsets,
unsupported controls, ignored forged GET body, deterministic output, close failure
before scoring, and exact SEC-only method/path admission. Fake sessions reject
writes; physical DB/socket and acquisition/encoder/LLM entry points are guarded.
Production SELECT/SET statements are compiled with the PostgreSQL dialect.

In-memory syntax/whitespace checks passed for all authorized files. AST comparison
against HEAD proved main.py changes only imports plus the new handler, and the
release allowlist delta is exactly the authorized GET with no removals.
git diff --check passed (Git notes existing CRLF checkout normalization).

Integrity recheck: main/HEAD unchanged; index empty. Only the five authorized paths
were added/changed by this task. All three protected SHA256 values above match;
private backend/.env remains ignored and fingerprint-identical (value not logged).
Approved filing_tone.py and its test module, freshness_service.py and
refresh_contracts.py are fingerprint-identical. The three pre-existing protected
worktree entries remain intact. No staging/commit/push was performed.

## Final outcome

Backend increment implemented and locally verified within synthetic offline scope.
No real database, provider, model, service, browser, UI or deployment acceptance.
No local implementation blocker; coordinator disposition and independent Astra
High review remain required before advancing. Stop here; this record does not
authorize the UI, market data, model admission, deployment or Git mutations.

Astra High should independently examine the five-file patch against this baseline:
canonical pre-session pin validation including zero; server-owned identities and
attribution; lifecycle/pending/version ordering; complete bounded inventory and
manifest/count/digest/vector validation; no full-text reconstruction or reads;
session closure before the unchanged kernel; exact fractions/Unicode offsets and
unscorable/unsupported distinctions; sanitized errors and no-store/version headers;
only the new exact GET in SEC-only admission; preservation and negative-test guards.
The reviewer must distinguish fake/compiled-SQL evidence from real DB acceptance
and must not repeat the already approved kernel or REL-01B suites.
