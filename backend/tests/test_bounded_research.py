"""Increment 3: fake sessions, compiled production PostgreSQL, no DB/model I/O."""
from datetime import date
import json
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest
from sqlalchemy.dialects import postgresql

from app import config, main, freshness_service as fresh, filing_search_service as search, rag_context_service as rag
from app.models import Company, CompanyRefreshState, FilingChunk, FilingPublication
from app.sec_client import build_filing_url

CIK = "0000320193"
ACC = "0000320193-26-000020"
BASE = f"/companies/AAPL/filings/{ACC}"
VECTOR = [1.0] + [0.0] * 383


def chunk(i=0, text="Revenue increased.", cik=CIK, accession=ACC):
    return FilingChunk(id=i + 1, company_cik=cik, accession_number=accession,
        form="10-Q", filed=date(2026, 7, 31), filename="report.htm",
        chunk_id=f"chunk_{i:04d}", chunk_index=i, text=text,
        start_char=i * 2250, end_char=i * 2250 + len(text),
        embedding=VECTOR, sec_url=build_filing_url(cik, accession))


def inventory(chunks):
    return [NS(**{f: getattr(c, f) for f in fresh.CHUNK_IDENTITY_FIELDS}, text_length=len(c.text))
            for c in chunks]


class Rows(list):
    def all(self): return self
    def first(self): return self[0] if self else None


class Store:
    """Serve explicit synthetic rows; record every actual production statement."""
    def __init__(self, chunks=None, *, version=0, legacy=False):
        self.chunks = [chunk()] if chunks is None else chunks
        self.inventory = inventory(self.chunks)
        self.statements = []
        self.events = []
        self.legacy = legacy
        self.version = version
        self.company = Company(id=1, ticker="AAPL", cik=CIK, name="Apple", exchange="NASDAQ")
        self.companies = [self.company]
        self.state = CompanyRefreshState(company_cik=CIK, data_version=version or 0,
            facts_version=0, evidence_version=version or 0, evidence={}, facts={})
        self.publications = [FilingPublication(company_cik=CIK, accession_number=ACC,
            form="10-Q", filed=date(2026, 7, 31), filename="report.htm",
            chunk_count=len(self.chunks), content_digest=fresh.chunk_digest(self.chunks), data_version=0)]
        self.text = "Revenue original full text."
        self.text_size = len(self.text)
        self.body_override = None
        self.distances = {}

    def get_bind(self): return NS(dialect=NS(name="postgresql"))
    def connection(self): return self
    def close(self): self.events.append("close")
    def get(self, model, key):
        assert model is CompanyRefreshState, "publication ORM get is forbidden"
        return self.state if self.version is not None else None

    def record(self, stmt):
        sql = str(stmt.compile(dialect=postgresql.dialect()))
        assert sql.lstrip().startswith(("SELECT", "SET TRANSACTION")), sql
        self.statements.append((stmt, sql))
        return sql

    def scalar(self, stmt):
        self.record(stmt)
        names = [c.key for c in stmt.selected_columns]
        entity = stmt.column_descriptions[0]["entity"]
        if entity is Company: return self.company
        if entity is CompanyRefreshState: return self.version
        assert entity is FilingPublication
        if names == ["accession_number"]: return ACC if self.publications else None
        if names[0] is None or "length" in names[0]:
            self.events.append("text_length")
            return self.text_size
        assert names == ["cleaned_text"]
        self.events.append("text_body")
        return self.text

    def execute(self, stmt):
        sql = self.record(stmt)
        if sql.startswith("SET"): return Rows()
        descriptions = stmt.column_descriptions
        entity = descriptions[0]["entity"]
        names = [c.key for c in stmt.selected_columns]
        if entity is FilingChunk:
            if names[-1] == "text_length":
                self.events.append("inventory")
                return Rows(self.inventory[:fresh.MAX_COMPANY_CHUNKS + 1])
            self.events.append("bodies")
            chunks = self.chunks if self.body_override is None else self.body_override
            # Production distance is evaluated in SQL; fixtures supply its values.
            return Rows(sorted([(c, self.distances.get(c.id, 0.1)) for c in chunks],
                               key=lambda row: (row[1] is None, row[1] or 0)))
        if entity is FilingPublication:
            assert "cleaned_text" not in names
            return Rows([NS(accession_number=ACC, form="10-Q", filed=date(2026, 7, 31))]
                        if self.publications else [])
        if entity is Company:
            return Rows([(c, 1) for c in self.companies])
        raise AssertionError(sql)

    def scalars(self, stmt):
        self.record(stmt)
        entity = stmt.column_descriptions[0]["entity"]
        if entity is Company: return Rows(self.companies)
        if entity is FilingPublication: return Rows(self.publications)
        if entity.__name__ == "FinancialFact": return Rows()
        assert entity is FilingChunk
        self.events.append("bodies")
        return Rows(self.chunks if self.body_override is None else self.body_override)


