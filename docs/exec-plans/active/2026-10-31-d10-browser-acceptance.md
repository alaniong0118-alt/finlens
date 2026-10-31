# D10 focused synthetic browser acceptance preparation

Status: active; preparation only, independent review and execution pending.
Roadmap phase: bounded Research Mode provenance display acceptance.

## Objective and constraints

Repair only focused Astra review 01a19228-0b54-7952-9979-dd98b3a8a03e:
align the synthetic as-of accession with its SEC link, and bind the accepted host
runner to a successor snapshot with exact suite-qualified test identities. Preserve
the existing desktop/mobile telemetry phase API, image, resource/network/deadline
controls, image attestation and owned cleanup. No browser/container/service/DB/SEC,
installation, private configuration access, production change or Git write.

## Current architecture and preserved state

Starting main HEAD: dce831a289f984c1f9645f4dec8227b07297f7cf; empty index.
Frozen component SHA256: 1819AAA3DF04DB91B7B1BE514248571063A9D4A92311B9AA74F3884DF9851B12.
Frozen interaction test SHA256: 11FDE505E4B640DBEEC247DD7F3C11D645B8346C6F3975A591F16BF6F0E18893.
Preserve dirty next-env, both historical untracked backend reports, excluded
annual-comparison Markdown-export plan and all prior external snapshots/evidence.
The existing 13 freshness/publication failures remain unresolved and out of scope.

Accepted runner parent: D:/Projects/finlens-annual-period-browser-18f48e0e0f25435988b0b5bc551e33b0.
Preserve first D10 snapshot: D:/Projects/finlens-d10-browser-41eed853973149d68943db3b2e7ae681.

## Decisions and implementation stages

- Correct only the as-of accession metadata in the browser spec.
- Reuse two supported internal phases: desktop for 1440px and mobile for 390px.
  Both select the existing desktop-chromium project, one suite-qualified case per
  phase; the narrow case does not claim touch/mobile-device acceptance.
- Preserve unchanged cleanup checkpoints: baseline, desktop-post-phase,
  mobile-post-phase, final-cleanup. Do not extend the telemetry helper API.
- Rebind the accepted external runner through an explicit minimal edit ledger;
  offline reversal must recover the exact accepted parent runner bytes. Capture
  nested suite identity in result parsing so identical leaf titles cannot alias.
- Create a new allowlisted, hash-bound snapshot/proposal; retain prior evidence.

## Progress and validation

- [x] Read focused review, root guidance and actual accepted runner/helper.
- [x] Align as-of accession/link metadata.
- [x] Bind and validate external successor runner and manifest.
- [x] Scoped lint/type checks, exact per-phase discovery and focused offline
  fixture/result-identity/phase/cleanup/inventory checks. Record commands/results
  in the external preparation record, bound by the successor manifest.
- [ ] Independent focused Astra review (coordinator controlled).
- [ ] Separately authorized one-attempt execution; not authorized by preparation.

## Completion criteria and final outcome

Preparation is reviewable when source/protected hashes match, the original
runner is recoverable by reversing only the recorded binding edits, exact
desktop1/narrow1 identities are discovered, and the proposed command is bound to
the successor manifest. No browser or cleanup acceptance claim follows from
offline checks. Remain active pending review and any separately authorized run.
Suggested later manual commit: test: cover alternative observation dates in browser.

## Preparation result — 2026-10-31

Successor: D:/Projects/finlens-d10-browser-0880704c056b4d35a09e81c30c5aa91c.
The actual binding also required reusing the accepted snapshot-only observer
bootstrap in external e2e-server.mjs; the repository launcher remains unchanged.
No helper API changed. Source inventory: 43 files / 1,407,055 bytes, aggregate
C431C2530EE7632D98FD437F85F8F16C33F9185F8EE3B8EB84FDDCB508DE2C07.

