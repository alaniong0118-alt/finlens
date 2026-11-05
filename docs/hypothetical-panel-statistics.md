# Hypothetical factor-panel statistics development candidate

This separate diagnostic uses only user-entered hypothetical exact gross factors.
It supplies no real-market history, probabilities, forecasts, recommendations,
portfolio wealth, rebalancing, financing or source/calendar certification.
The Risk/Stress v1 receipt formats, browser UI and local replay remain unchanged.

## Boundary and availability

Proposed endpoint: `POST /hypothetical-panel-statistics`, with the exact same
seven-field request as [Risk Lab](hypothetical-portfolio-risk.md#api-and-receipt).
It shares the existing default-off `FINLENS_HYPOTHETICAL_RISK=1` development gate,
one calculation slot, cancellation ownership, JSON/encoding checks, 128 KiB body
and 1 MiB response caps. It remains absent from OpenAPI and restricted release
allowlists. This proposal changes no deployment, configuration or provider.
There is no new browser button or importer; the v1 replay reader must reject this
different method/schema. User-selected original v1 files still restore inputs
only, clear old output and require a new explicit calculation.

At most 8 assets and 120 supplied intervals enter through this API. Each interval
must contain one positive exact factor for every exposed asset. All original ID,
currency, decimal, date, continuity, confidence, horizon and declared-value
validation remains. Missing factors, gaps and nonpositive factors reject; no
observation is filled, omitted or inferred. Signed exposure amounts, declared
value, confidence and horizon are retained as form inputs but do not weight or
annualize these asset statistics.

## Definitions and units

For each asset and supplied interval t, simple return is r[t]=factor[t]-1.
All intervals have equal observation weight. Different date lengths are reported
in `interval_days` with `equal_interval_lengths=false`; nothing infers trading
frequency or converts them to equal calendar durations. Input dates do not prove
exchange-calendar completeness. No independence or statistical adequacy is claimed.

- Cumulative return: product of every supplied gross factor minus 1. Available
  with at least one interval. This is dimensionless `return_ratio`, not percent.
- Maximum drawdown: greatest `1 - current_index/running_peak` along that asset's
  factor path, starting with normalized index 1 before interval 0. Initial losses
  therefore count. The implementation tracks a relative asset index; no portfolio
  balance or signed-position wealth is constructed. Positive values mean decline.
- Sample mean return: sum(r)/N, exposed for arithmetic audit, with N>=1.
- Sample variance: sum((r-mean)^2)/(N-1), with N>=2.
- Sample covariance: sum((r_a-mean_a)*(r_b-mean_b))/(N-1), with the same complete
  N observations for every pair. Units are `return_ratio_squared`; diagonal entries
  equal the corresponding sample variances and the matrix is symmetric. Negative
  off-diagonal values are valid. No portfolio variance or correlation is derived.
- Sample volatility: the nonnegative square root of sample variance, per supplied
  interval, in `return_ratio`. No square-root-of-time scaling or annualization.

Drawdown witnesses are boundary indices: boundary 0 precedes interval 0 and
boundary k follows interval k-1. Strictly larger peaks replace the current peak;
equal peaks retain the earlier one. Equal maximum drawdowns retain the first
witness. A zero drawdown uses peak=trough=0. Unavailable drawdown has null witnesses.

## Exactness and unavailable values

Products, means, variances, covariances and drawdowns use exact bounded Fractions
from the existing kernel. Their JSON values use the existing numerator,
denominator and 18-place HALF_EVEN display representation. These exact values
remain authoritative even if rounded display is zero.

Volatility contains `{radicand, display, reason}`. Its exact value is
`sqrt(radicand)`; the radicand is an exact encoded Fraction. Irrational roots are
not asserted to be exact rational numbers. The root display rounds using integer
isqrt and an exact squared-midpoint HALF_EVEN comparison, independently of Decimal
context. No rounded number feeds later arithmetic. A perfect-square radicand has
the same representation and convention, without a separate floating approximation.

No observations yields `insufficient_observations` for path/mean measures. Fewer
than two yields that reason for variance, volatility and covariance. Constant
observations instead yield available exact zero variance/volatility. An individual
exact arithmetic bound yields `arithmetic_resource_limit` for affected measures;
independently valid measures remain available. Mean failure propagates to moments
and cross-covariances involving that asset. `covariance_complete` is false if any
matrix cell is unavailable; no PSD or portfolio calculation is claimed for an
incomplete matrix. Aggregate input/operation/output limits reject without a partial
receipt. The pure kernel additionally caps N*assets^2 at the existing operation
budget; the API's 8*120 bounds sit well below that cap.

## Receipt and audit

The success envelope has exactly `schema_id: hypothetical-panel-statistics-v1`,
the unchanged submitted `inputs`, and `result`. The result identifies method
`supplied-factor-panel-statistics-v1`, precision
`exact-rational-symbolic-root-display18-half-even-v1` and authority
`unverified_synthetic_inputs`. It contains the full normalized exact panel,
canonical sorted asset IDs, N and N-1, supplied interval lengths, per-asset
measures, drawdown witnesses, symmetric covariance rows in that asset order and
explicit limitations. The retained panel and mean/variance operands allow audit
without treating synthetic labels as market evidence.

This candidate has no persistence, file upload/download, external service or
browser storage. It reuses existing parsing and exact panel validation; no VaR/ES
formula, nearest-rank/tail-tie convention or v1 serialization is changed.
UI, browser/screen-reader acceptance, authenticated ownership, real-source rights,
calendar/actions/FX verification and real-market acceptance remain separate gates.
