# FinLens: six-minute evidence-bound university showcase

Prepared 2026-10-22 against main at
`3d3a245a1919a255ae510b4bfe51b5421a476eba`.

**Task acceptance: FAIL (execution scope). Content package: CONDITIONAL.**
**Portable full showcase: BLOCKED. New live execution: NO-GO.**
This is an offline presentation script and evidence inventory, not a live application
demo or runtime acceptance. According to coordinator-provided review information,
independent documentation review completed with PASS WITH CONDITIONS; the original
review report remains unavailable.
The six allocations total 360 seconds; no timed human presentation rehearsal occurred.

## Presenter preparation and evidence rules

Use only existing screenshots, Markdown/JSON records and source text. Do not start
FinLens, a browser acceptance run, the ML demonstrator or any database/model process.
Do not follow official SEC links during this offline presentation. A retained image
may show an old URL, status or number; explicitly call it historical.

Every artifact ID below resolves through [evidence-manifest.json](evidence-manifest.json).
Its SHA-256 binds bytes inspected during preparation, not enduring availability or
the truth of every displayed fact. Repository files are relative to this pinned
checkout. External evidence uses logical `OPERATOR_TEMP` locators, never personal
absolute paths. Do not copy, extract, relocate or manufacture evidence for this task.

Current committed content was checked against Git. Where checkout newlines differ,
the manifest separately records actual-file and canonical-Git SHA-256 plus filtered
Git object equality. Historical browser captures are not certified current-HEAD UI.

| Segment | Planned time | Evidence readiness |
|---|---|---|
| S1 Purpose and limitations | 0:00-0:30 | PASS for portable narration |
| S2 Financial snapshot/history/provenance | 0:30-2:00 | PASS for historical prepared-data presentation |
| S3 Selected-filing and keyword research | 2:00-3:15 | CONDITIONAL; source/offline evidence, keyword live/browser NOT TESTED |
| S4 SEC risk comparison | 3:15-4:15 | BLOCKED for portable synthetic browser visuals |
| S5 Historical ML evaluation/error analysis | 4:15-5:30 | BLOCKED for portable accepted browser captures/acceptance chain |
| S6 Safeguards and roadmap | 5:30-6:00 | CONDITIONAL; failed original records are non-portable |

PASS in this table concerns the stated presentation scope only. A truthful fallback
allows narration to continue; it never converts a missing required visual or blocked
acceptance chain into PASS.

## S1 - 0:00-0:30: purpose and limitations

**Presenter script:**

> FinLens helps researchers inspect financial information and trace it to sources.
> Its core Research Mode works without a generative AI service. This presentation
> uses recorded application evidence, source inspection and historical analysis.
> I will identify synthetic material and unverified behavior as we go. It is a
> research and educational project, not an investment recommendation or a production
> deployment demonstration.

**Exact references:** `product-roadmap` ([ROADMAP.md](../../ROADMAP.md));
`runtime-boundary-runbook` ([local-demo.md](../local-demo.md)).

**Observable output:** the committed evidence-first/optional-AI product principle,
alongside the explicit offline mode and limitations stated above.

**Proves:** these are the project's documented principles and presentation boundaries.
**Do not claim:** current application health, a current database census, personalized
advice, or completion of planned roadmap phases.

**Fallback:** state this purpose verbally. If the roadmap is unavailable, omit
specific milestone assertions instead of reconstructing them from memory.

## S2 - 0:30-2:00: financial snapshot, history and provenance

**Presenter script:**

> These are historical captures of the prepared-data Research Mode. The snapshot
> keeps a value with its reporting period and units, rather than displaying an
> isolated number. The history view separates fiscal intervals and retains missing
> or incompatible observations. Source disclosures expose the original concept,
> filing accession and official SEC link. A researcher can inspect where a result
> came from instead of relying on a generated explanation.
>
> The retained browser record includes a bounded Apple fiscal-year comparison and
> cases where comparison is unavailable. Those are recorded results from that
> acceptance session. I am not querying today's database, refreshing SEC data or
> claiming these figures are the latest available. The useful engineering behavior
> is preserving the period, economic basis and source boundary, including an honest
> unavailable result when comparison is unsupported.

