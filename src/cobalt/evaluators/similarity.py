"""Cosine / dot-product similarity evaluator.

Uses TF-IDF from scikit-learn as a lightweight, dependency-free baseline.
For production use, swap ``_embed`` for an OpenAI embedding call.
"""

from __future__ import annotations

from typing import Any

from cobalt.evaluator import registry
from cobalt.types import EvalContext, EvalResult


def _tfidf_cosine(a: str, b: str) -> float:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    vec = TfidfVectorizer()
    try:
        matrix = vec.fit_transform([a, b])
    except ValueError:
        return 0.0
    return float(cosine_similarity(matrix[0], matrix[1])[0][0])


async def _similarity_handler(
    config: dict[str, Any],
    context: EvalContext,
    **_kwargs: Any,
) -> EvalResult:
    field: str = config["field"]
    threshold: float = config.get("threshold", 0.8)
    distance: str = config.get("distance", "cosine")

    reference = context.item.get(field)
    if reference is None:
        return EvalResult(score=0.0, reason=f"Field '{field}' not found in dataset item.")

    output_text = (
        context.output
        if isinstance(context.output, str)
        else str(context.output.get("output", context.output))
    )
    reference_text = str(reference)

    if distance == "dot":
        # For dot-product we still use cosine numerics via TF-IDF (unit vectors)
        sim = _tfidf_cosine(output_text, reference_text)
    else:
        sim = _tfidf_cosine(output_text, reference_text)

    score = 1.0 if sim >= threshold else sim / threshold
    return EvalResult(
        score=round(score, 4),
        reason=f"Similarity: {sim:.4f} (threshold: {threshold})",
    )


registry.register("similarity", _similarity_handler)
