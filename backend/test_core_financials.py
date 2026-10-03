from sqlalchemy import select

from app.database import SessionLocal
from app.models import FinancialFact


NVIDIA_CIK = "0001045810"

CORE_METRICS = [
    ("Revenues", "USD"),
    ("NetIncomeLoss", "USD"),
    ("EarningsPerShareDiluted", "USD/shares"),
]


def get_latest_quarter(
    session,
    metric: str,
):
    stmt = (
        select(FinancialFact)
        .where(
            FinancialFact.company_cik == NVIDIA_CIK,
            FinancialFact.metric == metric,
            FinancialFact.period_type == "quarter",
        )
        .order_by(
            FinancialFact.period_end.desc(),
            FinancialFact.period_start.desc(),
        )
    )

    return session.scalars(stmt).first()


if __name__ == "__main__":
    with SessionLocal() as session:
        print("Latest quarterly financials:\n")

        for metric, unit in CORE_METRICS:
            record = get_latest_quarter(
                session,
                metric,
            )

            if record is None:
                print(f"{metric}: NOT FOUND")
                continue

            print(f"Metric: {record.metric}")
            print(f"Value: {record.value}")
            print(f"Unit: {record.unit}")
            print(
                f"Period: "
                f"{record.period_start} → {record.period_end}"
            )
            print(
                f"Fiscal: "
                f"FY{record.fiscal_year} {record.fiscal_period}"
            )
            print(f"Form: {record.form}")
            print(f"Filed: {record.filed}")
            print()