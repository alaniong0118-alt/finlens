import os
import re

import httpx

from app.config import load_backend_env

load_backend_env()


SEC_BASE_URL = "https://data.sec.gov"

def get_sec_headers() -> dict[str, str]:
    """Require an explicit contact; never send a placeholder address to SEC."""
    contact = os.getenv("SEC_CONTACT_EMAIL", "").strip()
    domain = contact.rsplit("@", 1)[-1].lower()
    if (
        not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+", contact)
        or domain in {"example.com", "example.org", "example.net"}
        or domain.endswith((".example", ".invalid", ".test"))
        or "your_email" in contact.lower()
    ):
        raise ValueError("SEC_CONTACT_EMAIL is required for SEC requests.\nSet it in backend/.env.")
    return {
        "User-Agent": f"FinLens/0.1 (research project; contact: {contact})",
        "Accept-Encoding": "gzip, deflate",
    }


def get_company_facts(cik: str) -> dict:
    """Fetch SEC Company Facts for a company identified by CIK."""
    normalized_cik = cik.zfill(10)

    url = (
        f"{SEC_BASE_URL}/api/xbrl/companyfacts/"
        f"CIK{normalized_cik}.json"
    )

    with httpx.Client(
        headers=get_sec_headers(),
        timeout=30.0,
        follow_redirects=True,
    ) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.json()
def build_filing_url(
    company_cik: str,
    accession_number: str,
) -> str:
    """
    Build the SEC EDGAR filing detail URL
    from a CIK and accession number.
    """
    cik = str(int(company_cik))
    accession = accession_number
    accession_without_dashes = accession.replace("-", "")

    return (
        "https://www.sec.gov/Archives/edgar/data/"
        f"{cik}/"
        f"{accession_without_dashes}/"
        f"{accession}-index.html"
    )
def build_filing_raw_url(company_cik: str, accession_number: str) -> str:
    cik = str(int(company_cik))
    accession_without_dashes = accession_number.replace("-", "")

    return (
        "https://www.sec.gov/Archives/edgar/data/"
        f"{cik}/"
        f"{accession_without_dashes}/"
        f"{accession_number}.txt"
    )


def get_filing_raw_text(
    company_cik: str,
    accession_number: str,
) -> str:
    url = build_filing_raw_url(
        company_cik,
        accession_number,
    )

    with httpx.Client(
        headers=get_sec_headers(),
        timeout=30.0,
        follow_redirects=True,
    ) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.text
