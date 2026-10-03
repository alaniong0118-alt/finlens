from app.sec_client import get_company_facts
from app.sec_parser import (
    deduplicate_fact_data,
    normalize_fact_data,
)


if __name__ == "__main__":
    facts = get_company_facts("0001045810")

    print("Company:", facts["entityName"])
    print("CIK:", facts["cik"])

    revenue_data = normalize_fact_data(
        facts,
        "Revenues",
        "USD",
    )

    print("\nBefore deduplication:")
    print("Total:", len(revenue_data))

    revenue_data = deduplicate_fact_data(
        revenue_data,
    )

    print("\nAfter deduplication:")
    print("Total:", len(revenue_data))

    print("\nRecent Revenue data:")

    for item in revenue_data[-10:]:
        print(
            item["period_start"],
            "→",
            item["period_end"],
            "|",
            item["period_type"],
            "|",
            item["value"],
            "| FY",
            item["fiscal_year"],
            "|",
            item["fiscal_period"],
            "|",
            item["form"],
            "| filed:",
            item["filed"],
            "| accn:",
            item["accession_number"],
        )