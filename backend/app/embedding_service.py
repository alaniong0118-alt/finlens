from app.release_policy import development_only
from functools import lru_cache
from array import array
import math
from json import JSONDecodeError

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FilingChunk
from app.config import server_profile

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384


class EncoderDependencyError(RuntimeError):
    """Missing dependencies/cache, unreadable artifacts or incompatible model.

    Programming errors (including generic ValueError) are intentionally outside
    this boundary. Public HTTP handling never returns underlying diagnostics.
    """


def _encoder_unavailable():
    return EncoderDependencyError("The query encoder dependency is unavailable.")


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
    try:
        return _load_model()
    except (ImportError, OSError, JSONDecodeError) as exc:
        raise _encoder_unavailable() from exc


def _load_model():
    if server_profile().name == "sec_readonly":
        # Resolve a local snapshot without a hub request. Passing the local path
        # and local_files_only also constrains nested tokenizer/model loaders.
        from pathlib import Path
        from huggingface_hub import try_to_load_from_cache
        cached = try_to_load_from_cache(MODEL_NAME, "modules.json")
        if not isinstance(cached, str) or not Path(cached).is_file():
            raise _encoder_unavailable()
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(str(Path(cached).parent), local_files_only=True)
    else:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(MODEL_NAME)
    if model.get_sentence_embedding_dimension() != EMBEDDING_DIMENSION:
        raise _encoder_unavailable()
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


@development_only
def embed_filing_chunks(
    session: Session,
    company_cik: str | None = None,
    accession_number: str | None = None,
    batch_size: int = 32,
) -> int:
    from sqlalchemy.orm import sessionmaker
    from app.refresh_service import coordinator
    with coordinator(sessionmaker(bind=session.get_bind())):
        return _embed_filing_chunks(session, company_cik, accession_number, batch_size)


@development_only
def _embed_filing_chunks(session, company_cik=None, accession_number=None, batch_size=32):
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

        from app.refresh_service import register_complete_filings
        register_complete_filings(session, company_cik, accession_number)
        session.commit()
        return embedded_count
    except BaseException:
        # Also clear flushed, uncommitted batches after an interruption.
        session.rollback()
        raise