@pytest.fixture(autouse=True)
def forbidden_work(monkeypatch):
    bomb = Mock(side_effect=AssertionError("Unmocked session/model/provider work forbidden"))
    monkeypatch.setattr(main, "HttpSessionLocal", bomb)
    monkeypatch.setattr("app.embedding_service._get_model", bomb)
    monkeypatch.setattr("app.sec_client._sec_get", bomb)
    monkeypatch.setattr("app.answer_service._get_openai_client", bomb)
    monkeypatch.setenv("FINLENS_SERVER_PROFILE", "development")
    monkeypatch.setattr(fresh, "schema_ready", lambda _: True)
    monkeypatch.setattr(main, "schema_ready", lambda _: True)
    yield bomb


def install(monkeypatch, store):
    monkeypatch.setattr(main, "HttpSessionLocal", lambda: store)
    monkeypatch.setattr(fresh, "schema_ready", lambda _: not store.legacy)
    monkeypatch.setattr(main, "schema_ready", lambda _: not store.legacy)
    encoder = Mock(return_value=[VECTOR])
    monkeypatch.setattr(search, "embed_texts", encoder)
    return encoder


GET_PATHS = [BASE + "/search", BASE + "/semantic-search", BASE + "/context", "/companies/AAPL/context"]


@pytest.mark.parametrize("path", GET_PATHS)
@pytest.mark.parametrize("query,limit", [("", 5), (" \t\n", 5), ("x" * 2001, 5),
    ("x", 0), ("x", 51), ("x", "bad"), ("x", "1.5"), ("x", "1.0"), ("x", "1e1")])
def test_http_rejects_inputs_before_session(path, query, limit, forbidden_work):
    response = TestClient(main.app).get(path, params={"q": query, "limit": limit})
    assert response.status_code == 422
    forbidden_work.assert_not_called()


@pytest.mark.parametrize("payload", [
    {"question": q} for q in ["", " \n\t", "x" * 2001, " " + "x" * 2000]
] + [{"question": "x", "limit": n} for n in [0, 51, "bad", "5", 1.5, True]])
def test_answer_rejects_inputs_before_session(payload, forbidden_work):
    assert TestClient(main.app).post(BASE + "/answer", json=payload).status_code == 422
    forbidden_work.assert_not_called()


@pytest.mark.parametrize("query", ["x", "é" * 2000, "😀" * 2000])
@pytest.mark.parametrize("limit", [1, 50])
def test_character_input_boundaries(query, limit):
    fresh.validate_research_input(query, limit)


@pytest.mark.parametrize("query,limit", [("", 5), (" " * 10, 5), ("x" * 2001, 5),
    ("x", 0), ("x", 51), ("x", True), ("x", 1.5), ("x", "5")])
@pytest.mark.parametrize("entry", [search.search_filing_chunks, search.search_filing_chunks_semantic,
    search.hybrid_search_filing_chunks, rag.build_filing_context])
def test_direct_selected_inputs_before_session_and_encoder(query, limit, entry):
    with pytest.raises(HTTPException) as exc:
        entry(Mock(side_effect=AssertionError("session")), CIK, ACC, query, limit)
    assert exc.value.status_code == 422


@pytest.mark.parametrize("entry", [rag.build_company_context, search.hybrid_search_company_chunks,
                                  search.rank_hybrid_chunks, rag._build_context])
