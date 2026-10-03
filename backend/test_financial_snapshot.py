from app.database import SessionLocal
from app.financial_analysis import get_financial_snapshot


NVIDIA_CIK = "0001045810"


if __name__ == "__main__":
    with SessionLocal() as session:
        snapshot = get_financial_snapshot(
            session,
            NVIDIA_CIK,
        )

        print("Company CIK:")
        print(snapshot["company_cik"])

        print("\nPeriod:")
        print(snapshot["period"])

        print("\nValues:")
        print(snapshot["values"])

        print("\nAnalysis:")
        for name, metric in snapshot["analysis"]["metrics"].items():
            print(
                name,
                ":",
                f"{metric['value']:.2f}{metric['unit']}",
            )