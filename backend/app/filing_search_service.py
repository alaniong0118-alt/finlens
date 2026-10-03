from dataclasses import dataclass
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FilingChunk
from app.embedding_service import embed_texts


# Query-only stop words keep natural questions from diluting term coverage.
QUERY_STOP_WORDS = frozenset(
    "a an the what which how why when where did does do is are was were "
    "has have had of for in on to and or from with about its their this that "
    "please explain describe tell me company apple reported".split()
)


def lexical_query(query: str) -> str:
    """Remove bounded question frames, retaining topic qualifiers and negation.

    Only lexical matching uses this text. Embeddings and the LLM receive the
    original question, including any request for causes rather than just facts.
    """
    normalized = " ".join(re.findall(r"\w+", query.casefold()))
    for pattern in (
        r"(?:what|which) (?:were|are|was|is) (?:the )?(?:main )?drivers? of (.+)",
        r"what drove (.+)",
        r"what (?:was|is|were|are) (?:the )?(.+)",
        r"what (.+) (?:was|were) discussed",
        r"how (?:did|does) (.+) affect (?:the )?business",
    ):
        match = re.fullmatch(pattern, normalized)
        if match:
            return match.group(1)
    return normalized


def lexical_score(text: str, query: str) -> float:
    """0.8 * exact phrase indicator + 0.2 * distinct query term coverage.

    Matching is case-insensitive and token-boundary aware. Punctuation and
    whitespace are normalized; no substring or unbounded frequency boosts.
    """
    text_tokens = re.findall(r"\w+", text.casefold())
    topic = lexical_query(query)
    # SEC statements often label revenue as net sales. Keep every qualifier;
    # these aliases change retrieval wording only, never the model's question.
    variants = {topic, re.sub(r"\brevenues?\b", "net sales", topic)}
    for variant in tuple(variants):
        variants.add(re.sub(r"\b(revenue|net sales) growth\b", r"\1 increased", variant))
    best = 0.0
    for variant in variants:
        query_tokens = variant.split()
        terms = set(query_tokens) - QUERY_STOP_WORDS
        if not terms:
            continue
        coverage = len(terms.intersection(text_tokens)) / len(terms)
        phrase = f" {' '.join(query_tokens)} " in f" {' '.join(text_tokens)} "
        best = max(best, 0.8 * float(phrase) + 0.2 * coverage)
    return best


@dataclass(frozen=True)
class HybridSearchResult:
    chunk: FilingChunk
    semantic_similarity: float
    lexical_score: float
    hybrid_score: float


def rank_hybrid_chunks(
    candidates: list[tuple[FilingChunk, float]], query: str, limit: int,
) -> list[HybridSearchResult]:
    """Rank, then deduplicate; exact phrases outrank purely semantic matches."""
    if not 1 <= limit <= 50:
        raise ValueError("limit must be between 1 and 50")
    ranked = []
    for chunk, similarity in candidates:
        lexical = lexical_score(chunk.text, query)
        similarity = min(1.0, max(0.0, similarity))
        ranked.append(HybridSearchResult(
            chunk, similarity, lexical, lexical + 0.6 * similarity,
        ))
    ranked.sort(key=lambda result: (
        -result.hybrid_score, -result.semantic_similarity,
        result.chunk.chunk_index, result.chunk.id or 0,
    ))
    results = []
    seen_keys = set()
    seen_texts = set()
    for result in ranked:
        key = (result.chunk.accession_number, result.chunk.chunk_id)
        normalized_text = " ".join(result.chunk.text.split())
        if not normalized_text or key in seen_keys or normalized_text in seen_texts:
            continue
        seen_keys.add(key)
        seen_texts.add(normalized_text)
        results.append(result)
        if len(results) == limit:
            break
    return results


def hybrid_search_filing_chunks(
    session: Session, company_cik: str, accession_number: str,
    query: str, limit: int = 5,
) -> list[HybridSearchResult]:
    if not 1 <= limit <= 50:
        raise ValueError("limit must be between 1 and 50")
    if not (set(re.findall(r"\w+", query.casefold())) - QUERY_STOP_WORDS):
        return []
    vector = embed_texts([query.strip()])[0]
    distance = FilingChunk.embedding.cosine_distance(vector)
    # Read the scoped filing, not just the semantic top-k: a strong lexical hit
    # must remain a candidate even with a weak or missing embedding.
    rows = session.execute(select(FilingChunk, distance).where(
        FilingChunk.company_cik == company_cik,
        FilingChunk.accession_number == accession_number,
    )).all()
    candidates = [
        (chunk, 0.0 if value is None else 1.0 - float(value))
        for chunk, value in rows
    ]
    return rank_hybrid_chunks(candidates, query, limit)


def search_filing_chunks(
    session: Session,
    company_cik: str,
    accession_number: str,
    query: str,
    limit: int = 5,
) -> list[FilingChunk]:
    """
    Search filing chunks using simple keyword matching.
    """
    query = query.strip()

    if not query:
        return []

    if limit <= 0:
        raise ValueError(
            "limit must be greater than zero."
        )

    search_terms = [
        term.strip().lower()
        for term in query.split()
        if term.strip()
    ]

    if not search_terms:
        return []

    stmt = (
    select(FilingChunk)
    .where(
        FilingChunk.company_cik == company_cik,
        FilingChunk.accession_number == accession_number,
    )
    )

    chunks = list(
        session.scalars(stmt).all()
    )

    scored = []

    for chunk in chunks:
        text_lower = chunk.text.lower()

        score = sum(
            text_lower.count(term)
            for term in search_terms
        )

        if score > 0:
            scored.append(
                (score, chunk)
            )

    scored.sort(
        key=lambda item: (
            -item[0],
            item[1].chunk_index,
        )
    )

    return [
        chunk
        for _, chunk in scored[:limit]
    ]


def search_filing_chunks_semantic(
    session: Session,
    company_cik: str,
    accession_number: str,
    query: str,
    limit: int = 5,
) -> list[tuple[FilingChunk, float]]:
    """Rank chunks in one filing by pgvector cosine similarity."""
    query = query.strip()
    if not query:
        return []
    if limit <= 0:
        raise ValueError("limit must be greater than zero.")

    query_embedding = embed_texts([query])[0]
    distance = FilingChunk.embedding.cosine_distance(query_embedding)
    stmt = (
        select(FilingChunk, distance.label("distance"))
        .where(
            FilingChunk.company_cik == company_cik,
            FilingChunk.accession_number == accession_number,
            FilingChunk.embedding.is_not(None),
        )
        .order_by(distance)
        .limit(limit)
    )
    return [
        (chunk, max(0.0, 1.0 - float(chunk_distance)))
        for chunk, chunk_distance in session.execute(stmt).all()
    ]
