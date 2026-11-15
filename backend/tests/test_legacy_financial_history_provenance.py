"""Legacy grouped history must not misattribute file-level provenance."""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
import unittest

from app.financial_analysis import get_financial_history

OLD = ('0000320193-25-000001', date(2025, 5, 2), '10-Q')
NEW = ('0000320193-25-000002', date(2025, 6, 5), '10-Q/A')
START = date(2025, 1, 1)
END = date(2025, 3, 31)


class Session:
    def __init__(self, quarter, annual):
        self.tables = iter((quarter, annual))

    def scalars(self, _):
        return SimpleNamespace(all=lambda: next(self.tables))


def run(quarter, annual=()):
    return get_financial_history(Session(quarter, annual), "0000320193")


def fact(metric="Revenues", value="100", source=OLD, start=START, end=END, fiscal_period="Q1"):
    accession_number, filed, form = source
    return SimpleNamespace(metric=metric, value=Decimal(value), accession_number=accession_number,
                           filed=filed, form=form, period_start=start, period_end=end,
                           fiscal_period=fiscal_period)


class LegacySources(unittest.TestCase):
    def test_restatement_uses_winning_value_and_its_source(self):
        item, = run([fact(), fact(value="110", source=NEW)])
        self.assertEqual((item["revenue"], item["filed"], item["form"]), (Decimal("110"), *NEW[1:]))

    def test_mixed_sources_clear_both_shared_fields_and_keep_values(self):
        item, = run([fact(), fact("NetIncomeLoss", "9", NEW)])
        self.assertEqual((item["revenue"], item["net_income"]), (Decimal("100"), Decimal("9")))
        self.assertEqual((item["filed"], item["form"]), (None, None))

    def test_shared_filing_passes_through(self):
        item, = run([fact(), fact("NetIncomeLoss", "9"), fact("EarningsPerShareDiluted", "0.75")])
        self.assertEqual((item["filed"], item["form"], item["diluted_eps"]), (*OLD[1:], Decimal("0.75")))

    def test_same_form_and_date_are_not_filing_identity(self):
        another = ('0000320193-25-000099', *OLD[1:])
        item, = run([fact(), fact("NetIncomeLoss", "9", another)])
        self.assertEqual((item["filed"], item["form"]), (None, None))

    def test_unknown_accessions_do_not_imply_same_filing(self):
        unknown = (None, *OLD[1:])
        item, = run([fact(source=unknown), fact("NetIncomeLoss", "9", unknown)])
        self.assertEqual((item["filed"], item["form"]), (None, None))

    def test_incomplete_shared_form_or_date_clears_both(self):
        for original in ((OLD[0], OLD[1], None), (OLD[0], None, OLD[2])):
            with self.subTest(original=original):
                item, = run([fact(source=original)])
                self.assertEqual((item["filed"], item["form"]), (None, None))

    def test_fiscal_year_and_order_unchanged(self):
        annual = [fact(start=date(2024, 10, 1), end=date(2025, 9, 30))]
        following = fact(start=date(2025, 10, 1), end=date(2025, 12, 31))
        items = run([following, fact()], annual)
        self.assertEqual([(row['period_end'], row['fiscal_year']) for row in items],
                         [(END, 2025), (following.period_end, 2026)])
        self.assertTrue(all(row['fiscal_period'] == 'Q1' for row in items))


if __name__ == '__main__':
    unittest.main()
