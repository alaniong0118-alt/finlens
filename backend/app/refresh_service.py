"""Incremental SEC refresh using reviewed ingest primitives and atomic publication.

No work runs at import/startup. Live acquisition is only invoked by an explicit
operator command. Injected sources make all tests fully offline.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import date
import hashlib
import json
import threading
import time
from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.models import Company, FinancialFact, FilingChunk, CompanyRefreshState, RefreshAttempt, FilingPublication
from app.refresh_contracts import RefreshRequest, RefreshResult, StreamState, utcnow
from app.freshness_service import chunk_digest, stored_chunks, validate_chunks
from app.sec_importer import METRIC_SOURCES, FinancialSyncError, build_metric_data, fact_identity, merge_company_facts
from app.sec_client import FilingMetadata, build_filing_url, get_company_facts, get_filing_raw_text
from app.sec_parser import extract_filing_text, chunk_filing_text
from app.embedding_service import MODEL_NAME, embed_texts, validate_embedding

CONFIGURATION = f"parser-v1/chunk-2500-overlap-250/{MODEL_NAME}"
COORDINATOR_LOCK = (1 << 44) + 613
_local_lock = threading.Lock()
_admission = ContextVar("refresh_admission", default=None)


class RefreshBusy(RuntimeError):
    pass


@dataclass
class RefreshAdmission:
    connection: object = None

    def __call__(self):
        connection = self.connection
        if connection is not None:
            if connection.invalidated or connection.closed:
                raise RefreshBusy("refresh_lock_lost")
            try:
                probe_transaction = not connection.in_transaction()
                connection.execute(text("SELECT 1"))
                if probe_transaction:
                    connection.commit()  # Never commit an active publication on reentry.
            except Exception:
                raise RefreshBusy("refresh_lock_lost") from None


@contextmanager
def publication_session(factory, owned):
    """Publication and admission share one physical PostgreSQL connection.

    Loss after the ownership probe therefore kills the publication transaction;
    it cannot reconnect on a separate session and publish as a displaced worker.
    """
    owned()
    if owned.connection is None:
        with factory() as session:
            yield session
    else:
        try:
            with factory(bind=owned.connection) as session:
                yield session
        except DBAPIError:
            # A rollback/commit driver error may leave a live transaction even
            # when SQLAlchemy considers it inactive. Close the physical owner
            # before a fresh connection reconciles the durable ledger.
            owned.connection.invalidate()
            raise


def reconcile_publication(factory, cik, attempt_id):
    """Read durable outcome on a fresh connection after an ambiguous commit.

    Waiting for the publication's per-CIK lock establishes that its transaction
    has ended before interpreting a still-running attempt as rolled back.
    No metadata is changed here, and a bounded lock wait may remain indeterminate.
    """
    with factory() as session:
        if session.get_bind().dialect.name == "postgresql":
            session.execute(text("SET TRANSACTION READ ONLY"))
            session.execute(text("SET LOCAL lock_timeout = '5s'"))
            session.execute(text("SET LOCAL statement_timeout = '5s'"))
            session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": (1 << 40) + int(cik)})
        attempt = session.get(RefreshAttempt, attempt_id)
        if attempt is None:
            raise RuntimeError("publication_attempt_unavailable")
        if attempt.status in {"updated", "pending", "no_change"}:
            return RefreshResult.model_validate(attempt.details)
        if attempt.status not in {"running", "failed", "interrupted"}:
            raise RuntimeError("publication_outcome_unavailable")
    return None  # Publication ended without its atomic successful ledger update.


@contextmanager
def coordinator(factory):
    """Single SEC worker across processes; transaction locks still guard facts."""
    if _admission.get() is not None:
        _admission.get()()
        yield _admission.get()
        return
    if not _local_lock.acquire(blocking=False):
        raise RefreshBusy("refresh_busy")
    connection, token = None, None
    try:
        bind = getattr(factory, "kw", {}).get("bind")
        if bind is not None and bind.dialect.name == "postgresql":
            connection = bind.connect()
            if not connection.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": COORDINATOR_LOCK}):
                raise RefreshBusy("refresh_busy")
            connection.commit()
        owned = RefreshAdmission(connection)
        token = _admission.set(owned)
        yield owned
    finally:
        if token is not None:
            _admission.reset(token)
        try:
            if connection is not None:
                try:
                    # This connection is dedicated to admission/publication for
                    # the job. Always retire it: physical close aborts residual
                    # work and releases session advisory locks, without cleanup
                    # SQL or any possibility of committing a failed rollback.
                    connection.invalidate()
                finally:
                    connection.close()
        finally:
            _local_lock.release()


def state_row(session, cik):
    if session.get_bind().dialect.name == "postgresql":
        session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": (1 << 40) + int(cik)})
    row = session.scalar(select(CompanyRefreshState).where(CompanyRefreshState.company_cik == cik).with_for_update())
    if row is None:
        row = CompanyRefreshState(company_cik=cik, data_version=0, facts_version=0, evidence_version=0, facts={}, evidence={})
        session.add(row)
        session.flush()
    return row


def record_fact_change(session, cik, inserted, by_metric):
    """Compatibility writers publish a version but cannot certify a full check."""
    if not inserted:
        return
    state = state_row(session, cik)
    state.data_version += 1
    state.facts_version = state.data_version
    state.facts = StreamState(status="unknown", last_attempt_at=utcnow()).model_dump(mode="json")
    session.add(RefreshAttempt(id=str(uuid4()), run_id=str(uuid4()), company_cik=cik, stream="facts",
        status="updated", started_at=utcnow(), finished_at=utcnow(), published_version=state.data_version,
        details={"facts_inserted": inserted, "inserted_by_metric": by_metric, "origin": "compatibility_writer", "check_complete": False}))


def register_complete_filings(session, cik=None, accession=None):
    statement = select(FilingChunk).order_by(FilingChunk.company_cik, FilingChunk.accession_number, FilingChunk.chunk_index)
    if cik:
        statement = statement.where(FilingChunk.company_cik == cik)
    if accession:
        statement = statement.where(FilingChunk.accession_number == accession)
    groups = {}
    for c in session.scalars(statement):
        groups.setdefault((c.company_cik, c.accession_number), []).append(c)
    for identity, chunks in groups.items():
        if session.get(FilingPublication, identity):
            continue
        try:
            validate_chunks(chunks)
        except ValueError:
            continue
        state = state_row(session, identity[0])
        state.data_version += 1
        state.evidence_version = state.data_version
        state.evidence = StreamState(status="unknown", last_attempt_at=utcnow()).model_dump(mode="json")
        manifest(session, chunks, state.data_version)
        session.add(RefreshAttempt(id=str(uuid4()), run_id=str(uuid4()), company_cik=identity[0], stream="evidence",
            status="updated", started_at=utcnow(), finished_at=utcnow(), published_version=state.data_version,
            details={"filings_published": 1, "origin": "compatibility_writer", "check_complete": False}))


def observations(cik, payload):
    if str(payload.get("cik", "")).zfill(10) != cik:
        raise FinancialSyncError("company_facts_cik_mismatch")
    return [{"company_cik": cik, **item} for metric, spec in METRIC_SOURCES.items()
            for item in build_metric_data(payload, metric, spec["facts"], spec["unit"])]


def reject_conflicts(session, cik, candidates):
    """Reject unclear same-vintage corrections before existing ID tie-breaks."""
    existing = list(session.scalars(select(FinancialFact).where(FinancialFact.company_cik == cik)))
    contexts, priorities = {}, {}
    for row in [*existing, *candidates]:
        identity = fact_identity(row)
        key = identity[:5] + identity[6:]  # exact context, excluding value
        contexts.setdefault(key, set()).add(identity[5])
        # Frame/FY metadata variants must not turn same-accession conflicting
        # amounts into an insertion-order winner either.
        priority = identity[:5] + identity[6:9]
        priorities.setdefault(priority, set()).add(identity[5])
    candidate_keys = {fact_identity(c)[:5] + fact_identity(c)[6:] for c in candidates}
    candidate_priorities = {fact_identity(c)[:5] + fact_identity(c)[6:9] for c in candidates}
    if any(len(contexts[k]) > 1 for k in candidate_keys) or any(len(priorities[k]) > 1 for k in candidate_priorities):
        raise FinancialSyncError("ambiguous_source_revision")


def manifest(session, chunks, version, cleaned_text=None):
    validate_chunks(chunks)
    first = chunks[0]
    row = FilingPublication(company_cik=first.company_cik, accession_number=first.accession_number,
        form=first.form, filed=first.filed, filename=first.filename, chunk_count=len(chunks),
        content_digest=chunk_digest(chunks), cleaned_text=cleaned_text, configuration=CONFIGURATION,
        published_at=utcnow(), data_version=version)
    session.add(row)
    return row


def bootstrap_publications(session):
    """Explicit offline metadata bootstrap; never called by user read routes."""
    groups = {}
    for c in session.scalars(select(FilingChunk).order_by(FilingChunk.company_cik, FilingChunk.accession_number, FilingChunk.chunk_index)):
        groups.setdefault((c.company_cik, c.accession_number), []).append(c)
    result = {"registered": 0, "invalid": []}
    for identity, chunks in groups.items():
        if session.get(FilingPublication, identity):
            continue
        try:
            validate_chunks(chunks)
        except ValueError:
            result["invalid"].append({"company_cik": identity[0], "accession_number": identity[1]})
            continue
        state = state_row(session, identity[0])
        if state.data_version != 0:
            raise ValueError("Bootstrap is only valid before any versioned publication.")
        manifest(session, chunks, 0)
        result["registered"] += 1
    return result


def stage_filing(session, cik, metadata, encoder, raw_loader, deadline=None):
    existing = stored_chunks(session, cik, metadata.accession_number)
    if existing:
        # Resume only an identical stored filing; no downloads or replacements.
        from app.catalog_indexing_service import validate_filing
        validate_filing(existing, allow_amendments=True)
        if any((c.form, c.filed, c.filename) != (metadata.form, metadata.filed, metadata.primary_document) for c in existing):
            raise ValueError("stored_source_identity_conflict")
        detached = [FilingChunk(**{field: getattr(c, field) for field in
            ("company_cik", "accession_number", "form", "filed", "filename", "chunk_index", "chunk_id", "text", "start_char", "end_char", "sec_url", "embedding")}) for c in existing]
        cleaned = None
    else:
        parsed = extract_filing_text(raw_loader(cik, metadata.accession_number), metadata.form)
        if parsed["filename"] != metadata.primary_document:
            raise ValueError("primary_document_mismatch")
        cleaned = parsed["text"]
        detached = [FilingChunk(company_cik=cik, accession_number=metadata.accession_number, form=metadata.form,
            filed=metadata.filed, filename=metadata.primary_document, chunk_index=i,
            sec_url=build_filing_url(cik, metadata.accession_number), **c) for i, c in enumerate(chunk_filing_text(cleaned))]
    missing = [c for c in detached if c.embedding is None]
    for offset in range(0, len(missing), 32):
        if deadline is not None and time.monotonic() >= deadline:
            raise TimeoutError()
        batch = missing[offset:offset+32]
        vectors = encoder([c.text for c in batch])
        if len(vectors) != len(batch):
            raise ValueError("embedding_count_mismatch")
        for c, v in zip(batch, vectors, strict=True):
            validate_embedding(v)
            c.embedding = v
    validate_chunks(detached)
    return detached, cleaned


def persist_staged(session, cik, chunks, version, cleaned):
    """Caller owns commit; the manifest and every vector publish together."""
    existing = stored_chunks(session, cik, chunks[0].accession_number)
    if existing:
        if chunk_digest(existing) != chunk_digest(chunks) or len(existing) != len(chunks):
            raise ValueError("staged_source_changed")
        for old, staged in zip(existing, chunks, strict=True):
            if old.embedding is None:
                old.embedding = staged.embedding
        selected = existing
    else:
        session.add_all(chunks)
        selected = chunks
    session.flush()
    manifest(session, selected, version, cleaned)


def refresh(factory, request: RefreshRequest, *, facts_loader=get_company_facts,
            inventory_loader=None, raw_loader=get_filing_raw_text, encoder=embed_texts, on_progress=None):
    from app.sec_client import discover_refresh_filings
    inventory_loader = inventory_loader or discover_refresh_filings
    report = {"report_type": "data_refresh", "run_id": str(uuid4()), "dry_run": request.dry_run,
              "started_at": utcnow().isoformat(), "companies": [], "error": None, "openai_calls": 0}
    run_deadline = time.monotonic() + request.max_run_seconds
    try:
        with coordinator(factory) as owned:
            with factory() as session:
                catalog = dict(session.execute(select(Company.ticker, Company.cik)).all())
            tickers = sorted({t.upper().strip() for t in request.tickers})
            if any(t not in catalog for t in tickers):
                raise FinancialSyncError("unknown_ticker")
            if not request.dry_run:
                with publication_session(factory, owned) as s, s.begin():
                    for abandoned in s.scalars(select(RefreshAttempt).where(RefreshAttempt.status == "running")):
                        abandoned.status, abandoned.finished_at = "interrupted", utcnow()
                        abandoned.details = {"error": "worker_interrupted", "committed": False}
                        state = state_row(s, abandoned.company_cik)
                        old = StreamState.model_validate(getattr(state, abandoned.stream) or {})
                        old.status, old.last_error, old.failure_stage = "failed", "worker_interrupted", "recovery"
                        setattr(state, abandoned.stream, old.model_dump(mode="json"))
            for ticker in tickers:
                for stream in (["facts", "evidence"] if request.stream == "both" else [request.stream]):
                    if time.monotonic() >= run_deadline:
                        report["error"] = "run_budget_reached_resume_remaining"
                        break
                    owned()
                    result = refresh_stream(factory, ticker, catalog[ticker], stream, request, report["run_id"],
                        owned, facts_loader, inventory_loader, raw_loader, encoder, run_deadline)
                    report["companies"].append(result.model_dump(mode="json"))
                    if result.error == "database_or_failure_report_unavailable":
                        report["error"] = "database_unavailable"
                    if result.status == "indeterminate":
                        report["error"] = "commit_outcome_indeterminate_use_database_ledger"
                    if result.error == "refresh_lock_lost":
                        report["error"] = "refresh_busy_or_lock_lost"
                    if on_progress:
                        try:
                            on_progress(report)
                        except Exception:
                            report["error"] = "report_checkpoint_failed_use_database_ledger"
                    if result.status == "interrupted":
                        report["error"] = "interrupted"
                    if report["error"]:
                        break
                if report["error"]:
                    break
    except RefreshBusy:
        report["error"] = "refresh_busy_or_lock_lost"
    except Exception:
        report["error"] = "refresh_configuration_or_database_failed"
    report["finished_at"] = utcnow().isoformat()
    report["not_processed"] = [{"ticker": ticker, "stream": stream}
        for ticker in sorted({t.upper().strip() for t in request.tickers})
        for stream in (["facts", "evidence"] if request.stream == "both" else [request.stream])
        if not any(row["ticker"] == ticker and row["stream"] == stream for row in report["companies"])]
    if on_progress:
        try:
            on_progress(report)
        except Exception:
            report["error"] = "report_checkpoint_failed_use_database_ledger"
    return report


def refresh_stream(factory, ticker, cik, stream, request, run_id, owned, facts_loader, inventory_loader, raw_loader, encoder, run_deadline=None):
    started, deadline, attempt_id = utcnow(), time.monotonic() + request.max_seconds, str(uuid4())
    deadline = min(deadline, run_deadline) if run_deadline is not None else deadline
    result = RefreshResult(ticker=ticker, stream=stream, status="failed",
                           inserted_by_metric={m: 0 for m in METRIC_SOURCES} if stream == "facts" else {})
    stage = "discovery"
    try:
        with factory() as s:
            state = s.get(CompanyRefreshState, cik)
            result.version_before = result.version_after = state.data_version if state else 0
        if not request.dry_run:
            with publication_session(factory, owned) as s, s.begin():
                state = state_row(s, cik)
                current = StreamState.model_validate(getattr(state, stream) or {})
                current.status, current.last_attempt_at = "pending", started
                setattr(state, stream, current.model_dump(mode="json"))
                s.add(RefreshAttempt(id=attempt_id, run_id=run_id, company_cik=cik, stream=stream,
                    status="running", started_at=started, details={}))
        if stream == "facts":
            payload = facts_loader(cik)
            candidates = observations(cik, payload)
            latest = max((r["filed"] for r in candidates), default=None)
            source_digest = hashlib.sha256(json.dumps(sorted(str(fact_identity(r)) for r in candidates)).encode()).hexdigest()
            with factory() as s:
                reject_conflicts(s, cik, candidates)
                provisional = merge_company_facts(s, cik, payload, dry_run=True)
            result.would_insert = provisional["would_insert"]
            targets, complete, staged = [], bool(candidates), []
            if not complete:
                result.pending_targets = ["supported_company_facts_unavailable"]
        else:
            inventory = inventory_loader(cik)
            targets = inventory["filings"]
            complete = inventory["complete"]
            latest = max((m.filed for m in targets), default=None)
            source_digest = hashlib.sha256(str([(m.accession_number, str(m.filed)) for m in targets]).encode()).hexdigest()
            with factory() as s:
                known = {p.accession_number for p in s.scalars(select(FilingPublication).where(FilingPublication.company_cik == cik))}
            missing = [m for m in targets if m.accession_number not in known]
            result.pending_targets = [m.accession_number for m in missing]
            staged = []
            stage = "indexing"
            if not request.dry_run:
                for m in missing[:request.max_filings]:
                    if time.monotonic() > deadline:
                        raise TimeoutError()
                    with factory() as s:
                        chunks, cleaned = stage_filing(s, cik, m, encoder, raw_loader, deadline)
                    staged.append((chunks, cleaned))
            result.would_insert = len(missing)
        if time.monotonic() > deadline:
            raise TimeoutError()
        if request.dry_run:
            result.status = "would_update" if result.would_insert else "no_change"
            return result
        stage = "publication"
        with publication_session(factory, owned) as s, s.begin():
            state = state_row(s, cik)
            if stream == "facts":
                reject_conflicts(s, cik, candidates)
                merged = merge_company_facts(s, cik, payload, publish=False)
                changed = merged["facts_inserted"] > 0
            else:
                changed = bool(staged)
            if changed:
                state.data_version += 1
                setattr(state, f"{stream}_version", state.data_version)
            if stream == "evidence":
                for chunks, cleaned in staged:
                    persist_staged(s, cik, chunks, state.data_version, cleaned)
            published_targets = {chunks[0].accession_number for chunks, _ in staged}
            remaining = [target for target in result.pending_targets if target not in published_targets]
            status = "pending" if remaining or not complete else "current"
            old = StreamState.model_validate(getattr(state, stream) or {})
            setattr(state, stream, StreamState(status=status, last_attempt_at=started, last_checked_at=utcnow(),
                last_successful_sync_at=utcnow() if status == "current" else old.last_successful_sync_at,
                latest_source_filing_date=latest, pending_targets=remaining,
                inventory_complete=complete).model_dump(mode="json"))
            outcome = "pending" if status == "pending" else "updated" if changed else "no_change"
            committed = RefreshResult(**{**result.model_dump(), "status": outcome, "commit_outcome": "committed", "version_after": state.data_version,
                "pending_targets": remaining,
                "facts_inserted": merged["facts_inserted"] if stream == "facts" else 0,
                "inserted_by_metric": merged["inserted_by_metric"] if stream == "facts" else {},
                "filings_published": len(staged)})
            attempt = s.get(RefreshAttempt, attempt_id)
            attempt.status, attempt.finished_at = outcome, utcnow()
            attempt.published_version = state.data_version if changed else None
            attempt.source_digest, attempt.details = source_digest, committed.model_dump(mode="json")
        return committed  # Only publish committed counters after context exit.
    except BaseException as exc:
        if not isinstance(exc, (Exception, KeyboardInterrupt)):
            raise
        if isinstance(exc, RefreshBusy):
            # Another coordinator may now own admission. It recovers this
            # running attempt; this worker must neither publish nor overwrite it.
            raise
        if stage == "publication":
            try:
                recovered = reconcile_publication(factory, cik, attempt_id)
            except Exception:
                # An unknown commit is neither a successful publication nor a
                # confirmed rollback. Preserve diagnostics, never assert zeros.
                return result.model_copy(update={"status": "indeterminate", "commit_outcome": "indeterminate",
                    "facts_inserted": None, "filings_published": None, "version_after": None,
                    "inserted_by_metric": {metric: None for metric in result.inserted_by_metric},
                    "error": "commit_outcome_unknown", "failure_stage": stage})
            if recovered is not None:
                return recovered
            result.commit_outcome = "rolled_back"
        result.status = "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
        result.error = str(exc) if isinstance(exc, FinancialSyncError) else "refresh_stage_failed"
        result.failure_stage = stage
        if not request.dry_run:
            try:
                with publication_session(factory, owned) as s, s.begin():
                    state = state_row(s, cik)
                    old = StreamState.model_validate(getattr(state, stream) or {})
                    old.status, old.last_attempt_at = "failed", started
                    old.last_error, old.failure_stage = result.error, stage
                    if 'latest' in locals() and latest is not None:
                        old.latest_source_filing_date = latest
                    old.pending_targets = result.pending_targets
                    setattr(state, stream, old.model_dump(mode="json"))
                    attempt = s.get(RefreshAttempt, attempt_id)
                    if attempt and attempt.status == "running":
                        attempt.status, attempt.finished_at, attempt.details = result.status, utcnow(), result.model_dump(mode="json")
            except RefreshBusy:
                result.error = "refresh_lock_lost"
            except Exception:
                result.error = "database_or_failure_report_unavailable"
        return result
