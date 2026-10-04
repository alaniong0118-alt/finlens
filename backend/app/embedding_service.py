from functools import lru_cache
from array import array
import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FilingChunk

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384


def validate_embedding(vector) -> None:
    """Validate the float32 representation stored by pgvector, without changing it."""
    if len(vector) != EMBEDDING_DIMENSION:
        raise ValueError(f"Embedding must have {EMBEDDING_DIMENSION} dimensions.")
    try:
        values = array("f", vector)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Embedding values must be finite float32 numbers.") from exc
    if not all(math.isfinite(value) for value in values):
        raise ValueError("Embedding values must be finite float32 numbers.")
    if math.hypot(*values) <= 0:
        raise ValueError("Embedding norm must be greater than zero.")


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

    try:
        chunks = list(session.scalars(stmt).all())
        embedded_count = 0
        for offset in range(0, len(chunks), batch_size):
            batch = chunks[offset : offset + batch_size]
            vectors = embed_texts([chunk.text for chunk in batch])
            if len(vectors) != len(batch):
                raise ValueError("Encoder output count does not match the chunk batch.")
            # Validate the entire batch before assignment or flush. Existing
            # non-null vectors are excluded by the scoped query above.
            for vector in vectors:
                validate_embedding(vector)
            for chunk, vector in zip(batch, vectors, strict=True):
                chunk.embedding = vector
            session.flush()
            embedded_count += len(batch)

        session.commit()
        return embedded_count
    except BaseException:
        # Also clear flushed, uncommitted batches after an interruption.
        session.rollback()
        raise
