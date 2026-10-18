"""Selected-passage integration only: synthetic sessions and production SQL.

Run via run_dep01a2_increment2_offline.py with -B, no pytest cache/plugins.
No physical DB, dotenv, provider, model, service or filesystem output is needed.
"""
from datetime import date
from types import SimpleNamespace as NS
from unittest.mock import Mock

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest
from sqlalchemy.dialects import postgresql

from app import config, database, main, freshness_service as fresh
from app import filing_tone_service as tone
from app.filing_tone import score_filing_tone as kernel_score
from app.models import Company, CompanyRefreshState, FilingChunk, FilingPublication
from app.release_policy import READONLY_ROUTES
from app.sec_client import build_filing_url


CIK = "0000320193"
ACC = "0000320193-26-000020"
OTHER_ACC = "0000320193-25-000001"
BASE = f"/companies/AAPL/filings/{ACC}/chunks"
PATH = BASE + "/chunk_0000/tone"
TEMPLATE = "/companies/{ticker}/filings/{accession_number}/chunks/{chunk_id}/tone"
VECTOR = [1.0] + [0.0] * 383


def chunk(i=0, text="strong strong weak"):
    return FilingChunk(id=i + 1, company_cik=CIK, accession_number=ACC,
        form="10-Q", filed=date(2026, 7, 31), filename="report.htm",
        chunk_id=f"chunk_{i:04d}", chunk_index=i, text=text,
        start_char=i * 2250, end_char=i * 2250 + len(text),
        embedding=VECTOR, sec_url=build_filing_url(CIK, ACC))


def inventory(chunks):
    return [NS(**{f: getattr(c, f) for f in fresh.CHUNK_IDENTITY_FIELDS},
               text_length=len(c.text)) for c in chunks]


class Rows(list):
    pass


class Store:
    """In-memory fixtures; every SQL statement is compiled, never executed."""
    def __init__(self, chunks=None, *, version=0):
        self.chunks = [chunk()] if chunks is None else chunks
        self.inventory = inventory(self.chunks)
        self.version = version
        self.company = Company(id=1, ticker="AAPL", cik=CIK, name="Apple", exchange="NASDAQ")
        self.state = CompanyRefreshState(company_cik=CIK, data_version=version,
            evidence_version=version, facts_version=0, evidence={}, facts={})
        # Deliberately no cleaned_text attribute. Reading it must be impossible.
        self.publications = [NS(company_cik=CIK, accession_number=ACC,
            form="10-Q", filed=date(2026, 7, 31), filename="report.htm",
            chunk_count=len(self.chunks), content_digest=fresh.chunk_digest(self.chunks),
            data_version=0)]
        self.events = []
        self.statements = []
        self.body_override = None
        self.closed = False
        self.close_error = False
        self.legacy = False

    def get_bind(self): return NS(dialect=NS(name="postgresql"))
    def connection(self): return self

    def close(self):
        self.events.append("close")
        if self.close_error:
            raise RuntimeError("private cleanup diagnostic")
        self.closed = True

    def invalidate(self): self.events.append("invalidate")

    def get(self, model, key):
        assert model is CompanyRefreshState and key == CIK
        self.events.append("state")
        return self.state

    def record(self, stmt):
        sql = str(stmt.compile(dialect=postgresql.dialect()))
        assert sql.lstrip().startswith(("SELECT", "SET TRANSACTION")), "Writes forbidden"
        assert "cleaned_text" not in sql
        self.statements.append((stmt, sql))
        return sql

    def scalar(self, stmt):
        self.record(stmt)
        entity = stmt.column_descriptions[0]["entity"]
        if entity is CompanyRefreshState:
            self.events.append("pin")
            return self.version
        assert entity is Company
        self.events.append("company")
        return self.company

    def execute(self, stmt):
        sql = self.record(stmt)
        if sql.startswith("SET TRANSACTION"):
            return Rows()
        entity = stmt.column_descriptions[0]["entity"]
        names = tuple(c.key for c in stmt.selected_columns)
        if entity is FilingPublication:
            assert names == tone.PUBLICATION_FIELDS
            self.events.append("manifest")
            return Rows(self.publications[:2])
        assert entity is FilingChunk and names[-1] == "text_length"
        self.events.append("inventory")
        return Rows(self.inventory[:4001])

    def scalars(self, stmt):
        self.record(stmt)
        assert stmt.column_descriptions[0]["entity"] is FilingChunk
        self.events.append("bodies")
        return Rows(self.chunks if self.body_override is None else self.body_override)

    def forbidden_write(self, *args, **kwargs):
        raise AssertionError("Session writes forbidden")

    add = add_all = delete = flush = commit = rollback = forbidden_write


