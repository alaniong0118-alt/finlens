"""Verify the dedicated transient PostgreSQL before and after exact migrations."""
import sys
import time
import psycopg

def check(connection, stage):
    def fetch(query):
        return connection.execute(query).fetchone()[0]
    assert fetch("select current_database()") == "finlens_apple_proof"
    assert fetch("select current_setting('server_version_num')::int / 10000") == 16
    assert fetch("select inet_server_addr() = '127.0.0.1'::inet and inet_server_port() = 15432")
    if stage == "empty":
        assert fetch("select count(*) from pg_catalog.pg_tables where schemaname='public'") == 0
        assert fetch("select count(*) from pg_extension where extname='vector'") == 0
        connection.execute("CREATE EXTENSION vector")
    else:
        assert fetch("select count(*) from pg_extension where extname='vector'") == 1
        assert fetch("select version_num from alembic_version") == "b8d741104001"
        assert fetch("select count(*) from companies") == 0
        assert fetch("select count(*) from filing_chunks") == 0

assert len(sys.argv) == 2 and sys.argv[1] in {"empty", "migrated"}
for attempt in range(12):
    try:
        db = psycopg.connect(host="127.0.0.1", port=15432, dbname="finlens_apple_proof", user="finlens", connect_timeout=2)
        break
    except psycopg.OperationalError:
        if attempt == 11 or sys.argv[1] != "empty":
            raise
        time.sleep(1)
with db:
    check(db, sys.argv[1])
