# Default-off owned source-pinned notes

Status: active; bounded implementation complete, independent review pending.
Roadmap phase: bounded 7c/15b enabling slice; not full-feature acceptance.

## Objective

Reuse actual offline JWT verification and the existing owned session/artifact
transactions to save one immutable user note per artifact reservation, reopen it
under fresh authorization, and export its exact pinned publication reference.
Two-user isolation, invalidation and unavailable-source disclosure must hold.
This is one critical-path increment toward the requested full 67-feature scope,
with feature/data freeze November 28 and target delivery December 15. It does not
change those dates or count any full requirement as newly accepted.

## Current architecture and context

Verified main at 7adc12a012a95fca09ea250f596570a17180f1ac; origin is
https://github.com/alaniong0118-alt/finlens.git. Index empty. Preserve the existing
frontend/next-env.d.ts change, two untracked backend publication/discovery reports,
and the untracked annual-comparison-export and personal-site plans. SHA256 baseline
of these five paths is recorded outside the repository in the task workspace.

Read AGENTS.md, .agent/PLANS.md, engineering standards, product spec, roadmap,
full-feature requirements (7c/15b), shared contracts and current ownership/reference
code/tests. Local Codex memory was contextual only; current files take precedence.
Authentication and ownership have no configured production instance. The financial
session composition returns None and is outside this slice.

## Constraints

No credentials/private .env, provider/network access, live database, migration
execution, services, frontend, permissions, deployment, staging, commit or push.
Retain existing reference contracts and transaction lifecycle. No new dependencies
or duplicate harness. Leave changes unstaged for independent review.

## Non-goals

Provider login, HTTP/browser delivery, admitted financial calculations, uploads,
source resolution/rights, deletion/memory/watchlists, and completion of 7c/15b.
Do not repeat accepted ownership migration or backup/restore acceptance.

## Implementation stages

1. Add an immutable note payload table after the accepted ownership migration;
   retain artifact reservations as the ownership/quota identity.
2. Add save/reopen/export methods to the dormant ownership service, using the
   existing authenticated transaction and cancellation/commit handling.
3. Extend the maintained offline fake-transaction suite and compile only the new
   migration as SQL; do not execute SQL or the existing database acceptance harness.
4. Self-review and verify protected hashes, index, branch/HEAD and exact diff.

## Decisions

- 2026-11-04: Persist user-authored notes with DatabasePublicationRef pins only.
  The reference is structurally validated, never authority or a verified result.
  Export/reopen always say source availability not checked and source reference
  unverified; never fetch or silently replace a pin. No source excerpts are stored.
- One note per owned artifact reservation; immutable saves replay only identical
  payloads. Existing 100-artifact quota bounds note count without another allocator.
- New additive migration only; recovery is code rollback leaving note rows intact.
  New schema deployment and real persistence/constraints are separately unexecuted.

## Discovered issues

The first ownership test command stopped before tests: Python's Windows
platform.machine() fallback attempted cmd.exe during SQLAlchemy import and the
existing audit guard rejected the subprocess. The maintained test now supplies
inert AMD64 metadata before SQLAlchemy import. No socket/subprocess/database/env
guard was removed or relaxed. Corrected runs passed.

The accepted ownership PostgreSQL harness is intentionally pinned to its accepted
migration chain ending a7c730103001. It was neither changed nor rerun. This new
note migration needs a separate authorized extension of that maintained harness
for actual PostgreSQL/privilege/concurrency acceptance, not a duplicate harness.

The new table enforces artifact existence and owned-session references. Agreement
between the artifact's owner/session and the note's owner/session is checked by
the existing authenticated artifact lookup before the note query. No database
RLS, restricted-role grant, cross-process durability or database immutability
claim follows from these offline tests; note immutability is a service contract.

## Progress

- [x] Verified source, requirements and protected starting state.
- [x] Implement bounded dormant persistence API and additive schema.
- [x] Run focused offline tests and self-review.
- [x] Record final scope, results and limitations.

## Test and validation strategy