def test_other_direct_inputs_before_work(entry):
    args = (Mock(), CIK, " ", 5) if entry is rag.build_company_context else ([], " ", 5)
    with pytest.raises(HTTPException) as exc: entry(*args)
    assert exc.value.status_code == 422


@pytest.mark.parametrize("entry", [search.search_filing_chunks, search.search_filing_chunks_semantic,
                                   search.hybrid_search_filing_chunks, rag.build_filing_context])
@pytest.mark.parametrize("damage", ["count", "length", "unicode_length"])
def test_selected_entire_inventory_rejected_before_body_or_encoder(entry, damage, monkeypatch):
    store = Store([chunk(0, "Revenue strong hit."), chunk(1, "Unrelated low ranked text.")])
    if damage == "count": store.inventory = inventory([chunk(i) for i in range(4001)])
    else: store.inventory[-1].text_length = 3001
    encoder = install(monkeypatch, store)
    with pytest.raises(HTTPException) as exc: entry(store, CIK, ACC, "revenue", 1)
    assert exc.value.status_code == 409
    assert exc.value.headers["X-FinLens-Error-Code"] == "SEARCH_SCOPE_TOO_LARGE"
    assert store.events == ["inventory"]
    encoder.assert_not_called()


@pytest.mark.parametrize("count", [0, 4000, 4001])
def test_inventory_sentinel_and_empty_scope(count):
    store = Store([chunk(i) for i in range(count)])
    if count > 4000:
        with pytest.raises(HTTPException): fresh.research_chunks(store)
        assert "bodies" not in store.events
    else:
        assert len(fresh.research_chunks(store)) == count
        assert store.events == (["inventory", "bodies"] if count else ["inventory"])
    stmt, sql = store.statements[0]
    projection = sql.split("\nFROM")[0]
    assert "length(filing_chunks.text) AS text_length" in projection
    assert projection.count("filing_chunks.text") == 1 and "embedding" not in projection
    assert stmt.compile().params["param_1"] == 4001
    assert "ORDER BY filing_chunks.company_cik, filing_chunks.accession_number, filing_chunks.chunk_index, filing_chunks.id" in sql


@pytest.mark.parametrize("text", ["é" * 3000, "😀" * 3000, "x" * 3001])
def test_chunk_character_count_and_sql_guards(text):
    store = Store([chunk(text=text)])
    if len(text) > 3000:
        with pytest.raises(HTTPException): fresh.research_chunks(store)
        return
    predicates = (FilingChunk.company_cik == CIK, FilingChunk.accession_number == ACC)
    assert fresh.research_chunks(store, *predicates)[0].text == text
    stmt, sql = store.statements[-1]
    assert "filing_chunks.company_cik =" in sql and "filing_chunks.accession_number =" in sql
    assert "filing_chunks.id IN" in sql and "length(filing_chunks.text) <=" in sql
    assert 3000 in stmt.compile().params.values()


@pytest.mark.parametrize("damage", ["missing", "extra", "duplicate", "id", "company_cik", "accession_number",
    "chunk_index", "chunk_id", "form", "filed", "filename", "start_char", "end_char", "sec_url", "length"])
def test_admission_body_mismatch_fails_atomically(damage):
    store = Store([chunk(0), chunk(1)])
    store.body_override = [chunk(0), chunk(1)]
    if damage == "missing": store.body_override.pop()
    elif damage == "extra": store.body_override.append(chunk(2))
    elif damage == "duplicate": store.body_override[1] = store.body_override[0]
    elif damage == "length": store.body_override[-1].text += "x"
    else:
        old = getattr(store.body_override[-1], damage)
        setattr(store.body_override[-1], damage, old + 1 if type(old) is int else "different")
    with pytest.raises(HTTPException) as exc: fresh.research_chunks(store)
    assert exc.value.status_code == 409 and exc.value.headers["X-FinLens-Error-Code"] == "EVIDENCE_PENDING"


def test_duplicate_admission_ids_rejected_before_bodies():
    store = Store()
    store.inventory *= 2
    with pytest.raises(HTTPException): fresh.research_chunks(store)
    assert store.events == ["inventory"]


