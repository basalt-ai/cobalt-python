# Configuration

Cobalt is configured via `cobalt.toml` in your project root.

## Config File

```toml
[judge]
model    = "gpt-4o-mini"
provider = "openai"
# api_key = "sk-..."  # or set OPENAI_API_KEY / ANTHROPIC_API_KEY env var

[experiment]
test_dir    = "./experiments"
test_match  = ["**/*.cobalt.py"]
concurrency = 5
timeout     = 30.0   # seconds
reporters   = ["cli"]

[dashboard]
port = 4000
open = true

[langfuse]
public_key = ""
secret_key = ""
base_url   = "https://cloud.langfuse.com"

[langsmith]
api_key  = ""
base_url = "https://api.smith.langchain.com"

[braintrust]
api_key  = ""
base_url = "https://api.braintrust.dev"

[basalt]
api_key  = ""
base_url = "https://api.getbasalt.ai"
```

Cobalt searches for `cobalt.toml` in the current directory and every parent until found.

---

## Full Reference

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `judge.model` | `str` | `"gpt-4o-mini"` | LLM for LLM-judge evaluators |
| `judge.provider` | `"openai" \| "anthropic"` | `"openai"` | LLM provider |
| `judge.api_key` | `str` | env var | API key (overrides `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`) |
| `experiment.test_dir` | `str` | `"./experiments"` | Glob root for `cobalt run` discovery |
| `experiment.test_match` | `list[str]` | `["**/*.cobalt.py"]` | Glob patterns for experiment files |
| `experiment.concurrency` | `int` | `5` | Max parallel item executions |
| `experiment.timeout` | `float` | `30.0` | Per-item timeout in seconds |
| `reporters` | `list[str]` | `["cli"]` | Output reporters |
| `dashboard.port` | `int` | `4000` | `cobalt ui` server port |
| `dashboard.open` | `bool` | `true` | Auto-open browser on `cobalt ui` |

### Reporter Types

| Reporter | Description |
|----------|-------------|
| `"cli"` | Rich terminal output — scores table, colour-coded |
| `"json"` | Save full JSON report to `~/.cobalt/results/` (always on) |

---

## Integration Config Sections

### Langfuse

```toml
[langfuse]
public_key = "pk-lf-..."
secret_key = "sk-lf-..."
base_url   = "https://cloud.langfuse.com"
```

Or use env vars: `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`.

### LangSmith

```toml
[langsmith]
api_key = "ls-..."
```

Or: `LANGSMITH_API_KEY`.

### Braintrust

```toml
[braintrust]
api_key = "..."
```

Or: `BRAINTRUST_API_KEY`.

### Basalt

```toml
[basalt]
api_key = "..."
```

Or: `BASALT_API_KEY`.

---

## Python API

Load config programmatically:

```python
from cobalt.config import load_config, define_config, CobaltConfig, JudgeConfig

config = load_config()          # reads cobalt.toml from cwd
config = load_config("/my/dir") # reads from a specific directory

# Type-safe construction
config = CobaltConfig(
    judge=JudgeConfig(model="gpt-4o", provider="openai"),
    concurrency=10,
    timeout=60.0,
)
```

Pass config overrides to `experiment()`:

```python
report = await experiment(
    "my-run", dataset, runner,
    evaluators=evaluators,
    concurrency=2,    # overrides cobalt.toml
    timeout=60.0,
)
```

---

## Environment Variables

| Variable | Used for |
|----------|---------|
| `OPENAI_API_KEY` | LLM judge (OpenAI) + cost estimation |
| `ANTHROPIC_API_KEY` | LLM judge (Anthropic / Claude) |
| `COBALT_API_KEY` | Override for any provider (checked first) |
| `LANGFUSE_PUBLIC_KEY` | Langfuse dataset loader |
| `LANGFUSE_SECRET_KEY` | Langfuse dataset loader |
| `LANGSMITH_API_KEY` | LangSmith dataset loader |
| `BRAINTRUST_API_KEY` | Braintrust dataset loader |
| `BASALT_API_KEY` | Basalt dataset loader |
