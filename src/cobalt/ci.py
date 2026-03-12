"""CI reporting — GitHub PR comments and threshold validation."""

from __future__ import annotations

import os
import json
import subprocess
from typing import Any

from cobalt.types import ExperimentReport, ThresholdConfig, ThresholdMetric


def validate_and_report(reports: list[ExperimentReport]) -> bool:
    """Validate thresholds and post GitHub PR comment if in CI.

    Returns True if any threshold was violated.
    """
    if not reports:
        return False

    any_violation = False
    all_sections: list[str] = []

    for report in reports:
        section, violated = _build_report_section(report)
        all_sections.append(section)
        if violated:
            any_violation = True

    # Post GitHub PR comment if running in GitHub Actions
    if os.environ.get("GITHUB_ACTIONS") == "true":
        status = "🔴" if any_violation else "🟢"
        body = f"## {status} Cobalt Experiment Results\n\n" + "\n\n---\n\n".join(all_sections)
        body += "\n\n<!-- cobalt_eval_comment -->"
        try:
            _post_github_comment(body)
        except Exception as exc:
            print(f"[cobalt] Warning: failed to post GitHub comment: {exc}")

    return any_violation


def _build_report_section(report: ExperimentReport) -> tuple[str, bool]:
    """Build markdown section for one experiment. Returns (markdown, had_violations)."""
    lines: list[str] = []
    lines.append(f"### {report.name}\n")

    # Score table
    ci_result = report.config.get("_ci_result")
    violations_by_key: dict[str, str] = {}
    had_violations = False

    if ci_result is not None:
        had_violations = not ci_result.passed
        for v in ci_result.violations:
            violations_by_key[f"{v.category}.{v.metric}"] = v.message

    if report.summary.scores:
        lines.append("|  | Evaluator | Metric | Score | Threshold | Message |")
        lines.append("| --- | --- | --- | --- | --- | --- |")

        thresholds: ThresholdConfig | None = report.config.get("_thresholds")

        for eval_name, stats in report.summary.scores.items():
            ev_threshold = _get_evaluator_threshold(thresholds, eval_name)
            metrics = [
                ("avg", stats.avg),
                ("p50", stats.p50),
                ("p95", stats.p95),
                ("min", stats.min),
                ("max", stats.max),
            ]
            first = True
            for metric_name, value in metrics:
                key = f"{eval_name}.{metric_name}"
                violation_msg = violations_by_key.get(key, "")
                threshold_val = _get_threshold_value(ev_threshold, metric_name)
                threshold_str = f"≥ {threshold_val:.2f}" if threshold_val is not None else "—"
                is_fail = key in violations_by_key
                status = "🔴" if is_fail else "🟢" if threshold_val is not None else ""
                score_str = f"**{value:.2f}**" if is_fail else f"{value:.2f}"
                ev_col = f"**{eval_name}**" if first else ""
                metric_col = f"**{metric_name}**"
                lines.append(
                    f"| {status} | {ev_col} | {metric_col} | {score_str} | {threshold_str} | {violation_msg} |"
                )
                first = False

    # Performance table
    lines.append("")
    lines.append("#### ⚡ Performance")
    lines.append("| Metric | Avg | P50 | P95 | Min | Max |")
    lines.append("| --- | --- | --- | --- | --- | --- |")

    latencies = [item.latency_ms for item in report.items]
    if latencies:
        latencies_sorted = sorted(latencies)
        avg_lat = sum(latencies) / len(latencies)
        p50_lat = latencies_sorted[len(latencies_sorted) // 2]
        p95_idx = min(int(len(latencies_sorted) * 0.95), len(latencies_sorted) - 1)
        p95_lat = latencies_sorted[p95_idx]
        min_lat = latencies_sorted[0]
        max_lat = latencies_sorted[-1]
        lines.append(
            f"| Latency | {_fmt_latency(avg_lat)} | {_fmt_latency(p50_lat)} | "
            f"{_fmt_latency(p95_lat)} | {_fmt_latency(min_lat)} | {_fmt_latency(max_lat)} |"
        )

    # Summary line
    lines.append("")
    duration_s = report.summary.total_duration_ms / 1000
    lines.append(f"**Summary:** {report.summary.total_items} items · {duration_s:.1f}s")

    return "\n".join(lines), had_violations


def _fmt_latency(ms: float) -> str:
    if ms >= 1000:
        return f"{ms / 1000:.1f}s"
    return f"{ms:.0f}ms"


def _get_evaluator_threshold(
    thresholds: ThresholdConfig | None, eval_name: str
) -> ThresholdMetric | None:
    if thresholds is None:
        return None
    # Check per-evaluator first, then fall back to global score
    if thresholds.evaluators and eval_name in thresholds.evaluators:
        return thresholds.evaluators[eval_name]
    return thresholds.score


def _get_threshold_value(metric: ThresholdMetric | None, name: str) -> float | None:
    if metric is None:
        return None
    return getattr(metric, name, None)


def _post_github_comment(body: str) -> None:
    """Post or update a PR comment using the gh CLI."""
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        print("[cobalt] No GITHUB_EVENT_PATH set, skipping PR comment")
        return

    with open(event_path) as f:
        event = json.load(f)

    pr_number = None
    if "pull_request" in event:
        pr_number = event["pull_request"].get("number")
    elif "number" in event:
        pr_number = event["number"]

    if pr_number is None:
        print("[cobalt] Could not determine PR number from event, skipping comment")
        return

    repo = os.environ.get("GITHUB_REPOSITORY", "")
    marker = "<!-- cobalt_eval_comment -->"
    print(f"[cobalt] Posting comment to {repo}#{pr_number}")

    # Try to find existing comment to update
    result = subprocess.run(
        ["gh", "api", f"repos/{repo}/issues/{pr_number}/comments",
         "--jq", f'[.[] | select(.body | contains("{marker}")) | .id] | first'],
        capture_output=True, text=True, timeout=30,
    )
    existing_id = result.stdout.strip() if result.returncode == 0 else ""

    if existing_id and existing_id != "null":
        # Update existing comment
        print(f"[cobalt] Updating existing comment {existing_id}")
        r = subprocess.run(
            ["gh", "api", "--method", "PATCH",
             f"repos/{repo}/issues/comments/{existing_id}",
             "-f", f"body={body}"],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0:
            print(f"[cobalt] Failed to update comment: {r.stderr}")
    else:
        # Create new comment
        print("[cobalt] Creating new comment")
        r = subprocess.run(
            ["gh", "api", "--method", "POST",
             f"repos/{repo}/issues/{pr_number}/comments",
             "-f", f"body={body}"],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0:
            print(f"[cobalt] Failed to create comment: {r.stderr}")
