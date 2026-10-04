from contextlib import nullcontext

from sqlalchemy import select
from sqlalchemy.orm import Session

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
    # Added issuers verified against SEC company_tickers_exchange.json.
    # Names are SEC canonical strings; verification is recorded in reports/.
    # Financial services
    {
        "ticker": "BAC",
        "name": "BANK OF AMERICA CORP /DE/",
        "cik": "0000070858",
        "exchange": "NYSE",
    },
    {
        "ticker": "GS",
        "name": "GOLDMAN SACHS GROUP INC",
        "cik": "0000886982",
        "exchange": "NYSE",
    },
    {
        "ticker": "MS",
        "name": "MORGAN STANLEY",
        "cik": "0000895421",
        "exchange": "NYSE",
    },
    {
        "ticker": "MA",
        "name": "Mastercard Inc",
        "cik": "0001141391",
        "exchange": "NYSE",
    },
    {
        "ticker": "AXP",
        "name": "AMERICAN EXPRESS CO",
        "cik": "0000004962",
        "exchange": "NYSE",
    },
    # Consumer / retail / media
    {
        "ticker": "COST",
        "name": "COSTCO WHOLESALE CORP /NEW",
        "cik": "0000909832",
        "exchange": "NASDAQ",
    },
    {
        "ticker": "HD",
        "name": "HOME DEPOT, INC.",
        "cik": "0000354950",
        "exchange": "NYSE",
    },
    {
        "ticker": "KO",
        "name": "COCA COLA CO",
        "cik": "0000021344",
        "exchange": "NYSE",
    },
    {
        "ticker": "PEP",
        "name": "PEPSICO INC",
        "cik": "0000077476",
        "exchange": "NASDAQ",
    },
    {
        "ticker": "MCD",
        "name": "MCDONALDS CORP",
        "cik": "0000063908",
        "exchange": "NYSE",
    },
    {
        "ticker": "DIS",
        "name": "Walt Disney Co",
        "cik": "0001744489",
        "exchange": "NYSE",
    },
    # Healthcare
    {
        "ticker": "JNJ",
        "name": "JOHNSON & JOHNSON",
        "cik": "0000200406",
        "exchange": "NYSE",
    },
    {
        "ticker": "LLY",
        "name": "ELI LILLY & Co",
        "cik": "0000059478",
        "exchange": "NYSE",
    },
    {
        "ticker": "MRK",
        "name": "Merck & Co., Inc.",
        "cik": "0000310158",
        "exchange": "NYSE",
    },
    {
        "ticker": "ABBV",
        "name": "AbbVie Inc.",
        "cik": "0001551152",
        "exchange": "NYSE",
    },
    {
        "ticker": "UNH",
        "name": "UNITEDHEALTH GROUP INC",
        "cik": "0000731766",
        "exchange": "NYSE",
    },
    # Energy
    {
        "ticker": "XOM",
        "name": "ExxonMobil Holdings Corp",
        "cik": "0002115436",
        "exchange": "NYSE",
    },
    {
        "ticker": "CVX",
        "name": "CHEVRON CORP",
        "cik": "0000093410",
        "exchange": "NYSE",
    },
    {
        "ticker": "COP",
        "name": "CONOCOPHILLIPS",
        "cik": "0001163165",
        "exchange": "NYSE",
    },
    # Industrials
    {
        "ticker": "CAT",
        "name": "CATERPILLAR INC",
        "cik": "0000018230",
        "exchange": "NYSE",
    },
    {
        "ticker": "GE",
        "name": "GENERAL ELECTRIC CO",
        "cik": "0000040545",
        "exchange": "NYSE",
    },
    {
        "ticker": "HON",
        "name": "HONEYWELL INTERNATIONAL INC",
        "cik": "0000773840",
        "exchange": "NASDAQ",
    },
    {
        "ticker": "UPS",
        "name": "UNITED PARCEL SERVICE INC",
        "cik": "0001090727",
        "exchange": "NYSE",
    },
    # Automotive
    {
        "ticker": "GM",
        "name": "General Motors Co",
        "cik": "0001467858",
        "exchange": "NYSE",
    },
    {
        "ticker": "F",
        "name": "FORD MOTOR CO",
        "cik": "0000037996",
        "exchange": "NYSE",
    },
]


def seed_companies(session: Session | None = None, *, quiet: bool = False) -> None:
    """Insert missing catalog rows; preserve existing rows and reject identity conflicts."""
    with (nullcontext(session) if session is not None else SessionLocal()) as session:
        existing_companies = session.scalars(select(Company)).all()
        by_ticker = {company.ticker: company for company in existing_companies}
        by_cik = {company.cik: company for company in existing_companies}
        # Check all identities before adding anything. Names may be customized locally.
        for data in COMPANIES:
            existing = by_ticker.get(data["ticker"])
            if existing is not None and existing.cik != data["cik"]:
                raise ValueError(f"Catalog CIK conflict for {data['ticker']}")
            owner = by_cik.get(data["cik"])
            if owner is not None and owner.ticker != data["ticker"]:
                raise ValueError(f"Catalog ticker conflict for {data['ticker']}")

        for data in COMPANIES:
            if data["ticker"] not in by_ticker:
                session.add(Company(**data))
                if not quiet:
                    print(f"Added {data['ticker']}")
            else:
                if not quiet:
                    print(f"Skipped {data['ticker']} (already exists)")

        session.commit()


if __name__ == "__main__":
    seed_companies()
