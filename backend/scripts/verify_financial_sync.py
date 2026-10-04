"""Read-only Item 7 preservation, normalization and optional live HTTP audit."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone

import httpx
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.config import BACKEND_ROOT
from app.database import engine
from app.models import Company, FinancialFact
from app.financial_metric_registry import METRICS
from app.financial_metric_schemas import NormalizedFinancialSummary
from app.financial_metrics_service import FinancialMetrics, load_financial_metrics
from app.financial_sync_service import metric_coverage
from app.sec_importer import fact_identity
from scripts.sync_financial_facts import report_path, write_report
from scripts.verify_financial_metrics import fingerprint, verify_source, verify_history, verify_http_history

BASELINE = BACKEND_ROOT / "reports/structured_financial_baseline.json"
REPRESENTATIVES = ("AAPL", "MSFT", "JPM", "JNJ", "XOM", "COST", "CAT", "F")


def verify(api_url=None):
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    result = {"report_type": "financial_sync_verification", "verified_at": datetime.now(timezone.utc).isoformat(),
              "before": {k: baseline[k] for k in ("counts", "sha256", "companies_with_facts", "company_fact_counts")}}
    expectations = {}
    with engine.connect() as connection:
        connection.exec_driver_sql("SET TRANSACTION READ ONLY")
        after = fingerprint(connection)
        raw_rows = connection.exec_driver_sql("SELECT id,row_to_json(f)::text FROM financial_facts f ORDER BY id").all()
        hashes = {str(id): hashlib.sha256(raw.encode()).hexdigest() for id, raw in raw_rows}
        assert all(hashes.get(id) == value for id, value in baseline["fact_row_sha256"].items())
        assert after["sha256"]["companies"] == baseline["sha256"]["companies"]
        assert after["sha256"]["filing_chunks"] == baseline["sha256"]["filing_chunks"]
        assert after["counts"]["filing_chunks"] == baseline["counts"]["filing_chunks"]
        assert after["counts"]["embeddings"] == baseline["counts"]["embeddings"]
        with Session(bind=connection) as session:
            companies = list(session.scalars(select(Company).order_by(Company.ticker)))
            facts = list(session.scalars(select(FinancialFact).order_by(FinancialFact.id)))
            rows = {fact.id: fact for fact in facts}
            assert all(f.company_cik in {c.cik for c in companies} for f in facts)
            identities = Counter(fact_identity(f) for f in facts)
            duplicate_identities = sum(n - 1 for n in identities.values() if n > 1)
            assert duplicate_identities == 0
            result.update(after=after, original_facts_preserved=len(baseline["fact_row_sha256"]),
                          original_fact_subset_sha256=hashlib.sha256("\n".join(raw for id, raw in raw_rows
                              if str(id) in baseline["fact_row_sha256"]).encode()).hexdigest(),
                          duplicate_identities=duplicate_identities, orphan_facts=0,
                          coverage=metric_coverage(session), representatives=[])
            assert result["original_fact_subset_sha256"] == baseline["sha256"]["financial_facts"]
            for company in companies:
                service = FinancialMetrics(company, [f for f in facts if f.company_cik == company.cik])
                for kind in ("quarter", "annual"):
                    summary = service.summary(kind)
                    for point in summary.metrics.values():
                        verify_source(point, rows)
                    expectations[(company.ticker, "summary", kind)] = summary
                for name, definition in METRICS.items():
                    kind = "instant" if definition.kind == "instant" else "quarter"
                    verify_history(service.history(name, kind), rows)
                if company.ticker in REPRESENTATIVES:
                    summary = service.summary()
                    row = {"ticker": company.ticker, "company_cik": company.cik, "fact_count": len(service.facts),
                           "period": summary.period.model_dump(mode="json") if summary.period else None,
                           "metrics": {name: {**point.model_dump(mode="json", exclude={"alternatives"}),
                                              "alternative_fact_ids": [source.fact_id for source in point.alternatives]}
                                       for name, point in summary.metrics.items()}, "histories": []}
                    for name, kind in (("revenue", "quarter"), ("revenue", "annual"), ("diluted_eps", "quarter"),
                                       ("net_margin", "quarter"), ("revenue_growth_yoy", "quarter"),
                                       ("operating_cash_flow", "annual"), ("free_cash_flow", "annual")):
                        history = service.history(name, kind)
                        verify_history(history, rows)
                        expectations[(company.ticker, name, kind)] = history
                        row["histories"].append({"metric": name, "period": kind, "observations": len(history.history),
                                                 "status": history.status, "source_content": "passed"})
                    result["representatives"].append(row)
            selects = []
            def observe(_conn, _cursor, statement, *_):
                if statement.lstrip().lower().startswith("select"):
                    selects.append(statement)
            event.listen(connection, "before_cursor_execute", observe)
            try:
                load_financial_metrics(session, "AAPL").summary()
            finally:
                event.remove(connection, "before_cursor_execute", observe)
            assert len(selects) == 2
            result["summary_select_count"] = len(selects)
        assert fingerprint(connection) == after
    result["http_checks"] = []
    if api_url:
        with httpx.Client(base_url=api_url, timeout=60) as client:
            for (ticker, name, kind), expected in expectations.items():
                if ticker not in REPRESENTATIVES:
                    continue
                path = f"/companies/{ticker}/financials/summary" if name == "summary" else f"/companies/{ticker}/financials/metrics/{name}"
                response = client.get(path, params={"period": kind})
                assert response.status_code == 200
                if name == "summary":
                    assert NormalizedFinancialSummary.model_validate(response.json()) == expected
                else:
                    verify_http_history(response.json(), expected, rows)
                result["http_checks"].append({"ticker": ticker, "metric": name, "period": kind,
                                              "status": 200, "content": "passed"})
            company_response = client.get("/companies")
            assert company_response.status_code == 200
            catalog = company_response.json()
            assert len(catalog) == 35
            assert all(c["has_indexed_filing"] and c["indexed_filing_count"] == 1 for c in catalog)
            assert client.get("/healthz").status_code == 200
            result["filing_ready"] = len(catalog)
    with engine.connect() as connection:
        connection.exec_driver_sql("SET TRANSACTION READ ONLY")
        assert fingerprint(connection) == after
    result["preservation_passed"] = True
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url")
    parser.add_argument("--report", type=Path, default=BACKEND_ROOT / "reports/structured_financial_verification.json")
    args = parser.parse_args(argv)
    destination = report_path(args.report)
    if destination.exists() and json.loads(destination.read_text()).get("report_type") != "financial_sync_verification":
        raise ValueError("Existing file is not an Item 7 verification report.")
    result = verify(args.api_url)
    write_report(destination, result)
    print(json.dumps({"counts": result["after"]["counts"], "structured_companies": result["coverage"]["companies_with_facts"],
                      "original_facts_preserved": result["original_facts_preserved"], "duplicates": result["duplicate_identities"],
                      "http_checks": len(result["http_checks"]), "preservation_passed": True}))


if __name__ == "__main__":
    main()
