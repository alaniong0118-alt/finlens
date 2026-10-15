from typing import Any
import json

from sqlalchemy.orm import Session

from app.filing_search_service import hybrid_search_filing_chunks, hybrid_search_company_chunks
from app.evidence_policy import evidence_reason
from app.freshness_service import (
    published_company_chunks, valid_document_filename,
    validate_research_input, validate_research_chunks,
)

MAX_COMPANY_CONTEXT_CHARS = 24000


def build_filing_context(
    session: Session,
    company_cik: str,
    accession_number: str,
    query: str,
    limit: int = 5,
) -> dict[str, Any]:
    """Build bounded, citation-aware context from one filing's stored chunks."""
    validate_research_input(query, limit)

    ranked_chunks = hybrid_search_filing_chunks(
        session,
        company_cik,
        accession_number,
        query,
        50,
    )
    return _build_context(ranked_chunks, query, limit)


def build_company_context(session, company_cik, query, limit=5):
    validate_research_input(query, limit)
    chunks, metadata = published_company_chunks(session, company_cik)
    ranked = hybrid_search_company_chunks(chunks, query)
    return {**_build_context(ranked, query, limit, company_wide=True), **metadata,
            "retrieval_scope": "company", "company_cik": company_cik}


def _build_context(ranked_chunks, query, limit, *, company_wide=False):
    validate_research_input(query, limit)
    validate_research_chunks([result.chunk for result in ranked_chunks])

    citations: list[dict[str, Any]] = []
    source_blocks: list[str] = []
    seen_chunk_keys: set[tuple[str, str]] = set()
    seen_texts: set[str] = set()

    for result in ranked_chunks:
        chunk = result.chunk
        if company_wide and not valid_document_filename(chunk.filename):
            continue
        similarity = result.semantic_similarity
        reason = evidence_reason(similarity, result.lexical_score)
        if reason == "insufficient":
            continue
        chunk_key = (chunk.accession_number, chunk.chunk_id)
        normalized_text = " ".join(chunk.text.split())
        if chunk_key in seen_chunk_keys or normalized_text in seen_texts:
            continue

        seen_chunk_keys.add(chunk_key)
        seen_texts.add(normalized_text)
        citation_id = f"source_{len(citations) + 1}"
        citation = {
            "citation_id": citation_id,
            "chunk_id": chunk.chunk_id,
            "accession_number": chunk.accession_number,
            "form": chunk.form,
            "filed": chunk.filed,
            "filename": chunk.filename,
            "start_char": chunk.start_char,
            "end_char": chunk.end_char,
            "sec_url": chunk.sec_url,
            "similarity": similarity,
            "semantic_similarity": similarity,
            "lexical_score": result.lexical_score,
            "hybrid_score": result.hybrid_score,
            "evidence_reason": reason,
        }
        if company_wide:
            citation["company_cik"] = chunk.company_cik

        # Indent every source line so the block-scalar boundary remains clear
        # even if the filing text contains bracketed source-like strings.
        lines = chunk.text.split("\n") if company_wide else chunk.text.splitlines()
        indented_text = "\n".join(f"  {line}" for line in lines)
        headers = (
            f"chunk_id: {chunk.chunk_id}\n"
            f"accession_number: {chunk.accession_number}\n"
            f"form: {chunk.form}\n"
            f"similarity: {similarity:.6f}\n"
        )
        if company_wide:
            # JSON stays on one physical line even for hostile metadata. It cannot
            # manufacture text: |- or SOURCE boundaries; body text is separate.
            identity = {key: citation[key] for key in ("company_cik", "accession_number", "filename",
                        "chunk_id", "form", "filed", "start_char", "end_char")}
            headers = "metadata: " + json.dumps(identity, ensure_ascii=True, default=str) + "\n"
        source_block = (
            f"[SOURCE {citation_id}]\n"
            f"{headers}"
            "text: |-\n"
            f"{indented_text}\n"
            f"[END SOURCE {citation_id}]"
        )
        if len("\n\n".join([*source_blocks, source_block])) > MAX_COMPANY_CONTEXT_CHARS:
            break
        citations.append(citation)
        source_blocks.append(source_block)
        if len(citations) == limit:
            break

    return {
        "query": query,
        "context": "\n\n".join(source_blocks),
        "citations": citations,
        "evidence_status": "sufficient" if citations else "insufficient",
    }
