# Bounded Chinese financial amount questions

Status: active; candidate will remain unstaged for independent review.

## Objective and starting state

Starting `main`: `b2be213925879f38f95c444c1dd1f150b76829dc`; index empty.
The five existing exceptions retain their recorded hashes: modified
`frontend/next-env.d.ts`, two untracked backend reports and two unrelated plans.

Recognize the complete original utterance, such as `2024 財年的營收是多少？`,
without stripping unsupported semantic text. Reuse `bind_operation()`,
`operation_agrees()` and the existing financial-reader/metric/source dispatch.
The English Unicode admission guard and its entry points remain unchanged.

## Exact scope and grammar decision

Only `backend/app/research_answer_service.py`, the new
`backend/tests/test_chinese_research_answers.py`, and this plan may change.

The complete supported form is:

`[請問/请问] [股票代號/股票代碼/股票代码 + ASCII ticker + 的] period [的] metric 是多少/為多少/为多少 [? / ？]`

Optional spaces are ASCII or ideographic spaces at component boundaries only.
No normalization, translation, unknown-word removal or partial matching is allowed.
Ticker prefixes use an explicit stock-code label and an exact case-insensitive
catalog ticker, at most 10 ASCII characters. Bare tickers are deliberately rejected:
catalog words such as NOT/IF/OR must not consume negation or clauses. No company-name
or transliteration aliases. A known other labelled ticker receives existing mismatch
guidance; an unknown labelled ticker abstains.

Metric terms are presentation vocabulary for four existing canonical metrics:

| Metric | Exact question terms |
|---|---|
| Revenue | 營收 / 营收 / 營業收入 / 营业收入 |
| Net income | 淨利 / 净利 / 淨利潤 / 净利润 |
| Total assets | 總資產 / 总资产 |
| Free cash flow | 自由現金流 / 自由现金流 |

Periods are `最新` (latest available), `最新季度` / `最新一季`, `最新財年` /
`最新财年`, or one ASCII year 1900–2099 followed by `財年` / `财年`, optionally
`第1–4季/季度` using ASCII or 一/二/三/四. Fiscal dates, direct-quarter/YTD
selection, unavailable values, instant as-of labels and FCF arithmetic remain the
existing metric service's responsibility. No comparisons or growth operations.

## Fail-closed boundaries and limitations

Negation, definition/method requests, qualifications, multiple metrics/years or
companies, extra clauses/suffixes, calendar-only years, relative years, other
metrics and unlisted punctuation/forms abstain without reading financial facts.
Controls/format characters retain HTTP 422 validation before whitespace stripping.
The selected company remains authoritative; no company switch or source rule changes.

This is a finite Traditional/Simplified question grammar, not general Chinese
language support. Answers and service explanations remain in their existing English
presentation. Supported questions can still return unavailable; no new data coverage,
translation, credentials, live DB, browser, provider, migration or deployment work.

## Progress and evidence strategy

- [x] Verify branch/base/index/protected hashes; inspect recognition, typed dispatch,
  fiscal-period schema, public route and shared isolated fixtures.
- [x] Reproduce the supported-operation gap with new tests before implementation.
- [x] Add a whole-utterance grammar that emits existing single-value operations;
  preserve every existing English/Unicode guard and calculation path.
- [x] Verify bilingual aliases/periods/tickers, English-equivalent observations and
  provenance, missing-data honesty, adversarial rejection and zero fact reads.
- [x] Run the existing guarded offline runner on the new tests and the existing
  current, historical and operation-handoff suites. Preserve the previously observed
  guard exclusion for `test_period_kind_mixing_cannot_compare_even_service_directly`.
- [x] Review exact diff, recheck scope/protected hashes and leave the index empty.

Use `.venv/Scripts/python.exe -I -S -B tests/run_financial_insights.py` from
`backend`, explicitly selecting tests. The existing runner blocks network,
PostgreSQL, dotenv/private environment reads and providers; SQLite fixtures only.
No new test harness or guard exceptions. Rollback is the isolated three-file patch.

## Actual validation and outcome

2026-11-04, existing offline runner with no new harness or guard exceptions:

- Initial 73-case reproduction: 36 failed / 37 passed. Of the failures, 34 exposed
  the unsupported-operation gap; two were fixture setup errors (missing required
  exchange metadata), corrected in the new tests. Both original receipts are retained.
- First implementation: 71 passed / 2 fixture setup failures. After fixing the fixture,
  the combined current/historical/operation-handoff/new suite passed 642 cases.
- Tightened company prefixes to require an explicit stock-code label, then added
  regressions for bare NOT/IF/OR aliases and all three labelled ticker forms.
- Final command from `backend`: `.venv/Scripts/python.exe -I -S -B
  tests/run_financial_insights.py tests/test_chinese_research_answers.py
  tests/test_research_answers.py tests/test_historical_research_answers.py
  tests/test_research_operation_handoff.py
  -k "not test_period_kind_mixing_cannot_compare_even_service_directly" --tb=short`:
  **651 passed, 1 deselected**, including **82 new cases**. The one excluded direct
  metrics test retains its previously documented prohibited-evidence-loader guard
  limitation; it was not rerun or weakened for this task.
- Accepted aliases match the English path's complete observations/provenance,
  including instant assets and derived FCF. Missing inputs/quarters stay unavailable.
  Rejection fixtures contain current and historical facts and observe zero fact SELECTs.
- Source-segment comparison against the baseline verifies 12 existing definitions
  unchanged: the English Unicode/request/math/current/historical gates, operation
  category/agreement/binding, financial-reader answer dispatch and both resolvers.
- Diff whitespace check passes. Exactly three candidate files remain unstaged;
  index empty, baseline unchanged and five protected exception hashes preserved.

Private-workspace receipts: `chinese-grammar-before.txt`,
`chinese-grammar-focused.txt`, `chinese-grammar-compatibility.txt`,
`chinese-grammar-final.txt`. No receipts are added to the product repository.
Independent review remains pending; no staging, commit or push. This does not verify
live database/browser behavior or add general Chinese understanding/localized answers.
Suggested commit: `Recognize bounded Chinese financial amount questions`.
