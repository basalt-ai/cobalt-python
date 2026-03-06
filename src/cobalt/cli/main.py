"""Cobalt CLI — entry point for `cobalt` command."""

from __future__ import annotations

import asyncio
import glob
import importlib.util
import sys
import webbrowser
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="cobalt",
    help="Unit testing for AI Agents 🧪",
    add_completion=False,
)
console = Console()


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------


@app.command()
def run(
    file: Optional[str] = typer.Option(None, "--file", "-f", help="Path to a specific .cobalt.py file."),
    ci: bool = typer.Option(False, "--ci", help="Exit code 1 if thresholds are violated."),
    concurrency: Optional[int] = typer.Option(None, "--concurrency", "-c", help="Override concurrency."),
    filter_: Optional[str] = typer.Option(None, "--filter", help="Run only experiments matching this string."),
) -> None:
    """Discover and run experiment files."""
    from cobalt.config import load_config

    config = load_config()

    if file:
        experiment_files = [Path(file)]
    else:
        pattern = config.test_match[0] if config.test_match else "**/*.cobalt.py"
        experiment_files = [Path(p) for p in glob.glob(pattern, recursive=True)]

    if not experiment_files:
        console.print("[yellow]No experiment files found.[/yellow]")
        raise typer.Exit(0)

    console.print(f"[bold]Found {len(experiment_files)} experiment file(s)[/bold]")

    any_violation = False

    for exp_file in experiment_files:
        console.print(f"\n[cyan]Running:[/cyan] {exp_file}")
        spec = importlib.util.spec_from_file_location("_cobalt_exp", exp_file)
        if spec is None or spec.loader is None:
            console.print(f"[red]Failed to load {exp_file}[/red]")
            continue

        module = importlib.util.module_from_spec(spec)
        try:
            # Modules call experiment() — which is async — at import time via
            # asyncio.run() wrappers or the module's __main__ block.
            spec.loader.exec_module(module)  # type: ignore[union-attr]
        except SystemExit:
            pass
        except Exception as exc:
            console.print(f"[red]Error in {exp_file}: {exc}[/red]")

    if ci and any_violation:
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------


@app.command()
def init() -> None:
    """Create example experiment and cobalt.toml config."""
    experiments_dir = Path("experiments")
    experiments_dir.mkdir(exist_ok=True)

    example = experiments_dir / "my-agent.cobalt.py"
    if not example.exists():
        example.write_text(
            '''\
"""Example Cobalt experiment."""

import asyncio
from cobalt import Dataset, Evaluator, experiment


async def my_agent(text: str) -> str:
    """Replace with your real agent call."""
    return f"Echo: {text}"


dataset = Dataset.from_items([
    {"input": "What is 2+2?", "expected_output": "4"},
    {"input": "Capital of France?", "expected_output": "Paris"},
])

evaluators = [
    Evaluator(
        name="exact-match",
        type="function",
        fn=lambda ctx: __import__("cobalt").types.EvalResult(
            score=1.0 if str(ctx.item.get("expected_output", "")) in str(ctx.output) else 0.0
        ),
    ),
]


async def main() -> None:
    await experiment(
        "my-agent",
        dataset,
        runner=lambda ctx: my_agent(ctx.item["input"]).then(
            lambda out: __import__("cobalt").types.ExperimentResult(output=out)
        ),
        evaluators=evaluators,
    )


if __name__ == "__main__":
    asyncio.run(main())
''',
            encoding="utf-8",
        )
        console.print(f"[green]Created:[/green] {example}")

    config_file = Path("cobalt.toml")
    if not config_file.exists():
        config_file.write_text(
            """\
[judge]
model = "gpt-4o-mini"
provider = "openai"
# api_key = "sk-..."  # or set OPENAI_API_KEY env var

[experiment]
concurrency = 5
timeout = 30
test_dir = "./experiments"
""",
            encoding="utf-8",
        )
        console.print(f"[green]Created:[/green] {config_file}")

    console.print("\n[bold green]✓ Cobalt initialised.[/bold green] Run: [cyan]cobalt run[/cyan]")


# ---------------------------------------------------------------------------
# history
# ---------------------------------------------------------------------------


