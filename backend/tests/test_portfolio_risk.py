"""Synthetic-only numerical acceptance; runnable with Python -I -S -B.

No application bootstrap, provider, database, environment or external fixture.
Semantic mutants compile isolated copies of the actual kernel source in memory.
"""
import ast
from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime, timedelta
from decimal import Decimal, Inexact, Rounded, ROUND_DOWN, localcontext
from fractions import Fraction
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

SOURCE_PATH = Path(__file__).resolve().parents[1] / "app" / "portfolio_risk.py"
SOURCE = SOURCE_PATH.read_text(encoding="utf-8")
SPEC = importlib.util.spec_from_file_location("portfolio_risk_candidate", SOURCE_PATH)
risk = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = risk
SPEC.loader.exec_module(risk)
D, F = Decimal, Fraction
DAY = date(2026, 1, 1)
LOSSES = (-4, -2, 0, 1, 1, 2, 3, 4, 4, 10)


def inputs(module=risk, *, factors=None, losses=LOSSES, alpha=F(4, 5), horizon=1,
           amount=F(100), portfolio_value=F(100)):
    factors = tuple(F(1) - F(loss, 100) for loss in losses) if factors is None else factors
    sessions = tuple(module.FactorSession(f"s-{i:04}", DAY + timedelta(days=i),
                     DAY + timedelta(days=i + 1), (module.AssetFactor("asset-a", factor),))
                     for i, factor in enumerate(factors))
    return dict(exposures=(module.AssetExposure("asset-a", "USD", amount),),
                reporting_currency="USD", exposure_date=DAY,
                panel=module.ExactFactorPanel("synthetic-panel-v1", "synthetic-total-factor-v1", sessions),
                horizon=horizon, confidence=alpha, portfolio_value=portfolio_value)


def assert_values(test, result, var, es):
    test.assertEqual(result.var.exact, F(var))
    test.assertEqual(result.es.exact, None if es is None else F(es))


class References(unittest.TestCase):
    def test_threshold_ties(self):
        result = risk.calculate_historical_risk(**inputs())
        assert_values(self, result, 4, 7)
        self.assertEqual((result.scenario_count, result.rank, result.tail_mass), (10, 8, F(2)))
        self.assertEqual((result.strict_tail_count, result.threshold_tie_count), (1, 2))
        self.assertEqual([s.tail_mass for s in result.scenarios if s.loss == 4], [F(1, 2)] * 2)
        self.assertEqual([s.tail_mass for s in result.scenarios if s.loss == 10], [F(1)])
        self.assertEqual(sum(s.tail_mass for s in result.scenarios), result.tail_mass)
        self.assertEqual((result.var_percent.exact, result.es_percent.exact), (4, 7))

    def test_fractional_tail(self):
        result = risk.calculate_historical_risk(**inputs(alpha=D("0.85")))
        assert_values(self, result, 4, 8)
        self.assertEqual((result.rank, result.tail_mass), (9, F(3, 2)))
        self.assertEqual([s.tail_mass for s in result.scenarios if s.loss == 4], [F(1, 4)] * 2)
        self.assertEqual(sum(s.tail_mass for s in result.scenarios), F(3, 2))
        self.assertEqual((result.var_percent.exact, result.es_percent.exact), (4, 8))

    def test_sparse_tail(self):
        result = risk.calculate_historical_risk(**inputs(alpha=D("0.95")))
        assert_values(self, result, 10, None)
        self.assertEqual((result.rank, result.tail_mass), (10, F(1, 2)))
        self.assertEqual((result.strict_tail_count, result.threshold_tie_count), (0, 1))
        self.assertEqual(result.es.reason, "insufficient_tail_mass")
        self.assertIsNone(result.es.display)
        self.assertEqual(result.es_percent.reason, "insufficient_tail_mass")
        self.assertTrue(all(s.tail_mass is None for s in result.scenarios))

    def test_all_gains_preserve_negative_measures(self):
        result = risk.calculate_historical_risk(**inputs(losses=(-4, -3, -2, -1), alpha=F(1, 2)))
        assert_values(self, result, -3, F(-3, 2))
        self.assertEqual((result.var.display, result.es.display), (D(-3), D("-1.5")))

    def test_scaling_and_permutation_invariance(self):
        base = risk.calculate_historical_risk(**inputs())
        scaled = risk.calculate_historical_risk(**inputs(amount=F(200), portfolio_value=F(200)))
        assert_values(self, scaled, 8, 14)
        self.assertEqual(scaled.var_percent, base.var_percent)
        self.assertEqual(scaled.es_percent, base.es_percent)
        permuted = risk.calculate_historical_risk(**inputs(losses=tuple(reversed(LOSSES))))
        assert_values(self, permuted, 4, 7)
        self.assertEqual([(s.loss, s.tail_mass) for s in permuted.scenarios],
                         [(s.loss, s.tail_mass) for s in base.scenarios])

    def test_two_session_compounding_reaches_actual_product_branch(self):
        arguments = inputs(factors=(D("1.1"), D("0.9"), D("1.1"), D("0.9")),
                           horizon=2, alpha=F(1, 2))
        with patch.object(risk, "_scenario_loss", wraps=risk._scenario_loss) as compound:
            result = risk.calculate_historical_risk(**arguments)
        self.assertEqual([len(call.args[1]) for call in compound.call_args_list], [2, 2, 2])
        assert_values(self, result, 1, 1)
        self.assertEqual([s.loss for s in result.scenarios], [F(1)] * 3)
        self.assertEqual([s.tail_mass for s in result.scenarios], [F(1, 2)] * 3)
        self.assertEqual((result.scenario_count, result.rank, result.tail_mass), (3, 2, F(3, 2)))
        self.assertTrue(result.overlapping)
        self.assertEqual([(s.start_index, s.stop_index) for s in result.scenarios], [(0, 2), (1, 3), (2, 4)])
        assert_values(self, risk.calculate_historical_risk(**dict(arguments, horizon=1)), -10, 10)


