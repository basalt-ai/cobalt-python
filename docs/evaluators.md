# Evaluators

Evaluators score your agent's output. Cobalt has three built-in types and supports custom plugins.

Every evaluator returns an `EvalResult`:

```python
@dataclass
class EvalResult:
    score: float          # 0.0 – 1.0
    reason: str | None = None
    chain_of_thought: str | None = None
```

Evaluators never raise. On error they return `EvalResult(score=0.0, reason="error message")`.

## Quick Reference

| Type | Use Case | Requires API Key |
|------|----------|-----------------|
| `llm-judge` | Natural-language criteria evaluated by an LLM | Yes (OpenAI or Anthropic) |
| `function` | Custom Python logic (sync or async) | No |
| `similarity` | TF-IDF cosine similarity against a reference field | No |

---

## Creating Evaluators

```python
from cobalt import Evaluator

ev = Evaluator(name="my-check", type="function", fn=my_fn)
```

Pass evaluators to `experiment()`:

```python
await experiment("my-run", dataset, runner, evaluators=[ev])
```

---

## LLM Judge

Uses an LLM to score output. Supports template variables `{{input}}`, `{{output}}`, `{{expected_output}}`, and any dataset field.

Provider is auto-detected: models starting with `claude` use Anthropic; everything else uses OpenAI.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `prompt` | `str` | *required* | Evaluation prompt with `{{variable}}` placeholders |
| `model` | `str` | `"gpt-4o-mini"` | LLM to use |
| `scoring` | `"boolean" \| "scale"` | `"boolean"` | Boolean = PASS/FAIL, scale = 0.0–1.0 |
| `chain_of_thought` | `bool` | `True` for boolean | Include reasoning trace in result |

### Boolean (Pass/Fail)

```python
Evaluator(
    name="correctness",
    type="llm-judge",
    prompt="""Does the output correctly answer the question?

Question: {{input}}
Expected: {{expected_output}}
Answer: {{output}}

Reply PASS or FAIL.""",
    scoring="boolean",
)
```

### Scale (0.0 – 1.0)

```python
Evaluator(
    name="quality",
    type="llm-judge",
    scoring="scale",
    model="gpt-4o",
    prompt="""Rate the response quality from 0.0 to 1.0.

Question: {{input}}
Response: {{output}}

Return a number between 0.0 and 1.0.""",
)
```

### Using Claude

```python
Evaluator(
    name="helpfulness",
    type="llm-judge",
    model="claude-3-5-haiku-20241022",
    prompt="Is the response helpful? {{output}}\nPASS or FAIL.",
)
```

---

## Function Evaluator

Run arbitrary Python logic — sync or async. Score must be in `[0.0, 1.0]`.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `fn` | `Callable` | *required* | `(EvalContext) -> EvalResult \| Awaitable[EvalResult]` |

```python
from cobalt import Evaluator, EvalContext, EvalResult

def exact_match(ctx: EvalContext) -> EvalResult:
    expected = str(ctx.item.get("expected_output", "")).lower()
    score = 1.0 if expected in str(ctx.output).lower() else 0.0
    return EvalResult(score=score, reason=f"Expected: {expected}")

ev = Evaluator(name="exact-match", type="function", fn=exact_match)
```

### Async function evaluator

```python
import aiohttp

async def api_check(ctx: EvalContext) -> EvalResult:
    async with aiohttp.ClientSession() as s:
        resp = await s.post("https://my-grader.example.com/score", json={"output": ctx.output})
        data = await resp.json()
    return EvalResult(score=data["score"], reason=data.get("reason"))

ev = Evaluator(name="api-grader", type="function", fn=api_check)
```

### Conciseness example

```python
def conciseness(ctx: EvalContext) -> EvalResult:
    words = len(str(ctx.output).split())
    score = 1.0 if words <= 50 else max(0.0, 1.0 - (words - 50) / 50)
    return EvalResult(score=score, reason=f"{words} words (target ≤50)")
```

---

## Similarity Evaluator

Computes TF-IDF cosine similarity between the model output and a reference field in the dataset item.

> For production use, swap the TF-IDF backend for OpenAI embeddings by overriding the `fn` with a custom function evaluator.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `field` | `str` | *required* | Dataset item field to compare against |
| `threshold` | `float` | `0.8` | Similarity ≥ threshold → score = 1.0; below → proportional |
| `distance` | `"cosine" \| "dot"` | `"cosine"` | Distance metric |

```python
Evaluator(
    name="semantic-similarity",
    type="similarity",
    field="expected_output",
    threshold=0.75,
)
```

---

## Custom Evaluator Types

Register new evaluator types globally via `cobalt.evaluator.registry`:

```python
from cobalt.evaluator import registry
from cobalt.types import EvalContext, EvalResult

async def my_handler(config, context: EvalContext, **kwargs) -> EvalResult:
    # config contains all keys from the Evaluator(...)
    threshold = config.get("threshold", 0.5)
    score = 1.0 if len(str(context.output)) > threshold else 0.0
    return EvalResult(score=score)

registry.register("length-check", my_handler)

# Then use it:
Evaluator(name="length", type="length-check", threshold=20)
```

---

## Running Multiple Evaluators

```python
evaluators = [
    Evaluator(name="exact-match",  type="function",  fn=exact_match),
    Evaluator(name="conciseness",  type="function",  fn=conciseness),
    Evaluator(name="llm-accuracy", type="llm-judge", prompt="Is this accurate? {{output}} PASS/FAIL."),
    Evaluator(name="similarity",   type="similarity", field="expected_output"),
]

report = await experiment("my-run", dataset, runner, evaluators=evaluators)
```

Each evaluator runs independently per item. Scores appear in `report.summary.scores`.

---

## Best Practices

- **Use function evaluators** for deterministic checks (exact match, word count, regex) — faster and free.
- **Use LLM judge** for subjective metrics (helpfulness, tone, factual accuracy).
- **Use `gpt-4o-mini`** for LLM judge by default — cheaper, fast, good enough.
- **Name evaluators clearly** — names appear in history, dashboard, and CI output.
- **Keep prompts focused** — one criterion per evaluator is easier to interpret than a combined score.