@app.command()
def history(
    limit: int = typer.Option(20, "--limit", "-n"),
    experiment_name: Optional[str] = typer.Option(None, "--experiment", "-e"),
) -> None:
    """List recent experiment runs."""
    from cobalt.storage.db import HistoryDB

    with HistoryDB() as db:
        runs = db.list_runs(experiment=experiment_name, limit=limit)

    if not runs:
        console.print("[yellow]No runs found.[/yellow]")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("ID", style="dim")
    table.add_column("Name")
    table.add_column("Timestamp")
    table.add_column("Items", justify="right")
    table.add_column("Duration", justify="right")
    table.add_column("Scores")

    for run in runs:
        scores_str = "  ".join(f"{k}={v:.2f}" for k, v in run.avg_scores.items())
        table.add_row(
            run.id,
            run.name,
            run.timestamp[:19],
            str(run.total_items),
            f"{run.duration_ms:.0f}ms",
            scores_str,
        )
    console.print(table)


# ---------------------------------------------------------------------------
# compare
# ---------------------------------------------------------------------------


@app.command()
def compare(
    run_id_1: str = typer.Argument(..., help="First run ID"),
    run_id_2: str = typer.Argument(..., help="Second run ID"),
) -> None:
    """Compare two experiment runs side by side."""
    from cobalt.storage.results import load_result

    r1 = load_result(run_id_1)
    r2 = load_result(run_id_2)

    if r1 is None:
        console.print(f"[red]Run not found:[/red] {run_id_1}")
        raise typer.Exit(1)
    if r2 is None:
        console.print(f"[red]Run not found:[/red] {run_id_2}")
        raise typer.Exit(1)

    all_evaluators = sorted(set(list(r1.summary.scores.keys()) + list(r2.summary.scores.keys())))

    table = Table(show_header=True, header_style="bold")
    table.add_column("Evaluator")
    table.add_column(f"[cyan]{r1.name}[/cyan] ({run_id_1[:6]})", justify="right")
    table.add_column(f"[magenta]{r2.name}[/magenta] ({run_id_2[:6]})", justify="right")
    table.add_column("Δ", justify="right")

    for name in all_evaluators:
        s1 = r1.summary.scores.get(name)
        s2 = r2.summary.scores.get(name)
        v1 = f"{s1.avg:.3f}" if s1 else "—"
        v2 = f"{s2.avg:.3f}" if s2 else "—"
        if s1 and s2:
            delta = s2.avg - s1.avg
            color = "green" if delta > 0 else ("red" if delta < 0 else "dim")
            delta_str = f"[{color}]{delta:+.3f}[/{color}]"
        else:
            delta_str = "—"
        table.add_row(name, v1, v2, delta_str)

    console.print(table)


# ---------------------------------------------------------------------------
# clean
# ---------------------------------------------------------------------------


@app.command()
def clean(
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation."),
) -> None:
    """Delete all stored results and reset the history database."""
    import shutil
    from cobalt.storage.db import _DB_PATH
    from cobalt.storage.results import _RESULTS_DIR

    if not yes:
        typer.confirm("This will delete all results. Continue?", abort=True)

    if _RESULTS_DIR.exists():
        shutil.rmtree(_RESULTS_DIR)
        console.print(f"[green]Deleted:[/green] {_RESULTS_DIR}")

    if _DB_PATH.exists():
        _DB_PATH.unlink()
        console.print(f"[green]Deleted:[/green] {_DB_PATH}")

    console.print("[bold green]✓ Cleaned.[/bold green]")


# ---------------------------------------------------------------------------
# ui (dashboard)
# ---------------------------------------------------------------------------


@app.command()
def ui(
    port: int = typer.Option(4000, "--port", "-p", help="Port to bind the dashboard server."),
    no_open: bool = typer.Option(False, "--no-open", help="Don't automatically open browser."),
    host: str = typer.Option("127.0.0.1", "--host", help="Host interface to bind."),
) -> None:
    """Start the local Cobalt dashboard at http://localhost:<port>."""
    try:
        import uvicorn
    except ImportError:
        console.print(
            "[red]uvicorn not installed.[/red] Run: pip install 'cobalt-ai[dashboard]'"
        )
        raise typer.Exit(1)

    from cobalt.dashboard.server import app as dashboard_app

    url = f"http://{host}:{port}"
    console.print(f"[bold green]✓ Cobalt Dashboard[/bold green] → [cyan]{url}[/cyan]")

    if not no_open:
        import threading
        import time

        def _open():
            time.sleep(0.8)
            webbrowser.open(url)

        threading.Thread(target=_open, daemon=True).start()

    uvicorn.run(dashboard_app, host=host, port=port, log_level="warning")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
