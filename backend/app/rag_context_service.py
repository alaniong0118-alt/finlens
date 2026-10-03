from typing import Any

from sqlalchemy.orm import Session

from app.filing_search_service import hybrid_search_filing_chunks
from app.evidence_policy import evidence_reason


def build_filing_context(
    session: Session,
    company_cik: str,
    accession_number: str,
    query: str,
    limit: int = 5,
) -> dict[str, Any]:
    """Build bounded, citation-aware context from one filing's stored chunks."""
    if not 1 <= limit <= 50:
        raise ValueError("limit must be between 1 and 50.")

    ranked_chunks = hybrid_search_filing_chunks(
        session,
        company_cik,
        accession_number,
        query,
        50,
    )

    citations: list[dict[str, Any]] = []
    source_blocks: list[str] = []
    seen_chunk_keys: set[tuple[str, str]] = set()
    seen_texts: set[str] = set()

    for result in ranked_chunks:
        chunk = result.chunk
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
        citations.append(citation)

        # Indent every source line so the block-scalar boundary remains clear
        # even if the filing text contains bracketed source-like strings.
        indented_text = "\n".join(
            f"  {line}" for line in chunk.text.splitlines()
        )
        source_blocks.append(
            f"[SOURCE {citation_id}]\n"
            f"chunk_id: {chunk.chunk_id}\n"
            f"accession_number: {chunk.accession_number}\n"
            f"form: {chunk.form}\n"
            f"similarity: {similarity:.6f}\n"
            "text: |-\n"
            f"{indented_text}\n"
            f"[END SOURCE {citation_id}]"
        )
        if len(citations) == limit:
            break

    return {
        "query": query,
        "context": "\n\n".join(source_blocks),
        "citations": citations,
        "evidence_status": "sufficient" if citations else "insufficient",
    }
