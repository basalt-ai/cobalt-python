"""Cobalt MCP Server.

Exposes Cobalt's experiment runner to Claude and other MCP clients via the
Model Context Protocol (stdio transport).

Tools:    cobalt_run · cobalt_results · cobalt_compare · cobalt_generate
Resources: cobalt://config · cobalt://experiments · cobalt://latest-results
Prompts:  improve-agent · generate-tests · regression-check
"""

from __future__ import annotations

import asyncio
import dataclasses
import glob
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

from cobalt.config import load_config
from cobalt.storage.results import _RESULTS_DIR, list_results, load_result

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_server = Server("cobalt")


def _to_dict(obj: Any) -> Any:
    """Recursively convert dataclasses to JSON-serialisable dicts."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: _to_dict(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, list):
        return [_to_dict(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _to_dict(v) for k, v in obj.items()}
    return obj


def _json(obj: Any) -> str:
    return json.dumps(_to_dict(obj), indent=2, default=str)


def _text(content: str) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=content)]


# ---------------------------------------------------------------------------
# TOOLS
# ---------------------------------------------------------------------------


@_server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="cobalt_run",
            description=(
                "Run a Cobalt experiment file and return full results. "
                "Use this to execute tests and get scored results."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "file": {
                        "type": "string",
                        "description": "Path to the .cobalt.py experiment file.",
                    },
                    "concurrency": {
                        "type": "integer",
                        "description": "Override default concurrency.",
                    },
                },
                "required": ["file"],
            },
        ),
        types.Tool(
            name="cobalt_results",
            description=(
                "List recent experiment runs or get detailed results for a specific run. "
                "Pass runId for detail view; omit for list view."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "run_id": {
                        "type": "string",
                        "description": "Run ID for detailed view. Omit to list runs.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of recent runs to return (default 10).",
                    },
                    "experiment": {
                        "type": "string",
                        "description": "Filter by experiment name.",
                    },
                },
            },
        ),
        types.Tool(
            name="cobalt_compare",
            description=(
                "Compare two experiment runs side-by-side. Returns score deltas, "
                "regressions, and improvements per evaluator."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "run_a": {
                        "type": "string",
                        "description": "Baseline run ID.",
                    },
                    "run_b": {
                        "type": "string",
                        "description": "Candidate run ID.",
                    },
                },
                "required": ["run_a", "run_b"],
            },
        ),
        types.Tool(
            name="cobalt_generate",
            description=(
                "Analyse agent source code and auto-generate a .cobalt.py experiment "
                "file with a dataset and evaluators. Uses the configured LLM judge."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "agent_file": {
                        "type": "string",
                        "description": "Path to the agent Python source file.",
                    },
                    "output_file": {
                        "type": "string",
                        "description": "Output path for the generated experiment (optional).",
                    },
                    "dataset_size": {
                        "type": "integer",
                        "description": "Number of test cases to generate (default 10).",
                    },
                },
                "required": ["agent_file"],
            },
        ),
    ]


@_server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    if name == "cobalt_run":
        return await _tool_run(arguments)
    if name == "cobalt_results":
        return await _tool_results(arguments)
    if name == "cobalt_compare":
        return await _tool_compare(arguments)
    if name == "cobalt_generate":
        return await _tool_generate(arguments)
    return _text(f"Unknown tool: {name}")


# --- cobalt_run ---

async def _tool_run(args: dict) -> list[types.TextContent]:
    file = args.get("file", "")
    if not file:
        return _text('{"error": "file parameter is required"}')

    if not Path(file).exists():
        return _text(f'{{"error": "File not found: {file}"}}')

    cmd = [sys.executable, "-m", "cobalt.cli.main", "run", "--file", file]
    concurrency = args.get("concurrency")
    if concurrency:
        cmd += ["--concurrency", str(concurrency)]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
    except asyncio.TimeoutError:
        return _text('{"error": "Experiment timed out after 300s"}')
    except Exception as exc:
        return _text(f'{{"error": "Execution error: {exc}"}}')

    # Find the latest result file that was just written
    results = list_results(limit=1)
    if results:
        report = load_result(results[0].id)
        if report:
            return _text(_json(report))

    # Fallback: return CLI output
    output = stdout.decode(errors="replace") + stderr.decode(errors="replace")
    return _text(json.dumps({"output": output, "return_code": proc.returncode}))


# --- cobalt_results ---

async def _tool_results(args: dict) -> list[types.TextContent]:
    run_id = args.get("run_id")
    if run_id:
        report = load_result(run_id)
        if report is None:
            return _text(f'{{"error": "Run not found: {run_id}"}}')
        return _text(_json(report))

    limit = int(args.get("limit", 10))
    experiment = args.get("experiment")
    summaries = list_results(experiment=experiment, limit=limit)
    runs = []
    for s in summaries:
        runs.append({
            "id": s.id,
            "name": s.name,
            "timestamp": s.timestamp,
            "total_items": s.total_items,
            "duration_ms": s.duration_ms,
            "avg_scores": s.avg_scores,
            "tags": s.tags,
        })
    return _text(json.dumps({"runs": runs, "total": len(runs)}, indent=2))


# --- cobalt_compare ---

async def _tool_compare(args: dict) -> list[types.TextContent]:
    run_a = args.get("run_a", "")
    run_b = args.get("run_b", "")

    r1 = load_result(run_a)
    r2 = load_result(run_b)

    if r1 is None:
        return _text(f'{{"error": "Run not found: {run_a}"}}')
    if r2 is None:
        return _text(f'{{"error": "Run not found: {run_b}"}}')

    all_evals = sorted(set(list(r1.summary.scores.keys()) + list(r2.summary.scores.keys())))

    score_diffs: dict[str, dict] = {}
    regressions = []
    improvements = []

    for name in all_evals:
        s1 = r1.summary.scores.get(name)
        s2 = r2.summary.scores.get(name)
        if not s1 or not s2:
            continue
        diff = round(s2.avg - s1.avg, 4)
        pct = round(diff / s1.avg * 100, 1) if s1.avg > 0 else 0
        entry = {
            "evaluator": name,
            "baseline": round(s1.avg, 4),
            "candidate": round(s2.avg, 4),
            "diff": diff,
            "percent_change": pct,
        }
        score_diffs[name] = entry
        if diff <= -0.05:
            regressions.append(entry)
        elif diff >= 0.05:
            improvements.append(entry)

    # Per-item changes
    top_changes = []
    for item_a in r1.items:
        item_b = next((i for i in r2.items if i.index == item_a.index), None)
        if not item_b:
            continue
        changes: dict[str, float] = {}
        for ev in all_evals:
            ea = item_a.evaluations.get(ev)
            eb = item_b.evaluations.get(ev)
            if ea and eb:
                changes[ev] = round(eb.score - ea.score, 4)
        max_change = max((abs(v) for v in changes.values()), default=0)
        if max_change >= 0.15:
            top_changes.append({
                "index": item_a.index,
                "input": str(item_a.input)[:120],
                "changes": changes,
                "max_change": round(max_change, 4),
            })

    top_changes.sort(key=lambda x: x["max_change"], reverse=True)

    result = {
        "run_a": {"id": r1.id, "name": r1.name, "timestamp": r1.timestamp},
        "run_b": {"id": r2.id, "name": r2.name, "timestamp": r2.timestamp},
        "score_diffs": score_diffs,
        "regressions": regressions,
        "improvements": improvements,
        "top_changes": top_changes[:5],
    }
    return _text(json.dumps(result, indent=2))


# --- cobalt_generate ---

async def _tool_generate(args: dict) -> list[types.TextContent]:
    agent_file = args.get("agent_file", "")
    output_file = args.get("output_file")
    dataset_size = int(args.get("dataset_size", 10))

    if not Path(agent_file).exists():
        return _text(f'{{"error": "Agent file not found: {agent_file}"}}')

    source = Path(agent_file).read_text(encoding="utf-8")

    if not output_file:
        stem = Path(agent_file).stem
        output_file = str(Path(agent_file).parent / f"{stem}.cobalt.py")

    config = load_config()
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("COBALT_API_KEY")
    if not api_key:
        return _text('{"error": "OPENAI_API_KEY not set. Required for cobalt_generate."}')

    prompt = _build_generate_prompt(source, dataset_size)

    try:
        import openai
        client = openai.AsyncOpenAI(api_key=api_key)
        response = await client.chat.completions.create(
            model=config.judge.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2500,
        )
        generated = response.choices[0].message.content or ""
    except Exception as exc:
        return _text(f'{{"error": "LLM call failed: {exc}"}}')

    # Extract Python code block if present
    code = _extract_code_block(generated, "python") or generated

    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    Path(output_file).write_text(code, encoding="utf-8")

    return _text(json.dumps({
        "success": True,
        "output_file": output_file,
        "dataset_size": dataset_size,
        "model_used": config.judge.model,
        "message": f"Generated experiment written to {output_file}",
    }, indent=2))


def _build_generate_prompt(source: str, dataset_size: int) -> str:
    return f"""You are an expert AI testing engineer. Analyse the following Python agent code and generate a complete Cobalt experiment file.

