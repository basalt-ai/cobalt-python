# Your First Experiment

A complete walkthrough: test a Q&A agent with multiple evaluators against a real LLM.

## What You'll Build

- A Q&A agent backed by OpenAI
- Three evaluators: exact match, conciseness, LLM judge for factual accuracy
- A dataset loaded from JSON
- Cost and latency tracking

**Time**: ~15 minutes

## Project Structure

```
my-qa-test/
├── experiments/
│   └── qa-agent.cobalt.py
├── datasets/
│   └── questions.json
└── cobalt.toml
```

## Step 1: Create the Dataset

`datasets/questions.json`:

```json
[
  {"input": "What is the capital of France?",              "expected_output": "Paris",        "category": "geography"},
  {"input": "Who wrote '1984'?",                          "expected_output": "George Orwell", "category": "literature"},
  {"input": "What is the speed of light (m/s)?",          "expected_output": "299792458",     "category": "science"},
  {"input": "What year did World War II end?",            "expected_output": "1945",          "category": "history"},
  {"input": "What is the largest planet in the solar system?", "expected_output": "Jupiter",  "category": "science"}
]
```

## Step 2: Write the Experiment

`experiments/qa-agent.cobalt.py`:

```python
import asyncio
import openai
from cobalt import Dataset, Evaluator, EvalContext, EvalResult, ExperimentResult, experiment

client = openai.AsyncOpenAI()

# ---- Agent ----
async def answer_question(question: str) -> dict:
    start = __import__("time").monotonic()
    resp = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Answer concisely and factually."},
            {"role": "user",   "content": question},
        ],
        max_tokens=100,
    )
    return {
        "answer": resp.choices[0].message.content or "",
        "tokens": resp.usage.total_tokens if resp.usage else 0,
        "latency_ms": (__import__("time").monotonic() - start) * 1000,
    }

# ---- Dataset ----
dataset = Dataset.from_file("./datasets/questions.json")

# ---- Evaluators ----
def contains_answer(ctx: EvalContext) -> EvalResult:
    expected = str(ctx.item.get("expected_output", "")).lower()
    score = 1.0 if expected in str(ctx.output).lower() else 0.0
    return EvalResult(score=score, reason=f'Expected "{expected}"')

def conciseness(ctx: EvalContext) -> EvalResult:
    words = len(str(ctx.output).split())
    score = 1.0 if words <= 50 else max(0.0, 1.0 - (words - 50) / 50)
    return EvalResult(score=score, reason=f"{words} words (target ≤50)")

evaluators = [
    Evaluator(name="contains-answer", type="function", fn=contains_answer),
    Evaluator(name="conciseness",     type="function", fn=conciseness),
    Evaluator(
        name="factual-accuracy",
        type="llm-judge",
        model="gpt-4o-mini",
        scoring="boolean",
        prompt="""Is this answer factually accurate?

Question: {{input}}
Expected: {{expected_output}}
Answer: {{output}}

Reply PASS or FAIL.""",
    ),
]

# ---- Runner ----
async def runner(ctx) -> ExperimentResult:
    result = await answer_question(ctx.item["input"])
    return ExperimentResult(
        output=result["answer"],
        metadata={
            "tokens": result["tokens"],
            "latency_ms": result["latency_ms"],
            "category": ctx.item.get("category"),
        },
    )

# ---- Main ----
async def main():
    await experiment(
        "qa-agent",
        dataset,
        runner,
        evaluators=evaluators,
        concurrency=3,
        timeout=30.0,
        tags=["qa", "gpt-4o-mini", "v1"],
    )

asyncio.run(main())
```

## Step 3: Configure

`cobalt.toml`:

```toml
[judge]
model = "gpt-4o-mini"
provider = "openai"

[experiment]
concurrency = 3
timeout = 30
```

## Step 4: Run

```bash
export OPENAI_API_KEY="sk-..."
cobalt run --file experiments/qa-agent.cobalt.py
```

Expected output:

```
Experiment: qa-agent  abc123
Items: 5 | Duration: 8.2s | Avg latency: 1640ms

 Evaluator        Avg  Min  Max  P95
 contains-answer  1.00 1.00 1.00 1.00
 conciseness      0.97 0.92 1.00 1.00
 factual-accuracy 0.92 0.80 1.00 1.00
```

## Step 5: Explore Results

```bash
# Terminal history table
cobalt history

# Visual dashboard
cobalt ui

# Compare two runs
cobalt compare <run-id-1> <run-id-2>
```

## Next Steps

- [Understanding Results](understanding-results.md)
- [Evaluators](../evaluators.md)
- [CI/CD Integration](../ci-mode.md)
