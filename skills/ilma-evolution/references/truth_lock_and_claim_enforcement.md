# ILMA Truth Lock & Claim Enforcement Reference
## 2026-05-10 — Phase 51 forensic findings

---

## Core Principle

**Claim = artifact evidence, not narrative.** Before declaring any phase PASS, validate from artifacts only.

---

## The Manufactured Claim Problem

Phase 50 exposed a critical bug: `reuse_count = 8` was claimed, but `lessons_retrieved = 0` across all 8 cycles.

Root cause in the runner code:
```python
# BUGGY — increments even when no lessons retrieved
if reuse_count_this_cycle > 0:
    self.lesson_reuse_count += reuse_count_this_cycle
else:
    self.lesson_reuse_count += 1  # ← manufactured +1
```

The cycle always produced `reuse_count_this_cycle = 0` because `lessons_retrieved = []`, but the `else:` branch manufactured a +1 per cycle. 8 cycles × 1 = 8 claimed reuse — zero actual.

---

## Truth Validator Tool

**Location:** `scripts/ilma_phase50_truth_validator.py`
**Tests:** `tests/test_ilma_phase50_truth_validator.py` (7 tests, all PASS)

### Exit code semantics

| Exit | Meaning | Action |
|------|---------|--------|
| 0 | ALL checks pass — wall-clock ≥1800s, lessons_retrieved > 0, reuse_count consistent | Declare PASS ✅ |
| 1 | CRITICAL FAIL — wall-clock <1800s, exit code ≠ 0, process ended unexpectedly | Declare FAIL ❌ |
| 2 | PARTIAL PASS — wall-clock ≥1800s but retrieval/reuse broken | Declare PARTIAL ⚠️ |

### Checked fields

1. `wall_clock_seconds` ≥ 1800
2. `exit_code` == 0
3. `heartbeats` count ≥ 28
4. `checkpoints` count ≥ 2
5. `cycles` count ≥ 3
6. `judge_evaluations` count ≥ 3
7. `lessons_retrieved` total > 0 (CRITICAL)
8. `reuse_count` consistency (must NOT be > 0 when `lessons_retrieved == 0`)
9. `cycles_with_retrieval` > 0
10. Judge scores valid (40-100)

---

## The Lesson Retrieval Contradiction Explained

Phase 50 report said both:
- "lesson retrieval = 0"
- "lesson reuse count = 8"

These are mutually exclusive. Either:
- Lessons were retrieved and marked → reuse_count = 8 ✅
- Lessons were NOT retrieved → reuse_count = 0 ❌

The trace confirms 0 retrieval, 8 manufactured. The truth validator catches this.

---

## Lesson Memory.count_lessons() Missing

`LessonMemory` class does NOT have `count_lessons()`. Only:
- `add_lesson()`
- `mark_reused()`
- `search_lessons()`
- `retrieve_for_task()`
- `get_statistics()`
- `export_lessons()`
- `clear_all()`
- `validate_schema()`

First run (proc_8b58f01b5950) failed because caller called `count_lessons()`. Second run (proc_f9e2a2a09119) avoided the call and exited 0 — but the underlying retrieval bug remained.

---

## Fix Applied

```python
# FIXED — only increment from actual retrieval
if reuse_count_this_cycle > 0:
    self.lesson_reuse_count += reuse_count_this_cycle
    cycle_data["reuse_incremented"] = True
else:
    # No lessons retrieved — DO NOT manufacture a count
    cycle_data["reuse_incremented"] = False
    print(f"  Reuse: 0 (no lessons retrieved — count NOT incremented)")

except Exception as e:
    # Error — do NOT manufacture to hide it
    self.lesson_reuse_count = self.lesson_reuse_count  # No change
    cycle_data["reuse_incremented"] = False
```

---

## Claim Enforcement Rules

1. **Never claim PASS if validator exit code = 1 or 2**
2. **Never claim reuse if lessons_retrieved = 0**
3. **Never increment metric without underlying data**
4. **Never patch exit code to hide gate failure**
5. **Report PARTIAL when wall-clock valid but retrieval broken**
6. **Report FAIL when wall-clock invalid**

---

## When to Run Validator

- After every canary/daemon/autoloop run
- Before writing final phase report
- Before claiming any metric improvement
- During regression checks

Command: `python3 scripts/ilma_phase50_truth_validator.py [trace_path]`

---

*Created: 2026-05-10*
*Driven by: Phase 50 forensic truth lock (Phase 51-A)*
*Files: scripts/ilma_phase50_truth_validator.py, tests/test_ilma_phase50_truth_validator.py*