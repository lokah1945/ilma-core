---
name: ilma-dual-harness-code-forge
description: Dual-Harness Code Forge pattern — Generator + Reviewer + Validator + Arbiter + Knowledge Registry for autonomous engineering excellence. Trigger when Bos asks for "dual harness", "code forge", "multi-model governance", "iterative perfection loop", "Level 7 autonomous engineering", "N models compete", "arbiter scoring", or wants ILMA to act as an autonomous engineering organization rather than a single-shot code generator. Built Phase C (2026-06-17), 9 modules, 17/17 tasks done.
tags:
  - code-generation
  - multi-model
  - competitive-review
  - arbiter
  - knowledge-registry
  - autonomous-engineering
triggers:
  - "dual harness"
  - "code forge"
  - "multi-model governance"
  - "iterative perfection loop"
  - "level 7"
  - "N models compete"
  - "arbiter"
  - "weighted scoring"
  - "self-audit first"
  - "engineering organization"
  - "harness != model"
related_skills:
  - ilma-parallel-coding-agent
  - ilma-multi-agent
  - ilma-end-to-end-audit
  - ilma-audit-then-build
  - ilma-feature-flags
status: VERIFIED
evidence_ids:
  - ILMA-EVID-20260617-CODE-FORGE-001
  - ILMA-EVID-20260617-CAPABILITY-SCORER-001
  - ILMA-EVID-20260617-ORCHESTRATOR-001
---

# ILMA Dual-Harness Code Forge Pattern

## The Big Idea

**Single model + single prompt = single point of failure.**

Dual-Harness Code Forge = **two SEPARATE models** solve the same problem differently:
- **Generator** — produces code from a task spec
- **Reviewer** — must be a **DIFFERENT** model, evaluates against a 10-item explicit checklist
- **Validator** — runs the code: syntax, AST, tests, performance, security
- **Arbiter** — picks the winner with weighted scoring + explanation
- **Knowledge Registry** — records every task so future tasks learn from past wins/failures

The phrase **"Harness ≠ Model"** is central. Claude Code / Codex / Cursor are **HARNESSES** (tool-use frameworks). The actual MODEL comes from ILMA's SOT (382 free / 1796 paid). Picking a model from SOT is what differentiates ILMA from the harnesses used as-is.

## The 50/50 Rule

```
Code quality = 50% workflow + 50% model
```

Because ILMA uses free models (weaker than paid), the workflow side MUST be strong. Dual-Harness is a 50%-workflow approach: explicit checklists, weighted scoring, multi-stage validation, persistent knowledge.

## The 5-Tier Architecture

```
TIER 1: Generation (parallel)
  ├─ Generator Harness (Model A from SOT)
  ├─ Generator Harness (Model B from SOT)
  └─ Generator Harness (Model C from SOT)
         ↓
TIER 2: Review (multi-reviewer, EXPLICIT CHECKLIST)
  ├─ Reviewer Harness (Model X — DIFFERENT from generator)
  ├─ Static analysis: eval(), exec(), shell=True, bare-except
  └─ 10-item checklist: BUG, EDGE_CASE, SECURITY, PERFORMANCE, READABILITY,
         TEST, COMPATIBILITY, MEMORY, CONCURRENCY, ERROR_HANDLING
         ↓
TIER 3: Validation
  ├─ Syntax: compile(code, "<gen>", "exec")
  ├─ AST: ast.parse + count FunctionDef, ClassDef
  ├─ Tests: exec in sandbox, run test cases, measure pass rate
  ├─ Performance: benchmark compile time
  └─ Security: scan for dangerous patterns
         ↓
TIER 4: Decision (Arbiter)
  ├─ Weighted scoring: quality 30% + tests 30% + perf 20% + security 10% + cost 10%
  ├─ Confidence based on gap between winner and runner-up
  ├─ MUST explain decision (winner_id + scores + reasoning + tradeoffs + alternatives)
         ↓
TIER 5: Knowledge Update
  ├─ MongoDB collection: code_forge_knowledge
  └─ Local fallback: data/code_forge_knowledge.jsonl
```

