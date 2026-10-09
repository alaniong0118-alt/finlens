"""Operator safety regressions: pure fixtures/subprocesses, no database writes."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from scripts import verify_collation as gate


def identity(database="finlens", oid=16384):
    return {"cluster": gate.CLUSTER, "database": database, "database_oid": oid, "role": "finlens"}


def indexes():
    return [dict(gate.expected_index(name), oid=100+i, filenode=200+i, bytes=16384)
            for i, name in enumerate(gate.SPECS)]


def plan(kind="Index Scan", index="companies_cik_key", table="companies", schema="public"):
    return {"Node Type": kind, "Schema": schema, "Relation Name": table, "Index Name": index}


def report():
    return {"identity": identity(), "revision": gate.REVISION, "runtime": {"image": gate.IMAGE},
        "locale": ["c", "en_US.utf8", "en_US.utf8", "2.41", "2.36"],
        "indexes": {r["name"]: r for r in indexes()}, "status": "verified", "phase": "before"}


def test_normal_before_phase_and_all_exact_index_definitions():
    original = report()
    gate.validate_identity(identity(), identity(), "finlens", original)
    gate.validate_indexes(indexes(), ["public."+n for n in gate.SPECS])
    gate.validate_phase(original, None, "before")
    gate.validate_plan(plan(), "companies", "companies_cik_key")
    gate.validate_plan(plan("Seq Scan"), "companies")


@pytest.mark.parametrize("field,value", [
    ("cluster", "other-cluster"), ("database", "postgres"),
    ("database_oid", 999), ("role", "other-role"),
])
def test_target_disagreement_fails(field, value):
    local = identity()
    local[field] = value
    with pytest.raises(gate.SafetyError):
        gate.validate_identity(identity(), local, "finlens")


@pytest.mark.parametrize("field,value", [("cluster", "other"), ("database_oid", 999), ("database", "postgres")])
def test_both_paths_agree_on_wrong_target_still_fails(field, value):
    wrong = identity()
    wrong[field] = value
    with pytest.raises(gate.SafetyError):
        gate.validate_identity(wrong, wrong, "finlens")


@pytest.mark.parametrize("field,value", [
    ("definition", "CREATE INDEX changed ON public.companies USING btree (name)"),
    ("table_schema", "other"), ("table_name", "financial_facts"),
    ("schema", "other"), ("method", "hash"), ("unique", False),
    ("valid", False), ("ready", False), ("live", False),
    ("constraints", []), ("predicate", "cik IS NOT NULL"), ("relkind", "I"),
    ("attributes", [{"name": "cik", "collation": "pg_catalog.C", "opclass": "pg_catalog.text_ops"}]),
])
def test_changed_index_contract_rejected(field, value):
    rows = indexes()
    # First index is a constraint-backed, unique text primary key.
    rows[0][field] = value
    with pytest.raises(gate.SafetyError):
        gate.validate_indexes(rows, ["public."+n for n in gate.SPECS])


def test_extra_affected_schema_is_not_hidden_by_basename():
    with pytest.raises(gate.SafetyError):
        gate.validate_indexes(indexes(), ["public."+n for n in gate.SPECS] + ["other.companies_cik_key"])


@pytest.mark.parametrize("wrong", [
    plan(index="ix_companies_ticker"), plan(schema="other"), plan(table="financial_facts"),
    plan(kind="Index Only Scan"),
    {"Node Type": "Sort", "Plans": [plan()]},
    {"Node Type": "Append", "Plans": [plan(), plan("Seq Scan")]},
])
def test_wrong_index_or_indexed_plan_rejected(wrong):
    with pytest.raises(gate.SafetyError):
        gate.validate_plan(wrong, "companies", "companies_cik_key")


@pytest.mark.parametrize("wrong", [plan(), plan("Bitmap Heap Scan"), plan("Seq Scan", table="financial_facts")])
def test_nonsequential_reference_rejected(wrong):
    with pytest.raises(gate.SafetyError):
        gate.validate_plan(wrong, "companies")


def test_order_comparison_ignores_only_duplicate_key_row_order():
    require = gate.require
    require(gate.ordered_groups([("a", 2), ("a", 1), ("b", 3)], 1)
            == gate.ordered_groups([("a", 1), ("a", 2), ("b", 3)], 1), "Equivalent groups")
    assert gate.ordered_groups([("b", 3), ("a", 1)], 1) != gate.ordered_groups([("a", 1), ("b", 3)], 1)


@pytest.mark.parametrize("kind", ["rows", "vectors"])
def test_fingerprint_mismatch_rejected(kind):
    expected = {"counts": {"companies": 35}, "sha256": {"companies": "abc"}}
    actual = deepcopy(expected)
    vector = gate.VECTOR_HASH
    if kind == "rows":
        actual["sha256"]["companies"] = "changed"
    else:
        vector = "changed"
    with pytest.raises(gate.SafetyError):
        gate.validate_fingerprints(actual, vector, expected)


@pytest.mark.parametrize("device", ["docker_data", "docker_tmp", "host_C", "host_D"])
def test_insufficient_space_rejected(device):
    free = {name: gate.MIN_FREE for name in ("docker_data", "docker_tmp", "host_C", "host_D")}
    gate.validate_disk(free)
    free[device] -= 1
    with pytest.raises(gate.SafetyError):
        gate.validate_disk(free)


def test_missing_disk_gate_rejected():
    with pytest.raises(gate.SafetyError):
        gate.validate_disk({"docker_data": gate.MIN_FREE})


@pytest.mark.parametrize("change", ["revision", "collation", "provider", "locale", "runtime"])
def test_wrong_runtime_revision_or_collation_rejected(change):
    before = report()
    current = deepcopy(before)
    if change == "revision": current["revision"] = "f94c6f41e0cb"
    if change == "collation": current["locale"][4] = "2.41"
    if change == "provider": current["locale"][0] = "i"
    if change == "locale": current["locale"][1] = "C"
    if change == "runtime": current["runtime"] = {"image": "other"}
    with pytest.raises(gate.SafetyError):
        gate.validate_phase(current, before, "before")


def test_final_cannot_pass_existing_collation_mismatch():
    with pytest.raises(gate.SafetyError):
        gate.validate_phase(report(), report(), "final")


def test_rebuilt_and_final_require_all_physical_changes_and_preserve_oid():
    before = report()
    after = deepcopy(before)
    with pytest.raises(gate.SafetyError):
        gate.validate_phase(after, before, "rebuilt")
    for row in after["indexes"].values(): row["filenode"] += 100
    gate.validate_phase(after, before, "rebuilt")
    after["locale"][3] = "2.36"
    gate.validate_phase(after, before, "final")
    after["indexes"]["companies_cik_key"]["oid"] += 1
    with pytest.raises(gate.SafetyError):
        gate.validate_phase(after, before, "final")


@pytest.mark.parametrize("optimization", ["1", "2"])
def test_optimization_cli_fails_before_any_probe(optimization):
    result = subprocess.run([sys.executable, "-B", "-m", "scripts.verify_collation"],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True,
        env=dict(os.environ, PYTHONOPTIMIZE=optimization, PYTHONDONTWRITEBYTECODE="1"))
    assert result.returncode == 1
    assert json.loads(result.stderr)["reason"] == "Python optimization is prohibited for this safety gate"
    assert not result.stdout


def test_wrong_database_cli_stops_before_probe():
    result = subprocess.run([sys.executable, "-B", "-m", "scripts.verify_collation", "--database", "postgres"],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True,
        env=dict(os.environ, PYTHONOPTIMIZE="0", PYTHONDONTWRITEBYTECODE="1"))
    assert result.returncode == 1
    assert "namespace" in json.loads(result.stderr)["reason"]


def test_readonly_probe_failure_is_sanitized(monkeypatch):
    class Failed:
        returncode = 1
        stdout = ""
        stderr = "password=DO_NOT_EXPOSE"
    monkeypatch.setattr(gate.subprocess, "run", lambda *a, **k: Failed())
    with pytest.raises(gate.SafetyError, match="Read-only Docker probe failed") as exc:
        gate.command(["docker", "context", "show"])
    assert "DO_NOT_EXPOSE" not in str(exc.value)


@pytest.mark.parametrize("field", ["context", "endpoint", "container", "image", "volume", "ports"])
def test_runtime_changes_fail_closed(monkeypatch, field):
    context = "other" if field == "context" else "desktop-linux"
    endpoint = "other" if field == "endpoint" else "npipe:////./pipe/dockerDesktopLinuxEngine"
    container = "other" if field == "container" else gate.CONTAINER
    image = "other" if field == "image" else gate.IMAGE
    mounts = [{"Destination": "/var/lib/postgresql/data", "Type": "volume", "RW": True,
               "Name": "other" if field == "volume" else gate.VOLUME}]
    ports = {} if field == "ports" else {"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": "5432"}]}
    monkeypatch.setattr(gate, "command", lambda *a: context)
    monkeypatch.setattr(gate, "docker", lambda ctx, *args:
                        endpoint if args[0] == "context" else "|".join(json.dumps(v) for v in (container,image,mounts,ports)))
    with pytest.raises(gate.SafetyError):
        gate.runtime_identity()


class QueryFixture:
    """Exercise the production query loop, including EXPLAIN mode and plan guards."""
    def __init__(self, wrong_index=False, wrong_rows=False, duplicates=False):
        self.sequential = True
        self.value = None
        self.wrong_index, self.wrong_rows, self.duplicates = wrong_index, wrong_rows, duplicates

    def exec_driver_sql(self, sql):
        if sql.startswith("SET LOCAL"):
            if sql.endswith("enable_seqscan=on"): self.sequential = True
            if sql.endswith("enable_seqscan=off"): self.sequential = False
            return self
        if sql.startswith("SELECT count(*)"):
            self.value = int(self.duplicates)
            return self
        table = sql.split(" FROM public.")[1].split(" ORDER BY")[0]
        keys = sql.split(" ORDER BY ")[1].split(",")
        name = next(n for n,(t,k,_,_) in gate.SPECS.items() if t == table and k == keys)
        if sql.startswith("EXPLAIN"):
            if not sql.startswith("EXPLAIN (VERBOSE, FORMAT JSON)"):
                raise RuntimeError("Production query did not request verbose JSON")
            node = plan("Seq Scan" if self.sequential else "Index Scan", name, table)
            if self.wrong_index and not self.sequential: node["Index Name"] = "wrong_index"
            self.value = [{"Plan": node}]
        else:
            self.value = [tuple([label]*len(keys) + ([] if table == "alembic_version" else [i]))
                          for i,label in enumerate(("a", "b"))]
            if self.wrong_rows and not self.sequential: self.value.reverse()
        return self

    def scalar_one(self): return self.value
    def all(self): return self.value


def test_production_query_loop_positive_and_every_requested_index():
    checks = gate.verify_queries(QueryFixture())
    assert [r["index"] for r in checks] == ["public." + n for n in gate.SPECS]


@pytest.mark.parametrize("failure", ["wrong_index", "wrong_rows", "duplicates"])
def test_production_query_loop_rejects_injected_failures(failure):
    with pytest.raises(gate.SafetyError):
        gate.verify_queries(QueryFixture(**{failure: True}))


def test_sql_generation_is_guarded_and_preserves_operation_order():
    before = report()
    before["quiescent"] = True
    sql = gate.maintenance_sql(before, "rebuild")
    assert sql.startswith("BEGIN;") and sql.endswith("COMMIT;\n")
    assert sql.count("REINDEX INDEX public.") == 10
    assert "ALTER DATABASE" not in sql
    assert sql.index("Maintenance target mismatch") < sql.index("REINDEX")
    assert sql.count("Index changed after verification") == 10
    assert gate.CLUSTER in sql and "16384" in sql
    with pytest.raises(gate.SafetyError): gate.maintenance_sql(before, "refresh")
    before["phase"] = "rebuilt"
    refresh = gate.maintenance_sql(before, "refresh")
    assert "ALTER DATABASE finlens REFRESH COLLATION VERSION;" in refresh
    assert "REINDEX" not in refresh
    before["quiescent"] = False
    with pytest.raises(gate.SafetyError): gate.maintenance_sql(before, "rebuild")
