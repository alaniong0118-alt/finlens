# Standardized financial metrics

Item 6 adds a read-only service over existing `FinancialFact` rows. It never imports facts, writes normalized values, downloads filings, loads embeddings or calls an LLM. [Architecture](architecture.md) describes module ownership. [Item 6 verification](../backend/reports/financial_metrics_verification.json) preserves its initial dataset; [Item 7 verification](../backend/reports/structured_financial_verification.json) records expanded coverage. Ingestion follows the separate [sync policy](data-sources.md#structured-financial-sync), without changing these selection contracts.

## Registry and concepts

`backend/app/financial_metric_registry.py` owns units, concept priority and formulas. The original US-GAAP concept is extracted from the importer-preserved `SEC Company Facts API: <concept>` source string, even when `FinancialFact.metric` was renamed to `Revenues`. Unknown source strings/concepts are rejected rather than guessed from a legacy metric label. Values retain the SEC numeric scale; no millions/billions conversion is applied.

| Metric | Accepted concepts in priority order | Meaning / current evidence |
|---|---|---|
| revenue | RevenuesNetOfInterestExpense; RevenueFromContractWithCustomerExcludingAssessedTax; Revenues; SalesRevenueNet | Four observed concepts with distinct economic bases; scope is resolved before restatement priority. A reported component is labelled rather than asserted to cover total issuer revenue. Never summed. |
| net_income | NetIncomeLoss | Reported net income/loss; observed. No substitution with earnings available to common shareholders. |
| diluted_eps | EarningsPerShareDiluted | Reported diluted EPS; observed. Source `USD/shares` is presented as `USD/share`. |
| gross_profit | GrossProfit | Reported gross profit; not applicable to observed banking revenue bases. |
| operating_income | OperatingIncomeLoss | Reported operating profit/loss; no unsupported substitutes. |
| cash_and_equivalents | CashAndCashEquivalentsAtCarryingValue | Instant cash and equivalents, not restricted cash. |
| total_assets | Assets | Instant total assets. |
| total_liabilities | Liabilities | Instant total liabilities, not liabilities plus equity. |
| operating_cash_flow | NetCashProvidedByUsedInOperatingActivities | Signed operating cash flow; YTD and annual flows remain separate from quarters. |
| capital_expenditures | PaymentsToAcquirePropertyPlantAndEquipment | Positive cash payments for PP&E; negative observations are retained but not used in FCF. |

All monetary definitions require `USD`; other currencies and shares are rejected. Item 7 acquires only these already reviewed concepts/units. They contain no speculative aliases. Source presence does not establish compatible current-period coverage; broader mappings still require separate review.

### Revenue economic scope

`REVENUE_CONCEPTS` centrally records basis, meaning and whether a concept establishes a margin denominator. Definitions were checked against [FASB 2026 documentation](https://xbrl.fasb.org/us-gaap/2026/elts/us-gaap-doc-2026.xml) and [2018 legacy documentation](https://xbrl.fasb.org/us-gaap/2018/elts/us-gaap-doc-2018-01-31.xml). Only taxonomy documentation was consulted; no new company observations were acquired.

| Concept | `revenue_basis` | Scope / margin eligibility |
|---|---|---|
| Revenues | total_revenue | Broad earning activities, including interest before interest expense; approved total basis for non-bank margins. |
| RevenueFromContractWithCustomerExcludingAssessedTax | customer_contract | Customer performance obligations excluding collected taxes; may omit non-contract revenue. Standalone observations do not establish a consolidated margin denominator. |
| SalesRevenueNet | net_sales | Normal-course goods/services less returns, allowances and discounts; does not establish other earning activities. Standalone observations do not establish a consolidated margin denominator. |
| RevenuesNetOfInterestExpense | net_interest | Broad earning activities with interest expense deducted; approved financial-institution denominator. |

For one exact period, a known total takes precedence over components regardless of filing date. Net-interest and other conflicting bases are unavailable with all candidates in `alternatives`; different components without a known total are likewise ambiguous. Within one compatible basis, existing latest-filing and deterministic tie breaks remain. A single component can be returned as reported revenue with its explicit basis, but cannot be used to claim a consolidated margin. Equal values alone do not establish scope equivalence.

YoY requires the same basis or an explicit centrally reviewed equivalence. `REVENUE_EQUIVALENCES` is empty in production: none of these distinct families is universally interchangeable on current evidence. Fixtures demonstrate that a future explicit declaration is required before a cross-family transition works; they do not approve that declaration for real issuers. No ticker rules or speculative aliases were added.

## Period and selection policy

- Duration comes from start/end dates, including both endpoints: quarter 75–105 days, half-year 165–200, nine-month 245–295, annual 330–390. These reuse the existing classifier; the initial Item 6 dataset had durations of 89–98, 180–189, 271–280 and 364–371 days. Other durations are excluded from normalized metrics, even if valid source observations are retained during sync.
- Instants require an end date and no start date. Duration metrics require both dates. Stored `period_type` does not override dates. Half-year/nine-month observations remain separate YTD series; cash-flow YTD is never presented as a quarter.
- SEC `fy`/`fp` describe filing context and may label comparative observations with later years/quarters. Preserve them as `source_fiscal_year`/`source_fiscal_period` in provenance. Fiscal normalization uses unique observed annual revenue boundaries. A current year can use a YTD start immediately following a known annual end. Ambiguous boundaries leave normalized labels null.
- Normalized fiscal year means the calendar year containing the fiscal year end. `fiscal_label_basis` records that convention/boundary inference. Quarter starts are matched to the fiscal anchor's 0/13/26/39-week positions within 14 days, accommodating 52/53-week calendars. Annual/YTD series remain distinct. Calendar frames are retained as source metadata, not fiscal-quarter authority.
- Current-year inference uses the actual YTD start after an observed annual boundary. A prior full 364–371-day year supports a 52/53-week end-date range; assign a year only when the whole range falls in one calendar year. Two consecutive 365/366-day years with identical month/day boundaries can instead establish a calendar schedule (including Jan–Dec issuers). A single calendar-like year is insufficient near New Year; transition/stub calendars do not support projection. Preserve a supported quarter with `fiscal_year=null` when uncertain. A later observed annual may refine null to a known end year; it never overrides a guessed year because none was assigned.
- Group by exact start/end dates, classified kind and expected unit. Resolve revenue scope first. Within compatible candidates select latest filed date, then concept priority, period-appropriate form (10-Q for interim periods, 10-K for annual), amendment, accession and fact ID. Later filings may restate the same period; historical period ordering still follows reporting dates, never filed dates. Selected and competing/excluded source rows are exposed; values are never averaged.
- Summary uses the latest requested revenue period, falling back to another available base metric only when no revenue period exists. Duration metrics must match that exact period; instant metrics must match its end date. An older metric is not silently substituted into a newer snapshot.
- Direct Q4 observations may appear; no FY-minus-interim Q4 derivation is implemented. For example, stored MSFT June 2026 data is annual; its latest directly reported quarter in the dataset ends March 2026.

## Derived metrics

Calculations use Decimal with 28-digit precision. JSON values are decimal strings, including unrounded ratios; `0.25` means 25%, not 0.25%.

| Metric | Formula | Required compatibility |
|---|---|---|
| gross_margin | gross_profit / revenue | Same exact duration/period, USD; positive denominator. |
| operating_margin | operating_income / revenue | Same exact duration/period, USD; positive denominator. |
| net_margin | net_income / revenue | Same exact duration/period, USD; positive denominator. Negative earnings remain negative margins. |
| free_cash_flow | operating_cash_flow - capital_expenditures | Same exact duration/period, USD; CapEx payment nonnegative. Signed OCF and negative FCF are valid. FCF is this explicit non-GAAP calculation. |
| revenue_growth_yoy | (current - prior) / prior | Same period kind, positive prior revenue, unique comparable prior-year observation. |

YoY requires both start-date and end-date gaps of 357–378 days, duration difference at most nine days, and matching normalized fiscal period when both labels are known. Missing or multiple candidates are unavailable. No adjacent-row/sequential comparison or SEC filing-year match is substituted.

YoY additionally requires compatible revenue bases. All three margins require an approved total/net-interest denominator; component-only revenue yields null with a scope reason. Issuers showing a net-interest basis cannot receive margins using pre-interest total revenue. Derived input metadata carries the selected revenue basis alongside the original source fact.

The payments definition requires positive outflows; negative payment observations are unavailable, never converted with `abs`. Item 7 retained 3,296 CapEx observations across 25 issuers, including nine negative observations. Their presence does not authorize changing the convention. A new CapEx concept/sign convention needs explicit review before adoption. Missing inputs, incompatible periods/units and zero/negative denominators return null with a reason.

### Gross Margin local-data diagnosis (2026-10-10)

Read-only diagnosis at Git baseline `eae5c9f`; no ingestion or metric-selection changes. The service currently uses reported `GrossProfit / revenue`, equivalent to `(revenue - cost_of_revenue) / revenue` only when economic coverage is compatible. No cost-of-revenue observations are stored for the four issuers below; cost concepts are not currently imported by the registry-driven sync.

| Issuer | Latest direct quarter | Stored revenue (USD) | Stored GrossProfit (USD) | Result / cause |
|---|---|---:|---:|---|
| TSLA | 2026-04-01–2026-06-30 | 28,236,000,000 (`Revenues`) | 4,751,000,000 | Available: 16.8260%; approved total-revenue denominator. |
| AAPL | 2026-03-29–2026-06-27 | 109,417,000,000 (`RevenueFromContractWithCustomerExcludingAssessedTax`) | 54,770,000,000 | Scope safeguard rejects the customer-contract denominator; inputs otherwise match dates, USD and accession. |
| AMZN | 2026-04-01–2026-06-30 | 200,606,000,000 (customer-contract concept) | Missing | Stored GrossProfit ends 2009-12-31; no current compatible numerator or costs. |
| COST | 2026-02-16–2026-05-10 | 70,527,000,000 (customer-contract concept) | Missing | Stored GrossProfit ends 2019-09-01; no current compatible numerator or costs. |

AAPL inputs share accession `0000320193-26-000020`. Local `chunk_0001` contains the consolidated statement: total net sales 109,417, total cost of sales 54,647 and gross margin 54,770 (millions). This supports a manual source-traced calculation of approximately 50.0562%, but the table text is not a normalized cost fact or a machine-readable economic-scope declaration. The service deliberately does not parse excerpts into new financial inputs or waive scope checks based on matching numbers/accessions. AAPL annual FY2025 also has matching USD revenue 416,161,000,000 and GrossProfit 195,201,000,000, rejected for the same scope reason.

AMZN FY2025 revenue is 716,924,000,000; COST FY2025 total `Revenues` is 275,235,000,000. Both lack matching annual GrossProfit. Changing aliases alone cannot create these missing observations. No operating/total expenses or operating income may substitute for cost of revenue. `FinancialFact` stores concept, dates, unit, fiscal metadata, frame and accession, but no explicit XBRL dimensional context; unknown coverage must not be treated as proven compatible.

The four live summary endpoints returned HTTP 200 with these backend states. Research UI displays the returned status/reason without computing margins. Smallest future remediation: reviewed, provenance-backed scope support for AAPL's reported gross-profit denominator; for AMZN/COST, separately authorized acquisition of exact-period authoritative gross profit or cost-of-revenue observations plus reviewed revenue/cost scope compatibility. COST membership revenue versus merchandise costs needs explicit treatment. Do not enable customer-contract denominators globally or reuse old gross-profit periods.

Permanent isolated API/service regressions cover compatible total-revenue/GrossProfit inputs for all four ticker labels (synthetic fixtures, not real coverage), missing/wrong-period/wrong-unit inputs, rejected unreviewed expense/cost fallbacks, and AAPL-like same-filing scope rejection. Validation: `backend/.venv/Scripts/python.exe -B -m pytest tests/test_financial_metrics.py -q` from `backend`: **80 passed**. No production logic or database data changed.

### AAPL bounded consolidated-coverage correction

Following the diagnosis, `GROSS_MARGIN_COVERAGE` in the existing metric registry now explicitly authorizes **only** the reviewed AAPL Q3 FY2026 input pair. The local condensed consolidated statement in `aapl-20260627.htm`, `chunk_0001`, establishes that both source concepts cover the same consolidated operations: product plus service net sales = 109,417 million; product plus service cost of sales = 54,647 million; reported gross profit = 54,770 million. Thus `GrossProfit / revenue` equals `(revenue - cost_of_revenue) / revenue` for this pair. The cost amount is supporting filing evidence, not a newly inserted or inferred financial fact.

Approval is pinned to CIK `0000320193`, accession `0000320193-26-000020`, exact dates 2026-03-29–2026-06-27, USD, `10-Q`, filed 2026-07-31, both original concepts and both exact source values. Source row IDs are not hardcoded. Selected input provenance remains exposed. New dates, accessions, amendments, concepts or changed values fail closed and need a fresh scope review. The existing revenue basis remains `customer_contract`; neither YoY equivalences nor operating/net-margin policies are expanded. Gross-margin inputs must additionally share the same filing accession, including ordinary total-revenue inputs.

Current-code FastAPI route verification over the read-only local database returned HTTP 200: AAPL available `0.5005620698794520047159033788` (**50.0562%**), TSLA unchanged `0.1682603768239127355149454597`; AMZN/COST unavailable. This was an in-process API test, not a restart or proof that an already-running server loaded the edited code. AAPL annual and unreviewed historical periods remain unavailable under the scope safeguard. No frontend, database, acquisition or financial-selection changes were made. Focused independent Astra review is required before commit.

Validation after the correction: `python -B -m pytest tests/test_financial_metrics.py -q` from `backend` — **97 passed**. The existing listener on port 8000 still returned HTTP 200 with the previous unavailable scope result; it was left running unchanged as required. Loading the corrected code into that service is deferred until after independent review and separately permitted service recovery. Read-only counts remained 35 companies, 58,881 facts, 3,267 chunks and 3,267 embeddings.

The focused review identified an ambiguity defect: a contradictory same-filing observation could lose the row-ID tie break and leave the selected approved value available. The exception now inspects all eligible raw observations independently of ranking for each approved concept, matching issuer, accession, exact dates, unit, form and filed date. Their distinct values must equal the singleton approved source value. Conflicting revenue or gross profit rejects the exception in either insertion order; identical equivalent duplicates remain valid. Calendar frame/fiscal annotations do not establish different economic scopes. Unrelated issuers, accessions, concepts, dates, units or filing vintages are excluded from this conflict check; their ordinary selection behavior is unchanged.

Validation after the ambiguity correction: **117 financial-metric tests passed**, including four conflicting-input/order combinations, four identical-duplicate/order combinations and twelve unrelated-context checks. Current-code in-process API over read-only stored data returned AAPL **50.0562%**, TSLA **16.8260%**, AMZN/COST unavailable, all HTTP 200. No development data or service changes were performed.

## Inactive bounded revenue authorization foundation

`app/revenue_scope_authorizations.py` defines two independent permissions: `select:revenue` permits one exact observation within an otherwise ambiguous component-revenue group; `denominator:net_margin` permits one exact, already selected revenue/net-income pair for Net Margin. Both production registries and the withdrawal registry are **empty**. No AAPL Net Margin or FY2018/FY2019 history approval is activated. Existing formulas, source mappings, basis compatibility, comparison policies and the separate AAPL Gross Margin exception remain unchanged. Optional `scope_authorization` provenance is emitted only when a new permission actually applies; absent metadata is omitted from serialized responses.

Frozen records bind a permission/approval ID/version, complete reviewed raw-candidate manifest, exact CIK/source/taxonomy/concept/dates/period kind/USD/Decimal/accession/form/filed identity, and evidence fingerprints. Source identity excludes local row IDs, insertion order, frames and fiscal annotations. Independently supplied `SourceEvidence` binds the complete document content, accession-relative document identity, statement location and character range, exact XBRL context, verified dimensions and reviewed economic scope. Numeric equality cannot establish consolidated scope. The first release accepts only explicitly verified undimensioned contexts (`dimensions=()`); unknown dimensions, segment/member contexts or incomplete evidence fail closed. Revenue evidence cannot be classified as net income, and vice versa.

The evaluator scans all eligible raw observations for the company, period kind and end, including changed starts. Exact duplicate source annotations deduplicate; conflicting values for the same source fail regardless of row ranking. Different values across filing vintages require separate restatement analysis and are conservatively rejected even with a renewed manifest. Additional filings, same-value amendments, changed boundaries or competing scopes invalidate the old manifest. Renewed same-value reviews must bind every current candidate and select the latest filed observation; an older source is never preferred to obtain availability. Independently reviewed consolidated totals must agree, while a reviewed component may legitimately differ from a total. Rejected raw alternatives remain visible in provenance.

Versions require explicit revocation or supersession; incompatible/overlapping approvals fail closed. Lineage checks span the complete permission registry and withdrawal history, so a successor in another scope or a withdrawn newer version cannot silently reactivate an older approval. Changed/missing/ambiguous document or context evidence invalidates its fingerprint. Denominator permissions additionally require the named metric, exact numerator/revenue pair and identical company, period, unit, accession, form and filed date. Selection never grants denominator permission, denominator permission never resolves revenue ambiguity, and neither relabels the original concept/basis or creates global revenue equivalences.

The [inactive original SEC evidence adapter](sec-evidence-adapter.md) now provides an offline verification boundary for explicitly pinned local originals and capture receipts. Its production evidence-policy registry is **empty**, alongside the financial permission registries. The normal loader consequently supplies no evidence and performs no additional artifact reads or evidence queries. Stored Company Facts rows and cleaned chunks alone cannot establish original context/dimensional evidence. `SourceEvidence` remains an internal evaluation input, never a public approval parameter. Future activation requires independent review of source provenance, statement/context/accounting scope, complete manifests and versioned policies, plus explicit reviewed registry changes. Missing evidence is not reconstructed from approval records, numeric equality or frame labels. No network requests, database writes or restatement calculations are introduced. Synthetic contract tests live in `tests/test_revenue_scope_authorizations.py`; offline adapter tests live in `tests/test_sec_evidence_adapter.py`.

Validation of the inactive foundation uses pure in-memory fixtures and a narrowly scoped read-only AAPL comparison to commit `b1bb70a`: five summaries and twenty Revenue/Revenue YoY/Net Margin/Gross Margin histories serialize identically. Current AAPL Gross Margin remains available; Net Margin, FY2018 half-year Revenue and FY2019 half-year Revenue YoY remain unavailable. This is in-process verification, with no restart or claim that the running service loaded the new code. Financial activation, evidence-provider isolation and the conservative vintage policy still require Astra follow-up review.

## Provenance and financial institutions

Base observations expose canonical metric, selected fact ID, original concept, original value/unit, CIK, source label, stored period metadata, source fiscal labels, frame, filed date, form, accession, creation time and the server-built SEC filing URL. Creation time describes local storage, not refresh time. Alternative valid candidates remain visible. Derived observations expose formula, input roles/values/units/periods/fact IDs and the selected input provenance.

No ticker exceptions or sector guesses are used. Observed `RevenuesNetOfInterestExpense` identifies a banking revenue basis; gross profit/margin are then `not_applicable`. Other absent institution metrics are unavailable. Payment networks are not automatically classified as banks; their margin availability follows the selected denominator scope. Historical banking-basis detection is conservative and is not a substitute for future industry classification or formal cross-company comparability evaluation.

## API

- `GET /companies/{ticker}/financials/summary?period=quarter`
- `GET /companies/{ticker}/financials/metrics/{metric}?period=quarter&limit=40`

`period` accepts `quarter`, `half_year`, `nine_months`, `annual`, `instant`. Use `instant` for balance-sheet history. History is oldest-to-newest within the latest requested window; limit is 1–200. A history's availability describes its returned window. Each observation can independently be unavailable.

EPS history alone includes `comparability: {"value_basis": "reported_as_filed", "status": "unverified", "reason": "..."}`. Every value remains the exact selected SEC fact; filing vintages may have different split/restatement share bases. Consumers must not interpret this as a verified comparable trend. No adjustment factors are guessed. Non-EPS histories omit this field; optional metadata serialization supports the existing Pydantic 2.10 minimum.

Unknown company and unknown metric are HTTP 404 with distinct `detail.code` values. A known company/metric without observations returns HTTP 200, `status=unavailable`, null summary values or empty history, and a reason. Invalid period/limit is HTTP 422. Responses use dedicated Pydantic schemas. Legacy `/financial-summary`, `/financial-snapshot` and `/financial-history` contracts are retained; Item 8 Research Mode consumes the standardized routes while retaining the legacy APIs.

The financial service uses two SELECTs: company lookup and one bounded company fact load. After refresh metadata migration, API reads add one version SELECT in a REPEATABLE READ, READ ONLY transaction (three SELECTs total); the unchanged service has no per-metric queries. See [version consistency](data-freshness.md#freshness-and-read-consistency). All metric selection/calculation occurs in the service. The coverage verifier loads companies/facts once each and normalizes all 35 in memory. No per-metric SQL, cache or duplicated metrics table exists.

Research Mode also exposes `POST /companies/{ticker}/research-answer` with `{ "question": "What was Apple's latest quarterly revenue?" }`. This bounded value-question wrapper reuses the same service without changing its selector semantics. Explicit quarterly/annual uses summary alignment; latest available selects the newest actual normalized observation (including unavailable), preferring shorter direct periods on equal end dates. Instant values are as-of. Response `observation` is the exact NormalizedMetric contract; EPS also carries the existing as-filed/unverified comparability warning. Display rounding never changes provenance values. Unknown/ambiguous or unsupported causal/segment/arbitrary-date/multiple-metric questions return `not_matched`; recognizable company mismatch returns `company_mismatch`. Explicit fiscal dates/comparisons follow the additive contract below. No provider or indexed filing is required. See [Research Answer scope](product-spec.md#deterministic-research-answers).

## Historical values and comparisons

`POST /companies/{ticker}/research-answer` additionally recognizes one fiscal year (annual by default) or an explicit `Q1`–`Q4` plus year, limited to 1900–2099. It returns `answer_kind=historical_metric` with `requested_period={fiscal_year, quarter}` and the existing `observation`. Historical lookup uses shared metric/reporting anchors and one unique normalized fiscal label, then the unchanged observation selector. Instant values use that reporting end. Missing or ambiguous fiscal labels return null/reason, never filing FY or calendar-quarter guesses.

Two explicit periods plus a bounded comparison connector return `answer_kind=period_comparison`; `observation` is null. `comparison` contains earlier/later requested labels and complete normalized observations, status/reason, exact Decimal `absolute_change`, optional `percentage_change` ratio, its status/reason and direction. The answer wrapper provides formatted change/value text. One revenue-growth calculation over an explicit interval compares revenue levels; comparisons of separately identified growth observations are unsupported. Latest-value behavior remains unchanged; there is no frontend selector or per-year HTTP fan-out.

Explicit `YoY`/`year-over-year`/`year-to-year` wording is preserved before alias consumption. One adjacent-year interval expressed as a range or from/to can compare matching annual/same-quarter revenue periods, subject to all existing compatibility checks. Non-adjacent explicit YoY requests and compare/vs/between requests for two YoY rates return `not_matched`. Ordinary multi-year revenue comparisons are labelled cumulative period-to-period change. A single-period YoY request retains the existing canonical YoY metric. No CAGR or annualization is added. A structured mathematical-intent preflight runs before company/metric alias consumption. Its token stream retains `%` and `/`, treating apostrophes, hyphens, parentheses and whitespace as boundaries. It distinguishes metric-level changes, changes targeting growth itself, margin point differences, relative percentages and per-year/annualized requests. Growth with a change verb is conservatively unsupported even with possessive/reordered wording or compound targets. Slash/per-year denominators survive parentheses and fiscal-year punctuation; annualization and unknown slash operations fall back. Relative margin changes (including grow/grew) return `not_matched`; ordinary margin comparisons retain labelled percentage-point differences. Ordinary revenue `% change` remains supported. Classification does not expand the closed question grammar: unfamiliar wording, including unsupported explicit operator phrases, may still fall back. This is bounded recognition, not universal natural-language understanding.

Recognition now carries a typed internal `FinancialOperation` through dispatch: requested operation, canonical metric, fiscal requests, operand structure, support/ambiguity status, original mathematical intent and rejection reason. Binding distinguishes single observations, revenue-level intervals, adjacent-year YoY, cumulative growth and margin point differences. A mandatory agreement check verifies operation, metric, operand cardinality/shape, chronological matching fiscal slots and retained mathematical qualifiers before loading facts. Only explicitly bound revenue interval operations dispatch to revenue levels; single growth values retain `revenue_growth_yoy`. FinancialMetrics still owns source selection, actual date/unit/economic-basis compatibility and all arithmetic. No public API fields change.

`Compare 2024 revenue growth and 2025 revenue growth` identifies two growth observations and returns `not_matched`, even without the word YoY. Ambiguous compare/vs growth wording also abstains; `2024-2025 revenue growth` and `revenue growth from 2024 to 2025` remain supported intervals. Targeted translation maps `％` to `%` and `／`, `∕`, `⁄` to `/` before classification. It does not normalize period ranges or assume arbitrary slash expressions are supported division. Unknown mathematical symbols and uninterpreted non-ASCII numeric notation fail closed. Relative margin changes, explicit EPS percentage changes, growth-rate comparisons, annualization/CAGR and arbitrary division remain unsupported; ordinary margin point and EPS as-filed absolute comparisons remain available. See the [API handoff regressions](../backend/tests/test_research_operation_handoff.py) and [verification record](../backend/reports/historical_answers_verification.json).

Comparisons require chronological different fiscal years, matching annual or same-quarter slots, equal units, duration difference at most nine days, and start/end gaps within `14 + floor(year_gap/4) + 1` days of `365 * year_gap` (week calendars/leap days). Instant comparisons check end-date alignment. Fiscal-calendar shifts and mixed kinds fail safely. Revenue requires the registry's basis compatibility; derived operands additionally require matching role/metric/unit sets and compatible revenue inputs. Existing source scope/vintage selection is not changed.

Absolute change is `later - earlier`. Percentage change is `(later - earlier) / earlier` only with a positive baseline, calculated with 28-digit Decimal precision. A zero/negative earlier value retains valid absolute comparison, with percentage unavailable and a reason. Positive-to-negative changes remain mathematically defined; equality yields zero. Ratio differences use percentage points, with relative growth not applicable. EPS absolute differences are explicitly reported-as-filed/unverified; no percentage growth is claimed without share-basis comparability. Every selected/alternative source and derived operand remains inspectable on both sides.

For historical periods the existing latest-filed compatible source may be a later comparative/restated filing. This does not establish an original-filing or as-of series, nor comparable restatement/share bases across vintages. No averaging, Q4 synthesis, YTD conversion, currency conversion, predecessor merging or arbitrary date reasoning is added. See [product behavior](product-spec.md#historical-and-comparative-research-answers) and [real-data acceptance](../backend/reports/historical_answers_verification.json).

## Verified coverage and limitations

Item 6's historical baseline contained 3,251 facts for ten issuers. Item 7 now has **58,881 observations across 35/35 companies**, retaining every original row unchanged. Supported source revenue/net-income observations exist for 35/35; EPS for 34/35. Current snapshot coverage below is measured after scope/date/unit selection:

| Metric | Quarterly summary available /35 | Annual summary available /35 |
|---|---:|---:|
| revenue | 34 | 32 |
| gross_profit | 8 | 8 |
| operating_income | 23 | 23 |
| net_income | 32 | 31 |
| diluted_eps | 34 | 33 |
| cash_and_equivalents | 30 | 29 |
| total_assets | 35 | 34 |
| total_liabilities | 25 | 24 |
| operating_cash_flow | 5 | 34 |
| capital_expenditures | 3 | 21 |
| free_cash_flow | 3 | 21 |
| revenue_growth_yoy | 33 | 31 |
| gross_margin | 4 | 4 |
| operating_margin | 13 | 14 |
| net_margin | 21 | 20 |

Instant summary values match the selected period end. Annual cash-flow coverage is more useful than quarterly availability because many issuers report YTD flows. Four banking-basis issuers have gross profit/margin `not_applicable`. AXP's latest revenue is unavailable because customer-contract and net-interest observations coexist. CAT/F/MA latest net income lacks a compatible primary fact, although historical observations exist. Visa has no supported EPS. COST latest YoY is unavailable due to a revenue-basis transition. No speculative mappings fill these gaps.

AAPL/MSFT retain source-faithful revenue/income/EPS and unavailable component-denominator margins. XOM stays current CIK 0002115436 with 22 supported observations. Official current-registrant comparative periods are retained, with no independent predecessor acquisition. No annual revenue or established fiscal-year label is claimed for that limited response. Filing readiness and financial coverage remain separate.

Real expanded source rows/formulas were checked for AAPL/MSFT/JPM/JNJ/XOM/COST/CAT/F, including values, concepts, dates, units, accessions, filed dates, source URLs and derived inputs. All original fact fingerprints and company/chunk/vector hashes were preserved. Source responses may no longer contain candidates discarded by legacy ingestion, so sync cannot guarantee complete vintage recovery. No currency conversion, Q4 synthesis, interpolation, as-of filing snapshot, adjusted EPS comparability or full filing-text numerical re-audit is provided. Legacy financial routes retain their earlier analysis contracts; Research Mode should consume the standardized routes.

Item 7's verifier checks all-company source histories, representative annual revenue/cash-flow/FCF histories and derived inputs. Sixteen summaries and 56 histories across eight representatives were compared with real HTTP bodies, alongside catalog/health checks. Item 6's earlier verification remains separately recorded.

For this local Item 7 baseline, run `.venv/Scripts/python.exe -m scripts.verify_financial_sync --api-url http://127.0.0.1:8000` from backend against a running current backend. It reads the database and writes only its report. Its ID-specific baseline is a local preservation artifact, not a fresh-clone prerequisite. The older `verify_financial_metrics` intentionally verifies the frozen Item 6 dataset; do not overwrite that historical report to accommodate expanded data.
