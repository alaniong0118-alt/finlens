# History-contract portability and minimal CI dependencies

Status: active — clean Windows validation passed; Ubuntu execution awaits reviewed integration
Roadmap phase: bounded maintained contract-test reproducibility

## Objective, authority and scope

Run the maintained 44-case backend history matrix and pass its one fresh export
through the frontend transport/validators on normal Windows and Linux CPython.
Keep isolation, IO/model guards, deadlines and guaranteed cleanup.

Baseline: `f64ac4e3e7cc03a97631eb1c2ae626be65afbd1f`. Reviewed offline patch:
`b414bc3deb50abee6f82b60650bff125103c80fdec8ca8c7ddb1e4a655da1aef`, preserved
in `D:\Projects\finlens-history-portability-offline-20261102-r1`. This continuation
uses `D:\Projects\finlens-history-ci-approved-20261102-r1`; its delivery manifest
records exact source, archive, patch, command and evidence hashes. Root AGENTS.md,
.agent/PLANS.md and engineering standards apply; no nested instructions or
`.agents/skills` exist in the committed tree.

The user approved bounded official-source retrieval and CI provisioning at
2026-11-02 23:15 UTC (`Sentinel_dcc8b42a00bc8191a31a5f3fd2d29d85`). The reviewed
runner, bridge, path tests and package command remain byte-identical. This
continuation adds two locks, backend path triggers and three steps in the existing
Chromium job, and updates this plan. No production, shared guard-tail, jobs,
services, permissions, deployment or data changes. The sole integrator handles
live integration and Git; live source/index/refs and five historical exceptions
remain untouched. All earlier artifacts and results remain preserved.

## Reviewed implementation

- Only checkout `backend/.venv/Scripts/python.exe` (Windows) or
  `backend/.venv/bin/python` (Linux), and its normal `Lib/site-packages` or
  `lib/python<actual-major.minor>/site-packages`. No ambient fallback; other
  implementations, free-threaded/unsupported layouts and missing paths fail.
- Retain `-I -S -B`; never process `site`/`.pth` or ambient packages. The
  runner's entire existing environment/guard/application-import tail is unchanged.
- One child selects the full history file, including its export case.
  `npm run test:history-contract` consumes its fresh 43-response artifact and
  reports the backend summary before 15 frontend assertions/controls. No second
  capture subprocess. Owned temporary captures are removed on all outcomes;
  explicitly caller-owned evidence survives. Existing deadlines remain.
- Path controls simulate Linux strings on Windows; they do not establish Linux
  interpreter, wheel, ABI or Ubuntu acceptance.

## Official-source verification and locks

Normal CPython 3.14.7 x64 and pip 26.2.1 were verified available from official
sources; no proposed version was substituted. The existing Windows executable
and DLL match the downloaded Python.org runtime archive bytes; valid Python
Software Foundation signatures were checked. No global reinstall occurred.

