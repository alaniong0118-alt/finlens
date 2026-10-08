"""Source freshness contracts; financial interpretation remains in FinancialMetrics."""
from datetime import date, datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Stream = Literal["facts", "evidence"]
Status = Literal["unknown", "pending", "current", "stale", "failed"]


def utcnow():
    return datetime.now(timezone.utc)


class StreamState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Status = "unknown"
    last_attempt_at: datetime | None = None
    last_checked_at: datetime | None = None
    last_successful_sync_at: datetime | None = None
    latest_source_filing_date: date | None = None
    last_error: str | None = None
    failure_stage: str | None = None
    pending_targets: list[str] = Field(default_factory=list)
    inventory_complete: bool = False


class FilingIdentity(BaseModel):
    accession_number: str
    form: str
    filed: date


class Freshness(BaseModel):
    ticker: str
    data_version: int = 0
    facts_version: int = 0
    evidence_version: int = 0
    status: Status = "unknown"
    facts: StreamState = Field(default_factory=StreamState)
    evidence: StreamState = Field(default_factory=StreamState)
    latest_indexed_filing: FilingIdentity | None = None
    migration_required: bool = False
    scope: str = "Supported Company Facts and latest 10-Q/10-K with amendments in the checked submissions window."


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tickers: list[str] = Field(min_length=1, max_length=35)
    stream: Literal["facts", "evidence", "both"] = "both"
    dry_run: bool = False
    max_filings: int = Field(default=2, ge=1, le=10)
    max_seconds: int = Field(default=300, ge=1, le=1800)
    max_run_seconds: int = Field(default=1800, ge=1, le=14400)


class RefreshResult(BaseModel):
    ticker: str
    stream: Stream
    status: Literal["updated", "no_change", "pending", "failed", "would_update", "interrupted", "indeterminate"]
    commit_outcome: Literal["not_attempted", "committed", "rolled_back", "indeterminate"] = "not_attempted"
    facts_inserted: int | None = 0
    inserted_by_metric: dict[str, int | None] = Field(default_factory=dict)
    filings_published: int | None = 0
    would_insert: int = 0
    version_before: int = 0
    version_after: int | None = 0
    error: str | None = None
    failure_stage: str | None = None
    pending_targets: list[str] = Field(default_factory=list)