class ContractAndArithmetic(unittest.TestCase):
    def reject(self, arguments, reason=None):
        with self.assertRaisesRegex(risk.PortfolioRiskError, reason or ".+"):
            risk.calculate_historical_risk(**arguments)

    def test_long_short_fixed_exposure_currency_and_canonical_asset_order(self):
        arguments = inputs(factors=(F(11, 10), F(9, 10), F(11, 10)), alpha=F(1, 2), horizon=2)
        exposures = (risk.AssetExposure("asset-b", "USD", D("-50")),
                     risk.AssetExposure("asset-a", "USD", D("100")))
        sessions = tuple(replace(s, factors=(risk.AssetFactor("asset-b", F(2)), *s.factors))
                         for s in arguments["panel"].sessions)
        result = risk.calculate_historical_risk(**dict(arguments, exposures=exposures,
            panel=replace(arguments["panel"], sessions=sessions)))
        # Each horizon: A loses 1; short B loses 150 (factor 2*2=4).
        assert_values(self, result, 151, 151)
        self.assertEqual((result.net_exposure, result.gross_exposure), (50, 150))
        self.assertEqual([e.asset_id for e in result.exposures], ["asset-a", "asset-b"])
        reversed_input = dict(arguments, exposures=tuple(reversed(exposures)),
            panel=replace(arguments["panel"], sessions=tuple(replace(s, factors=tuple(reversed(s.factors)))
                                                          for s in sessions)))
        self.assertEqual(risk.calculate_historical_risk(**reversed_input), result)

    def test_exact_nonterminating_factors_context_and_receipt_replay(self):
        arguments = inputs(factors=(F(1, 3), F(3), F(1, 3)), horizon=2, alpha=F(1, 2))
        expected = risk.calculate_historical_risk(**arguments)
        assert_values(self, expected, 0, 0)
        with localcontext() as context:
            context.prec, context.rounding = 2, ROUND_DOWN
            context.traps[Inexact] = context.traps[Rounded] = True
            result = risk.calculate_historical_risk(**arguments)
            self.assertEqual(result, expected)
            self.assertEqual(result.var.display.as_tuple().exponent, -18)
        replay = risk.calculate_historical_risk(exposures=result.exposures,
            reporting_currency=result.reporting_currency, exposure_date=result.exposure_date,
            panel=result.panel, horizon=result.horizon, confidence=result.confidence,
            portfolio_value=result.portfolio_value)
        self.assertEqual(replay, result)
        self.assertEqual(result.method_id, "historical-loss-es-v1")
        self.assertEqual(result.data_authority, "unverified_synthetic_inputs")
        with self.assertRaises(FrozenInstanceError):
            result.panel.sessions[0].session_id = "changed"

    def test_rounding_only_display_with_half_even_signed_ties(self):
        for numerator, expected in ((1, "0e-18"), (3, "2e-18"), (5, "2e-18"),
                                     (-1, "-0e-18"), (-3, "-2e-18"), (-5, "-2e-18")):
            with self.subTest(numerator=numerator):
                value = F(numerator, 2 * 10**18)
                self.assertEqual(risk.display18(value).as_tuple(), D(expected).as_tuple())
                result = risk.calculate_historical_risk(**inputs(factors=(1 - value, 1 - value),
                    alpha=F(1, 2), amount=F(1)))
                self.assertEqual(result.var.exact, value)
                self.assertEqual(result.var.display.as_tuple(), D(expected).as_tuple())
        self.assertEqual(risk.display18(F(1, 3)), D("0.333333333333333333"))

    def test_ordering_uses_exact_losses_even_when_displays_collide(self):
        tiny = F(1, 10**30)
        losses = (F(1) + tiny, F(1), F(1) + 2 * tiny)
        result = risk.calculate_historical_risk(**inputs(
            factors=tuple(1 - loss / 100 for loss in losses), alpha=F(1, 2)))
        self.assertEqual(result.var.exact, 1 + tiny)
        self.assertEqual(result.es.exact, 1 + F(5, 3) * tiny)
        self.assertEqual([s.scenario_id[1] for s in result.scenarios], ["s-0001", "s-0000", "s-0002"])
        self.assertEqual([risk.display18(s.loss) for s in result.scenarios], [D(1)] * 3)

    def test_tail_against_independent_greedy_worst_first_integral(self):
        # Independent oracle: fill mass from the worst observation down, rather
        # than using the implementation's quantile/strict-tail/tie formula.
        for losses in (LOSSES, (-4, -3, -2, -1), (2, 2, 2, 2), (3, -7, 3, 8, -2, 1)):
            for alpha in (F(1, 10), F(1, 4), F(1, 2), F(3, 4), F(9, 10)):
                with self.subTest(losses=losses, alpha=alpha):
                    result = risk.calculate_historical_risk(**inputs(losses=losses, alpha=alpha))
                    q = result.var.exact
                    self.assertLess(sum(loss < q for loss in losses) / F(len(losses)), alpha)
                    self.assertGreaterEqual(sum(loss <= q for loss in losses) / F(len(losses)), alpha)
                    mass = len(losses) * (1 - alpha)
                    if mass < 1:
                        self.assertEqual(result.es.reason, "insufficient_tail_mass")
                        continue
                    remaining, integral = mass, F(0)
                    for loss in sorted(losses, reverse=True):
                        take = min(remaining, F(1))
                        integral += take * loss
                        remaining -= take
                    self.assertEqual(result.es.exact, integral / mass)
                    self.assertEqual(sum(s.tail_mass for s in result.scenarios), mass)

    def test_denominator_unavailable_preserves_currency_risk_and_net_zero(self):
        for value, reason in ((None, "portfolio_value_not_declared"), (F(0), "nonpositive_portfolio_value"),
                              (D(-1), "nonpositive_portfolio_value")):
            with self.subTest(value=value):
                result = risk.calculate_historical_risk(**inputs(portfolio_value=value))
                assert_values(self, result, 4, 7)
                self.assertEqual(result.var_percent.reason, reason)
                self.assertEqual(result.es_percent.reason, reason)
                self.assertIsNone(result.var_percent.display)
        args = inputs(amount=F(0), portfolio_value=F(0))
        assert_values(self, risk.calculate_historical_risk(**args), 0, 0)
        self.reject(inputs(portfolio_value=0), "exact_number_required")

    def test_insufficient_scenarios_empty_singleton_or_horizon_exceeds_window(self):
        for factors, horizon, count in (((), 1, 0), ((F(1),), 1, 1), ((F(1),), 2, 0),
                                         ((F(1), F(1)), 2, 1)):
            with self.subTest(factors=factors, horizon=horizon):
                result = risk.calculate_historical_risk(**inputs(factors=factors, horizon=horizon))
                self.assertEqual(result.scenario_count, count)
                self.assertEqual(result.var.reason, "insufficient_scenarios")
                self.assertEqual(result.es.reason, "insufficient_scenarios")
                self.assertIsNone(result.rank)
                self.assertTrue(all(s.tail_mass is None for s in result.scenarios))

    def test_exact_tail_boundary_small_alpha_and_all_equal(self):
        for alpha in (F(9, 10), F(1, 100)):
            result = risk.calculate_historical_risk(**inputs(alpha=alpha))
            if alpha == F(9, 10):
                self.assertEqual(result.tail_mass, 1)
                self.assertEqual(result.es.exact, 10)
            else:
                self.assertEqual(result.rank, 1)
                self.assertEqual(sum(s.tail_mass for s in result.scenarios), F(99, 10))
                reference = (sum(LOSSES[1:]) + F(9, 10) * LOSSES[0]) / F(99, 10)
                self.assertEqual(result.es.exact, reference)
        equal = risk.calculate_historical_risk(**inputs(losses=(2, 2, 2, 2), alpha=F(1, 2)))
        assert_values(self, equal, 2, 2)
        self.assertEqual([s.tail_mass for s in equal.scenarios], [F(1, 2)] * 4)

    def test_float_coercion_nonfinite_inputs_in_every_numeric_field(self):
        bad = (True, False, 1, 0.8, "0.8", None, D("NaN"), D("sNaN"), D("Infinity"), D("-Infinity"))
        for value in bad:
            for field in ("confidence", "exposure", "factor", "portfolio_value"):
                if field == "portfolio_value" and value is None:
                    continue
                with self.subTest(value=value, field=field):
                    args = inputs()
                    if field == "exposure":
                        args["exposures"] = (replace(args["exposures"][0], amount=value),)
                    elif field == "factor":
                        session = args["panel"].sessions[0]
                        args["panel"] = replace(args["panel"], sessions=(replace(session,
                            factors=(replace(session.factors[0], gross_factor=value),)), *args["panel"].sessions[1:]))
                    else:
                        args[field] = value
                    self.reject(args)

    def test_invalid_confidence_horizon_currency_exposure_identifiers_and_dates(self):
        for value in (F(0), F(1), F(-1), F(101, 100)):
            self.reject(inputs(alpha=value), "invalid_confidence")
        for value in (0, -1, True, False, 1.0, D(1), F(1), "1", 253):
            self.reject(inputs(horizon=value), "unsupported_horizon")
        for value in ("", "usd", "US", "USDD", " USD", None, 123):
            self.reject(dict(inputs(), reporting_currency=value), "invalid_reporting_currency")
        self.reject(dict(inputs(), exposure_date=datetime(2026, 1, 1)), "invalid_exposure_date")
        for exposures in ((), [], (risk.AssetExposure("", "USD", F(1)),),
                          (risk.AssetExposure("a", "EUR", F(1)),), inputs()["exposures"] * 2):
            self.reject(dict(inputs(), exposures=exposures))
        for label in ("", " a", "a\n", "x" * 129, True):
            self.reject(dict(inputs(), panel=replace(inputs()["panel"], panel_id=label)), "invalid_exact_factor_panel")
        self.reject(dict(inputs(), panel=object()), "invalid_exact_factor_panel")
        for factor in (F(0), F(-1)):
            self.reject(inputs(factors=(factor, F(1))), "nonpositive_gross_factor")

    def test_missing_inconsistent_gapped_reordered_and_mutable_panels(self):
        base = inputs()
        panel = base["panel"]
        sessions = panel.sessions
        bad_sessions = (
            list(sessions),
            (replace(sessions[0], factors=()), *sessions[1:]),
            (replace(sessions[0], factors=(risk.AssetFactor("unknown", F(1)),)), *sessions[1:]),
            (replace(sessions[0], factors=(None,)), *sessions[1:]),
            (replace(sessions[0], factors=list(sessions[0].factors)), *sessions[1:]),
            (replace(sessions[0], end=sessions[0].start), *sessions[1:]),
            (replace(sessions[0], start=datetime(2026, 1, 1)), *sessions[1:]),
            (replace(sessions[0], session_id=sessions[1].session_id), *sessions[1:]),
            (sessions[0], *sessions[2:]),  # Explicit supplied gap must not bridge.
            tuple(reversed(sessions)),
            (sessions[0], sessions[0]),
            (None,),
        )
        for changed in bad_sessions:
            with self.subTest(changed=changed):
                self.reject(dict(base, panel=replace(panel, sessions=changed)))
        for horizon in (2, 252):
            # Even an insufficient requested horizon cannot hide invalid cells.
            self.reject(dict(base, horizon=horizon, panel=replace(panel, sessions=(
                *sessions[:-1], replace(sessions[-1], factors=())))), "incomplete_factor_panel")
        two_assets = (*base["exposures"], risk.AssetExposure("b", "USD", F(-10)))
        duplicate = tuple(replace(s, factors=(s.factors[0], s.factors[0])) for s in sessions)
        self.reject(dict(base, exposures=two_assets, panel=replace(panel, sessions=duplicate)), "inconsistent_factor_assets")

    def test_no_calendar_or_provenance_authority_from_valid_names(self):
        args = inputs(factors=(F(1), F(1)), alpha=F(1, 2))
        # Contiguous declared intervals can hide a real exchange session. The
        # pure kernel cannot detect this without a trusted calendar adapter.
        sessions = (replace(args["panel"].sessions[0], end=DAY + timedelta(days=7)),
                    replace(args["panel"].sessions[1], start=DAY + timedelta(days=7),
                            end=DAY + timedelta(days=8)))
        panel = replace(args["panel"], panel_id="official-admitted-complete", sessions=sessions)
        result = risk.calculate_historical_risk(**dict(args, panel=panel))
        self.assertEqual(result.data_authority, "unverified_synthetic_inputs")
        self.assertIn("supplied_calendar_not_verified", result.notices)
        imports = {node.module if isinstance(node, ast.ImportFrom) else alias.name
                   for node in ast.walk(ast.parse(SOURCE)) if isinstance(node, (ast.Import, ast.ImportFrom))
                   for alias in node.names}
        self.assertEqual(imports, {"dataclasses", "datetime", "decimal", "fractions", "re"})


