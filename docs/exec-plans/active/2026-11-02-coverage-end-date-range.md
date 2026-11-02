# Bounded stored coverage by reported period end date

Status: active
Roadmap phase: partial D9 stored-data coverage usability correction

## Objective and context

Allow an explicit inclusive reported-period end-date range without truncating a
coverage map or changing canonical calculations. Manual AAPL acceptance reported
19 annual windows / 209 cells at publication 1 (facts 0, evidence 1); the quarter
request displayed the resource-limit message. The underlying limit was not
measured, so the report does not establish a 65th-window failure.

Baseline: b6460fe7546a183ca52408898a9159fd259af074, empty index. Ports 8021/3003
had no listeners before implementation. The five historical exceptions, including
the completed personal-site plan, remain outside this change.

## Constraints and decisions

- Keep the 64-window / 704-cell / 4096-source-reference ceilings and all complete
  company input, work, output, source-policy and publication safeguards.
- Optional paired `end_from` / `end_to` ISO dates select by period end, inclusively.
  Unfiltered calls retain their behavior; no implicit latest-N selection or paging.
- Load and admit complete bounded company inputs before selection. Preserve
  overlapping windows and prior-year calculation operands outside the display range.
- Echo the exact selected range; a filtered map is complete only within that scope,
  never a claim of complete filing history. Report only safely known limit categories.
- No service, browser, real DB, private configuration, acquisition or Git writes.
  The Computer Use URL-confidence stop remains unresolved and is not retried here.

## Implementation and validation

- [x] Verify baseline, stopped listeners and protected bytes; inspect contracts.
- [x] Implement schema/route, scoped diagnostics, range UI and runtime validation.
- [x] Guarded synthetic backend and mounted frontend tests, affected regressions,
  lint and TypeScript checks. Record commands and actual results below.
- [ ] Freeze candidate for independent review; no commit or runtime acceptance yet.

Focused cases: 65-window unfiltered rejection versus complete bounded success,
inclusive boundaries, overlaps, invalid selectors, remaining resource bounds,
outside-range YoY lineage, version zero, stale/ignored-abort results and safe errors.

## Evidence and limits (2026-11-02)

From `backend`, the existing isolated runner blocks private dotenv reads, physical
DB/provider/socket/model dependencies before application imports:

```powershell
.\.venv\Scripts\python.exe -I -S -B tests/run_financial_insights.py tests/test_financial_coverage.py tests/test_financial_coverage_policy.py tests/test_quarter_window_comparison.py tests/test_quarter_window_policy.py tests/test_financial_insights.py
```

Result: **272 passed**, one existing Starlette/httpx deprecation warning. The real
in-process route tests use synthetic sessions, confirm zero/nonzero pins, stale
409 rejection, read-only transaction setup/close, and unchanged route admission.
This is not a physical PostgreSQL or real HTTP server acceptance.

From `frontend`:

```powershell
& E:/node.exe --test tests/financial-coverage.test.mjs tests/quarter-window-comparison.test.mjs
& E:/node.exe node_modules/eslint/bin/eslint.js . --ext .ts,.tsx
& E:/node.exe node_modules/typescript/bin/tsc --noEmit --incremental false
```

Result: **32 passed, 0 failed/skipped**; lint and TypeScript exit 0. Scoped date
controls retain native focus/editor identity and 44px targets; CSS sizing checks
are static, not proof of actual narrow-screen paint or calendar-picker behavior.

CoverageBudget reuses the unchanged Budget limits and records only the failed
check's allowlisted category. Generic unclassified resource failures remain
generic. No count, source content or private configuration is added to errors.
Filtering does not remove complete-company admission or bank/YoY context. For the
sole off-map operand case (filtered YoY prior revenue), validation still requires
one exact prior source, correct role/metric/value/unit/date, company/archive path
and immutable fact identity; all in-map raw projections remain cross-checked.
No formulas or shared annual/quarter validators were changed.

The user may need a narrower explicit range even after filtering if source/work
limits remain exceeded. Complete input limits still apply before range selection;
these are logical/cooperative limits, not new native memory/egress guarantees.

## Final outcome

Implementation and focused offline evidence are ready for independent review.
Unfiltered calls retain their limits and meaning, with additive null range metadata;
filtered results echo the exact inclusive end-date scope. No route permissions,
data/calculation rules, launchers or existing full-runtime gates changed. No Git
staging/commit/push, services, real DB/HTTP or browser action was performed.
Native browser and real AAPL acceptance remain pending; the manually observed
quarter failure's specific limit remains unknown. Suggested later commit:
`fix(coverage): support explicit bounded period-end ranges`.
