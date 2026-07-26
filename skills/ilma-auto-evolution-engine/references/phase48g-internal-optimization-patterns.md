# Phase 48G Core Fix Patterns — ILMA Self-Optimization

**Phase 48G session:** 48G-J-20260510130000
**Purpose:** Patterns discovered while ILMA optimized itself internally

---

## Pattern 1: Evidence Backfill for weak VERIFIED

**Problem:** 9 capabilities had `status=VERIFIED` but no `evidence_id` field.

**Discovery:** These are "weak VERIFIED" — status claim is stronger than evidence. Must be treated as a gap, not ignored.

**Honest backfill approach:**

```
1. Check if behavioral evidence actually exists (tests, docs, artifacts)
2. If evidence exists → backfill with real evidence_id
3. If evidence does NOT exist → downgrade to PARTIAL or add REAL evidence
4. Never fabricate evidence_id
5. Use format: {capability}_{YYYYMMDD}_verified
   Example: "writing_scripts_20260510_verified"
```

**Files patched in Phase 48G:**
- `ilma_capability_registry.py` — 9 CapabilityEntry blocks patched
- Affected capabilities: api_integration, authentication, code_analysis, data_analysis, database, external_api, messaging, networking, writing

**Verification:**
```python
from ilma_capability_registry import list_all, CapabilityStatus
caps = list_all()
weak = [c for c in caps if c.status == CapabilityStatus.VERIFIED and not c.evidence_id]
print(f"weak VERIFIED = {len(weak)}")  # target: 0
```

---

## Pattern 2: Lesson Retrieval Deduplication

**Problem:** `search_lessons()` could return the same lesson multiple times if it matched multiple keywords or appeared in different result slots.

**Fix location:** `scripts/ilma_lesson_memory.py`, `search_lessons()` method, after relevance sort, before return.

**Implementation:**
```python
# === PHASE 48G-G: Deduplication ===
# NOTE: lessons use "lesson_id" field (not "id")
seen_ids = set()
deduped = []
for r in results:
    lid = r.get("lesson_id", "")
    if lid and lid not in ("N/A", ""):
        if lid not in seen_ids:
            seen_ids.add(lid)
            deduped.append(r)
    else:
        sig = r.get("failure_signature", "")
        if sig and sig not in ("N/A", ""):
            if sig not in seen_ids:
                seen_ids.add(sig)
                deduped.append(r)
        else:
            deduped.append(r)  # legacy lesson
return deduped[:limit]
```

**Dedup priority:**
1. `lesson_id` (UUID) — unique identifier
2. `failure_signature` — semantic deduplication
3. Legacy lessons (no id, no sig) — include without dedup

**Tests added:** `scripts/test_phase48g_dedup.py` — 5 tests (all PASS)

---

## Pattern 3: mark_reused Integration with Judge Gating

**Problem:** `reuse_count` and `reused_at` never auto-incremented. Lesson lifecycle was incomplete.

**Fix location:** `scripts/ilma_task_entrypoint.py`, after judge evaluation, before final status determination.

**Implementation:**
```python
# === PHASE 48G-H: mark_reused Integration ===
if retrieved and retrieved.get('lessons'):
    lesson_ids_to_mark = [l.get('lesson_id', '') for l in retrieved['lessons'] if l.get('lesson_id')]
    if lesson_ids_to_mark and judge_result.status in (JudgeStatus.PASS, JudgeStatus.WARN):
        if verbose:
            print(f"[TaskEntrypoint] Marking {len(lesson_ids_to_mark)} lessons as reused (judge={judge_result.status.value})...")
        for lid in lesson_ids_to_mark:
            if lid:
                lesson_memory.mark_reused(lid)
```

**Gating logic:**
| Judge Status | mark_reused? | Reason |
|---|---|---|
| PASS | ✅ Yes | Artifact evaluation succeeded |
| WARN | ✅ Yes | Artifact evaluation acceptable |
| FAIL | ❌ No | Artifact evaluation failed |
| ERROR | ❌ No | Unexpected error |

**Field name note:** The lesson storage uses `reused_at` field, NOT `last_reused_at`.

**Tests added:** `scripts/test_phase48g_mark_reused.py` — 5 tests (all PASS)

---

## Pattern 4: ILMA-as-Test-Subject Canary

**Principle:** Use ILMA itself as the test subject for auto-learning canaries — safe boundaries, observable artifacts, meaningful improvements.

**Why it works:**
1. Internal changes don't affect external systems
2. All artifacts are accessible within the same environment
3. Improvements are real and measurable
4. Scope can be tightly bounded

**Canary structure used in Phase 48G-J:**
```
Owner command → active_scope + forbidden_scope defined
↓
Pre-task lesson retrieval
↓
Deduplication check
↓
Plan with lesson injection
↓
Judge evaluation
↓
mark_reused if PASS/WARN
↓
Trace export
↓
Exit code 0 = PASS
```

**Honest labeling:** Always label as ACCELERATED unless real-time elapsed is measured with actual wall-clock time.

---

## Pattern 5: Import Path Discipline

**Key distinction:**
- Core modules at **root level**: `ilma_capability_registry.py`, `ilma_workflow_ecc.py`, etc.
- Supporting modules in **scripts/**: `ilma_lesson_memory.py`, `ilma_critic_judge.py`, `ilma_task_entrypoint.py`

**Correct import pattern:**
```python
import sys
sys.path.insert(0, '.')  # root level first
# Now can import both root modules AND scripts/ modules
from ilma_capability_registry import list_all  # root
from scripts.ilma_lesson_memory import LessonMemory  # scripts/
```

**Common error:** `from scripts.ilma_capability_registry` fails — that module is at root, not in scripts/.

**Cache clearing for re-import:**
```python
for _m in list(sys.modules.keys()):
    if 'ilma_' in _m or 'lesson' in _m or 'judge' in _m: 
        del sys.modules[_m]
```

---

## Pattern 6: Lesson Retrieval Query Strategy

**Finding:** Broad queries return 0 results. Specific keyword queries work.

| Query Type | Example | Result |
|---|---|---|
| Broad (task description) | "Optimize ILMA internal evidence and auto-learning workflow" | 0 |
| Specific (technical keyword) | "external_publish" | ✅ finds lesson |
| Specific (technical keyword) | "parser" | ✅ finds lesson |
| Technical phrase | "status_label_bug" | ✅ finds lesson |

**Implication:** Lesson retrieval relies on keyword extraction from the query. Composite phrases work better than general descriptions.

---

## Phase 48G Key Metrics

| Metric | Before | After |
|--------|--------|-------|
| weak VERIFIED | 9 | 0 |
| Duplicate lesson_ids | Possible | Blocked |
| reuse_count auto-increment | None | ✅ After PASS/WARN |
| Total tests | 131 | 141 |

---

**Files created in Phase 48G:**
- `scripts/test_phase48g_dedup.py`
- `scripts/test_phase48g_mark_reused.py`
- `scripts/ilma_phase48g_micro_canary.py`
- `docs/ILMA_PHASE48G_*_2026-05-10.md` (13 files)
- `evidence/evolution_traces/limited_internal/trace_48G-J-20260510130000.json`