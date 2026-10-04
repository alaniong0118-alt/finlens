# Standardized financial metrics

Item 6 adds a read-only service over existing `FinancialFact` rows. It never imports facts, writes normalized values, downloads filings, loads embeddings or calls an LLM. [Architecture](architecture.md) describes module ownership; the [verification report](../backend/reports/financial_metrics_verification.json) records the actual local dataset, coverage and source-row checks.

## Registry and concepts

`backend/app/financial_metric_registry.py` owns units, concept priority and formulas. The original US-GAAP concept is extracted from the importer-preserved `SEC Company Facts API: <concept>` source string, even when `FinancialFact.metric` was renamed to `Revenues`. Unknown source strings/concepts are rejected rather than guessed from a legacy metric label. Values retain the SEC numeric scale; no millions/billions conversion is applied.

| Metric | Accepted concepts in priority order | Meaning / current evidence |
|---|---|---|
| revenue | RevenuesNetOfInterestExpense; RevenueFromContractWithCustomerExcludingAssessedTax; Revenues; SalesRevenueNet | Four observed concepts with distinct economic bases; scope is resolved before restatement priority. A reported component is labelled rather than asserted to cover total issuer revenue. Never summed. |
| net_income | NetIncomeLoss | Reported net income/loss; observed. No substitution with earnings available to common shareholders. |
| diluted_eps | EarningsPerShareDiluted | Reported diluted EPS; observed. Source `USD/shares` is presented as `USD/share`. |
| gross_profit | GrossProfit | Reported gross profit. Conditional primary definition only; no stored observations. |
| operating_income | OperatingIncomeLoss | Reported operating profit/loss. Conditional; no stored observations. |
| cash_and_equivalents | CashAndCashEquivalentsAtCarryingValue | Instant cash and equivalents, not restricted cash. Conditional; no stored observations. |
| total_assets | Assets | Instant total assets. Conditional; no stored observations. |
| total_liabilities | Liabilities | Instant total liabilities, not liabilities plus equity. Conditional; no stored observations. |
| operating_cash_flow | NetCashProvidedByUsedInOperatingActivities | Signed operating cash flow. Conditional; no stored observations. |
| capital_expenditures | PaymentsToAcquirePropertyPlantAndEquipment | Positive cash payments for PP&E. Conditional; no stored observations. |

All monetary definitions require `USD`; other currencies and shares are rejected. The unobserved primary definitions are covered with SEC-like fixtures, not claimed as verified issuer coverage. They contain no speculative aliases. Broader acquisition/mappings need a separately authorized, audited milestone.

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

- Duration comes from start/end dates, including both endpoints: quarter 75–105 days, half-year 165–200, nine-month 245–295, annual 330–390. These reuse the existing classifier; observed durations are 89–98, 180–189, 271–280 and 364–371 days. Other durations are excluded.
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

There is no stored CapEx data to establish issuer sign conventions. The conditional payments definition assumes positive outflows; negative payment observations are unavailable, never converted with `abs`. A new CapEx concept/sign convention needs explicit review before adoption. Missing inputs, incompatible periods/units and zero/negative denominators return null with a reason.

## Provenance and financial institutions

Base observations expose canonical metric, selected fact ID, original concept, original value/unit, CIK, source label, stored period metadata, source fiscal labels, frame, filed date, form, accession, creation time and the server-built SEC filing URL. Creation time describes local storage, not refresh time. Alternative valid candidates remain visible. Derived observations expose formula, input roles/values/units/periods/fact IDs and the selected input provenance.

No ticker exceptions or sector guesses are used. Observed `RevenuesNetOfInterestExpense` identifies a banking revenue basis; gross profit/margin are then `not_applicable`. Other absent institution metrics are unavailable. Payment networks are not automatically classified as banks; their margin availability follows the selected denominator scope. Historical banking-basis detection is conservative and is not a substitute for future industry classification or formal cross-company comparability evaluation.

## API

- `GET /companies/{ticker}/financials/summary?period=quarter`
- `GET /companies/{ticker}/financials/metrics/{metric}?period=quarter&limit=40`

`period` accepts `quarter`, `half_year`, `nine_months`, `annual`, `instant`. Use `instant` for balance-sheet history. History is oldest-to-newest within the latest requested window; limit is 1–200. A history's availability describes its returned window. Each observation can independently be unavailable.

EPS history alone includes `comparability: {"value_basis": "reported_as_filed", "status": "unverified", "reason": "..."}`. Every value remains the exact selected SEC fact; filing vintages may have different split/restatement share bases. Consumers must not interpret this as a verified comparable trend. No adjustment factors are guessed. Non-EPS histories omit this field; optional metadata serialization supports the existing Pydantic 2.10 minimum.

Unknown company and unknown metric are HTTP 404 with distinct `detail.code` values. A known company/metric without observations returns HTTP 200, `status=unavailable`, null summary values or empty history, and a reason. Invalid period/limit is HTTP 422. Responses use dedicated Pydantic schemas. Legacy `/financial-summary`, `/financial-snapshot` and `/financial-history` contracts are retained; the frontend migration is future work.

Each endpoint uses two SELECTs: company lookup and one bounded company fact load. All metric selection/calculation occurs in the service. The coverage verifier loads companies/facts once each and normalizes all 35 in memory. No per-metric SQL, cache or duplicated metrics table exists.

## Verified coverage and limitations

Current 3,251 facts contain revenue/net income/EPS only, for the original ten issuers. Snapshot availability: reported revenue/net income/YoY revenue growth 10/35 (28.57%); EPS 9/35 (25.71%, Visa has none); net margin 3/35 (8.57%, GOOGL/NVDA/JPM); other metrics 0/35. The scope fix makes AAPL/AMZN/META/MSFT/TSLA/V/WMT net margins unavailable because only customer-contract observations are retained for their latest quarters. Their reported revenue, income and compatible YoY values remain source-faithful. JPM gross profit/margin are not applicable. All 25 additions have indexed filing evidence but no structured facts; filing readiness and financial coverage are separate states.

Real source rows/formulas were checked for AAPL, MSFT, JPM and WMT. GS, COST, JNJ, XOM, CAT and F were checked for honest absence. All-company coverage and unchanged table fingerprints are recorded. Fixture tests cover additional formulas/primary definitions; they do not prove real issuer coverage. Legacy ingestion already discarded some duplicate/concept candidates; the service cannot recover them. No currency conversion, Q4 synthesis, missing-period interpolation, as-of filing snapshot or full SEC numerical re-audit is provided.

The verifier now checks source rows for every returned all-company history point and representative annual revenue histories. It verifies ordering, kind/dates, exact values, IDs/concepts/accessions and official source URLs, including derived inputs. Twenty-six representative histories (716 observations) are also compared with real HTTP response contents, alongside ten summaries. The report retains initial validation separately from review-fix evidence.

Reproduce the recorded read-only checks from backend using `.venv/Scripts/python.exe -m scripts.verify_financial_metrics --api-url http://127.0.0.1:8000` against this baseline dataset and a running current backend. The script updates only its report and verifies exact database preservation; it does not ingest data. Historical report counts are not a fresh-clone data prerequisite.
