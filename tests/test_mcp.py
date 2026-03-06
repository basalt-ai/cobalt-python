"""Tests for the Cobalt MCP server — tools, resources, and prompts."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from cobalt import Dataset, EvalContext, EvalResult, Evaluator, ExperimentResult
from cobalt.experiment import experiment
from cobalt.storage import results as results_mod
from cobalt.mcp.server import (
    _server,
    _resource_config,
    _resource_latest_results,
    _resource_experiments,
    _to_dict,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_results(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(results_mod, "_RESULTS_DIR", tmp_path)
    return tmp_path


@pytest.fixture()
async def two_reports(tmp_results):
    """Two experiment reports with different scores."""
    ds = Dataset.from_items([
        {"input": "q1", "expected_output": "a1"},
        {"input": "q2", "expected_output": "a2"},
    ])

    def fn_perfect(ctx: EvalContext) -> EvalResult:
        return EvalResult(score=1.0, reason="perfect")

    def fn_half(ctx: EvalContext) -> EvalResult:
        return EvalResult(score=0.5, reason="half")

    async def runner(ctx) -> ExperimentResult:
        return ExperimentResult(output=ctx.item["expected_output"])

    ev_a = Evaluator(name="accuracy", type="function", fn=fn_perfect)
    ev_b = Evaluator(name="accuracy", type="function", fn=fn_half)

    r1 = await experiment("exp-a", ds, runner, evaluators=[ev_a])
    r2 = await experiment("exp-b", ds, runner, evaluators=[ev_b])
    return r1, r2


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------


def test_resource_config_returns_json():
    raw = _resource_config()
    data = json.loads(raw)
    assert "judge" in data
    assert data["judge"]["api_key"] is None or data["judge"]["api_key"] == "[REDACTED]"
    assert "concurrency" in data
    assert "test_dir" in data


def test_resource_config_redacts_api_key(monkeypatch):
    import cobalt.mcp.server as mcp_mod
    from cobalt.types import CobaltConfig, JudgeConfig
    monkeypatch.setattr(mcp_mod, "load_config", lambda *a, **kw: CobaltConfig(
        judge=JudgeConfig(api_key="sk-supersecret")
    ))
    raw = _resource_config()
    data = json.loads(raw)
    assert "supersecret" not in raw
    assert data["judge"]["api_key"] == "[REDACTED]"


def test_resource_latest_results_empty(tmp_results):
    raw = _resource_latest_results()
    data = json.loads(raw)
    assert data["count"] == 0
    assert data["results"] == []


@pytest.mark.asyncio
async def test_resource_latest_results_populated(tmp_results):
    ds = Dataset.from_items([{"input": "x"}])

    def fn(ctx):
        return EvalResult(score=0.8)

    async def runner(ctx):
        return ExperimentResult(output="ok")

    ev = Evaluator(name="q", type="function", fn=fn)
    await experiment("my-exp", ds, runner, evaluators=[ev])
    await experiment("my-exp", ds, runner, evaluators=[ev])  # second run

    raw = _resource_latest_results()
    data = json.loads(raw)
    # Should have exactly ONE result per experiment name
    assert data["count"] == 1
    assert data["results"][0]["name"] == "my-exp"


def test_resource_experiments_empty_dir(tmp_path, monkeypatch):
    from cobalt import config as cfg_mod
    from cobalt.types import CobaltConfig
    monkeypatch.setattr(cfg_mod, "load_config", lambda *a, **kw: CobaltConfig(
        test_dir=str(tmp_path)
    ))
    raw = _resource_experiments()
    data = json.loads(raw)
    assert data["count"] == 0


# ---------------------------------------------------------------------------
# Tool: cobalt_results
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tool_results_list(tmp_results):
    ds = Dataset.from_items([{"input": "x"}])
    async def runner(ctx): return ExperimentResult(output="y")
    ev = Evaluator(name="q", type="function", fn=lambda ctx: EvalResult(score=1.0))
    await experiment("list-test", ds, runner, evaluators=[ev])

    from cobalt.mcp.server import _tool_results
    result = await _tool_results({"limit": 10})
    data = json.loads(result[0].text)
    assert data["total"] >= 1
    assert data["runs"][0]["name"] == "list-test"


@pytest.mark.asyncio
async def test_tool_results_detail(tmp_results):
    ds = Dataset.from_items([{"input": "x"}])
    async def runner(ctx): return ExperimentResult(output="y")
    ev = Evaluator(name="q", type="function", fn=lambda ctx: EvalResult(score=1.0))
    report = await experiment("detail-test", ds, runner, evaluators=[ev])

    from cobalt.mcp.server import _tool_results
    result = await _tool_results({"run_id": report.id})
    data = json.loads(result[0].text)
    assert data["id"] == report.id
    assert data["name"] == "detail-test"


@pytest.mark.asyncio
async def test_tool_results_not_found():
    from cobalt.mcp.server import _tool_results
    result = await _tool_results({"run_id": "nonexistent-xyz"})
    data = json.loads(result[0].text)
    assert "error" in data


# ---------------------------------------------------------------------------
# Tool: cobalt_compare
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tool_compare_basic(two_reports):
    r1, r2 = two_reports
    from cobalt.mcp.server import _tool_compare
    result = await _tool_compare({"run_a": r1.id, "run_b": r2.id})
    data = json.loads(result[0].text)
    assert data["run_a"]["id"] == r1.id
    assert data["run_b"]["id"] == r2.id
    # r1=1.0, r2=0.5 → regression
    assert len(data["regressions"]) == 1
    assert data["regressions"][0]["evaluator"] == "accuracy"
    assert data["regressions"][0]["diff"] == pytest.approx(-0.5, abs=0.01)


@pytest.mark.asyncio
async def test_tool_compare_not_found():
    from cobalt.mcp.server import _tool_compare
    result = await _tool_compare({"run_a": "bad1", "run_b": "bad2"})
    data = json.loads(result[0].text)
    assert "error" in data


# ---------------------------------------------------------------------------
# Prompts (structure only — no LLM calls)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prompt_improve_agent_no_run_id():
    result = await get_prompt("improve-agent", {})
    assert result.messages
    assert "improve" in result.messages[0].content.text.lower()


@pytest.mark.asyncio
async def test_prompt_generate_tests():
    result = await get_prompt("generate-tests", {"experiment_file": "nonexistent.cobalt.py"})
    assert result.messages
    assert "coverage" in result.messages[0].content.text.lower() or "test" in result.messages[0].content.text.lower()


@pytest.mark.asyncio
async def test_prompt_regression_check_structure():
    result = await get_prompt("regression-check", {"baseline_run_id": "a", "current_run_id": "b"})
    assert result.messages
    assert "regression" in result.messages[0].content.text.lower()


@pytest.mark.asyncio
async def test_prompt_unknown_raises():
    with pytest.raises(ValueError, match="Unknown prompt"):
        await get_prompt("nonexistent-prompt", {})


# ---------------------------------------------------------------------------
# Helper: invoke server prompt handler directly
# ---------------------------------------------------------------------------


async def get_prompt(name: str, arguments: dict):
    """Call the server's get_prompt handler directly."""
    from cobalt.mcp.server import get_prompt as _get_prompt
    return await _get_prompt(name, arguments)
