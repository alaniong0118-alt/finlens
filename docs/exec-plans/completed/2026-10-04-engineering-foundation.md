# Long-horizon engineering documentation

Status: completed
Roadmap phase: scoped planning foundation; no feature milestone authorized

## Objective

Establish maintainable roadmap, product/source/engineering contracts, and an ExecPlan lifecycle, while preserving existing documentation and application behavior.

## Current architecture and context

Read [AGENTS.md](../../../AGENTS.md) first. Existing [architecture](../../architecture.md), [technical challenges](../../technical-challenges.md), and [README](../../../README.md) describe the implemented system. The frontend is currently a single-filing question workspace; financial and search/context APIs already work independently of generation.

Starting HEAD: `641febb` (UI polish). Starting Git status: only the user-provided root `AGENTS.md` is untracked. Read-only database/API inspection on 2026-10-04 found 10 companies, 3,251 financial facts, 37 chunks, 37 embeddings, and one Ready company (AAPL). Recorded real LLM acceptance remains incomplete because of exhausted credits; no provider call is needed for this task.

## Constraints

Documentation only; no code, dependencies, schema, data, secret exposure, commit, or push. Reuse existing architecture/setup/evaluation records. Follow the [ExecPlan standard](../../../.agent/PLANS.md).

## Non-goals

Company expansion, SEC indexing, metric implementation, UI changes, and paid AI evaluation.

## Implementation stages

1. Inspect relevant documentation, code, tests, Git, and read-only data/API state.
2. Define roadmap phases, product boundaries, source policy, engineering rules, and optional-AI ADR.
3. Connect documentation from the README; validate internal references and scope.
4. Record results and move this plan to completed; preserve an empty active directory.

## Decisions

- 2026-10-04: Keep architecture/setup details in their existing documents; new documents define direction and contracts, with links instead of repeated implementation descriptions.
- 2026-10-04: Distinguish existing no-LLM APIs from the planned complete Research Mode frontend. Catalog breadth, universal filing coverage, and advanced AI are future work.

## Discovered issues

- Root instructions reference planning documents that do not yet exist. This task creates them.
- Existing verification documents are historical records with earlier test totals and ports; retain them as dated evidence, not a current acceptance claim.
- The legacy financial importer replaces a company's metric rows. Future bulk ingestion must address preservation and resumability before reuse; it is not executed here.

## Progress

- [x] 2026-10-04: Repository instructions, existing docs, relevant implementation/tests, Git baseline, and read-only DB/API inspected.
- [x] 2026-10-04: Created roadmap, product/source/engineering contracts, ExecPlan standard, optional-AI ADR, and README navigation; existing architecture preserved.
- [x] 2026-10-04: Validated internal links/anchors, explicit repository references, documentation-only scope, and whitespace; moved this plan to completed. No feature work is active.

## Test and validation strategy

Validate internal Markdown targets and anchors plus documented local file/directory references. Run `git diff --check`, inspect Git status/diff, and confirm only documentation changed. Application tests/build are unnecessary for this documentation-only task and will not be reported as run. No SEC/model/provider calls or database writes.

## Completion criteria

Requested files/directories exist; current and planned behavior are distinct; all requested roadmap goals and ExecPlan fields are covered; references resolve; existing architecture is preserved; whitespace/scope checks pass.

## Final outcome

Created the roadmap, ExecPlan policy, product specification, engineering standards, source policy, and ADR 003; linked them from the README. Existing architecture and technical-challenge documents are unchanged. Both plan directories are retained with placeholders.

Validation ran from the repository root using the existing backend venv Python: 14 Markdown documents, 57 internal links, 6 anchors, and 15 explicit repository references passed. `git diff --check` passed; additional no-index checks covered all nine newly created documentation files and found no whitespace errors. Scope review found no application, dependency, migration, or data changes. The API and database baseline was read only; no SEC, embedding, or provider operation ran. Application tests/build were not rerun for documentation.

Git outcome: README modified; new planning documents and plan directories untracked; the pre-existing untracked AGENTS.md was preserved. No commit or push. Suggested commit: `Document FinLens roadmap and agent engineering workflow`.
