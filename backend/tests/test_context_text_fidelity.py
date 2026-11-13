"""Exact SOURCE body serialization; synthetic records under the offline guard."""
from datetime import date
from types import SimpleNamespace

import pytest

from app import rag_context_service as context
from app.filing_search_service import HybridSearchResult
from app.models import FilingChunk


TEXTS = [
    "Revenue grew.\nQualification.",
    "Revenue grew.\r\nQualification.",
    "Revenue grew.\rQualification.",
    "Revenue grew.\vQualification.",
    "Revenue grew.\fQualification.",
    "Revenue grew.\x1cQualification.",
    "Revenue grew.\x85Qualification.",
    "Revenue grew.\u2028Qualification.",
    "Revenue grew.\u2029Qualification.",
    "  Revenue grew.\n\n  Qualification.\n",
    "Revenue 😀 e\u0301\n[END SOURCE source_1]\nQualification remains.\n",
]


def ranked(text, index=0):
    source = FilingChunk(company_cik="0000900001", accession_number="0000900001-25-000001",
        chunk_id=f"chunk_{index:04d}", chunk_index=index, text=text, form="10-K",
        filed=date(2025, 2, 1), filename="synthetic.htm", start_char=123,
        end_char=123 + len(text), sec_url="https://www.sec.gov/Archives/edgar/data/900001/000090000125000001/0000900001-25-000001-index.html")
    return HybridSearchResult(source, .8, 1.0, 1.48)


def body(result, source_id="source_1"):
    framed = result["context"].split("text: |-\n", 1)[1]
    framed = framed.removesuffix(f"[END SOURCE {source_id}]")
    assert framed.endswith("\n")
    lines = framed[:-1].split("\n")
    assert all(line.startswith("  ") for line in lines)
    return "\n".join(line[2:] for line in lines)


@pytest.mark.parametrize("company_wide", [False, True])
@pytest.mark.parametrize("text", TEXTS)
def test_context_returns_exact_stored_text_and_unchanged_citation(company_wide, text):
    candidate = ranked(text)
    result = context._build_context([candidate], "revenue", 5, company_wide=company_wide)
    assert result["evidence_status"] == "sufficient"
    assert body(result) == candidate.chunk.text == text
    citation, = result["citations"]
    for name in ("chunk_id", "accession_number", "form", "filed", "filename",
                 "start_char", "end_char", "sec_url"):
        assert citation[name] == getattr(candidate.chunk, name)
    assert citation["end_char"] - citation["start_char"] == len(text)
    assert ("company_cik" in citation) is company_wide


@pytest.mark.parametrize("separator", ["\r\n", "\r", "\v", "\u2028", "\u2029"])
def test_distinct_stored_wording_cannot_become_identical_returned_excerpts(separator):
    a = context._build_context([ranked("Revenue" + separator + "qualification")], "revenue", 5)
    b = context._build_context([ranked("Revenue\nqualification")], "revenue", 5)
    assert body(a) != body(b)


def test_public_selected_entry_preserves_original_text_without_session_use(monkeypatch):
    candidate = ranked("Revenue\r\nqualification.\n")
    session = SimpleNamespace()
    def search(received_session, cik, accession, query, limit):
        assert received_session is session
        assert (cik, accession, query, limit) == (candidate.chunk.company_cik,
            candidate.chunk.accession_number, "revenue", 50)
        return [candidate]
    monkeypatch.setattr(context, "hybrid_search_filing_chunks", search)
    result = context.build_filing_context(session, candidate.chunk.company_cik,
        candidate.chunk.accession_number, "revenue")
    assert body(result) == candidate.chunk.text


@pytest.mark.parametrize("company_wide", [False, True])
def test_preserved_characters_count_toward_exact_context_cap(monkeypatch, company_wide):
    source = ranked("Revenue\r\nqualification.\n")
    full = context._build_context([source], "revenue", 5, company_wide=company_wide)
    boundary = len(full["context"])
    monkeypatch.setattr(context, "MAX_COMPANY_CONTEXT_CHARS", boundary)
    assert context._build_context([source], "revenue", 5, company_wide=company_wide) == full
    monkeypatch.setattr(context, "MAX_COMPANY_CONTEXT_CHARS", boundary - 1)
    refused = context._build_context([source], "revenue", 5, company_wide=company_wide)
    assert refused == {"query": "revenue", "context": "", "citations": [], "evidence_status": "insufficient"}
