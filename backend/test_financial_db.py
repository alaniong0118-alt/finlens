from sqlalchemy import select

from app.database import SessionLocal
from app.models import FinancialFact


NVIDIA_CIK = "0001045810"


if __name__ == "__main__":
    with SessionLocal() as session:
        stmt = (
            select(FinancialFact)
            .where(
                FinancialFact.company_cik == NVIDIA_CIK,
                FinancialFact.metric == "Revenues",
            )
            .order_by(
                FinancialFact.period_end.desc(),
                FinancialFact.period_start.desc(),
            )
        )

        records = session.scalars(stmt).all()

        print("Revenue records in database:", len(records))

        print("\nLatest 10 Revenue records:")

        for record in records[:10]:
            print(
                record.period_start,
                "→",
                record.period_end,
                "|",
                record.period_type,
                "|",
                record.value,
                "| FY",
                record.fiscal_year,
                "|",
                record.fiscal_period,
                "|",
                record.form,
                "| filed:",
                record.filed,
            )