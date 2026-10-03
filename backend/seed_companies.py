from sqlalchemy import select

from app.database import SessionLocal
from app.models import Company


COMPANIES = [
    {
        "ticker": "NVDA",
        "name": "NVIDIA Corporation",
        "cik": "0001045810",
        "exchange": "NASDAQ",
    },
    {
        "ticker": "AAPL",
        "name": "Apple Inc.",
        "cik": "0000320193",
        "exchange": "NASDAQ",
    },
    {
        "ticker": "MSFT",
        "name": "Microsoft Corporation",
        "cik": "0000789019",
        "exchange": "NASDAQ",
    },
    {
        "ticker": "AMZN",
        "name": "Amazon.com, Inc.",
        "cik": "0001018724",
        "exchange": "NASDAQ",
    },
    {
        "ticker": "GOOGL",
        "name": "Alphabet Inc.",
        "cik": "0001652044",
        "exchange": "NASDAQ",
    },
    {
        "ticker": "META",
        "name": "Meta Platforms, Inc.",
        "cik": "0001326801",
        "exchange": "NASDAQ",
    },
    {
        "ticker": "TSLA",
        "name": "Tesla, Inc.",
        "cik": "0001318605",
        "exchange": "NASDAQ",
    },
    {
        "ticker": "JPM",
        "name": "JPMorgan Chase & Co.",
        "cik": "0000019617",
        "exchange": "NYSE",
    },
    {
        "ticker": "V",
        "name": "Visa Inc.",
        "cik": "0001403161",
        "exchange": "NYSE",
    },
    {
        "ticker": "WMT",
        "name": "Walmart Inc.",
        "cik": "0000104169",
        "exchange": "NYSE",
    },
]


def seed_companies() -> None:
    with SessionLocal() as session:
        for data in COMPANIES:
            existing = session.scalar(
                select(Company).where(Company.ticker == data["ticker"])
            )

            if existing is None:
                session.add(Company(**data))
                print(f"Added {data['ticker']}")
            else:
                print(f"Skipped {data['ticker']} (already exists)")

        session.commit()


if __name__ == "__main__":
    seed_companies()