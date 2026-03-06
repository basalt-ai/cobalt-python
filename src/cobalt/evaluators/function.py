"""Custom function evaluator."""

from __future__ import annotations

import asyncio
import inspect
from typing import Any

from cobalt.evaluator import registry
from cobalt.types import EvalContext, EvalResult


async def _function_handler(
    config: dict[str, Any],
    context: EvalContext,
    **_kwargs: Any,
) -> EvalResult:
    fn = config.get("fn")
    if fn is None:
        raise ValueError("Function evaluator requires a 'fn' key with a callable.")

    # Apply optional context mapping
    ctx_map = config.get("context")
    if ctx_map is not None:
        context = ctx_map(context)

    result = fn(context)
    if inspect.isawaitable(result):
        result = await result
    return result  # type: ignore[return-value]


registry.register("function", _function_handler)
