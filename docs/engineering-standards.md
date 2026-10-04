# Engineering standards

[AGENTS.md](../AGENTS.md) is the governing repository instruction. This document defines the working and acceptance conventions; [architecture](architecture.md) owns implementation details, [product spec](product-spec.md) owns behavior, and [data sources](data-sources.md) owns provenance policy.

## Scope and durable state

Read root instructions first, inspect Git status and relevant implementation/tests, and consult the [roadmap](../ROADMAP.md) for milestone work. Preserve existing changes; do not begin later phases automatically. Use an [active ExecPlan](../.agent/PLANS.md) for complex, risky, long-running, or multi-stage work. Record decisions, discoveries, progress, verification, and remaining work there so another agent can resume.

Use small changes within the existing FastAPI/SQLAlchemy/PostgreSQL and Next.js/TypeScript architecture. Add dependencies or infrastructure only for a demonstrated need. Preserve API compatibility or explicitly plan the transition. Avoid N+1 SQL/HTTP; measure representative cost before adding caches or parallelism.

## Financial and evidence correctness

- Define canonical metric, unit/currency, scale, instant/duration period, fiscal dates, and source mapping before adding a metric. Retain original SEC concepts and filing lineage.
- Keep monetary calculations precise; define rounding at presentation boundaries. Specify formulas and compatible operands for ratios, YoY/QoQ, and free cash flow. Handle missing values, zero denominators, year-to-date records, amendments, and restatements explicitly.
- Match comparison periods by documented fiscal/duration rules, not adjacent rows or calendar-quarter assumptions. Separate reporting period from filed date. Do not mix currencies or incomparable industry measures silently.
- Return derivation inputs and source references for important calculated values. Use deterministic calculations rather than an LLM for arithmetic.
- Keep retrieval company/accession scope, ranking, deduplication, evidence thresholds, and context bounds explicit and evaluated. Valid citation identity is not proof of claim support; real audits must check the actual supplied evidence.

## Data, credentials, and recovery

Do not expose secrets in output, files, plans, logs, or commits. Private env files stay ignored; public examples contain blanks/placeholders. Confirm credential presence without printing values. Optional AI configuration must not gate core Research Mode.

Ingestion should be idempotent, resumable, and isolated by company/accession; preserve existing data and report partial failures. Audit the legacy replacing metric importer before any bulk reuse. Schema/data changes require an ExecPlan with migration, preservation, and recovery strategy. Never rewrite migration history or perform destructive database/filesystem/volume operations without explicit user approval.

Record long-lived product/architecture choices in concise [decision records](decisions/). Keep current behavior distinct from future goals and historical verification. Reuse documentation through links.

## Validation proportional to change

| Change | Expected evidence |
|---|---|
| Documentation | Internal targets/anchors resolve, scope review, `git diff --check`. |
| Backend/API | Relevant maintained tests, import/HTTP smoke where affected, backward compatibility. |
| Frontend | Existing relevant tests, lint/build, actual browser checks for changed states, keyboard/focus and responsive checks. |
| Financial metrics | Representative concept/unit/period fixtures, formulas, missing/zero inputs, provenance and fiscal comparison checks. |
| Ingestion/schema | Disposable test databases, first run/rerun/interruption/recovery, migration checks, preservation and before/after counts/fingerprints. |
| Retrieval/AI | Versioned relevance/data-quality cases, abstention negatives, source lineage, prompt-injection checks; real claim audits separately from mocks. |

Use maintained suites under `backend/tests/` and `frontend/tests/`; setup commands and environment prerequisites are in the [README](../README.md#testing-and-current-verification-status). Some legacy root-level backend test scripts access SEC/network services; inspect before running them. Opt-in DB regression assumes its documented fixture/model cache. Broaden testing when the changed scope or a failure justifies it; do not rerun unrelated acceptance for a documentation change.

Capture exact command, working directory, environment assumptions without secrets, passed/failed/skipped results, and limitations. Never claim a browser/API check ran when only code was inspected. Distinguish local database retrieval, provider mocks, failed real SDK attempts, and successful real claim audits. Billable calls require intentional authorization and a recorded budget; failure is not success and unlimited retries are unacceptable.

## Product quality and completion

Maintain the restrained navy/teal identity, accessible labels, focus states, text statuses, responsive layouts, and honest empty/loading/insufficient states. Do not use fake data to improve screenshots.

Before reporting completion, review the diff for scope, secret exposure, generated noise, regressions, and unresolved acceptance failures; run `git diff --check`. Keep application/data behavior unchanged for documentation tasks. Report files, outcome, actual checks, blockers, Git status, and suggested commit. Do not commit or push without explicit request. Portfolio claims must match reproducible evidence.
