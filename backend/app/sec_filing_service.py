from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Company, FinancialFact, FilingChunk
from app.sec_client import (
    build_filing_url,
    get_filing_raw_text,
    FilingMetadata,
)
from app.sec_parser import (
    chunk_filing_text,
    extract_filing_text,
)


def ingest_filing_chunks(
    session: Session,
    company: Company,
    accession_number: str,
    *,
    metadata: FilingMetadata | None = None,
    preserve_existing: bool = True,
) -> int:
    from sqlalchemy.orm import sessionmaker
    from app.refresh_service import coordinator
    with coordinator(sessionmaker(bind=session.get_bind())):
        return _ingest_filing_chunks(session, company, accession_number, metadata=metadata, preserve_existing=preserve_existing)


def _ingest_filing_chunks(session, company, accession_number, *, metadata=None, preserve_existing=True):
    if not preserve_existing:
        raise ValueError("Replacing persisted filing evidence is not supported.")
    if preserve_existing:
        existing = session.scalars(select(FilingChunk).where(
            FilingChunk.company_cik == company.cik,
            FilingChunk.accession_number == accession_number,
        )).all()
        if existing:
            return len(existing)

    filing = metadata or session.scalar(
        select(FinancialFact)
        .where(
            FinancialFact.company_cik == company.cik,
            FinancialFact.accession_number
            == accession_number,
        )
        .order_by(
            FinancialFact.filed.desc()
        )
    )

    if filing is None:
        raise ValueError(
            f"Filing '{accession_number}' "
            f"not found for {company.ticker}."
        )

    form = filing.form

    if metadata and (metadata.company_cik != company.cik or metadata.accession_number != accession_number):
        raise ValueError("Filing metadata does not match the requested identity.")

    if not form:
        raise ValueError(
            f"Filing '{accession_number}' has no form."
        )

    raw_text = get_filing_raw_text(
        company.cik,
        accession_number,
    )

    parsed = extract_filing_text(
        raw_text,
        form,
    )

    chunks = chunk_filing_text(
        parsed["text"]
    )

    if metadata and parsed["filename"] != metadata.primary_document:
        raise ValueError("Primary document does not match SEC submissions metadata.")
    if not chunks:
        raise ValueError("Filing contains no usable text chunks.")

    from app.refresh_service import state_row
    # Legacy staging is durable but unpublished until all vectors validate.
    state_row(session, company.cik)

    sec_url = build_filing_url(
        company.cik,
        accession_number,
    )

    for index, chunk in enumerate(chunks):
        session.add(
            FilingChunk(
                company_cik=company.cik,
                accession_number=accession_number,
                form=parsed["form"],
                filename=parsed["filename"],
                filed=filing.filed,
                chunk_index=index,
                chunk_id=chunk["chunk_id"],
                text=chunk["text"],
                start_char=chunk["start_char"],
                end_char=chunk["end_char"],
                sec_url=sec_url,
            )
        )

    session.commit()

    return len(chunks)
