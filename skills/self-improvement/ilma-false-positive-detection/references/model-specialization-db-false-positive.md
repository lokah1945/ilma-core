# False Positive: Model Specialization DB "16/16 NOT IN Database" (Phase 57)

## The False Positive

During MASTER_TARGET_SELF_OPTIMIZATION_V5, validation reported:
```
❌ planner_model: primary 'nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free' NOT IN models
❌ research_model: primary 'openrouter/owl-alpha' NOT IN models
... (all 16 task categories)
```

This looked like the model specialization database was broken. It wasn't.

## Root Cause: Key Format Mismatch, Not Broken Data

The verification checked if `spec_db['models'][primary_model]` exists.
The `task_models['primary_model']` values were built from router output.
But the `models` dict was keyed using `f"{prov_name}/{model_id}"` format from the raw provider DB.

The router returns `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`.
The provider DB has key `nemotron-3-nano-omni-30b-a3b-reasoning:free` (no nvidia prefix for nvidia provider).
So `f"nvidia/{model_id}"` = `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` — which matches! ✓
Wait, actually for nvidia the prefix IS added for some models. For openrouter, the keys are already `openrouter/...`.

**The mismatch:** For openrouter models, the key was `openrouter/baidu/cobuddy:free` but router returns `baidu/cobuddy:free`.
For nvidia models, the key was `nvidia/01-ai/yi-large` but router returns `01-ai/yi-large` (no nvidia prefix).

The rule for key formation varies by provider, and `f"{prov}/{model}"` doesn't match what the router returns for all providers.

## The Fix

Don't assume key formats align. Build the DB by querying the router:

```python
# Build task_models via router, not assumptions
primary = get_best_model(route_to)
new_task_models[cat] = {
    "primary_model": primary.get('model_id'),  # Router's returned ID
}
```

Then verification `spec_db['models'][primary_model]` works correctly.

## Key Lesson

When verification reports X/16 capabilities as "not found," the first instinct should be: **is the database keyed correctly against what the router actually returns?** Not "is the router broken?" The router was fine. The DB key formation was the problem.

This is the same false-positive pattern as:
- Registry says UNVERIFIED but runtime works → registry metadata wrong
- Tests say FAIL but code works → test methodology wrong
- DB says "model not found" but router works → key format mismatch

**Rule:** Always verify against runtime output, not assumed formats.