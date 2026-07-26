# Phase 57: Live Research Activation
## Date: 2026-05-11
## Status: COMPLETE ✅

---

## Problem

ILMA's autonomous evolution loop could only use:
1. Internal lesson memory (past lessons stored in JSONL)
2. Reflection engine (analysis of failures)

**Gap:** When reflection gave unclear/unknown root cause AND fix plan was weak, ILMA had no way to discover external solutions. The loop would retry with the same weak insights, leading to repeated failures.

---

## Solution: Live Research Module

Created `scripts/ilma_live_research.py` — autonomous live research trigger that activates when internal knowledge is insufficient.

### LiveResearch Class

```python
from scripts.ilma_live_research import LiveResearch

lr = LiveResearch()

# Check if research is warranted
should, reason = lr.should_research(
    failed_attempts=3,
    root_cause="unknown",
    has_lesson_memory=False
)

# Perform research
result = lr.research(
    error_context="ModuleNotFoundError: No module named 'numpy'",
    task_type="code",
    root_cause="",
    failed_attempts=2
)

# result = ResearchResult(
#   solutions: List[str],
#   papers: List[Dict], 
#   confidence: float,
#   new_knowledge: List[str],
#   sources: List[str],
#   research_duration: float
# )
```

### Research Sources

| Source | Purpose | Status |
|--------|---------|--------|
| DuckDuckGo HTML | Web search (primary) | ✅ |
| Startpage | Web search (fallback) | ✅ |
| Mojeek | Web search (fallback) | ✅ |
| arXiv API | Technical papers (code/analysis/planning) | ✅ |
| Pattern cache | Known solutions storage | ✅ |

---

## Integration Points

### 1. `ilma_reflection_engine.py` — `_generate_fix_plan()` enhancement

**Trigger:** Fix plan <= 2 steps AND root cause unclear/unknown

```python
# === PHASE 57: LIVE RESEARCH TRIGGER ===
if len(plan) <= 2 and root_cause and ("unknown" in root_cause.lower() or "unclear" in root_cause.lower()):
    plan = self._enhance_with_live_research(plan, failures, root_cause)
```

### 2. `ilma_task_entrypoint.py` — post-reflection trigger

**Trigger:** Root cause unclear AND iteration >= 2

```python
root_cause_unclear = not refl_result.root_cause or "unknown" in refl_result.root_cause.lower()

if root_cause_unclear and iteration >= 2:
    # Trigger live research
    research_result = lr.research(error_context, task_type, root_cause, iteration)
    # Enhance fix_plan with solutions found
    refl_result.fix_plan.insert(0, f"📚 Live research suggests: {research_result.solutions[0][:100]}")
```

---

## Automatic Trigger Conditions

| Condition | Trigger Location | Notes |
|-----------|------------------|-------|
| Fix plan <= 2 steps + root cause unclear | ReflectionEngine._generate_fix_plan() | During fix plan generation |
| Iteration >= 2 + root cause unclear | task_entrypoint.py | After reflection.analyze() |
| Failed attempts >= 3 + root cause unclear | LiveResearch.should_research() | Pre-research check |
| No lesson memory + confidence < 0.3 | LiveResearch.should_research() | Pre-research check |
| Novel error pattern not in cache | LiveResearch.should_research() | Pre-research check |

---

## Safety Properties

- **Non-fatal:** All research failures caught with try/except — execution continues
- **Timeout:** Max 30s research duration prevents infinite blocks
- **Confidence scoring:** Prevents low-quality solutions from dominating
- **Pattern cache:** Results stored for future reuse

---

## Test Results

```
Phase 56 CLI Tests: 21/21 ✅
All Project Tests: 233/233 ✅
Live research arXiv: Working (4 papers found)
```

---

## Files Changed

| File | Change |
|------|--------|
| `scripts/ilma_live_research.py` | NEW — LiveResearch module |
| `scripts/ilma_reflection_engine.py` | ADD — `_enhance_with_live_research()` (~65 lines) |
| `scripts/ilma_task_entrypoint.py` | ADD — live research trigger after reflection (~45 lines) |

---

## Documentation

`docs/ILMA_PHASE57_LIVE_RESEARCH_ACTIVATION_2026-05-11.md`

---

## Problem Solving Flow (UPDATED)

```
TASK FAILURE (Judge FAIL)
     ↓
Reflection.analyze()
     ↓
Fix plan <= 2 steps?
     ↓ YES
_enhance_with_live_research()
     ↓
LiveResearch.should_research() → True/False
     ↓ (True)
LiveResearch.research() → Web search + arXiv
     ↓
solutions + papers found
     ↓
store_research_result() → cache for future
     ↓
Add to fix_plan: "📚 Live research suggests: ..."
     ↓
Retry with new insights
```

---

## Key Pattern: External Research Trigger

The core pattern is that ILMA now has TWO problem-solving layers:

1. **Internal:** Lesson Memory + Reflection → uses stored experience
2. **External:** Live Research (web + arXiv) → discovers new knowledge

When internal knowledge is insufficient (unclear root cause, weak fix plan), ILMA automatically triggers external research before retrying.

This follows the same pattern as human problem solving: "I don't know → let me look it up → try again with new information."