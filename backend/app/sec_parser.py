from datetime import date
from typing import Any
import re

from bs4 import BeautifulSoup

def get_us_gaap_fact(
    facts: dict[str, Any],
    fact_name: str,
) -> dict[str, Any] | None:
    """
    Get a single US-GAAP fact from SEC Company Facts.
    """
    us_gaap = facts.get("facts", {}).get("us-gaap", {})

    return us_gaap.get(fact_name)


def get_fact_units(
    facts: dict[str, Any],
    fact_name: str,
) -> dict[str, list[dict[str, Any]]] | None:
    """
    Return the units available for a specific US-GAAP fact.
    """
    fact = get_us_gaap_fact(facts, fact_name)

    if not fact:
        return None

    return fact.get("units", {})


def list_us_gaap_facts(
    facts: dict[str, Any],
) -> list[str]:
    """
    Return all available US-GAAP fact names.
    """
    us_gaap = facts.get("facts", {}).get("us-gaap", {})

    return sorted(us_gaap.keys())


def get_fact_data(
    facts: dict[str, Any],
    fact_name: str,
) -> list[dict[str, Any]]:
    """
    Return all data points for a US-GAAP fact.
    """
    fact = get_us_gaap_fact(facts, fact_name)

    if not fact:
        return []

    units = fact.get("units", {})

    if "USD" in units:
        return units["USD"]

    return []


def classify_period(
    period_start: str | None,
    period_end: str | None,
) -> str | None:
    """
    Classify an SEC income-statement period by duration.

    Returns:
        quarter
        half_year
        nine_months
        annual
        unknown
        None
    """
    if not period_start or not period_end:
        return None

    start = date.fromisoformat(period_start)
    end = date.fromisoformat(period_end)

    duration_days = (end - start).days + 1

    if 75 <= duration_days <= 105:
        return "quarter"

    if 165 <= duration_days <= 200:
        return "half_year"

    if 245 <= duration_days <= 295:
        return "nine_months"

    if 330 <= duration_days <= 390:
        return "annual"

    return "unknown"


def normalize_fact_data(
    facts: dict[str, Any],
    fact_name: str,
    unit: str = "USD",
) -> list[dict[str, Any]]:
    """
    Convert SEC Company Facts data into FinLens standard records.
    """
    fact = get_us_gaap_fact(facts, fact_name)

    if not fact:
        return []

    units = fact.get("units", {})
    data = units.get(unit, [])

    normalized: list[dict[str, Any]] = []

    for item in data:
        period_start = item.get("start")
        period_end = item.get("end")

        normalized.append(
            {
                "metric": fact_name,
                "value": item.get("val"),
                "unit": unit,
                "period_start": period_start,
                "period_end": period_end,
                "period_type": classify_period(
                    period_start,
                    period_end,
                ),
                "fiscal_year": item.get("fy"),
                "fiscal_period": item.get("fp"),
                "form": item.get("form"),
                "filed": item.get("filed"),
                "accession_number": item.get("accn"),
                "frame": item.get("frame"),
                "source": "SEC Company Facts API",
            }
        )

    return normalized


