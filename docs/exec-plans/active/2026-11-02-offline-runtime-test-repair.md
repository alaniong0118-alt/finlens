# Focused offline runtime test repair

Status: active — documentation-only R2 recipe passed fresh-copy verification; integration pending
Roadmap phase: maintained-test confidence after requirement16c

## Objective and context

Repair test setup for the 27 failures preserved during the earlier overbroad
financial-runner selection, without changing production contracts or shared
runners. Baseline is `5b270633f9aa3bde3c9e45fc7426484c16975bdd`, captured with
read-only Git archive after the history-contract delivery became committed.
R2 scratch: `D:\Projects\finlens-runtime-test-repair-repro-r2-20261102`.
Original R1 artifacts remain at `D:\Projects\finlens-runtime-test-repair-20261102-r1`.
Both reviewed test files are byte-for-byte unchanged in this revision.

Root AGENTS.md, .agent/PLANS.md and engineering standards govern this work.
No nested AGENTS.md or `.agents/skills` exists in this committed tree. The live
checkout's five historical exceptions remain protected; no live source/index/refs
writes, commit or push are authorized here. Original failure logs, first contract
package and R2 package/evidence remain preserved in their previous scratch roots.

## Scope, decisions and non-goals

- Two existing test files and this plan only; no production, shared-runner,
  dependency, schema or policy changes. No skips or relaxed response assertions.
- Use the existing Increment 2 guard for 21 encoder cases. The financial runner
  intentionally forbids `_get_model`/`_load_model` and cannot exercise them.
  Intended constructors and hub cache lookup are fake modules; the real encoder
  control flow remains exercised. The four programming-error cases now assert
  exact injected exception identity and one exact mocked constructor invocation,
  preventing a runner AssertionError from masquerading as the intended failure.
- Six existing route parameters get valid canonical pin/selector/query shapes
  with no GET body. Tone uses a synthetic valid accession and `chunk_0000`.
  Quarter/coverage select `InsightsSessionLocal`; other routes use
  `HttpSessionLocal`. The other factory bombs. Preserve 503 DATABASE_BUSY, one
  intended factory call and absence of an unverified response-version header.
- Coverage wrapper forwards explicit pin 0 or 7 to its existing helper. Fake
  sessions cover query construction and orchestration, not physical ORM
  hydration, PostgreSQL isolation or physical connection cleanup.
- No live DB, network/provider/model access, service, browser, Docker, downloads,
  credentials or security-setting changes. Windows installed interpreter and
  existing `.venv/Lib/site-packages` only; no POSIX acceptance claim.

## Implementation and progress

- [x] Capture immutable committed baseline without Git writes or integrator locks.
- [x] Correct constructor identity/call assertions, route requests/factories and
  parameterized coverage wrapper.
- [x] Inspect both existing runners and selected fake-module/session fixtures.
- [x] Run exactly 21 encoder, six route and two wrapper cases in guarded fresh children.
- [x] Original R1 restoration/protection checks and 29-case review passed.
- [x] Embed the complete copyable guarded recipe and exact targets in this plan.
- [x] Verify the complete recipe in a fresh baseline-plus-candidate copy without the original launcher; preserve and repackage exact hashes.

## Validation instructions and limits

Prerequisites: Windows PowerShell, the installed trusted `backend/.venv` and
project dependencies described in the README. No installation, downloads or
credentials are part of this recipe. Start in the checkout's `backend/` directory
and copy the entire following block into PowerShell. It creates its own bootstrap
and receipts in a new owned temporary directory; no pre-existing `evidence/`
folder or scratch launcher is needed. Keep that directory for review, including
after failure. The checkout's two committed guarded runners remain unchanged.

The complete bootstrap below contains the exact targets, dependency isolation,
dotenv/model-import/DNS guards, and post-run factory/profile/cache/module checks.
It retains the original runners' physical DB/socket guards. Temporary code is a
fixed three-phase verification recipe, not a new framework or project runner.

