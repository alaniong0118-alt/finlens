"""Pure synthetic references, exact invariants and resource/rounding edges."""
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal, Inexact, Rounded, ROUND_DOWN, localcontext
from fractions import Fraction as F
from itertools import product
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

BACKEND = Path(__file__).resolve().parents[1]
PRIMARY = BACKEND if (BACKEND / 'app/portfolio_risk.py').is_file() else Path('D:/Projects/finlens-foundation/backend')
sys.path.insert(0, str(PRIMARY))
from app import portfolio_risk as risk
spec = importlib.util.spec_from_file_location('panel_statistics_candidate', BACKEND / 'app/factor_panel_statistics.py')
stats = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = stats
spec.loader.exec_module(stats)
DAY = date(2026, 1, 1)


def inputs(columns=((F(11,10), F(9,10)), (F(6,5), F(4,5))), amounts=None):
    size = len(columns)
    amounts = (F(100),) * size if amounts is None else amounts
    return dict(exposures=tuple(risk.AssetExposure(f'a{j}', 'USD', amounts[j]) for j in range(size)),
        reporting_currency='USD', exposure_date=DAY,
        panel=risk.ExactFactorPanel('synthetic-panel', 'user-exact-factors', tuple(
            risk.FactorSession(f's{i}', DAY+timedelta(days=i), DAY+timedelta(days=i+1), tuple(
                risk.AssetFactor(f'a{j}', columns[j][i]) for j in range(size))) for i in range(len(columns[0])))),
        confidence=F(1,2), horizon=1, portfolio_value=None)


