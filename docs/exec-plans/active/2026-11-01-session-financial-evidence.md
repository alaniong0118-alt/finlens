# Session-owned financial evidence bridge

Status: active — offline candidate implemented and focused checks run; independent review and production admission remain outstanding.

## Objective and current context

Build a bounded session-artifact path from original inline-XBRL bytes through complete cash-flow inventory and the existing deterministic financial engine to a session provenance receipt. Limit results to annual operating cash flow, positive-outflow capital expenditure and existing free cash flow. Work began on main `d11cfd87adb368c9b35bdec42d9e7a25f22c490e`, was paused while browser CI repairs landed, and resumed on `663bb57e0ce1a2fb343804d60560b08f9f47ca54`. Preserve the modified `frontend/next-env.d.ts`, two existing backend reports and blocked Markdown export plan. The current ownership service resolves metadata only, and the existing original-filing adapter inventories revenue and net income, not cash flow. No structural reference or digest grants financial authority.

## Constraints and non-goals

No provider/network, database writes, credentials, private environment, services, installs, deployment, Git writes or changes to public financial response schemas. Never query or insert Company/FinancialFact for this path. Entrypoints accept raw token and session/artifact selectors/revisions and requested annual metric/period; trusted server composition owns custody, identity, operation rights and parser mapping, with unconfigured production denied before artifact bytes are read. No fake DB fact IDs, accessions or CIKs, no second calculator, no generic IFRS/source support. Separate session and DB references, preserve exact DB sort and public IDs. Prevent incomplete inventories from becoming results; inspect relevant facts in every period including dimensional and nested facts before annual selection. Recheck owner, revisions, source, rights, mapping and cancellation before handoff, without holding a database lock during parsing. That check is point-in-time, not an atomic HTTP delivery guarantee.

Logical bounds: 4 MiB original bytes; 100,000 XML nodes; depth 64; 4,096 contexts; 256 units; 4,096 inline facts in total (including relevant cash-flow facts); 64 KiB encoded result. Enforce bounds during construction; these do not guarantee native parser memory or hard runtime isolation. Reject unsupported encoding, DTD/entity/external resolution, malformed or unsupported inline semantics, unresolved references, and resource exhaustion; allow ordinary predefined/numeric XML character references.

## Stages and decisions

1. Add explicit session observation identity and ordering without changing integer DB-fact semantics; test DB parity.
2. Add fixed-profile complete bounded SEC cash-flow inventory over original bytes with no acquisition. Relevant malformed nonannual facts and conflicts must not be ignored.
3. Add internal session result contract and default-deny server composition; validate identity, rights, units, period, dimensions, mapping and scope before shared-engine invocation. Recheck authorization at handoff.
4. Test synthetic annual success and negative cases, including no Company/FinancialFact access; exercise existing real local 10-Q sample for parsing and specifically reject it as an annual match. A verified annual real-original fixture remains an acceptance prerequisite.

## Validation and progress

- [x] Inspect engine, ownership and original filing adapters and document scope.
- [x] Implement typed session observation keys, bounded inventory and a default-deny private-composition calculation path.
- [x] Run focused offline negative, integration, existing engine parity, adapter and ownership checks; see actual results below.
- [ ] Independent actual-code review and subsequent operator-controlled delivery.

From `backend`, using the existing `.venv` and its guarded offline runner:

- `.\.venv\Scripts\python.exe -I -S -B tests/run_financial_insights.py tests/test_session_financial_research.py`: 52 passed. Includes synthetic annual FCF, negative/missing inputs and mismatched annual intervals, private fake-composition admission and reauthorization, no SQL/socket calls, parser limits, hidden/nested and nonannual conflicts, dimensional exclusion, and the bounded receipt. After review it also checks future facts, reordered dimension identity and post-tree cancellation/ownership exception identity.
- `.\.venv\Scripts\python.exe -I -S -B tests/run_financial_insights.py`: 141 passed, including the existing C5 shared-engine comparison against the reference implementation. One existing Starlette deprecation warning was reported.
- The same guarded runner with 17 explicitly selected existing SEC adapter parser tests: 128 passed; existing v2/v3 behavior was exercised without production source admission.
- `.\.venv\Scripts\python.exe -I -S -B tests/test_research_ownership.py`: 29 passed under its separate offline guard.
- One initial combined pytest invocation mixed incompatible test-isolation guards and produced setup errors; it was interrupted and is not a passing run. Subsequent checks above used their separate supported guards. No PostgreSQL or provider was started or used.

Independent review identified two integrity issues and one error-propagation issue: a relevant fact could end after the trusted filing period, equivalent dimension sets could be ordered differently, and callback `ValueError` subclasses could lose their identity after tree construction. The candidate now rejects out-of-bound facts before selection, canonicalizes dimensions for conflict comparison while retaining original locators, and rethrows the original callback exception. The revised candidate still requires independent re-review.

The reviewer independently reported 100 C5 cases passing (117 deselected). The reviewer's initial nine-case SQLite attempt failed at fixture setup because SQLite lacked the `C` collation; the remaining eight cases did not run. The in-memory financial-metrics fixture now installs a test-only UTF-8 byte comparator for `C` before metadata creation; this is not a PostgreSQL configuration or acceptance test. With `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, the guarded `tests/run_dep01a2_increment2_offline.py` run passed the fixture collation control (1 case) and the five specifically selected legacy selectors (9 parameterized cases): revenue provenance, deterministic ranking, form/amendment/ID tie-break, exact EPS serialization and the API schema/no-key/query bound. One Starlette and 19 SQLAlchemy deprecation warnings were reported for the nine-case run. No physical database or provider was used.

The fixed profile accepts the specifically observed English month-name date transform with strict parsing; unsupported lexical forms still fail closed. The known, hash-checked original 10-Q parsed four nine-month cash-flow facts. A private synthetic composition reached and asserted the specific `annual_period_unavailable_or_ambiguous` rejection for FY2026; it did not grant that filing production authority. These observations do not establish real annual filing acceptance.

## Completion and limits

No live or non-SEC provider acceptance, source-rights approval, real identity provider, PostgreSQL acceptance, or full UCR completion is implied. Synthetic bytes do not confer authority. Existing local original `aapl-20260627.htm` matches its known 1,018,326-byte SHA-256 and contains both relevant concepts for nine-month intervals, not an established annual result. A separately verified original annual filing and production source/rights/custody decisions are still needed. Retain all existing work and update this record with actual results and remaining blockers.