Use the existing test_account_auth guards and ownership fake database, with real
ephemeral RSA signatures. Test authenticated create/reserve/save/reopen/export,
fresh service instances over the same fake store, cross-user/missing denial,
revoked session/artifact/account/token, exact pin/body replay and conflicts,
bounded UTF-8 output, cancellation, commit uncertainty and malformed stored data.
Compile new PostgreSQL DDL without loading Alembic env.py or a real database.
These are offline unit/SQL-shape checks, not PostgreSQL/browser acceptance.

## Completion criteria

Focused tests pass, dormant defaults preserved, protected files unchanged, new
table only, no credentials/activation, empty index and changes ready for review.

## Final outcome

Five candidate paths, all unstaged:

- backend/app/research_ownership.py: SavedNote; save_note/reopen_note/export_note;
  bounded UTF-8 user text and existing DatabasePublicationRef round-trip; existing
  transaction/authorization/commit semantics retained. No issuer, token or subject
  is exported. JSON carries schema version 1 and explicit unverified-reference /
  availability-not-checked fields. No fetching, link construction or pin replacement.
- backend/app/models.py: additive ResearchNote only; old models unchanged.
- backend/migrations/versions/b8d741104001_add_owned_research_notes.py: creates only
  research_notes after a7c730103001; never executed, forward-only recovery guard.
- backend/tests/test_research_ownership.py: extends the existing fake-transaction
  harness; 17 new note behavior tests and two new SQL/DDL tests, retaining 29 prior
  tests. No new persistence engine or separate harness.
- This ExecPlan, retained active for independent review and integration handoff.

Actual commands (repository root, established Python 3.14 interpreter):

    & 'D:\Projects\finlens-foundation\backend\.venv\Scripts\python.exe' -I -S -B backend/tests/test_research_ownership.py

Final result: 48 tests passed, zero failures/errors/skips. Covers actual ephemeral
RSA JWT verification plus fake-store create/reserve/save/reopen/export, both users'
positive paths and cross-user denial, exact pins including zero versions,
immutable replay/conflicts, missing/revoked/stale/disabled/invalidated access,
UTF-8/shape/output limits, malformed saved data, cancellation before/after commit,
indeterminate outcomes/reconciliation, expiry and cleanup failure. SQL assertions
compile owner/session/artifact filters and FOR UPDATE. Mock Alembic Operations
compile note DDL and compare it to ORM, with no database/environment loaded.

    & 'D:\Projects\finlens-foundation\backend\.venv\Scripts\python.exe' -I -S -B backend/tests/test_account_auth.py

Result: 16 tests passed, zero failures/errors/skips. Total focused evidence:
64 tests. Intermediate ownership runs passed 44 and then 48 tests; the final run
followed the last early-size-bound refinement. The first pre-test platform failure
above is retained as failed historical evidence, not counted as a passing run.

Read-only AST verification confirms every pre-existing model and ownership class
method (including _run and its cleanup/commit ordering) is unchanged. Only the
existing _metadata function gains note detachment. Five-file Python syntax / final
newline / trailing-whitespace checks and git diff --check pass. Branch/HEAD,
empty index, origin and all five protected hashes remain unchanged. No unexpected
worktree writer or interface conflict was observed. Git emitted its existing
LF/CRLF warnings; no configuration was changed.

Limitations: persistence is implemented for PostgreSQL but tested with the
maintained fake store and fresh service instances only, not a real process restart
or database. Real PostgreSQL constraints/roles/races, note schema deployment,
provider identity/login, HTTP/browser flows and source authority/availability/
rights remain unexecuted. The financial-session composition still returns None.
No provider, network, credentials, live DB, migrations, services, permissions,
frontend changes, deployment or Git delivery occurred. Accepted ownership
migration and qualified backup/restore were not repeated.

Suggested eventual commit: feat(research): add dormant owned source-pinned notes

Next safe action: independent review of these five paths, then commission the
new-table PostgreSQL acceptance and provider/HTTP composition as bounded tasks.
