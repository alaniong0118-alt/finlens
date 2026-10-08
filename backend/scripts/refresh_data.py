"""Explicit operator refresh; never scheduled/enabled at application startup."""
import argparse
import json
from pathlib import Path
import sys

from app.config import BACKEND_ROOT
from app.refresh_contracts import RefreshRequest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--ticker", action="append")
    selection.add_argument("--all", action="store_true")
    selection.add_argument("--show-run", help="Reconstruct committed outcomes from the database ledger; no source calls.")
    parser.add_argument("--stream", choices=("facts", "evidence", "both"), default="both")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-network", action="store_true", help="Explicitly authorize SEC acquisition for this run.")
    parser.add_argument("--bootstrap", action="store_true", help="Offline registration of validated existing evidence only.")
    parser.add_argument("--max-filings", type=int, default=2)
    parser.add_argument("--max-seconds", type=int, default=300)
    parser.add_argument("--max-run-seconds", type=int, default=1800)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    if not args.bootstrap and not args.show_run and not args.allow_network:
        print("SEC acquisition is disabled. Use --allow-network only after live rollout authorization.", file=sys.stderr)
        return 2
    if args.bootstrap and args.dry_run:
        print("Bootstrap is an offline metadata write; omit --dry-run or inspect freshness read-only.", file=sys.stderr)
        return 2
    try:
        from sqlalchemy import select
        from app.database import SessionLocal
        from app.models import Company, RefreshAttempt
        from app.refresh_service import bootstrap_publications, coordinator, refresh
        from scripts.setup_demo import check_schema
        from scripts.sync_financial_facts import report_path, write_report
        with SessionLocal() as session:
            check_schema(session)
            if args.show_run:
                attempts = list(session.scalars(select(RefreshAttempt).where(RefreshAttempt.run_id == args.show_run).order_by(RefreshAttempt.started_at)))
                print(json.dumps({"run_id": args.show_run, "attempts": [{"attempt_id": a.id, "company_cik": a.company_cik,
                    "stream": a.stream, "status": a.status, "published_version": a.published_version, "details": a.details} for a in attempts]}))
                return 0 if attempts else 1
            tickers = list(session.scalars(select(Company.ticker))) if args.all else args.ticker
        request = RefreshRequest(tickers=tickers, stream=args.stream, dry_run=args.dry_run,
                                 max_filings=args.max_filings, max_seconds=args.max_seconds,
                                 max_run_seconds=args.max_run_seconds)
        if args.bootstrap:
            if not args.all:
                raise ValueError("Bootstrap requires --all; it validates the complete stored inventory.")
            with coordinator(SessionLocal), SessionLocal() as session, session.begin():
                result = bootstrap_publications(session)
            print(json.dumps(result))
            return 1 if result["invalid"] else 0
        from app.sec_client import get_sec_headers
        get_sec_headers()  # Validate private contact before work; never print it.
        destination = report_path(args.report) if args.report else None
        if destination and destination.exists():
            raise ValueError("Use a new report filename; prior reports are immutable evidence.")
        report = refresh(SessionLocal, request,
                         on_progress=(lambda r: write_report(destination, r)) if destination else None)
        if destination is None:
            destination = report_path(BACKEND_ROOT / "reports" / f"refresh-{report['run_id']}.json")
            write_report(destination, report)
        print(json.dumps({"run_id": report["run_id"], "error": report["error"], "results": report["companies"]}))
        return 1 if report["error"] or any(r["status"] in {"failed", "interrupted", "pending", "indeterminate"} for r in report["companies"]) else 0
    except Exception:
        print("Refresh could not start/finish. Check schema, explicit selection, database and report permissions. No private configuration logged.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
