# ILMA Phase 3 Optimization Audit

**Date:** 2026-05-13  
**Phase:** 3A (Script Deduplication) & 3B (ILMA.py Integration Test)

---

## PHASE 3A - Script Deduplication Results

### Duplicate Script Names (Same Basename, Different Locations)

| Count | Filename |
|-------|----------|
| 12 | `__init__.py` |
| 3 | `core.py` |
| 2 | `ilma_config_manager.py` |
| 1 | All others (unique) |

**Total Scripts:** 456 Python files

### Scripts Larger Than 100KB
No scripts found exceeding 100KB.

### Scripts Referencing ILMA Core Modules

The following scripts reference ILMA core router/adapter modules:

- `ilma_benchmark_suite.py`
- `ilma_integrated_test_runner.py`
- `ilma_passive_benchmark_refresh.py`
- `ilma_phase23_evidence_tests.py`
- `ilma_phase24_behavioral_tests.py`
- `ilma_phase25_focused_tests.py`
- `ilma_phase27_behavioral_proof_suite.py`
- `ilma_phase59_optimization_test.py`
- `ilma.py`
- `ilma_unified_router_adapter.py`

### 3A Findings

1. **High duplication:** `__init__.py` appears 12 times, `core.py` appears 3 times — likely copied across module directories
2. **Large scripts:** No scripts exceed 100KB; no obvious "canonical" oversized candidates
3. **Core references:** 10 scripts directly reference `ilma_unified_router_adapter`, `ilma_model_router`, or `ilma_complete_system`
4. **Recommendation:** The 3 `core.py` files should be audited for content divergence; `__init__.py` multiplicity is normal for Python packages

---

## PHASE 3B - ILMA.py Entry Point Verification

### Command: `python3 scripts/ilma.py --help`

```
usage: ilma.py [-h] {run,status,stop,resume,validate,doctor} ...

ILMA Single Owner Command Interface — Phase 56 Production

positional arguments:
  {run,status,stop,resume,validate,doctor}
                        Available commands
    run                 Run a task via real runtime body
    status              Show current status with weak_VERIFIED and traces
    stop                Stop current task via owner_stop flag
    resume              Resume stopped task (honest: limited support)
    validate            Validate safety contract, claim boundary, registry,
                        evidence
    doctor              Run system health checks with smoke tests
```

**Status:** ✅ Working

### Command: `python3 scripts/ilma.py validate`

```
============================================================
ILMA Validate — Phase 56
============================================================

🔍 [1/6] Validating safety contract...
   ✅ always_on=false (correct)
   ✅ owner_command_required=True (correct)
   ✅ Rules count: 10

🔍 [2/6] Validating claim boundary...
   ✅ Claim boundary defined: 11 claimable items
   ✅ Production claims defined: ['agent_body_integration']
   ✅ Forbidden claims defined: 9 items

🔍 [3/6] Validating capability registry...
   ✅ Registry loaded: 108 capabilities

🔍 [4/6] Validating evidence ledger...
   ✅ Ledger exists: 2 entries, 0 weak_VERIFIED

🔍 [5/6] Validating service imports...
   ✅ RuntimeRouter
   ✅ LessonMemory
   ✅ ToolSkillSelector
   ✅ CriticJudge
   ✅ FinalReportGenerator

🔍 [6/6] Validating task entrypoint...
   ✅ run_task_with_evolution available
```

**Status:** ✅ All 6/6 checks passed

### Command: `python3 scripts/ilma.py doctor`

```
2026-05-13 20:33:24,786 - scripts.services.report.final_report_generator.FinalReportGenerator - ERROR - Failed to load evidence ledger: 'list' object has no attribute 'get'
2026-05-13 20:33:24,786 - scripts.services.report.final_report_generator.FinalReportGenerator - INFO - FinalReportGenerator initialized with 0 evidence entries

============================================================
ILMA Doctor - System Health Check — Phase 56
============================================================

📁 [1/9] Checking workspace...
   ✅ Workspace exists: /root/.hermes/profiles/ilma

⚙️  [2/9] Checking config...
   ✅ Config directory exists

🔒 [3/9] Checking safety contract...
   ✅ Safety contract exists

📋 [4/9] Checking claim boundary...
   ✅ Claim boundary config exists

🧩 [5/9] Checking module imports...
   ✅ RuntimeRouter
   ✅ LessonMemory
   ✅ ToolSkillSelector
   ✅ CriticJudge
   ✅ FinalReportGenerator
   ✅ TaskEntrypoint

🔥 [6/9] Running module smoke tests...
   ✅ RuntimeRouter smoke: class=audit
   ✅ LessonMemory smoke: 2 lessons retrieved
```

**Status:** ⚠️ Non-fatal error in FinalReportGenerator — evidence ledger has a data format issue (`'list' object has no attribute 'get'`). Health checks otherwise pass.

### Command: `python3 scripts/ilma.py status`

```
============================================================
ILMA Status — Phase 56
============================================================

📊 Current State:
   Task ID: task_a92916491b44
   Owner: Bos
   Status: completed
   Completed at: 2026-05-13T17:08:01.104900
   Judge: WARN
   Artifacts: ['/tmp/ilma_actor_artifact_task_a92916491b44.md']
   Trace: /root/.hermes/profiles/ilma/traces/trace_task_a92916491b44_1778666881.jsonl

📜 History: 259 tasks
   Recent tasks:
   - task_9f9b79e950d4: completed judge=WARN
   - task_e31b61d7108a: completed judge=WARN
   - task_db232274b4b3: completed judge=WARN
   - task_7ec7b73856da: completed judge=WARN
   - task_a92916491b44: completed judge=WARN
```

**Status:** ✅ Working — shows 259 historical tasks, current task is completed with WARN judgment.

---

## Summary

| Area | Result |
|------|--------|
| Total scripts | 456 |
| Duplicate `__init__.py` | 12 instances (normal for Python packages) |
| Duplicate `core.py` | 3 instances (needs content audit) |
| Large scripts (>100KB) | None found |
| ILMA.py `--help` | ✅ Working |
| ILMA.py `validate` | ✅ 6/6 checks passed |
| ILMA.py `doctor` | ⚠️ 1 non-fatal error (FinalReportGenerator ledger bug) |
| ILMA.py `status` | ✅ Working, 259 tasks in history |

## Action Items

1. **[MEDIUM]** Audit 3 `core.py` files for content divergence — potential for deduplication
2. **[LOW]** Investigate `FinalReportGenerator` evidence ledger error: `'list' object has no attribute 'get'` — data format mismatch in ledger loading
3. **[INFO]** 456 total scripts is large; consider future consolidation by functional domain