def test_selected_lexical_semantic_hybrid_below_limit_preservation(monkeypatch):
    a, b, c = chunk(0, "Revenue Revenue."), chunk(1, "Revenue."), chunk(2, "Assets.")
    a.embedding = None
    store = Store([a, b, c])
    store.distances = {a.id: None, b.id: 0.3, c.id: 0.1}
    encoder = install(monkeypatch, store)
    assert [c.id for c in search.search_filing_chunks(store, CIK, ACC, " revenue ")] == [a.id, b.id]
    semantic = search.search_filing_chunks_semantic(store, CIK, ACC, " revenue ", 1)
    assert [(c.id, s) for c, s in semantic] == [(c.id, 0.9)]
    ranked = search.hybrid_search_filing_chunks(store, CIK, ACC, " revenue ")
    assert [r.chunk.id for r in ranked] == [b.id, a.id, c.id]
    assert ranked[1].semantic_similarity == 0 and ranked[1].lexical_score == 1
    assert all(call.args == (["revenue"],) for call in encoder.call_args_list)


@pytest.mark.parametrize("path", GET_PATHS + [BASE + "/chunks", BASE + "/text"])
def test_http_oversized_scope_atomic(path, monkeypatch):
    store = Store([chunk(0), chunk(1, "x" * 3001)])
    encoder = install(monkeypatch, store)
    response = TestClient(main.app).get(path, params={"q": "revenue"})
    assert response.status_code == 409, response.text
    assert response.headers["X-FinLens-Error-Code"] == "SEARCH_SCOPE_TOO_LARGE"
    assert "bodies" not in store.events and "text_body" not in store.events
    encoder.assert_not_called()


@pytest.mark.parametrize("size", [12000000, 12000001, None])
def test_full_text_preflight_boundary_null_and_character_units(size):
    store = Store()
    store.text_size = size
    store.text = "é" * size if size is not None and size <= 12000000 else None
    if size == 12000000:
        assert len(fresh.stored_research_text(store, CIK, ACC)) == size
        assert store.events == ["text_length", "text_body"]
        assert "length(filing_publications.cleaned_text) <=" in store.statements[-1][1]
    else:
        with pytest.raises(HTTPException) as exc: fresh.stored_research_text(store, CIK, ACC)
        assert exc.value.headers["X-FinLens-Error-Code"] == (
            "STORED_TEXT_UNAVAILABLE" if size is None else "SEARCH_SCOPE_TOO_LARGE")
        assert store.events == ["text_length"]
    projected = store.statements[0][1].split("\nFROM")[0]
    assert projected.count("cleaned_text") == 1 and "length(" in projected


def test_text_body_inconsistency_and_missing_schema(monkeypatch):
    store = Store()
    store.text_size += 1
    with pytest.raises(HTTPException) as exc: fresh.stored_research_text(store, CIK, ACC)
    assert exc.value.headers["X-FinLens-Error-Code"] == "EVIDENCE_PENDING"
    monkeypatch.setattr(fresh, "schema_ready", lambda _: False)
    store.statements.clear()
    with pytest.raises(HTTPException) as exc: fresh.stored_research_text(store, CIK, ACC)
    assert exc.value.headers["X-FinLens-Error-Code"] == "STORED_TEXT_UNAVAILABLE"
    assert store.statements == []


def test_publication_existence_and_latest_are_scalar_projections(monkeypatch):
    store = Store()
    install(monkeypatch, store)
    fresh.require_published(store, CIK, ACC)
    assert "cleaned_text" not in store.statements[-1][1]
    assert [c.key for c in store.statements[-1][0].selected_columns] == ["accession_number"]
    result = fresh.freshness(store, "AAPL")
    assert result.latest_indexed_filing.accession_number == ACC
    assert "cleaned_text" not in store.statements[-1][1]
    store.publications = []
    assert fresh.freshness(store, "AAPL").latest_indexed_filing is None


