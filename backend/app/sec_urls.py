"""Pure SEC URL construction; no acquisition or configuration dependencies."""


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