Actual offline checks: scoped ESLint and tsc --noEmit --incremental false exited 0;
exact full-argument --list discovery found desktop1/narrow1, zero executed results;
26 focused Node checks passed; PowerShell parse and seven actual host identity
guard checks passed. The explicit sixteen-edit ledger reverses the successor
runner to the exact accepted parent bytes. Prior snapshots remain unchanged.
Detailed commands/results and exclusions are in successor PREPARATION.md; discovery
and host-guard evidence are in the matching external finlens-d10-preflight root.
Final manifest/proposal hashes and exact proposed command are supplied at handoff
and in preflight handoff.json, outside the immutable mounted source inventory.

Preparation is complete for coordinator-controlled focused Astra review. Browser,
runtime enforcement and cleanup acceptance remain unexecuted. Stop here: no
review dispatch, optional-dependency risk acceptance or operational permission is
inferred. Existing thirteen failures remain unresolved. The index remains empty;
only the scoped browser spec and this plan changed in this repair.

## Retained failed attempt and diagnostic-only preparation

The separately executed attempt 046d2f3dc25643f1a1fa3acd149bbd19 used manifest
03EF35CE738497418BE47A6778B9176B0361852A6DFFEA269696962C2B9B05EA.
Its retained overall outcome is FAILED: desktop 1440px outline containment was
false with focus-visible true, solid outline and width 3px; the narrow phase was
not reached. The report has no target rect, outline offset or scroll geometry,
so no clipping/root-cause diagnosis is established. Preserve the full attempt at
D:/Projects/finlens-annual-browser-artifacts-046d2f3dc25643f1a1fa3acd149bbd19.
Its incomplete test/artifact gates remain incomplete; observed container absence
does not turn the failed browser case into acceptance.

Current authorization is diagnostic-only test instrumentation and a new prepared
one-run proposal. Preserve exact native Tab/Space path, strict viewport-outline
containment, both width selections, fail-fast behavior and all runtime controls.
No after-focus scroll, product fix, helper API extension or assertion weakening.

- [x] Add bounded, sanitized per-focus geometry capture to the new browser spec:
  element rect/client/scroll geometry; outline width/offset; viewport/scroll;
  clipping ancestors' rect, overflow and scroll, with explicit truncation flags.
  No DOM text, URLs, raw attributes or arbitrary CSS value capture.
- [x] Exercise the actual capture/assertion/attachment functions with offline
  geometry examples; verify native path and strict predicates remain unchanged.
- [x] Freeze a successor source/runner/proposal and exact one-run command for
  focused independent review. No browser/container execution in this preparation.

Diagnostic successor:
D:/Projects/finlens-d10-browser-6e9e9f04833e41bcb5ee38fbd04e75c3.
Source inventory: 43 files / 1,409,247 bytes; aggregate SHA256
D49069942091848B54CC15AC69A7706AB2D38EB149A7AF2140366503D5C1D6A3.
Only the browser spec changes among source entries; the native runner only rebinds
snapshot pins/support inventory. A fifth support file supplies geometry examples.

Actual offline results: 17 geometry/capture/attachment/path-preservation examples
passed; 26 existing bound-runner/source/phase/discovery checks passed. Scoped
ESLint, TypeScript, PowerShell proposal parsing and git diff --check exited 0.
Exact desktop1/narrow1 --list discovery used unchanged selectors, both with zero
execution results. No browser rerun occurred. The failed attempt's indexed bytes
and FAILED overall-result hash match; parent source/support/proposal remain intact.
Commands/results are recorded in successor PREPARATION.md and matching preflight
handoff.json, including the final immutable manifest digest and one-run proposal.

Stop for focused Astra review. This diagnostic preparation establishes neither
the real clipping geometry nor a product fix or browser/cleanup acceptance. The
native path and strict predicates remain unchanged, so the later authorized
diagnostic run may reproduce the failure and must remain fail-fast. All prior
evidence and original protected exceptions remain preserved; no Git write.

