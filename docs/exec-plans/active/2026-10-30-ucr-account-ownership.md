# Dormant account-backed research ownership

Status: active; bounded implementation authorized, independent review pending.
Roadmap phase: UCR/15a-15b prerequisite, not UCR completion.

## Objective

Implement the unwired token -> account -> research session -> artifact ownership
metadata -> revocation chain. It supplies no login UI, HTTP capability, document
storage, source rights, custody, financial admission or calculation eligibility.

## Current architecture and context

Starting branch main; HEAD 011e54ec51e1ea5e45dbe3fd29681ca3270e5ac0; index empty.
Static migration head f94c6f41e0cb follows d7b834408ba8. No migration entrypoint ran.
Read root rules, ExecPlan standard, roadmap, engineering standards, C7-C9 and U3/U4.
Existing engine/facade and C5 review evidence are preserved, not re-reviewed.

Protected SHA256 baselines (all matched before edits):

- frontend/next-env.d.ts: F4E8976C19FC926644D72610BF1058BD6BF52ADD97E46A02BC0B912A751625C0
- backend/reports/canary-aapl_guarded_live_20261010_111844_3580610-publication.json: A783517D2875E39DF4C831C410265D0126FBF6A9D3DDBA1103F7BD61B057844C
- backend/reports/refresh-discovery-aapl_sec_discovery_20261010_002323_0671678.json: F8DF96C8890C0ECE1E1701B25BC5C43B879C359ECEB96ACB451A2A0DAA58BF7C

## Constraints

Only account_auth.py, research_ownership.py, models.py, the new
a7c730103001_add_research_ownership.py migration, requirements.txt, the two new
test_account_auth.py/test_research_ownership.py tests, shared-research-contracts.md
and this plan may change. All paths are under backend/app, backend/migrations/versions,
backend/tests or docs as specified by the coordinator. Never inspect/hash backend/.env.
No database connections (including SQLite), migration execution, service startup,
provider/SEC requests, runtime configuration, routes, Git writes or extra packages.

## Non-goals

Production principals, provider setup, HTTP delivery, native custody, real database
enforcement, financial observations, billing/entitlements and completed UCR.

## Implementation stages

1. Accept exact dependencies and preserve baseline inventory.
2. Implement immutable single-provider verification, bounded key lifecycle and clocks.
3. Add ownership models/migration and explicit transactional service.
4. Exercise real offline signatures, fake-session lifecycle and isolated DDL checks.
5. Self-review, scope/preservation checks and coordinator handoff without Git delivery.

## Decisions

- 2026-10-30: One RFC 9068 RS256 interactive-client profile; no issuer selected.
  Default configuration is unavailable. Request callers cannot supply principals.
- Use account -> session -> artifact locks and READ COMMITTED transactions owned
  by the service. Allocation replay must still authenticate and authorize live state.
- Mark COMMIT-issued before invoking the driver. A subsequent failure is indeterminate;
  confirmed commits persist even if cancellation/cleanup prevents return. No automatic retry.
- Database wall time is cross-checked against verifier time within 30 seconds.
  Both clocks check token time; invalidation uses max(old cutoff, ceil(DB time)+30).
  Never apply clock allowance to the stored cutoff comparison.
- Additive schema only; refuse automatic downgrade. Code rollback leaves data intact.
- All new identity and opaque-key columns explicitly use C collation so database
  locale cannot merge different issuers, subjects, request keys or object keys.
- Do not author placeholder/skipped real-PostgreSQL tests. Their concrete acceptance
  scenarios remain listed below for a separately authorized database task.

## Discovered issues

Initial explicit-path metadata found all four target packages absent, confirming
the previous result. Dependency-only preparation was separately authorized.

Initial test development caught three fixture/harness issues, all corrected within
the approved test files: PyJWT removes redundant b64=true during encoding, so exact
prohibited headers now use real RSA signatures over explicit bytes; Windows
SQLAlchemy platform discovery called gethostname, now replaced with inert test
metadata while all real socket/DNS/connection events remain blocked; a regression
fixture accidentally rewound monotonic time as well as wall time, now corrected to
model only a small wall adjustment. The prior failed commands remain historical
failures, not passing evidence. Self-review also made UTF-8 shape checks reject
surrogates cleanly and made collation explicit in both ORM and migration.