@pytest.mark.parametrize("company_wide", [False, True])
def test_context_full_formatted_boundary_prefix_duplicates_and_identity(monkeypatch, company_wide):
    # Many newlines make indentation significant; a raw passage budget would fail.
    ranked = [search.HybridSearchResult(chunk(i, text=("Revenue\n" * 200) + str(i)
                                            if i < 2 else "Revenue short later block."), .9, 1., 1.54)
              for i in range(3)]
    duplicated = [ranked[0], ranked[0], *ranked[1:]]
    query = " revenue "
    complete = rag._build_context(duplicated, query, 3, company_wide=company_wide)
    assert complete["query"] == query and len(complete["citations"]) == 3
    boundary = len(rag._build_context(duplicated, query, 2, company_wide=company_wide)["context"])
    monkeypatch.setattr(rag, "MAX_COMPANY_CONTEXT_CHARS", boundary)
    admitted = rag._build_context(duplicated, query, 3, company_wide=company_wide)
    assert len(admitted["context"]) == boundary and len(admitted["citations"]) == 2
    assert admitted["context"].endswith("[END SOURCE source_2]")
    assert admitted["citations"] == complete["citations"][:2]
    monkeypatch.setattr(rag, "MAX_COMPANY_CONTEXT_CHARS", boundary - 1)
    assert len(rag._build_context(duplicated, query, 3, company_wide=company_wide)["citations"]) == 1
    monkeypatch.setattr(rag, "MAX_COMPANY_CONTEXT_CHARS", 1)
    assert rag._build_context(duplicated, query, 3, company_wide=company_wide)["context"] == ""


@pytest.mark.parametrize("company_wide", [False, True])
def test_context_actual_24000_ceiling_complete_sources(company_wide):
    ranked = [search.HybridSearchResult(chunk(i, "Revenue " + str(i) + "\nx" * 1400), .9, 1, 1.54)
              for i in range(50)]
    result = rag._build_context(ranked, "revenue", 50, company_wide=company_wide)
    assert 0 < len(result["context"]) <= 24000
    assert len(result["citations"]) < 50
    assert result["context"].endswith(f'[END SOURCE source_{len(result["citations"])}]')


@pytest.mark.parametrize("path", ["/companies", "/companies/AAPL/sources"])
def test_legacy_discovery_bounds_are_atomic(path, monkeypatch):
    store = Store(legacy=True)
    store.inventory = inventory([chunk(i) for i in range(4001)])
    encoder = install(monkeypatch, store)
    response = TestClient(main.app).get(path)
    assert response.status_code == 409
    assert response.headers["X-FinLens-Error-Code"] == "SEARCH_SCOPE_TOO_LARGE"
    assert "bodies" not in store.events
    encoder.assert_not_called()


def test_legacy_expected_35_company_catalog_and_sources_offline(monkeypatch):
    report = Path(__file__).resolve().parents[1] / "reports/catalog_indexing_batch.json"
    catalog = json.loads(report.read_text(encoding="utf-8"))["companies"]
    assert len(catalog) == 35 and sum(c["chunk_count"] for c in catalog) == 3175
    chunks, companies = [], []
    for row in catalog:
        companies.append(Company(id=len(companies) + 1, ticker=row["ticker"], cik=row["company_cik"],
                                 name=row["ticker"], exchange="NASDAQ"))
        for i in range(row["chunk_count"]):
            c = chunk(i, cik=row["company_cik"], accession=row["accession_number"])
            c.id = len(chunks) + 1
            chunks.append(c)
    store = Store(chunks, legacy=True)
    store.companies = companies
    encoder = install(monkeypatch, store)
    result = TestClient(main.app).get("/companies")
    assert result.status_code == 200, result.text
    assert len(result.json()) == 35 and all(c["indexed_filing_count"] == 1 for c in result.json())
    assert len([s for _, s in store.statements if "FROM filing_chunks" in s]) == 2
    # Company-only sources use one bulk inventory/body pair, no per-filing loop.
    selected = Store([c for c in chunks if c.company_cik == CIK], legacy=True)
    install(monkeypatch, selected)
    response = TestClient(main.app).get("/companies/AAPL/sources")
    assert response.status_code == 200 and response.json()[0]["has_filing_chunks"]
    assert len([s for _, s in selected.statements if "FROM filing_chunks" in s]) == 2
    encoder.assert_not_called()


