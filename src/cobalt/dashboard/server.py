"""Cobalt local dashboard — FastAPI backend."""

from __future__ import annotations

import dataclasses
import json
import webbrowser
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from cobalt.storage.db import HistoryDB
from cobalt.storage.results import _RESULTS_DIR, load_result, list_results

_STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Cobalt Dashboard", docs_url=None, redoc_url=None)


def _to_json(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: _to_json(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, list):
        return [_to_json(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _to_json(v) for k, v in obj.items()}
    return obj


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------


@app.get("/api/runs")
def api_runs(experiment: str | None = None, limit: int = 100):
    """List recent runs."""
    summaries = list_results(experiment=experiment, limit=limit)
    return [_to_json(s) for s in summaries]


@app.get("/api/runs/{run_id}")
def api_run_detail(run_id: str):
    """Full report for a single run."""
    report = load_result(run_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    return _to_json(report)


@app.get("/api/compare")
def api_compare(run_id_1: str, run_id_2: str):
    """Compare two runs."""
    r1 = load_result(run_id_1)
    r2 = load_result(run_id_2)
    if r1 is None:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id_1}")
    if r2 is None:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id_2}")

    all_evals = sorted(set(list(r1.summary.scores.keys()) + list(r2.summary.scores.keys())))
    comparison = []
    for name in all_evals:
        s1 = r1.summary.scores.get(name)
        s2 = r2.summary.scores.get(name)
        comparison.append(
            {
                "evaluator": name,
                "run1": _to_json(s1) if s1 else None,
                "run2": _to_json(s2) if s2 else None,
                "delta": round(s2.avg - s1.avg, 4) if s1 and s2 else None,
            }
        )

    return {
        "run1": _to_json(r1),
        "run2": _to_json(r2),
        "comparison": comparison,
    }


# ---------------------------------------------------------------------------
# Static files + SPA catch-all
# ---------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
@app.get("/{path:path}", response_class=HTMLResponse)
def spa(path: str = ""):
    index = _STATIC_DIR / "index.html"
    if not index.exists():
        return HTMLResponse("<h1>Dashboard static files not found</h1>", status_code=500)
    return HTMLResponse(index.read_text(encoding="utf-8"))
