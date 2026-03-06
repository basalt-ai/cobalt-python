# Installation

Install and configure cobalt-python in your project.

## Prerequisites

- Python 3.11+
- `pip`, `uv`, or `poetry`
- An OpenAI or Anthropic API key (for LLM evaluators)

## Install

```bash
pip install cobalt-ai
```

Or with uv (recommended):

```bash
uv add cobalt-ai
```

With the local dashboard:

```bash
pip install 'cobalt-ai[dashboard]'
```

## Initialize a New Project

```bash
cobalt init
```

This scaffolds:

```
my-project/
├── experiments/
│   └── my-agent.cobalt.py   # Example experiment
├── cobalt.toml              # Configuration
└── ~/.cobalt/               # Runtime storage (history + results)
    ├── results/
    └── history.db
```

## Set Your API Key

```bash
export OPENAI_API_KEY="sk-..."
# Or for Anthropic
export ANTHROPIC_API_KEY="sk-ant-..."
```

Or set it in `cobalt.toml`:

```toml
[judge]
api_key = "sk-..."
```

## Verify

```bash
cobalt --help
cobalt run --file experiments/my-agent.cobalt.py
```

## Next Steps

- [Quickstart](quickstart.md) — 5-minute walkthrough
- [Your First Experiment](first-experiment.md) — Detailed guide
- [Configuration](../configuration.md) — All config options