- [Python release](https://www.python.org/downloads/release/python-3147/) and
  [Windows manifest](https://www.python.org/ftp/python/3.14.7/windows-3.14.7.json):
  downloaded normal x64 ZIP, 36,747,122 bytes, SHA256
  `ac1a727a71738e11de80b76e975f9b8a258aea6412bfc31696b929d59c6aafd0`.
- [setup-python](https://github.com/actions/setup-python/tree/ece7cb06caefa5fff74198d8649806c4678c61a1):
  immutable `ece7cb06caefa5fff74198d8649806c4678c61a1` (v6, Node 24,
  verified commit signature). Official python-versions manifest commit
  `160ca1e232997f36def6bb6e857f628222bef58a` lists stable normal 3.14.7 on
  Ubuntu 24.04 x64. Its release API advertises runtime archive SHA256
  `76d5ddab6d2dd89a39c06220f6efeda486a48ed481eae97bfc596c74ac3623db`,
  109,870,670 bytes. This Linux runtime archive was not downloaded or executed.
- `backend/requirements-history-bootstrap.lock` separately pins the official
  universal pip wheel. `backend/requirements-history-contract.lock` closes the
  actual import roots: beautifulsoup4, fastapi, httpx, numpy, openai, pgvector,
  psycopg[binary], pydantic, pytest, python-dotenv and sqlalchemy. NumPy and the
  OpenAI SDK are current eager-import prerequisites; API/model use stays guarded.
- Actual wheel METADATA establishes all transitive requirements and markers:
  35 runtime distributions on Windows, 33 on Ubuntu; colorama/tzdata are
  Windows-only. Official PyPI JSON verifies every pinned version, Python
  requirement, non-yanked status and compatible archive. Five native packages
  have separate Windows/Linux hashes. All 41 unique wheels, including pip,
  totaling 57,666,783 bytes, were downloaded and matched official SHA256/length.
  Windows hashes are not used to certify Linux artifacts.
- The lock excludes sentence-transformers, torch, transformers and the ML closure.
  Missing versions/wheels, incompatible tags and hash mismatches fail; no floating
  resolution or source builds. No full requirements-dev installation.
- E: had ample free capacity, but creation of a unique child under the existing
  `E:\Backups\FinLens` failed with filesystem Access Denied. No ACL changes,
  deletion or retry. D: had 183,208,456,192 free bytes and was the authorized
  fallback. Existing backups were untouched.

## Reproducibility and actual commands

The committed workflow contains the complete standalone Ubuntu provisioning
recipe; no scratch-only launcher is required. Its existing Chromium job selects
normal 3.14.7 x64, fetches pip's verified official wheel via isolated stdlib, creates
`backend/.venv` without pip, and bootstraps from the verified wheel under
`-I -S -B` using supported module invocation. It then downloads binary-only
locked dependencies from explicit PyPI and installs offline from that wheel
directory. Pip uses isolated mode, disabled host configuration, no cache,
`--require-hashes --only-binary=:all: --no-compile`, then `pip check`.
The existing synthetic-capture job and authorization are unchanged.

After dependency provisioning and frontend `npm ci`, maintained commands need
only committed code and locks, not an evidence helper:

```powershell
# From frontend, Windows or Ubuntu; package command selects its fixed venv.
npm run test:history-contract
# Additional Windows path controls, from backend.
.\.venv\Scripts\python.exe -I -S -B tests/run_financial_insights.py tests/test_financial_runner_paths.py
```

```bash
# Additional Ubuntu path controls, from backend; not yet executed on Ubuntu.
./.venv/bin/python -I -S -B tests/run_financial_insights.py tests/test_financial_runner_paths.py
```

Actual clean Windows preparation used the verified base interpreter's
`-I -S -B -m venv --without-pip`. An archived diagnostic driver installed only
the verified local wheels under socket/model guards, a cleared host environment
and disabled pip configuration. Bootstrap, runtime install and pip check receipts
all report exit 0 and zero blocked attempts. This driver is evidence, not a
dependency of the maintained command or committed CI recipe.

The first diagnostic bootstrap used incorrect script-style runpy arguments and
failed before installing packages. The next stage was started too early and
stopped because pip was absent. Both failures are preserved. Matching official
ensurepip's supported `runpy.run_module(..., alter_sys=True)` invocation corrected
the launcher; no pip safety check or permission was bypassed.

## Progress and evidence

- [x] Preserve baseline/reviewed patch and verify identities read-only.
- [x] Verify official runtime/action/PyPI metadata and compatible wheel bytes.
- [x] Audit both closures and write binary-only hash-pinned locks.
- [x] Clean Windows install: exact 35 runtime packages plus pip; pip check passes.
- [x] `npm --prefix frontend run test:history-contract`: backend **44 passed**,
  frontend **15 passed**, zero failures/skips. One existing Starlette/httpx
  deprecation warning. Fresh backend artifact generated and consumed.
- [x] Additional guarded backend path controls: **12 passed**, zero skips,
  including poisoned PYTHONPATH and nonexecuting `.pth` controls.
- [x] Literal workflow Python bootstrap: five Windows offline controls passed
  (valid wheel, size/hash mismatch, redirect and wrong lock); no Linux claim.
- [ ] Independent review, sole-integrator integration and authorized GitHub CI.
- [ ] Actual Ubuntu provisioning/import/ABI/full matrix acceptance.

Exact logs: `evidence/clean-windows-history-contract.log`,
`evidence/clean-windows-paths.log`, `evidence/pip-bootstrap.log`,
`evidence/pip-runtime.log`, `evidence/pip-check.log`. Adjacent JSON records
installed packages, dependency edges, official URLs, archive sizes/hashes and
runtime identities; the delivery manifest hashes them. Frontend dependencies
reused existing installed node_modules through an owned scratch junction; this
was a clean Python dependency test, not a fresh npm install or browser run.

## Limits and completion

Linux archive bytes/metadata are verified; actual Ubuntu execution remains
unverified until authorized CI after review. Fake read-only sessions prove
SQLAlchemy query construction and the real FastAPI handler/serialization/cleanup
contract, not physical ORM hydration or transactions. Schema readiness and the
empty authorization-evidence adapter are stubbed and outside coverage. No live
DB, provider, model, listening service, browser, Docker, credentials or security
changes occurred. No broad mismatched suite rerun or historical cleanup occurred.

Candidate completion requires clean Windows results, exact closure, preserved
guards/reviewed code/protected files, strict patch application and source-byte
verification, and explicit Linux limitations. The delivery manifest records
these checks and exact identities. No live integration, staging, commit or push.
The preserved initial archive uses Windows CRLF export. Final delivery patches
use canonical Git blob line endings; both raw reviewed hashes and canonical
delivery hashes are recorded. This changes no test logic or dependency pins.
Suggested commit: `test(history): pin minimal dependencies for portable CI contract`.