@pytest.fixture(autouse=True)
def forbid_work(monkeypatch):
    bomb = Mock(side_effect=AssertionError("Unapproved physical/provider/model work"))
    monkeypatch.setattr(main, "HttpSessionLocal", bomb)
    monkeypatch.setattr(database.engine, "connect", bomb)
    monkeypatch.setattr("app.embedding_service._get_model", bomb)
    monkeypatch.setattr("app.embedding_service.embed_texts", bomb)
    monkeypatch.setattr("app.sec_client._sec_get", bomb)
    monkeypatch.setattr("app.answer_service._get_openai_client", bomb)
    monkeypatch.setattr(config, "_SERVER_PROFILE", config.ServerProfile("development"))
    yield bomb
    bomb.assert_not_called()


def install(monkeypatch, store):
    monkeypatch.setattr(main, "HttpSessionLocal", lambda: store)
    monkeypatch.setattr(fresh, "schema_ready", lambda _: not store.legacy)
    monkeypatch.setattr(tone, "schema_ready", lambda _: not store.legacy)
    def score(text):
        assert store.closed, "Scoring must follow successful session close"
        assert text in [c.text for c in store.chunks]
        store.events.append("score")
        return kernel_score(text)

    scoring = Mock(side_effect=score)
    monkeypatch.setattr(tone, "score_filing_tone", scoring)
    return scoring


def get(pin="0", path=PATH, **kwargs):
    headers = {} if pin is None else {"X-FinLens-Data-Version": pin}
    return TestClient(main.app).get(path, headers=headers, **kwargs)


def assert_error(response, code, status=409):
    assert response.status_code == status, response.text
    assert response.headers["X-FinLens-Error-Code"] == code
    assert response.headers["Cache-Control"] == "no-store"
    assert "private" not in response.text


@pytest.mark.parametrize("pin", [None, "", " ", " 0", "0 ", "+0", "-1", "00", "01",
    "1.0", "1e0", "1,0", "9007199254740992", "9" * 100])
def test_pin_rejected_before_session(pin):
    assert_error(get(pin), "TONE_INVALID_INPUT", 422)


@pytest.mark.parametrize("ticker,accession,chunk_id", [
    ("A" * 17, ACC, "chunk_0000"), ("A%20APL", ACC, "chunk_0000"),
    ("AAPL", "bad", "chunk_0000"), ("AAPL", ACC + "x", "chunk_0000"),
    ("AAPL", ACC, "chunk_0"), ("AAPL", ACC, "chunk_00000"),
    ("AAPL", ACC, "CHUNK_0000"), ("AAPL", ACC, "chunk_-001"),
])
def test_invalid_selectors_before_session(ticker, accession, chunk_id):
    assert_error(get(path=f"/companies/{ticker}/filings/{accession}/chunks/{chunk_id}/tone"),
                 "TONE_INVALID_INPUT", 422)


@pytest.mark.parametrize("pin", [True, 0, 0.0, "０", "١", "0\n"])
def test_direct_invalid_pin_types_and_unicode(pin):
    with pytest.raises(HTTPException) as exc:
        tone.resolve_published_passage(Mock(), "AAPL", ACC, "chunk_0000", pin)
    assert exc.value.status_code == 422


def test_duplicate_headers_and_untrusted_query_metadata_before_session():
    response = TestClient(main.app).get(PATH, headers=[
        ("X-FinLens-Data-Version", "0"), ("X-FinLens-Data-Version", "0")])
    assert_error(response, "TONE_INVALID_INPUT", 422)
    for key in ("text", "sec_url", "company_cik", "data_version", "accession_number"):
        assert_error(get(params={key: "forged"}), "TONE_INVALID_INPUT", 422)


