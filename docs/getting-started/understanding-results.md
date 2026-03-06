# Understanding Results

How to read, interpret, and act on Cobalt experiment output.

## Console Output

After every run you'll see a Rich table:

```
Experiment: qa-agent  abc123
Items: 5 | Duration: 8.2s | Avg latency: 1640ms

 Evaluator        Avg  Min  Max  P95
 contains-answer  1.00 1.00 1.00 1.00
 conciseness      0.97 0.92 1.00 1.00
 factual-accuracy 0.92 0.80 1.00 1.00
```

Colour codes:
- **Green** — avg ≥ 0.8
- **Yellow** — avg 0.5–0.8
- **Red** — avg < 0.5

## Score Statistics Explained

| Stat | Meaning | Use for |
|------|---------|---------|
| `avg` | Mean across all items | Overall performance |
| `min` | Worst single item | Identifying failures |
| `max` | Best single item | Upper bound check |
| `p50` | Median | Typical performance (outlier-resistant) |
| `p95` | 95th percentile | Consistency — only 5% worse than this |
| `p99` | 99th percentile | Tail-risk analysis |

## Result Files

Every run is persisted to:

```
~/.cobalt/
├── history.db           # Lightweight SQLite index
└── results/
    └── qa-agent-abc123.json   # Full JSON report
```

### JSON Report Structure

```json
{
  "id": "abc123",
  "name": "qa-agent",
  "timestamp": "2026-03-05T19:00:00Z",
  "tags": ["qa", "v1"],
  "config": { "concurrency": 3, "timeout": 30, "evaluators": ["contains-answer"] },
  "summary": {
    "total_items": 5,
    "total_duration_ms": 8200,
    "avg_latency_ms": 1640,
    "scores": {
      "contains-answer": { "avg": 1.0, "min": 1.0, "max": 1.0, "p50": 1.0, "p95": 1.0, "p99": 1.0 }
    }
  },
  "items": [
    {
      "index": 0,
      "input": { "input": "Capital of France?", "expected_output": "Paris" },
      "output": { "output": "Paris", "metadata": { "tokens": 4 } },
      "latency_ms": 820,
      "evaluations": {
        "contains-answer": { "score": 1.0, "reason": "Expected \"paris\"" }
      },
      "error": null
    }
  ]
}
```

## CLI Commands

```bash
# List recent runs
cobalt history --limit 20
cobalt history --experiment qa-agent

# Compare two runs
cobalt compare abc123 def456

# Visual dashboard
cobalt ui
```

### `cobalt history` output

```
 ID      Name       Timestamp          Items  Duration  Scores
 abc123  qa-agent   2026-03-05 19:00   5      8.2s      contains-answer=1.00
 def456  qa-agent   2026-03-04 14:00   5      9.1s      contains-answer=0.94
```

### `cobalt compare` output

```
 Evaluator        Avg 1  Avg 2  Δ
 contains-answer  1.00   0.94  -0.06
 conciseness      0.97   0.99  +0.02
```

## Dashboard

```bash
cobalt ui --port 4000
```

Opens a local web dashboard with:
- Run list with score pills
- Per-run score distribution bar chart
- Item-by-item drill-down with input, output, and evaluator reasons
- Side-by-side run comparison

## Programmatic Access

```python
from cobalt.storage.results import load_result, list_results

# List all runs
summaries = list_results(limit=20)
for s in summaries:
    print(s.name, s.id, s.avg_scores)

# Load a full report
report = load_result("abc123")
for item in report.items:
    score = item.evaluations["factual-accuracy"].score
    if score < 0.7:
        print(f"Low score: {item.input}")
```

## Common Patterns

### High Variance (large min–max gap)

```
factual-accuracy: avg=0.75 min=0.30 max=1.00
```

Investigation path:
1. Find items where `score < 0.5`
2. Look at the `reason` field
3. Check if they share a pattern (topic, format, length)

### Consistent Failures

All items in a category score 0 → agent has a systematic gap, not random noise.

### Timeout Errors

```json
{ "error": "Timeout after 30.0s", "latency_ms": 30012 }
```

Increase `timeout` in `cobalt.toml` or reduce `concurrency` to avoid overloading the API.

## Next Steps

- [Evaluators](../evaluators.md) — Choose the right evaluation strategy
- [CI/CD Integration](../ci-mode.md) — Gate deploys on score thresholds
- [Configuration](../configuration.md) — Tune performance and cost
