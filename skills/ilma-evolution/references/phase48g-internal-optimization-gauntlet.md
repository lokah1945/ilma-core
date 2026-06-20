# Phase 48G: Internal System Optimization Gauntlet

**Date:** 2026-05-10
**Session:** 48G-J-20260510130000
**Type:** ACCELERATED_INTERNAL_OPTIMIZATION_CANARY
**Decision:** READY_FOR_NEXT_ACCELERATED_INTERNAL_OPTIMIZATION

---

## Concept: ILMA as Its Own Test Subject

Phase 48G used ILMA itself as the test subject for the auto-learning gauntlet. Instead of optimizing external systems, ILMA optimized its own internal workflow — evidence registry, lesson deduplication, mark_reused tracking. Safe boundaries, observable artifacts, meaningful improvements.

**Why this works:**
1. Internal changes don't affect external systems
2. All artifacts accessible in same environment
3. Improvements are real and measurable
4. Scope tightly bounded via safety contract
5. Rollback always available

---

## Four Internal Optimizations Applied

### 1. Evidence Backfill: weak VERIFIED 9→0

**Problem:** 9 capabilities had `status=VERIFIED` but no `evidence_id` — "weak VERIFIED."

**Approach:**
- Check if behavioral evidence actually exists (tests, docs, artifacts)
- If evidence exists → backfill with real evidence_id
- If no evidence → downgrade to PARTIAL
- Never fabricate evidence_id

**Evidence_id format:** `{capability}_{YYYYMMDD}_verified`

**Files patched:** `ilma_capability_registry.py` — 9 CapabilityEntry blocks

**Verification:**
```python
from ilma_capability_registry import list_all, CapabilityStatus
caps = list_all()
weak = [c for c in caps if c.status == CapabilityStatus.VERIFIED and not c.evidence_id]
print(f"weak VERIFIED = {len(weak)}")  # target: 0
```

---

### 2. Retrieval Deduplication

**Problem:** `search_lessons()` could return the same lesson multiple times (same lesson_id or failure_signature).

**Fix:** `scripts/ilma_lesson_memory.py`, `search_lessons()` method, after relevance sort:

```python
# === PHASE 48G-G: Deduplication ===
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

**Tests:** 5 tests in `scripts/test_phase48g_dedup.py` (all PASS)

---

### 3. mark_reused Integration

**Problem:** `reuse_count` and `reused_at` never auto-incremented. Lesson lifecycle incomplete.

**Fix:** `scripts/ilma_task_entrypoint.py`, after judge evaluation:

```python
# === PHASE 48G-H: mark_reused Integration ===
if retrieved and retrieved.get('lessons'):
    lesson_ids_to_mark = [l.get('lesson_id', '') for l in retrieved['lessons'] if l.get('lesson_id')]
    if lesson_ids_to_mark and judge_result.status in (JudgeStatus.PASS, JudgeStatus.WARN):
        for lid in lesson_ids_to_mark:
            if lid:
                lesson_memory.mark_reused(lid)
```

**Gating:**

| Judge Status | mark_reused? |
|---|---|
| PASS | ✅ Yes |
| WARN | ✅ Yes |
| FAIL | ❌ No |
| ERROR | ❌ No |

**Field name:** Uses `reused_at` NOT `last_reused_at`

**Tests:** 5 tests in `scripts/test_phase48g_mark_reused.py` (all PASS)

---

### 4. Trace Schema Hardening

Canonical trace now includes: `active_scope`, `forbidden_scope`, `deduped_lessons`, `reused_lessons`, `reuse_count_before_after`.

---

## Test Results

| Suite | Count | Result |
|-------|-------|--------|
| Project tests | 118 | ✅ PASS |
| Lesson retrieval tests | 13 | ✅ PASS |
| Dedup tests | 5 | ✅ PASS |
| mark_reused tests | 5 | ✅ PASS |
| **Total** | **141** | **✅ ALL PASS** |

---

## Key Finding: Lesson Query Strategy

| Query Type | Example | Result |
|---|---|---|
| Broad (task description) | "Optimize ILMA internal evidence..." | 0 |
| Specific (technical keyword) | "external_publish" | ✅ finds lesson |
| Specific (technical keyword) | "parser" | ✅ finds lesson |

**Implication:** Lesson retrieval relies on keyword extraction. Composite phrases work better than general descriptions.

---

## Import Path Discipline

**Key distinction:**
- Core modules at **root level**: `ilma_capability_registry.py`, `ilma_workflow_ecc.py`
- Supporting modules in **scripts/**: `ilma_lesson_memory.py`, `ilma_critic_judge.py`

**Correct pattern:**
```python
import sys
sys.path.insert(0, '.')  # root level first
from ilma_capability_registry import list_all  # root module ✅
from scripts.ilma_lesson_memory import LessonMemory  # scripts/ ✅
```

**Common error:** `from scripts.ilma_capability_registry` — that module is at root.

---

## Scripts Created

| Script | Purpose |
|--------|---------|
| `scripts/test_phase48g_dedup.py` | 5 dedup unit tests |
| `scripts/test_phase48g_mark_reused.py` | 5 mark_reused unit tests |
| `scripts/ilma_phase48g_micro_canary.py` | Accelerated internal optimization canary |

---

## Documentation

- `docs/ILMA_PHASE48G_A_BASELINE_TRUTH_FREEZE_2026-05-10.md`
- `docs/ILMA_PHASE48G_B_INTERNAL_OPTIMIZATION_TASK_DEFINITION_2026-05-10.md`
- `docs/ILMA_PHASE48G_C_PRETASK_LESSON_RETRIEVAL_2026-05-10.md`
- `docs/ILMA_PHASE48G_D_ACTOR_PLAN_WITH_LESSON_INJECTION_2026-05-10.md`
- `docs/ILMA_PHASE48G_E_CRITIC_JUDGE_PLAN_REVIEW_2026-05-10.md`
- `docs/ILMA_PHASE48G_F_EVIDENCE_BACKFILL_RESULT_2026-05-10.md`
- `docs/ILMA_PHASE48G_G_RETRIEVAL_DEDUPLICATION_RESULT_2026-05-10.md`
- `docs/ILMA_PHASE48G_H_MARK_REUSED_INTEGRATION_RESULT_2026-05-10.md`
- `docs/ILMA_PHASE48G_I_TRACE_SCHEMA_HARDENING_2026-05-10.md`
- `docs/ILMA_PHASE48G_J_INTERNAL_OPTIMIZATION_CANARY_RESULT_2026-05-10.md`
- `docs/ILMA_PHASE48G_K_TEST_AND_GATE_RUN_2026-05-10.md`
- `docs/ILMA_PHASE48G_L_BEHAVIOR_CHANGE_PROOF_2026-05-10.md`
- `docs/ILMA_PHASE48G_M_READINESS_DECISION_2026-05-10.md`
- `docs/ILMA_PHASE48G_INTERNAL_SYSTEM_OPTIMIZATION_GAUNTLET_REPORT_2026-05-10.md`

---

## Relationship to Phase 48F

Phase 48F fixed the task execution chain (retrieve → inject → evaluate → PASS).
Phase 48G extended the lifecycle (retrieve → inject → evaluate → mark_reused → deduplication → evidence backfill).

Together they form a complete internal optimization workflow:
```
Lesson Memory
    ↓
Pre-task retrieval (deduplicated)
    ↓
Actor artifact injection
    ↓
Judge evaluation (PASS/WARN)
    ↓
mark_reused (if PASS/WARN)
    ↓
reuse_count incremented
    ↓
Evidence backfill
    ↓
Trace export
    ↓
Next cycle benefits from reuse tracking
```