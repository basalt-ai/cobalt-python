# MCP Integration

Cobalt exposes a native [Model Context Protocol](https://modelcontextprotocol.io) (MCP) server, letting Claude and other MCP clients run experiments, analyse results, and generate tests — all via natural language.

## Quick Start

### 1. Start the MCP Server

```bash
cobalt mcp
```

Runs in stdio mode, ready for any MCP client to connect.

### 2. Configure Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "cobalt": {
      "command": "cobalt",
      "args": ["mcp"],
      "env": {
        "OPENAI_API_KEY": "sk-..."
      }
    }
  }
}
```

Or with `uvx` (no global install needed):

```json
{
  "mcpServers": {
    "cobalt": {
      "command": "uvx",
      "args": ["cobalt-ai", "mcp"],
      "env": {
        "OPENAI_API_KEY": "sk-..."
      }
    }
  }
}
```

Restart Claude Desktop after saving.

---

## Tools

Claude can call these tools interactively.

| Tool | Purpose | Cost |
|------|---------|------|
| `cobalt_run` | Run an experiment file, return full results | Runs your agent + evaluators |
| `cobalt_results` | List runs or get details for a specific run | Free (reads files) |
| `cobalt_compare` | Compare two runs, return delta / regressions | Free (reads files) |
| `cobalt_generate` | Analyse agent source, generate `.cobalt.py` | One LLM call |

### cobalt_run

```
"Run experiments/qa-agent.cobalt.py and show me the scores"
```

Parameters:
- `file` *(required)* — path to `.cobalt.py` experiment file
- `concurrency` *(optional)* — override concurrency

Returns: full `ExperimentReport` (scores, items, latencies).

### cobalt_results

```
"Show me results for run abc123"
"List my last 5 runs"
```

Parameters:
- `run_id` — detail view for a specific run
- `limit` — number of runs to list (default 10)
- `experiment` — filter by experiment name

### cobalt_compare

```
"Compare run abc123 to def456 — any regressions?"
```

Parameters:
- `run_a` *(required)* — baseline run ID
- `run_b` *(required)* — candidate run ID

Returns: per-evaluator deltas, regression/improvement lists, top changed items.

**Regression threshold**: ±5% triggers classification.

### cobalt_generate

```
"I wrote a new chatbot in src/chatbot.py. Generate tests for it."
```

Parameters:
- `agent_file` *(required)* — path to Python agent source
- `output_file` *(optional)* — output path (default: `<agent>.cobalt.py`)
- `dataset_size` *(optional)* — number of test cases (default 10)

Uses the configured `judge.model` to analyse the code and generate a complete `.cobalt.py` file.

---

## Resources

Read-only data sources Claude can access without running anything.

| Resource | Content |
|----------|---------|
| `cobalt://config` | Current `cobalt.toml` (API keys redacted) |
| `cobalt://experiments` | All `.cobalt.py` files discovered in `test_dir` |
| `cobalt://latest-results` | Most recent run per experiment |

### cobalt://config

```
"What's my Cobalt configuration?"
"Am I using the right judge model?"
```

Returns judge model, concurrency, timeout, reporters — API keys are always redacted.

### cobalt://experiments

```
"What experiments do I have?"
"Do I have tests for my summarizer?"
```

Returns list of `.cobalt.py` files with paths and names.

### cobalt://latest-results

```
"How did my tests perform recently?"
"Are any experiments failing?"
```

Returns one result summary per experiment (most recent run), with avg scores per evaluator.

---

## Prompts

Structured multi-step workflows. These guide Claude through analysis tasks.

| Prompt | When to use |
|--------|-------------|
| `improve-agent` | Scores are low — get code fix suggestions |
| `generate-tests` | Need better test coverage |
| `regression-check` | Before deploying — detect regressions |

### improve-agent

Arguments:
- `run_id` *(optional)* — run to analyse (uses latest if omitted)

