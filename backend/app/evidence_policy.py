import math


def evidence_reason(semantic_similarity: float, lexical_score: float) -> str:
    """Heuristics for this encoder, not calibrated confidence probabilities."""
    if not all(math.isfinite(value) for value in (semantic_similarity, lexical_score)):
        return "insufficient"
    if not (0 <= semantic_similarity <= 1 and 0 <= lexical_score <= 1):
        return "insufficient"
    if lexical_score >= 0.8:
        return "strong_lexical"
    # Mid-range MiniLM similarity alone can match company/report boilerplate
    # for an unrelated topic. Require lexical support below the stronger .60 bar.
    if semantic_similarity >= 0.60 or (semantic_similarity >= 0.40 and lexical_score >= 0.10):
        return "strong_semantic"
    if lexical_score >= 0.2 and semantic_similarity >= 0.25:
        return "combined"
    return "insufficient"