@pytest.mark.parametrize("version", [0, 8, tone.MAX_SAFE_VERSION])
def test_current_pin_zero_and_old_publication_survive_facts_advances(monkeypatch, version):
    store = Store(version=version)
    store.state.evidence_version = 0
    scoring = install(monkeypatch, store)
    response = get(str(version), path=PATH.replace("AAPL", "aapl"))
    assert response.status_code == 200, response.text
    body = response.json()
    assert response.headers["X-FinLens-Data-Version"] == str(version)
    assert response.headers["Cache-Control"] == "no-store"
    assert body["ticker"] == "AAPL" and body["company_cik"] == CIK
    assert body["company_name"] == "Apple"
    assert body["data_version"] == version and body["evidence_version"] == 0
    assert body["publication"] == {"accession_number": ACC, "data_version": 0,
                                   "content_digest": store.publications[0].content_digest}
    assert body["source"] == {"chunk_id": "chunk_0000", "form": "10-Q",
        "filed": "2026-07-31", "filename": "report.htm", "sec_url": build_filing_url(CIK, ACC)}
    assert body["text"] == store.chunks[0].text
    assert body["scope"] == "published_chunk" and body["offsets"] == "unicode_code_point"
    assert body["tone"]["score"] == {"numerator": 1, "denominator": 3}
    assert body["tone"]["method_version"] == "sec-filing-tone-v1"
    assert body["tone"]["lexicon_version"] == "authored-finance-tone-v1"
    assert store.events[-2:] == ["close", "score"]
    scoring.assert_called_once_with(body["text"])
    assert "REPEATABLE READ, READ ONLY" in store.statements[0][1]


def test_stale_pin_before_publication_or_bodies(monkeypatch):
    store = Store(version=1)
    scoring = install(monkeypatch, store)
    response = get("0")
    assert_error(response, "DATA_VERSION_CHANGED")
    assert response.headers["X-FinLens-Data-Version"] == "1"
    assert store.events == ["pin", "close"]
    scoring.assert_not_called()


def test_missing_current_version_is_not_zero(monkeypatch):
    store = Store()
    store.version = None
    scoring = install(monkeypatch, store)
    response = get()
    assert_error(response, "DATA_VERSION_CHANGED")
    assert "X-FinLens-Data-Version" not in response.headers
    scoring.assert_not_called()


@pytest.mark.parametrize("damage", ["missing", "duplicate", "pending", "invalid_stream", "legacy",
    "missing_state", "state_company", "negative_evidence", "future_evidence", "bool_evidence"])
def test_lifecycle_failures_before_chunk_inventory(monkeypatch, damage):
    store = Store()
    if damage == "missing": store.publications = []
    elif damage == "duplicate": store.publications *= 2
    elif damage == "pending": store.state.evidence = {"status": "pending", "pending_targets": [ACC]}
    elif damage == "invalid_stream": store.state.evidence = {"status": "invented"}
    elif damage == "legacy": store.legacy = True
    elif damage == "missing_state": store.state = None
    elif damage == "state_company": store.state.company_cik = "0000000001"
    elif damage == "negative_evidence": store.state.evidence_version = -1
    elif damage == "future_evidence": store.state.evidence_version = 1
    elif damage == "bool_evidence": store.state.evidence_version = True
    scoring = install(monkeypatch, store)
    # Legacy schema fails in shared pin admission, before the resolver.
    assert_error(get(), "DATA_VERSION_CHANGED" if damage == "legacy" else "EVIDENCE_PENDING")
    assert "inventory" not in store.events and store.closed
    scoring.assert_not_called()


@pytest.mark.parametrize("status", ["failed", "pending", "stale", "unknown"])
def test_unrelated_refresh_status_does_not_invalidate_intact_publication(monkeypatch, status):
    store = Store(version=5)
    store.state.evidence_version = 2
    store.state.evidence = {"status": status, "pending_targets": [OTHER_ACC]}
    install(monkeypatch, store)
    assert get("5").status_code == 200


