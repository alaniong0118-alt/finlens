# Optional Uvicorn log safeguard

Status: active; scratch candidate and offline verification, independent review pending.
Roadmap phase: narrow private-login commissioning prerequisite.

## Objective and boundaries

Offer an explicitly installed, default-off filter for the confirmed Uvicorn
access-query and ASGI TRACE-scope exposures. Do not alter application routing,
provider configuration, authentication, existing logging levels, or handlers.
Preserve method, safe path, HTTP version, status and trace event category.
Unrelated ERROR records retain their original message, exception and metadata.

Main was `b05f59d706b4e840ebcbebf34c796628000fe0eb`, index empty; the ten pending
sign-in files and five protected exceptions must remain unchanged. The source
and tests are new scratch files; importing the module does not install a filter.

## Decisions and non-goals

Only Uvicorn's `uvicorn.access` INFO and `uvicorn.asgi` TRACE records are altered.
Access queries are removed across routes, client address is omitted, unknown
private subpaths are masked, and arbitrary extras/tracebacks are not retained in
these records. ASGI TRACE details are reduced to a closed event category. This
is a privacy/observability tradeoff; public access paths, methods and statuses
remain available. Error-level records, including other loggers, are untouched.

Explicit trusted bootstrap must install the filter **after** final logging
configuration and before traffic. There is deliberately no application import,
environment switch, runtime configuration change or activation in this task.
Real handlers must be checked for compatibility: a custom structured formatter
requiring discarded extra fields may fail or lose records. No guarantee is made
for a LogRecord factory/exporter that observes data before logger filters.

This does not sanitize `uvicorn.error` exceptions, private secrets embedded in
non-private URL paths, Next request/proxy errors, other processes, gateways or
external APM. No universal log-redaction or production-readiness claim is made.
Before real login, a separately reviewed ingress/logging design must address all
of those sinks and prove that unrelated errors remain actionable.

## Progress and validation

- [x] Reuse the prior synthetic Uvicorn/Next canary investigation; retain its
  handoff `5f77e5be608f5006d65be28d22d2c627a220874eaa348beea34bb4ddd1b512f7`.
- [x] Implement one stdlib-only optional filter and focused synthetic tests.
- [x] Initial seven-test run had one test-fixture error constructing an invalid
  LogRecord; its test was corrected. The final focused suite has 10 passing tests.
- [x] Run 28 existing synthetic login tests with the filter installed in-process.
- [ ] Independently review exact artifacts; choose a trusted production bootstrap
  and full ingress/Next/APM redaction boundary separately.

From `C:\Users\IITSt\Documents\Codex\2026-11-04\task-3`:

```powershell
.\pg-acceptance-c00c746\backend\.venv\Scripts\python.exe -I -S -B .\backend-log-redaction-20261105\backend\tests\test_private_uvicorn_logging.py
.\pg-acceptance-c00c746\backend\.venv\Scripts\python.exe -I -S -B .\backend-log-redaction-20261105\run_login_regression.py
```

The focused tests exercise the installed Uvicorn AccessFormatter and TRACE helper,
synthetic code/state/token/cookie canaries, malformed records, encoded private
paths, the actual logger-to-handler path, status preservation, opt-in behavior and
unchanged unrelated exceptions. The login suite reuses the maintained guarded
fixture and fake repository. No network, real database, Docker or real credentials
are used. The test guard checks attempted network and file writes; the synthetic
fixtures use only in-memory signing keys.

## Completion criteria and outcome

38 offline tests pass and exact scratch source hashes are available for review.
The primary checkout and pending work remain untouched. `proposed.patch` is for
independent review only; no stage, commit, push, deployment or provider activation.
Next/proxy, external ingress, APM and actual server logging acceptance remain open.
