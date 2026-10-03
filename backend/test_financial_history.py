from app.database import SessionLocal
from app.financial_analysis import get_financial_history


NVIDIA_CIK = "0001045810"


if __name__ == "__main__":
    with SessionLocal() as session:
        history = get_financial_history(
            session,
            NVIDIA_CIK,
        )

        print("Quarterly history records:", len(history))

        print("\nLatest 10 quarters:")

        for item in history[-10:]:
            print(
                item["period_start"],
                "→",
                item["period_end"],
                "| FY",
                item["fiscal_year"],
                item["fiscal_period"],
                "| Revenue:",
                item["revenue"],
                "| Net Income:",
                item["net_income"],
                "| EPS:",
                item["diluted_eps"],
                "| filed:",
                item["filed"],
            )