@pytest.mark.parametrize("raw", [None, [], "", 0, False, {"pending_targets": "forged"},
    {"status": "current", "extra_field": "forged"}])
def test_malformed_lifecycle_json_is_not_defaulted_to_empty_state(monkeypatch, raw):
    store = Store()
    store.state.evidence = raw
    scoring = install(monkeypatch, store)
    assert_error(get(), "EVIDENCE_PENDING")
    assert "manifest" not in store.events
    scoring.assert_not_called()


@pytest.mark.parametrize("field,value", [
    ("company_cik", "0000000001"), ("accession_number", OTHER_ACC),
    ("form", "8-K"), ("filed", "2026-07-31"), ("filename", "../report.htm"),
    ("filename", "report.htm#forged"), ("chunk_count", 0), ("chunk_count", True),
    ("data_version", -1), ("data_version", 1), ("data_version", True),
    ("content_digest", None), ("content_digest", "g" * 64),
])
def test_invalid_manifest_fails_before_bodies(monkeypatch, field, value):
    store = Store()
    setattr(store.publications[0], field, value)
    scoring = install(monkeypatch, store)
    assert_error(get(), "EVIDENCE_PENDING")
    assert "inventory" not in store.events and store.closed
    scoring.assert_not_called()


@pytest.mark.parametrize("target,field,value", [
    ("company", "ticker", "MSFT"), ("company", "cik", "bad"),
    ("chunk", "company_cik", "0000000001"), ("chunk", "accession_number", OTHER_ACC),
    ("chunk", "form", "10-K"), ("chunk", "filed", date(2025, 1, 1)),
    ("chunk", "filename", "different.htm"), ("chunk", "sec_url", "https://evil.invalid/"),
    ("chunk", "chunk_id", "chunk_0001"), ("chunk", "chunk_index", 1),
    ("chunk", "start_char", -1), ("chunk", "end_char", 1),
])
def test_no_company_filing_or_chunk_substitution(monkeypatch, target, field, value):
    store = Store()
    setattr(store.company if target == "company" else store.chunks[0], field, value)
    # Keep inventory internally consistent to exercise publication/URL binding too.
    store.inventory = inventory(store.chunks)
    scoring = install(monkeypatch, store)
    assert_error(get(), "EVIDENCE_PENDING")
    scoring.assert_not_called()


@pytest.mark.parametrize("vector", [None, [], [1.0], [0.0] * 384,
    [float("nan")] * 384, [float("inf")] * 384, [1e100] * 384, ["bad"] * 384])
def test_every_embedding_must_be_valid_even_unselected(monkeypatch, vector):
    store = Store([chunk(), chunk(1, "other passage")])
    store.chunks[1].embedding = vector
    scoring = install(monkeypatch, store)
    assert_error(get(), "EVIDENCE_PENDING")
    scoring.assert_not_called()


def test_digest_covers_unselected_text_and_missing_chunks(monkeypatch):
    store = Store([chunk(), chunk(1, "other passage")])
    store.chunks[1].text = "alter passage"  # Same length, different digest.
    scoring = install(monkeypatch, store)
    assert_error(get(), "EVIDENCE_PENDING")
    scoring.assert_not_called()


@pytest.mark.parametrize("damage", ["count", "missing_body", "duplicate_body", "foreign_body",
    "identity_change", "duplicate_inventory", "empty_text"])
def test_inventory_and_body_must_exactly_agree(monkeypatch, damage):
    store = Store()
    if damage == "count": store.publications[0].chunk_count = 2
    elif damage == "missing_body": store.body_override = []
    elif damage == "duplicate_body": store.body_override = store.chunks * 2
    elif damage == "foreign_body":
        foreign = chunk()
        foreign.id = 200
        store.body_override = [foreign]
    elif damage == "identity_change": store.chunks[0].filename = "different.htm"
    elif damage == "duplicate_inventory":
        store.inventory *= 2
        store.publications[0].chunk_count = 2
    elif damage == "empty_text":
        store.chunks[0].text = " " * len(store.chunks[0].text)
    scoring = install(monkeypatch, store)
    assert_error(get(), "EVIDENCE_PENDING")
    if damage in {"count", "duplicate_inventory"}: assert "bodies" not in store.events
    scoring.assert_not_called()


