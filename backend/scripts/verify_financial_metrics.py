"""Read-only 35-company audit. Run after initial baseline audit; never imports SEC data."""
import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone

import httpx
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.database import engine
from app.models import Company, FinancialFact
from app.financial_metric_registry import METRICS
from app.financial_metric_schemas import NormalizedMetricHistory, NormalizedFinancialSummary
from app.financial_metrics_service import FinancialMetrics, load_financial_metrics
from app.sec_parser import classify_period

REPRESENTATIVES = ("AAPL", "MSFT", "JPM", "GS", "WMT", "COST", "JNJ", "XOM", "CAT", "F")
HISTORY_REPRESENTATIVES = ("AAPL", "MSFT", "JPM", "WMT")
REPORT = Path(__file__).resolve().parents[1] / "reports/financial_metrics_verification.json"


def fingerprint(connection):
    result = {"counts": {}, "sha256": {}}
    for table in ("companies", "financial_facts", "filing_chunks"):
        rows = connection.exec_driver_sql(f"SELECT row_to_json(t)::text FROM (SELECT * FROM {table} ORDER BY id) t").scalars().all()
        result["counts"][table] = len(rows)
        result["sha256"][table] = hashlib.sha256("\n".join(rows).encode()).hexdigest()
    result["counts"]["embeddings"] = connection.exec_driver_sql("SELECT count(embedding) FROM filing_chunks").scalar_one()
    return result


def verify_source(point, rows):
    for source in point.provenance + point.alternatives:
        row = rows[source.fact_id]
        assert source.company_cik == row.company_cik
        assert source.value == row.value and source.unit == row.unit
        assert source.period_start == row.period_start and source.period_end == row.period_end
        assert source.source_fiscal_year == row.fiscal_year and source.source_fiscal_period == row.fiscal_period
        assert source.accession_number == row.accession_number and source.form == row.form and source.filed == row.filed
        assert source.original_concept == row.source.removeprefix("SEC Company Facts API: ")
        assert source.stored_metric == row.metric and source.source == row.source
        assert source.frame == row.frame and source.stored_at == row.created_at
        assert source.sec_url == (f"https://www.sec.gov/Archives/edgar/data/{int(row.company_cik)}/"
                                  f"{row.accession_number.replace('-', '')}/{row.accession_number}-index.html")
    if point.status == "available":
        if not point.inputs:
            assert len(point.provenance) == 1
            row = rows[point.provenance[0].fact_id]
            assert point.value == row.value
            assert point.period.start == row.period_start and point.period.end == row.period_end
        else:
            values = []
            for operand in point.inputs:
                assert len(operand.fact_ids) == 1
                row = rows[operand.fact_ids[0]]
                assert operand.value == row.value
                assert operand.unit == row.unit
                assert operand.period.start == row.period_start and operand.period.end == row.period_end
                values.append(row.value)
            left, right = values
            if point.metric == "free_cash_flow":
                assert point.value == left-right
            elif point.metric == "revenue_growth_yoy":
                assert point.value == (left-right)/right
                assert 357 <= (point.inputs[0].period.end-point.inputs[1].period.end).days <= 378
            else:
                assert point.value == left/right
                assert point.inputs[0].period.start == point.inputs[1].period.start
                assert point.inputs[0].period.end == point.inputs[1].period.end
    else:
        assert point.value is None


def verify_history(history, rows):
    """Check every returned observation against stored source rows, not a snapshot."""
    assert history.unit == METRICS[history.metric].unit
    keys = [(p.period.end, p.period.start or p.period.end) for p in history.history]
    assert keys == sorted(keys) and len(keys) == len(set(keys))
    for point in history.history:
        assert point.metric == history.metric and point.unit == history.unit
        assert point.period.kind == history.requested_period
        if point.period.kind == "instant":
            assert point.period.start is None
        else:
            assert point.period.start is not None
            assert classify_period(point.period.start.isoformat(), point.period.end.isoformat()) == point.period.kind
        assert all(source.company_cik == history.company_cik for source in point.provenance + point.alternatives)
        verify_source(point, rows)
        if point.status == "available" and not point.inputs:
            assert point.provenance[0].original_concept in METRICS[history.metric].concepts
    if history.metric == "diluted_eps":
        assert history.comparability.status == "unverified"
        assert history.comparability.value_basis == "reported_as_filed"
    else:
        assert history.comparability is None


def verify_http_history(payload, expected, rows):
    actual = NormalizedMetricHistory.model_validate(payload)
    verify_history(actual, rows)
    for field in ("ticker", "company_cik", "metric", "unit", "requested_period", "status", "reason", "comparability", "selection_policy"):
        assert getattr(actual, field) == getattr(expected, field)
    assert len(actual.history) == len(expected.history)
    for point, reference in zip(actual.history, expected.history, strict=True):
        for field in ("period", "status", "reason", "value", "revenue_basis", "formula", "provenance", "alternatives", "inputs"):
            assert getattr(point, field) == getattr(reference, field)


