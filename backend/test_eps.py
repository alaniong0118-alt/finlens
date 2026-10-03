from app.sec_client import get_company_facts
from app.sec_parser import (
    deduplicate_fact_data,
    normalize_fact_data,
)


NVIDIA_CIK = "0001045810"


if __name__ == "__main__":
    facts = get_company_facts(NVIDIA_CIK)

    print("Company:", facts["entityName"])
    print("CIK:", facts["cik"])

    eps_data = normalize_fact_data(
        facts,
        "EarningsPerShareDiluted",
        "USD/shares",
    )

    print("\nBefore deduplication:")
    print("Total:", len(eps_data))

    eps_data = deduplicate_fact_data(
        eps_data,
    )

    print("\nAfter deduplication:")
    print("Total:", len(eps_data))

    print("\nRecent Diluted EPS data:")

    for item in eps_data[-10:]:
        print(
            item["period_start"],
            "→",
            item["period_end"],
            "|",
            item["period_type"],
            "|",
            item["value"],
            "|",
            item["unit"],
            "| FY",
            item["fiscal_year"],
            "|",
            item["fiscal_period"],
            "|",
            item["form"],
            "| filed:",
            item["filed"],
        )