@pytest.mark.parametrize("damage", ["manifest_count", "inventory_count", "length", "null_length"])
def test_bounds_before_body_materialization(monkeypatch, damage):
    store = Store()
    if damage == "manifest_count": store.publications[0].chunk_count = 4001
    elif damage == "inventory_count": store.inventory = inventory([chunk(i) for i in range(4001)])
    elif damage == "length": store.inventory[0].text_length = 3001
    else: store.inventory[0].text_length = None
    scoring = install(monkeypatch, store)
    assert_error(get(), "SEARCH_SCOPE_TOO_LARGE")
    assert "bodies" not in store.events
    scoring.assert_not_called()


@pytest.mark.parametrize("chunks", [[chunk(text="é" * 3000)], [chunk(i) for i in range(4000)]])
def test_exact_publication_bounds_are_supported(monkeypatch, chunks):
    store = Store(chunks)
    install(monkeypatch, store)
    assert get().status_code == 200


def test_sql_is_scoped_bounded_and_never_reads_full_filing(monkeypatch):
    store = Store()
    install(monkeypatch, store)
    assert get().status_code == 200
    manifest, inv, body = store.statements[-3:]
    for stmt, sql in (manifest, inv, body):
        params = stmt.compile().params
        assert CIK in params.values() and ACC in params.values()
        assert "cleaned_text" not in sql
        assert "LIMIT" in sql
    assert manifest[0].compile().params["param_1"] == 2
    assert "embedding" not in inv[1]
    assert "length(filing_chunks.text) AS text_length" in inv[1]
    assert inv[1].split("\nFROM")[0].count("filing_chunks.text") == 1
    assert "filing_chunks.chunk_id =" not in inv[1]
    assert inv[0].compile().params["param_1"] == 4001
    assert "filing_chunks.id IN" in body[1] and "length(filing_chunks.text) <=" in body[1]
    assert 3000 in body[0].compile().params.values()
    assert body[0].compile().params["param_1"] == 4001
    assert body[0].get_execution_options()["populate_existing"] is True
    assert "ORDER BY filing_chunks.company_cik, filing_chunks.accession_number, filing_chunks.chunk_index, filing_chunks.id" in body[1]


def test_unknown_scoped_chunk_is_404_without_fallback(monkeypatch):
    store = Store()
    scoring = install(monkeypatch, store)
    assert_error(get(path=BASE + "/chunk_0001/tone"), "TONE_CHUNK_NOT_FOUND", 404)
    assert store.closed and "bodies" in store.events
    scoring.assert_not_called()


def test_selected_nonfirst_overlapping_chunk_has_only_local_tone(monkeypatch):
    # Valid stored windows can overlap. Never combine their repeated words.
    first, second = chunk(text="strong"), chunk(1, "weak weak")
    first.start_char, first.end_char = 2000, 5000
    second.start_char, second.end_char = 4250, 7250
    store = Store([first, second])
    scoring = install(monkeypatch, store)
    response = get(path=BASE + "/chunk_0001/tone")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source"]["chunk_id"] == "chunk_0001"
    assert body["text"] == second.text
    assert body["tone"]["score"] == {"numerator": -1, "denominator": 1}
    assert [(m["start"], m["end"]) for m in body["tone"]["matches"]] == [(0, 4), (5, 9)]
    scoring.assert_called_once_with(second.text)


def test_independent_snapshots_produce_identical_exact_output(monkeypatch):
    install(monkeypatch, Store())
    first = get().json()
    install(monkeypatch, Store())
    assert get().json() == first


def test_unknown_company_is_404(monkeypatch):
    store = Store()
    store.company = None
    scoring = install(monkeypatch, store)
    assert get().status_code == 404
    assert "manifest" not in store.events and store.closed
    scoring.assert_not_called()


