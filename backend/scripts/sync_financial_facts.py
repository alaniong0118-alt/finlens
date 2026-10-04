"""Sync official SEC facts: python -m scripts.sync_financial_facts [--ticker JNJ] [--dry-run]."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

from app.config import BACKEND_ROOT


def report_path(path):
    resolved = path.resolve()
    root = (BACKEND_ROOT / "reports").resolve()
    if root not in resolved.parents or resolved.suffix != ".json" or resolved.is_symlink():
        raise ValueError("Report must be a JSON file inside backend/reports.")
    return resolved


def write_report(path, report):
    """Atomic checkpoint after each company; temporary file contains no secrets."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=".financial-sync-", suffix=".tmp", delete=False) as output:
        temporary = Path(output.name)
        output.write(json.dumps(report, indent=2) + "\n")
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticker", action="append", help="Stored ticker; repeat for a subset.")
    parser.add_argument("--dry-run", action="store_true", help="Fetch/compare facts without database writes.")
    parser.add_argument("--report", type=Path, default=BACKEND_ROOT / "reports/financial_facts_sync.json")
    args = parser.parse_args(argv)
    try:
        destination = report_path(args.report)
        # Validate report permissions before any source requests or database writes.
        if destination.exists():
            if json.loads(destination.read_text(encoding="utf-8")).get("report_type") != "financial_facts_sync":
                raise ValueError("Existing file is not a sync report.")
        from app.database import SessionLocal
        from app.financial_sync_service import sync_catalog
        from scripts.setup_demo import check_schema
        with SessionLocal() as session:
            check_schema(session)
        report = sync_catalog(SessionLocal, args.ticker, dry_run=args.dry_run,
                              on_progress=lambda r: write_report(destination, r),
                              on_result=lambda r: print(
                                  f"{r['ticker']}: {r['status']} before={r['facts_before']} "
                                  f"inserted={r['facts_inserted']} after={r['facts_after']} "
                                  f"would_insert={r['would_insert']}"
                                  + (f" error={r['error']} HTTP={r['http_status']}" if r['error'] else ""), flush=True))
        print(f"Requested={len(report['companies_requested'])} updated={report['updated']} "
              f"already_current={report['already_current']} failed={report['failed']} "
              f"no_usable_source={report['no_usable_source']} inserted={report['facts_inserted']}")
        print(f"Report: {destination}")
        if report["catalog_error"]:
            print(report["catalog_error"], file=sys.stderr)
        return 1 if report["failed"] or report["no_usable_source"] or report["catalog_error"] else 0
    except Exception:
        print("Sync could not start or write its report. Check schema, database, SEC contact and "
              "report permissions. No private configuration was logged.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
