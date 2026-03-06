# CI/CD Integration

Gate deploys on evaluation quality. `cobalt run --ci` exits with code 1 if thresholds are violated.

## Quick Start

### 1. Define Thresholds

Pass a `ThresholdConfig` to `experiment()`:

```python
from cobalt.types import ThresholdConfig, ThresholdMetric

thresholds = ThresholdConfig(
    evaluators={
        "factual-accuracy": ThresholdMetric(avg=0.85, p95=0.70),
        "contains-answer":  ThresholdMetric(avg=0.90),
    }
)

report = await experiment(
    "qa-agent", dataset, runner,
    evaluators=evaluators,
    thresholds=thresholds,
)
```

### 2. Run in CI

```bash
cobalt run --ci
# Exit 0 = all thresholds passed
# Exit 1 = one or more thresholds violated
```

### 3. GitHub Actions

```yaml
name: AI Quality Check
on: [pull_request]

jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install cobalt-ai
      - run: cobalt run --ci
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

---

## Threshold Configuration

### `ThresholdMetric` Fields

| Field | Type | Description |
|-------|------|-------------|
| `avg` | `float` | Minimum average score |
| `min` | `float` | Minimum score any single item may receive |
| `max` | `float` | Maximum score constraint (rarely needed) |
| `p50` | `float` | Minimum median score |
| `p95` | `float` | Minimum 95th-percentile score |
| `p99` | `float` | Minimum 99th-percentile score |
| `pass_rate` | `float` | Fraction of items that must score ≥ `min_score` |
| `min_score` | `float` | Score floor used by `pass_rate` (default 0.5) |

All fields are optional. Only set the ones you care about.

### Per-Evaluator Thresholds

```python
ThresholdConfig(
    evaluators={
        "exact-match":     ThresholdMetric(avg=0.95, p95=0.80),
        "conciseness":     ThresholdMetric(avg=0.80),
        "llm-accuracy":    ThresholdMetric(avg=0.85, pass_rate=0.90, min_score=0.5),
    }
)
```

### Global Score Threshold

```python
ThresholdConfig(
    score=ThresholdMetric(avg=0.80),   # applies to ALL evaluators' avg
)
```

---

## Violation Output

When a threshold is violated, the run still completes (results are saved) and then a summary is printed:

```
3 threshold(s) violated:
  factual-accuracy.avg: expected >= 0.850, got 0.780
  factual-accuracy.p95: expected >= 0.700, got 0.620
  contains-answer.avg:  expected >= 0.900, got 0.840
```

Exit code 1 is set — your CI pipeline will mark the step as failed.

---

## Regression Detection

Compare a new run against a known-good baseline before shipping:

```yaml
- name: Run experiments
  run: |
    cobalt run --ci
    cobalt compare $BASELINE_ID $(cobalt history --limit 1 --json | jq -r '.[0].id')
  env:
    BASELINE_ID: "abc123"   # pin your baseline
```

---

## Best Practices

- **Start conservative** — use `avg=0.7` initially; tighten after a few runs.
- **Use `p95`** for consistency checks — a good average with low p95 means some items are failing badly.
- **Pin baselines** — store a known-good `run_id` and compare against it on every PR.
- **Separate CI from exploratory runs** — tag CI runs with `["ci", "pr-123"]` for filtering.