def verify(api_url=None):
    recorded = json.loads(REPORT.read_text(encoding="utf-8"))
    coverage, representatives, history_checks = [], [], []
    http_expectations, summary_expectations = {}, {}
    recorded.setdefault("review_fixes", {"before": recorded["before"], "previous_aggregate": recorded["aggregate"],
                                          "previous_validation": recorded.get("validation", {})})
    with engine.connect() as connection:
        connection.exec_driver_sql("SET TRANSACTION READ ONLY")
        assert fingerprint(connection) == recorded["before"]
        with Session(bind=connection) as session:
            companies = list(session.scalars(select(Company).order_by(Company.ticker)))
            facts = list(session.scalars(select(FinancialFact).order_by(FinancialFact.id)))
            rows = {f.id: f for f in facts}
            for company in companies:
                service = FinancialMetrics(company, facts)
                summary = service.summary()
                for point in summary.metrics.values():
                    verify_source(point, rows)
                histories = {name: service.history(name, "instant" if definition.kind == "instant" else "quarter")
                             for name, definition in METRICS.items()}
                for history in histories.values():
                    verify_history(history, rows)
                coverage.append({"ticker": company.ticker, "fact_count": len(service.facts),
                                 "period": summary.period.model_dump(mode="json") if summary.period else None,
                                 "metrics": {name: {"status": p.status, "value": str(p.value) if p.value is not None else None,
                                                    "reason": p.reason, "revenue_basis": p.revenue_basis,
                                                    "fact_ids": [s.fact_id for s in p.provenance]}
                                             for name, p in summary.metrics.items()},
                                 "history_available": {name: history.status for name, history in histories.items()}})
                if company.ticker in REPRESENTATIVES:
                    summary_expectations[company.ticker] = summary
                    requests = [("revenue", "quarter")]
                    if company.ticker in HISTORY_REPRESENTATIVES:
                        requests += [("diluted_eps", "quarter"), ("net_margin", "quarter"),
                                     ("revenue_growth_yoy", "quarter"), ("revenue", "annual")]
                    for metric, kind in requests:
                        history = service.history(metric, kind)
                        verify_history(history, rows)
                        http_expectations[(company.ticker, metric, kind)] = history
                        history_checks.append({"ticker": company.ticker, "metric": metric, "period": kind,
                                               "observations": len(history.history), "status": history.status,
                                               "ordering_periods_values_lineage": "passed",
                                               "comparability": history.comparability.model_dump() if history.comparability else None})
                    available = [p for p in summary.metrics.values() if p.status == "available"]
                    representatives.append({"ticker": company.ticker, "fact_count": len(service.facts),
                                            "verification": "stored_rows_and_formulas_matched" if available else "no_stored_facts_no_fabricated_values",
                                            "observations": [p.model_dump(mode="json") for p in available],
                                            "unavailable_metrics": [p.metric for p in summary.metrics.values() if p.status != "available"]})
            aggregate = {}
            for name in METRICS:
                counts = Counter(row["metrics"][name]["status"] for row in coverage)
                aggregate[name] = {"available": counts["available"], "unavailable": counts["unavailable"],
                                   "not_applicable": counts["not_applicable"],
                                   "coverage_percent": round(counts["available"] / len(companies) * 100, 2)}
            queries = []
            def observe(_conn, _cursor, statement, *_):
                if statement.lstrip().lower().startswith("select"):
                    queries.append(statement)
            event.listen(connection, "before_cursor_execute", observe)
            try:
                load_financial_metrics(session, "AAPL").summary()
            finally:
                event.remove(connection, "before_cursor_execute", observe)
            assert len(queries) == 2
            recorded.update(coverage=coverage, aggregate=aggregate, representatives=representatives,
                            summary_select_count=len(queries), openai_calls=0, history_checks=history_checks)
        recorded["after"] = fingerprint(connection)
        assert recorded["after"] == recorded["before"]
    if api_url:
        http_checks = []
        with httpx.Client(base_url=api_url, timeout=30) as client:
            for row in representatives:
                ticker = row["ticker"]
                response = client.get(f"/companies/{ticker}/financials/summary")
                assert response.status_code == 200
                expected = next(c for c in coverage if c["ticker"] == ticker)
                actual = response.json()
                # Compare current, DB-validated models; no stored golden payload.
                assert NormalizedFinancialSummary.model_validate(actual) == summary_expectations[ticker]
                for name, point in actual["metrics"].items():
                    assert point["status"] == expected["metrics"][name]["status"]
                    expected_value = expected["metrics"][name]["value"]
                    assert (Decimal(point["value"]) if point["value"] is not None else None) == (Decimal(expected_value) if expected_value is not None else None)
                for (company_ticker, metric, kind), expected_history in http_expectations.items():
                    if company_ticker != ticker:
                        continue
                    history = client.get(f"/companies/{ticker}/financials/metrics/{metric}", params={"period": kind})
                    assert history.status_code == 200
                    verify_http_history(history.json(), expected_history, rows)
                    next(check for check in history_checks if (check["ticker"], check["metric"], check["period"]) ==
                         (ticker, metric, kind))["http_content"] = "passed"
                http_checks.append({"ticker": ticker, "summary": response.status_code, "history": history.status_code,
                                    "revenue_status": actual["metrics"]["revenue"]["status"]})
            assert client.get("/companies/AAPL/financials/metrics/unknown").status_code == 404
            assert client.get("/companies/UNKNOWN/financials/summary").status_code == 404
            assert client.get("/healthz").status_code == 200
        recorded["http_checks"] = http_checks
    # Include real HTTP reads in the preservation interval.
    with engine.connect() as connection:
        connection.exec_driver_sql("SET TRANSACTION READ ONLY")
        assert fingerprint(connection) == recorded["before"]
    recorded["review_fixes"].update(after=recorded["after"], history_verification="passed",
                                    history_http_content="passed" if api_url else "not_run",
                                    representative_history_checks=len(history_checks),
                                    verified_at=datetime.now(timezone.utc).isoformat())
    recorded["verified_at"] = datetime.now(timezone.utc).isoformat()
    recorded["preservation_passed"] = True
    REPORT.write_text(json.dumps(recorded, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"counts": recorded["after"]["counts"], "aggregate": recorded["aggregate"],
                      "summary_select_count": recorded["summary_select_count"], "preservation_passed": True}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", help="Optional running backend for real HTTP checks.")
    verify(parser.parse_args().api_url)
