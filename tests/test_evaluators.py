"""Tests for Evaluator."""

from __future__ import annotations

import pytest
import pytest_asyncio

from cobalt import EvalContext, EvalResult, Evaluator


# ---------------------------------------------------------------------------
# Function evaluator — sync
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_function_evaluator_sync():
    def my_fn(ctx: EvalContext) -> EvalResult:
        return EvalResult(score=1.0, reason="ok")

    ev = Evaluator(name="test", type="function", fn=my_fn)
    ctx = EvalContext(item={"input": "hi"}, output="hi")
    result = await ev.evaluate(ctx)
    assert result.score == 1.0
    assert result.reason == "ok"


# ---------------------------------------------------------------------------
# Function evaluator — async
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_function_evaluator_async():
    async def my_fn(ctx: EvalContext) -> EvalResult:
        return EvalResult(score=0.5, reason="half")

    ev = Evaluator(name="async-test", type="function", fn=my_fn)
    ctx = EvalContext(item={}, output="output")
    result = await ev.evaluate(ctx)
    assert result.score == 0.5


# ---------------------------------------------------------------------------
# Function evaluator — unknown type raises
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unknown_evaluator_type_raises():
    ev = Evaluator(name="bad", type="nonexistent")
    ctx = EvalContext(item={}, output="x")
    with pytest.raises(ValueError, match="Unknown evaluator type"):
        await ev.evaluate(ctx)


# ---------------------------------------------------------------------------
# Similarity evaluator (TF-IDF, no API call needed)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_similarity_identical_strings():
    ev = Evaluator(name="sim", type="similarity", field="expected", threshold=0.5)
    ctx = EvalContext(item={"expected": "hello world"}, output="hello world")
    result = await ev.evaluate(ctx)
    assert result.score == 1.0


@pytest.mark.asyncio
async def test_similarity_missing_field():
    ev = Evaluator(name="sim", type="similarity", field="missing_field", threshold=0.5)
    ctx = EvalContext(item={}, output="hello")
    result = await ev.evaluate(ctx)
    assert result.score == 0.0
    assert "not found" in (result.reason or "")


# ---------------------------------------------------------------------------
# Evaluator requires name
# ---------------------------------------------------------------------------


def test_evaluator_requires_name():
    with pytest.raises(ValueError, match="name"):
        Evaluator(type="function")