```powershell
$runDir = Join-Path ([System.IO.Path]::GetTempPath()) ('finlens-runtime-recipe-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $runDir | Out-Null
$bootstrap = Join-Path $runDir 'guarded-focus.py'
@'
"""Fixed offline 21/6/2 recipe using committed runners and fake dependencies."""
import builtins
import importlib.abc
import io
import json
import os
from pathlib import Path
import runpy
import socket
import sys

ROOT = Path.cwd().resolve()
assert sys.platform == "win32", "This recipe supports the Windows venv layout only"
assert (ROOT / ".venv/Lib/site-packages").is_dir()
assert (ROOT / "tests/run_dep01a2_increment2_offline.py").is_file()
sys.path[:0] = [str(ROOT / ".venv/Lib/site-packages"), str(ROOT), str(ROOT / "tests")]
safe_env = {key: os.environ[key] for key in ("SystemRoot", "WINDIR", "PATH", "TEMP", "TMP", "COMSPEC", "PATHEXT") if key in os.environ}
os.environ.clear()
os.environ.update(safe_env, FINLENS_FINANCIAL_ONLY="0", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", PYTHON_DOTENV_DISABLED="1")
blocked = []


def reject(label):
    blocked.append(label)
    raise AssertionError("Unexpected IO/import: " + label)


def protect(original):
    def guarded(path, *args, **kwargs):
        if isinstance(path, (str, bytes, os.PathLike)):
            name = os.fsdecode(os.fspath(path)).replace("\\", "/").rsplit("/", 1)[-1]
            if name == ".env" or name.startswith(".env."):
                reject("dotenv artifact")
        return original(path, *args, **kwargs)
    return guarded


builtins.open, io.open, os.open = map(protect, (builtins.open, io.open, os.open))


class NoRealModels(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in {"torch", "sentence_transformers", "transformers", "tensorflow", "huggingface_hub"}:
            reject(fullname)


sys.meta_path.insert(0, NoRealModels())
socket.getaddrinfo = lambda *a, **k: reject("DNS")
import psycopg
psycopg.AsyncConnection.connect = classmethod(lambda *a, **k: reject("async physical DB"))

runtime = "tests/test_http_database_runtime.py::"
policy = "tests/test_financial_only_policy.py::"
targets = {
    "encoder": [runtime+name for name in (
        "test_narrow_encoder_dependency_failures", "test_encoder_programming_errors_are_not_outages",
        "test_missing_cache_does_not_construct_or_download", "test_encoder_local_only_and_development_constructor_compatibility",
        "test_incompatible_model_is_explicit_dependency_failure")]
        + [policy+"test_encoder_guard_rejects_before_an_existing_cache_hit"],
    "routes": [runtime+"test_every_http_database_path_uses_bounded_factory["+profile+"-GET-"+path+"]"
               for profile in ("development", "sec_readonly") for path in (
                   "/companies/{ticker}/filings/{accession_number}/chunks/{chunk_id}/tone",
                   "/companies/{ticker}/financials/coverage", "/companies/{ticker}/financials/quarters")],
    "coverage": [policy+"test_restricted_real_coverage_keeps_pin_and_readonly_transaction"],
}
phase, evidence_path = sys.argv[1:]
assert phase in targets
EVIDENCE = Path(evidence_path).resolve()
assert EVIDENCE.is_dir()
runner = "tests/run_dep01a2_increment2_offline.py" if phase == "encoder" else "tests/run_financial_insights.py"
receipt = dict(phase=phase, runner=runner, node_ids=targets[phase], expected_cases={"encoder": 21, "routes": 6, "coverage": 2}[phase])
print(json.dumps(receipt), flush=True)
sys.argv = [runner, *targets[phase]]
try:
    runpy.run_path(str(ROOT / runner), run_name="__main__")
except SystemExit as result:
    code = result.code
else:
    raise AssertionError("Existing runner did not report an exit status")

assert not blocked, blocked
from app import main, database, config, embedding_service
assert main.HttpSessionLocal is database.HttpSessionLocal
assert main.InsightsSessionLocal is database.InsightsSessionLocal
assert config.server_profile() == config.ServerProfile("development", False)
assert not any(name in sys.modules for name in ("huggingface_hub", "sentence_transformers", "torch", "transformers", "tensorflow"))
if phase == "encoder":
    assert embedding_service._get_model.__module__ == "app.embedding_service"
    assert embedding_service._load_model.__module__ == "app.embedding_service"
    assert embedding_service._get_model.cache_info().currsize == 0
else:
    assert embedding_service._get_model is embedding_service._load_model
    assert embedding_service._get_model.__name__ == "forbidden"
assert socket.create_connection.__name__ == ("bomb" if phase == "encoder" else "forbidden")
assert psycopg.connect.__name__ == ("bomb" if phase == "encoder" else "forbidden")
receipt.update(exit_code=code, blocked_attempts=blocked, restoration="factories/profile/fake modules/cache or encoder bombs restored; socket/DB guards retained")
(EVIDENCE / (phase+"-receipt.json")).write_text(json.dumps(receipt, indent=2)+"\n", encoding="utf-8")
print(json.dumps(receipt), flush=True)
raise SystemExit(code)
'@ | Set-Content -LiteralPath $bootstrap -Encoding utf8
foreach ($phase in @('encoder', 'routes', 'coverage')) {
    & .\.venv\Scripts\python.exe -I -S -B $bootstrap $phase $runDir 2>&1 | Tee-Object -FilePath (Join-Path $runDir ($phase + '.log'))
    if ($LASTEXITCODE -ne 0) { throw "Focused $phase phase failed; evidence retained at $runDir" }
}
"Evidence retained at: $runDir"
```

