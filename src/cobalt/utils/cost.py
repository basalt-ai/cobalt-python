"""LLM cost estimation (USD per 1M tokens)."""

from __future__ import annotations

# Prices per 1M tokens [input, output] in USD — best-effort, update as needed.
_PRICES: dict[str, tuple[float, float]] = {
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-4": (30.00, 60.00),
    "gpt-3.5-turbo": (0.50, 1.50),
    "claude-3-5-sonnet": (3.00, 15.00),
    "claude-3-5-haiku": (0.80, 4.00),
    "claude-3-opus": (15.00, 75.00),
    "claude-3-haiku": (0.25, 1.25),
}


def estimate_cost(tokens: dict[str, int], model: str) -> float | None:
    """Return estimated USD cost given token counts and model name.

    *tokens* should contain ``"input"`` and ``"output"`` keys.
    Returns ``None`` if the model is unknown.
    """
    # Fuzzy-match: strip version suffixes to find a price entry.
    matched: tuple[float, float] | None = None
    for key, price in _PRICES.items():
        if model.startswith(key) or key in model:
            matched = price
            break

    if matched is None:
        return None

    input_cost = tokens.get("input", 0) * matched[0] / 1_000_000
    output_cost = tokens.get("output", 0) * matched[1] / 1_000_000
    return input_cost + output_cost
