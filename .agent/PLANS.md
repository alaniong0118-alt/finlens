# ExecPlan standard

An ExecPlan is a living implementation record that another agent can resume without chat history. Follow [repository instructions](../AGENTS.md), the [roadmap](../ROADMAP.md), and [engineering standards](../docs/engineering-standards.md).

## When a plan is required

Create or update an active plan before implementation for complex, risky, long-running, or multi-stage work. This includes multi-company SEC indexing, financial metric normalization, schema changes, major retrieval changes, multi-filing analysis, data migrations, and significant architecture refactors. A small, reversible correction does not need a plan unless it introduces one of these risks.

Keep the plan proportional to the task. A plan does not authorize a later roadmap phase, destructive operations, paid API calls, or a commit/push.

## Location and lifecycle

- Active plans: [docs/exec-plans/active/](../docs/exec-plans/active/).
- Completed plans: [docs/exec-plans/completed/](../docs/exec-plans/completed/).
- Name: `YYYY-MM-DD-short-task-name.md`; use a stable descriptive name, not a chat ID.
- Before resuming, inspect Git status, relevant code/tests, and current data or application state. Reconcile them with the plan; observed state takes precedence over stale notes.
- Update progress after each meaningful stage and record decisions or discoveries when they affect subsequent work. Include exact commands, working directories, results, and limitations needed to reproduce verification; never include secrets or private environment values.
- Keep blocked or interrupted work in active, with the blocker, preserved state, and next safe action. Do not label unfinished work complete.
- Move a plan to completed only after its completion criteria are satisfied, validation and self-review are recorded, and its final outcome is written. Fix relative links after moving it. Completion of a plan does not imply completion of the whole product.

## Required content

Use these headings, or an equally clear equivalent. Separate planned validation from checks actually run.

```markdown
# Task title

Status: active | blocked | completed
Roadmap phase: phase name, or a scoped enabling task

## Objective
User-visible or engineering outcome, with observable acceptance criteria.

## Current architecture and context
Relevant modules, existing behavior, data baseline, and links to authoritative docs.
Record the starting Git state and existing changes that must be preserved.

## Constraints
Scope, compatibility, data/secret safety, resource budgets, and required approvals.

## Non-goals
Explicit exclusions, including later roadmap work.

## Implementation stages
Small ordered stages, their dependencies, and any recovery/rollback procedure.

## Decisions
Date, decision, reason, and alternatives that materially affected the choice.
Link durable architecture decisions instead of duplicating them.

## Discovered issues
Evidence, impact, resolution or remaining blocker; do not silently expand scope.

## Progress
Dated checkboxes for completed and remaining stages; note the next safe action.

## Test and validation strategy
Targeted tests and observable checks, isolation, before/after data checks where
applicable, and relevant regression. Record actual results as stages finish.

## Completion criteria
Explicit gates for behavior, compatibility, evidence, validation, and review.

## Final outcome
Changes, checks actually run, limitations, Git status, and suggested commit.
Leave pending until the criteria are satisfied.
```

For ingestion or migrations, additionally record affected identities, transaction boundaries, resumability, failure isolation, preservation checks, and recovery steps. For financial metrics, record units, period semantics, formulas, provenance, and representative edge cases. For retrieval or AI work, record evaluation scope, source lineage, abstention checks, and whether provider output is real or mocked.
