"""Dormant review proposal, NOT an installed or independently approved permission.

Production registries/loaders do not import this module. Importing it only creates
immutable descriptors; it performs no evidence I/O, registration or configuration.
Activation requires separate user approval, Astra High review and a code patch
installing the exact denominator record AND evidence policy into their registries.
There is deliberately no environment toggle, installer or registration function.
"""
from datetime import date
from decimal import Decimal

from app.revenue_scope_authorizations import (
    ApprovalRef, DenominatorAuthorization, EvidenceBinding, SourceIdentity,
)
from app.sec_evidence_adapter import ArtifactPin, EvidencePolicy, ObservationReview


REVIEWED_TICKER = "AAPL"  # Display/audit label; the authoritative issuer key is CIK.
DATABASE_FACT_IDS = (1853, 1976)  # Audit cross-reference, not financial identity.
EXPECTED_DATA_VERSIONS = (1, 0, 1)  # data / facts / evidence, bound by snapshot below.
REVENUE_BASIS = "customer_contract"  # Never relabel as total_revenue globally.
REF = ApprovalRef("denominator:net_margin", "aapl-net-margin-0000320193-26-000020-q3", 1)

REVENUE = SourceIdentity(
    cik="0000320193", source_namespace="SEC Company Facts API", taxonomy_namespace="us-gaap",
    concept="RevenueFromContractWithCustomerExcludingAssessedTax",
    start=date(2026, 3, 29), end=date(2026, 6, 27), kind="quarter", unit="USD",
    value=Decimal("109417000000"), accession="0000320193-26-000020",
    form="10-Q", filed=date(2026, 7, 31),
)
NET_INCOME = SourceIdentity(
    cik="0000320193", source_namespace="SEC Company Facts API", taxonomy_namespace="us-gaap",
    concept="NetIncomeLoss", start=date(2026, 3, 29), end=date(2026, 6, 27),
    kind="quarter", unit="USD", value=Decimal("29789000000"),
    accession="0000320193-26-000020", form="10-Q", filed=date(2026, 7, 31),
)
ARTIFACT = ArtifactPin(
    cik=REVENUE.cik, accession=REVENUE.accession, filename="aapl-20260627.htm",
    form="10-Q", filed=date(2026, 7, 31), period_end=date(2026, 6, 27),
    sha256="ff8ff7fb32493f9ca51b5d3afa6b336adacea503f7e50e53618a6e585e7eac07",
    byte_length=1018326, receipt_filename="retrieval-20261010T111011020789Z.json",
    receipt_sha256="0d3b3c51c53780ffa7564d57dfa6450d5a5041afb62855619ffcd8c5a3bee62a",
    gaap_namespace="http://fasb.org/us-gaap/2025", dei_namespace="http://xbrl.sec.gov/dei/2025",
)
STATEMENT_SHA256 = "417819dec67798830dd5659634bf5e9b3bfc130ad766946d4e883dc2b194889b"
REVIEWS = (
    ObservationReview(
        REVENUE, ARTIFACT.filename, "f-56", "c-18", 12, STATEMENT_SHA256,
        "consolidated_revenue",
        "Condensed consolidated statements of operations: Total net sales, three months ended June 27, 2026; consolidated revenue for this exact pair only.",
    ),
    ObservationReview(
        NET_INCOME, ARTIFACT.filename, "f-104", "c-18", 12, STATEMENT_SHA256,
        "consolidated_net_income",
        "Condensed consolidated statements of operations: Net income, three months ended June 27, 2026; consolidated net income for this exact pair only.",
    ),
)
REVENUE_BINDING = EvidenceBinding(
    REVENUE, "7dbb968795450f8003e3093e66229a98b565f0e7b2139656ac437e72f18fb949",
)
NET_INCOME_BINDING = EvidenceBinding(
    NET_INCOME, "7b5a3312bf2e56edbaa7210d5acbbee29c6426acae626a564b903060ed75e964",
)
PROPOSED_DENOMINATOR_AUTHORIZATION = DenominatorAuthorization(
    ref=REF, metric="net_margin", revenue=REVENUE_BINDING, numerator=NET_INCOME_BINDING,
    candidates=(REVENUE_BINDING, NET_INCOME_BINDING),
    reviewed_scope="Reviewed exact AAPL consolidated NetIncomeLoss / customer-contract Total net sales pair; denominator permission only, without Revenue selection or cross-basis equivalence.",
)
PROPOSED_EVIDENCE_POLICY = EvidencePolicy(
    ref=REF,
    approval_sha256="8b39531ff03ffd1f4a0fb9b58a20900aed6ae599f5dc12a9726ccfaaf1f56253",
    snapshot_sha256="01b530f47b1d7b15bd7306af097d3bf972eeef17dabdc72467e195451a540dd9",
    artifacts=(ARTIFACT,), observations=REVIEWS, parser_version="sec-inline-v2",
)