Claude will:
1. Load the run results
2. Identify failure patterns (items scoring < 0.7)
3. Suggest 3 specific code improvements with before/after snippets
4. Estimate score delta per improvement

```
"Analyse my latest run and tell me how to fix the failures"
```

### generate-tests

Arguments:
- `experiment_file` *(required)* — path to experiment to enhance
- `focus` *(optional)* — `edge-cases` | `adversarial` | `coverage` (default)

Claude will:
1. Read the existing dataset
2. Identify coverage gaps
3. Generate 8–12 new test items as JSON

```
"Generate adversarial test cases for experiments/chatbot.cobalt.py"
```

### regression-check

Arguments:
- `baseline_run_id` *(required)*
- `current_run_id` *(required)*

Claude will:
1. Load and compare both runs
2. Apply thresholds: > 10% drop → FAIL, 5–10% → WARN, < 5% → PASS
3. Output: verdict + root-cause hypothesis + recommendation

```
"Regression check between abc123 (baseline) and def456 (candidate)"
```

**Verdict levels:**
- ✅ **PASS** — no significant regressions
- ⚠️ **WARN** — minor regressions (5–10% drop)
- ❌ **FAIL** — major regressions (> 10% drop or new failures)

---

## Common Workflows

### Run → Analyse → Fix

```
👤 "Run experiments/qa.cobalt.py and analyse any failures"

🤖 [cobalt_run] → Results: 3/20 items below 0.7 on factual-accuracy
🤖 [improve-agent prompt] → 3 specific fixes + expected deltas

👤 "Apply those fixes and re-run"

🤖 [cobalt_run] → New results
🤖 [regression-check] → PASS ✅ — factual-accuracy +18%
```

### Discover → Generate → Test

```
👤 "I have a new summariser in src/summariser.py. Bootstrap tests for it."

🤖 [cobalt://experiments] → No existing tests found
🤖 [cobalt_generate] → Generated experiments/summariser.cobalt.py
🤖 [cobalt_run] → Initial results: 0.82 avg
```

### Pre-Deploy Gate

```
👤 "Check if the new prompt caused any regressions before I ship"

🤖 [cobalt_compare] → Delta table
🤖 [regression-check] → WARN ⚠️ — conciseness -6%

👤 "Root cause?"

🤖 Shorter max_tokens likely causing truncation on complex questions.
   Recommend: increase max_tokens from 100 → 200 before deploy.
```

---

## Architecture

```
┌─────────────────┐
│  Claude / MCP   │
│     Client      │
└────────┬────────┘
         │ MCP Protocol (stdio)
┌────────▼────────┐
│  cobalt mcp     │
│  (MCP server)   │
├─────────────────┤
│ Tools (4)       │
│ Resources (3)   │
│ Prompts (3)     │
└────────┬────────┘
         │ Direct Python import
┌────────▼────────┐
│  Cobalt Core    │
│  experiment /   │
│  evaluators /   │
│  storage        │
└─────────────────┘
```

The MCP server is a thin async wrapper around Cobalt's core — no extra processes or network services needed.

---

## Troubleshooting

### "cobalt mcp not responding"

Check the server starts cleanly:

```bash
cobalt mcp  # should block silently waiting for MCP messages
```

### "cobalt_generate fails"

Requires `OPENAI_API_KEY` (or `ANTHROPIC_API_KEY` + `claude-*` judge model):

```bash
export OPENAI_API_KEY="sk-..."
cobalt mcp
```

### "No experiments found"

Ensure `cobalt.toml` exists and `test_dir` points to your experiments folder.

---

## See Also

- [Tools Reference](#tools) — Full parameter docs
- [Resources Reference](#resources) — Available read-only data
- [Prompts Reference](#prompts) — Guided workflows
- [Configuration](configuration.md) — cobalt.toml judge model setup
- [CI/CD Integration](ci-mode.md) — Automate with GitHub Actions
