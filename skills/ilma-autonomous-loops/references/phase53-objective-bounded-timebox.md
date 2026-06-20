# Phase 53: Objective-Bounded Timebox — Key Learnings

## Core Insight: Duration ≠ Minimum Requirement

**Problem (BEFORE Phase 53):**
- ILMA treated "run for 300 minutes" as ENDURANCE_TEST semantics — must reach wall-clock >= 18,000s
- Early completion was treated as potential failure
- Boss could say "auto learning selama 300 menit" and ILMA would interpret it as "must literally run for 300 minutes minimum"

**Truth (AFTER Phase 53):**
- "300 minute budget" means time is a MAXIMUM cap, not a minimum requirement
- For OBJECTIVE_BOUNDED_TIMEBOX mode: completion before budget = PASSED_EARLY ✅
- Duration requirements only apply to ENDURANCE_TEST mode explicitly requested as such

**Config source:** `config/ilma_autonomy_execution_semantics.json`

```json
{
  "default_mode": "OBJECTIVE_BOUNDED_TIMEBOX",
  "time_budget_is_maximum": true,
  "early_success_is_pass": true,
  "wall_clock_required_only_for_endurance_test": true,
  "never_fail_only_because_finished_early": true
}
```

---

## Mode Hierarchy

| Mode | Duration Requirement | Exit Code 0 When |
|------|---------------------|-------------------|
| **OBJECTIVE_BOUNDED_TIMEBOX** (default) | Maximum cap only | Objective passed + valid evidence before budget |
| **ENDURANCE_TEST** | Minimum 18,000s | Full wall-clock reached + no failures |
| **EXPLORATION_BUDGET** | Maximum cap | Budget exhausted (no hard objective) |
| **VALIDATION_BUDGET** | Maximum cap | All gates passed before budget |

---

## Decision: PASSED_EARLY vs FULL_BUDGET vs FAIL

```
IF mode == OBJECTIVE_BOUNDED_TIMEBOX:
    IF objective_passed_with_evidence:
        final_status = PASSED_EARLY  ← NOT FAILURE
        exit_code = 0
    ELIF time_budget_exhausted AND objective_incomplete:
        final_status = INCOMPLETE
        exit_code = 1

IF mode == ENDURANCE_TEST:
    IF wall_clock < 18000:
        exit_code = 1  ← Cannot claim completion yet
    ELIF wall_clock >= 18000 AND no_fatal_failures:
        final_status = COMPLETE
        exit_code = 0
```

---

## Agent Body Optimization Example

Phase 53 task: "Make ILMA's runtime workflow more coherent..." with 300-min budget

**Actual execution:**
- ~45 minutes wall-clock (parallel sub-agents)
- 11 sub-phases complete
- 545 tests PASS
- Decision: AGENT_BODY_OPTIMIZED_EARLY

**BEFORE Phase 53 semantics:** Would have waited for 300 minutes, treating early completion as incomplete.

**AFTER Phase 53 semantics:** Recognized objective achieved → PASSED_EARLY ✅

---

## Implementation Notes

1. Daemon modes are defined in `config/ilma_autonomy_execution_semantics.json`
2. CLI should support `--mode` argument to explicitly set mode
3. For owner-triggered "run X minutes" commands → default to OBJECTIVE_BOUNDED_TIMEBOX
4. For explicit "endurance test" or "stress test" requests → ENDURANCE_TEST mode
5. Final report must show which mode was used and why decision was made

---

## Related Files

- `config/ilma_autonomy_execution_semantics.json` — Mode definitions (v1.0, 2026-05-10)
- `config/ilma_relentless_problem_solving_policy.json` — 21-step ladder (v1.0, 2026-05-10)
- `docs/ILMA_PHASE53_K_FINAL_DECISION_2026-05-10.md` — Decision matrix
- `docs/ILMA_PHASE53_OBJECTIVE_BOUNDED_SELF_OPTIMIZATION_REPORT_2026-05-10.md` — Full report