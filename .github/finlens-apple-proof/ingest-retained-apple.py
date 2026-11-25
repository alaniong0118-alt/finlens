"""Unexecuted hosted-proof draft. Stage real SEC bytes before sealed execution."""

import hashlib
import json
import math
import os
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

ASSETS = Path(__file__).with_name("public-input-metadata.json")
CIK = "0000320193"
ACCESSION = "0000320193-26-000020"
SOURCE = "https://www.sec.gov/Archives/edgar/data/320193/000032019326000020/0000320193-26-000020-index.html"
EXPECTED_DIGEST = "63bd9d7c6d1a2fff5ac22b3363c35b7dbd712d155fb324f43a7cc739404f7b7f"

def isolation_precheck() -> None:
    if os.environ.get("FINLENS_APPLE_ADMITTED") != "one-use-network-none":
        raise RuntimeError("admission missing")
    if {entry.name for entry in Path("/sys/class/net").iterdir()} != {"lo"}:
        raise RuntimeError("non-loopback interface present")
    routes = Path("/proc/net/route").read_text().splitlines()[1:]
    if any(line.split()[0] != "lo" for line in routes if line.strip()):
        raise RuntimeError("non-loopback IPv4 route")
    if os.environ.get("OPENAI_API_KEY") or os.environ.get("HF_HUB_OFFLINE") != "1":
        raise RuntimeError("offline no-key environment missing")
    db = urlsplit(os.environ["DATABASE_URL"])
    if (db.scheme, db.hostname, db.port, db.path) != ("postgresql+psycopg", "127.0.0.1", 15432, "/finlens_apple_proof"):
        raise RuntimeError("not the disposable test database")

def load_inputs(directory: Path) -> tuple[dict, str]:
    metadata = json.loads(ASSETS.read_text())
    rows = metadata["sec"]
    if [entry["name"] for entry in rows] != ["facts.raw", "submission.raw"]:
        raise RuntimeError("wrong SEC inputs")
    values = []
    for entry in rows:
        body = (directory / entry["name"]).read_bytes()
        if len(body) != entry["length"] or hashlib.sha256(body).hexdigest() != entry["sha256"]:
            raise RuntimeError("wrong retained bytes")
        values.append(body)
    facts = json.loads(values[0])
    if str(facts.get("cik", "")).zfill(10) != CIK:
        raise RuntimeError("wrong issuer")
    return facts, values[1].decode("utf-8")

def check_vector(vector) -> bool:
    return len(vector) == 384 and all(math.isfinite(float(value)) for value in vector) and abs(
        math.sqrt(sum(float(value) ** 2 for value in vector)) - 1
    ) <= 1e-5

def run() -> dict:
    isolation_precheck()
    facts, raw = load_inputs(Path(os.environ["FINLENS_APPLE_INPUT_DIRECTORY"]))
    from sqlalchemy import text
    from app import sec_client, sec_filing_service
    from app.database import SessionLocal
    from app.embedding_service import embed_texts, _get_model
    from app.models import FilingPublication
    from scripts import setup_demo

    # Circle only the transport boundary. Real ingestion, metrics, encoder and
    # PostgreSQL are not mocked. Neither disk sources nor keys are printed.
    def company_facts(cik):
        if cik != CIK:
            raise RuntimeError("unexpected source CIK")
        return facts

    def raw_filing(cik, accession):
        if (cik, accession) != (CIK, ACCESSION):
            raise RuntimeError("unexpected filing request")
        return raw

    with SessionLocal() as session:
        if session.execute(text("SELECT count(*) FROM companies")).scalar_one() != 0:
            raise RuntimeError("disposable database was not empty")
        if session.execute(text("SELECT count(*) FROM filing_chunks")).scalar_one() != 0:
            raise RuntimeError("disposable database already had chunks")
        with patch.object(sec_client, "get_sec_headers", return_value={}), \
             patch.object(sec_client, "get_company_facts", side_effect=company_facts) as f, \
             patch.object(sec_filing_service, "get_filing_raw_text", side_effect=raw_filing) as s:
            result = setup_demo.setup_demo(session)
            f.assert_called_once_with(CIK)
            s.assert_called_once_with(CIK, ACCESSION)
        if (result["status"], result["action"], result["new_embeddings"]) != ("ready", "ingested", 37):
            raise RuntimeError("fresh ingestion did not create 37 new embeddings")
        chunks = setup_demo.demo_chunks(session)
        if len(chunks) != 37 or not all(row.sec_url == SOURCE and row.filename == "aapl-20260627.htm"
                                      and check_vector(row.embedding) for row in chunks):
            raise RuntimeError("wrong stored filing evidence or embedding")
        published = session.get(FilingPublication, (CIK, ACCESSION))
        if published is None or published.content_digest != EXPECTED_DIGEST:
            raise RuntimeError("wrong published content digest")
        item = embed_texts(["services net sales"])
        if len(item) != 1 or not check_vector(item[0]):
            raise RuntimeError("query vector is not finite normalized 384-dimensional")
        # A fresh process should resolve the same pinned cache, but reopen
        # through setup must not invoke either transport or encoder.
        _get_model.cache_clear()
        def prohibited(*args, **kwargs):
            raise RuntimeError("reopen tried to re-acquire inputs")
        from app import embedding_service
        with patch.object(sec_client, "get_sec_headers", side_effect=prohibited), \
             patch.object(sec_client, "get_company_facts", side_effect=prohibited), \
             patch.object(sec_filing_service, "get_filing_raw_text", side_effect=prohibited), \
             patch.object(embedding_service, "embed_texts", side_effect=prohibited):
            reopened = setup_demo.setup_demo(session)
        if (reopened["action"], reopened["new_embeddings"]) != ("already_complete", 0):
            raise RuntimeError("reopen did not reuse filing")
    return {"result": "ingestion_verified", "accession": ACCESSION, "chunks": 37,
            "new_vectors": 37, "reopen_new_vectors": 0, "dimensions": 384}

if __name__ == "__main__":
    try:
        print(json.dumps(run(), sort_keys=True))
    except (Exception, AssertionError) as cause:
        raise SystemExit(f"HOLD: {type(cause).__name__}") from None