## DPR-1 measurement correction preparation

Coordinator supplied Astra's later review of retained attempt
b3e1cc982df14658b9e62841c0425ed1 (manifest
E5DDF39958B3CBD587C0D4B8974620F71A914F9C4C4B4B37615F552D65FB1612).
It remains FAILED under its original strict assertion. Review measured the outer
bottom at 1000.421875 CSS px in a 1000px viewport; the retained screenshot showed
a complete three-row accent stroke. DPR was not recorded then, so internal
raster-rounding cause and behavior at other DPRs are not established.

New authorization permits only a bounded test measurement correction: explicitly
configure deviceScaleFactor 1, assert/record actual DPR 1, preserve strict
contained and measured edge overflow, and accept only finite nonnegative overflow
strictly below 0.5 physical pixel on every edge. Reject half-pixel/larger overflow,
invalid/nonfinite geometry and any DPR other than finite numeric 1. Retain native
Tab/focus/visibility/outline checks, ancestor capture, no scrolling, both widths,
fail-fast/no-retry behavior and all runtime controls. No product/CSS change.

- [x] Implement test-only DPR/measurement predicate and evidence fields.
- [x] Add four-edge 0.421875/0.5/1 examples, DPR and invalid-geometry cases;
  verify all other native/focus/clipping checks remain unchanged.
- [x] Freeze a successor snapshot/proposal and exact one-run command for focused
  review only; retain both historical failed attempts without reclassification.

Measurement successor:
D:/Projects/finlens-d10-browser-12d9f8d9741b45f9ae087ff2a3f6e988.
Source inventory: 43 files / 1,410,864 bytes; aggregate SHA256
17ED39114B6FD8C9DFE960C9135D8503B58BDC95968E02DE372B46EAEF0D3D45.
Only the scoped browser spec changes among source entries. Its existing geometry
support gains the DPR-1 cases; the native runner only rebinds snapshot identities.

Actual offline results: 70 geometry/DPR/attachment/native-path checks passed,
including all four 0.421875/0.5/1 boundaries, invalid/nonfinite geometry and DPR,
negative physical-overflow predicate rejection, retained strict evidence and
actual helper enforcement. Twenty-six bound-runner/source/phase checks passed.
Scoped lint, TypeScript, PowerShell parse-only and git diff --check exited 0.
Exact full-argument --list discovery found desktop1/narrow1, no executed results.
Both retained failed attempts' indexed evidence and FAILED overall results match.
Detailed commands and results are in successor PREPARATION.md; matching preflight
handoff.json records final immutable hashes and the exact one-run proposal.

Stop for focused Astra review. Actual DPR, visible ring completeness at both
widths, browser success and runtime/cleanup acceptance remain unverified here.
The bounded geometry correction alone is not a visible-ring acceptance claim.
Both historical failures and thirteen unrelated failures remain unresolved under
their original scopes. No browser/container/network/service execution or Git write
occurred.

## Per-focus raster evidence preparation

Latest focused Astra review conditionally passed the DPR-1 measurement change,
but identified that the failure-only screenshot/trace settings did not guarantee
retained pixels for successful focus checks. Current authorization closes only
that evidence gap: capture and attach a bounded viewport PNG before assertions at
each of the seven existing focus points in both unchanged cases. Use page-level
viewport capture, never locator screenshots or scrolling/navigation/actions.
Keep full tracing unchanged and retain existing artifact/export limits.

- [x] Add per-focus PNG capture before focus/visibility/outline/DPR/containment
  assertions, on both eventual success and failure. Fail closed if capture or
  attachment fails; cap seven PNGs per case and 2 MiB per PNG.
- [x] Add actual-helper offline capture/order/limit/failure checks and retain
  existing geometry/DPR/native-path and runner checks.
- [x] Bind immutable successor, record exact command/hashes and stop for narrow
  Astra delta review. No browser/container execution or Git write authorized.