def deduplicate_fact_data(
    data: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Remove duplicate SEC records for the same reporting period.

    Filing preference depends on the reporting period:

        quarter / half_year / nine_months
            -> prefer 10-Q / 10-Q-A

        annual
            -> prefer 10-K / 10-K-A

    Within the same filing type, keep the latest filing date.
    """

    def filing_priority(
        period_type: str | None,
        form: str | None,
    ) -> int:
        if period_type in {
            "quarter",
            "half_year",
            "nine_months",
        }:
            if form in {"10-Q", "10-Q/A"}:
                return 3

            if form in {"10-K", "10-K/A"}:
                return 2

            return 1

        if period_type == "annual":
            if form in {"10-K", "10-K/A"}:
                return 3

            if form in {"10-Q", "10-Q/A"}:
                return 2

            return 1

        if form in {"10-K", "10-K/A"}:
            return 2

        if form in {"10-Q", "10-Q/A"}:
            return 1

        return 0

    grouped: dict[tuple[Any, ...], dict[str, Any]] = {}

    for item in data:
        key = (
            item.get("metric"),
            item.get("unit"),
            item.get("period_start"),
            item.get("period_end"),
            item.get("period_type"),
        )

        existing = grouped.get(key)

        if existing is None:
            grouped[key] = item
            continue

        existing_priority = filing_priority(
            existing.get("period_type"),
            existing.get("form"),
        )

        current_priority = filing_priority(
            item.get("period_type"),
            item.get("form"),
        )

        if current_priority > existing_priority:
            grouped[key] = item
            continue

        if current_priority == existing_priority:
            existing_filed = existing.get("filed") or ""
            current_filed = item.get("filed") or ""

            if current_filed > existing_filed:
                grouped[key] = item

    return sorted(
        grouped.values(),
        key=lambda item: (
            item.get("period_end") or "",
            item.get("period_start") or "",
        ),
    )
    """
    Remove duplicate SEC records for the same reporting period.

    For the same metric, unit, period and period type,
    keep the record with the latest SEC filing date.
    """
    grouped: dict[tuple[Any, ...], dict[str, Any]] = {}

    for item in data:
        key = (
            item.get("metric"),
            item.get("unit"),
            item.get("period_start"),
            item.get("period_end"),
            item.get("period_type"),
        )

        existing = grouped.get(key)

        if existing is None:
            grouped[key] = item
            continue

        existing_filed = existing.get("filed") or ""
        current_filed = item.get("filed") or ""

        if current_filed > existing_filed:
            grouped[key] = item

    return sorted(
        grouped.values(),
        key=lambda item: (
            item.get("period_end") or "",
            item.get("period_start") or "",
        ),
    )
def extract_primary_filing_document(
    raw_text: str,
    form_type: str,
) -> dict:
    """
    Extract the primary SEC filing document from
    a complete EDGAR submission text.
    """
    pattern = re.compile(
        rf"(?ms)"
        rf"<DOCUMENT>\s*"
        rf"<TYPE>\s*{re.escape(form_type)}\s*"
        rf".*?"
        rf"<FILENAME>\s*(?P<filename>[^\r\n]+)\s*"
        rf".*?"
        rf"<TEXT>(?P<body>.*?)</TEXT>\s*"
        rf"</DOCUMENT>"
    )

    match = pattern.search(raw_text)

    if match is None:
        raise ValueError(
            f"Primary {form_type} document not found."
        )

    return {
        "form": form_type,
        "filename": match.group("filename").strip(),
        "html": match.group("body"),
    }


def clean_filing_html(html: str) -> str:
    """
    Convert inline XBRL HTML into readable filing text.
    """
    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    for tag in soup.find_all(
        ["script", "style"]
    ):
        tag.decompose()

    for tag in soup.find_all("ix:header"):
        tag.decompose()

    hidden_elements = []

    for tag in soup.find_all(
        style=True
    ):
        style = tag.get("style", "")
        normalized_style = style.replace(
            " ",
            "",
        ).lower()

        if "display:none" in normalized_style:
            hidden_elements.append(tag)

    for tag in hidden_elements:
        tag.decompose()

    root = soup.body or soup

    text = root.get_text(
        " ",
        strip=True,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def extract_filing_text(
    raw_text: str,
    form_type: str,
) -> dict:
    """
    Extract and clean the primary filing document.
    """
    document = extract_primary_filing_document(
        raw_text,
        form_type,
    )

    text = clean_filing_html(
        document["html"]
    )

    return {
        "form": document["form"],
        "filename": document["filename"],
        "text": text,
    }
def chunk_filing_text(
    text: str,
    chunk_size: int = 2500,
    overlap: int = 250,
) -> list[dict]:
    """
    Split filing text into overlapping chunks
    while preserving character offsets.
    """
    if chunk_size <= 0:
        raise ValueError(
            "chunk_size must be greater than zero."
        )

    if overlap < 0 or overlap >= chunk_size:
        raise ValueError(
            "overlap must be >= 0 and smaller than chunk_size."
        )

    chunks = []

    start = 0
    chunk_index = 0

    while start < len(text):
        end = min(
            start + chunk_size,
            len(text),
        )

        chunk_text = text[start:end].strip()

        if chunk_text:
            chunks.append(
                {
                    "chunk_id": (
                        f"chunk_{chunk_index:04d}"
                    ),
                    "text": chunk_text,
                    "start_char": start,
                    "end_char": end,
                }
            )

        if end >= len(text):
            break

        start = end - overlap
        chunk_index += 1

    return chunks