## The Iterative Perfection Loop (NOT Generate → Approve)

```
Generate → Review → Fix → Review → Fix → Benchmark → Approve
(max 4-6 iterations per task)
```

**Forbidden**: `Generator → Approve` (single-shot rubber-stamping).
**Required**: Multi-pass with explicit iterations, each one recorded in knowledge.

## Self-Audit FIRST Pattern (Block 1 before Block 2)

**Critical lesson from Phase C**: Before building new capabilities, audit what you have:
- List all modules (e.g., `find . -name "ilma_*.py" -exec wc -l`)
- List all scripts and skills
- For each top-10 module: weakness, failure mode, missing feature, attack vector, improvement path
- System-level risks: SPOF, technical debt, dangerous assumptions
- **Be brutally honest** — self-criticism is for the agent, not marketing

Output: Master inventory + Self-criticism report + Gap matrix (claimed vs actual).

## Reference Implementation (9 modules, ~2,180 lines)

| Module | LOC | Purpose |
|--------|-----|---------|
| `ilma_code_forge.py` | 280 | 5-tier orchestrator |
| `ilma_generator_harness.py` | 250 | Takes task_spec, uses SOT model, returns Solution(code, rationale, tests) |
| `ilma_reviewer_harness.py` | 290 | 10-item checklist, static analysis for eval/exec/shell |
| `ilma_validator_harness.py` | 400 | 5 checks: syntax, AST, tests, perf, security |
| `ilma_arbiter.py` | 200 | Weighted scoring + confidence + reasoning |
| `ilma_knowledge_registry.py` | 260 | MongoDB + local JSONL fallback |
| `ilma_competitive_review.py` | 80 | N-way competition wrapper |
| `ilma_task_orchestrator.py` | 210 | Split + parallel exec with dependency order |
| `ilma_capability_scorer.py` | 210 | 5 granular scores added to model_intelligence |

All modules behind feature flags (default: disabled) per Bos rule "no breaking existing functionality".

## The Arbiter's Weighted Scoring Formula

```python
WEIGHTS = {
    "quality": 0.30,    # from reviewer
    "tests": 0.30,      # from validator (test pass rate)
    "performance": 0.20, # from validator (benchmark)
    "security": 0.10,   # from reviewer (security_score)
    "cost": 0.10,       # free model bonus
}

# Per-solution total
total = (
    quality * 0.30 +
    tests * 0.30 +
    perf * 0.20 +
    security * 0.10 +
    cost * 0.10
)

# Confidence from gap between winner and runner-up
gap = winner_score - runner_up_score
if gap > 10:   confidence = 0.95
elif gap > 5:  confidence = 0.80
elif gap > 2:  confidence = 0.60
else:          confidence = 0.40
```

## Generator/Reviewer/Validator Pattern (Hard Rule)

**Generator and Reviewer MUST use DIFFERENT models.** Same model defeats the dual-harness purpose. In offline/test mode, use distinct IDs:

```python
for i in range(num_solutions):
    sol = generator.generate(task_spec, model_id=f"generator_{i}")
    review = reviewer.review(sol, model_id=f"reviewer_{i}_distinct")
```

## Canned Solutions for E2E Testing

When testing the forge WITHOUT a live LLM, use deterministic canned solutions for known task IDs:

```python
CANNED = {
    "fib_memo": (memoized_fib_code, "O(n) memoized", ["test_fib_0", "test_fib_10"]),
    "lru_cache": (lru_ordered_dict_code, "O(1) get/put", ["test_eviction_order"]),
    "http_retry": (exponential_backoff_code, "Configurable retry", ["test_500"]),
}
```