Raster-evidence successor:
D:/Projects/finlens-d10-browser-857b4c18b30f4272a6af44bba08e20ac.
Source inventory: 43 files / 1,411,680 bytes; aggregate SHA256
B3E046F8C7A1C627CDDFB9C30BD03144E48F38D2E94707F389820208E234C415.
Only six prefix statements in the existing spec focus helper are added. The full
native test body, geometry/DPR function and prior focus/assertion statements are
unchanged. Runner changes only identity/byte pins; no artifact or trace setting
changes. The seven per-case PNGs use the established attachment/export mechanism.

Actual offline checks: 80 geometry/DPR/capture examples passed, including PNG
options, image-before-assertion order, successful and failing focus, seven/eighth
capture bounds, empty/oversized payloads, timeout and attachment errors. Twenty-six
bound-runner/source/result/phase checks passed. Scoped lint, TypeScript, proposal
parsing and git diff --check exited 0. Exact --list discovery found desktop1/
narrow1 with zero executed results. All prior frozen source/protected hashes and
both failed attempts remain unchanged; both historical outcomes stay FAILED.
Detailed commands/results and the exact one-run proposal are recorded in the
successor PREPARATION.md and matching preflight handoff.json.

Stop for narrow Astra delta review. No actual raster screenshot or browser result
is generated by these offline mock capture checks. Actual complete-ring visual,
browser, runtime and cleanup acceptance remain pending a separately authorized
one-attempt run and inspection. No Git write or unrelated thirteen-failure work.


## Actual bounded synthetic browser outcome — 2026-10-31

This append records the coordinator-supplied execution/visual outcome and the
retained reports. It supersedes earlier pending-execution statements for this
bounded synthetic D10 slice only. It does not establish complete accessibility,
touch/device acceptance, production deployment or broader regression success.

Attempt: 7266e68ab4984b85b5b9bc58bb88da6d.
Frozen snapshot: D:/Projects/finlens-d10-browser-857b4c18b30f4272a6af44bba08e20ac.
Manifest SHA256:
19F0C3DD3AD5B07ACFDEF75A364E4BBED206FF7BE34FEAE7B695D2696E4B21F1.
Retained evidence:
D:/Projects/finlens-annual-browser-artifacts-7266e68ab4984b85b5b9bc58bb88da6d.

**Automated synthetic outcome: PASS, desktop1 plus narrow1, retry zero.** Both
cases ran in desktop-chromium: 1440x1000 and 390x844. Each passed once with no
failed/skipped/flaky case in its report. Native Tab/Space, supplied duration/as-of/
unknown alternative dates, values/order/SEC links, narrow wrapping/no document
overflow and the bounded DPR-1 measurement checks passed within these synthetic
fixtures. No external source-link navigation or real financial-data acceptance
is inferred.

The overall result records all six gates PASS: testEvidence, artifacts,
containerAbsent, preservation, proposalPreserved and hostClisReaped. Both phase
cleanupVerified flags and final cleanup.verified are true. The attempt's final
cleanup records ports 3107/3108 closed, zero extra live processes and temporary
QA copies, and removal of its dependency link and owned runtime root. These are
recorded end-of-attempt observations, not a new/current liveness check.

**Raster/geometry evidence and visual limits.** The reports retain fourteen PNG
attachments and fourteen geometry attachments: seven pairs per viewport, captured
before the corresponding assertions. Every geometry record reports actual DPR 1
and rasterContained true. Acceptance explicitly requires finite nonnegative
per-edge overflow strictly below 0.5 physical pixel; it is not exact geometric
containment. Desktop as-of source focus (d10-focus-raster-3 / d10-focus-7) retains
strict contained false with bottom overflow 0.421875 physical pixel and passes
the explicit raster tolerance. Other thirteen records retain strict contained
true with zero recorded edge overflow.

