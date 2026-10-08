"""Insert-only Company Facts ingestion; selection belongs to the metrics layer."""
from datetime import date
from decimal import Decimal, InvalidOperation
import re

from sqlalchemy import select, text

from app.database import SessionLocal
from app.financial_metric_registry import METRICS
from app.models import Company, FinancialFact
from app.sec_client import get_company_facts
from app.sec_parser import normalize_fact_data


# Reuse reviewed Item 6 definitions, not a new alias/selection registry.
# Preserve the legacy stored revenue name consumed by financial_analysis.
METRIC_SOURCES = {
    "Revenues" if name == "revenue" else definition.concepts[0]: {
        "facts": list(definition.concepts), "unit": definition.source_unit,
    }
    for name, definition in METRICS.items() if definition.kind != "derived"
}

IDENTITY_FIELDS = (
    "company_cik", "source", "unit", "period_start", "period_end", "value",
    "accession_number", "filed", "form", "frame", "fiscal_year", "fiscal_period",
)


class FinancialSyncError(ValueError):
    """Public error code; never contains source bodies or private configuration."""


def fact_identity(record):
    """Exact source observation, not a period or economic equivalence key."""
    def field(name):
        value = record.get(name) if isinstance(record, dict) else getattr(record, name)
        if name in {"period_start", "period_end", "filed"} and isinstance(value, str):
            return date.fromisoformat(value)
        if name == "value":
            return Decimal(str(value))
        return value
    return tuple(field(name) for name in IDENTITY_FIELDS)


def validate_item(item):
    """Reject malformed/unrepresentable data before a company transaction writes."""
    try:
        value = Decimal(str(item["value"]))
        if (not value.is_finite() or abs(value) >= Decimal("1e20")
                or value != value.quantize(Decimal("0.0001"))):
            raise FinancialSyncError("unrepresentable_numeric_value")
        item["value"] = value
        for key in ("period_start", "period_end", "filed"):
            item[key] = date.fromisoformat(item[key]) if item[key] else None
        if (item["period_end"] is None or item["filed"] is None
                or (item["period_start"] and item["period_start"] > item["period_end"])
                or not re.fullmatch(r"\d{10}-\d{2}-\d{6}", item["accession_number"] or "")):
            raise FinancialSyncError("invalid_observation_metadata")
        for key, maximum in (("unit", 20), ("metric", 100), ("source", 100),
                             ("form", 20), ("frame", 30), ("fiscal_period", 10)):
            value = item[key]
            if value is not None and (not isinstance(value, str) or not value or len(value) > maximum):
                raise FinancialSyncError("invalid_observation_metadata")
        if not item["form"]:
            raise FinancialSyncError("invalid_observation_metadata")
        if item["fiscal_year"] is not None and (
                type(item["fiscal_year"]) is not int or not 0 < item["fiscal_year"] < 10000):
            raise FinancialSyncError("invalid_observation_metadata")
    except FinancialSyncError:
        raise
    except (ValueError, TypeError, InvalidOperation, KeyError) as exc:
        raise FinancialSyncError("invalid_observation_metadata") from exc
    return item


def build_metric_data(facts, canonical_metric, source_fact_names, unit):
    """Collect every distinct source vintage/concept; never choose a winner here."""
    combined, seen = [], set()
    for concept in source_fact_names:
        try:
            records = normalize_fact_data(facts, concept, unit)
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            raise FinancialSyncError("invalid_company_facts_payload") from exc
        for item in records:
            item["metric"] = canonical_metric
            item["source"] = f"SEC Company Facts API: {concept}"
            if item["value"] is None:
                continue  # A null XBRL value is not a numerical observation.
            item = validate_item(item)
            key = fact_identity(item)
            if key not in seen:
                combined.append(item)
                seen.add(key)
    return combined


def merge_company_facts(session, company_cik, facts, *, dry_run=False, metrics=None, publish=True):
    """Flush missing observations only. Caller owns the transaction/commit.

    Supported PostgreSQL writers take the same per-CIK transaction lock before
    reading identities. SQLite fixtures use a single writer.
    """
    cik = company_cik.zfill(10)
    if str(facts.get("cik", "")).zfill(10) != cik:
        raise FinancialSyncError("company_facts_cik_mismatch")
    if not isinstance(facts.get("facts", {}).get("us-gaap", {}), dict):
        raise FinancialSyncError("invalid_company_facts_payload")
    data = [item for metric in (metrics if metrics is not None else METRIC_SOURCES)
            for item in build_metric_data(facts, metric, METRIC_SOURCES[metric]["facts"], METRIC_SOURCES[metric]["unit"])]
    if not dry_run and session.get_bind().dialect.name == "postgresql":
        # A repeatable-read snapshot taken while waiting for the lock can miss
        # the preceding writer's commit. Fail safely rather than duplicate it.
        if session.connection().get_isolation_level() != "READ COMMITTED":
            raise FinancialSyncError("merge_requires_read_committed")
        session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": (1 << 40) + int(cik)})
    if not dry_run:
        from app.freshness_service import schema_ready
        from app.refresh_service import reject_conflicts
        if not schema_ready(session.connection()):
            raise FinancialSyncError("refresh_schema_migration_required")
    if session.scalar(select(Company.id).where(Company.cik == cik)) is None:
        raise FinancialSyncError("unknown_company_cik")
    existing = list(session.scalars(select(FinancialFact).where(FinancialFact.company_cik == cik)))
    if not dry_run:
        reject_conflicts(session, cik, [{"company_cik": cik, **item} for item in data])
    identities = {fact_identity(row) for row in existing}
    missing = []
    for item in data:
        record = {"company_cik": cik, **item}
        identity = fact_identity(record)
        if identity not in identities:
            identities.add(identity)
            missing.append(record)
    if not dry_run:
        session.add_all(FinancialFact(**record) for record in missing)
        session.flush()
    inserted = len(missing) if not dry_run else 0
    if publish and inserted:
        from app.refresh_service import record_fact_change
        record_fact_change(session, cik, inserted, {metric: sum(r["metric"] == metric for r in missing)
                                                   for metric in (metrics if metrics is not None else METRIC_SOURCES)})
    return {"facts_before": len(existing), "source_observations": len(data),
            "already_present": len(data) - len(missing), "facts_inserted": inserted,
            "would_insert": len(missing), "facts_after": len(existing) + inserted,
            "inserted_by_metric": {metric: sum(r["metric"] == metric for r in missing) if not dry_run else 0
                                   for metric in (metrics if metrics is not None else METRIC_SOURCES)}}


def import_metric(company_cik, facts, metric_name):
    """Compatibility entry point: count newly inserted facts, never replace."""
    with SessionLocal() as session, session.begin():
        return merge_company_facts(session, company_cik, facts, metrics=[metric_name])["facts_inserted"]


def import_company(company_cik):
    """One atomic merge for all supported metrics of a stored company."""
    cik = company_cik.zfill(10)
    from app.refresh_service import coordinator
    with coordinator(SessionLocal):
        facts = get_company_facts(cik)
        with SessionLocal() as session, session.begin():
            return merge_company_facts(session, cik, facts)["inserted_by_metric"]


def import_all_companies():
    """Legacy invocation delegates to the supported safe sync command."""
    from scripts.sync_financial_facts import main
    return main([])


if __name__ == "__main__":
    raise SystemExit(import_all_companies())
