"""Pure validation of stored embedding vectors; no encoder dependencies."""
from array import array
import math


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