Coordinator raster inspection found the first narrow alternative-summary image
(d10-focus-raster-1 in mobile/results.json) partly occluded by a circular marker.
The same summary's return-focus image (d10-focus-raster-6) was unobscured. The
marker is strongly consistent with the Next development indicator, but definitive
DOM identity was not established. Do not claim that every individual event was
unobscured, that clipping-ancestor diagnostics prove complete ring visibility, or
that this is complete accessibility or touch acceptance. The automated PASS and
this visual qualification are both part of the outcome.

The artifact index lists 26 payload files / 2,474,251 bytes. Its indexed sizes and
SHA256 values were checked read-only during this closure. PNG/geometry attachment
counts refer to retained report attachments, not an invented set of standalone
image/JSON files. Key raw artifact hashes:

| Artifact | SHA256 |
| --- | --- |
| overall-result.json | 1DD66ACCCBE9D1463C3D252BB7EBAD2F3FE198ED60B7C6152B1B55036799F8C9 |
| artifact-index.json | 5820D43AAE0D7EA481351B5BE1263F66BF0586AC199CEC6C1708EC1344FA6C9D |
| receipt.json | 67D17D18871D40E0E0B89FC65502606E792E0DFC9A11E9D32BEA3A19981BD05D |
| desktop/results.json | D2517B0535B3D39BAF9619CB34F5188F74E756E2639CF0CBCEFF3E070E2DFF27 |
| mobile/results.json | 8416099D61D9AB63FDB59BFC2B489134329A0B6E17F5B6BADA5871CCBABB8019 |

**Historical failures remain separate.** Attempts
046d2f3dc25643f1a1fa3acd149bbd19 and b3e1cc982df14658b9e62841c0425ed1 remain
FAILED under their original assertions. Their immutable evidence is preserved;
the later bounded pass does not retroactively repair either attempt.

The unresolved freshness/publication regressions also remain separate. The
candidate's filtered run reported 61 passed / 13 failed. The coordinator's pinned
baseline selection reported one passing control and failures in the same thirteen
test names; some failed at different assertion points. This does not prove
identical causes or resolve those failures. They remain outside the D10 slice.

**Documentation-only closure.** No tests, imports, browser/container/service/
network work, Git writes or new review dispatch occurred here. Only this append
changes the repository. Production component, interaction test, browser spec,
protected next-env, two historical backend reports and excluded Markdown-export
plan retain their hashes. HEAD/main and the empty index remain unchanged.

The accepted manifest continues to bind this plan's pre-append bytes: SHA256
CAAF46DA9FE49EA25B36E47A048EB3E5FE919E2673DE287B7561FD2961AB6A5A.
Do not repin/rewrite that manifest, any earlier snapshot, or retained evidence.
The final appended-document hash belongs in the manual handoff. Suggested later
manual commit: fix(frontend): show alternative observation periods.


## 2026-11-01: request-accounting integration and final manual handoff

The earlier 61-pass/13-fail filtered result and pinned-baseline 1-pass/13-fail
result above remain historical failures under their original assertions. They
are not rewritten or relabeled by the later correction. The same thirteen named
accounting cases now pass with the independently reviewed test expectations in
the current combined candidate, alongside all three D10 cases.

The product change remains the bounded D10 display of each alternative source's
own observation dates. The accounting correction changes tests, not product
request logic: annual discovery is an additional pinned request; StrictMode's
one retired annual setup and four active endpoints are asserted explicitly;
annual mismatch self-cancellation is distinguished from three sibling transports.
Exact endpoints/pins, fail-closed recovery, coalesced freshness coordination and
late old-pin response isolation remain asserted. No blanket annual/cancelled
request filter or global count increase was introduced.

**Actual current-repository integration:** 16 executed, 16 passed, 0 failed,
0 skipped, 0 cancelled, exit 0, one actual test-process run. Selection was exactly
13 accounting cases (company switch plus twelve lifecycle variants) and three
D10 cases. The first inline-command approval request was rejected before process
launch; its NOT EXECUTED receipt remains intact. The later approved readable
command file compiled JavaScript RegExp selection from sixteen explicit names
and passed that pattern as a single process argument. No automatic retry occurred.