class Resources(unittest.TestCase):
    def test_scalar_decimal_and_fraction_bounds_inclusive_and_one_over(self):
        for factor in (D("1e256"), D("1e-256"), D("1." + "1" * 127),
                       F(2**2047), F(1, 2**2047)):
            with self.subTest(factor=factor):
                risk.calculate_historical_risk(**inputs(factors=(factor,)))
        for factor in (D("1e257"), D("1e-257"), D("0e-1000000000"),
                       D("1." + "1" * 128), F(2**2048), F(1, 2**2048)):
            with self.subTest(factor=factor):
                with self.assertRaisesRegex(risk.PortfolioRiskError, "input_resource_limit"):
                    risk.calculate_historical_risk(**inputs(factors=(factor,)))
        risk._bounded(F(2**8191))
        with self.assertRaisesRegex(risk.PortfolioRiskError, "arithmetic_resource_limit"):
            risk._bounded(F(2**8192))

    def test_real_compounding_and_aggregate_sum_overflow_no_partial_output(self):
        # Per-cell values pass; compounding itself grows beyond the bit budget.
        with self.assertRaisesRegex(risk.PortfolioRiskError, "arithmetic_resource_limit"):
            risk.calculate_historical_risk(**inputs(factors=(F(2**2047),) * 5, horizon=5))
        with patch.object(risk, "MAX_RATIONAL_BITS", 10):
            with self.assertRaisesRegex(risk.PortfolioRiskError, "arithmetic_resource_limit"):
                risk.calculate_historical_risk(**inputs(amount=F(1023)))

    def test_asset_session_and_horizon_caps(self):
        def rectangle(assets, sessions):
            args = inputs(factors=(F(1),) * sessions)
            args["exposures"] = tuple(risk.AssetExposure(f"a-{i}", "USD", F(1)) for i in range(assets))
            args["panel"] = replace(args["panel"], sessions=tuple(replace(s,
                factors=tuple(risk.AssetFactor(e.asset_id, F(1)) for e in args["exposures"]))
                for s in args["panel"].sessions))
            return args
        risk.calculate_historical_risk(**rectangle(35, 2))
        risk.calculate_historical_risk(**rectangle(1, 6000))
        risk.calculate_historical_risk(**inputs(factors=(F(1),) * 253, horizon=252, alpha=F(1, 2)))
        for args, reason in ((rectangle(36, 2), "invalid_exposures"),
                             (rectangle(1, 6001), "session_resource_limit"),
                             (rectangle(10, 6000), None), (rectangle(11, 6000), "factor_cell_resource_limit")):
            with self.subTest(reason=reason):
                if reason is None:
                    risk.calculate_historical_risk(**args)  # Exactly 60000 cells.
                else:
                    with self.assertRaisesRegex(risk.PortfolioRiskError, reason):
                        risk.calculate_historical_risk(**args)

    def test_operation_and_aggregate_limits_exact_then_one_less(self):
        args = inputs(factors=(F(1),) * 4, horizon=2, alpha=F(1, 2))
        # 3 overlapping scenarios * 2 sessions * 1 asset = 6 products.
        for cap, passes in ((6, True), (5, False)):
            with patch.object(risk, "MAX_FACTOR_OPERATIONS", cap):
                if passes:
                    risk.calculate_historical_risk(**args)

                else:
                    with self.assertRaisesRegex(risk.PortfolioRiskError, "operation_resource_limit"):
                        risk.calculate_historical_risk(**args)
        result = risk.calculate_historical_risk(**args)
        input_bits = sum(risk._bits(v) for v in (result.confidence, result.portfolio_value,
            result.exposures[0].amount, *(s.factors[0].gross_factor for s in result.panel.sessions)))
        output_bits = sum(risk._bits(v) for v in (result.net_exposure, result.gross_exposure,
            result.confidence, result.tail_mass, result.var.exact, result.es.exact,
            result.var_percent.exact, result.es_percent.exact,
            *(s.loss for s in result.scenarios), *(s.tail_mass for s in result.scenarios)))
        for name, boundary, reason in (("MAX_TOTAL_INPUT_BITS", input_bits, "aggregate_input_resource_limit"),
                                      ("MAX_TOTAL_OUTPUT_BITS", output_bits, "aggregate_output_resource_limit")):
            with patch.object(risk, name, boundary):
                self.assertEqual(risk.calculate_historical_risk(**args), result)
            with patch.object(risk, name, boundary - 1):
                with self.assertRaisesRegex(risk.PortfolioRiskError, reason):
                    risk.calculate_historical_risk(**args)

    def test_default_operation_cap_is_reachable_and_one_more_window_rejects(self):
        # N=5000, h=200, A=1: exactly 1,000,000 factor products.
        args = inputs(factors=(F(1),) * 5199, horizon=200, alpha=F(1, 2))
        result = risk.calculate_historical_risk(**args)
        self.assertEqual(result.scenario_count * result.horizon, risk.MAX_FACTOR_OPERATIONS)
        with self.assertRaisesRegex(risk.PortfolioRiskError, "operation_resource_limit"):
            risk.calculate_historical_risk(**inputs(factors=(F(1),) * 5200, horizon=200))


