from app.database import SessionLocal
from app.financial_analysis import get_diluted_eps_yoy_growth


NVIDIA_CIK = "0001045810"


if __name__ == "__main__":
    with SessionLocal() as session:
        result = get_diluted_eps_yoy_growth(
            session,
            NVIDIA_CIK,
        )

        print("Metric:", result["metric"])
        print(
            "Growth:",
            f"{result['value']:.2f}{result['unit']}",
        )

        print("\nCurrent quarter:")
        print(result["current"])

        print("\nPrevious-year comparable quarter:")
        print(result["previous"])