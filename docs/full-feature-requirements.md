# FL-ALL-1215 full-feature requirement register

Status: documentation draft for independent review; not implementation or release approval.
Recorded: 2026-10-29 (Asia/Macau).
Task: FL-ALL-1215-W1-C0, bounded documentation implementation.
Revision: FL-ALL-1215-W1-C0-FIX1, local documentation correction; focused independent re-review pending. Astra's C0 documentation Git Step 1 FAIL and C1 implementation NO-GO remain historical/current independent dispositions until superseded by coordinator review; local checks do not confer approval.
Inspection baseline: main at `b8e89ef884b96f8fd8eec1ea4daba37b2f04295a`, empty index.

## Mandate and authorization

December 15, 2026 is the fixed full-scope acceptance target, not an MVP or recorded-showcase substitute. All sixteen research/product domains, their 45 subfeatures, ten differentiators D1-D10, Universal Company Research U1-U6 and non-commercial billing parity B1-B6 remain required: **67 atomic requirement records**. The sixteen domain headings are groups, not sixteen additional accepted features. Dependencies do not remove or defer requirements.

November 28 is the feature/data **baseline** freeze: freeze feature behavior, schemas, source policies, algorithm versions and regression datasets while governed acquisition/publication continues. December 5 is the code/configuration freeze. Exceptions require coordinator disposition and affected reacceptance; an incomplete feature cannot be relabelled defect repair. Dates are targets, not evidence of feasibility or acceptance.

The revised FL-ALL-1215 conversation is the planning input. Its 296-hour aggressive allocation (including 40 contingency) and 296-446 operator-hour range are unmeasured planning budgets for one operator at 35-45 hours/week with Sol/Astra assistance, not guaranteed AI productivity. C0 does not restart that feasibility study. No additional engineers, installations, acquisitions or deployments are assumed authorized.

FinLens remains useful without an LLM. Deterministic finance, search and evidence inspection are core. Free local generative AI and optional explicitly selected paid-cloud AI are both full-target requirements. Educational optimization/forecasts use user-set assumptions; personalized investment advice, trade execution and unsupported price targets remain excluded under [AGENTS.md](../AGENTS.md).

FinLens is currently non-commercial. Billing includes complete code, mocks and separately approved actual Stripe test-mode/sandbox workflows. Merchant activation, company registration, live payments and real money movement are **not** December 15 prerequisites. Future commercialization is not authorized.

Only this file and [shared-research-contracts.md](shared-research-contracts.md) are created by C0. No production integration, services, database access, provider/SEC acquisition, model loading, credentials, dependencies, staging, commit or push is authorized. The [ExecPlan standard](../.agent/PLANS.md) applies before later complex implementation; C0 creates no third file.

## Status and acceptance rules

Allowed current statuses:

- **tested**: a specifically bounded existing component has recorded historical test/acceptance evidence. It does not certify all target behavior, current data, current HEAD runtime or deployment.
- **partial**: usable code/contract ingredients exist, but the full row outcome is incomplete or unaccepted.
- **missing**: no complete corresponding product workflow was found in the relevant inspected interfaces.
- **blocked**: a material acceptance/activation prerequisite remains unresolved; the row's blocker states which one.

Current totals: **5 tested, 26 partial, 30 missing, 6 blocked**. These are scoped baseline classifications, not release completion counts. No runtime/browser/application tests were run in C0. Static source inspection and previously recorded results must stay separate.

Every row's `Candidate` and `New acceptance` cells are real, initially unpopulated acceptance records. `unassigned` means no implementation candidate is nominated for this row. `pending` expands to the following fields for **each individual row**, including historically tested rows:

| Per-row field | Initial value | Required later evidence |
|---|---|---|
| candidate_revision_or_digest | unassigned | Exact reviewed Git revision or immutable candidate/file digest; baseline HEAD is not automatically the candidate. |
| actual_checks | not run by C0 | Command, date/environment, result/counts, artifact/report link and limitations. |
| offline_acceptance | pending | Actual deterministic/mutation/contract evidence for that candidate. |
| source_and_runtime_acceptance | pending | Actual permitted-source, DB/model/parser/worker evidence where relevant; otherwise explicit justified applicability. |
| product_and_operations_acceptance | pending | Browser/accessibility/isolation/recovery evidence appropriate to the row, without claiming live commercialization. |
| independent_review | pending | Reviewer, scoped verdict/findings and exact reviewed candidate. |
| coordinator_disposition | pending | Accepted boundary or remaining blocker, without rewriting historical failures. |

A later update must replace the specific row's pending record with its own evidence link/fields before declaring full acceptance. A plan, source filename, model self-report, mock, successful compilation or valid citation ID cannot populate real-source/runtime/support evidence. A historical report may be cited as historical evidence only; do not overwrite it. Omitted/unsupported observations are honest data states, but an absent whole workflow is not complete merely because it shows “unavailable.”

## Evidence index: actual interfaces and historical boundaries

Evidence codes below name inspected implementation or recorded acceptance sources, **not new executions**. Baseline data freshness, physical DB contents and running application state were not accessed.

