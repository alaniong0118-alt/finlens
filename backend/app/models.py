from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, Text, UniqueConstraint
from pgvector.sqlalchemy import VECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    ticker: Mapped[str] = mapped_column(
        String(10),
        unique=True,
        index=True,
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    cik: Mapped[str] = mapped_column(
        String(10),
        unique=True,
        nullable=False,
    )

    exchange: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )


class FinancialFact(Base):
    __tablename__ = "financial_facts"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    company_cik: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        index=True,
    )

    metric: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    value: Mapped[Decimal] = mapped_column(
        Numeric(24, 4),
        nullable=False,
    )

    unit: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    period_start: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    period_end: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        index=True,
    )

    period_type: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    fiscal_year: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    fiscal_period: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )

    form: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    filed: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    accession_number: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    frame: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    source: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

class FilingChunk(Base):
    __tablename__ = "filing_chunks"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    company_cik: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        index=True,
    )

    accession_number: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
    )

    form: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    filed: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    chunk_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    start_char: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    end_char: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    sec_url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    embedding: Mapped[list[float] | None] = mapped_column(
        VECTOR(384),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )


Index(
    "ix_filing_chunks_company_accession",
    FilingChunk.company_cik,
    FilingChunk.accession_number,
)

Index(
    "ix_filing_chunks_accession_index",
    FilingChunk.accession_number,
    FilingChunk.chunk_index,
    unique=True,
)
Index(
    "ix_financial_facts_company_metric_period",
    FinancialFact.company_cik,
    FinancialFact.metric,
    FinancialFact.period_end,
)


class CompanyRefreshState(Base):
    __tablename__ = "company_refresh_state"
    company_cik: Mapped[str] = mapped_column(String(10), ForeignKey("companies.cik"), primary_key=True)
    data_version: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    facts_version: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    evidence_version: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    facts: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    __table_args__ = (CheckConstraint("data_version >= 0 AND facts_version >= 0 AND evidence_version >= 0 AND facts_version <= data_version AND evidence_version <= data_version", name="ck_refresh_versions"),)


class RefreshAttempt(Base):
    __tablename__ = "refresh_attempts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    company_cik: Mapped[str] = mapped_column(String(10), ForeignKey("companies.cik"), nullable=False, index=True)
    stream: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_version: Mapped[int | None] = mapped_column(BigInteger)
    source_digest: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    __table_args__ = (
        UniqueConstraint("company_cik", "published_version", name="uq_refresh_committed_version"),
        CheckConstraint("stream IN ('facts', 'evidence')", name="ck_refresh_stream"),
        CheckConstraint("status IN ('running', 'updated', 'no_change', 'pending', 'failed', 'interrupted')", name="ck_refresh_attempt_status"),
        CheckConstraint("published_version IS NULL OR (published_version > 0 AND status IN ('updated', 'pending'))", name="ck_refresh_event_version"),
    )


class FilingPublication(Base):
    __tablename__ = "filing_publications"
    company_cik: Mapped[str] = mapped_column(String(10), ForeignKey("companies.cik"), primary_key=True)
    accession_number: Mapped[str] = mapped_column(String(30), primary_key=True)
    form: Mapped[str] = mapped_column(String(20), nullable=False)
    filed: Mapped[date] = mapped_column(Date, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False)
    content_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    cleaned_text: Mapped[str | None] = mapped_column(Text)
    configuration: Mapped[str] = mapped_column(String(200), nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    data_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    __table_args__ = (CheckConstraint("chunk_count > 0 AND data_version >= 0", name="ck_publication_counts"),)
