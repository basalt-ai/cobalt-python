"""Tests for the experiment() runner."""

from __future__ import annotations

import asyncio

import pytest

from cobalt import Dataset, EvalContext, EvalResult, Evaluator, ExperimentResult
from cobalt.experiment import experiment


def _make_dataset(n: int = 3) -> Dataset:
    return Dataset.from_items([{"input": f"item-{i}", "expected_output": f"out-{i}"} for i in range(n)])


async def _passthrough_runner(ctx) -> ExperimentResult:
    return ExperimentResult(output=ctx.item["expected_output"])


def _exact_match_evaluator() -> Evaluator:
    def fn(ctx: EvalContext) -> EvalResult:
        expected = ctx.item.get("expected_output", "")
        score = 1.0 if str(expected) == str(ctx.output) else 0.0
        return EvalResult(score=score)

    return Evaluator(name="exact-match", type="function", fn=fn)


# ---------------------------------------------------------------------------
# Basic run
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_experiment_basic():
    ds = _make_dataset(3)
    report = await experiment(
        "test-basic",
        ds,
        _passthrough_runner,
        evaluators=[_exact_match_evaluator()],
    )

    assert report.name == "test-basic"
    assert len(report.items) == 3
    assert "exact-match" in report.summary.scores
    assert abs(report.summary.scores["exact-match"].avg - 1.0) < 0.01


# ---------------------------------------------------------------------------
# All fail
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_experiment_all_fail():
    ds = _make_dataset(2)

    async def bad_runner(ctx) -> ExperimentResult:
        return ExperimentResult(output="wrong answer")

    report = await experiment(
        "test-fail",
        ds,
        bad_runner,
        evaluators=[_exact_match_evaluator()],
    )
    assert report.summary.scores["exact-match"].avg == 0.0


# ---------------------------------------------------------------------------
# Empty dataset raises
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_experiment_empty_dataset_raises():
    ds = Dataset.from_items([])
    with pytest.raises(ValueError, match="empty"):
        await experiment("test-empty", ds, _passthrough_runner, evaluators=[])


# ---------------------------------------------------------------------------
# Timeout
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_experiment_timeout():
    ds = _make_dataset(1)

    async def slow_runner(ctx) -> ExperimentResult:
        await asyncio.sleep(10)
        return ExperimentResult(output="late")

    report = await experiment(
        "test-timeout",
        ds,
        slow_runner,
        evaluators=[],
        timeout=0.01,
    )
    assert report.items[0].error is not None
    assert "Timeout" in report.items[0].error


# ---------------------------------------------------------------------------
# Report structure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_experiment_report_structure():
    ds = _make_dataset(2)
    report = await experiment(
        "test-structure",
        ds,
        _passthrough_runner,
        evaluators=[_exact_match_evaluator()],
        tags=["smoke"],
    )

    assert report.id  # non-empty string
    assert report.timestamp  # ISO string
    assert report.tags == ["smoke"]
    assert report.summary.total_items == 2
    assert report.summary.total_duration_ms >= 0
    assert len(report.items) == 2
    for item in report.items:
        assert "exact-match" in item.evaluations
        assert 0.0 <= item.evaluations["exact-match"].score <= 1.0