Retained integration evidence root:
D:/Projects/finlens-foundation/frontend/.cache/finlens-accounting-final-integration-b0733be4505845559e035ea92683d3f0.
- Command: node '<evidence root>/run-integration-16.mjs' (cwd frontend).
- Runner SHA256: 41071E44DBA339B310EE66BB451D34B06AF03BF40711AD35D97E57EC7E6D251D.
- Explicit selection manifest SHA256: 442C992261CD020B604D7212E9CF415392304FFBCE73E85121033B547E684381.
- integration-commandfile-output.txt SHA256: 1F42C60583D7398F0D0FF47F618ED885C6D91A268EEB099A9D801E246D808A61.
- integration-commandfile-result.json SHA256: 8B969E49719293C6CD75743A0A4B532DEABD0652CCBB40296E4EE34F5265A494.
- Verified combined interaction-test raw SHA256: 076F5DA375B261C8ECBD82663BEBF7FA27E735A60EC0364900427C81CFAA4989.

**Applied independent review:** Astra chat 01a1921e-acfb-7833-ad6b-2b5020c87baf,
latest completed review turn 01a192d2-e668-7812-8bb6-ed78254d059a, returned PASS
for separate manual Git handoff within this scope, with no blocking findings.
The reviewer verified the applied helper/twelve variants and company-switch
correction against reviewed scratch sources; reversing the complete accounting
patch in memory with original newline bytes restored D10-only test SHA256
11FDE505E4B640DBEEC247DD7F3C11D645B8346C6F3975A591F16BF6F0E18893.
The imprecise existing "All three transports" comment was noted as non-blocking.
The reviewer inspected retained evidence and did not rerun tests.

**Separate audit boundaries:** the frozen D10-only patch SHA256
DD5C48600A0C783411CE941DDB06942304F74BA042093A037E8B0C481F1F0985 and
its manifest SHA256 6C44DAC048A605BB0E6841A58E1346AECBEE7FFF083EB040983EDAA946C254D9
remain unchanged in the earlier finlens-d10-accounting-integration-d7ab2986c52f442a88e41f284b3438b0
scratch root. That manifest binds this plan's earlier EFFCE401... bytes, not this
append. The complete accounting patch is separately bound at SHA256
64AFA3061090E573A18442B1E4EFCF73DABAF5C2E8CAE5B0E734B23C78F67764 (+97/-11).
The applied integration manifest remains SHA256
B7558BFDDED3CCF2A74B9239155435C1ECA384992497A38AD5A6244AB660C10A.
No prior manifest, snapshot, rejected-launch receipt or failed browser record
was repinned or rewritten. Final four-file raw and Git-clean identities belong
in the new manual handoff audit, outside this self-referential document.

**Acceptance limits remain unchanged:** the retained limited synthetic browser
acceptance covers one 1440px and one 390px desktop Chromium case. The first narrow
focus image's circular-marker occlusion, the unobscured return-focus image, DPR 1
and the reviewed strict-less-than-half-physical-pixel tolerance remain qualified
as recorded above. This is not complete accessibility, touch, full-suite,
lint/build, production, provider, service or database acceptance. The two older
browser attempts remain FAILED. No test/browser/service/network work ran during
this documentation-only finalization; no new independent review was dispatched.

The four-file delivery is the D10 production component, combined interaction
test, D10 browser spec and this ExecPlan. Other code and the four protected
exceptions remain unchanged; HEAD is dce831a289f984c1f9645f4dec8227b07297f7cf and
the index is empty at handoff. Stage all four paths together only after manual
hash verification; do not partially stage display versus necessary accounting.
Suggested combined commit: fix(frontend): show alternative observation periods and align request lifecycle tests.
