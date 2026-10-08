import os
import re
import time
from urllib.parse import urlsplit
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import httpx

from app.config import load_backend_env

load_backend_env()


SEC_BASE_URL = "https://data.sec.gov"
_last_request = 0.0
MAX_RESPONSE_BYTES = 64 * 1024 * 1024


def _sec_get(url: str) -> httpx.Response:
    """Sequential fair-access requests; retry transient failures at most twice."""
    global _last_request
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname not in {"data.sec.gov", "www.sec.gov"}
            or parsed.username or parsed.password or parsed.port not in {None, 443}
            or not parsed.path.startswith(("/submissions/", "/api/xbrl/companyfacts/", "/Archives/edgar/data/"))
            or parsed.query or parsed.fragment):
        raise ValueError("Untrusted SEC source URL.")
    with httpx.Client(headers=get_sec_headers(), timeout=60.0, follow_redirects=False) as client:
        for attempt in range(3):
            time.sleep(max(0.0, 0.25 - (time.monotonic() - _last_request)))
            _last_request = time.monotonic()
            try:
                with client.stream("GET", url) as response:
                    response.raise_for_status()
                    body = bytearray()
                    for block in response.iter_bytes():
                        body.extend(block)
                        if len(body) > MAX_RESPONSE_BYTES:
                            raise ValueError("SEC response exceeds the configured size bound.")
                    headers = {k: v for k, v in response.headers.items() if k.lower() not in {"content-encoding", "content-length", "transfer-encoding"}}
                    return httpx.Response(response.status_code, headers=headers, content=bytes(body), request=response.request)
            except httpx.HTTPStatusError as exc:
                if attempt == 2 or exc.response.status_code not in {403, 429, 500, 502, 503, 504}:
                    raise
            except httpx.TransportError:
                if attempt == 2:
                    raise
            retry_after = response.headers.get("Retry-After", "") if 'response' in locals() else ""
            delay = min(30, int(retry_after)) if retry_after.isdigit() else 2 ** (attempt + 1)
            time.sleep(max(2 ** (attempt + 1), delay))
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

    # Avoid binary-float rounding before Numeric(24,4) representability checks.
    return _sec_get(url).json(parse_float=Decimal)
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


def discover_refresh_filings(company_cik: str):
    """Bounded recent inventory, latest Q/K independently and recent amendments.

    Complete means both base forms found in the recent window, not all EDGAR
    history. Sparse registrants remain pending; no predecessor guesses.
    """
    cik = company_cik.zfill(10)
    data = _sec_get(f"{SEC_BASE_URL}/submissions/CIK{cik}.json").json()
    if str(data.get("cik", "")).zfill(10) != cik:
        raise ValueError("SEC submissions identity mismatch.")
    rows = data["filings"]["recent"]
    forms = rows["form"]
    if len(forms) > 2000 or any(len(rows.get(f, [])) != len(forms) for f in ("accessionNumber", "filingDate", "primaryDocument")):
        raise ValueError("Invalid or oversized submissions inventory.")
    candidates = []
    for i, form in enumerate(forms):
        if form not in {"10-Q", "10-K", "10-Q/A", "10-K/A"}:
            continue
        accession, document = rows["accessionNumber"][i], rows["primaryDocument"][i]
        if not re.fullmatch(r"\d{10}-\d{2}-\d{6}", accession) or not re.fullmatch(r"[A-Za-z0-9_.-]+", document):
            raise ValueError("Invalid filing identity.")
        candidates.append(FilingMetadata(cik, accession, form, date.fromisoformat(rows["filingDate"][i]), document))
    selected = [max(group, key=lambda m: (m.filed, m.accession_number)) for form in ("10-Q", "10-K")
                if (group := [m for m in candidates if m.form == form])]
    # Recent amendments are retained as separate evidence, never substituted
    # for another accession. An older amendment still may revise old facts.
    selected.extend(m for m in candidates if m.form.endswith("/A"))
    selected.sort(key=lambda m: (m.filed, m.accession_number))
    return {"filings": selected, "complete": len({m.form for m in selected} & {"10-Q", "10-K"}) == 2}