## Agent Source Code

```python
{source}
```

## Instructions

Generate a complete `.cobalt.py` file that:
1. Imports the agent from the source file
2. Creates a `Dataset` with {dataset_size} realistic test cases
3. Defines appropriate evaluators (function-based and/or LLM-judge)
4. Calls `experiment()` via `asyncio.run(main())`

Rules:
- Use Python idioms (dataclasses, async/await, type hints)
- Cover normal cases, edge cases, and at least 2 adversarial cases
- Use `from cobalt import Dataset, Evaluator, EvalContext, EvalResult, ExperimentResult, experiment`
- Make the runner call the agent function from the imported module
- Add a `ThresholdConfig` with sensible defaults (avg ≥ 0.7 for each evaluator)
- Output ONLY valid Python code — no explanation, no markdown

Output the complete `.cobalt.py` file:"""


def _extract_code_block(text: str, lang: str = "python") -> str | None:
    import re
    pattern = rf"```{lang}\s*(.*?)```"
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else None


# ---------------------------------------------------------------------------
# RESOURCES
# ---------------------------------------------------------------------------


@_server.list_resources()
async def list_resources() -> list[types.Resource]:
    return [
        types.Resource(
            uri="cobalt://config",
            name="Cobalt Configuration",
            description="Current cobalt.toml configuration (API keys redacted).",
            mimeType="application/json",
        ),
        types.Resource(
            uri="cobalt://experiments",
            name="Experiment Files",
            description="All .cobalt.py experiment files discovered in testDir.",
            mimeType="application/json",
        ),
        types.Resource(
            uri="cobalt://latest-results",
            name="Latest Results",
            description="Most recent run result per experiment.",
            mimeType="application/json",
        ),
    ]


@_server.read_resource()
async def read_resource(uri: types.AnyUrl) -> str:
    uri_str = str(uri)
    if uri_str == "cobalt://config":
        return _resource_config()
    if uri_str == "cobalt://experiments":
        return _resource_experiments()
    if uri_str == "cobalt://latest-results":
        return _resource_latest_results()
    raise ValueError(f"Unknown resource: {uri_str}")


def _resource_config() -> str:
    cfg = load_config()
    return json.dumps({
        "test_dir": cfg.test_dir,
        "test_match": cfg.test_match,
        "concurrency": cfg.concurrency,
        "timeout": cfg.timeout,
        "reporters": cfg.reporters,
        "judge": {
            "model": cfg.judge.model,
            "provider": cfg.judge.provider,
            "api_key": "[REDACTED]" if cfg.judge.api_key else None,
        },
    }, indent=2)


def _resource_experiments() -> str:
    cfg = load_config()
    test_dir = Path(cfg.test_dir)
    pattern = cfg.test_match[0] if cfg.test_match else "**/*.cobalt.py"
    files = [
        {"path": str(p), "name": p.stem.replace(".cobalt", "")}
        for p in sorted(test_dir.glob(pattern.lstrip("**/")) if test_dir.exists() else [])
    ]
    return json.dumps({"test_dir": str(test_dir), "count": len(files), "experiments": files}, indent=2)


def _resource_latest_results() -> str:
    summaries = list_results(limit=200)
    # One result per experiment name — keep latest
    seen: dict[str, Any] = {}
    for s in summaries:
        if s.name not in seen:
            seen[s.name] = {
                "id": s.id,
                "name": s.name,
                "timestamp": s.timestamp,
                "total_items": s.total_items,
                "duration_ms": s.duration_ms,
                "avg_scores": s.avg_scores,
                "tags": s.tags,
            }
    return json.dumps({"count": len(seen), "results": list(seen.values())}, indent=2)


# ---------------------------------------------------------------------------
# PROMPTS
# ---------------------------------------------------------------------------


@_server.list_prompts()
async def list_prompts() -> list[types.Prompt]:
    return [
        types.Prompt(
            name="improve-agent",
            description=(
                "Analyse experiment failures and suggest specific improvements "
                "to the agent code (code examples + expected score impact)."
            ),
            arguments=[
                types.PromptArgument(
                    name="run_id",
                    description="Run ID to analyse. Uses latest run if omitted.",
                    required=False,
                )
            ],
        ),
        types.Prompt(
            name="generate-tests",
            description=(
                "Generate additional test cases to improve coverage "
                "for an existing experiment."
            ),
            arguments=[
                types.PromptArgument(
                    name="experiment_file",
                    description="Path to the .cobalt.py experiment file to enhance.",
                    required=True,
                ),
                types.PromptArgument(
                    name="focus",
                    description=(
                        "Focus area: 'edge-cases', 'adversarial', or 'coverage' (default)."
                    ),
                    required=False,
                ),
            ],
        ),
        types.Prompt(
            name="regression-check",
            description=(
                "Compare two runs and output a PASS/WARN/FAIL verdict "
                "with root-cause analysis and recommendations."
            ),
            arguments=[
                types.PromptArgument(
                    name="baseline_run_id",
                    description="Run ID of the baseline (earlier) run.",
                    required=True,
                ),
                types.PromptArgument(
                    name="current_run_id",
                    description="Run ID of the current (candidate) run.",
                    required=True,
                ),
            ],
        ),
    ]


@_server.get_prompt()
async def get_prompt(
    name: str, arguments: dict[str, str] | None
) -> types.GetPromptResult:
    args = arguments or {}
    if name == "improve-agent":
        return _prompt_improve_agent(args)
    if name == "generate-tests":
        return _prompt_generate_tests(args)
    if name == "regression-check":
        return _prompt_regression_check(args)
    raise ValueError(f"Unknown prompt: {name}")


def _prompt_improve_agent(args: dict) -> types.GetPromptResult:
    run_id = args.get("run_id", "")
    run_context = ""
    if run_id:
        report = load_result(run_id)
        if report:
            # Summarise failures
            failures = [
                {
                    "index": item.index,
                    "input": item.input,
                    "output": item.output.output if item.output else "",
                    "evaluations": {
                        k: {"score": v.score, "reason": v.reason}
                        for k, v in item.evaluations.items()
                        if v.score < 0.7
                    },
                }
                for item in report.items
                if any(v.score < 0.7 for v in item.evaluations.values())
            ]
            run_context = json.dumps({
                "run_id": report.id,
                "name": report.name,
                "summary": _to_dict(report.summary),
                "failures": failures[:10],
            }, indent=2, default=str)

    messages = [
        types.PromptMessage(
            role="user",
            content=types.TextContent(
                type="text",
                text=f"""You are an expert AI evaluation engineer. Your job is to analyze Cobalt experiment results and suggest specific, actionable improvements to the agent code.