Final inventory review found pre-existing manifest drift: pgvector 0.5.0 satisfies
the declared >=0.3,<1.0 range; only sentence-transformers 6.1.0 is outside >=3.4,<6.0.
Both versions are present in the recorded 71-distribution baseline and unchanged.
Pip check validates installed distributions' dependencies, not requirements.txt
compliance. No dependency remediation was performed. This does not
invalidate the exact four-package delta, but broader reproducibility/runtime claims
remain unaccepted; coordinator should disposition this separately.

## Progress

- [x] Expected HEAD, empty index, exact historical exceptions and hashes verified.
- [x] Dependency gate passed on established Python 3.14.7.
- [x] Implement verifier and ownership chain, metadata-only schema and documentation.
- [x] Focused offline validation and source self-review.
- [x] Final scope/preservation checks and handoff recorded below.

## Test and validation strategy

Use isolated Python -I -S -B and guards installed before application imports.
No site initialization, application startup, dotenv or database bootstrap.
Use ephemeral in-memory RSA test keys; never persist/log tokens or private keys.
Fake repositories/sessions establish unit behavior only. Mock Alembic Operations
compile PostgreSQL DDL without loading env.py or connecting. Real PostgreSQL,
provider, Windows, HTTP and end-to-end gates stay unexecuted.

### Dependency evidence actually run

Explicit importlib.metadata.distributions path:
D:/Projects/finlens-foundation/backend/.venv/Lib/site-packages.
Before: 71 distributions; all four targets absent. Baseline pip check exit 0.
Baseline inventory (distribution metadata only):

Jinja2==3.1.6, Mako==1.4.3, MarkupSafe==3.0.3, PyYAML==6.0.3, Pygments==2.21.0, SQLAlchemy==2.1.2, alembic==1.20.0, annotated-doc==0.0.5, annotated-types==0.8.0, anyio==4.15.1, beautifulsoup4==4.15.0, certifi==2026.7.22, click==8.5.0, cloudpickle==3.1.2, colorama==0.4.6, distro==1.9.0, fastapi==0.142.2, filelock==4.0.9, fsspec==2026.9.0, h11==0.16.0, hf-xet==1.6.0, httpcore==1.0.9, httptools==0.8.0, httpx==0.28.1, huggingface_hub==1.33.0, idna==3.20, iniconfig==2.3.0, jiter==0.17.0, joblib==1.6.0, markdown-it-py==4.2.0, mdurl==0.1.2, mpmath==1.3.0, narwhals==2.26.0, networkx==3.7, numpy==2.5.3, openai==2.54.0, opentelemetry-api==1.45.0, packaging==26.3, pgvector==0.5.0, pip==26.2.1, pluggy==1.6.0, psycopg==3.3.6, psycopg-binary==3.3.6, pydantic==2.13.5, pydantic_core==2.46.5, pytest==9.1.1, python-dotenv==1.2.4, regex==2026.9.29, rich==15.0.0, safetensors==0.8.0, scikit-learn==1.9.1, scipy==1.18.1, sentence-transformers==6.1.0, setuptools==84.0.0, shellingham==1.5.4, sniffio==1.3.1, soupsieve==2.10, starlette==1.7.0, sympy==1.14.0, threadpoolctl==3.7.0, tokenizers==0.23.2, torch==2.14.1, tqdm==4.70.1, transformers==5.18.0, typer==0.27.2, typing-inspection==0.4.4, typing_extensions==4.16.0, tzdata==2026.4, uvicorn==0.54.0, watchfiles==1.3.0, websockets==17.1

Pip isolated configuration had no extra source, trusted-host, redirected destination
or no-index option. Executable/prefix/purelib resolve to the existing backend/.venv.

Exact authorized installation command (repository root; exit 0):

    & 'D:\Projects\finlens-foundation\backend\.venv\Scripts\python.exe' -I -B -m pip --isolated --require-virtualenv install --only-binary=:all: --no-deps --no-compile --no-cache-dir --disable-pip-version-check --no-input --index-url https://pypi.org/simple 'PyJWT[crypto]==2.15.1' 'cryptography==50.0.2' 'cffi==2.1.1' 'pycparser==3.12'

After: exactly PyJWT 2.15.1, cryptography 50.0.2, cffi 2.1.1 and pycparser 3.12
added; 75 distributions. No removals or other version changes. Post-install pip
check exit 0. Both pip checks used the established interpreter with
-I -B -m pip --isolated --disable-pip-version-check check.
Guarded -I -S -B imports and in-memory RSA-2048 RS256 sign/verify passed, with
network, app/dotenv/database imports and private environment reads blocked.
No private key/token file was created. This is not application/runtime acceptance.

