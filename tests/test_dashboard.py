"""Tests for the Cobalt dashboard API."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cobalt import Dataset, EvalContext, EvalResult, Evaluator, ExperimentResult
from cobalt.experiment import experiment
from cobalt.storage import results as results_mod


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_results(tmp_path: Path, monkeypatch):
    """Redirect result storage to a temp directory for isolation."""
    monkeypatch.setattr(results_mod, "_RESULTS_DIR", tmp_path)
    return tmp_path


@pytest.fixture()
def client(tmp_results):
    from cobalt.dashboard.server import app
    return TestClient(app)


@pytest.fixture()
async def sample_report(tmp_results):
    """Run a tiny experiment to generate a persisted report."""
    ds = Dataset.from_items([
        {"input": "q1", "expected_output": "a1"},
        {"input": "q2", "expected_output": "a2"},
    ])

    def fn(ctx: EvalContext) -> EvalResult:
        return EvalResult(score=1.0)

    ev = Evaluator(name="exact", type="function", fn=fn)

    async def runner(ctx) -> ExperimentResult:
        return ExperimentResult(output=ctx.item["expected_output"])

    report = await experiment("dashboard-test", ds, runner, evaluators=[ev])
    return report


# ---------------------------------------------------------------------------
# /api/runs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_api_runs_empty(client):
    resp = client.get("/api/runs")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_api_runs_returns_summary(client, sample_report):
    resp = client.get("/api/runs")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "dashboard-test"
    assert data[0]["total_items"] == 2


# ---------------------------------------------------------------------------
# /api/runs/{run_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_api_run_detail(client, sample_report):
    resp = client.get(f"/api/runs/{sample_report.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == sample_report.id
    assert data["name"] == "dashboard-test"
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_api_run_detail_not_found(client):
    resp = client.get("/api/runs/nonexistent-id")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# /api/compare
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_api_compare(client, tmp_results):
    ds = Dataset.from_items([{"input": "x"}])

    def fn1(ctx):
        return EvalResult(score=1.0)

    def fn2(ctx):
        return EvalResult(score=0.5)

    async def runner(ctx):
        return ExperimentResult(output="ok")

    ev1 = Evaluator(name="score", type="function", fn=fn1)
    ev2 = Evaluator(name="score", type="function", fn=fn2)

    r1 = await experiment("exp-a", ds, runner, evaluators=[ev1])
    r2 = await experiment("exp-b", ds, runner, evaluators=[ev2])

    resp = client.get(f"/api/compare?run_id_1={r1.id}&run_id_2={r2.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["run1"]["id"] == r1.id
    assert data["run2"]["id"] == r2.id
    comparison = {c["evaluator"]: c for c in data["comparison"]}
    assert "score" in comparison
    assert comparison["score"]["delta"] == pytest.approx(-0.5, abs=0.01)


@pytest.mark.asyncio
async def test_api_compare_missing_run(client):
    resp = client.get("/api/compare?run_id_1=bad1&run_id_2=bad2")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# SPA catch-all
# ---------------------------------------------------------------------------


def test_spa_serves_html(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "cobalt" in resp.text.lower()
