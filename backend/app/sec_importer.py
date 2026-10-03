from decimal import Decimal

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Company, FinancialFact
from app.sec_client import get_company_facts
from app.sec_parser import (
    deduplicate_fact_data,
    normalize_fact_data,
)


METRIC_SOURCES = {
    "Revenues": {
    "facts": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
        "RevenuesNetOfInterestExpense",
    ],
    "unit": "USD",
},
    "NetIncomeLoss": {
        "facts": [
            "NetIncomeLoss",
        ],
        "unit": "USD",
    },
    "EarningsPerShareDiluted": {
        "facts": [
            "EarningsPerShareDiluted",
        ],
        "unit": "USD/shares",
    },
}


def build_metric_data(
    facts: dict,
    canonical_metric: str,
    source_fact_names: list[str],
    unit: str,
) -> list[dict]:
    """
    Collect multiple SEC XBRL concepts and normalize them
    into one FinLens canonical metric.
    """

    combined: list[dict] = []

    for source_fact_name in source_fact_names:
        data = normalize_fact_data(
            facts,
            source_fact_name,
            unit,
        )

        for item in data:
            # Convert different SEC concept names into
            # one stable FinLens metric name.
            item["metric"] = canonical_metric

            item["source"] = (
                "SEC Company Facts API: "
                f"{source_fact_name}"
            )

            # Ignore malformed records without a value.
            if item.get("value") is None:
                continue

            combined.append(item)

    return deduplicate_fact_data(combined)


def import_metric(
    company_cik: str,
    facts: dict,
    metric_name: str,
) -> int:
    """
    Import one canonical FinLens metric for a company.
    """

    config = METRIC_SOURCES[metric_name]

    data = build_metric_data(
        facts=facts,
        canonical_metric=metric_name,
        source_fact_names=config["facts"],
        unit=config["unit"],
    )

    with SessionLocal() as session:
        session.query(FinancialFact).filter(
            FinancialFact.company_cik == company_cik,
            FinancialFact.metric == metric_name,
        ).delete(
            synchronize_session=False,
        )

        for item in data:
            record = FinancialFact(
                company_cik=company_cik,
                metric=metric_name,
                value=Decimal(str(item["value"])),
                unit=item["unit"],
                period_start=item["period_start"],
                period_end=item["period_end"],
                period_type=item["period_type"],
                fiscal_year=item["fiscal_year"],
                fiscal_period=item["fiscal_period"],
                form=item["form"],
                filed=item["filed"],
                accession_number=item["accession_number"],
                frame=item["frame"],
                source=item["source"],
            )

            session.add(record)

        session.commit()

        return len(data)


def import_company(
    company_cik: str,
) -> dict[str, int]:
    """
    Import all core financial metrics for one company.
    """

    normalized_cik = company_cik.zfill(10)

    facts = get_company_facts(
        normalized_cik
    )

    results: dict[str, int] = {}

    for metric_name in METRIC_SOURCES:
        results[metric_name] = import_metric(
            normalized_cik,
            facts,
            metric_name,
        )

    return results


def import_all_companies() -> None:
    """
    Import all companies currently registered
    in the Company table.
    """

    with SessionLocal() as session:
        companies = session.scalars(
            select(Company).order_by(Company.ticker)
        ).all()

        company_data = [
            (
                company.ticker,
                company.cik,
            )
            for company in companies
        ]

    for ticker, cik in company_data:
        print(
            f"Importing {ticker} "
            f"(CIK {cik})..."
        )

        try:
            results = import_company(cik)

            print(
                f"  Revenue: "
                f"{results['Revenues']}"
            )

            print(
                f"  Net Income: "
                f"{results['NetIncomeLoss']}"
            )

            print(
                f"  Diluted EPS: "
                f"{results['EarningsPerShareDiluted']}"
            )

        except Exception as exc:
            print(
                f"  FAILED: "
                f"{type(exc).__name__}: {exc}"
            )


if __name__ == "__main__":
    import_all_companies()