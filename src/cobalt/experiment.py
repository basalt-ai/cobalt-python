"""Core experiment() runner."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from secrets import token_hex
from typing import Any, Awaitable, Callable

from cobalt.config import get_api_key, load_config
from cobalt.dataset import Dataset
from cobalt.evaluator import Evaluator
from cobalt.storage.db import HistoryDB
from cobalt.storage.results import save_result
from cobalt.types import (
    CIResult,
    EvalContext,
    ExperimentReport,
    ExperimentResult,
    ExperimentSummary,
    ItemEvaluation,
    ItemResult,
    RunnerContext,
    ThresholdConfig,
    ThresholdViolation,
)
from cobalt.utils import stats as stats_mod

# Register all built-in evaluator handlers
import cobalt.evaluators  # noqa: F401


RunnerFn = Callable[[RunnerContext], Awaitable[ExperimentResult]]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def experiment(
    name: str,
    dataset: Dataset,  # type: ignore[type-arg]
    runner: RunnerFn,
    *,
    evaluators: list[Evaluator | dict[str, Any]],
    runs: int = 1,
    concurrency: int | None = None,
    timeout: float | None = None,
    tags: list[str] | None = None,
    thresholds: ThresholdConfig | None = None,
) -> ExperimentReport:
    """Run *runner* against every item in *dataset*, evaluate, report.

    Parameters
    ----------
    name:
        Experiment name (used for storage and display).
    dataset:
        :class:`~cobalt.dataset.Dataset` of test items.
    runner:
        Async callable ``(RunnerContext) -> ExperimentResult``.
    evaluators:
        List of :class:`~cobalt.evaluator.Evaluator` instances or config dicts.
    runs:
        How many times to run each item (default ``1``).
    concurrency:
        Max concurrent item evaluations (overrides config).
    timeout:
        Per-item timeout in seconds (overrides config).
    tags:
        Free-form labels attached to the run.
    thresholds:
        CI threshold configuration (only validated if provided).
    """
    config = load_config()
    _concurrency = concurrency or config.concurrency
    _timeout = timeout or config.timeout
    _tags = tags or []
    api_key = get_api_key(config)
    judge_model = config.judge.model

    # Normalise evaluators
    eval_instances = [
        ev if isinstance(ev, Evaluator) else Evaluator(ev)
        for ev in evaluators
    ]

    items = dataset.items()
    if not items:
        raise ValueError("Dataset is empty.")

    semaphore = asyncio.Semaphore(_concurrency)
    start_time = time.monotonic()

    # Run all items concurrently
    tasks = [
        _run_item(
            item,
            idx,
            runner,
            eval_instances,
            semaphore,
            _timeout,
            api_key,
            judge_model,
            runs,
        )
        for idx, item in enumerate(items)
    ]
    results: list[ItemResult] = await asyncio.gather(*tasks)

    total_duration_ms = (time.monotonic() - start_time) * 1000
    summary = _build_summary(results, total_duration_ms)

    run_id = token_hex(6)
    report = ExperimentReport(
        id=run_id,
        name=name,
        timestamp=datetime.now(tz=timezone.utc).isoformat(),
        tags=_tags,
        config={
            "runs": runs,
            "concurrency": _concurrency,
            "timeout": _timeout,
            "evaluators": [e.name for e in eval_instances],
        },
        summary=summary,
        items=results,
    )

    # CI threshold validation
    if thresholds:
        ci = _validate_thresholds(report, thresholds)
        report_dict = {  # attach informally; ExperimentReport has no ci_status field
            "ci_status": ci,
            **report.__dict__,
        }

    # Persist
    try:
        save_result(report)
    except Exception:
        pass
    try:
        with HistoryDB() as db:
            db.insert_run(report)
    except Exception:
        pass

    # CLI reporter — print summary to stdout
    _print_summary(report)

    return report


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _run_item(
    item: Any,
    idx: int,
    runner: RunnerFn,
    evaluators: list[Evaluator],
    semaphore: asyncio.Semaphore,
    timeout: float,
    api_key: str | None,
    judge_model: str,
    runs: int,
) -> ItemResult:
    async with semaphore:
        ctx = RunnerContext(item=item, index=idx)
        start = time.monotonic()
        error: str | None = None
        output = ExperimentResult(output="")

        try:
            result = await asyncio.wait_for(runner(ctx), timeout=timeout)
            output = result
        except asyncio.TimeoutError:
            error = f"Timeout after {timeout}s"
        except Exception as exc:
            error = str(exc)

        latency_ms = (time.monotonic() - start) * 1000

        evaluations: dict[str, ItemEvaluation] = {}
        if not error:
            eval_ctx = EvalContext(
                item=item,
                output=output.output,
                metadata=output.metadata,
            )
            for ev in evaluators:
                try:
                    result_ev = await ev.evaluate(
                        eval_ctx, api_key=api_key, model=judge_model
                    )
                    evaluations[ev.name] = ItemEvaluation(
                        score=result_ev.score,
                        reason=result_ev.reason,
                        chain_of_thought=result_ev.chain_of_thought,
                    )
                except Exception as exc:
                    evaluations[ev.name] = ItemEvaluation(
                        score=0.0, reason=f"Evaluator error: {exc}"
                    )

        return ItemResult(
            index=idx,
            input=item,
            output=output,
            latency_ms=latency_ms,
            evaluations=evaluations,
            error=error,
        )


def _build_summary(results: list[ItemResult], total_duration_ms: float) -> ExperimentSummary:
    total = len(results)
    avg_latency = sum(r.latency_ms for r in results) / total if total else 0.0

    scores_by_evaluator: dict[str, list[float]] = {}
    for result in results:
        for name, ev in result.evaluations.items():
            scores_by_evaluator.setdefault(name, []).append(ev.score)

    score_stats = {name: stats_mod.calculate(scores) for name, scores in scores_by_evaluator.items()}

    return ExperimentSummary(
        total_items=total,
        total_duration_ms=total_duration_ms,
        avg_latency_ms=avg_latency,
        scores=score_stats,
    )


def _print_summary(report: ExperimentReport) -> None:
    try:
        from rich.console import Console
        from rich.table import Table

        console = Console()
        console.print(f"\n[bold cyan]Experiment:[/bold cyan] {report.name}  [dim]{report.id}[/dim]")
        console.print(
            f"[dim]Items: {report.summary.total_items} | "
            f"Duration: {report.summary.total_duration_ms:.0f}ms | "
            f"Avg latency: {report.summary.avg_latency_ms:.0f}ms[/dim]"
        )

        if report.summary.scores:
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Evaluator")
            table.add_column("Avg", justify="right")
            table.add_column("Min", justify="right")
            table.add_column("Max", justify="right")
            table.add_column("P95", justify="right")

            for name, s in report.summary.scores.items():
                color = "green" if s.avg >= 0.8 else ("yellow" if s.avg >= 0.5 else "red")
                table.add_row(
                    name,
                    f"[{color}]{s.avg:.2f}[/{color}]",
                    f"{s.min:.2f}",
                    f"{s.max:.2f}",
                    f"{s.p95:.2f}",
                )
            console.print(table)
    except Exception:
        # Fallback if rich isn't installed
        print(f"\nExperiment: {report.name} ({report.id})")
        print(f"Items: {report.summary.total_items}")
        for name, s in report.summary.scores.items():
            print(f"  {name}: avg={s.avg:.2f} min={s.min:.2f} max={s.max:.2f}")


def _validate_thresholds(report: ExperimentReport, thresholds: ThresholdConfig) -> CIResult:
    violations: list[ThresholdViolation] = []

    def check(category: str, metric: str, expected: float, actual: float) -> None:
        if actual < expected:
            violations.append(
                ThresholdViolation(
                    category=category,
                    metric=metric,
                    expected=expected,
                    actual=actual,
                    message=f"{category}.{metric}: expected >= {expected:.3f}, got {actual:.3f}",
                )
            )

    # Global score thresholds
    if thresholds.score:
        for name, s in report.summary.scores.items():
            t = thresholds.score
            if t.avg is not None:
                check(name, "avg", t.avg, s.avg)
            if t.p95 is not None:
                check(name, "p95", t.p95, s.p95)
            if t.min is not None:
                check(name, "min", t.min, s.min)

    # Per-evaluator thresholds
    for ev_name, t in (thresholds.evaluators or {}).items():
        s = report.summary.scores.get(ev_name)
        if s is None:
            continue
        if t.avg is not None:
            check(ev_name, "avg", t.avg, s.avg)
        if t.p95 is not None:
            check(ev_name, "p95", t.p95, s.p95)
        if t.min is not None:
            check(ev_name, "min", t.min, s.min)

    passed = len(violations) == 0
    summary = "All thresholds passed." if passed else f"{len(violations)} threshold(s) violated."
    return CIResult(passed=passed, violations=violations, summary=summary)
