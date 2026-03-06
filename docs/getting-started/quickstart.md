# Quickstart

Get your first Cobalt experiment running in 5 minutes.

## Prerequisites

- Python 3.11+
- `pip install cobalt-ai`
- OpenAI API key

## Step 1: Set Your API Key

```bash
export OPENAI_API_KEY="sk-..."
```

## Step 2: Create Your First Experiment

Create `experiments/my-first-test.cobalt.py`:

```python
import asyncio
from cobalt import Dataset, Evaluator, EvalContext, EvalResult, ExperimentResult, experiment

# 1. Define test data
dataset = Dataset.from_items([
    {"input": "What is the capital of France?", "expected_output": "Paris"},
    {"input": "What is 2 + 2?",                "expected_output": "4"},
    {"input": "Who wrote Romeo and Juliet?",    "expected_output": "Shakespeare"},
])

# 2. Define evaluators
def contains_answer(ctx: EvalContext) -> EvalResult:
    expected = str(ctx.item.get("expected_output", "")).lower()
    got = str(ctx.output).lower()
    score = 1.0 if expected in got else 0.0
    return EvalResult(score=score, reason="Found" if score else "Not found")

evaluators = [
    Evaluator(name="contains-answer", type="function", fn=contains_answer),
]

# 3. Define the runner (replace with your real agent)
async def my_runner(ctx) -> ExperimentResult:
    return ExperimentResult(output=f"The answer is {ctx.item['expected_output']}")

# 4. Run
async def main():
    await experiment(
        "my-first-test",
        dataset,
        my_runner,
        evaluators=evaluators,
        tags=["quickstart"],
    )

asyncio.run(main())
```

## Step 3: Run It

```bash
cobalt run --file experiments/my-first-test.cobalt.py
```

Output:

```
Experiment: my-first-test  a1b2c3
Items: 3 | Duration: 45ms | Avg latency: 15ms

 Evaluator       Avg  Min  Max  P95
 contains-answer 1.00 1.00 1.00 1.00
```

## Step 4: View History

```bash
cobalt history
```

## Step 5: Open the Dashboard

```bash
cobalt ui
```

Opens `http://localhost:4000` with run history, score charts, and item-level detail.

## Next Steps

- [Your First Experiment](first-experiment.md) — Full walkthrough with a real LLM
- [Evaluators](../evaluators.md) — All evaluator types
- [Datasets](../datasets.md) — Loading and transforming data
- [CI/CD](../ci-mode.md) — Automate quality gates
