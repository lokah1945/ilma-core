# Phase 48E Lesson Retrieval Fix

**Session:** Phase 48E (de5ec5e7)
**Problem:** Lesson retrieval returned 0 lessons despite storage working fine.

---

## Root Causes (3 bugs found)

### Bug 1: `retrieve_for_task()` signature mismatch

**Symptom:** `retrieve_for_task(task_type='heavy')` returned 0 — seeded lessons had `task_type` values like `'parser_fix'`, `'scope_parser'`, not `'heavy'`.

**Fix:** Remove `task_type` filter. Pass task description only:
```python
# BEFORE (broken):
results = pretask_hook.retrieve_for_task(target, task_type='heavy', limit=10)

# AFTER (fixed):
results = pretask_hook.retrieve_for_task(target, limit=10)
```

### Bug 2: `sys.modules` cache not cleared after patch

**Symptom:** After patching `ilma_pretask_learning_hook.py` or `ilma_task_entrypoint.py`, the old module was still loaded in Python's module cache. Re-importing returned stale cached version.

**Fix:** Clear cache before re-importing:
```python
import sys
for _m in list(sys.modules.keys()):
    if 'ilma_' in _m or 'lesson' in _m or 'pretask' in _m:
        del sys.modules[_m]
# Now re-import
from ilma_pretask_learning_hook import PreTaskLearningHook
```

### Bug 3: Priority sort missing — seeded lessons lost

**Symptom:** Seeded lessons (with `failure_signature`) were mixed with legacy lessons. No sort priority.

**Fix:** Priority sort in `search_lessons()`:
```python
# Priority: lessons with failure_signature FIRST (new schema)
# Legacy lessons without failure_signature LAST
def sort_key(lesson):
    if lesson.get("failure_signature") and lesson["failure_signature"] not in ("N/A", ""):
        return (0, -lesson.get("relevance_score", 0.5))  # high priority
    else:
        return (1, -lesson.get("relevance_score", 0.5))  # low priority
results.sort(key=sort_key)
```

### Bug 4: `_extract_keywords()` missing composite phrases

**Symptom:** Query "auto learning" didn't match lesson keywords like "autonomous_learning", "auto-learning".

**Fix:** Add composite phrases to keyword extraction:
```python
COMPOSITE_PATTERNS = [
    "auto learning", "self improvement", "self-improvement",
    "auto-learning", "lesson retrieval", "lesson-aware",
    "reflection loop", "actor-critic", "critic judge"
]
# Extract these as single keywords before splitting
```

---

## Verification Test

```python
from ilma_pretask_learning_hook import PreTaskLearningHook
hook = PreTaskLearningHook()
results = hook.retrieve_for_task("auto learning internal optimization", limit=10)
print(f"Retrieved: {len(results)}")  # Should be > 0
for r in results[:3]:
    print(f"  - {r.get('failure_signature', 'N/A')}")
```

---

## Session Outcome

After fixes: Lesson retrieval returned non-empty results for targeted queries.
- Phase 48E paired test: verdict changed from FAIL to PASS ✅
- 13 lesson retrieval tests PASS
- Behavior-change chain proven