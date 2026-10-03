from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FilingChunk

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384


@lru_cache(maxsize=1)
def _get_model():
    """Load the encoder once, on first use, to keep API startup lightweight."""
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(MODEL_NAME)
    if model.get_sentence_embedding_dimension() != EMBEDDING_DIMENSION:
        raise RuntimeError(
            f"{MODEL_NAME} must produce {EMBEDDING_DIMENSION}-dimensional vectors."
        )
    return model


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    vectors = _get_model().encode(
        texts,
        batch_size=32,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return vectors.tolist()


def embed_filing_chunks(
    session: Session,
    company_cik: str | None = None,
    accession_number: str | None = None,
    batch_size: int = 32,
) -> int:
    """Embed chunks missing vectors, optionally scoped to one company or filing."""
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than zero.")

    stmt = select(FilingChunk).where(FilingChunk.embedding.is_(None))
    if company_cik is not None:
        stmt = stmt.where(FilingChunk.company_cik == company_cik)
    if accession_number is not None:
        stmt = stmt.where(FilingChunk.accession_number == accession_number)
    stmt = stmt.order_by(FilingChunk.id)

    chunks = list(session.scalars(stmt).all())
    embedded_count = 0
    for offset in range(0, len(chunks), batch_size):
        batch = chunks[offset : offset + batch_size]
        vectors = embed_texts([chunk.text for chunk in batch])
        for chunk, vector in zip(batch, vectors, strict=True):
            chunk.embedding = vector
        session.flush()
        embedded_count += len(batch)

    session.commit()
    return embedded_count