@pytest.mark.parametrize("version", [0, 7, None])
def test_freshness_zero_positive_unavailable_and_stale_pins(monkeypatch, version):
    store = Store(version=version)
    install(monkeypatch, store)
    client = TestClient(main.app)
    response = client.get("/companies/AAPL/freshness")
    assert response.status_code == (503 if version is None else 200)
    if version is None:
        assert response.headers["X-FinLens-Error-Code"] == "FRESHNESS_UNAVAILABLE"
        assert "X-FinLens-Data-Version" not in response.headers
    else:
        assert response.json()["data_version"] == version
        assert response.headers["X-FinLens-Data-Version"] == str(version)
    store.events.clear()
    stale = client.get(BASE + "/chunks", headers={"X-FinLens-Data-Version": "99"})
    assert stale.status_code == 409 and stale.headers["X-FinLens-Error-Code"] == "DATA_VERSION_CHANGED"
    assert "inventory" not in store.events and "bodies" not in store.events


def test_development_answer_and_exact_selected_metadata(monkeypatch):
    store = Store()
    encoder = install(monkeypatch, store)
    generate = Mock(return_value={"answer": "", "claims": [], "citations": [], "evidence_status": "insufficient",
                                 "question": " revenue ", "insufficient_evidence": True, "model": "fixture"})
    monkeypatch.setattr(main, "answer_filing_question", generate)
    client = TestClient(main.app)
    for suffix in ["search", "semantic-search", "context", "chunks", "text"]:
        response = client.get(BASE + "/" + suffix, params={"q": " revenue "})
        assert response.status_code == 200, response.text
        assert response.json()["accession_number"] == ACC
        if suffix in {"search", "semantic-search", "context"}: assert response.json()["query"] == " revenue "
    response = client.post(BASE + "/answer", json={"question": " revenue "})
    assert response.status_code == 200, response.text
    assert generate.call_args.args[0] == " revenue "
    context = generate.call_args.args[1]
    citation = generate.call_args.args[2][0]
    assert context.endswith("[END SOURCE source_1]")
    assert citation["sec_url"] == build_filing_url(CIK, ACC)
    assert citation["filename"] == "report.htm" and citation["start_char"] == 0
    assert citation["end_char"] == len(store.chunks[0].text)
    assert "close" in store.events
    assert encoder.call_count == 3


def test_sec_only_answer_admission_before_any_forbidden_work(monkeypatch, forbidden_work):
    monkeypatch.setattr(config, "_SERVER_PROFILE", config.ServerProfile("sec_readonly"))
    response = TestClient(main.app).post(BASE + "/answer", json={"question": "revenue"})
    assert response.status_code == 403 and response.headers["X-FinLens-Error-Code"] == "RELEASE_MODE_BLOCKED"
    forbidden_work.assert_not_called()


@pytest.mark.parametrize("path", GET_PATHS)
@pytest.mark.parametrize("query,limit", [("x", 1), ("é" * 2000, 50)])
def test_http_accepts_exact_input_boundaries(path, query, limit, monkeypatch):
    store = Store()
    install(monkeypatch, store)
    response = TestClient(main.app).get(path, params={"q": query, "limit": limit})
    assert response.status_code == 200, response.text
    assert response.json()["query"] == query


@pytest.mark.parametrize("entry", [search.hybrid_search_company_chunks, search.rank_hybrid_chunks])
def test_direct_rankers_admit_complete_inventory_before_embedding_or_ranking(entry, monkeypatch):
    encoder = Mock(side_effect=AssertionError("encoder must not execute"))
    monkeypatch.setattr(search, "embed_texts", encoder)
    chunks = [chunk(), chunk(1, "Unrelated " + "x" * 3000)]
    with pytest.raises(HTTPException) as exc:
        entry([(c, 0.1) for c in chunks] if entry is search.rank_hybrid_chunks else chunks, "revenue", 1)
    assert exc.value.headers["X-FinLens-Error-Code"] == "SEARCH_SCOPE_TOO_LARGE"
    encoder.assert_not_called()


