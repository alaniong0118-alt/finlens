"""Canonical definitions and explicitly reviewed revenue economic scopes."""
from dataclasses import dataclass


@dataclass(frozen=True)
class MetricDefinition:
    unit: str
    source_unit: str
    kind: str
    concepts: tuple[str, ...] = ()
    formula: str | None = None


@dataclass(frozen=True)
class RevenueConcept:
    basis: str
    meaning: str
    margin_denominator: bool


# Meanings checked against FASB 2026 documentation and the 2018 legacy taxonomy.
# Customer-contract and net-sales observations do not establish total issuer
# revenue; their absence of other components is not evidence of consolidation.
REVENUE_CONCEPTS = {
    "Revenues": RevenueConcept("total_revenue", "Total earning activities, including interest before interest expense.", True),
    "RevenueFromContractWithCustomerExcludingAssessedTax": RevenueConcept("customer_contract", "Customer performance obligations, excluding collected taxes; may be a subset of total revenue.", False),
    "SalesRevenueNet": RevenueConcept("net_sales", "Normal-course goods/services less returns, allowances and discounts; does not establish other revenue coverage.", False),
    "RevenuesNetOfInterestExpense": RevenueConcept("net_interest", "Earning activities including interest after interest expense; financial-institution basis.", True),
}

# No cross-basis equivalence is established by this dataset or by taxonomy
# labels alone. Future reviewed declarations belong here, never in ticker rules.
REVENUE_EQUIVALENCES: frozenset[frozenset[str]] = frozenset()


def revenue_bases_compatible(left, right):
    return left == right or frozenset((left, right)) in REVENUE_EQUIVALENCES


# Revenue aliases are all present in the audited database. Other base metrics
# have one standard primary concept, conditional on a real matching source row;
# they have no current coverage and no speculative fallback aliases.
METRICS = {
    "revenue": MetricDefinition("USD", "USD", "duration", (
        "RevenuesNetOfInterestExpense",  # net interest expense is the bank revenue basis
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues", "SalesRevenueNet",
    )),
    "gross_profit": MetricDefinition("USD", "USD", "duration", ("GrossProfit",)),
    "operating_income": MetricDefinition("USD", "USD", "duration", ("OperatingIncomeLoss",)),
    "net_income": MetricDefinition("USD", "USD", "duration", ("NetIncomeLoss",)),
    "diluted_eps": MetricDefinition("USD/share", "USD/shares", "duration", ("EarningsPerShareDiluted",)),
    "cash_and_equivalents": MetricDefinition("USD", "USD", "instant", ("CashAndCashEquivalentsAtCarryingValue",)),
    "total_assets": MetricDefinition("USD", "USD", "instant", ("Assets",)),
    "total_liabilities": MetricDefinition("USD", "USD", "instant", ("Liabilities",)),
    "operating_cash_flow": MetricDefinition("USD", "USD", "duration", ("NetCashProvidedByUsedInOperatingActivities",)),
    "capital_expenditures": MetricDefinition("USD", "USD", "duration", ("PaymentsToAcquirePropertyPlantAndEquipment",)),
    "free_cash_flow": MetricDefinition("USD", "USD", "derived", formula="operating_cash_flow - capital_expenditures"),
    "revenue_growth_yoy": MetricDefinition("ratio", "ratio", "derived", formula="(revenue - prior_comparable_revenue) / prior_comparable_revenue"),
    "gross_margin": MetricDefinition("ratio", "ratio", "derived", formula="gross_profit / revenue"),
    "operating_margin": MetricDefinition("ratio", "ratio", "derived", formula="operating_income / revenue"),
    "net_margin": MetricDefinition("ratio", "ratio", "derived", formula="net_income / revenue"),
}

SELECTION_POLICY = "Exact dates and units; establish revenue economic scope first, then latest filed, compatible concept priority, period-appropriate form, amendment, accession, fact ID."