This pattern lets you run the full 5-tier pipeline (generate → review → validate → arbitrate → record) in offline mode for smoke tests.

## The Knowledge Registry Schema

```json
{
  "timestamp": "2026-06-17T03:30:00Z",
  "task_id": "fib_memo",
  "task_type": "code",
  "winner_id": "sol_0",
  "winner_score": 100.0,
  "all_scores": {"sol_0": 100.0, "sol_1": 100.0},
  "reasoning": "Selected sol_0 with total 100.00/100. Quality: 100/100, Tests: 100%, ...",
  "confidence": 0.4,
  "tradeoffs": ["Performance is sub-optimal"],
  "solutions": [
    {
      "id": "sol_0",
      "model_id": "generator_0",
      "is_free": true,
      "review": {"quality": 100, "security": 100, "passed": true, "findings_count": 0},
      "validation": {"test_pass_rate": 1.0, "performance": 1.0, "complexity": 3, "passed": true}
    }
  ]
}
```

Stored in `code_forge_knowledge` MongoDB collection + `data/code_forge_knowledge.jsonl` local fallback.

## Capability Scoring (SOT Enhancement)

Add 5 granular fields to `model_intelligence`:

```python
CAPABILITY_PATTERNS = {
    "code_generation_score": [qwen.*coder, deepseek-coder, starcoder, yi-coder, ...],
    "code_review_critique_score": [claude, sonnet, opus, gpt-4, gpt-5, ...],
    "bug_detection_score": [claude, sonnet, opus, gpt-4, gpt-5, ...],
    "instruction_following_score": [claude, sonnet, opus, gpt-4, gpt-5, instruct, ...],
    "reasoning_depth_score": [o1, o3, opus, sonnet, pro, thinking, reasoning, ...],
}
```

Each pattern match boosts the score by 10-15 points. Top 5 free for code_gen (verified 2026-06-17):
- qwen/qwen3-coder-480b-a35b-instruct: 95.0
- nv-embedcode-7b-v1: 86.95
- bigcode/starcoder2-15b: 84.0
- deepseek-ai/deepseek-coder-6.7b-instruct: 84.0
- ibm/granite-8b-code-instruct: 84.0

## Task Orchestrator (Parallel + Dependencies)

```python
class TaskOrchestrator:
    def split_task(self, task_spec) -> List[SubTask]:
        if task_spec["type"] == "implement_feature":
            return [
                SubTask("design_api",   "design", deps=[]),
                SubTask("impl_backend", "code",   deps=["design_api"]),
                SubTask("impl_frontend","code",   deps=["design_api"]),
                SubTask("write_tests",  "code",   deps=["impl_backend", "impl_frontend"]),
                SubTask("integrate",    "code",   deps=["write_tests"]),
            ]

    async def execute_parallel(self, sub_tasks):
        # Topological sort: assign level = max(deps.level) + 1
        # Group by level, run each level with asyncio.gather
        # Skip tasks whose deps aren't satisfied
```

## Pitfalls (Phase C lessons)

1. **Canned solutions are required for offline E2E tests.** Without them, the forge can't run end-to-end in test mode. Always provide a `_get_canned_solution(task_id)` method.

2. **Confidence score for canned solutions will be low (0.4).** All canned solutions score identically, so the gap is 0. This is expected — the arbiter still picks a winner, it just expresses low confidence.

3. **Cyclic dependencies in task orchestrator → infinite loop.** The `_compute_levels` method has a 100-iteration cap. Always design dependency graphs to be DAGs.

4. **Feature flag pattern must be applied to ALL new modules.** Even utility modules (capability scorer, knowledge registry) get a feature flag. Per Bos rule: no breaking existing functionality.

5. **Reviewer model ID MUST differ from generator's.** Even in offline mode, use `f"reviewer_{i}_distinct"` to make the distinction clear in evidence.

6. **Generator pattern matching for capability scoring is heuristic, not measured.** Use existing fields (composite_score, capabilities) to derive capability-specific scores. Production should use real benchmark results.