{"## Experiment Results\n\n```json\n" + run_context + "\n```\n" if run_context else "Use the cobalt_results tool to load the latest run results first."}

## Your Task

1. **Identify failure patterns** — What types of inputs fail? Which evaluators score lowest? Are there common themes?

2. **Suggest exactly 3 improvements**, ordered by impact (HIGH / MEDIUM / LOW):
   - Show the current code snippet and the improved version
   - Explain *why* the change will improve scores
   - Estimate the expected score delta (e.g. "+12% on factual-accuracy")

3. **Summarize** the expected combined improvement.

Be specific. Quote exact code. No generic advice.""",
            ),
        )
    ]
    return types.GetPromptResult(
        description="Analyse failures and suggest agent improvements",
        messages=messages,
    )


def _prompt_generate_tests(args: dict) -> types.GetPromptResult:
    experiment_file = args.get("experiment_file", "")
    focus = args.get("focus", "coverage")
    source = ""
    if experiment_file and Path(experiment_file).exists():
        source = Path(experiment_file).read_text(encoding="utf-8")

    focus_instructions = {
        "edge-cases": "Focus on boundary conditions: empty inputs, very long inputs, malformed data, unusual formatting, null/None values.",
        "adversarial": "Focus on adversarial cases: prompt injection attempts, ambiguous queries, contradictory inputs, inputs designed to confuse the agent.",
        "coverage": "Generate a balanced mix: normal cases covering untested scenarios, edge cases, and 2-3 adversarial inputs.",
    }.get(focus, "Generate a balanced mix of normal, edge, and adversarial cases.")

    messages = [
        types.PromptMessage(
            role="user",
            content=types.TextContent(
                type="text",
                text=f"""You are an expert AI testing engineer. Analyse this Cobalt experiment and generate additional test cases to improve coverage.