class MutationControls(unittest.TestCase):
    def mutant(self, before, after):
        self.assertEqual(SOURCE.count(before), 1, "Mutation must select exactly one intended source location")
        module = types.ModuleType("portfolio_risk_mutant")
        sys.modules[module.__name__] = module
        self.addCleanup(sys.modules.pop, module.__name__, None)
        exec(compile(SOURCE.replace(before, after, 1), str(SOURCE_PATH), "exec"), module.__dict__)
        return module

    def test_sign_interpolation_tie_average_and_integer_tail_mutants(self):
        cases = (
            ("return -pnl", "return pnl", {}, (4, 7)),
            ("        var = RiskValue(threshold)",
             "        losses = tuple(s.loss for s in scenarios)\n"
             "        position = alpha * (count - 1)\n        left = int(position)\n"
             "        var = RiskValue(losses[left] + (position - left) * (losses[left + 1] - losses[left]))",
             {"alpha": F(3, 4)}, (4, F(32, 5))),
            ("es = _bounded(total / mass)",
             "es = sum(loss for loss in losses if loss >= threshold) / sum(loss >= threshold for loss in losses)",
             {}, (4, 7)),
            ("mass = _bounded(count * (1 - alpha))\n    rank",
             "mass = _bounded(Fraction(int(count * (1 - alpha))))\n    rank",
             {"alpha": F(17, 20)}, (4, 8)),
        )
        for before, after, options, expected in cases:
            with self.subTest(mutation=before):
                baseline = risk.calculate_historical_risk(**inputs(**options))
                assert_values(self, baseline, *expected)
                mutant = self.mutant(before, after)
                result = mutant.calculate_historical_risk(**inputs(mutant, **options))
                # Numeric output was reached, not a parse/validation failure.
                with self.assertRaises(AssertionError):
                    assert_values(self, result, *expected)

    def test_h2_direct_sqrt_scaling_mutant_reaches_compounding_and_fails_numerically(self):
        options = dict(factors=(D("1.1"), D("0.9"), D("1.1"), D("0.9")),
                       horizon=2, alpha=F(1, 2))
        assert_values(self, risk.calculate_historical_risk(**inputs(**options)), 1, 1)
        # Replace ONLY the h>1 estimator values, after the real horizon path.
        # The invalid method uses the SAME exposures/factors/confidence at h=1.
        # Fraction.from_float is deliberately confined to this wrong-method test.
        marker = "        var = RiskValue(threshold)"
        mutant = self.mutant(marker,
            "        if horizon > 1:\n"
            "            one = calculate_historical_risk(exposures=exposures, reporting_currency=reporting_currency,\n"
            "                exposure_date=exposure_date, panel=panel, horizon=1, confidence=alpha, portfolio_value=value)\n"
            "            scale = Fraction.from_float(__import__('math').sqrt(horizon))\n"
            "            threshold, expected = one.var.exact * scale, one.es.exact * scale\n" + marker)
        with patch.object(mutant, "_scenario_loss", wraps=mutant._scenario_loss) as branch:
            result = mutant.calculate_historical_risk(**inputs(mutant, **options))
        lengths = [len(call.args[1]) for call in branch.call_args_list]
        self.assertEqual(lengths, [2, 2, 2, 1, 1, 1, 1])
        self.assertEqual(result.scenario_count, 3)
        self.assertEqual([s.loss for s in result.scenarios], [F(1)] * 3)
        self.assertLess(result.var.exact, 0)  # Wrong sign from -10 * sqrt(2).
        self.assertGreater(result.es.exact, 14)
        self.assertLess(result.es.exact, 15)
        for actual in (result.var.exact, result.es.exact):
            with self.assertRaises(AssertionError):
                self.assertEqual(actual, F(1))


if __name__ == "__main__":
    unittest.main(verbosity=2)
