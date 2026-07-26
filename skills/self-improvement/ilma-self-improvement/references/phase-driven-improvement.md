# ILMA Phase-Driven Self-Improvement Pattern
**Source:** Phase 14/15/16 (2026-05-09) — Systematic multi-phase improvement

---

## The Phase Execution Model

ILMA uses phased self-improvement cycles with strict governance:

| Phase | Focus | Output |
|-------|-------|--------|
| 14 | Core runtime repair, capability verification | 67→73 verified caps |
| 15 | Database hardening, services decomposition | 0 shell=True, 1 domain moved |
| 16 | Missing module resolution, 500-file planning | 80 verified, 2 modules created |

Each phase follows the **12-step pipeline**: A (freeze) → B (audit) → C (verify) → D (resolve) → E (resolve) → F (plan) → G (roadmap) → H (gate) → I (update) → J (regression) → K (report) → L/M (final).

---

## Key Learnings

### 1. Registry Was Wrong, Not Code

`workflow_ecc` was flagged UNVERIFIED but the code was fine. `parser.parse_args()` was on line 402 all along. The registry entry was stale — capability verification must test ACTUAL code, not trust registry claims.

### 2. Missing Script ≠ Capability Missing

`ilma_memory_layer.py` didn't exist. But 4 memory modules existed (`analytics`, `cleanup`, `persistence`, `search`). Create a compatibility shim that integrates them. Similarly, `ilma_qa_critic.py` didn't exist but `scripts/skills_exec/ilma_exec_qa_critic.py` (running since Phase 2) existed. Build a wrapper.

### 3. Deprecate Honestly

`mutation_bug_cycle`: No script found, no equivalent, concept not viable. Mark DEPRECATED. Don't fake VERIFIED.

### 4. Partial Capabilities Need Honest Classification

A capability is PARTIAL when:
- File exists but orchestrator missing
- File exists but 0 bytes
- Module exists but no runtime test
- File exists but depends on external deps

Keep PARTIAL with reason. Upgrade only with evidence.

### 5. Phase Scope Discipline

User says "don't start Phase 15 yet" → wait. Phase 14R first → report → wait for confirmation → THEN start Phase 15. Session handoff summary can say "Phase 15 in progress" but user instruction wins.

---

## Test Discipline for Capability Verification

For every capability upgrade, always run:

```python
# 1. Import test
from module_name import ClassName  # must not raise ImportError

# 2. Instantiate test
instance = ClassName()  # must not raise exception

# 3. Method tests (at least 3, actual behavior, not just hasattr)
result = instance.method_name(args)
assert result is not None

# 4. Full pytest maintained
pytest test_projects/phase10_250file_codebase/ -q --tb=no
# Must remain 345/345
```

---

## Evidence Discipline

Create evidence files for every capability upgrade:

```json
{
  "evidence_id": "ILMA-EVID-YYYYMMDD-P##-CAPABILITY-001",
  "capabilities": ["cap_name"],
  "phase": "P##",
  "verification_method": "import + instantiate + 3 method tests",
  "test_results": [...],
  "confidence": 0.72,
  "notes": "..."
}
```

---

## Readiness Gate Pattern

Before claiming readiness for next phase, verify:

1. Tests 345/345 ✅
2. Registry truthful (VERIFIED/PARTIAL/DEPRECATED counts honest)
3. Missing modules resolved or honestly marked
4. Security score 92%+
5. Dependency health 80%+
6. Evidence format stable
7. Rollback strategy documented
8. No false execution claims (plan ≠ execution)

Decision: `READY_FOR_PHASE{N}_PLANNING_ONLY` or `READY_FOR_PHASE{N}_PARTIAL_EXECUTION` or `NOT_READY`