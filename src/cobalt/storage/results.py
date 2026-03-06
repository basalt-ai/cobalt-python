"""JSON result persistence for experiment reports."""

from __future__ import annotations

import dataclasses
import json
import re
from pathlib import Path
from typing import Any

from cobalt.types import ExperimentReport, ExperimentSummary, ItemResult, ItemEvaluation, ExperimentResult, ResultSummary, ScoreStats

_RESULTS_DIR = Path.home() / ".cobalt" / "results"


def _dataclass_to_dict(obj: Any) -> Any:
    """Recursively convert dataclasses to dicts."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: _dataclass_to_dict(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, list):
        return [_dataclass_to_dict(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _dataclass_to_dict(v) for k, v in obj.items()}
    return obj


def _safe_name(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "-", name)[:64]


def save_result(report: ExperimentReport, results_dir: Path | None = None) -> Path:
    """Persist *report* as JSON and return the file path."""
    directory = results_dir or _RESULTS_DIR
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"{_safe_name(report.name)}-{report.id}.json"
    path = directory / filename
    path.write_text(json.dumps(_dataclass_to_dict(report), indent=2), encoding="utf-8")
    return path


def load_result(run_id: str, results_dir: Path | None = None) -> ExperimentReport | None:
    """Load a report by run ID.  Returns *None* if not found."""
    directory = results_dir or _RESULTS_DIR
    matches = list(directory.glob(f"*-{run_id}.json"))
    if not matches:
        return None
    raw = json.loads(matches[0].read_text(encoding="utf-8"))
    return _dict_to_report(raw)


def list_results(
    experiment: str | None = None,
    limit: int = 50,
    results_dir: Path | None = None,
) -> list[ResultSummary]:
    directory = results_dir or _RESULTS_DIR
    if not directory.exists():
        return []
    files = sorted(directory.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    summaries: list[ResultSummary] = []
    for f in files:
        try:
            raw: dict[str, Any] = json.loads(f.read_text(encoding="utf-8"))
            if experiment and raw.get("name") != experiment:
                continue
            summaries.append(
                ResultSummary(
                    id=raw["id"],
                    name=raw["name"],
                    timestamp=raw["timestamp"],
                    tags=raw.get("tags", []),
                    total_items=raw["summary"]["total_items"],
                    duration_ms=raw["summary"]["total_duration_ms"],
                    avg_scores={k: v["avg"] for k, v in raw["summary"].get("scores", {}).items()},
                )
            )
            if len(summaries) >= limit:
                break
        except Exception:
            continue
    return summaries


# ---------------------------------------------------------------------------
# Deserialization helpers
# ---------------------------------------------------------------------------


def _dict_to_report(raw: dict[str, Any]) -> ExperimentReport:
    summary_raw = raw["summary"]
    scores = {
        name: ScoreStats(**stats) for name, stats in summary_raw.get("scores", {}).items()
    }
    summary = ExperimentSummary(
        total_items=summary_raw["total_items"],
        total_duration_ms=summary_raw["total_duration_ms"],
        avg_latency_ms=summary_raw["avg_latency_ms"],
        total_tokens=summary_raw.get("total_tokens"),
        estimated_cost=summary_raw.get("estimated_cost"),
        scores=scores,
    )
    items = [_dict_to_item(i) for i in raw.get("items", [])]
    return ExperimentReport(
        id=raw["id"],
        name=raw["name"],
        timestamp=raw["timestamp"],
        tags=raw.get("tags", []),
        config=raw.get("config", {}),
        summary=summary,
        items=items,
    )


def _dict_to_item(raw: dict[str, Any]) -> ItemResult:
    evaluations = {
        name: ItemEvaluation(**ev) for name, ev in raw.get("evaluations", {}).items()
    }
    output_raw = raw.get("output", {})
    output = ExperimentResult(
        output=output_raw.get("output", ""),
        metadata=output_raw.get("metadata", {}),
    )
    return ItemResult(
        index=raw["index"],
        input=raw.get("input", {}),
        output=output,
        latency_ms=raw.get("latency_ms", 0.0),
        evaluations=evaluations,
        error=raw.get("error"),
    )