## Existing Experiment

```python
{source if source else f"(file: {experiment_file} — not loaded)"}
```

## Focus

{focus_instructions}

## Your Task

1. **Identify coverage gaps** in the existing dataset — what scenarios aren't covered?

2. **Generate 8–12 new test items** as a JSON array:
```json
[
  {{
    "input": "...",
    "expected_output": "...",
    "category": "normal|edge|adversarial",
    "description": "why this test is important"
  }}
]
```

3. **Explain rationale** — briefly describe what gap each category fills.

Output the JSON array of new test cases, followed by the rationale.""",
            ),
        )
    ]
    return types.GetPromptResult(
        description="Generate additional test cases for better coverage",
        messages=messages,
    )


def _prompt_regression_check(args: dict) -> types.GetPromptResult:
    baseline_id = args.get("baseline_run_id", "")
    current_id = args.get("current_run_id", "")

    comparison_data = ""
    if baseline_id and current_id:
        r1 = load_result(baseline_id)
        r2 = load_result(current_id)
        if r1 and r2:
            all_evals = sorted(set(list(r1.summary.scores.keys()) + list(r2.summary.scores.keys())))
            diffs = []
            for ev in all_evals:
                s1 = r1.summary.scores.get(ev)
                s2 = r2.summary.scores.get(ev)
                if s1 and s2:
                    diff = s2.avg - s1.avg
                    pct = diff / s1.avg * 100 if s1.avg > 0 else 0
                    diffs.append({
                        "evaluator": ev,
                        "baseline": round(s1.avg, 4),
                        "candidate": round(s2.avg, 4),
                        "diff": round(diff, 4),
                        "percent_change": round(pct, 1),
                        "regression": diff <= -0.05,
                        "improvement": diff >= 0.05,
                    })
            comparison_data = json.dumps({
                "baseline": {"id": r1.id, "name": r1.name, "timestamp": r1.timestamp},
                "candidate": {"id": r2.id, "name": r2.name, "timestamp": r2.timestamp},
                "score_diffs": diffs,
            }, indent=2)

    messages = [
        types.PromptMessage(
            role="user",
            content=types.TextContent(
                type="text",
                text=f"""You are an AI quality assurance engineer. Perform a regression check between two Cobalt experiment runs.

