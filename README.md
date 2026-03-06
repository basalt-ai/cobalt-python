# 🧪 cobalt-python

> Unit testing for AI Agents — Python port of [Cobalt](https://github.com/basalt-ai/cobalt)

[![Tests](https://github.com/basalt-ai/cobalt-python/actions/workflows/test.yml/badge.svg)](https://github.com/basalt-ai/cobalt-python/actions/workflows/test.yml)
[![PyPI](https://img.shields.io/pypi/v/cobalt-ai)](https://pypi.org/project/cobalt-ai/)
[![Python](https://img.shields.io/pypi/pyversions/cobalt-ai)](https://pypi.org/project/cobalt-ai/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Cobalt lets you write deterministic, repeatable tests for your LLM-powered agents and pipelines — the same way you'd write unit tests for regular code.

This is the **Python** port. The original TypeScript SDK lives at [basalt-ai/cobalt](https://github.com/basalt-ai/cobalt).

---

## Features

- **Dataset loaders** — JSON, JSONL, CSV, remote URL, Langfuse, Langsmith, Braintrust, Basalt
- **Three evaluator types** — LLM-judge, custom function, semantic similarity
- **Async-native runner** — configurable concurrency + per-item timeout
- **SQLite history** — compare runs over time with `cobalt history` / `cobalt compare`
- **Local dashboard** — `cobalt ui` spins up a web UI with score charts, item drill-down, and run comparison
- **CI-ready** — declare score thresholds, get exit code 1 on regression
- **Rich CLI** — `cobalt run`, `cobalt init`, `cobalt history`, `cobalt compare`, `cobalt ui`, `cobalt clean`
- **Full docs** — [docs/](docs/) matches TypeScript SDK structure and coverage

---

## Install

```bash
pip install cobalt-ai
```

For development / from source:

```bash
git clone https://github.com/basalt-ai/cobalt-python
cd cobalt-python
pip install -e ".[dev]"
```

---

## Quick start

```python
# my_agent.cobalt.py
import asyncio
from cobalt import Dataset, Evaluator, EvalContext, EvalResult, ExperimentResult, experiment


async def my_agent(question: str) -> str:
    # Replace with your real LLM call
    return f"The answer is 42"


dataset = Dataset.from_items([
    {"input": "What is 6 × 7?", "expected_output": "42"},
    {"input": "What is the capital of France?", "expected_output": "Paris"},
])


def exact_match(ctx: EvalContext) -> EvalResult:
    expected = str(ctx.item.get("expected_output", ""))
    score = 1.0 if expected in str(ctx.output) else 0.0
    return EvalResult(score=score, reason=f"Expected: {expected}")


async def main():
    await experiment(
        "my-agent",
        dataset,
        runner=lambda ctx: my_agent(ctx.item["input"]).then(
            lambda out: ExperimentResult(output=out)
        ),
        evaluators=[
            Evaluator(name="exact-match", type="function", fn=exact_match),
        ],
    )


asyncio.run(main())
```

```bash
cobalt run --file my_agent.cobalt.py
```

---

## Evaluators

### Function evaluator

```python
def my_check(ctx: EvalContext) -> EvalResult:
    return EvalResult(score=1.0 if "yes" in ctx.output.lower() else 0.0)

Evaluator(name="contains-yes", type="function", fn=my_check)
```

### LLM Judge

```python
Evaluator(
    name="helpfulness",
    type="llm-judge",
    model="gpt-4o-mini",       # or claude-3-5-haiku, etc.
    scoring="boolean",          # "boolean" (PASS/FAIL) or "scale" (0–1)
    chain_of_thought=True,
    prompt="""
You are evaluating an AI assistant's response.

Question: {{input}}
Response: {{output}}

Is the response helpful and accurate? Reply PASS or FAIL.
""",
)
```

### Similarity

```python
Evaluator(
    name="semantic-similarity",
    type="similarity",
    field="expected_output",   # dataset field to compare against
    threshold=0.7,             # score = 1.0 if similarity >= threshold
)
```

---

## Datasets

```python
# From Python
ds = Dataset.from_items([{"input": "hello", "expected": "world"}])

# From files
ds = Dataset.from_file("data.csv")     # csv / json / jsonl — auto-detected
ds = Dataset.from_jsonl("data.jsonl")
ds = Dataset.from_json("data.json")

# Remote
ds = await Dataset.from_remote("https://example.com/data.jsonl")

# Platforms
ds = await Dataset.from_langfuse("my-dataset")
ds = await Dataset.from_langsmith("my-dataset")
ds = await Dataset.from_braintrust("my-project", "my-dataset")
ds = await Dataset.from_basalt("dataset-id")

# Transformations (chainable)
ds = ds.filter(lambda item, i: item["score"] > 0.5)
ds = ds.map(lambda item, i: {**item, "idx": i})
ds = ds.sample(100)
ds = ds.slice(0, 50)
```

---

## Configuration

Create `cobalt.toml` in your project root (or run `cobalt init`):

```toml
[judge]
model = "gpt-4o-mini"
provider = "openai"
# api_key = "sk-..."  # or set OPENAI_API_KEY env var

[experiment]
concurrency = 5
timeout = 30
test_dir = "./experiments"
```

---

## Dashboard

```bash
pip install 'cobalt-ai[dashboard]'
cobalt ui
# Opens http://localhost:4000
```

The local dashboard provides:
- Run history with colour-coded score pills
- Per-run score distribution chart (avg / p95 / min per evaluator)
- Item-level drill-down — input, output, evaluator reasons
- Side-by-side run comparison

## CLI

```bash
# Scaffold config + example experiment
cobalt init

# Run all *.cobalt.py files
cobalt run

# Run a specific file
cobalt run --file experiments/my-agent.cobalt.py

# CI mode — exit 1 if thresholds violated
cobalt run --ci

# List recent runs
cobalt history --limit 20

# Compare two runs
cobalt compare <run-id-1> <run-id-2>

# Local web dashboard
cobalt ui --port 4000

# Delete all stored results
cobalt clean
```

---

## CI Integration

```python
from cobalt.types import ThresholdConfig, ThresholdMetric

thresholds = ThresholdConfig(
    evaluators={
        "exact-match": ThresholdMetric(avg=0.9, p95=0.7),
        "helpfulness":  ThresholdMetric(avg=0.8),
    }
)

report = await experiment(
    "my-agent", dataset, runner,
    evaluators=[...],
    thresholds=thresholds,
)
```

```yaml
# .github/workflows/eval.yml
- name: Run evaluations
  run: cobalt run --ci
  env:
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

---

## Architecture

```
src/cobalt/
├── __init__.py          # Public API surface
├── types.py             # All dataclasses
├── config.py            # cobalt.toml loader
├── dataset.py           # Dataset class
├── evaluator.py         # Evaluator + registry
├── experiment.py        # Core runner
├── evaluators/
│   ├── function.py      # Custom function evaluator
│   ├── llm_judge.py     # LLM-judge evaluator
│   └── similarity.py    # TF-IDF cosine similarity
├── storage/
│   ├── db.py            # SQLite history
│   └── results.py       # JSON result files
├── utils/
│   ├── stats.py         # Descriptive statistics
│   ├── template.py      # {{variable}} rendering
│   └── cost.py          # Token cost estimation
└── cli/
    └── main.py          # cobalt CLI (Typer)
```

---

## Development

```bash
# Install
pip install -e ".[dev]"

# Test
pytest tests/ -v

# Lint
ruff check src/ tests/
```

---

## Relationship to TypeScript Cobalt

| Feature | TypeScript | Python |
|---------|-----------|--------|
| Dataset loaders | ✅ | ✅ |
| LLM judge | ✅ | ✅ |
| Function evaluator | ✅ | ✅ |
| Similarity | ✅ | ✅ (TF-IDF) |
| CLI | ✅ | ✅ |
| History / compare | ✅ | ✅ |
| SQLite storage | ✅ | ✅ |
| CI thresholds | ✅ | ✅ |
| Platform integrations | Langfuse, Langsmith, Braintrust, Basalt | ✅ same |

Python conventions used throughout: `async/await`, `dataclasses`, `asyncio.Semaphore`, `typer`, `rich`.

---

## License

MIT — see [LICENSE](LICENSE).

Built by [Basalt AI](https://getbasalt.ai).