| Code | Source | Evidence boundary |
|---|---|---|
| E0 | [API inventory](../backend/app/main.py), [ORM inventory](../backend/app/models.py), [current frontend](../frontend/app/page.tsx) | No complete corresponding workflow in these relevant interfaces; does not assert no experimental helper exists anywhere. |
| E1 | [Roadmap](../ROADMAP.md), [product spec](product-spec.md), [historical Research Mode record](exec-plans/completed/2026-10-05-research-mode.md) | Curated catalog/readiness and no-key research have historical bounded acceptance; old counts/status prose are not current DB measurements. |
| E2 | [Financial schemas](../backend/app/financial_metric_schemas.py), [metric service](../backend/app/financial_metrics_service.py), [registry](../backend/app/financial_metric_registry.py), [financial contracts](financial-metrics.md), [insights schemas](../backend/app/financial_insights_schemas.py) | Fifteen canonical metrics, conservative normalization, existing deterministic/comparison/evidence contracts; no complete statements/segments or general external adapter. |
| E3 | [Comparison client](../frontend/lib/company-comparison.ts), [CC-02 record](exec-plans/active/2026-10-16-cc02-annual-metric-expansion.md) | Qualified synthetic 2-4-company/eleven-metric annual acceptance; strict frontend/backend pair must be delivered/rolled back compatibly. |
| E4 | [Refresh contracts](../backend/app/refresh_contracts.py), [refresh service](../backend/app/refresh_service.py), [SEC parser](../backend/app/sec_parser.py), [original-evidence adapter](../backend/app/sec_evidence_adapter.py), [freshness runbook](data-freshness.md) | Existing ingestion/publication/reconciliation and narrow reviewed original-evidence handling; no blanket source, scheduler or live-operation approval. |
| E5 | [Retrieval/context](../backend/app/rag_context_service.py), [generation](../backend/app/answer_service.py) | Stored bounded retrieval and development-only optional cloud answer policy; citation identity is not claim-support proof; no accepted general multi-document/local generation workflow. |
| E6 | [Market contracts](../backend/app/market_data_contracts.py), [return engine](../backend/app/market_returns.py), [market history evidence](market-data-history.md) | Offline inputs, normalization and exact returns/alignment; hashes do not prove source custody, calendar/action completeness or display rights. |
| E7 | [Risk-topic implementation](../frontend/lib/sec-risk.ts), [risk comparison](../frontend/components/sec-risk-comparison.tsx), [tone](../backend/app/filing_tone.py), [news sentiment baseline](news-sentiment-baseline.md), [failure analysis](exec-plans/active/2026-10-21-ml-fail-01-aggregate-analysis.md) | Bounded risk exploration/lexical tone and private academic sentiment/failure evidence; no generalized financial risk score, deployed licensed news service or accepted forecasting. |
| E8 | [Browser evidence boundaries](browser-e2e-testing.md), [insights record](exec-plans/active/2026-10-26-fin-depth-01-frontend-1b.md) | Historical/qualified synthetic browser acceptance; native/zoom/assistive-technology and candidate-specific exclusions must remain explicit. |
| E9 | [Strict publication helper](../backend/app/publication_admission.py), [resource policy](../backend/app/reader_resource_policy.py), [helper tests](../backend/tests/test_reader_publication_admission.py), [Reader entrypoint](../backend/app/sec_reader.py) | Helper independently accepted/committed as b8e89ef per coordinator and present at HEAD. Reader still diagnostics-only. No DB/HTTP lifecycle, ranking integration, activation or deployment acceptance follows. Do not reopen the completed helper review. |
| E10 | [Research-note serializer](../frontend/lib/research-note.ts) | Validated source-backed comparison export ingredients; no complete persistent workspace/receipt system. |

