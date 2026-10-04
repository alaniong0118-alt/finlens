import os
import re
import time
from dataclasses import dataclass
from datetime import date

import httpx

from app.config import load_backend_env

load_backend_env()


SEC_BASE_URL = "https://data.sec.gov"
_last_request = 0.0


def _sec_get(url: str) -> httpx.Response:
    """Sequential fair-access requests; retry transient failures at most twice."""
    global _last_request
    with httpx.Client(headers=get_sec_headers(), timeout=60.0, follow_redirects=True) as client:
        for attempt in range(3):
            time.sleep(max(0.0, 0.25 - (time.monotonic() - _last_request)))
            _last_request = time.monotonic()
            try:
                response = client.get(url)
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as exc:
                if attempt == 2 or exc.response.status_code not in {403, 429, 500, 502, 503, 504}:
                    raise
            except httpx.TransportError:
                if attempt == 2:
                    raise
            time.sleep(2 ** (attempt + 1))
    raise RuntimeError("SEC request did not complete.")


@dataclass(frozen=True)
class FilingMetadata:
    company_cik: str
    accession_number: str
    form: str
    filed: date
    primary_document: str


def select_latest_filing(company_cik: str, rows: dict) -> FilingMetadata | None:
    """Prefer latest exact 10-Q, then exact 10-K; reject malformed metadata."""
    candidates = []
    forms = rows.get("form", [])
    fields = ("accessionNumber", "filingDate", "primaryDocument")
    if any(len(rows.get(field, [])) != len(forms) for field in fields):
        raise ValueError("SEC filing metadata arrays do not align.")
    for index, form in enumerate(forms):
        if form not in {"10-Q", "10-K"}:
            continue
        accession, filed, document = (rows[field][index] for field in fields)
        if (not re.fullmatch(r"\d{10}-\d{2}-\d{6}", accession)
                or not re.fullmatch(r"[A-Za-z0-9_.-]+", document)):
            raise ValueError("SEC filing identity is invalid.")
        candidates.append(FilingMetadata(company_cik, accession, form, date.fromisoformat(filed), document))
    return max(candidates, key=lambda f: (f.form == "10-Q", f.filed, f.accession_number)) if candidates else None


def discover_filing(company_cik: str) -> FilingMetadata | None:
    cik = company_cik.zfill(10)
    data = _sec_get(f"{SEC_BASE_URL}/submissions/CIK{cik}.json").json()
    if str(data.get("cik", "")).zfill(10) != cik:
        raise ValueError("SEC submissions identity does not match the company.")
    rows = data["filings"]["recent"]
    selected = select_latest_filing(cik, rows)
    if selected and selected.form == "10-Q":
        return selected
    # Recent metadata normally includes years of filings. Consult older official
    # pages only when needed to honor 10-Q preference; no predecessor substitution.
    candidates = [selected] if selected else []
    for archive in sorted(data["filings"].get("files", []), key=lambda a: a["filingTo"], reverse=True):
        filename = archive["name"]
        if not re.fullmatch(rf"CIK{cik}-submissions-\d+\.json", filename):
            raise ValueError("SEC archive metadata identity is invalid.")
        historical = select_latest_filing(cik, _sec_get(f"{SEC_BASE_URL}/submissions/{filename}").json())
        if historical:
            candidates.append(historical)
        # Older pages cannot contain a newer 10-Q than the page just examined.
        if historical and historical.form == "10-Q":
            break
    return max(candidates, key=lambda f: (f.form == "10-Q", f.filed, f.accession_number)) if candidates else None

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

    return _sec_get(url).json()
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

    return _sec_get(url).text
