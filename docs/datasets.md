# Datasets

`Dataset` loads, transforms, and passes test data to experiments. All transformations are immutable and chainable.

## Creating Inline

```python
from cobalt import Dataset

dataset = Dataset.from_items([
    {"input": "What is 2+2?",      "expected_output": "4"},
    {"input": "Capital of France?", "expected_output": "Paris"},
])
```

Items are plain dicts. Use whatever keys your runner expects.

---

## Loading from Files

### Auto-detect format

```python
dataset = Dataset.from_file("./data/questions.csv")
```

Picks the loader from the file extension (`.json`, `.jsonl`, `.csv`). Falls back to JSON for unknown extensions.

### JSON

Accepts a JSON array or an object with an `items` key:

```python
dataset = Dataset.from_json("./data/questions.json")
```

```json
[
  {"input": "...", "expected_output": "..."},
  {"input": "...", "expected_output": "..."}
]
```

```json
{ "items": [ ... ] }
```

### JSONL

One JSON object per line:

```python
dataset = Dataset.from_jsonl("./data/questions.jsonl")
```

```jsonl
{"input": "question 1", "expected_output": "answer 1"}
{"input": "question 2", "expected_output": "answer 2"}
```

### CSV

First row is treated as headers. All values are strings.

```python
dataset = Dataset.from_csv("./data/questions.csv")
```

```csv
input,expected_output,category
"What is 2+2?","4","math"
"Capital of France?","Paris","geography"
```

---

## Loading from Remote Sources

### HTTP/HTTPS

```python
dataset = await Dataset.from_remote("https://example.com/qa.jsonl")
```

Format is auto-detected (JSON array or JSONL).

### Platform Integrations

| Loader | Signature | Env Variables |
|--------|-----------|---------------|
| **Langfuse** | `Dataset.from_langfuse(name, ...)` | `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` |
| **LangSmith** | `Dataset.from_langsmith(name, ...)` | `LANGSMITH_API_KEY` |
| **Braintrust** | `Dataset.from_braintrust(project, dataset, ...)` | `BRAINTRUST_API_KEY` |
| **Basalt** | `Dataset.from_basalt(dataset_id, ...)` | `BASALT_API_KEY` |

All platform loaders return `Awaitable[Dataset]` and read credentials from keyword args first, then env vars.

```python
dataset = await Dataset.from_langfuse("my-eval-set")

dataset = await Dataset.from_langsmith("my-dataset")

dataset = await Dataset.from_braintrust("my-project", "my-dataset")

dataset = await Dataset.from_basalt("dataset-abc123")
```

Optional kwargs override env vars:

```python
dataset = await Dataset.from_langfuse(
    "my-eval-set",
    public_key="pk-...",
    secret_key="sk-...",
    base_url="https://us.cloud.langfuse.com",
)
```

---

## Transformations

All transformations are **immutable** — they return new `Dataset` instances.

### filter

```python
# Keep only high-priority items
dataset = dataset.filter(lambda item, i: item.get("priority") == "high")
```

### map

```python
# Normalise keys
dataset = dataset.map(lambda item, i: {
    "input": item["question"],
    "expected_output": item["answer"],
    "index": i,
})
```

### sample

Random sample of N items (without replacement):

```python
dataset = dataset.sample(50)
```

### slice

```python
# First 20 items
dataset = dataset.slice(0, 20)

# Items 10–30
dataset = dataset.slice(10, 30)
```

### Chaining

```python
dataset = (
    Dataset.from_file("./data/qa.jsonl")
    .filter(lambda item, _: item.get("difficulty") == "hard")
    .sample(100)
    .slice(0, 50)
)
```

---

## Accessing Items

```python
items = dataset.items()   # list[dict]
count = len(dataset)      # int
for item in dataset:      # iterable
    print(item["input"])
```

---

## Best Practices

- **Version your datasets** — keep `v1/`, `v2/` subdirectories for reproducibility.
- **Use JSONL for large datasets** — easier to append and stream.
- **Filter before sampling** — `filter().sample()` is more intentional than `sample().filter()`.
- **Include metadata** — add `category`, `difficulty`, `source` fields; they're available in evaluators and metadata.