The competitor outcome baseline is [StephaneWamba/finlens at 27e64a8345b104da95bca490b639cbcf191f4b41](https://github.com/StephaneWamba/finlens/tree/27e64a8345b104da95bca490b639cbcf191f4b41), inspected in the prior planning conversation, not fetched or run by C0. Parity covers complex/multi-document research, hybrid search, PDF/image uploads and batch/OCR/table processing, persistent sessions/memory/history, authentication/profiles/usage, financial comparisons/trends/visualizations and subscription lifecycle. GPU technology, agent count, Supabase/Qdrant/Redis/LangGraph or a particular hosting stack are not user-outcome requirements.

## Dependencies, ownership and shared contract mapping

P0 runtime/security/identity; P1 data/Universal Research; P2 financial depth; P3 retrieval/generation; P4 workspace/documents; P5 markets/portfolio/simulations; P6 risk/NLP/ML; P7 test billing; P8 UX/exports/differentiators; P9 acceptance/operations. These are logical work packages, not additional engineers. Sol implementation, independent Astra risk review and operator integration need later bounded authorization.

Contract references C1-C9 refer to the **proposed** interfaces in [shared-research-contracts.md](shared-research-contracts.md). A range such as C1-C5 or 7a-7c includes every intervening ID. Dependencies such as D3/5c or D5/7c express the same shared feature family, not a requirement to implement duplicate services or an impossible strict cycle. Build their common prerequisite, then accept each distinct outcome.

P0 boundaries precede exposed/private consumers; pure consumers may be developed against locked fixtures. Source/model rights and actual acceptance are independent of code readiness. Preserve the complete-publication checks, separate fact/evidence/market versions and existing API/client semantics.

## Atomic requirement records

Each row records expected outcome, baseline status/evidence, positive and negative acceptance, dependencies/owner, blockers and its unpopulated candidate/acceptance record. Every row remains in the December 15 target.

### 1. Company catalog, identity and research

| ID | Expected user outcome | Status / evidence | Acceptance and negative cases | Dependencies / contracts / owner | Remaining blocker | Candidate | New acceptance |
|---|---|---|---|---|---|---|---|
| 1a | Identify catalog issuers and data-derived filing readiness. | tested; E1; bounded historical catalog/readiness acceptance | Identity/readiness agree; negative: unindexed or partial accessions never become Ready and no N+1 listing. | P0; C1/C2; owner P0 | Current data inventory not measured. | unassigned | pending |
| 1b | Research metrics, history and filing evidence without an AI key. | tested; E1/E2; historical no-key browser/API acceptance | Current-candidate source-backed journey works; negative: AI/evidence failure cannot erase a valid deterministic answer. | P0/P2; C2/C5/C6; owner P2 | Current-candidate runtime/browser acceptance pending. | unassigned | pending |
| 1c | Research issuers absent from the local catalog. | missing; E0; stored-company loaders reject unknown companies | U1-U6 pass end to end; negative: no hardcoded issuer map or mandatory company/fact insertion. | U1-U6; C1-C9; owner P1 | Generic identity/source/session pipeline missing. | unassigned | pending |

### 2. SEC acquisition, parsing and automatic updates

| ID | Expected user outcome | Status / evidence | Acceptance and negative cases | Dependencies / contracts / owner | Remaining blocker | Candidate | New acceptance |
|---|---|---|---|---|---|---|---|
| 2a | Discover, acquire and parse permitted official SEC filings. | partial; E4; SEC client/parser/importer and catalog workflow | Preserve issuer/accession/original bytes; first run/rerun/interruption work; negative: identity or parse mismatch quarantines data. | P0/P1; C1-C5/C8/C9; owner P1 | Current source/runtime acquisition acceptance pending. | unassigned | pending |
| 2b | Update tracked companies automatically without issuer-specific code edits. | blocked; E4; refresh/version machinery, operational activation unaccepted | Scheduled cycles respect leases/budgets and publish complete updates; negative: maintenance/lease loss cannot permit a stale writer. | 2a/15d; C8/C9; owner P1 | Scheduler, writer fencing and actual operating acceptance. | unassigned | pending |
| 2c | Preserve amendments, quarantine ambiguity and recover safely. | partial; E4; insert-only facts and publication/reconciliation helpers | Retain originals/vintages and prior intact publications; negative: no destructive revision, duplicate import or partial publication after failure. | 2a/2b; C3/C4/C8/C9; owner P1 | Broader revision coverage and actual recovery acceptance. | unassigned | pending |

### 3. Statements, metrics, ratios and segments

| ID | Expected user outcome | Status / evidence | Acceptance and negative cases | Dependencies / contracts / owner | Remaining blocker | Candidate | New acceptance |
|---|---|---|---|---|---|---|---|
| 3a | Inspect existing normalized metrics and deterministic calculations. | tested; E2; fifteen definitions and historical period/formula acceptance | Preserve Decimal calculations, operands, units and provenance; negative: missing/zero/incompatible inputs never fabricate values. | P2; C3/C5; owner P2 | Full-target coverage/current acceptance still separate. | unassigned | pending |
| 3b | Inspect income, balance and cash-flow statements and expanded ratios. | partial; E2; selected metrics are not complete statements | Retain supported source line items, reconcile totals and review industry-specific formulas; negative: missing lines are not zero or universal coverage. | 2a/2c; C3-C5; owner P2 | Statement structure, definitions and admitted coverage incomplete. | unassigned | pending |
| 3c | Compare business/geographic segments with source context. | missing; E0/E2; no complete dimensional analysis workflow | Preserve dimensions, eliminations, scales and changed segment definitions; negative: do not add overlapping totals or silently match renamed segments. | 3b/8c; C1-C5; owner P2 | Dimensional/table extraction and comparability policy. | unassigned | pending |
| 3d | Select original/restated vintages and supported as-of observations. | partial; E2/E4; alternatives exist, default selects latest compatible vintage | Availability/system-knowledge cutoff selects correct originals; negative: future-known rows or today's revised facts cannot establish a historical snapshot. | 2c; C3/C4/C5; owner P2 | Historical originals/timestamps and vintage selector. | unassigned | pending |

### 4. Multi-company and multi-period comparison

| ID | Expected user outcome | Status / evidence | Acceptance and negative cases | Dependencies / contracts / owner | Remaining blocker | Candidate | New acceptance |
|---|---|---|---|---|---|---|---|
| 4a | Compare the delivered bounded annual company/metric set. | tested; E3; qualified synthetic CC-02 acceptance | Preserve 2-4 issuers, eleven metrics, independent pins and source drill-down; negative: reject wrong issuer/window/metric set. | 3a/15c; C1/C3/C5; owner P2 | Prepared-data/current runtime acceptance not established here. | unassigned | pending |
| 4b | Compare multiple years/quarters and compatible company measures. | partial; E2/E3; bounded same-company comparisons already exist | Deterministic multi-period grids expose source pairs; negative: no annual/YTD substitution, silent FX conversion or incompatible-basis ranking. | 3b/3d; C1/C3/C5; owner P2 | Expanded comparison UI and supported arithmetic. | unassigned | pending |
| 4c | Understand why financial values are or are not comparable. | partial; E2/E3; compatibility checks/warnings exist | Explain fiscal window, accounting scope, currency, industry and EPS limitations; negative: an exclusion cannot silently disappear. | D6; C3/C5; owner P2 | Integrated inspector and current UI acceptance. | unassigned | pending |

### 5. Hybrid search, complex RAG and multi-document synthesis

| ID | Expected user outcome | Status / evidence | Acceptance and negative cases | Dependencies / contracts / owner | Remaining blocker | Candidate | New acceptance |
|---|---|---|---|---|---|---|---|
| 5a | Search admitted filing evidence lexically and semantically. | blocked; E5/E9; retrieval implemented, runtime/release admission incomplete | Complete-publication integrity and bounded scoped ranking survive; negative: corrupt unselected evidence, stale pins or encoder denial cannot fall back insecurely. | P0/model admission; C2/C4/C6/C9; owner P3 | Actual runtime/model admission and release adapter acceptance. | unassigned | pending |
| 5b | Ask complex multi-document and cross-company questions. | missing; E5; company-wide retrieval has no generation action | Bounded decomposition/synthesis answers supported subquestions with lineage; negative: wrong company/period or unsupported subquestion abstains. | 5a/6c; C1-C6/C9; owner P3 | Synthesis workflow and evaluated evidence planning. | unassigned | pending |
| 5c | See evaluated retrieval and supported rather than invented claims. | partial; E5; heuristics/tests are not general relevance or entailment proof | Versioned gold cases cover retrieval, periods, numerics, injection and abstention; negative: citation identity alone never passes support evaluation. | 5a/5b/D3; C2/C3/C6; owner P3 | Gold set/threshold approval and real output audits. | unassigned | pending |

### 6. Free local and selectable paid-cloud AI

| ID | Expected user outcome | Status / evidence | Acceptance and negative cases | Dependencies / contracts / owner | Remaining blocker | Candidate | New acceptance |
|---|---|---|---|---|---|---|---|
| 6a | Generate useful free local evidence-grounded narrative answers. | missing; E5/E9; MiniLM is an encoder, not a generative provider | Actual local generation works with cloud disabled; measure quality/resources/cancellation; negative: no external-knowledge gap filling or silent cloud fallback. | P0/5c; C2/C6/C9; owner P3 | Runtime/model artifact/loader admission and measured inference. | unassigned | pending |
| 6b | Explicitly select optional controlled paid-cloud analysis. | partial; E5; existing development-only provider integration | Opt-in model/provider identity, consent, budgets and failure handling work; negative: no dispatch after failed reservation or automatic billable retry. | 6c/15b; C6/C7/C9; owner P3 | Gateway, approved provider budget and real claim acceptance. | unassigned | pending |
| 6c | Switch generation providers without changing evidence/privacy rules. | partial; E5; existing citation/policy foundations only | Both providers consume the same authorized evidence and validation; negative: switching cannot export private history or revive cancelled work. | 5c/15b; C2/C6/C7/C9; owner P3 | Provider-independent contract and lifecycle integration. | unassigned | pending |

### 7. Persistent chat, history, memory and saved research

| ID | Expected user outcome | Status / evidence | Acceptance and negative cases | Dependencies / contracts / owner | Remaining blocker | Candidate | New acceptance |
|---|---|---|---|---|---|---|---|
| 7a | Use multiple persistent threads and grounded follow-ups. | missing; E0; no complete thread/turn persistence workflow | Restart/reopen retains turns and evidence/version references; negative: follow-ups cannot change issuer scope or reuse another owner's history. | 15a/15b; C1/C4/C6/C7; owner P4 | Owned persistence and contextual follow-up implementation. | unassigned | pending |
| 7b | Control long-term memory and its deletion/export. | missing; E0 | Default off; inspect/edit/delete/export covers derived indexes/caches; negative: memory is never authoritative finance or silently restored after deletion. | 7a/15b; C2/C7/C9; owner P4 | Memory lifecycle, retention and restore/deletion policy. | unassigned | pending |
| 7c | Save investigations, notes and watchlists across sessions. | partial; E10; transient workspace/export ingredients | Owned notes/watchlists reopen with evidence pins; negative: expired/unavailable originals must be disclosed, not silently replaced. | 15b/D5; C4/C7/C8; owner P4 | Workspace persistence and durable references. | unassigned | pending |

### 8. PDF/image uploads, OCR and table extraction

| ID | Expected user outcome | Status / evidence | Acceptance and negative cases | Dependencies / contracts / owner | Remaining blocker | Candidate | New acceptance |
|---|---|---|---|---|---|---|---|
| 8a | Upload and manage private PDF/PNG/JPG/JPEG batches. | missing; E0; SEC HTML ingestion is not private upload handling | Owned upload/status/cancel/retrieval/delete work; negative: cross-user access, MIME spoofing and unbounded batches reject. | 15b; C2/C4/C7-C9; owner P4 | Artifact storage, quotas and owned job interface. | unassigned | pending |
| 8b | Read text PDFs/scanned images with page/heading provenance. | missing; E0 | Isolated parsing/OCR includes resumable representative 1,000-page acceptance; negative: corrupt/encrypted/bomb inputs cannot exhaust or escape workers. | 8a; C2/C4/C8/C9; owner P4 | Approved parser/OCR packaging and actual resource acceptance. | unassigned | pending |
| 8c | Inspect extracted tables without losing financial relationships. | partial; E4; narrow structured/Inline-XBRL helpers, no general OCR table workflow | Retain cells/rows/columns, units/scales/footnotes; negative: uncertain OCR, merged cells or conflicting scale cannot become verified facts. | 8b/3b; C2-C5; owner P1/P4 | Generic table provenance and admission policy. | unassigned | pending |

### 9. Market data, adjustments, returns and charts

| ID | Expected user outcome | Status / evidence | Acceptance and negative cases | Dependencies / contracts / owner | Remaining blocker | Candidate | New acceptance |
|---|---|---|---|---|---|---|---|
| 9a | Inspect permitted real price histories with listing identity. | blocked; E6; offline contracts/adapters, no accepted live product | Bind security/listing/calendar/currency/source dates and rights; negative: ticker reuse, gaps or unknown custody cannot imply continuity. | 15b/source rights; C1-C4/C8/C9; owner P5 | Rights, acquisition custody and actual source acceptance. | unassigned | pending |
| 9b | Use correctly adjusted prices and deterministic returns. | partial; E6; exact return/action/alignment kernels | Independent split/dividend/same-day tests and real action completeness pass; negative: missing actions or incompatible calendars block returns. | 9a; C1/C3/C5; owner P5 | Real corporate-action authority/completeness acceptance. | unassigned | pending |
| 9c | View/export clearly labelled market series and charts. | missing; E0/E6; financial-history charts are not market charts | Raw/adjusted basis, gaps and export agree exactly; negative: no fabricated fills or mixed adjustment basis. | 9a/9b; C3-C5/C7; owner P5/P8 | Market UI/export workflow. | unassigned | pending |

### 10. Portfolio analytics and optimization

| ID | Expected user outcome | Status / evidence | Acceptance and negative cases | Dependencies / contracts / owner | Remaining blocker | Candidate | New acceptance |
|---|---|---|---|---|---|---|---|
| 10a | Analyze hypothetical holdings/benchmarks, including VaR and CVaR (Expected Shortfall). | missing; E0/E6 | Historical returns, volatility, drawdown, covariance and historical-loss VaR/ES reproduce from pinned data under the specification below; negative: wrong sign/quantile/tail, sparse/nonfinite/missing data or currency/exposure mismatch cannot produce misleading risk values. | 9b/15b; C1/C3/C5/C7/C9; owner P5 | Owned holdings, risk-method implementation and independent numerical acceptance. | unassigned | pending |
| 10b | Explore constrained educational optimization. | missing; E0 | User-set objectives/constraints give reproducible feasible solutions or explained failure; negative: infeasibility/singular inputs cannot become personalized allocation advice. | 10a; C5/C7/C9; owner P5 | Optimizer/solver acceptance and research-only presentation. | unassigned | pending |

### Proposed 10a historical VaR/CVaR acceptance specification

Status: PROPOSED / PENDING INDEPENDENT REVIEW; this extends 10a without adding an ID or changing its missing status. Value at Risk (VaR) and Conditional Value at Risk (CVaR, Expected Shortfall/ES) are distinct from volatility/drawdown and are not future-performance guarantees.

- **Loss/exposure:** loss is `L = -P&L` in the declared reporting currency: positive means loss, negative means gain; never clamp a negative VaR/ES to zero. Revalue the explicitly pinned hypothetical portfolio under each historical horizon. With initial signed asset exposures `E_j` and admitted horizon gross total-return factors `G_j,i,h`, use `P&L_i,h = sum(E_j * (G_j,i,h - 1))`. Keep initial holdings/exposures fixed across scenarios, with each asset's dividend/action treatment inherited from its admitted return method; disclose no fees/financing costs unless explicitly included by a separately reviewed method. Record positions, exposure date, net/gross exposure and currency. A percentage output divides by strictly positive declared portfolio value only; zero/negative net value leaves valid currency loss measures intact but percentage unavailable. Missing FX authority or mixed undeclared currencies fails closed.
- **Confidence/horizon:** confidence `alpha` is a finite exact Decimal/string value with `0 < alpha < 1` (80% means 0.8), never a binary float, boolean or implicit percentage conversion. Default display selection is 0.95, explicitly shown. Horizon `h` is an exact positive integer number of supplied trading sessions, default 1; no booleans, fractional horizon or square-root-of-time scaling. Construct complete consecutive h-session gross factors from the existing admitted return engine; do not recompute adjusted prices with a new engine.
- **Sampling:** equally weighted empirical historical scenarios over the explicitly selected, pinned window. For h > 1 use all overlapping complete consecutive h-session windows and disclose overlap/sample count; no iid claim. The requested asset/calendar/window must be complete; a gap, missing observation/action coverage or nonfinite input makes the affected analysis unavailable, with no silent sample dropping, zero fill or backfill.
- **Quantile:** sort finite losses ascending `L_(1)..L_(N)`; `VaR_alpha = L_(ceil(alpha*N))` (empirical inverse CDF, nearest-rank/type-1 quantile). Do not linearly interpolate or use a library's default percentile convention. Exact Decimal/rational ordering is required; preserve source IDs for audit.
- **Tail/ties:** let `k = N*(1-alpha)`, `q = VaR_alpha`, `n_gt = count(L_i > q)`. ES is `[sum(L_i for L_i > q) + (k-n_gt)*q] / k`. Include all losses strictly greater than q at full weight; use only the remaining tail mass at q, distributed equally among observations equal to q for the receipt. Do not average every observation with L >= q; threshold ties must not inflate tail mass. Non-integer k uses fractional boundary mass, not a rounded sample count.
- **Precision/method:** method ID `historical-loss-es-v1`; derive exactly using Decimal/rational operands. Keep exact numerator/denominator or terminating Decimal and source pins in the calculation reference; round display only to 18 decimal places with HALF_EVEN, disclosing precision. Other methods (including Monte Carlo estimates) need their own method ID/assumptions and cannot be substituted for the historical reference.
- **Insufficiency:** N < 2 complete scenarios makes both unavailable. With N >= 2, empirical VaR can be shown with N/h/confidence and a sample-limitation notice; if k < 1, ES is unavailable as `insufficient_tail_mass`, not the maximum loss or a model estimate. Report k, strict-tail count, threshold-tie count and overlap. These computational minima do not claim statistical adequacy or coverage guarantees.

Deterministic documentation reference cases (hypothetical fixtures, not issuer or market data):

| Case | Inputs | Required exact result |
|---|---|---|
| Threshold ties | One USD 100 exposure, h=1, ten losses in USD [-4,-2,0,1,1,2,3,4,4,10], alpha=0.8 | N=10, k=2, rank=8, VaR=4 USD, ES=7 USD; VaR/ES percentages 4%/7%. Strict tail is 10; each threshold-4 observation receives weight 1/2. |
| Fractional tail | Same losses/exposure, alpha=0.85 | k=1.5, rank=9, VaR=4 USD, ES=8 USD; each threshold-4 observation receives weight 1/4. |
| Sparse tail | Same losses, alpha=0.95 | rank=10, VaR=10 USD; k=0.5 means ES unavailable, not 10 USD by substitution. |
| All gains | Four losses [-4,-3,-2,-1] USD, alpha=0.5, h=1 | VaR=-3 USD and ES=-1.5 USD; preserve signs. |
| Scaling/order | Multiply exposures/losses by 2, or permute the first fixture | Doubled VaR/ES 8/14 USD; permutation leaves values/tie mass unchanged. |
| Two-session compounding | Initial USD 100 exposure; consecutive gross factors [1.1,0.9,1.1,0.9], h=2, all overlapping windows, alpha=0.5 | Three gross factors [0.99,0.99,0.99] give losses [1,1,1] USD; N=3, rank=2, k=1.5, VaR=1 USD and CVaR/ES=1 USD. Each threshold observation receives tail weight 1/2. |

Exact documentation arithmetic for the two-session fixture: each adjacent product is (11/10)*(9/10) or (9/10)*(11/10) = 99/100, so each loss is -100*(99/100-1)=1 USD. At alpha=1/2, nearest rank ceil(3/2)=2 selects q=1; k=3/2 and n_gt=0 give ES=[0+(3/2)*1]/(3/2)=1 USD. The same factors at h=1 give losses [-10,10,-10,10] USD, VaR=-10 USD and ES=10 USD under the unchanged conventions. Direct sqrt(2) scaling would give -10*sqrt(2) and 10*sqrt(2) USD (approximately -14.1421 and 14.1421), not 1 and 1: the wrong VaR has the wrong sign, and the wrong ES squared is 200 rather than 1. This exact rational derivation independently checks the authored fixture; it is not an executed production mutation test.

Negative/mutation acceptance: reject alpha 0/1/out-of-range/nonfinite/float/bool; horizon 0/negative/fractional/bool; empty/singleton, missing asset/window/action/FX data, NaN/Infinity, undeclared exposure/currency and nonpositive percentage denominator. Mutating sign, quantile to interpolation, tail to all L>=q or fractional k to integer rounding must fail the relevant reference. The future horizon mutation test must first pass the two-session fixture through the intended compounded-horizon path, then replace only that path with direct square-root scaling of the one-session VaR/ES for the same exposure/factors/confidence. The mutant must reach the intended h=2 branch and fail the VaR/ES numerical assertions for that reason, not an unrelated parse/validation/guard failure. The five earlier h=1 cases alone cannot detect this mutation because sqrt(1)=1. Documentation arithmetic is not evidence that a production mutation test ran; no such application test was executed here. The missing/denominator cases preserve independently valid outputs only where specified above; no future-loss probability guarantee follows.

### 11. Monte Carlo, scenarios and stress testing

| ID | Expected user outcome | Status / evidence | Acceptance and negative cases | Dependencies / contracts / owner | Remaining blocker | Candidate | New acceptance |
|---|---|---|---|---|---|---|---|
| 11a | Explore seeded correlated simulations and bootstrap distributions. | missing; E0 | Seeds, assumptions, convergence and tail limitations are recorded; negative: invalid covariance or resource overflow fails without partial results. | 9b/10a; C3/C5/C7/C9; owner P5 | Simulation kernels, evaluation and UI. | unassigned | pending |
| 11b | Apply explicit scenarios, shocks and sensitivity tests. | missing; E0 | User assumptions propagate deterministically over supported exposures; negative: unsupported causal mappings or advice requests reject. | 3b/10a; C5/C7/C9; owner P5/P6 | Exposure definitions and stress workflow. | unassigned | pending |

### 12. Financial and SEC risk analysis

| ID | Expected user outcome | Status / evidence | Acceptance and negative cases | Dependencies / contracts / owner | Remaining blocker | Candidate | New acceptance |
|---|---|---|---|---|---|---|---|
| 12a | Explore guided and cross-issuer SEC risk evidence. | partial; E7; risk-topic and two-issuer exploration implemented | Actual source/UI acceptance preserves issuer/version boundaries; negative: empty evidence never implies no risk. | 5a; C1-C4/C6; owner P6 | Current prepared-data/browser acceptance and review disposition. | unassigned | pending |
| 12b | Inspect explained debt, liquidity and cash-flow vulnerability measures. | missing; E0/E2 | Reviewed source-backed indicators disclose industry applicability and missing operands; negative: no invented issuer score or unsupported ranking. | 3b/11b; C3/C5; owner P6 | Expanded finance inputs and quantitative risk workflow. | unassigned | pending |

### 13. NLP and financial news sentiment

| ID | Expected user outcome | Status / evidence | Acceptance and negative cases | Dependencies / contracts / owner | Remaining blocker | Candidate | New acceptance |
|---|---|---|---|---|---|---|---|
| 13a | Inspect source-bound filing passage tone. | partial; E7; authored lexical proxy and integration | Exact source/span and bounded result remain; negative: lexical tone cannot be labelled confidence, market sentiment or financial risk. | 5a; C2/C4/C6/C9; owner P6 | Current runtime/UI and remaining review acceptance. | unassigned | pending |
| 13b | Research permitted news and evaluated sentence sentiment. | blocked; E7; private PhraseBank experiment, no deployed licensed news pipeline | Entity/date/source binding, deduplication, attribution and deployable inference pass domain tests; negative: private dataset permission cannot authorize public redistribution. | 15b/source rights; C1-C4/C6/C8/C9; owner P6 | News/provider/model rights and application workflow. | unassigned | pending |

### 14. ML research, forecasting and failure evaluation

| ID | Expected user outcome | Status / evidence | Acceptance and negative cases | Dependencies / contracts / owner | Remaining blocker | Candidate | New acceptance |
|---|---|---|---|---|---|---|---|
| 14a | Inspect reproducible ML experiments and recorded failures. | tested; E7; recorded real private sentiment baseline/failure analysis | Preserve dataset/model/split/environment hashes, baselines and failure examples; negative: historical metrics cannot certify a new launch or domain. | P6; C2-C5/C9; owner P6 | Application experiment registry/integration still incomplete. | unassigned | pending |
| 14b | Explore financial-series forecasts and honest failure evaluation. | missing; E0/E6 | Walk-forward/as-of inputs, naive/seasonal baselines, intervals and leakage checks pass; negative: failed models or revised future data cannot masquerade as predictive success. | 3d/9b/14a; C3-C5/C7/C9; owner P6 | Point-in-time datasets and forecast/evaluation workflow. | unassigned | pending |

### 15. Authentication, isolation and secure remote Windows hosting

| ID | Expected user outcome | Status / evidence | Acceptance and negative cases | Dependencies / contracts / owner | Remaining blocker | Candidate | New acceptance |
|---|---|---|---|---|---|---|---|
| 15a | Onboard/login/logout and manage profile/session/usage history. | missing; E0/E9; server profile is not user authentication | Stable identity, session expiry/revocation and owned profile/usage work; negative: forged email/header, expired token or untrusted issuer rejects. | P0; C7/C9; owner P0 | Identity provider/configuration and session implementation. | unassigned | pending |
| 15b | Keep all private objects, jobs and quotas isolated per user. | missing; E0 | Authorize before reads/ranking/export; two-user object/cache/job tests pass; negative: guessed IDs or caller-supplied owner IDs never grant access. | 15a; C2/C6-C9; owner P0 | Ownership enforcement and privilege separation. | unassigned | pending |
| 15c | Access FinLens securely over HTTPS from other networks. | blocked; E9; diagnostics-only Reader and admission helpers | Actual Windows/external-network HTTPS and exact route admission pass; negative: no direct DB/inference exposure or wildcard proxy authorization. | 15a/15b/15d; C7/C9; owner P0/P9 | Reader DB/HTTP lifecycle, ingress/config and deployment approval. | unassigned | pending |
| 15d | Recover safely with non-owning reader roles and fenced workers. | partial; E4/E9; historical safety/recovery foundations | Actual backup/restore, restart, lease loss and maintenance tests pass; negative: failed cleanup/stale worker cannot publish or reuse unsafe sessions. | P0/P1; C8/C9; owner P9 | Actual role/target continuity and operating acceptance. | unassigned | pending |

### 16. Responsive UX, accessibility, exports and reliability

| ID | Expected user outcome | Status / evidence | Acceptance and negative cases | Dependencies / contracts / owner | Remaining blocker | Candidate | New acceptance |
|---|---|---|---|---|---|---|---|
| 16a | Use every workflow responsively and with assistive technology. | partial; E8; historical and qualified synthetic UI acceptance | Keyboard/focus, small widths, 200% zoom, forced colors and screen-reader cases pass; negative: clipping, contrast or focus loss cannot be accepted by DOM-only tests. | All consumers; C6/C7/C9; owner P8 | Full new-workflow native/browser/accessibility acceptance. | unassigned | pending |
| 16b | Export source-backed data, reports and research receipts. | partial; E10; existing comparison note serializer | CSV/printable report/receipt reproduce values, sources, assumptions and versions; negative: unsafe links or expired/private sources cannot leak or be silently substituted. | D8/15b; C2-C7/C9; owner P8 | Expanded exports and actual consumer/clipboard acceptance. | unassigned | pending |
| 16c | Run a reproducible, bounded and recoverable full product. | blocked; E8/E9; harnesses/budgets are not deployment acceptance | Fresh setup, load/cancellation, monitoring, graceful degradation and restore pass on candidate; negative: compile/mocks cannot replace real runtime acceptance. | All packages; C1-C9; owner P9 | Cross-module, Windows and operational acceptance. | unassigned | pending |

### Differentiators D1-D10

| ID | Expected user outcome | Status / evidence | Acceptance and negative cases | Dependencies / contracts / owner | Remaining blocker | Candidate | New acceptance |
|---|---|---|---|---|---|---|---|
| D1 | Financial Update Radar: follow financial changes without code edits. | partial; E4; freshness/publication ingredients | Followed issuers produce committed changes/check times; negative: failed checks or pending publications cannot appear as current. | 2b/7c; C1/C3/C4/C7-C9; owner P1/P8 | Scheduled updates/watchlists and change UI. | unassigned | pending |
| D2 | Financial Time Machine: compare original/restated/as-of research. | partial; E2/E4; alternatives, no complete vintage workflow | Originals and availability/system-knowledge cutoffs explain changes; negative: current revised facts cannot reconstruct missing historical knowledge. | 3d; C3-C5; owner P2/P8 | Historical originals, temporal selector and UI. | unassigned | pending |
| D3 | Evidence-Verified AI: inspect support for material claims. | partial; E5; identity checks are not semantic support proof | Numbers bind admitted facts/formulas and narrative support is audited; negative: invented citations or model self-certification cannot authorize claims. | 5c/6c; C2-C6; owner P3 | Shared support gate and real claim audit. | unassigned | pending |
| D4 | Risk Observatory: combine source-backed financial/SEC/scenario views. | partial; E7; bounded risk exploration/tone only | Financial indicators, SEC evidence and licensed signals expose methods; negative: no unsupported issuer ranking or predictive risk score. | 12a/12b/11b/9a; C1-C7; owner P6/P8 | Quantitative inputs and integrated views. | unassigned | pending |
| D5 | Research Workspace: retain notebooks, investigations, watchlists and alerts. | partial; E10; transient workspace/export ingredients | Saved investigations reopen/export accurately and owner-scoped; negative: stale/expired evidence cannot be silently refreshed. | 7a-7c/15b; C4/C7/C8; owner P4 | Owned persistence and workspace integration. | unassigned | pending |
| D6 | Comparability Inspector: explain financial comparison limits. | partial; E2/E3; compatibility checks exist | Explain period/currency/basis/industry/share exclusions beside values; negative: incompatible values cannot be ranked as equivalent. | 4c; C1/C3/C5; owner P2/P8 | Inspector UI and consistent rule explanations. | unassigned | pending |
| D7 | Research Change Inbox: see changes affecting saved research. | missing; E0 | Publication-linked idempotent unread/read events link affected investigations; negative: retries cannot duplicate notices or republish facts. | D1/D5; C4/C7/C8; owner P4/P8 | Outbox/recipient authorization and inbox UI. | unassigned | pending |
| D8 | Reproducible Research Receipt: inspect and replay research lineage. | partial; E2/E10; provenance/serialization ingredients | Pin artifacts/data/formulas/parameters/model/output and replay deterministic results; negative: no promise of identical generation or replay after prohibited retention. | 3d/16b; C3-C7/C9; owner P8 | Durable pins, retention decisions and receipt UI. | unassigned | pending |
| D9 | Coverage Planner: inspect source/period/metric gaps and permitted jobs. | partial; E1/E4; readiness/inventory ingredients | Expose form/period/metric gaps and authorized job plans/outcomes; negative: viewing coverage never starts acquisition or implies complete SEC coverage. | 2a/3b; C1-C5/C8/C9; owner P1/P8 | Coverage interface and generic planning view. | unassigned | pending |
| D10 | Evidence Conflict View: inspect alternatives and unresolved conflicts. | partial; E2/E4; conservative rejection/alternatives exist | Show source/vintage and selection/rejection reasons; negative: legitimate revisions are not conflated with same-vintage contradictions or silently resolved by AI. | 2c/3d; C2-C5; owner P2/P8 | Conflict presentation and cross-source admission. | unassigned | pending |

### Universal Company Research U1-U6

| ID | Expected user outcome | Status / evidence | Acceptance and negative cases | Dependencies / contracts / owner | Remaining blocker | Candidate | New acceptance |
|---|---|---|---|---|---|---|---|
| U1 | Resolve an absent issuer from authoritative identity references. | missing; E0/E1; stored catalog identity exists, no generic resolver | Ticker/exchange, CIK, name or trusted reference returns verified candidates; negative: collisions/renames cannot be resolved by name similarity or ticker hacks. | P0/P1; C1/C2/C3; owner P1 | Authority registry and generic identity resolver. | unassigned | pending |
| U2 | Discover and acquire permitted official evidence on demand. | missing; E4; SEC acquisition pieces, no universal official-source path | Prefer admitted local coverage, then SEC/IR/exchange/regulator sources; negative: search snippets, prohibited hosts/redirects or rights denial never supply facts. | U1/15b; C1-C4/C7-C9; owner P1 | Source policies, discovery and controlled external worker. | unassigned | pending |
| U3 | Extract verified facts and calculate deterministically. | missing; E2/E4; reuse candidates, external bridge not implemented | Preserve identity, units/scale/dimensions/period/basis and formula inputs; negative: OCR uncertainty/conflicts cannot enter financial output. | U2/3b/8c; C2-C5; owner P1/P2 | Reviewed admission bridge; no fabricated DB fact IDs. | unassigned | pending |
| U4 | Finish research without inserting a company or financial facts. | missing; E0; existing loaders require catalog/CIK facts | End-to-end successful session runs with company/fact insertion disabled; negative: saving cannot automatically promote private/session evidence to shared data. | U1-U3/15b; C1/C2/C4/C5/C7; owner P1 | Session evidence store and persistence-independent adapter. | unassigned | pending |
| U5 | Answer external-evidence narrative questions with free local AI. | missing; E0/E5 | Actual local generation works with cloud disabled and source/date/period/basis/status labels; negative: no model-knowledge gap filling or forced cloud purchase. | U3/U4/6a; C2-C7/C9; owner P3 | Admitted model plus external-bundle generation. | unassigned | pending |
| U6 | Fail closed securely across absent-company and negative cases. | missing; E0 | Uncatalogued SEC and non-SEC cases pass plus identity/conflict/missing/OCR/quota/cancel cases; negative: no SSRF, arbitrary file path or resource bypass. | U1-U5/15b; C1-C9; owner P9 | Whole workflow and actual source/runtime acceptance. | unassigned | pending |

### Non-commercial billing parity B1-B6

| ID | Expected user outcome | Status / evidence | Acceptance and negative cases | Dependencies / contracts / owner | Remaining blocker | Candidate | New acceptance |
|---|---|---|---|---|---|---|---|
| B1 | Create/view test subscriptions and checkout/customer records. | missing; E0; competitor user-outcome parity requirement | Mocks and separately approved Stripe sandbox creation/status succeed with server-allowlisted test prices; negative: caller cannot select arbitrary entitlement/customer. | 15a/15b; C7-C9; owner P7 | Billing adapter/ledger and separately authorized test credentials. | unassigned | pending |
| B2 | Manage plans, renewals, failures, recovery and cancellation. | missing; E0 | Mock/test-mode changes, immediate/end-period cancel and customer management preserve access timing; negative: failed renewal/late event cannot grant stale access. | B1; C7-C9; owner P7 | Subscription state policy and sandbox lifecycle acceptance. | unassigned | pending |
| B3 | Process signed webhooks exactly once in effect. | missing; E0 | Validate original bytes/signature and handle duplicate/replayed/reordered events idempotently; negative: forged signature or wrong mode/account rejects. | B1/15b; C7-C9; owner P7 | Verified event ingress and durable processing. | unassigned | pending |
| B4 | Reconcile missed events and uncertain billing outcomes. | missing; E0 | Mock/sandbox provider reconciliation repairs ledger consistently; negative: blind retry cannot double-create effects or trust client redirects. | B3; C7-C9; owner P7 | Reconciler and auditable provider-operation ledger. | unassigned | pending |
| B5 | Enforce server-side entitlements and usage under concurrency. | missing; E0 | Grant/revoke/quota state matches versioned policy and races; negative: browser claims, cross-user requests or failed reservations cannot grant access. | B2-B4/15b; C7-C9; owner P7 | Entitlement/usage enforcement and concurrency tests. | unassigned | pending |
| B6 | Operate complete billing parity without commercial activation. | missing; E0; scope is code, mocks and approved sandbox flows | Actual Stripe test workflows plus mocks pass; negative: live credentials/events or real charging are disabled in non-commercial deployment. | B1-B5; C7-C9; owner P7/P9 | Test-mode access/acceptance only; no merchant/company/live-payment prerequisite. | unassigned | pending |

## Cross-module acceptance and compatibility

All 67 rows require appropriate contract, offline, real-source/runtime, product/isolation/accessibility and operations gates; billing additionally requires actual separately approved Stripe sandbox workflows, not live charging. Reuse one evidence/ownership/job layer without letting billing, user memory, uploads or generated text confer financial authority. Retain the eleven-metric CC-02 client/server pair and the current closed insights/reference schema until an explicit versioned transition is accepted.

U1-U6 must succeed for uncatalogued SEC and non-SEC issuers using permitted official evidence, with company/fact insertion disabled. U5 requires actual local generation with cloud disabled; mock generation cannot close it. Search engines are discovery tools, not unquestioned financial sources. Conflicts, missing information and rights/resource denial fail closed; absence of public information is not permission to invent facts. Governed on-demand acquisition is an explicit job action, never a side effect of existing read routes.

B1-B6 require creation/status, plan/cancellation lifecycle, signed raw-byte webhooks, idempotency, reordered/missed-event recovery/reconciliation and authoritative entitlements under concurrency. Mocks cover deterministic failures; separately approved Stripe test mode covers the actual provider seam. Live-mode rejection is part of acceptance. Test access is an external prerequisite; merchant activation and real money are not.

The ten differentiators are integration consumers: D1/D7 share committed change events, D2/D8 share versions/originals, D6/D10 share financial diagnostics, and D4 uses research/risk/scenario inputs. Their individual acceptance rows remain mandatory.

## C0 preservation, verification and handoff

Entry and closure baseline: main at `b8e89ef884b96f8fd8eec1ea4daba37b2f04295a`, empty index. Preserve these pre-existing exceptions:

| Path relative to repository | SHA-256 |
|---|---|
| frontend/next-env.d.ts | F4E8976C19FC926644D72610BF1058BD6BF52ADD97E46A02BC0B912A751625C0 |
| backend/reports/canary-aapl_guarded_live_20261010_111844_3580610-publication.json | A783517D2875E39DF4C831C410265D0126FBF6A9D3DDBA1103F7BD61B057844C |
| backend/reports/refresh-discovery-aapl_sec_discovery_20261010_002323_0671678.json | F8DF96C8890C0ECE1E1701B25BC5C43B879C359ECEB96ACB451A2A0DAA58BF7C |

Documentation verification is recorded only after it runs: inventory counts/IDs/statuses, all-row contract references, evidence/link targets, whitespace and exact two-file scope, branch/HEAD/index and protected hashes. No application test, DB/source/model/browser/provider or deployment result may be inferred from these checks.

### Checks actually run by C0 (2026-10-29)

- An ephemeral standard-library Python validator, run from repository root with the existing interpreter and `-I -S -B`, verified 67 unique exact IDs: 45 subfeatures across 16 domains, D1-D10, U1-U6 and B1-B6; all row fields, owner/contract/dependency references, five tested/26 partial/30 missing/six blocked statuses, unassigned candidate/pending acceptance cells, all ten differentiator names, nine proposed contract sections, 63 local link targets, Markdown fence balance and scoped whitespace/EOF rules. It imports no application modules and performs no DB/network/model operations. The checker initially assumed nine rather than eight register columns; that checker assertion was corrected. Extra blank EOF lines detected by the subsequent check were removed from the two new documents. The complete final validation passed.
- `git diff --check` returned 0. Each `git diff --no-index --check -- NUL` returned 1 because the new document differs from NUL, with only Git's informational LF-to-CRLF conversion notice and no whitespace-error diagnostics; the independent whitespace/EOF validator passed. The check wrapper initially treated this expected no-index difference code as a failure; its interpretation was corrected without changing content for that reason. No application, browser or service-backed tests ran.
- A non-environment tracked/nonignored-file SHA-256 inventory compared 374 entry files with 376 closure files: every original file byte-identical, no deletions, and exactly the two authorized documentation additions. Private dotenv files were excluded without reads/hashes; protected public files were included and unchanged.
- Branch/HEAD/index/status and the three protected hashes were rechecked. main/HEAD remain b8e89ef884b96f8fd8eec1ea4daba37b2f04295a, the index is empty, and status consists only of the three original exceptions plus these two new documents. No staging, commit or push occurred.

Self-review disposition: ready for independent documentation/contract review, not approval to implement consumers. Remaining join decisions and the inert first-slice proposal are explicit in the shared-contract draft. Suggested eventual commit, only if separately requested: `docs: add full-feature register and shared research contract draft`.

Resume by reading root instructions, roadmap, this register and shared contracts, then rechecking current Git state. Do not use historical HEAD or statuses as current acceptance. The proposed next slice is the inert identity/evidence-reference boundary in the shared-contract draft, only after independent documentation/contract review and separate implementation authorization. Reader DB/HTTP activation remains a distinct gate. C0 authorizes no consumer module, new dependency or Git delivery.

## FIX1 local correction record (2026-10-29)

Coordinator supplied Astra's independent C0 verdict: documentation Git Step 1 FAIL and C1 implementation NO-GO, with three P2 findings and no P0/P1. The original C0 self-review recommendation above is historical; this local correction does not supersede the independent verdict.

- P2 #1: extended existing 10a with VaR/CVaR/Expected Shortfall, exact loss/exposure/currency/horizon/confidence/sampling/quantile/tail/tie/insufficiency policy, five authored deterministic reference cases and negative/mutation criteria. No requirement ID/status/count changed and no risk implementation exists yet.
- P2 #2: C6 now excludes every unsupported factual assertion from ValidatedAnswer/conclusions, defines supported/partially-supported/abstention semantics and negative cases, and aligns receipts with accepted output only. Existing production citation/abstention errors remain unchanged; semantic support enforcement is still proposed, not claimed implemented.
- P2 #3: C5 distinguishes the inspected exact observation tuple, both existing refresh conflict buckets and separately reviewed economic comparability; proposed UCR identities retain revision/origin/concept/unit/dimensions/accounting context without fake DB IDs or new finance definitions.
- U2 now cites E4 and U3 cites E2/E4. Adjacent U rows/evidence families were checked without unrelated changes. C1 now has an explicit proposed representation lock, alternatives/tradeoffs, limits and negative/mutation matrix; it remains pending independent review and separate implementation authorization.
- Actual documentation checks: exact 67 IDs and unchanged 5/26/30/6 status totals; all candidate/acceptance fields remain unassigned/pending; nine contract sections and 65 local links; scoped whitespace/EOF checks. Static AST/source inspection confirmed importer identity fields and refresh slices without importing application modules. Standard-library rational arithmetic independently checked the five hypothetical VaR/ES references, permutation/tie weights and distinguishing interpolation/tail-rounding cases; these are documentation calculations, not application/contract tests. Proposed C1 tests were not run because C1 is not implemented.
- Exact scope/preservation checks compare the FIX1 entry non-environment inventory against closure: the same 376 paths, only these two documents changed, all 374 other files byte-identical, no additions/deletions. main/HEAD b8e89ef884b96f8fd8eec1ea4daba37b2f04295a and empty index remain; all three protected SHA-256 baselines match. Private backend/.env was never inspected, hashed or modified. No application tests, DB/services, SEC/providers/models, dependencies or Git writes.

Local disposition: GO for focused Astra re-review of the corrected documentation and proposed C1 representation; C1 implementation and Git Step 1 remain NO-GO pending independent verdict/coordinator authorization. Suggested eventual commit, only if separately requested: `docs: correct risk claim and identity contracts and specify proposed C1 representation`.