@pytest.mark.parametrize("text,score,status,reason", [
    ("strong weak", {"numerator": 0, "denominator": 1}, "scored", None),
    ("ordinary revenue", None, "unscorable", "no_lexicon_matches"),
    ("not strong", None, "unscorable", "all_matches_negated"),
    ("...", None, "unscorable", "no_tokens"),
])
def test_exact_zero_is_distinct_from_valid_unscorable(monkeypatch, text, score, status, reason):
    store = Store([chunk(text=text)])
    install(monkeypatch, store)
    response = get()
    assert response.status_code == 200, response.text
    result = response.json()["tone"]
    assert (result["score"], result["status"], result["reason"]) == (score, status, reason)


def test_unicode_crlf_and_negation_offsets_use_exact_input(monkeypatch):
    text = "  📈\r\nSTRONG no loss; weak"
    store = Store([chunk(text=text)])
    install(monkeypatch, store)
    response = get()
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["text"] == text
    matches = body["tone"]["matches"]
    assert [m["text"] for m in matches] == ["STRONG", "loss", "weak"]
    for match in matches:
        assert text[match["start"]:match["end"]] == match["text"]
    assert [m["start"] for m in matches] == sorted(m["start"] for m in matches)
    assert matches[0]["start"] == 5  # Emoji is one Python code point, CRLF is two.
    assert matches[1]["negator_span"] == [12, 14]
    assert body["tone"]["negated_count"] == 1
    assert body["tone"]["score"] == {"numerator": 0, "denominator": 1}


@pytest.mark.parametrize("text", ["strong\x00weak", "strong\u200bweak", "strong " * 400])
def test_unsupported_kernel_text_maps_to_sanitized_409(monkeypatch, text):
    store = Store([chunk(text=text)])
    install(monkeypatch, store)
    response = get()
    # 400 matches fits kernel limits; control characters are unsupported.
    if "\x00" not in text and "\u200b" not in text:
        assert response.status_code == 200
    else:
        assert_error(response, "TONE_INPUT_UNSUPPORTED")
        assert text not in response.text
    assert store.events[-2:] == ["close", "score"]


def test_client_body_cannot_substitute_source_or_text(monkeypatch):
    store = Store()
    install(monkeypatch, store)
    response = TestClient(main.app).request("GET", PATH,
        headers={"X-FinLens-Data-Version": "0"},
        json={"text": "weak", "sec_url": "https://evil.invalid/", "company_cik": "forged"})
    assert response.status_code == 200
    assert response.json()["text"] == store.chunks[0].text
    assert response.json()["source"]["sec_url"] == build_filing_url(CIK, ACC)


def test_failed_session_close_never_scores(monkeypatch):
    store = Store()
    store.close_error = True
    scoring = install(monkeypatch, store)
    with TestClient(main.app, raise_server_exceptions=False) as client:
        response = client.get(PATH, headers={"X-FinLens-Data-Version": "0"})
    assert response.status_code == 500
    assert "private" not in response.text
    assert "invalidate" in store.events
    scoring.assert_not_called()


def test_only_exact_new_get_is_admitted_in_sec_readonly(monkeypatch):
    monkeypatch.setattr(config, "_SERVER_PROFILE", config.ServerProfile("sec_readonly"))
    store = Store()
    install(monkeypatch, store)
    assert get().status_code == 200
    assert {pair for pair in READONLY_ROUTES if pair[1].endswith("/tone")} == {("GET", TEMPLATE)}


@pytest.mark.parametrize("method,path", [
    ("POST", PATH), ("PUT", PATH), ("DELETE", PATH), ("PATCH", PATH), ("HEAD", PATH),
    ("GET", PATH + "/"), ("GET", PATH.replace("/tone", "/tone-alias")),
])
def test_other_methods_and_aliases_blocked_before_work(monkeypatch, method, path):
    monkeypatch.setattr(config, "_SERVER_PROFILE", config.ServerProfile("sec_readonly"))
    response = TestClient(main.app).request(method, path, follow_redirects=False)
    assert_error(response, "RELEASE_MODE_BLOCKED", 403)
