# Cobalt Python — Documentation

> Unit testing for AI Agents | Python port of [basalt-ai/cobalt](https://github.com/basalt-ai/cobalt)

## Getting Started

| Guide | Description |
|-------|-------------|
| [Installation](getting-started/installation.md) | Install and set up cobalt-python |
| [Quickstart](getting-started/quickstart.md) | First experiment in 5 minutes |
| [Your First Experiment](getting-started/first-experiment.md) | Full walkthrough with a real LLM |
| [Understanding Results](getting-started/understanding-results.md) | Interpreting scores, reports, and the dashboard |

## Core Concepts

| Guide | Description |
|-------|-------------|
| [Datasets](datasets.md) | Load and transform test data |
| [Evaluators](evaluators.md) | Score your agent's output |
| [CI/CD Integration](ci-mode.md) | Gate deploys on quality thresholds |
| [Configuration](configuration.md) | `cobalt.toml` full reference |
| [MCP Integration](mcp.md) | Use Cobalt with Claude via Model Context Protocol |

## CLI Reference

```bash
cobalt init          # Scaffold config + example experiment
cobalt run           # Discover and run all *.cobalt.py files
cobalt run -f FILE   # Run a specific file
cobalt run --ci      # Exit 1 on threshold violations
cobalt history       # List recent runs
cobalt compare A B   # Side-by-side score comparison
cobalt ui            # Start local web dashboard (port 4000)
cobalt clean         # Delete all stored results
```

## Dashboard

```bash
pip install 'cobalt-ai[dashboard]'
cobalt ui
```

Opens at `http://localhost:4000`:
- Run history with score pills
- Per-run score distribution chart (avg / p95 / min)
- Item-by-item drill-down with input, output, evaluator reasons
- Side-by-side run comparison

## API Reference

### `experiment()`

```python
from cobalt import experiment

report = await experiment(
    name="my-run",
    dataset=dataset,
    runner=my_runner,          # async (RunnerContext) -> ExperimentResult
    evaluators=[...],          # list[Evaluator]
    runs=1,                    # repetitions per item
    concurrency=5,
    timeout=30.0,
    tags=["v1", "prod"],
    thresholds=ThresholdConfig(...),
)
```

### `Dataset`

```python
Dataset.from_items([...])
Dataset.from_file("path.csv")
Dataset.from_json("path.json")
Dataset.from_jsonl("path.jsonl")
await Dataset.from_remote("https://...")
await Dataset.from_langfuse("name")
await Dataset.from_langsmith("name")
await Dataset.from_braintrust("project", "dataset")
await Dataset.from_basalt("id")

dataset.filter(fn).sample(100).slice(0, 50)
```

### `Evaluator`

```python
Evaluator(name="...", type="function",    fn=my_fn)
Evaluator(name="...", type="llm-judge",   prompt="...", model="gpt-4o-mini")
Evaluator(name="...", type="similarity",  field="expected_output", threshold=0.8)
```

### Storage

```python
from cobalt.storage.results import load_result, list_results, save_result

summaries = list_results(experiment="my-run", limit=20)
report    = load_result("abc123")
```

## TypeScript Version

Python feature parity with [basalt-ai/cobalt](https://github.com/basalt-ai/cobalt) (TypeScript SDK):

| Feature | TypeScript | Python |
|---------|-----------|--------|
| Dataset loaders | ✅ | ✅ |
| LLM judge | ✅ | ✅ |
| Function evaluator | ✅ | ✅ |
| Similarity evaluator | ✅ | ✅ (TF-IDF) |
| CI thresholds | ✅ | ✅ |
| History & compare | ✅ | ✅ |
| SQLite storage | ✅ | ✅ |
| Local dashboard | ✅ | ✅ (`cobalt ui`) |
| MCP integration | ✅ | ✅ (`cobalt mcp`) |
| GitHub Actions | ✅ | ✅ |
| Platform integrations | Langfuse / Langsmith / Braintrust / Basalt | ✅ same |

Differences:
- Config format: `.ts` → `cobalt.toml`
- Dashboard backend: Node.js → FastAPI + uvicorn
- Similarity: OpenAI embeddings → TF-IDF (zero API cost)
- Cache: not yet implemented (roadmap)
- MCP integration: not yet implemented (roadmap)
