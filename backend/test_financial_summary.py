from app.database import SessionLocal
from app.financial_analysis import get_financial_summary


NVIDIA_CIK = "0001045810"


if __name__ == "__main__":
    with SessionLocal() as session:
        summary = get_financial_summary(
            session,
            NVIDIA_CIK,
        )

        print("Company CIK:")
        print(summary["company_cik"])

        print("\nFinancial Summary:")

        revenue = summary["metrics"]["revenue_yoy_growth"]
        net_income = summary["metrics"]["net_income_yoy_growth"]
        net_margin = summary["metrics"]["net_margin"]
        eps_growth = summary["metrics"]["diluted_eps_yoy_growth"]

        print(
            "Revenue YoY Growth:",
            f"{revenue['value']:.2f}{revenue['unit']}",
        )

        print(
            "Net Income YoY Growth:",
            f"{net_income['value']:.2f}{net_income['unit']}",
        )

        print(
            "Net Margin:",
            f"{net_margin['value']:.2f}{net_margin['unit']}",
        )

        print(
            "Diluted EPS YoY Growth:",
            f"{eps_growth['value']:.2f}{eps_growth['unit']}",
        )