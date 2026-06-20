---
name: ilma-batch-processing
description: Hermes Batch Runner — parallel RL training data generation with checkpointing, toolset distributions, and ShareGPT-format trajectory output. SSS Tier.
version: 1.0.0
category: mlops
platforms:
  - linux
  - macos
metadata:
  hermes:
    tags: [batch, rl, training, trajectory, parallel, checkpointing]
    category: mlops
---

# ILMA Batch Processing — RL Training Data Generation

## Overview

Hermes batch processing runs the agent across hundreds or thousands of prompts in parallel, generating structured trajectory data for RL training or evaluation.

```bash
python batch_runner.py \
    --dataset_file=data/prompts.jsonl \
    --batch_size=10 \
    --run_name=my_run \
    --model=anthropic/claude-sonnet-4.6 \
    --num_workers=4
```

## Use Cases

| Use Case | Description |
|----------|-------------|
| **RL Training Data** | Generate ShareGPT-format trajectories with tool usage stats |
| **Model Evaluation** | Test how well a model uses tools across standardized prompts |
| **Benchmark** | Run prompts across specific container images per prompt |
| **Data Augmentation** | Generate diverse problem-solving trajectories |

---

## Dataset Format

Input is JSONL (one JSON per line). Each entry must have `prompt`:

```jsonl
{"prompt": "Write a Python function that finds the longest palindromic substring"}
{"prompt": "Create a REST API endpoint for user authentication using Flask"}
{"prompt": "Debug this error: TypeError: cannot unpack non-iterable NoneType object"}
```

**Optional fields:**
- `image` or `docker_image` — container image for sandbox (Docker, Modal, Singularity)
- `cwd` — working directory override

```jsonl
{"prompt": "Install numpy and compute eigenvalues", "image": "python:3.11-slim"}
{"prompt": "Compile this Rust program", "image": "rust:1.75"}
{"prompt": "Set up Node.js Express server", "image": "node:20-alpine", "cwd": "/app"}
```

---

## Configuration Options

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--dataset_file` | (required) | Path to JSONL dataset |
| `--batch_size` | (required) | Prompts per batch |
| `--run_name` | (required) | Run name (output dir + checkpointing) |
| `--distribution` | `"default"` | Toolset distribution to sample from |
| `--model` | `claude-sonnet-4.6` | Model to use |
| `--base_url` | `https://openrouter.ai/api/v1` | API base URL |
| `--api_key` | (env var) | API key for model |
| `--max_turns` | `10` | Max tool-calling iterations per prompt |
| `--num_workers` | `4` | Parallel worker processes |
| `--resume` | `false` | Resume from checkpoint |
| `--verbose` | `false` | Enable verbose logging |
| `--max_samples` | all | Only process first N samples |
| `--max_tokens` | model default | Max tokens per model response |

### Provider Routing

| Parameter | Description |
|-----------|-------------|
| `--providers_allowed` | Comma-separated allowed providers (e.g., `"anthropic,openai"`) |
| `--providers_ignored` | Comma-separated ignored providers |
| `--providers_order` | Comma-separated preferred provider order |
| `--provider_sort` | Sort by `price`, `throughput`, or `latency` |

### Reasoning Control

| Parameter | Description |
|-----------|-------------|
| `--reasoning_effort` | Effort level: `none`, `minimal`, `low`, `medium`, `high`, `xhigh` |
| `--reasoning_disabled` | Completely disable reasoning/thinking tokens |

### Advanced Options

| Parameter | Description |
|-----------|-------------|
| `--ephemeral_system_prompt` | System prompt during execution NOT saved to trajectories |
| `--log_prefix_chars` | Characters to show in log previews (default: 100) |
| `--prefill_messages_file` | JSON file with prefill messages for few-shot priming |

---

## Toolset Distributions

Each prompt gets a randomly sampled set of toolsets from a **distribution**:
- Ensures training data covers diverse tool combinations
- Use `--list_distributions` to see all available
- Sampler flips each toolset independently, guarantees at least one enabled

---

## Output Format

All output goes to `data/<run_name>/`:

```text
data/my_run/
├── trajectories.jsonl    # Combined final output (all batches merged)
├── batch_0.jsonl         # Individual batch results
├── batch_1.jsonl
├── ...
├── checkpoint.json       # Resume checkpoint
└── statistics.json       # Aggregate tool usage stats
```

### Trajectory Format

Each line in `trajectories.jsonl`:

```json
{
  "prompt_index": 42,
  "conversations": [
    {"from": "human", "value": "Write a function..."},
    {"from": "gpt", "value": "I'll create that function...", "tool_calls": [...]},
    {"from": "tool", "value": "..."},
    {"from": "gpt", "value": "Here's the completed function..."}
  ],
  "metadata": {
    "batch_num": 2,
    "timestamp": "2026-01-15T10:30:00",
    "model": "anthropic/claude-sonnet-4.6"
  },
  "completed": true,
  "partial": false,
  "api_calls": 3,
  "toolsets_used": ["terminal", "file"],
  "tool_stats": {
    "terminal": {"count": 2, "success": 2, "failure": 0},
    "read_file": {"count": 1, "success": 1, "failure": 0}
  },
  "tool_error_counts": {
    "terminal": 0,
    "read_file": 0
  }
}
```

Uses ShareGPT-like format with `from` and `value` fields.

---

## Checkpointing

- **Checkpoint file:** Saved after each batch completes, tracking prompt indices done
- **Content-based resume:** On `--resume`, runner scans existing batch files and matches completed prompts by content (not just indices)
- **Failed prompts:** Only successfully completed prompts marked done — failed prompts retried on resume
- **Batch merging:** On completion, all batch files merged into single `trajectories.jsonl`

### How Resume Works

```
1. Scan all batch_*.jsonl files for completed prompts (by content matching)
2. Filter dataset to exclude already-completed prompts
3. Re-batch remaining prompts
4. Process only remaining prompts
5. Merge all batch files (old + new) into final output
```

---

## Quality Filtering

Automatic quality filtering applied:
- **No-reasoning filter:** Samples where zero assistant turns contain reasoning → discarded
- **Corrupted entry filter:** Entries with hallucinated tool names → filtered during final merge
- **Reasoning statistics:** Tracks % of turns with/without reasoning across run

---

## Statistics

After completion, runner prints:
- Tool usage: call counts, success/failure rates per tool
- Reasoning coverage: % of assistant turns with reasoning
- Samples discarded: count filtered for lacking reasoning
- Duration: total processing time

Saved to `statistics.json` for programmatic analysis.

---

## ILMA Batch Pattern

For ILMA to implement batch processing:

```python
# ilma_batch_runner.py (future implementation)
# - JSONL dataset reader
# - ThreadPoolExecutor for parallel workers
# - Checkpoint management
# - Trajectory formatter (ShareGPT format)
# - Quality filtering
# - Statistics aggregation

# Example: generate training data for code completion
ilma_batch_run(
    dataset="data/code_prompts.jsonl",
    run_name="code_v1",
    model="minimax-m2.7",
    num_workers=4,
    max_turns=15,
    distribution="coding"
)
```

---

## Auto-Trigger

Load this skill when:
- User asks to "generate training data", "run batch prompts", "parallel inference"
- User mentions "RL training", "trajectory generation", "batch processing"
- User wants to "test model across thousands of prompts"

---

*Hermes v0.13.0 — Batch Processing feature*
*Integrated into ILMA v3.3*