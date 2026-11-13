"""Synthetic cleaned-filing source ranges; no DB, network or model fixtures."""
from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app import rag_context_service, refresh_service
from app.filing_search_service import rank_hybrid_chunks
from app.models import FilingChunk
from app.sec_urls import build_filing_url
from app.sec_parser import chunk_filing_text, clean_filing_html


@pytest.mark.parametrize("text,size,overlap", [
    (" Revenue increased. ", 2500, 250),
    ("Revenue grew. Costs fell.", 13, 3),
    ("  Revenue increased.\r\n\t", 2500, 250),
    ("\u2003Revenue increased.\u00a0", 2500, 250),
    ("Revenue  costs  cash  income", 9, 2),
    ("Revenue\U0001f4ca increased.\u2003Costs fell.", 15, 4),
])
def test_chunk_offsets_identify_exact_stored_passage(text, size, overlap):
    chunks = chunk_filing_text(text, chunk_size=size, overlap=overlap)
    assert chunks
    for chunk in chunks:
        assert text[chunk["start_char"]:chunk["end_char"]] == chunk["text"]
        assert chunk["end_char"] - chunk["start_char"] == len(chunk["text"])


def test_default_windows_match_exact_cleaned_filing_ranges():
    # Ordinary HTML cleaning produces single spaces; default windows routinely
    # cut next to them. No unusual whitespace or alternate parser is required.
    cleaned = clean_filing_html("<html><body><p>" + "Revenue increased. " * 500
                                + "</p></body></html>")
    chunks = chunk_filing_text(cleaned)
    assert len(chunks) > 1
    for chunk in chunks:
        assert cleaned[chunk["start_char"]:chunk["end_char"]] == chunk["text"]


def test_trimmed_offsets_preserve_existing_text_ids_and_window_overlap():
    chunks = chunk_filing_text("  abcd  efgh  ijkl  ", chunk_size=10, overlap=3)
    assert chunks == [
        {"chunk_id": "chunk_0000", "text": "abcd  ef", "start_char": 2, "end_char": 10},
        {"chunk_id": "chunk_0001", "text": "efgh  ijk", "start_char": 8, "end_char": 17},
        {"chunk_id": "chunk_0002", "text": "ijkl", "start_char": 14, "end_char": 18},
    ]


@pytest.mark.parametrize("text", ["", " ", "\t\r\n\u2003", " " * 40])
def test_no_passage_is_invented_for_empty_or_whitespace_text(text):
    assert chunk_filing_text(text, chunk_size=10, overlap=3) == []


def test_synthetic_staging_to_retrieved_citation_keeps_exact_source_ranges(monkeypatch):
    """Real parser/stager/ranker/context, fake acquisition/encoder, no persistence.

    This does not commission a publication or grant source/financial authority.
    """
    cik, accession = "0000320193", "0000320193-26-000001"
    metadata = SimpleNamespace(accession_number=accession, form="10-Q",
                               filed=date(2026, 7, 31), primary_document="fixture.htm")
    raw = ("<DOCUMENT>\n<TYPE>10-Q\n<FILENAME>fixture.htm\n<TEXT><html><body>"
           + "<p>Revenue increased. Costs fell.</p>" * 300
           + "</body></html></TEXT>\n</DOCUMENT>")
    # No existing publication or DB operation: exercise only detached staging.
    monkeypatch.setattr(refresh_service, "stored_chunks", lambda *_args: [])
    session = Mock(side_effect=AssertionError("Database use forbidden"))
    loader = Mock(return_value=raw)
    encoder = Mock(side_effect=lambda texts: [[1.0] + [0.0] * 383 for _ in texts])
    chunks, cleaned = refresh_service.stage_filing(session, cik, metadata, encoder, loader)
    loader.assert_called_once_with(cik, accession)
    assert session.mock_calls == []
    assert len(chunks) > 1 and cleaned is not None
    assert encoder.call_args.args[0] == [chunk.text for chunk in chunks]
    for chunk in chunks:
        assert cleaned[chunk.start_char:chunk.end_char] == chunk.text

    ranked = rank_hybrid_chunks([(chunk, 0.0) for chunk in chunks], "revenue", 50)
    monkeypatch.setattr(rag_context_service, "hybrid_search_filing_chunks",
                        lambda *_args: ranked)
    context = rag_context_service.build_filing_context(session, cik, accession, "revenue")
    assert context["evidence_status"] == "sufficient"
    assert context["citations"]
    stored = {chunk.chunk_id: chunk for chunk in chunks}
    for citation in context["citations"]:
        chunk = stored[citation["chunk_id"]]
        assert citation["accession_number"] == accession
        assert citation["start_char"] == chunk.start_char
        assert citation["end_char"] == chunk.end_char
        assert cleaned[citation["start_char"]:citation["end_char"]] == chunk.text
        assert "text: |-\n  " + chunk.text + "\n[END SOURCE " + citation["citation_id"] + "]" in context["context"]
    assert session.mock_calls == []


def test_synthetic_existing_chunks_keep_legacy_offsets_without_reacquisition(monkeypatch):
    cik, accession = "0000320193", "0000320193-26-000001"
    metadata = SimpleNamespace(accession_number=accession, form="10-Q",
                               filed=date(2026, 7, 31), primary_document="fixture.htm")
    legacy = FilingChunk(company_cik=cik, accession_number=accession, form=metadata.form,
        filed=metadata.filed, filename=metadata.primary_document, chunk_index=0,
        chunk_id="chunk_0000", text="Revenue increased.", start_char=0, end_char=20,
        sec_url=build_filing_url(cik, accession), embedding=[1.0] + [0.0] * 383)
    fields = ("company_cik", "accession_number", "form", "filed", "filename",
              "chunk_index", "chunk_id", "text", "start_char", "end_char", "sec_url", "embedding")
    before = {field: getattr(legacy, field) for field in fields}
    monkeypatch.setattr(refresh_service, "stored_chunks", lambda *_args: [legacy])
    session = Mock(side_effect=AssertionError("Database use forbidden"))
    loader = Mock(side_effect=AssertionError("Reacquisition forbidden"))
    encoder = Mock(side_effect=AssertionError("Re-embedding forbidden"))
    chunks, cleaned = refresh_service.stage_filing(session, cik, metadata, encoder, loader)
    assert cleaned is None and len(chunks) == 1 and chunks[0] is not legacy
    assert {field: getattr(chunks[0], field) for field in fields} == before
    assert {field: getattr(legacy, field) for field in fields} == before
    assert session.mock_calls == []
    loader.assert_not_called()
    encoder.assert_not_called()
