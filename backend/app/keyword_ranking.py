"""Deterministic keyword arithmetic over caller-bounded detached inputs.

Callers own validation, admission and publication. A rank is not evidence authority.
"""
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class KeywordChunk:
    position: int
    chunk_index: int
    text: str


def keyword_terms(query: str) -> list[str]:
    """Prepare terms before the caller's read, retaining repeated contributions."""
    query = query.strip()
    return [
        term.strip().lower()
        for term in query.split()
        if term.strip()
    ]


def rank_keyword_positions(
    chunks: tuple[KeywordChunk, ...], search_terms: list[str], limit: int = 5,
) -> list[int]:
    """Return original positions; exact score/index ties retain input order."""
    if not search_terms:
        return []
    scored = []
    for chunk in chunks:
        text_lower = chunk.text.lower()
        score = sum(text_lower.count(term) for term in search_terms)
        if score > 0:
            scored.append((score, chunk))
    scored.sort(key=lambda item: (-item[0], item[1].chunk_index))
    return [chunk.position for _, chunk in scored[:limit]]
