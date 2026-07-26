# Sub-Agent Router Role Names — Critical Bug Pattern

## The Problem

Most ILMA sessions that test SubAgentRouter FAIL because they use simple role strings instead of the full role names.

## The Discovery

When testing `ilma_subagent_router.py` in session 2026-05-18:

```python
# ❌ WRONG — simple strings (what most tests do)
router.select_model(role="general", task_category="general")
# → Returns FALLBACK model (not the primary configured route)

# ✅ CORRECT — full role names (what the registry actually uses)
router.select_model(role="general_subagent", task_category="general")
# → Returns PRIMARY model: useai-qwen-2-72b
```

## Why It Fails

The SubAgentRouter reads role→model mappings from `ModelRegistry.get_subagent_routes()`, which stores keys like `"coding_subagent"`, NOT `"coding"`.

When you pass a simple role like `"general"`, the router:
1. Doesn't find `"general"` in the routes dict
2. Falls back to ANY healthy model (emergency fallback tier)
3. Returns a random/fallback model, not the pre-configured primary

## All Valid Role Names

From `ModelRegistry.get_subagent_routes()`:

| Role (CORRECT) | Simple Form (WRONG) | Primary Model |
|---|---|---|
| `coding_subagent` | `coding` | useai-gpt-5 |
| `creative_subagent` | `creative` | nvidia/DeepSeek-R1 |
| `general_subagent` | `general` | useai-qwen-2-72b |
| `long_context_subagent` | `long_context` | (varies) |
| `planning_subagent` | `planning` | nvidia/DeepSeek-R1 |
| `reasoning_subagent` | `reasoning` | useai-claude-opus-4.6-thinking |
| `research_subagent` | `research` | useai-gemini-2-5-pro |
| `vision_subagent` | `vision` | (varies) |
| `writing_subagent` | `writing` | nvidia/DeepSeek-R1 |

## How to Verify

```python
import sys
sys.path.insert(0, '/root/.hermes/profiles/ilma')

from ilma_subagent_router import get_router
from ilma_model_registry import get_registry

# First: check what roles the registry actually has
registry = get_registry()
routes = registry.get_subagent_routes()
print("Registry role names:", list(routes.keys()))
# Output: ['coding_subagent', 'creative_subagent', 'general_subagent', ...]

# Then: test with correct role names
router = get_router()
decision = router.select_model(role="coding_subagent", task_category="coding")
print(f"{decision.model} — fallback={decision.is_fallback}")
```

## The Rule

**When calling SubAgentRouter.select_model():**
1. Always append `_subagent` to the role
2. Pass `task_category` as the simple form (without `_subagent`)
3. Example: `select_model(role="research_subagent", task_category="research")`

**Common mistakes:**
- `role="research"` → FALLBACK (wrong)
- `role="researcher"` → FALLBACK (wrong)
- `role="research_subagent"` → PRIMARY (correct)
- `role="coders"` → FALLBACK (wrong)
- `role="coding_subagent"` → PRIMARY (correct)