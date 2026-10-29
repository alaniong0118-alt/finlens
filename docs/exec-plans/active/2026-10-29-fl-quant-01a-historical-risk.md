# FL-QUANT-01A — Pure historical portfolio VaR / Expected Shortfall

Status: completed within FL-QUANT-01A implementation scope; independent review pending
Roadmap phase: scoped enabling numerical task for requirement 10a; no product completion claim.

## Objective

Implement and independently test `historical-loss-es-v1` with synthetic exact
session factors, signed currency exposures, overlapping compounded horizons,
nearest-rank VaR and fractional-tail ES. Reproduce all six reference cases in
[the requirement](../../full-feature-requirements.md#proposed-10a-historical-varcvar-acceptance-specification).

## Current architecture and context

Read root AGENTS.md, .agent/PLANS.md, ROADMAP.md, engineering standards, the
complete 10a specification, shared research contracts, market_data_contracts.py,
market_returns.py and relevant return/alignment tests. Existing returns calculate
with exact rationals but expose approximate 80-digit gross factors. Those public
factors are unsuitable as exact original operands. Existing financial and market
modules will remain untouched. Shared C1-C9 references confer no authority.

Starting baseline (2026-10-29 Asia/Macau): main at
`d8be4dfc49a202a8de1bf0351eb5256f588f3952`; empty index. Only existing changes:
modified frontend/next-env.d.ts and two untracked protected report files.
SHA256 hashes matched the user's baseline:

- frontend/next-env.d.ts: F4E8976C19FC926644D72610BF1058BD6BF52ADD97E46A02BC0B912A751625C0
- backend/reports/canary-aapl_guarded_live_20261010_111844_3580610-publication.json: A783517D2875E39DF4C831C410265D0126FBF6A9D3DDBA1103F7BD61B057844C
- backend/reports/refresh-discovery-aapl_sec_discovery_20261010_002323_0671678.json: F8DF96C8890C0ECE1E1701B25BC5C43B879C359ECEB96ACB451A2A0DAA58BF7C

## Constraints

Create only backend/app/portfolio_risk.py, backend/tests/test_portfolio_risk.py
and this plan. Do not edit existing files, read/hash backend/.env, stage, commit
or push. Synthetic offline inputs only; standard library only in the kernel.
Invalid contracts/resource overruns raise; valid insufficient samples return
explicit unavailable values. Preserve independently valid currency results when
percentage denominators are absent/nonpositive.

## Non-goals

No raw-price/action/dividend engine, real-data adapter/acquisition, DB, routes,
ownership, services, UI, optimization, Monte Carlo or next roadmap increment.
No Reader/C1/browser regression reruns. No source, license or authentication claim.

## Implementation stages

1. Verify baseline and inspect authoritative semantics (done).
2. Define a frozen exact-factor boundary and bounded rational kernel.
3. Add six references, invalid-input controls and in-memory semantic mutants.
4. Run focused offline tests, syntax/whitespace and preservation checks; self-review.

Recovery: remove only the three newly created paths if this slice is abandoned;
never restore or overwrite protected existing work.

## Decisions

- 2026-10-29: Use explicit synthetic per-session exact Decimal/Fraction factors,
  never import approximate market_returns display factors. A future separately
  reviewed adapter must recover exact admitted operands from the existing engine.
- 2026-10-29: Require complete rectangular asset panels and contiguous supplied
  start/end session boundaries. This proves structural continuity only; without a
  trusted calendar an omitted real exchange session cannot be detected.
- 2026-10-29: Use bounded direct overlapping-window products for simplicity and
  auditability; no rolling division or scaling approximation.

## Discovered issues

- Initial 22-test run: the interpolated-threshold mutant caused division by zero
  in tie allocation before producing a result. This was an inadequate mutation
  control, not a production defect. Changed the single mutation location to the
  returned VaR estimator, after the correct tail audit, to isolate wrong quantile
  values. The subsequent 22-test run passed.
- Adding more independent arithmetic/resource tests briefly inserted a new test
  method before an existing `else`, causing an IndentationError at test line 371.
  Moved the complete method to its own class location; the expanded 25-test run
  passed. No kernel semantic change was needed for either test-harness issue.
- Source/calendar/rights/runtime admission is intentionally deferred.

## Progress

- [x] 2026-10-29: Verified expected HEAD, main, empty index and protected hashes.
- [x] 2026-10-29: Read required contracts and existing exact return semantics.
- [x] 2026-10-29: Implemented kernel and exact contract.
- [x] 2026-10-29: Completed six references, negative controls and five mutants.
- [x] 2026-10-29: Recorded actual verification, self-review and final preservation.

## Test and validation strategy

Use a standalone standard-library unittest module under the existing Python
interpreter with `-I -S -B`, avoiding configuration, site packages and I/O services.
Run actual source mutants in isolated module namespaces; each must pass its
baseline and fail numerical assertions after exactly one intended formula change.
The h=2 control must execute actual compounding before replacing only its horizon
branch with direct sqrt scaling of one-session VaR/ES.

Planned: all six references, exact tail receipts, signed multi-asset exposures,
percentage rules, hostile Decimal context, malformed/gapped panels, scalar and
aggregate resource boundaries, overflow and deterministic audit replay.
Syntax checks compile in memory; whitespace checks include untracked new files.
Actual commands/results are recorded below.

## Exact input/output contract and formulas

`calculate_historical_risk` has keyword-only arguments: `exposures`,
`reporting_currency`, `exposure_date`, `panel`, `horizon`, `confidence`, and optional
`portfolio_value` (default unknown). There are no implicit horizon/confidence
defaults or conversions. All financial numbers must be exact built-in Decimal or
Fraction values, not ints/floats/bools/strings/subclasses. The horizon is an exact
built-in int; dates are exact date values, not datetime or subclasses.

- `AssetExposure(asset_id, currency, amount)` declares signed initial notional,
  not share count. Amount may be positive, negative or zero. Currency is explicit
  and must equal the reporting currency. Currency syntax is three uppercase ASCII
  letters; this is not an ISO registry lookup or FX/usage authorization.
- `ExactFactorPanel(panel_id, factor_method_id, sessions)` is exclusively the
  synthetic exact-factor boundary. Each `FactorSession(session_id, start, end,
  factors)` covers a chronological positive interval; each preceding end equals
  the next start. Each interval contains exactly one `AssetFactor` for each
  exposed asset and no other asset. Gross factors must be strictly positive;
  zero-factor terminal-loss economics are outside this v1 domain, consistent with
  the existing positive-factor return boundary. No missing value is filled.
- All collections are exact tuples and records use the exact declared classes.
  Identifiers are 1..128 ASCII token characters matching
  `[A-Za-z0-9][A-Za-z0-9._:-]{0,127}`. Asset and session duplicates reject. Session
  order is contractual; asset/factor order is canonicalized by asset ID. A
  permutation of h=1 factors preserves numerical/tie-mass results; arbitrary h>1
  session permutations do not represent the same chronological experiment.
- Validation covers the entire supplied panel before arithmetic, including
  cells outside a usable requested horizon. Gaps, overlaps, unknown/missing assets,
  malformed records and resource excess raise `PortfolioRiskError` with a stable
  reason. No dropped prefix, interpolation, inner join, zero fill or backfill.

For M supplied intervals and horizon h, N=max(0,M-h+1). Every consecutive window
is used, with fixed initial exposures inside and across windows:

```text
G[j,i,h] = product(g[j,t] for t=i..i+h-1)
P&L[i,h] = sum(E[j] * (G[j,i,h] - 1))
L[i,h]   = -P&L[i,h]
rank     = ceil(alpha * N)
q        = sorted_losses[rank-1]
k        = N * (1-alpha)
n_gt     = count(L > q)
ES       = (sum(L for L > q) + (k-n_gt)*q) / k
tie_mass_per_observation = (k-n_gt) / count(L == q)
percent  = 100 * currency_risk / declared_positive_portfolio_value
```

No fees, financing, horizon annualization or square-root scaling. Negative q/ES
are preserved. Exposures are not rebalanced each session. Net exposure is sum(E),
gross is sum(abs(E)); the separate declared portfolio denominator is never
inferred from these exposure measures or certified by this kernel.

`HistoricalRisk` retains exact Fraction operands and results, full normalized
panel, signed positions, exposure date, currency, denominator, net/gross exposure,
method `historical-loss-es-v1`, precision ID, confidence, horizon, N, rank, k,
strict-tail and tie counts, actual overlapping-window flag, notices, and sorted
`LossScenario` records. A scenario ID is `(panel_id, first_session_id,
last_session_id)` plus inclusive start/exclusive stop indices into the retained
panel. These are reproducible supplied-scope labels, not globally authenticated
publication IDs. Sorting is by exact loss then scenario ID; values that display
identically still sort and receive tail mass by exact value.

Every scenario records its unnormalized tail observation mass: 1 strictly above
q, equal remaining mass per threshold tie, 0 below. Dividing these masses by k
would give normalized ES weights. For sparse/insufficient samples these weights
are unknown, not invented zeros. N<2 makes both measures unavailable as
`insufficient_scenarios`; N>=2 with k<1 retains VaR but makes ES unavailable as
`insufficient_tail_mass`. Rank is null if N<2. A supported horizon longer than
the panel yields no scenarios, not a parse/parameter error. Computational minima
do not establish statistical adequacy. For h>1 and N>1, overlapping is true; the
scenario indices disclose h-1 shared intervals between adjacent windows.

`RiskValue.exact` is Fraction or null with a reason. Its `display` property alone
returns an 18-place Decimal by exact integer remainder/parity HALF_EVEN rounding,
including signed zero. No rounded value is fed back into the kernel. Percentages
are percentage points, also exact; absent/nonpositive declared portfolio value
disables percentages only. Nonfinite/invalid denominators reject rather than
silently becoming unavailable. Empty synthetic inventories and singleton complete
inventories are valid insufficient-sample states, never available zero risk.

## Resource decisions and limits

All caps are inclusive and fixed in the module, not caller-selectable:

| Resource | Limit and counting rule |
|---|---|
| Assets | 35 exposures, all distinct |
| Supplied intervals | 6000 |
| Horizon | integer 1..252 supplied sessions |
| Factor cells | M * assets <=60000; exact complete rectangle required |
| Window factor operations | N * h * assets <=1000000, checked before computation |
| Input Fraction | numerator and denominator each <=2048 bits |
| Decimal preflight | <=128 coefficient digits, absolute tuple exponent <=256, before rational conversion; applies even to zero |
| Intermediate/result Fraction | numerator and denominator each <=8192 bits; every growth/product/sum/ES/percentage step bounded |
| Aggregate input numeric bits | <=4000000, sum of abs(numerator).bit_length()+denominator.bit_length() for alpha, optional denominator, exposures and factors |
| Additional output numeric bits | <=8000000 for scenario losses/tail masses, net/gross, alpha, k and available currency/percentage measures |

The output embeds the already separately budgeted normalized input panel; it does
not recount those inputs as additional output. Counts/date/ID widths also bound
non-numeric metadata. A single multiply/add can temporarily use approximately
twice the scalar bit cap before post-operation rejection; its operands are
already bounded. Decimal exponent preflight avoids giant power-of-ten allocation.
These conservative logical caps favor simple direct products over an additional
optimized numerical path. They are not wall-time, RSS, concurrency, transport,
serialization or worker-termination guarantees. No service deadline/cancellation
or persistence is introduced. Resource excess rejects the entire result.

Tests exercise default asset/session/cell/horizon and scalar inclusive limits and
one-over cases. The actual operation cap is reachable: M=5199, h=200, assets=1
produces N=5000 and exactly 1000000 products; another interval rejects before
products. Aggregate numeric bit budgets use measured small fixtures with reduced
caps at the exact counted boundary and one bit less, not claims of a valid
maximum-sized runtime payload. An actual five-session 2048-bit-factor product
also demonstrates intermediate overflow rejection without a numeric fallback.

## Reference and mutation evidence

| Synthetic reference | Exact numerical results |
|---|---|
| Threshold ties, alpha=4/5 | N=10, rank=8, k=2, VaR=4 USD, ES=7 USD; 4%/7%; strict count=1, ties=2, threshold mass=1/2 each |
| Fractional tail, alpha=17/20 | rank=9, k=3/2, VaR=4 USD, ES=8 USD; 4%/8%; threshold mass=1/4 each |
| Sparse tail, alpha=19/20 | rank=10, k=1/2, VaR=10 USD; ES unavailable: insufficient_tail_mass |
| All gains, alpha=1/2 | VaR=-3 USD, ES=-3/2 USD |
| Scaling / permutation | doubled exposure gives 8/14 USD; h=1 permutation preserves 4/7 and all loss/tie masses |
| Two-session 11/10,9/10,11/10,9/10 | N=3, rank=2, k=3/2; all losses=1 USD; VaR=ES=1 USD; all three tail masses=1/2 |

Five in-memory mutants of the actual kernel source compile and reach results,
then fail the intended exact-value assertions: reverse loss sign; interpolate
VaR (alpha=3/4 gives 15/4 instead of 4); average all losses >=q (6 instead of 7);
floor fractional tail mass (10 instead of 8); and apply direct sqrt(2) scaling of
the same one-session estimates (-10/10) to the h=2 estimator. That final mutant
executes the real three compounded two-session windows, then changes only h>1
estimator values to the wrong method. Instrumentation observes window lengths
`[2,2,2,1,1,1,1]`; complete h=2 scenarios still have losses [1,1,1], while wrong
VaR is negative and wrong ES is between 14 and 15. Each VaR/ES assertion fails
numerically against 1. The mutant's float sqrt is intentionally confined to the
wrong-method test, never an accepted input or production numerical operation.

Additional acceptance includes long/short multi-asset fixed exposure, exact
nonterminating-factor cancellation, equal-display/different-exact-loss ordering,
hostile Decimal precision/traps, signed HALF_EVEN ties, exact receipt replay and
immutability. An independent worst-first greedy tail-integral oracle checks four
loss datasets across five confidence levels. Invalid/coercive/nonfinite numeric
fields, mixed currencies, invalid dates/horizons/IDs and inconsistent/gapped/
mutable panels reject. Missing cells cannot hide in an insufficient horizon.

## Actual verification commands and results

All commands used repository root `D:\Projects\finlens-foundation`:

1. Baseline: `git rev-parse HEAD`, `git branch --show-current`,
   `git diff --cached --name-only`, `git status --short`, and PowerShell
   `Get-FileHash -Algorithm SHA256 -LiteralPath` on only the three named protected
   files. Expected main/HEAD, empty index and every protected hash matched.
2. `backend/.venv/Scripts/python.exe -I -S -B backend/tests/test_portfolio_risk.py`:
   first run 22 tests, one mutation-harness error; next run 22 tests passed;
   expanded-test editing run failed to parse (IndentationError); corrected final
   expanded run **25 tests passed in 1.141s**, zero failures/errors/skips.
   All five mutants are exercised inside those passing tests. No site packages,
   application bootstrap, live provider, DB, model or browser were used.
3. A PowerShell single-quoted here-string was piped to
   `backend/.venv/Scripts/python.exe -I -S -B -`. The standard-library checker
   used `compile(text, path, 'exec')` on both new Python files; strict UTF-8/BOM,
   trailing whitespace and single-final-newline assertions on all three new files;
   `git diff --check`; exact main/HEAD/empty-index assertions; exact tracked and
   untracked path-set assertions through `git diff --name-only` and
   `git ls-files --others --exclude-standard`; and `hashlib.sha256` on only the
   three protected paths listed above. **PASS**, exit 0. All protected hashes
   matched, the index stayed empty, and HEAD/main stayed unchanged. New-file
   insertion counts were emitted from `len(text.splitlines())` without staging;
   ordinary `git diff --stat` omits these untracked additions. Final documentation
   edits receive the same checks again before reporting.

## Source/provenance boundary and deferred gates

ExactFactorPanel is an explicit synthetic mathematical assertion, not admitted
market evidence. Identifiers, factor-method strings, structural continuity and
even exact rational representations cannot attest original factor truth. An
80-digit rounded market_returns factor wrapped in this type would still be the
wrong original economic input; the kernel cannot authenticate the caller's
claim. No existing MarketPublication, ReturnInterval or AlignedPanel adapter is
implemented, and this module imports none of those modules.

A separately authorized/reviewed real-data adapter must recover exact operands
from the current engine's established raw-close/action/dividend semantics,
without treating displayed factors as original rationals; prove per-asset
calendar/window/action completeness without inner-join dropping or bridging
excluded intervals; verify security/listing continuity, currency and any FX;
bind actual originals, publication/pins/vintages and return-method versions;
resolve source custody and operation-specific usage rights; and enforce trusted
owner/authentication/runtime budgets. With no trusted calendar, a real missing
exchange session hidden inside one declared contiguous interval is undetectable.
An explicit synthetic test demonstrates that such valid labels retain
`unverified_synthetic_inputs` authority and a calendar-not-verified notice.

No real-source eligibility, licensed-data custody, authenticated holdings, API/UI,
browser, live market/provider, DB, deployment or statistical adequacy gate has
been exercised. Those remain deferred. This increment does not complete 10a or
authorize the next roadmap item.

## Completion criteria

All six references and targeted controls pass; all intended mutants are killed
for their intended numerical reason; only three new paths; baseline/index and
protected hashes preserved. GO means ready for independent financial correctness
review, never accepted product/source/runtime behavior.

## Final outcome

Kernel and tests implemented in the exact three new paths. Self-review found no
remaining financial formula issue within the specified synthetic domain. Existing
market/finance modules and contracts are untouched. Syntax/whitespace, exact-scope
and protected-state checks passed. The only tracked modification remains the
pre-existing frontend/next-env.d.ts; untracked files are the two pre-existing
reports and the three new task files. No backend/.env access, staging, commit,
push, data/source/runtime operation or broader completed-suite rerun occurred.

**GO for independent Astra 6 High financial correctness review** of this bounded
synthetic implementation. That review has not run; GO is readiness only. Real-data
and product integration remain NO-GO within this increment. This completed record
stays at the exact user-required active-plan path rather than introducing a fourth
path by moving it.

Suggested commit after independent review:
`feat(quant): add exact historical portfolio VaR and ES kernel`.
