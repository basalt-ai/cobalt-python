"""Evaluator class and global registry."""

from __future__ import annotations

import asyncio
import inspect
from typing import Any, Awaitable, Callable

from cobalt.types import EvalContext, EvalResult


EvalHandler = Callable[..., EvalResult | Awaitable[EvalResult]]


class EvaluatorRegistry:
    """Singleton registry mapping type names to async handler functions."""

    def __init__(self) -> None:
        self._handlers: dict[str, EvalHandler] = {}

    def register(self, type_name: str, handler: EvalHandler) -> None:
        self._handlers[type_name] = handler

    async def evaluate(
        self, config: dict[str, Any], context: EvalContext, **kwargs: Any
    ) -> EvalResult:
        evaluator_type = config.get("type", "function")
        handler = self._handlers.get(evaluator_type)
        if handler is None:
            raise ValueError(
                f"Unknown evaluator type: '{evaluator_type}'. "
                f"Registered types: {list(self._handlers)}"
            )
        result = handler(config, context, **kwargs)
        if inspect.isawaitable(result):
            return await result
        return result  # type: ignore[return-value]


# Module-level singleton — evaluator modules import this and call register()
registry = EvaluatorRegistry()


class Evaluator:
    """Thin wrapper around an evaluator config dict.

    Accepts either a plain dict or keyword arguments matching the
    evaluator config fields (``name``, ``type``, ``fn``, ``prompt``, …).

    Example::

        ev = Evaluator(name="exact-match", type="function", fn=my_fn)
        result = await ev.evaluate(context)
    """

    def __init__(self, config: dict[str, Any] | None = None, **kwargs: Any) -> None:
        if config is None:
            config = {}
        self._config: dict[str, Any] = {**config, **kwargs}
        if "name" not in self._config:
            raise ValueError("Evaluator requires a 'name' field.")

    @property
    def name(self) -> str:
        return self._config["name"]

    @property
    def evaluator_type(self) -> str:
        return self._config.get("type", "function")

    async def evaluate(
        self,
        context: EvalContext,
        *,
        api_key: str | None = None,
        model: str | None = None,
    ) -> EvalResult:
        return await registry.evaluate(
            self._config, context, api_key=api_key, model=model
        )

    def __repr__(self) -> str:
        return f"Evaluator(name={self.name!r}, type={self.evaluator_type!r})"
