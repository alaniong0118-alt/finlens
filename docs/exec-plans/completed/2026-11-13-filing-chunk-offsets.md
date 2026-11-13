# Exact cleaned-text offsets for filing passages

Status: completed; bounded offline correction independently reviewed
Roadmap phase: bounded source-lineage correctness in existing filing research

## Objective

Every newly chunked passage must equal the original cleaned filing text sliced
at its advertised half-open start_char/end_char range. Preserve existing passage
text, chunk IDs, window size, overlap, ranking and evidence authority.

## Current architecture and context

Read AGENTS.md first, ROADMAP.md, .agent/PLANS.md, engineering standards,
product source-lineage requirements and architecture. The data-sources contract
defines FilingChunk offsets against cleaned text, never HTML bytes.
sec_parser.chunk_filing_text strips each window but returns the window's original
offsets. Both sec_filing_service and refresh_service.stage_filing consume these
offsets. Existing stored evidence is reused, not rewritten.

Starting HEAD: 17be7b5ba856a6b881a79c2c778bb6bf85eca297; empty index and 170
pre-existing dirty files. Initial raw status, hashes of all dirty files and the
clean parser snapshot are in D:/Projects/finlens-chunk-offsets-offline-20261113/.
The reviewed accession and comparison test corrections must remain untouched.

## Constraints

Only backend/app/sec_parser.py, a new backend/tests/test_filing_chunk_offsets.py
and this plan may be edited by this task. Use installed Python with the existing
guarded offline runner. No DB operations (including SQLite), Docker, credentials, live data,
network, downloads/installations, providers/models, settings/ACL changes,
staging/commit/push, PG/Home files or bypasses of tool denials. The specifically
approved source edit may be resubmitted through the same supported edit tool.

## Non-goals

No persisted-offset repair, publication/digest migration, rechunking, new source
authority/rights/custody, changed source serialization, financial calculations,
retrieval policy, UI or milestone/release acceptance.

## Implementation stages

1. Reproduce the mismatch with synthetic cleaned filing text under the guard.
2. Adjust only emitted offsets for stripped boundary characters.
3. Exercise actual parser-to-context lineage and relevant existing pure
   regressions, self-review and verify unrelated bytes.
4. Freeze the slice for separately requested independent Astra review.
5. After that review passes, update only this record and move it to completed.

Rollback removes only this task's parser delta and two new files. No data changes.

## Decisions

- 2026-11-13: Keep trimming and window advancement unchanged. Return the exact
  trimmed interval rather than changing source text or widening a citation's
  advertised range. Existing stored rows and their digests remain authoritative
  for their own publications; this is prospective parsing behavior only.

## Discovered issues

Guarded reproduction confirms that trimmed passage text differs from its source
slice in five cases, including ordinary HTML-cleaned text at default 2500/250
windows. One positive control passes. No source/financial authority is inferred.

The subsequent combined application/test edit was rejected by apply_patch with
the exact message `patch rejected by user`; no reason was supplied. Inspection
confirmed the parser is unchanged and only the initial six reproduction cases
exist at that stop. The user subsequently explicitly answered `同意` to resubmit
the same bounded correction and tests. The coordinator clarified that its earlier
skip arose from a mistaken test-escalation assumption and did not intend to reject
the product fix. On resume, rechecked AGENTS.md, HEAD, source/tests/plan and all
170 original dirty-file hashes (zero changes), and captured a separate resume
manifest. Resume only through apply_patch; a further denial requires stopping.

The same-tool resubmission succeeded after that approval. The exact approved
formula is applied: window=text[start:end], chunk_text=window.strip(),
chunk_start=start+len(window)-len(window.lstrip()), end=chunk_start+len(chunk_text).
Window advancement/overlap and text/identity generation remain unchanged.

At final preservation verification, two original dirty files had concurrently
changed: backend/app/private_database.py and
backend/tests/test_session_research_local.py. A concurrent new plan also appeared:
docs/exec-plans/active/2026-11-13-owned-research-cleanup-uncertainty.md. This task
did not edit or restore these files; they are outside this slice. The other
168 original dirty-file hashes match entry. Reviewed accession and comparison
changes and PG/Home files remain untouched by this task.

## Progress

- [x] Read governing files and relevant source/callers; preserve dirty baseline.
- [x] Reproduce with failing guarded synthetic tests: 5 failed, 1 passed.
- [x] User approved same-tool resubmission; current files/preservation rechecked.
- [x] Implement bounded correction and verify lineage/regressions.
- [x] Self-review exact scope and preservation; freeze for separate Astra review.
- [x] Coordinator supplied separate Astra review with no actionable findings.
- [x] Verify frozen candidate hashes and close this plan without source/test edits.

## Test and validation strategy

From backend use .venv/Scripts/python.exe -I -S -B
tests/run_sec_reader_offline.py with explicit pure test selections. The unchanged
runner blocks real network/DNS, databases, .env reads, models and SDK clients.
Synthetic fixtures cover normal default-size cleaned SEC-style text, leading/
trailing/Unicode whitespace, overlap and source/citation offsets. Planned
regression includes the existing detached HybridTests, not DB or SDK fixtures.
Record actual commands/results here; no live acceptance is inferred.

