# Manufactured Claims: Detection and Prevention
## Phase 51-A forensic lessons — 2026-05-10

---

## The Manufactured Claim Pattern

A **manufactured claim** occurs when a metric is incremented without the underlying data supporting it. The process "faked" a result by incrementing a counter when zero actual work happened.

**Phase 50 example:**
- 8 cycles ran
- 0 lessons retrieved across all cycles
- `lesson_reuse_count` still incremented to 8
- Root cause: code had `reuse_count += 1` in the "no lessons found" branch

```python
# BUGGY — manufactured +1 per cycle
if reuse_count_this_cycle > 0:
    self.lesson_reuse_count += reuse_count_this_cycle
else:
    self.lesson_reuse_count += 1  # ← manufactured when nothing retrieved
```

8 cycles × manufactured +1 = claimed reuse_count of 8 — but zero actual retrieval.

---

## Why This Is Dangerous

1. **Report claims PASS** but retrieval system is broken
2. **User trusts the metric** but it's fabricated
3. **Bug in code** gets masked by incrementing in error handlers too
4. **Future audits can't find the root cause** — the trace looks fine (8 cycles, exit 0, 29 heartbeats)
5. **The wall-clock is real** (1800.03s) but the lesson claim is fake — PARTIAL truth

---

## Detection Pattern: Truth Validator

**Tool:** `scripts/ilma_phase50_truth_validator.py`

```python
# The validator's critical check:
if total_retrieved > 0:
    # reuse_count should be <= total_retrieved * 2
    if reported_reuse <= total_retrieved * 2:
        passes.append(f"reuse_count: {reported_reuse} (reasonable)")
else:
    # 0 lessons retrieved → reuse_count must also be 0
    if reported_reuse == 0:
        passes.append(f"reuse_count: 0 (correct when no retrieval)")
    else:
        issues.append(
            f"reuse_count: {reported_reuse} but lessons_retrieved: 0 ❌ "
            "(MANUFACTURED — increments without retrieval)"
        )
```

**Rule:** `reuse_count > 0` when `lessons_retrieved == 0` is ALWAYS a manufactured claim.

---

## Prevention Rules for All Runners/Loops

Any script that increments a metric must follow:

| Rule | Why |
|------|-----|
| Increment ONLY when underlying data exists | Prevents manufactured counts |
| Never increment in error handlers to "avoid gate failure" | Error should FAIL, not be hidden |
| Never increment just because cycle ran successfully | Cycle success ≠ lesson reuse |
| Always check the data source first | e.g., `len(lessons) > 0` before counting |
| Error handlers should NOT modify metric state | Preserve truth, don't patch |

```python
# ✅ CORRECT: increment only from actual data
if lessons_retrieved:
    for lesson in lessons_retrieved:
        mark_reused(lesson['id'])
        count += 1
    reuse_count += count
else:
    reuse_count = reuse_count  # No change — honest

# ❌ WRONG: manufacture when no data
if lessons_retrieved:
    ...
else:
    reuse_count += 1  # Manufacture = lie
```

---

## The Exit Code Semantics for Truth

| Exit | Meaning | Claim |
|------|---------|-------|
| 0 | ALL checks pass | FULL PASS |
| 1 | CRITICAL FAIL (wall-clock < minimum, exit ≠ 0) | FAIL |
| 2 | Wall-clock valid, but retrieval/metric broken | PARTIAL |

**Critical:** Never claim FULL PASS (status=COMPLETE) when exit code is 2. Report PARTIAL.

---

## Audit Questions for Any Phase Report

Before accepting any phase report as COMPLETE, answer:

1. **Wall-clock real?** → Verify against process end time
2. **Exit code matches status?** → exit 0 + COMPLETE = OK; exit 0 + ERROR = contradiction
3. **Metric backed by data?** → `reuse_count` must have `mark_reused()` calls; `lessons_retrieved` must have actual lesson objects
4. **No manufactured increments?** → Check error handlers and "no data" branches
5. **Report generated AFTER process exits?** → Generated-before-crash = false claim

---

## Phase 51-A Truth Lock Results

| Metric | Claimed | Artifact Verified | Status |
|--------|---------|-------------------|--------|
| Wall-clock | 1800.03s | 1800.03s | ✅ TRUE |
| Exit code | 0 | 0 | ✅ TRUE |
| Cycles | 8 | 8 | ✅ TRUE |
| Lessons retrieved | non-empty | 0 | ❌ FALSE |
| reuse_count | 8 | 8 (manufactured) | ❌ FALSE |
| Heartbeats | 29 | 29 | ✅ TRUE |
| Judge scores | valid | valid (85) | ✅ TRUE |

**Phase 50 verdict:** ⚠️ **PARTIAL PASS** (exit code 2)
- Wall-clock valid ✅
- Retrieval system broken ❌
- Claimed 8 reuse, reality: 0 retrieved → manufactured

---

## Files Created

- `scripts/ilma_phase50_truth_validator.py` — validator tool
- `tests/test_ilma_phase50_truth_validator.py` — 7 tests (all PASS)
- `scripts/ilma_phase50_realtime_30min_canary.py` — BUGGY (fixed)

**Bug fix applied:**
```python
# OLD: manufactured +1 when no lessons
# NEW: no change when no lessons retrieved
```

---

## When to Run This Audit

- After every canary/daemon/autoloop run
- Before writing any phase final report
- When report claims PASS but retrieval was complex
- When metrics show improvement but no actual data

---

*Created: 2026-05-10*
*From: Phase 51-A forensic truth lock (Phase 50 contradiction discovered)*