**Exact assets:** `financial-research-capture`
([snapshot screenshot](../screenshots/research-mode-light.jpg)) and
`financial-history-capture`
([historical comparison screenshot](../screenshots/historical-comparison-desktop.jpg)).
Supporting records: `financial-research-record`
([record](../../backend/reports/research_mode_verification.json)) and
`financial-history-record`
([browser cases](../../backend/reports/historical_answers_browser.json)).

**Observable output:** recorded snapshot/history presentation; historical comparison
and source disclosures. The browser cases include AAPL +6.43% FY2024-FY2025 revenue
change and incompatible/unavailable JPM/COST/XOM cases. These are historical labels
and values from the retained record, not newly validated financial claims.

**Proves:** earlier prepared-data browser acceptance recorded these bounded workflows.
**Do not claim:** fresh acquisition, current values, present database preservation,
arbitrary cross-company comparability, or current-HEAD browser acceptance.

**Fallback:** read a labelled historical case and provenance description from the
portable records. If both records and captures are unavailable, mark the visual
demonstration MISSING and explain the design verbally without quoting numbers.

## S3 - 2:00-3:15: selected-filing research and explicit keyword mode

**Presenter script:**

> This older capture shows selected-filing evidence presentation and source
> disclosures. It predates the explicit keyword mode, so it is not a screenshot of
> that feature. The current committed code adds a separate Keyword search purpose.
> It verifies a version-pinned filing inventory and requires an explicit submission.
> Matching counts case-insensitive substrings in stored passages from the selected
> filing; it is neither exact-phrase search nor semantic retrieval.
>
> The source also implements distinct semantic and hybrid retrieval paths, which
> need approved database and encoder access to run. The UI's general evidence
> context is hybrid; there is no dedicated semantic-only UI demonstrated here.
> Recorded offline tests cover response identity, stale requests and retry focus.
> According to the coordinator-provided independent review result, the three keyword
> corrections passed review. Native-browser and live keyword acceptance remain untested. Stored
> matches are not digest-revalidated evidence, verified financial claims or proof
> that the complete filing contains no other matches.

**Exact assets:** `filing-evidence-capture`
([historical answer/evidence screenshot](../screenshots/answer-evidence-desktop.jpg));
`filing-evidence-record` ([acceptance](../answer-presentation-verification.md)).
Current source: `keyword-ui-source`
([KeywordSearch and research-purpose controls](../../frontend/components/filing-research.tsx)),
`keyword-api-source` ([getKeywordFilingSources/getKeywordSearch](../../frontend/lib/finlens-api.ts)),
and `keyword-matching-source`
([search_filing_chunks/search_filing_chunks_semantic](../../backend/app/filing_search_service.py)).
Offline definitions: `keyword-backend-bridge-tests`, `keyword-mounted-tests`.
Recorded results: `keyword-offline-record`
([REL-LEX-01 plan](../exec-plans/active/2026-10-21-rel-lex-01-keyword-search.md)).
Review provenance: `keyword-astra-coordinator` in the manifest.

**Observable output:** older evidence card, then source text for the explicit
keyword control, pinned preflight, literal-match disclosure and synthetic test cases.
There is no selected keyword result screenshot and no keyword request is executed.

**Proves:** committed implementation exists; the plan records offline checks. Its
886 frontend/188 backend counts are inspected recorded results, not tests run here.
The operator's REL-DEMO-02 instructions are the authoritative coordinator attestation
of completed independent P2 review. The original review report is MISSING from this
selected evidence set; no timestamp, report hash or direct review reproduction is
invented. The old ExecPlan's pending-review wording is stale, not the current verdict.