All actual commands ran from D:/Projects/finlens-foundation/backend with
`.venv/Scripts/python.exe -I -S -B tests/run_sec_reader_offline.py` followed by:

| Test arguments | Actual result | Receipt |
|---|---|---|
| tests/test_filing_chunk_offsets.py before fix | 5 failed, 1 passed | reproduction.txt |
| tests/test_filing_chunk_offsets.py after approved fix, before legacy reuse case | 13 passed | focused.txt |
| tests/test_filing_chunk_offsets.py tests/test_rag.py::HybridTests tests/test_bounded_research.py | 211 passed, 8 subtests passed; one existing Starlette/httpx deprecation warning | regression.txt |

Receipts are retained in the external path above. Final invocation includes all
14 new cases and 197 existing cases; repeated focused cases are not additive.
No dependency denial occurred. Synthetic staging uses real parser/stager/vector
validation/ranker/context code, an authored SGML/HTML body, fake acquisition and
fake vectors, and a patched stored-chunk lookup. The session has zero operations.
Legacy reuse verifies detached source/text/offset fields remain unchanged, with
no loader or encoder invocation. It does not persist or read actual rows.

The all-file bounded-research selection additionally ran 16 existing in-memory
TypeScript validator cases through installed Node subprocesses, broader than the
intended Python-only test selection. Their fetch is a fixture response stub; no
Node build, browser, Home spawn retry, download or external request was used.
This is synthetic ASGI/transport behavior, not live HTTP/source/DB acceptance.

Self-review verified the full parser diff and all new tests, exact half-open
cleaned-text ranges, unchanged text/IDs/window progression, and legacy reuse.
The parser diff is 7 added/4 removed lines including its final newline; no
other production module changes. Scoped git diff --check passed.

### Independent review and documentation closure — 2026-11-13

The coordinator supplied the completed independent Astra review result under
reference `01a1d285-57f7-7652-8a53-292cb45aeb44`: no actionable findings;
23 selected tests plus 8 subtests passed, and 84,596 input/window comparisons
against HEAD passed. The reviewer reported all three candidate hashes unchanged.
These selected tests overlap the author's prior suite; counts are not additive.
The full 211-test invocation was not repeated by the reviewer. This closure
records the supplied review result and does not claim to have rerun its probes.
Actual stored database rows were not inspected; legacy reuse evidence remains
detached synthetic fixtures plus source inspection.

Before this documentation-only closure, local SHA256 checks independently
matched all three frozen candidate hashes in the external candidate-sha256.json:
parser E3128B3D75444120C41E836338E340F0FB3BF4B353F25DB027C7C13001A99BE7;
test 6C8864EFDF14309C73D9DF171D8AA4E6D79B10208F6C5E68C9FA8C848835A42C;
pre-closure plan 0BA0DACDFB5DAC1F575D0A5704A3B5F0A3467C63EC26286138EA452EFD6BFFFF.
Only this plan's text/path changes during closure. The original active-plan
candidate remains retained in the external receipts, while this completed record
adds the supplied review and closure disposition. Source and test remain frozen.

Post-move verification found no changed bytes among retained dirty paths,
including the frozen source/test. The shared worktree concurrently moved the
unrelated owned-research-cleanup-uncertainty plan from active to completed;
that move was left untouched. The only remaining mention of this plan's old
active path is plain historical text in that other record, not a Markdown link.
Scoped diff/plan-whitespace checks passed; HEAD and the empty index are unchanged.

## Completion criteria

Failure reproduced before fix; exact source intervals and unchanged text/IDs
verified; focused and relevant regressions pass; only three task files differ
from entry excluding identified concurrent work; independent review passes.
These bounded criteria are satisfied. Repository ExecPlan rules permit moving
this record to completed without live-data or broader milestone acceptance.

## Final outcome

Implemented and verified one prospective source-lineage correction. Newly
generated trimmed passages now have exact cleaned-text offsets. Existing stored
passages, offsets and publication digests retain the existing source-code reuse
path without rewriting; this was verified only with detached synthetic records,
not actual stored rows. Repairing historical records remains outside scope.
This task edits exactly the parser,
new dedicated 14-case test and this plan. It adds no source/rights/custody or
financial authority and changes no retrieval threshold, serialization or formula.

HEAD remains 17be7b5ba856a6b881a79c2c778bb6bf85eca297, with zero staged paths,
59 modified and 115 untracked individual files at final verification, including
the separately identified concurrent work. No commit/push, DB/Docker/network,
credential/provider/model operation, settings change or build was performed.
Independent Astra review passed with the limited evidence recorded above.
Documentation-only closure retains the frozen source/test content and changes
only this plan's review/closure record and location. No tests are repeated for
that documentation update. No live source, stored-row repair, actual
commissioning, browser, provider, deployment or full-suite acceptance is claimed. Docker
named-pipe and Home build denials remain unresolved and were not retried.

Suggested commit when authorized:
`fix(filings): align trimmed passage offsets with source text`.
