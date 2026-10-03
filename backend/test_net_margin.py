from app.database import SessionLocal
from app.financial_analysis import get_net_margin


NVIDIA_CIK = "0001045810"


if __name__ == "__main__":
    with SessionLocal() as session:
        result = get_net_margin(
            session,
            NVIDIA_CIK,
        )

        print("Metric:", result["metric"])
        print(
            "Net Margin:",
            f"{result['value']:.2f}{result['unit']}",
        )

        print("\nCurrent period:")
        print(result["current"])