@pytest.mark.parametrize("path", GET_PATHS + [BASE + "/chunks", BASE + "/text"])
def test_http_missing_admitted_body_cannot_return_partial_success(path, monkeypatch):
    store = Store([chunk(), chunk(1, "Revenue other.")])
    store.body_override = [store.chunks[0]]
    install(monkeypatch, store)
    response = TestClient(main.app).get(path, params={"q": "revenue"})
    assert response.status_code == 409, response.text
    assert response.headers["X-FinLens-Error-Code"] == "EVIDENCE_PENDING"


@pytest.mark.parametrize("suffix", ["chunks", "text"])
def test_empty_stored_inventory_returns_typed_unavailable(suffix, monkeypatch):
    store = Store([])
    install(monkeypatch, store)
    response = TestClient(main.app).get(BASE + "/" + suffix)
    assert response.status_code == 409
    assert response.headers["X-FinLens-Error-Code"] == "EVIDENCE_PENDING"


@pytest.mark.parametrize("size,code", [(12000001, "SEARCH_SCOPE_TOO_LARGE"), (None, "STORED_TEXT_UNAVAILABLE")])
def test_http_full_text_rejects_before_exact_body_read(size, code, monkeypatch):
    store = Store()
    store.text_size = size
    install(monkeypatch, store)
    response = TestClient(main.app).get(BASE + "/text")
    assert response.status_code == 409 and response.headers["X-FinLens-Error-Code"] == code
    assert "text_body" not in store.events


def test_development_answer_oversized_scope_before_generation(monkeypatch):
    store = Store([chunk(0), chunk(1, "x" * 3001)])
    encoder = install(monkeypatch, store)
    generate = Mock(side_effect=AssertionError("generation forbidden"))
    monkeypatch.setattr(main, "answer_filing_question", generate)
    response = TestClient(main.app).post(BASE + "/answer", json={"question": "revenue"})
    assert response.status_code == 409
    assert response.headers["X-FinLens-Error-Code"] == "SEARCH_SCOPE_TOO_LARGE"
    encoder.assert_not_called()
    generate.assert_not_called()


@pytest.mark.parametrize("entry", [search.search_filing_chunks_semantic, search.hybrid_search_filing_chunks])
def test_actual_distance_sql_bounds_all_candidates_before_filtering(entry, monkeypatch):
    store = Store()
    install(monkeypatch, store)
    entry(store, CIK, ACC, "revenue", 1)
    admission, body = store.statements
    assert "embedding" not in admission[1] and "IS NOT NULL" not in admission[1]
    assert body[0].compile().params["param_1"] == 4001
    assert "ORDER BY filing_chunks.embedding <=>" in body[1]
    assert "length(filing_chunks.text) <=" in body[1]
    assert "filing_chunks.id IN" in body[1]
    assert "filing_chunks.company_cik =" in body[1] and "filing_chunks.accession_number =" in body[1]


def test_legacy_oversized_chunk_atomic_before_any_body(monkeypatch):
    for path in ["/companies", "/companies/AAPL/sources"]:
        store = Store([chunk(0), chunk(1, "x" * 3001)], legacy=True)
        install(monkeypatch, store)
        response = TestClient(main.app).get(path)
        assert response.status_code == 409
        assert response.headers["X-FinLens-Error-Code"] == "SEARCH_SCOPE_TOO_LARGE"
        assert "bodies" not in store.events


@pytest.mark.parametrize("count", [20, 21])
def test_company_twenty_filing_ceiling_and_projection_remain_intact(count, monkeypatch):
    store = Store()
    store.publications *= count  # Count gate; below gate old eligibility still verifies chunks.
    install(monkeypatch, store)
    if count == 21:
        with pytest.raises(HTTPException) as exc: fresh.published_company_chunks(store, CIK)
        assert exc.value.headers["X-FinLens-Error-Code"] == "SEARCH_SCOPE_TOO_LARGE"
        assert "inventory" not in store.events
    else:
        fresh.published_company_chunks(store, CIK)
        assert "inventory" in store.events
    stmt, sql = store.statements[0]
    assert "cleaned_text" not in sql
    assert stmt.compile().params["param_1"] == 21