class PanelStatisticsTests(unittest.TestCase):
    def test_hand_calculated_path_variance_covariance_and_root(self):
        r = stats.calculate_panel_statistics(**inputs())
        a, b = r.assets
        self.assertEqual((a.cumulative_return.exact,b.cumulative_return.exact),(F(-1,100),F(-1,25)))
        self.assertEqual((a.maximum_drawdown.exact,b.maximum_drawdown.exact),(F(1,10),F(1,5)))
        self.assertEqual((a.peak_boundary,a.trough_boundary),(1,2))
        self.assertEqual((a.sample_mean_return.exact,b.sample_mean_return.exact),(0,0))
        self.assertEqual((a.sample_variance.exact,b.sample_variance.exact),(F(1,50),F(2,25)))
        self.assertEqual([[v.exact for v in row] for row in r.covariance],[[F(1,50),F(1,25)],[F(1,25),F(2,25)]])
        self.assertEqual(a.sample_volatility.radicand,F(1,50))
        self.assertEqual(a.sample_volatility.display,'0.141421356237309505')
        self.assertEqual((r.sample_count,r.sample_denominator),(2,1))
        self.assertTrue(r.covariance_complete)
        self.assertEqual((r.return_unit,r.covariance_unit),('return_ratio','return_ratio_squared'))

    def test_initial_decline_recovery_later_peak_and_tie_witness(self):
        a=stats.calculate_panel_statistics(**inputs(((F(4,5),F(5,4),F(6,5),F(1,2)),))).assets[0]
        self.assertEqual((a.cumulative_return.exact,a.maximum_drawdown.exact),(F(-2,5),F(1,2)))
        self.assertEqual((a.peak_boundary,a.trough_boundary),(3,4))
        a=stats.calculate_panel_statistics(**inputs(((F(9,10),F(10,9),F(9,10)),))).assets[0]
        self.assertEqual((a.maximum_drawdown.exact,a.peak_boundary,a.trough_boundary),(F(1,10),0,1))
        for factors in [(F(1),F(1)),(F(2),F(3))]:
            a=stats.calculate_panel_statistics(**inputs((factors,))).assets[0]
            self.assertEqual((a.maximum_drawdown.exact,a.peak_boundary,a.trough_boundary),(0,0,0))

    def test_no_observations_and_single_interval_have_explicit_availability(self):
        r=stats.calculate_panel_statistics(**inputs(((),)))
        a=r.assets[0]
        for measure in (a.cumulative_return,a.maximum_drawdown,a.sample_mean_return,a.sample_variance,r.covariance[0][0]):
            self.assertIsNone(measure.exact);self.assertEqual(measure.reason,'insufficient_observations')
        self.assertIsNone(a.sample_volatility.radicand);self.assertIsNone(a.sample_volatility.display)
        self.assertEqual((a.peak_boundary,a.trough_boundary),(None,None))
        self.assertIsNone(r.sample_denominator);self.assertIsNone(r.equal_interval_lengths)
        for factor in (F(4,5),F(1),F(6,5)):
            r=stats.calculate_panel_statistics(**inputs(((factor,),)));a=r.assets[0]
            self.assertEqual(a.cumulative_return.exact,factor-1)
            self.assertEqual(a.maximum_drawdown.exact,max(F(0),1-factor))
            self.assertEqual(a.sample_mean_return.exact,factor-1)
            self.assertEqual(a.sample_variance.reason,'insufficient_observations')
            self.assertFalse(r.covariance_complete)

    def test_sign_zero_exposure_and_risk_parameters_do_not_change_asset_statistics(self):
        base=inputs();r=stats.calculate_panel_statistics(**base)
        for amounts in [(F(-500),F(0)),(F(0),F(0)),(F(99),F(-99))]:
            other=inputs(amounts=amounts);other.update(horizon=20,confidence=F(99,100),portfolio_value=F(-1))
            self.assertEqual(stats.calculate_panel_statistics(**other),r)
        reversed_input=dict(base,exposures=tuple(reversed(base['exposures'])),panel=replace(base['panel'],sessions=tuple(
            replace(s,factors=tuple(reversed(s.factors))) for s in base['panel'].sessions)))
        self.assertEqual(stats.calculate_panel_statistics(**reversed_input),r)

    def test_unequal_interval_lengths_remain_equal_weight_observations(self):
        value=inputs();first,second=value['panel'].sessions
        value['panel']=replace(value['panel'],sessions=(first,replace(second,end=second.end+timedelta(days=5))))
        r=stats.calculate_panel_statistics(**value);base=stats.calculate_panel_statistics(**inputs())
        self.assertEqual(r.assets,base.assets);self.assertEqual(r.covariance,base.covariance)
        self.assertEqual(r.interval_days,(1,6));self.assertFalse(r.equal_interval_lengths)
        self.assertEqual(r.observation_basis,'equal_weight_supplied_intervals')

    def test_exact_covariance_is_symmetric_psd_and_diagonal_matches_variance(self):
        cases=0
        for returns in product((F(-1,4),F(0),F(1,4)),repeat=6):
            r=stats.calculate_panel_statistics(**inputs((tuple(1+x for x in returns[:3]),tuple(1+x for x in returns[3:]))))
            a,b=r.assets;v=r.covariance
            self.assertEqual(v[0][1],v[1][0]);self.assertEqual(v[0][0],a.sample_variance);self.assertEqual(v[1][1],b.sample_variance)
            self.assertGreaterEqual(a.sample_variance.exact,0);self.assertGreaterEqual(b.sample_variance.exact,0)
            self.assertGreaterEqual(v[0][0].exact*v[1][1].exact-v[0][1].exact**2,0)
            cases+=1
        self.assertEqual(cases,729)

    def test_sample_denominator_is_n_minus_one_and_negative_covariance_is_valid(self):
        r=stats.calculate_panel_statistics(**inputs(((F(1),F(2),F(3)),(F(3),F(2),F(1)))))
        self.assertEqual((r.assets[0].sample_mean_return.exact,r.assets[0].sample_variance.exact),(1,1))
        self.assertEqual(r.covariance[0][1].exact,-1)
        self.assertEqual(r.assets[0].sample_volatility.display,'1.000000000000000000')
        r=stats.calculate_panel_statistics(**inputs(((F(1),)*3,)))
        self.assertEqual((r.assets[0].sample_variance.exact,r.assets[0].sample_volatility.radicand),(0,0))

    def test_three_asset_cross_covariances_and_all_small_integer_quadratic_forms(self):
        returns=((F(0),F(1,10),F(-1,10),F(1,5)),
                 (F(1,5),F(0),F(-1,5),F(1,10)),
                 (F(-1,10),F(0),F(1,10),F(1,5)))
        r=stats.calculate_panel_statistics(**inputs(tuple(tuple(1+x for x in values) for values in returns)))
        covariance=[[value.exact for value in row] for row in r.covariance]
        self.assertEqual(covariance,[[F(1,60),F(7,600),F(1,150)],
                                     [F(7,600),F(7,240),F(-1,120)],
                                     [F(1,150),F(-1,120),F(1,60)]])
        for weights in product(range(-2,3),repeat=3):
            self.assertGreaterEqual(sum(weights[i]*covariance[i][j]*weights[j] for i in range(3) for j in range(3)),0)

    def test_sqrt_midpoint_half_even_and_high_precision_independent_reference(self):
        for units in (0,1,2,3,10**18,10**18+1):
            midpoint=F(2*units+1,2*risk.SCALE)
            expected=units if units%2==0 else units+1
            self.assertEqual(F(stats.sqrt_display18(midpoint**2)),F(expected,risk.SCALE))
            self.assertEqual(F(stats.sqrt_display18(midpoint**2-F(1,10**100))),F(units,risk.SCALE))
            self.assertEqual(F(stats.sqrt_display18(midpoint**2+F(1,10**100))),F(units+1,risk.SCALE))
        with localcontext() as context:
            context.prec=150
            for v in (F(1,50),F(2),F(9999,7),F(1,10**70)):
                reference=(Decimal(v.numerator)/Decimal(v.denominator)).sqrt().quantize(Decimal('1e-18'))
                self.assertEqual(stats.sqrt_display18(v),reference)
        with self.assertRaises(risk.PortfolioRiskError):stats.sqrt_display18(F(-1))
        with self.assertRaises(risk.PortfolioRiskError):stats.sqrt_display18(0.1)

    def test_hostile_decimal_context_and_tiny_nonzero_volatility(self):
        source=inputs(((F(1),1+F(2,10**50)),));baseline=stats.calculate_panel_statistics(**source)
        with localcontext() as context:
            context.prec=2;context.rounding=ROUND_DOWN;context.traps[Inexact]=True;context.traps[Rounded]=True
            self.assertEqual(stats.calculate_panel_statistics(**source),baseline)
        v=baseline.assets[0].sample_volatility
        self.assertGreater(v.radicand,0);self.assertEqual(v.display,'0.000000000000000000');self.assertIsNone(v.reason)

    def test_path_arithmetic_unavailable_does_not_erase_valid_moments_or_drawdown(self):
        value=inputs(((F(2**2000-1),)*5,))
        a=stats.calculate_panel_statistics(**value).assets[0]
        self.assertEqual(a.cumulative_return.reason,'arithmetic_resource_limit')
        self.assertEqual(a.maximum_drawdown.exact,0)
        self.assertEqual(a.sample_variance.exact,0);self.assertEqual(a.sample_volatility.radicand,0)
        a=stats.calculate_panel_statistics(**inputs(((F(1,2**2000),)*5,))).assets[0]
        self.assertEqual(a.maximum_drawdown.reason,'arithmetic_resource_limit')
        self.assertEqual((a.peak_boundary,a.trough_boundary),(None,None))
        self.assertEqual(a.sample_variance.exact,0)

    def test_mean_arithmetic_limits_propagate_to_covariance_without_approximation(self):
        factors=tuple(F(1,2**power+1) for power in range(2000,2010,2))
        r=stats.calculate_panel_statistics(**inputs((factors,(F(1),)*5)))
        self.assertEqual(r.assets[0].sample_mean_return.reason,'arithmetic_resource_limit')
        self.assertEqual(r.assets[0].sample_variance.reason,'arithmetic_resource_limit')
        self.assertEqual(r.covariance[0][1].reason,'arithmetic_resource_limit')
        self.assertEqual(r.covariance[1][1].exact,0);self.assertFalse(r.covariance_complete)

    def test_missing_nonpositive_gap_duplicate_and_nonexact_inputs_reject(self):
        for case in ('missing','unknown','zero','negative','float','gap','duplicate','currency'):
            value=inputs();s=list(value['panel'].sessions)
            if case=='missing':s[0]=replace(s[0],factors=s[0].factors[:1])
            if case=='unknown':s[0]=replace(s[0],factors=(risk.AssetFactor('other',F(1)),s[0].factors[1]))
            if case in ('zero','negative','float'):
                factor={'zero':F(0),'negative':F(-1),'float':1.0}[case]
                s[0]=replace(s[0],factors=(replace(s[0].factors[0],gross_factor=factor),s[0].factors[1]))
            if case=='gap':s[1]=replace(s[1],start=s[1].start+timedelta(days=1))
            if case=='duplicate':value['exposures']=(value['exposures'][0],)*2
            if case=='currency':value['reporting_currency']='EUR'
            value['panel']=replace(value['panel'],sessions=tuple(s))
            with self.subTest(case=case),self.assertRaises(risk.PortfolioRiskError):stats.calculate_panel_statistics(**value)

    def test_operation_and_aggregate_output_bounds_are_explicit_rejections(self):
        with patch.object(stats,'MAX_FACTOR_OPERATIONS',8):
            stats.calculate_panel_statistics(**inputs())
            with self.assertRaisesRegex(risk.PortfolioRiskError,'statistics_operation_resource_limit'):
                stats.calculate_panel_statistics(**inputs(((F(1),)*3,(F(1),)*3)))
        with patch.object(stats,'MAX_TOTAL_OUTPUT_BITS',1):
            with self.assertRaisesRegex(risk.PortfolioRiskError,'aggregate_output_resource_limit'):
                stats.calculate_panel_statistics(**inputs())


if __name__=='__main__':unittest.main(verbosity=2)