The encoder phase selects 21 cases using the Increment 2 runner. The six route
cases and two coverage-wrapper cases use the financial runner. Each phase is a
fresh `-I -S -B` child with an explicit Windows dependency path and allowlisted
environment. Mock modules supply constructors/cache lookup; fake sessions supply
query results. No physical ORM hydration/transactions are exercised. Expected
totals are 21 + 6 + 2 = 29, with no skipped/deselected cases. Any nonzero phase
exit or restoration failure stops the recipe and retains evidence.

Original R1 verification: 21/6/2 passed on installed Python 3.14.7; original logs
and all five protected live-file hashes remain preserved in its delivery.
Independent review also passed those cases and the negative false-positive
control. The first instructions depended on a scratch-only launcher; R2 fixes
only this documentation blocker. Fresh-copy verification of this complete recipe
passed 21/6/2 cases on installed Python 3.14.7, with zero skips, deselections or
unexpected failures. The fresh copy initially contained only baseline plus the
three candidate files and the installed-dependency reference; no old launcher or
evidence directory was copied. The single PowerShell block was extracted from
this plan and executed unchanged. It generated its own temporary bootstrap and
all receipts. Factory/profile/cache/module restoration passed; no additive guard
recorded a blocked attempt. Both shared runners and both reviewed test files
remain unchanged. The existing Starlette/httpx warning remains. No broad-suite
rerun, real-data or production acceptance is implied.

## Discovered issues

The original failures are test setup: 20 wrong-runner failures, six invalid
all-route request fixtures (also wrong bounded factory), and one missing helper
argument. One additional AssertionError encoder parameter previously passed for
the wrong reason, so the focused encoder selection is 21 cases, not 20.

## Completion criteria and outcome

All 29 intended cases exercise their asserted paths with no skipped cases or
unexpected IO. Test monkeypatches restore; noncandidate source/shared runners
and all original evidence remain unchanged. Reviewable three-file patch includes
exact baseline/file/evidence hashes and commands. The two existing test files
retain their committed CRLF endings; the new plan uses LF. Patch generation
preserves raw bytes, and strict Git whitespace checks explicitly recognize
`cr-at-eol` while retaining blank-at-eol/blank-at-eof/space-before-tab checks.
These are per-command formatting options, not persistent settings.
The patch, launcher source and receipts are recorded in scratch
`delivery-r2/delivery-manifest.json`. Independent
integration/review remain pending; nothing is committed or pushed.
Suggested commit: `test(backend): repair guarded runtime contract fixtures`.
