"""Read-only, deployment-specific collation gate. Never executes maintenance SQL.

Run from backend: python -B -m scripts.verify_collation --help
All checks raise explicit exceptions; Python assertions are deliberately absent.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import itertools
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys


IMAGE = "sha256:7b822b0aac60967beb1ea5e576b8602c94c300a157d187f385ae3e0da199b90a"
CONTAINER = "b6b6024497e57ecdf82927b557f51ef20d7321be74b3a526afe134db851817d8"
VOLUME = "finlens-foundation_finlens-postgres-data"
CLUSTER = "7692131504986030119"
REVISION = "d7b834408ba8"
VECTOR_HASH = "d5146e1e5f4b843bdfeb4cca65db1211cfe272527d6aee0888d36b1e4e250cb6"
MIN_FREE = 1024**3
ROOT = Path(__file__).resolve().parents[1]

# name: table, ordered keys, unique, constraint type (if constraint-backed)
SPECS = {
    "alembic_version_pkc": ("alembic_version", ["version_num"], True, "p"),
    "companies_cik_key": ("companies", ["cik"], True, "u"),
    "ix_companies_ticker": ("companies", ["ticker"], True, None),
    "ix_financial_facts_company_cik": ("financial_facts", ["company_cik"], False, None),
    "ix_financial_facts_company_metric_period":
        ("financial_facts", ["company_cik", "metric", "period_end"], False, None),
    "ix_financial_facts_metric": ("financial_facts", ["metric"], False, None),
    "ix_filing_chunks_accession_index":
        ("filing_chunks", ["accession_number", "chunk_index"], True, None),
    "ix_filing_chunks_accession_number": ("filing_chunks", ["accession_number"], False, None),
    "ix_filing_chunks_company_accession":
        ("filing_chunks", ["company_cik", "accession_number"], False, None),
    "ix_filing_chunks_company_cik": ("filing_chunks", ["company_cik"], False, None),
}
IDENTITY_SQL = """SELECT system_identifier::text AS cluster,
 current_database() AS database, current_user AS role,
 (SELECT oid::bigint FROM pg_database WHERE datname=current_database()) AS database_oid
 FROM pg_control_system()"""
INDEX_SQL = """SELECT n.nspname AS schema, x.relname AS name,
 tn.nspname AS table_schema,t.relname AS table_name,am.amname AS method,x.relkind,
 i.indisunique AS unique,i.indisprimary AS primary,i.indisvalid AS valid,
 i.indisready AS ready,i.indislive AS live,pg_get_indexdef(x.oid) AS definition,
 pg_get_expr(i.indexprs,i.indrelid) AS expression,pg_get_expr(i.indpred,i.indrelid) AS predicate,
 x.oid AS oid,pg_relation_filenode(x.oid) AS filenode,pg_relation_size(x.oid) AS bytes,
 (SELECT json_agg(json_build_object('name',a.attname,'collation',
 CASE WHEN co.oid IS NULL THEN NULL ELSE cn.nspname||'.'||co.collname END,
 'opclass',ons.nspname||'.'||op.opcname) ORDER BY k.ord)
 FROM unnest(i.indkey::smallint[]) WITH ORDINALITY k(num,ord)
 LEFT JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=k.num
 LEFT JOIN pg_collation co ON co.oid=i.indcollation[(k.ord-1)::int]
 LEFT JOIN pg_namespace cn ON cn.oid=co.collnamespace
 LEFT JOIN pg_opclass op ON op.oid=i.indclass[(k.ord-1)::int]
 LEFT JOIN pg_namespace ons ON ons.oid=op.opcnamespace) AS attributes,
 (SELECT coalesce(json_agg(json_build_object('name',c.conname,'type',c.contype,
 'definition',pg_get_constraintdef(c.oid),'validated',c.convalidated)
 ORDER BY c.conname),'[]'::json) FROM pg_constraint c WHERE c.conindid=x.oid) AS constraints
 FROM pg_index i JOIN pg_class x ON x.oid=i.indexrelid
 JOIN pg_namespace n ON n.oid=x.relnamespace JOIN pg_class t ON t.oid=i.indrelid
 JOIN pg_namespace tn ON tn.oid=t.relnamespace JOIN pg_am am ON am.oid=x.relam
 WHERE n.nspname NOT IN ('pg_catalog','information_schema','pg_toast') ORDER BY n.nspname,x.relname"""
AFFECTED_SQL = """SELECT DISTINCT n.nspname||'.'||x.relname
 FROM pg_index i JOIN pg_class x ON x.oid=i.indexrelid
 JOIN pg_namespace n ON n.oid=x.relnamespace
 CROSS JOIN LATERAL unnest(i.indcollation::oid[]) k(oid)
 JOIN pg_collation co ON co.oid=k.oid WHERE co.collprovider='d'
 OR co.collversion <> pg_collation_actual_version(co.oid)"""


class SafetyError(RuntimeError):
    """Only controlled, credential-free messages may reach the operator."""


def require(condition, message):
    if not condition:
        raise SafetyError(message)


def check_optimization():
    require(sys.flags.optimize == 0, "Python optimization is prohibited for this safety gate")


def command(args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=30)
    require(result.returncode == 0, "Read-only Docker probe failed; inspect locally")
    return result.stdout.strip()


def docker(context, *args):
    return command(["docker", "--context", context, *args])


def runtime_identity():
    context = command(["docker", "context", "show"])
    require(context == "desktop-linux", "Unexpected Docker context")
    endpoint = docker(context, "context", "inspect", context, "--format", "{{.Endpoints.docker.Host}}")
    require(endpoint == "npipe:////./pipe/dockerDesktopLinuxEngine", "Unexpected Docker endpoint")
    # Inspect only selected fields: never serialize container environment/secrets.
    raw = docker(context, "inspect", CONTAINER, "--format",
                 '{{json .Id}}|{{json .Image}}|{{json .Mounts}}|{{json .NetworkSettings.Ports}}')
    cid, image, mounts, ports = [json.loads(part) for part in raw.split("|", 3)]
    data = [m for m in mounts if m["Destination"] == "/var/lib/postgresql/data"]
    require(cid == CONTAINER and image == IMAGE, "Container/image identity changed")
    require(len(data) == 1 and data[0]["Type"] == "volume" and data[0]["Name"] == VOLUME
            and data[0]["RW"] is True, "Persistent volume identity changed")
    require(ports.get("5432/tcp") == [{"HostIp": "127.0.0.1", "HostPort": "5432"}],
            "Unexpected PostgreSQL port mapping")
    return {"context": context, "endpoint": endpoint, "container": cid, "image": image,
            "volume": data[0], "ports": ports}


def docker_identity(runtime, database):
    sql = "BEGIN READ ONLY; SELECT row_to_json(i) FROM (" + IDENTITY_SQL + ") i; ROLLBACK;"
    value = docker(runtime["context"], "exec", runtime["container"], "psql", "-X", "-qAt",
                   "-U", "finlens", "-d", database, "-v", "ON_ERROR_STOP=1", "-c", sql)
    return json.loads(value)


def validate_identity(tcp, local, database, baseline=None, restored=False):
    require(tcp == local, "TCP and Docker PostgreSQL identities disagree")
    require(tcp["cluster"] == CLUSTER and tcp["database"] == database
            and tcp["role"] == "finlens", "Unexpected PostgreSQL target")
    if database == "finlens":
        require(tcp["database_oid"] == 16384, "Development database OID changed")
    else:
        require(bool(re.fullmatch(r"finlens_collationcheck_[0-9_]+", database)),
                "Disposable database name is outside the allowed namespace")
        require(tcp["database_oid"] != 16384, "Disposable database aliases development")
    if baseline:
        require(baseline["identity"]["cluster"] == tcp["cluster"], "Baseline cluster mismatch")
        if not restored:
            require(baseline["identity"] == tcp, "Baseline database identity changed")
        else:
            require(baseline["identity"]["database"] == "finlens", "Restore needs development baseline")


def validate_disk(free):
    require(set(free) == {"docker_data", "docker_tmp", "host_C", "host_D"}, "Incomplete disk gates")
    for name, available in free.items():
        require(isinstance(available, int) and available >= MIN_FREE, "Insufficient disk space: " + name)


def disk_space(runtime):
    free = {"host_C": shutil.disk_usage("C:\\").free, "host_D": shutil.disk_usage("D:\\").free}
    for name, path in (("docker_data", "/var/lib/postgresql/data"), ("docker_tmp", "/tmp")):
        line = docker(runtime["context"], "exec", runtime["container"], "df", "-Pk", path).splitlines()[-1]
        free[name] = int(line.split()[3]) * 1024
    validate_disk(free)
    return free


def expected_index(name):
    table, keys, unique, constraint = SPECS[name]
    attrs = []
    for key in keys:
        kind = "int4" if key == "chunk_index" else "date" if key == "period_end" else "text"
        attrs.append({"name": key, "collation": None if kind != "text" else "pg_catalog.default",
                      "opclass": "pg_catalog." + kind + "_ops"})
    constraints = [] if constraint is None else [{"name": name, "type": constraint,
        "definition": ("PRIMARY KEY" if constraint == "p" else "UNIQUE") + " (" + ", ".join(keys) + ")",
        "validated": True}]
    return {"schema": "public", "name": name, "table_schema": "public", "table_name": table,
        "method": "btree", "relkind": "i", "unique": unique, "primary": constraint == "p",
        "valid": True, "ready": True, "live": True, "expression": None, "predicate": None,
        "definition": "CREATE " + ("UNIQUE " if unique else "") + "INDEX " + name
            + " ON public." + table + " USING btree (" + ", ".join(keys) + ")",
        "attributes": attrs, "constraints": constraints}


def validate_indexes(indexes, affected):
    require(set(affected) == {"public." + name for name in SPECS}, "Affected qualified inventory changed")
    found = {}
    for row in indexes:
        identity = row["schema"] + "." + row["name"]
        require(identity not in found, "Duplicate qualified index identity")
        found[identity] = row
        require(row["valid"] and row["ready"] and row["live"], "Invalid/unready/dead index: " + identity)
    for name in SPECS:
        expected = expected_index(name)
        actual = found.get("public." + name)
        require(actual is not None, "Expected index missing: " + name)
        require({k: actual[k] for k in expected} == expected, "Index definition/attributes/constraints changed: " + name)
        require(isinstance(actual["oid"], int) and actual["filenode"] > 0, "Missing physical index identity")
    return {name: found["public." + name] for name in SPECS}


def nodes(plan):
    yield plan
    for child in plan.get("Plans", []):
        yield from nodes(child)


def validate_plan(plan, table, index=None):
    parts = list(nodes(plan))
    if index is None:
        require(any(p["Node Type"] == "Seq Scan" and p.get("Schema") == "public"
                    and p.get("Relation Name") == table for p in parts), "Reference is not the intended Seq Scan")
        require(not any("Index" in p["Node Type"] or "Bitmap" in p["Node Type"] for p in parts),
                "Indexed access in sequential reference")
    else:
        require(any(p["Node Type"] == "Index Scan" and p.get("Schema") == "public"
                    and p.get("Relation Name") == table and p.get("Index Name") == index for p in parts),
                "Requested index was not exercised: public." + index)
        require(not any("Sort" in p["Node Type"] or p["Node Type"] == "Seq Scan" for p in parts),
                "Indexed ordering depends on sort/sequence fallback")


def ordered_groups(rows, count):
    return [(key, sorted(tuple(r[count:]) for r in group))
            for key, group in itertools.groupby(rows, key=lambda r: tuple(r[:count]))]


def verify_queries(c):
    checks = []
    c.exec_driver_sql("SET LOCAL jit=off")
    c.exec_driver_sql("SET LOCAL max_parallel_workers_per_gather=0")
    for name, (table, keys, unique, _) in SPECS.items():
        columns = keys + ([] if table == "alembic_version" else ["id"])
        sql = "SELECT " + ",".join(columns) + " FROM public." + table + " ORDER BY " + ",".join(keys)
        for setting in ("enable_seqscan=on", "enable_indexscan=off", "enable_indexonlyscan=off",
                        "enable_bitmapscan=off", "enable_sort=on"):
            c.exec_driver_sql("SET LOCAL " + setting)
        seq_plan = c.exec_driver_sql("EXPLAIN (VERBOSE, FORMAT JSON) " + sql).scalar_one()[0]["Plan"]
        validate_plan(seq_plan, table)
        sequential = c.exec_driver_sql(sql).all()
        if unique:
            duplicates = c.exec_driver_sql("SELECT count(*) FROM (SELECT " + ",".join(keys)
                + " FROM public." + table + " GROUP BY " + ",".join(keys) + " HAVING count(*)>1) d").scalar_one()
            require(duplicates == 0, "Unique-key conflict: " + name)
        for setting in ("enable_seqscan=off", "enable_indexscan=on", "enable_sort=off"):
            c.exec_driver_sql("SET LOCAL " + setting)
        plan = c.exec_driver_sql("EXPLAIN (VERBOSE, FORMAT JSON) " + sql).scalar_one()[0]["Plan"]
        validate_plan(plan, table, name)
        indexed = c.exec_driver_sql(sql).all()
        require(ordered_groups(sequential, len(keys)) == ordered_groups(indexed, len(keys)),
                "Indexed/sequence results disagree: " + name)
        checks.append({"index": "public." + name, "rows": len(indexed),
                       "sequential_plan": seq_plan, "indexed_plan": plan})
    return checks


def validate_fingerprints(fp, vectors, expected):
    require(fp == expected, "Source-data fingerprint mismatch")
    require(vectors == VECTOR_HASH, "Embedding fingerprint mismatch")


def validate_phase(report, baseline, phase):
    require(phase in {"before", "restored", "rebuilt", "final"}, "Unknown audit phase")
    require(report["revision"] == REVISION, "Unexpected migration revision")
    locale = report["locale"]
    require(locale[:3] == ["c", "en_US.utf8", "en_US.utf8"] and locale[4] == "2.36", "Unexpected runtime collation")
    recorded = "2.36" if phase in {"restored", "final"} or report["identity"]["database"] != "finlens" else "2.41"
    require(locale[3] == recorded, "Wrong recorded collation for phase")
    if phase != "before":
        require(baseline is not None, "This phase requires a saved before baseline")
    if baseline:
        require(baseline.get("status") == "verified" and baseline.get("phase") in {"before", "restored"},
                "Baseline must be a verified pre-rebuild snapshot")
        require(report["runtime"] == baseline["runtime"], "Docker runtime changed since baseline")
        if phase != "restored":
            for name in SPECS:
                old, new = baseline["indexes"][name], report["indexes"][name]
                require(old["oid"] == new["oid"], "Logical index identity changed: " + name)
                changed = old["filenode"] != new["filenode"]
                require(changed == (phase in {"rebuilt", "final"}), "Unexpected physical rebuild state: " + name)


def maintenance_sql(report, operation):
    """Generate a reviewable plan only. There is deliberately no SQL execution path."""
    require(report.get("status") == "verified" and report.get("quiescent") is True,
            "SQL plans require a fresh verified quiescent snapshot")
    require(operation in {"rebuild", "refresh"}, "Unknown maintenance operation")
    require(report["phase"] in ({"before", "restored", "rebuilt"} if operation == "rebuild" else {"rebuilt"}),
            "Operation is out of order")
    ident = report["identity"]
    database = ident["database"]
    require(database == "finlens" or bool(re.fullmatch(r"finlens_collationcheck_[0-9_]+", database)),
            "Invalid SQL target")
    require(ident["cluster"] == CLUSTER and isinstance(ident["database_oid"], int), "Invalid SQL identity")
    sql = ["BEGIN;", "SET LOCAL lock_timeout='5s';", "SET LOCAL statement_timeout='120s';",
        "DO $target$ BEGIN IF (SELECT system_identifier::text FROM pg_control_system()) <> '" + CLUSTER
        + "' OR current_database() <> '" + database + "' OR (SELECT oid FROM pg_database WHERE datname=current_database()) <> "
        + str(ident["database_oid"]) + " THEN RAISE EXCEPTION 'Maintenance target mismatch'; END IF; END; $target$;",
        "LOCK TABLE public.alembic_version, public.companies, public.financial_facts, public.filing_chunks IN ACCESS EXCLUSIVE MODE;"]
    for name in SPECS:
        row = report["indexes"][name]
        require(isinstance(row["filenode"], int) and isinstance(row["oid"], int), "Invalid physical identity")
        sql.append("DO $index$ BEGIN IF 'public." + name + "'::regclass::oid <> " + str(row["oid"])
            + " OR pg_relation_filenode('public." + name + "'::regclass) <> " + str(row["filenode"])
            + " THEN RAISE EXCEPTION 'Index changed after verification'; END IF; END; $index$;")
    if operation == "rebuild":
        sql.extend("REINDEX INDEX public." + name + ";" for name in SPECS)
    else:
        sql.append("ALTER DATABASE " + database + " REFRESH COLLATION VERSION;")
    return "\n".join([*sql, "COMMIT;", ""])


def audit(database, phase, baseline=None, quiescent=False):
    check_optimization()
    require(database == "finlens" or bool(re.fullmatch(r"finlens_collationcheck_[0-9_]+", database)),
            "Database outside authorized verification namespace")
    require(phase != "restored" or database != "finlens", "Restore phase cannot target development")
    require(phase not in {"rebuilt", "final"} or quiescent, "Post-write gates require quiescent inspection")
    from sqlalchemy import create_engine
    from app.database import engine
    from scripts.verify_financial_metrics import fingerprint

    require(engine.url.host in {"localhost", "127.0.0.1"} and (engine.url.port or 5432) == 5432
            and engine.url.database == "finlens" and engine.url.username == "finlens", "Unexpected backend connection")
    runtime = runtime_identity()
    local = docker_identity(runtime, database)
    free = disk_space(runtime)
    target = create_engine(engine.url.set(database=database))
    try:
        with target.connect().execution_options(isolation_level="REPEATABLE READ", postgresql_readonly=True) as c:
            c.exec_driver_sql("SET LOCAL statement_timeout='60s'")
            c.exec_driver_sql("SET LOCAL lock_timeout='5s'")
            require(c.exec_driver_sql("SHOW transaction_read_only").scalar_one() == "on", "Audit is not read-only")
            tcp = dict(c.exec_driver_sql(IDENTITY_SQL).mappings().one())
            validate_identity(tcp, local, database, baseline, phase == "restored")
            versions = dict(c.exec_driver_sql("SELECT current_setting('server_version_num') AS postgres, "
                "(SELECT extversion FROM pg_extension WHERE extname='vector') AS pgvector").mappings().one())
            require(versions == {"postgres": "160015", "pgvector": "0.8.7"}, "PostgreSQL/pgvector runtime changed")
            if quiescent:
                require(c.exec_driver_sql("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() "
                    "AND pid<>pg_backend_pid()").scalar_one() == 0, "Other database sessions remain; stop API/writers")
            # Refuse additional persisted expression/partition/view scope; do not silently expand REINDEX.
            objects = c.exec_driver_sql("SELECT n.nspname||'.'||t.relname FROM pg_class t JOIN pg_namespace n "
                "ON n.oid=t.relnamespace WHERE n.nspname NOT IN ('pg_catalog','pg_toast','information_schema') "
                "AND t.relkind IN ('r','p','v','m','f')").scalars().all()
            require(set(objects) == {"public." + t for t in ("companies", "financial_facts", "filing_chunks", "alembic_version")},
                    "Persisted object inventory changed; repeat scope review")
            require(c.exec_driver_sql("SELECT count(*) FROM pg_attribute a JOIN pg_class t ON t.oid=a.attrelid "
                "WHERE t.relnamespace='public'::regnamespace AND a.attgenerated<>''").scalar_one() == 0,
                    "Generated expressions require scope review")
            manifest = validate_indexes([dict(r) for r in c.exec_driver_sql(INDEX_SQL).mappings()],
                                        c.exec_driver_sql(AFFECTED_SQL).scalars().all())
            fp = fingerprint(c)
            vectors = c.exec_driver_sql("SELECT id::text||chr(9)||embedding::text FROM filing_chunks "
                                       "WHERE embedding IS NOT NULL ORDER BY id").scalars().all()
            vector_hash = hashlib.sha256("\n".join(vectors).encode()).hexdigest()
            validate_fingerprints(fp, vector_hash, json.loads((ROOT / "reports/data_freshness_baseline.json").read_text()))
            report = {"identity": tcp, "runtime": runtime, "versions": versions, "free_bytes": free, "indexes": manifest,
                "fingerprints": fp, "embedding_sha256": vector_hash, "phase": phase,
                "revision": c.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one(),
                "locale": list(c.exec_driver_sql("SELECT datlocprovider,datcollate,datctype,datcollversion,"
                    "pg_database_collation_actual_version(oid) FROM pg_database WHERE datname=current_database()").one())}
            validate_phase(report, baseline, phase)
            report["query_checks"] = verify_queries(c)
            if quiescent:
                require(c.exec_driver_sql("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() "
                    "AND pid<>pg_backend_pid()").scalar_one() == 0, "Database sessions appeared during audit")
            require(runtime_identity() == runtime, "Runtime changed during audit")
            require(docker_identity(runtime, database) == tcp, "Docker database changed during audit")
            report.update(status="verified", captured_at=datetime.now(timezone.utc).isoformat(),
                          quiescent=quiescent, database_writes=False)
            return report
    finally:
        target.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", default="finlens")
    parser.add_argument("--phase", choices=("before", "restored", "rebuilt", "final"), default="before")
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--quiescent", action="store_true")
    parser.add_argument("--output", type=Path, help="New report file; existing files are never overwritten")
    parser.add_argument("--plan", choices=("rebuild", "refresh"), help="Generate SQL text only; never execute it")
    parser.add_argument("--sql-output", type=Path, help="New SQL plan file; requires --plan")
    args = parser.parse_args()
    try:
        check_optimization()
        require(bool(args.plan) == bool(args.sql_output), "--plan and --sql-output must be supplied together")
        baseline = json.loads(args.baseline.read_text(encoding="utf-8-sig")) if args.baseline else None
        result = audit(args.database, args.phase, baseline, args.quiescent)
        sql = maintenance_sql(result, args.plan) if args.plan else None
        content = json.dumps(result, indent=2, default=str)
        if args.output:
            with args.output.open("x", encoding="utf-8") as handle:
                handle.write(content + "\n")
        if sql is not None:
            with args.sql_output.open("x", encoding="utf-8") as handle:
                handle.write(sql)
        print(content)
        return 0
    except SafetyError as exc:
        print(json.dumps({"status": "rejected", "reason": str(exc)}), file=sys.stderr)
    except Exception:
        # Driver/OS exceptions can contain DSNs, connection arguments or server details.
        print(json.dumps({"status": "rejected", "reason": "Probe/report I/O failed; inspect privately"}), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
