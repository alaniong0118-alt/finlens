"""Sequential, company-atomic structured SEC synchronization."""
from collections import Counter, defaultdict
from datetime import datetime, timezone

import httpx
from sqlalchemy import func, select, text

from app.financial_metric_registry import METRICS
from app.financial_metrics_service import FinancialMetrics
from app.models import Company, FinancialFact
from app.sec_client import get_company_facts
from app.sec_importer import FinancialSyncError, METRIC_SOURCES, merge_company_facts


def metric_coverage(session):
    """Two bulk reads; coverage is measured, never assigned by ticker."""
    companies = list(session.scalars(select(Company).order_by(Company.ticker)))
    grouped = defaultdict(list)
    for fact in session.scalars(select(FinancialFact).order_by(FinancialFact.id)):
        grouped[fact.company_cik].append(fact)
    result = {"companies_with_facts": sum(bool(grouped[c.cik]) for c in companies),
              "source_metric_companies": {metric: sum(any(f.metric == metric for f in grouped[c.cik])
                                                       for c in companies) for metric in METRIC_SOURCES},
              "companies": [], "quarter": {}, "annual": {}}
    for company in companies:
        service = FinancialMetrics(company, grouped[company.cik])
        row = {"ticker": company.ticker, "company_cik": company.cik, "fact_count": len(service.facts)}
        for kind in ("quarter", "annual"):
            summary = service.summary(kind)
            row[kind] = {"period": summary.period.model_dump(mode="json") if summary.period else None,
                         "metrics": {name: {"status": p.status, "value": str(p.value) if p.value is not None else None,
                                             "revenue_basis": p.revenue_basis, "reason": p.reason,
                                             "fact_ids": [source.fact_id for source in p.provenance]}
                                     for name, p in summary.metrics.items()}}
        result["companies"].append(row)
    for kind in ("quarter", "annual"):
        for name in METRICS:
            counts = Counter(row[kind]["metrics"][name]["status"] for row in result["companies"])
            result[kind][name] = {status: counts[status] for status in ("available", "unavailable", "not_applicable")}
    return result


def failure_details(exc):
    """Never include exception text, URLs, response bodies or contact headers."""
    if isinstance(exc, FinancialSyncError):
        return {"error": str(exc), "http_status": None}
    if isinstance(exc, httpx.HTTPStatusError):
        return {"error": "sec_http_error", "http_status": exc.response.status_code}
    if isinstance(exc, httpx.TransportError):
        return {"error": "sec_transport_error", "http_status": None}
    return {"error": "company_sync_failed", "http_status": None}


def sync_catalog(session_factory, tickers=None, *, dry_run=False, on_result=None, on_progress=None):
    """Reports are diagnostic; fresh source + stored identities determine work.

    Each company uses a new session and atomic transaction. A failed session is
    discarded; a separate health check distinguishes per-company errors from a
    global database outage. Keyboard interruption preserves earlier commits.
    """
    report = {"report_type": "financial_facts_sync", "started_at": datetime.now(timezone.utc).isoformat(), "dry_run": dry_run,
              "companies_requested": [], "already_current": 0, "updated": 0, "failed": 0,
              "no_usable_source": 0, "facts_inserted": 0, "would_insert": 0,
              "companies": [], "catalog_error": None, "interrupted": False}
    try:
        with session_factory() as session:
            companies = list(session.scalars(select(Company).order_by(Company.ticker)))
            catalog = {c.ticker: c.cik for c in companies}
            counts = dict(session.execute(select(FinancialFact.company_cik, func.count())
                                           .group_by(FinancialFact.company_cik)).all())
        requested = sorted({ticker.upper().strip() for ticker in tickers}) if tickers is not None else sorted(catalog)
        if not requested or any(ticker not in catalog for ticker in requested):
            raise FinancialSyncError("unknown_or_empty_ticker_selection")
        report.update(companies_requested=requested, catalog_total=len(catalog), facts_before=sum(counts.values()),
                      facts_after=sum(counts.values()), companies_with_facts_before=sum(counts.get(cik, 0) > 0 for cik in catalog.values()))
        if on_progress:
            on_progress(report)
        for ticker in requested:
            cik = catalog[ticker]
            row = {"ticker": ticker, "company_cik": cik, "facts_before": counts.get(cik, 0),
                   "facts_after": counts.get(cik, 0), "facts_inserted": 0, "would_insert": 0,
                   "inserted_by_metric": {metric: 0 for metric in METRIC_SOURCES},
                   "status": "failed", "error": None, "http_status": None}
            try:
                facts = get_company_facts(cik)
                with session_factory() as session, session.begin():
                    if dry_run and session.get_bind().dialect.name == "postgresql":
                        session.execute(text("SET TRANSACTION READ ONLY"))
                    merge_result = merge_company_facts(session, cik, facts, dry_run=dry_run)
                # Flush results are provisional until the transaction commits.
                row.update(merge_result)
                row["status"] = ("no_usable_source" if not row["source_observations"] else
                                 "would_update" if dry_run and row["would_insert"] else
                                 "updated" if row["facts_inserted"] else "already_current")
            except Exception as exc:
                row.update(failure_details(exc))
                # Transaction context rolls back, including a failed flush.
                row.update(facts_inserted=0, would_insert=0, facts_after=row["facts_before"])
                try:
                    with session_factory() as healthy:
                        healthy.execute(text("SELECT 1"))
                except Exception:
                    report["catalog_error"] = "database_unavailable"
            report["companies"].append(row)
            if row["status"] in {"updated", "already_current", "failed", "no_usable_source"}:
                report[row["status"]] += 1
            report["facts_inserted"] += row["facts_inserted"]
            report["would_insert"] += row["would_insert"]
            report["facts_after"] = report["facts_before"] + report["facts_inserted"]
            if on_result:
                on_result(row)
            if on_progress:
                on_progress(report)
            if report["catalog_error"]:
                break
        if not report["catalog_error"]:
            with session_factory() as session:
                report["normalized_coverage"] = metric_coverage(session)
                report["facts_after"] = session.scalar(select(func.count()).select_from(FinancialFact))
                report["companies_with_facts_after"] = report["normalized_coverage"]["companies_with_facts"]
    except KeyboardInterrupt:
        report["interrupted"] = True
        report["catalog_error"] = "interrupted_rerun_to_resume"
    except FinancialSyncError as exc:
        report["catalog_error"] = str(exc)
    except Exception:
        report["catalog_error"] = "catalog_sync_or_report_failed"
    report["not_processed"] = [ticker for ticker in report["companies_requested"]
                               if ticker not in {row["ticker"] for row in report["companies"]}]
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    if on_progress:
        on_progress(report)
    return report