**Do not claim:** live/native-browser keyword acceptance, new SEC retrieval, semantic
fallback from keyword mode, digest validation, complete filing coverage, or SQL
cancellation inferred from a client timeout.

**Fallback:** show only committed source and labelled offline test definitions. If
the historical capture is missing, omit the visual. Never manufacture keyword
results or reuse an older semantic/evidence image as a keyword screenshot.

## S4 - 3:15-4:15: SEC risk evidence comparison

**Presenter script:**

> This segment concerns candidate passages for a research topic, not a ranking of
> which issuer is riskier. The earlier browser evidence uses synthetic AAA and BBB
> fixtures. It exercises independent issuer versions, source disclosures, partial
> outcomes and explicit retries. It does not retrieve real SEC data or align
> reporting periods.
>
> Six synthetic browser cases passed in that earlier run. A later focus correction
> has separate offline checks; the old captures do not verify the repaired current
> source. Strict QA teardown acceptance also failed and remains failed. The original
> captures currently depend on ignored local output, so the portable visual part
> of this segment is blocked. If those captures cannot be opened, I will explain
> the design from the committed record rather than simulate a live result.

**Exact references:** `risk-browser-report` is the ignored local
`frontend/test-results/sec-risk-cc01-final-721cd8d233a8416f87b902bee14b64bb/results.json`.
`risk-desktop-layout` and `risk-mobile-layout` select the embedded `cc01-layout`
PNG attachment for desktop-chromium/mobile-width-chromium respectively, in the test
named `SEC-RISK-CC01 independent evidence, three disclosure targets, layout and keyboard focus`.
The manifest hashes the decoded PNG bytes separately from the reporter JSON.
Do not extract or copy those PNGs under this authorization.

Portable fallback references: `risk-comparison-record`
([plan and historical source fingerprints](../exec-plans/active/2026-10-20-sec-risk-cc01.md))
and `risk-comparison-source`
([component](../../frontend/components/sec-risk-comparison.tsx)).

**Observable output:** retained synthetic layout/ledger attachments, if an existing
viewer can display them without generation or extraction; otherwise the textual
record only. **Proves:** bounded historical synthetic UI behavior, not current real
issuer risk research. **Do not claim:** live retrieval, complete source coverage,
comparative severity, reporting-period alignment, current repaired-browser closure
or overall QA teardown PASS.

**Fallback:** narrate the independent-pin/partial-result design from the portable
record and source. The portable synthetic-browser visual remains **BLOCKED**;
fallback narration is not replacement browser acceptance.

## S5 - 4:15-5:30: historical ML evaluation and failure analysis

**Presenter script:**

> This is a separate historical Financial PhraseBank sentence-classification
> experiment. The recorded held-out set contains 691 observations: 592 correct and
> 99 incorrect, with 85.6729 percent accuracy and 0.799833 macro-F1. The majority
> neutral baseline is 62.0839 percent accuracy. Macro-F1 helps reveal weaknesses
> hidden by the class imbalance.
>
> In the confusion matrix, rows are actual labels and columns are predictions.
> The model detected 53 of 84 negative examples. Of the 31 misses, 17 were predicted
> neutral and 14 positive. These aggregate counts do not explain individual errors;
> adding false positives and false negatives does not create 198 distinct errors.
>
> The accepted browser view was static with JavaScript disabled. Its input matches
> the committed HTML, but this is not a working classifier demonstration or a new
> evaluation. It establishes neither SEC-filing suitability nor current inference,
> calibrated confidence, investment usefulness or production generalization.

**Exact assets:** `ml-desktop-capture` and `ml-mobile-capture`, using the manifest's
logical temporary locators. Acceptance chain: `ml-static-report`, `ml-static-summary`.
Portable source/aggregate fallback: `ml-static-source`
([HTML as source text only](../../backend/scripts/news_sentiment_demo.html)) and
`ml-frozen-aggregate` ([historical record](../news-sentiment-baseline.md)).

