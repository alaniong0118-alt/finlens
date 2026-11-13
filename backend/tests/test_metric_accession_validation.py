"""Detached synthetic facts only; execute through the guarded offline runner."""
from datetime import date
from decimal import Decimal

import pytest

from app.financial_metric_registry import METRICS
from app.financial_metrics_service import FinancialMetrics, usable
from test_financial_insights import COMPANY, fact


CANONICAL = "0000000001-26-000001"
NON_ASCII = (
    "٠٠٠٠٠٠٠٠٠١-26-000001",
    "0000000001-٢٦-000001",
    "0000000001-26-٠٠٠٠٠١",
    "０００００００００１-26-000001",
    "0000000001-２６-000001",
    "0000000001-26-０００００１",
    "000000000١-26-000001",
)


@pytest.mark.parametrize("accession", NON_ASCII)
def test_non_ascii_accession_cannot_be_a_normalized_source(accession):
    row = fact(accession_number=accession)
    assert not usable(row, METRICS["revenue"])
    model = FinancialMetrics(COMPANY, [row])
    assert model.summary("annual").metrics["revenue"].status == "unavailable"
    assert model.history("revenue", "annual").history == []


@pytest.mark.parametrize("accession", NON_ASCII)
def test_malformed_newer_source_does_not_displace_canonical_observation(accession):
    original = fact(value="100", accession_number=CANONICAL)
    malformed = fact(value="999", id=2, accession_number=accession, filed=date(2026, 3, 1))
    point = FinancialMetrics(COMPANY, [original, malformed]).summary("annual").metrics["revenue"]
    assert point.status == "available" and point.value == Decimal("100")
    assert [source.fact_id for source in point.provenance] == [original.id]
    assert point.provenance[0].accession_number == CANONICAL
    assert point.provenance[0].sec_url == (
        "https://www.sec.gov/Archives/edgar/data/1/000000000126000001/"
        "0000000001-26-000001-index.html"
    )
    assert point.alternatives == []


@pytest.mark.parametrize("concept,metric", [
    ("Revenues", "net_margin"),
    ("NetIncomeLoss", "net_margin"),
    ("NetCashProvidedByUsedInOperatingActivities", "free_cash_flow"),
    ("PaymentsToAcquirePropertyPlantAndEquipment", "free_cash_flow"),
])
def test_malformed_operand_cannot_feed_a_derived_result(concept, metric):
    rows = [fact(name, value, id=index) for index, (name, value) in enumerate([
        ("Revenues", "100"), ("NetIncomeLoss", "20"),
        ("NetCashProvidedByUsedInOperatingActivities", "30"),
        ("PaymentsToAcquirePropertyPlantAndEquipment", "10"),
    ], start=1)]
    for row in rows:
        if row.metric == concept:
            row.accession_number = NON_ASCII[0]
    point = FinancialMetrics(COMPANY, rows).summary("annual").metrics[metric]
    assert point.status == "unavailable" and point.value is None


@pytest.mark.parametrize("accession", [CANONICAL, "0000000002-00-000000", "9999999999-99-999999"])
def test_ascii_accession_preserves_source_without_requiring_submitter_cik_match(accession):
    row = fact(value="123.45", accession_number=accession)
    assert usable(row, METRICS["revenue"])
    point = FinancialMetrics(COMPANY, [row]).summary("annual").metrics["revenue"]
    assert point.status == "available" and point.value == Decimal("123.45")
    assert point.provenance[0].accession_number == accession