## Comparison Data

```json
{comparison_data if comparison_data else f"Run IDs: baseline={baseline_id}, current={current_id}\n(Use cobalt_compare tool to load data if not shown above)"}
```

## Regression Thresholds

| Change | Classification |
|--------|---------------|
| Drop > 10% per evaluator | Major regression (FAIL) |
| Drop 5–10% per evaluator | Minor regression (WARN) |
| Drop < 5% | Acceptable variance (PASS) |
| Gain > 5% | Improvement |
| New failures (was passing, now failing) | Always FAIL |

## Your Task

Output a structured regression report:

1. **Verdict**: PASS ✅ / WARN ⚠️ / FAIL ❌
2. **Summary**: # regressions, # improvements, overall score delta
3. **Regressions** (if any): which evaluators, which items, % drop
4. **Improvements** (if any): which evaluators, % gain
5. **Root Cause Hypothesis**: what likely caused regressions
6. **Recommendation**: deploy / investigate / do not deploy

Be decisive. Give a clear action recommendation.""",
            ),
        )
    ]
    return types.GetPromptResult(
        description="Regression check — PASS/WARN/FAIL verdict with analysis",
        messages=messages,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def run_server() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await _server.run(
            read_stream,
            write_stream,
            _server.create_initialization_options(),
        )


def main() -> None:
    asyncio.run(run_server())


if __name__ == "__main__":
    main()