**Observable output:** historical accuracy/baseline, per-class table, matrix,
negative-class misses, frozen provenance and attribution. The existing capture also
contains inactive Connecting/classifier controls; those are outside accepted scope.

**Proves:** REL-SHOW-01D PASS for its JavaScript-disabled static view and exact tested
navigation/viewports. Current HTML SHA-256 is
`679a0e59e2a3e6848931e7724ec5747c7c9b0da3847e5901a4d6007df9190717`,
matching the accepted input. No model/corpus was read and no inference/evaluation
was run during this preparation. Preserve private nonprofit academic use and the
existing attribution; no license expansion or corpus/weight redistribution.

**Do not claim:** functional Classify/Stop controls, live ML performance, fresh SEC
analysis, formal screen-reader certification, other-browser/device acceptance or
deployment. Do not open the HTML with JavaScript enabled: its original application
script polls local APIs. This package authorizes source inspection and existing
captures only, not HTML/browser execution.

**Fallback:** explain the portable aggregate Markdown and HTML source tables as
historical results. Original accepted captures/report are non-portable, so the
portable accepted-browser visual/acceptance chain remains **BLOCKED**, even though
the aggregate explanation remains available.

## S6 - 5:30-6:00: safeguards, limitations and next gates

**Presenter script:**

> The engineering goal is traceable evidence and honest unavailable states. New
> live execution remains no-go: database identity and encoder admission are blocked,
> and strict immediate teardown failures remain failures despite later clean
> observations. The next gates are evidence portability, independent package review
> and an actual timed rehearsal. Feature/data freeze is November 28, code/config
> freeze December 5, and the stable showcase is December 15. Future phases remain
> separately authorized work, not completed features.

**Exact references:** `runtime-boundary-runbook`, `product-roadmap`,
`qa-risk-original-fail` and `qa-risk-teardown-fail` via the manifest. The original
failure records are temporary and non-portable; they have not been modified.

**Observable output:** distinct PASS/static, FAIL/teardown, NOT TESTED/keyword-browser
and BLOCKED/runtime/portability boundaries. **Proves:** the inspected records retain
those outcomes. **Do not claim:** cleared operational gates, future delivery certainty,
production deployment, or a measured six-minute human rehearsal.

**Fallback:** state unresolved gates verbally. If an original failure file disappears,
mark its availability MISSING; never replace its recorded FAIL with PASS.

## Package acceptance and remaining decisions

Execution compliance is **FAIL**, independently of the document checks: the first
verifier called Python tempfile.gettempdir(), whose installed implementation creates,
writes and unlinks a four-byte randomized probe before returning the temporary root.
That transient external write was not authorized. No probe file was retained, its
name was not captured, and no waiver is inferred. This is a preparation deviation,
not a historical acceptance failure and not a new runtime/browser run. The final
verifier reads the existing TEMP environment value without probing and denies Python
filesystem mutation audit events. Content checks passing cannot erase this failure.

All 28 logical artifacts are inventoried: 25 physical files, two in-memory embedded
PNGs and one missing original independent-review report with operator attestation.
At preparation, all 25 selected physical files and both embedded PNGs are readable.
Eighteen artifacts are portable tracked repository files; ten are non-portable or
missing. No screenshot or evidence copy was created.

Package checks validate traceability, bytes, existing outcomes and aggregate arithmetic.
They do not repeat application tests, inspect a database, or certify runtime/browser
behavior. The six time allocations are planned, not measured. S4/S5 portability,
the missing original keyword review report, conditions of the independent
documentation-package review and the human rehearsal remain open. Do not call the full showcase accepted.

By November 28, select the exact evidence and either obtain separately authorized
durable evidence handling or explicitly retain the blocked-visual fallbacks. Do not
copy evidence under this task. By December 5, freeze the reviewed presentation/config
scope. Before December 15, separately authorize and perform the human rehearsal;
any future live path needs its own independently gated protocol. This document does
not authorize evidence copying, runtime work, Git staging, commit or push.
