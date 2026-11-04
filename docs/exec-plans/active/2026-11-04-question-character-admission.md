# Fail-closed question character admission

Status: active; bounded correction awaiting independent review.

## Objective and context

At baseline `1dbe1af222dbdff294877593140531e5457362cb`, `words()` erases non-ASCII
semantic text. Chinese negation or a request for a definition can become a numeric
revenue request. Both current and historical recognizers need raw-text admission,
including when the caller provides a precomputed mathematical intent.

The starting index is empty. The existing modified `frontend/next-env.d.ts`, two
untracked backend reports and two unrelated ExecPlans retain their recorded hashes.

## Scope and decisions

- Change only the answer service, its existing operation-handoff tests and this plan.
- Admit printable ASCII subject to the existing unknown-math-symbol exclusions,
  Unicode space separators, explicitly listed English
  typographic quotes/dashes/ellipsis and the four existing mathematical equivalents.
  Reject other semantic characters before word/token extraction. Do not translate,
  case-fold or introduce general Unicode/Chinese recognition.
- Check both recognition entry points even with precomputed intent. Keep the
  mathematical classifier consistent with their raw-text boundary.
- Reject control/format characters and Unicode line/paragraph separators before
  request whitespace stripping, including boundary tabs/newlines; retain existing
  empty-question validation. Such requests return validation error 422; unsupported
  semantic text follows the existing `not_matched` evidence fallback.
- No company-name exemption: an unsupported character in a configured company name
  must not authorize erasing arbitrary semantic text. Accented/non-Latin question
  spellings deliberately abstain; supported ASCII ticker spellings retain existing
  behavior. Company catalog/alias normalization is not redesigned by this correction.

## Evidence plan and progress

- [x] Verify branch, baseline, empty index and five protected hashes; inspect both
  recognizers, operation dispatch, request validation and existing offline runner.
- [x] Reproduce the confirmed examples and precomputed-intent bypass with focused tests.
- [x] Add admission guards, including operation diagnostics before company aliases,
  and preserve punctuation/operator compatibility.
- [x] Run new regressions and existing current/historical/operation-handoff suites with
  `backend/.venv/Scripts/python.exe -I -S -B tests/run_financial_insights.py` from
  `backend`, explicitly selecting those three test files. The existing runner forbids
  network, dotenv/private environment reads, PostgreSQL connections and providers;
  fixtures use isolated in-memory SQLite only.
- [x] Verify rejected inputs execute no financial-fact SELECT, inspect the final diff,
  recheck protected hashes, leave all three files unstaged for independent review.

No live database, credentials, provider, browser, migration or deployment is needed.
Rollback is the isolated three-file patch; no stored data or configuration changes.

## Actual validation and final outcome

2026-11-04, using the existing guarded runner, without modifying its restrictions:

- Before the service change: `tests/test_research_operation_handoff.py -k question_text
  --tb=short` reproduced both confirmed examples and the supplied-intent path:
  **40 failed, 15 passed, 119 deselected**. The definition request became latest
  revenue; the negated fiscal-year request became a historical revenue operation.
- Initial focused correction: **55 passed, 119 deselected**. Additional boundary
  cases then covered Unicode line/paragraph separators, unknown ASCII math symbols,
  and production rejection before company-alias normalization.
- Full three-file compatibility attempt: **568 passed, 1 failed**. The existing
  `test_period_kind_mixing_cannot_compare_even_service_directly` calls `view()` and
  stops at the runner's forbidden `load_production_evidence` dependency. This is
  outside the modified recognition path; that direct-service test remains unverified.
  The guard was not relaxed and no production evidence was loaded.
- Final command from `backend`: `.venv/Scripts/python.exe -I -S -B
  tests/run_financial_insights.py tests/test_research_answers.py
  tests/test_historical_research_answers.py tests/test_research_operation_handoff.py
  -k "not test_period_kind_mixing_cannot_compare_even_service_directly" --tb=short`:
  **569 passed, 1 deselected**, including **67 new cases**. Rejection API tests
  observe zero financial-fact SELECTs with current and historical fixtures present.
- Logs are retained in the private task workspace as `question-admission-before.txt`,
  `question-admission-focused.txt`, `question-admission-compatibility.txt` and
  `question-admission-final.txt`; no test receipts are added to the product repository.
- Final diff whitespace check passed. Exactly these three candidate files remain
  unstaged; the index is empty and all five protected exception hashes are unchanged.

The policy intentionally narrows unknown Unicode punctuation and semantic text,
including accented company spellings; a known company name is not an exemption.
The existing ASCII ticker path is tested with an accented catalog name. No new
multilingual catalog aliases are claimed. English company-mismatch protection and
mathematical operation/period comparisons retain their existing regression coverage.

Independent review is pending. This is not Chinese-language support, source
verification, browser or real PostgreSQL acceptance. No commit or push was performed.
Suggested commit: `Reject unsupported question characters before numeric recognition`.