### Implementation evidence actually run

Working directory for all commands: D:/Projects/finlens-foundation.

    & 'D:\Projects\finlens-foundation\backend\.venv\Scripts\python.exe' -I -S -B backend/tests/test_account_auth.py

Final corrected code: exit 0; 16 tests passed, zero failures/skips. Actual ephemeral
RSA-2048 signatures verify. Negative profiles, key changes/expiry, clock/claim
bounds, malformed JSON, exact token limit, key limits and forbidden effects pass.

    & 'D:\Projects\finlens-foundation\backend\.venv\Scripts\python.exe' -I -S -B backend/tests/test_research_ownership.py

Final corrected code: exit 0; 29 tests passed, zero failures/skips. Twenty-five
ownership/fake-transaction tests and four isolated schema/SQL checks cover the
chain, two-owner denial, replay, quotas, revocation/invalidation, both token clocks,
pre-dispatch cancellation, confirmed persistence despite withheld delivery,
indeterminate COMMIT, cleanup, exact collation and mock PostgreSQL DDL parity.
No Alembic environment or real database was loaded or used.

    & 'D:\Projects\finlens-foundation\backend\.venv\Scripts\python.exe' -I -S -B backend/tests/test_research_contracts.py

Relevant unchanged reference regression: exit 0; 49 tests and 609 subtests passed,
zero failures/skips. C1 is consumed by the new service; no C5 acceptance group or
completed independent review was repeated. C1 execution preceded the final
UTF-8/collation self-review refinements, which do not edit the C1 module or tests;
both new suites were rerun successfully after those refinements.

Initial authentication run: 15 tests, one failed fixture case. First ownership
run aborted during guarded platform discovery before test execution. Next run:
24 tests, one failed clock fixture. Subsequent focused runs passed. No security
guard was relaxed to permit a real connection, environment load or startup.

### Explicitly unexecuted acceptance

- Native Windows key/configuration protection, custody, process memory/termination,
  hard timeouts and synchronized deployed clocks.
- Real PostgreSQL migration/schema, unique/composite-FK enforcement, concurrent
  first login, competing last-quota allocation, idempotent allocation races,
  both revocation orderings, rollback/close failures and commit reconciliation.
  Fake-session logs and compiled SQL prove neither locks nor database isolation.
- Real provider/token profile, configured interactive-client grants, JWKS TLS
  capture/rotation/renewal/emergency removal, login, logout and refresh revocation.
- HTTP route admission, authentication error mapping, last-delivery access checks,
  browser/accessibility and a usable persistent research workspace.
- Source rights/custody, verified financial admission, external engine references,
  absent-company no-insertion end-to-end research, services and deployment.

None is counted as a skip/pass or completed product requirement. The next connected
integration is separately scoped session POST/GET after provider/PostgreSQL and
privilege gates; financial admission remains an independent prerequisite.

## Completion criteria

Exactly nine candidate files; offline contracts pass; index/HEAD/protected files
preserved. Document all excluded gates, self-review findings and exact commands.
Stop for coordinator review; no deployment or independent approval claim.

## Final outcome

The nine-file dormant implementation is ready for coordinator-directed independent
review. No routes, real issuer/client,
public-key configuration, account seed, provider connection, database, services or
financial admission were activated. Dependencies alone were installed as expressly
authorized. No implementation scope expansion; explicit C collation and sanitized
UTF-8 rejection are conservative implementation details within the accepted scope.
The active plan is retained at its whitelisted path; it is not release acceptance.

Final read-only checks require the same HEAD, an empty index and exactly the nine
candidate paths plus the three protected exceptions. All protected hashes match.
AST comparison confirms every pre-existing model/index node is unchanged apart
from additive SQLAlchemy imports. The nine-file scan parses Python without imports
and checks whitespace/final newlines including untracked files. It found one extra
blank EOF line in account_auth.py, removed without a semantic change. Scoped Git
diff --check and the final nine-file scan pass after this documentation update.
Git's existing LF/CRLF warnings were observed; no Git configuration was changed.
There is no staged change, commit, push, branch change or completed UCR claim.

Suggested eventual commit, only after separate authorization:
feat(research): add dormant account-backed ownership boundary
