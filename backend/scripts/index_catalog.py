"""Run from backend: python -m scripts.index_catalog [--ticker MSFT] [--dry-run]."""
import argparse
import json
from pathlib import Path
import sys

from app.config import BACKEND_ROOT


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticker", action="append", help="Only this stored ticker; repeat for a subset.")
    parser.add_argument("--dry-run", action="store_true", help="Discover metadata without writing chunks/vectors.")
    parser.add_argument("--report", type=Path, default=BACKEND_ROOT / "reports" / "catalog_indexing.json")
    args = parser.parse_args(argv)
    try:
        from app.database import SessionLocal
        from app.catalog_indexing_service import index_catalog
        from scripts.setup_demo import check_schema
        with SessionLocal() as session:
            check_schema(session)
            report = index_catalog(session, args.ticker, dry_run=args.dry_run, on_result=lambda r: print(
                f"{r['ticker']}: {r['status']} chunks={r['chunk_count']} embeddings={r['embedding_count']}"
                + (f" error={r['error_stage']} HTTP={r.get('http_status', '-')}" if r['status'] == 'failed' else ''),
                flush=True,
            ))
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"Catalog={report['catalog_total']} skipped={report['skipped']} indexed={report['newly_indexed']} "
              f"resumed={report['resumed']} failed={report['failed']} Ready={report['final_ready']}")
        print(f"Report: {args.report}")
        if report.get("catalog_error"):
            print(report["catalog_error"], file=sys.stderr)
        return 1 if report["failed"] or report.get("catalog_error") else 0
    except Exception:
        print("Catalog indexing could not start or write its report. Check database/schema, ticker selection, "
              "configuration and report permissions. No credentials were logged.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