7. **Knowledge registry must have BOTH MongoDB and local fallback.** MongoDB may be blocked; local JSONL ensures knowledge is never lost.

8. **Task orchestrator returns list of SubTask, not dicts.** The original code accidentally accepted dicts; the fix is to always return `List[SubTask]`.

9. **Validator's `_run_tests` for canned tasks must handle each task type explicitly.** Generic "import + exec" is not enough; canned tasks need specific test cases (e.g., LRU test_evict_b).

10. **Harness ≠ Model is the most misunderstood concept.** A future engineer may try to "use Claude Code as a model". Claude Code is a HARNESS. The model is what the harness CALLS. ILMA picks the model from SOT.

## When to Use This Pattern

**Use when:**
- Code generation tasks (medium to heavy)
- Multiple models should solve the same problem
- Quality and security matter (production code)
- Bos asks for "the best code" not "fast code"

**Do NOT use when:**
- Single-line edits (overhead > benefit)
- Latency-sensitive (3 models in parallel = N×time)
- Trivial tasks (use single-shot SubAgentRouter)
- Tasks where deterministic single-source is required

## Integration with Existing ILMA

| Existing module | How Dual-Harness integrates |
|----------------|------------------------------|
| `ilma_model_router` | Forge uses router for model selection (free-first) |
| `ilma_feature_flags` | Each new module has its own flag (default: false) |
| `ilma_mongo_connection` | Knowledge registry uses MongoDB singleton |
| `ilma_metrics` (Phase P) | Can wrap forge.execute_task for metrics |
| `ilma_tracing` (Phase P) | Can trace forge tiers |
| `ilma_circuit_breaker` (Phase P) | Can gate failed generators |
| `ilma_self_healing` (Phase P) | Can monitor forge health |

## CLI Usage

```python
from ilma_code_forge import DualHarnessCodeForge, get_forge

forge = get_forge()
result = forge.execute_task(
    task_spec={
        "id": "my_feature",
        "title": "Build user auth",
        "description": "Add user authentication with JWT",
        "type": "code",
        "requirements": ["Use bcrypt", "JWT tokens", "Refresh token rotation"],
    },
    num_solutions=3,  # 3 models compete
)

print(f"Winner: {result.arbiter_result.winner_id}")
print(f"Confidence: {result.arbiter_result.confidence}")
print(f"Reasoning: {result.arbiter_result.reasoning}")
print(f"Solution code:\n{result.winner_solution.code}")
print(f"Knowledge recorded: {result.knowledge_recorded}")
```

## Production Rollout Plan

- **Day 0**: All 9 modules merged behind feature flags (default: disabled)
- **Day 1-3**: Enable `code_forge_generator_enabled` for low-traffic tests
- **Day 4-7**: Enable reviewer + validator
- **Day 8-14**: Enable arbiter + knowledge
- **Day 15+**: Enable competitive review + task orchestrator

## Status

- **Phase C (2026-06-17)**: 17/17 tasks DONE
- **Modules**: 9 created, ~2,180 lines
- **SOT**: 5 new fields in model_intelligence, 250 models updated, 1 new collection
- **Tests**: 9/9 SQL injection (already), 5/5 circuit breaker, 3/3 E2E tasks, 5/5 sub-tasks parallel
- **Level**: Foundation for Level 7 (Elite Autonomous Engineering Organization)
- **Production rollout**: pending (gradual flag enablement)

## See Also

- `ilma-parallel-coding-agent` — simpler N-way voting (no review/validate/arbitrate cycle)
- `ilma-multi-agent` — multi-agent delegation patterns
- `ilma-end-to-end-audit` — self-audit pattern (Block 1 of Phase C)
- `ilma-audit-then-build` — audit-then-build methodology
- `ilma-feature-flags` — feature flag pattern for safe rollouts
