# FREE Model + Kanban Integration — Operational Lessons (2026-05-24)

## Model ID Canonical Forms (Critical)

When matching against `data/ilma_dashboard.db`:

| Model | DB Canonical Form | Common Mistake | Why |
|-------|-------------------|----------------|-----|
| DeepSeek-R1 | `deepseek-r1` | `DeepSeek-R1` or `nvidia/DeepSeek-R1` | DB stores lowercase bare form for nvidia rows; no provider prefix |
| Qwen2.5-Coder-32B | `qwen2.5-coder-32b-instruct` | `Qwen2.5-Coder-32B` | DB uses lowercase; title case fails case-insensitive matching |
| Llama Vision | `llama-3.2-11b-vision-instruct` | `openrouter/gpt-4o-mini:free` | openrouter free pool has only 25 models; gpt-4o-mini:free not among them |
| MiniMax-M2.7 | `minimax/minimax-m2.7` | — | Full form with provider prefix |

**Matching rule:** The optimizer uses case-insensitive partial matching — checks if model_id is contained within canonical OR canonical is contained within model_id. So `qwen2.5-coder-32b-instruct` matches `nvidia/qwen2.5-coder-32b-instruct` and vice versa.

## Vision Model — Not openrouter

The openrouter FREE pool has exactly 25 models. `gpt-4o-mini:free` is NOT in that pool. For vision tasks, use:
- **Primary:** `nvidia/llama-3.2-11b-vision-instruct` (verified FREE on nvidia)
- **Fallback:** `nvidia/llama-3.2-11b-vision-instruct` is the ONLY verified free vision model

## FREE Model Pool (163 Total)

| Provider | Count | Best For |
|----------|-------|----------|
| nvidia | 131 | Reasoning, coding, heavy tasks, vision |
| minimax | 6 | Fast general, writing |
| openrouter | 25 | Free reasoning (o3-mini-high:free) |
| blackbox | 1 | Multimodal fallback |

## Kanban Worker Model Routing

`ilma_kanban_free_model_optimizer.py` provides the routing:

```python
from ilma_kanban_free_model_optimizer import (
    get_best_free_for_task,
    get_model_for_task_body,
    get_fallback_chain,
    get_kanban_stats
)

# By task type
model = get_best_free_for_task("reasoning_xhigh")
# → ("nvidia", "deepseek-r1")

model = get_best_free_for_task("heavy_coding")
# → ("nvidia", "qwen2.5-coder-32b-instruct")

model = get_best_free_for_task("vision")
# → ("nvidia", "llama-3.2-11b-vision-instruct")

model = get_best_free_for_task("fast_tasks")
# → ("minimax", "minimax-m2.7")

# From body text — auto-infers task type
model = get_model_for_task_body("Debug this API endpoint, stack trace attached")
# → ("nvidia", "qwen2.5-coder-32b-instruct") — heavy_coding

model = get_model_for_task_body("Write a research paper about AI agents")
# → ("nvidia", "deepseek-r1") — reasoning_xhigh

model = get_model_for_task_body("Quick translation, 500 words")
# → ("minimax", "minimax-m2.7") — fast_tasks

# Fallback chain
chain = get_fallback_chain("heavy_coding")
# → [("nvidia", "qwen2.5-coder-32b-instruct"), ("nvidia", "deepseek-r1"), ("minimax", "minimax-m2.7"), ...]

# Stats
stats = get_kanban_stats()
# → {total: 163, by_provider: {"nvidia": 131, "minimax": 6, ...}}
```

## Task Type → Best FREE Model

| Task Type | Provider | Model ID |
|-----------|----------|----------|
| reasoning_xhigh | nvidia | deepseek-r1 |
| heavy_coding | nvidia | qwen2.5-coder-32b-instruct |
| medium_coding | nvidia | qwen2.5-coder-32b-instruct |
| research | nvidia | deepseek-r1 |
| vision | nvidia | llama-3.2-11b-vision-instruct |
| general | minimax | minimax-m2.7 |
| fast_tasks | minimax | minimax-m2.7 |
| writing | minimax | minimax-m2.7 |

## ILMA Kanban Integration Wiring

```python
from ilma_kanban_integration import ILMAKanban

kanban = ILMAKanban()

# create() auto-selects FREE model from body
task = kanban.create(
    title="Research task",
    body="Analyze this research paper and summarize findings",
    assignee="researcher"
)
# Worker gets deepseek-r1 automatically

# fan_out() — each worker gets its own FREE model
parent, children = kanban.fan_out(
    tasks=["Task A", "Task B", "Task C"],
    body_prefix="Research: ",
    assignee="researcher"
)
# Each child worker auto-selects best free model from its body
```

## Provider URL Fixes (from integration testing)

| Provider | Wrong URL | Correct URL | Status |
|----------|-----------|-------------|--------|
| minimax | `api.minimax.chat` | `api.minimax.io` | 200 OK |
| perplexity | `/models` | `/v1/models` | 200 OK |
| together | `.Together.ai` | `.together.xyz` | CF 1010 (blocked) |
| aimlapi | `gateway.aimlapi.com` | N/A (DNS fail) | Unreachable |

## Git Commit

`commit 0795d7c` — "feat(kanban): ILMA Kanban Free Model Optimizer — 163 FREE models end-to-end"