# Phase 49 Pattern Reference: Body Integration + Real-Time Canary

**Source:** Phase 49 (2026-05-10) — 300-Minute Owner-Triggered System Integration
**Purpose:** Capture new patterns for future session reference

---

## 1. Body Integration Architecture

### Runtime Router (`scripts/ilma_runtime_router.py`)
Intent → TaskClass → Workflow → Capabilities → Tools → Skills

```python
class RuntimeRouter:
    def classify_intent(self, message: str) -> tuple[TaskClass, float]:
        """Returns TaskClass + confidence. Max 92%."""
        
    def route(self, task_class: TaskClass, confidence: float) -> RouteResult:
        """Returns workflow, capabilities, tools, skills, judge_rubric"""
```

**Task classes:** CODE, WRITE, RESEARCH, AUDIT, PLAN, INTERNAL, MULTI, UNSAFE

**Key fix:** Router confidence was inflated by `len(msg)`. Fixed to keyword-only only, max 92%.

### Capability Routing Matrix (`config/ilma_capability_routing_matrix.json`)
- 24 capabilities mapped to workflows/tools/skills/evidence
- Each entry: capability → workflow → tools → skills → evidence_id → judge_rubric

### Tool/Skill Selection Policy (`config/ilma_tool_skill_selection_policy.json`)
| Task Type | Primary Tools | Primary Skills | Fallback |
|-----------|--------------|----------------|----------|
| Coding | terminal, file, search | ilma-python-patterns, ilma-testing | decline_or_template |
| Writing | file | ilma-writing, ilma-documentation | outline_only |
| Research | web, search | ilma-research, arxiv | limited_sources_note |
| Audit | terminal, file, search | ilma-security-audit, ilma-code-review | limited_audit |
| Internal | file, terminal, search | ilma-self-improvement, ilma-learning | abort_and_report |
| Unsafe | none | none | safety_explanation_no_execution |

---

## 2. Real-Time Canary Protocol

### 5-Minute Gate (minimum)
```python
duration = 300  # seconds
start_time = time.monotonic()  # NOT time.time()
while (time.monotonic() - start_time) < duration:
    # cycle work
    heartbeat_check()
    checkpoint_check()
    time.sleep(remaining)
```

**Wall-clock measured via `time.monotonic()`** — not `time.time()` (wall-clock vs wall-clock, but monotonic is monotonic).

### Heartbeat (60s interval)
```python
print(f"[HEARTBEAT] Cycle {n}, {elapsed:.1f}s elapsed, {passed}/{total} passed")
```

### Checkpoint (every 10 min OR per-cycle)
```python
checkpoint_data = {
    'session_id': SESSION_ID,
    'checkpoint_at_cycle': n,
    'timestamp': time.time(),
    'passed': sum(1 for r in results if r['exit_code'] == 0)
}
with open(f'checkpoint-{n}-{SESSION_ID}.json', 'w') as f:
    json.dump(checkpoint_data, f, indent=2)
```

### Lesson Retrieval (CRITICAL)
```
Phase 48H BROKE: broad query "internal workflow optimization evidence..." → 0 results
Phase 49 FIXED: targeted multi-query with keyword extraction → 36 lessons
```

**Enhanced Lesson Retrieval (`scripts/ilma_enhanced_lesson_retrieval.py`):**
```python
# Auto-generate targeted queries
queries = [
    task.split()[0],  # first word
    ' '.join(task.split()[:3]),  # first 3 words
    forbidden_scope_terms,  # from contract
    failure_signature_terms,  # from previous phases
]
# Multi-query + dedup + rank by relevance
```

### Trace Export
```python
final_trace = {
    'session_id': SESSION_ID,
    'type': 'real_time_gate',
    'duration_seconds': elapsed,
    'actual_real_time': elapsed >= duration * 0.99,  # flag
    'total_cycles': len(results),
    'passed_cycles': passed,
    'heartbeats': heartbeat_count,
    'checkpoints': checkpoint_count,
    'results': results
}
```

---

## 3. Judge/Reflexion Rubric v2

10 criteria for self-verification:

| # | Criterion | Weight | Threshold | Penalty |
|---|-----------|--------|-----------|---------|
| 1 | unsafe_scope | 3.0 | 0.8 | REJECT_AND_WARN |
| 2 | missing_rollback | 2.0 | 0.7 | REJECT_PATCH |
| 3 | false_claims | 2.0 | 0.7 | DOWNGRADE_CLAIM |
| 4 | missing_evidence | 1.5 | 0.6 | MARK_PARTIAL |
| 5 | no_tests | 1.5 | 0.6 | REQUIRE_TESTS |
| 6 | no_trace | 1.0 | 0.5 | WARN_AND_LOG |
| 7 | capability_mismatch | 1.0 | 0.5 | REROUTE |
| 8 | weak_routing | 1.0 | 0.5 | REROUTE |
| 9 | lesson_not_used | 0.8 | 0.5 | WARN |
| 10 | artifact_too_generic | 0.8 | 0.5 | REQUIRE_REVISION |

**Decision matrix:** PASS | WARN | FAIL | REJECT

**Reflexion must produce:** root_cause + failed_criterion + revision_plan + safe_patch_plan + test_plan

---

## 4. Claim Boundary

### Can Claim ✅
- 35 capabilities (30 VERIFIED, 5 PROVISIONAL)
- Owner-triggered limited internal auto-learning
- Real-time 5-minute canary (300.00s wall-clock, x2 proven)
- Unified runtime router (7/7 correct)
- Lesson memory with search/dedup/reuse
- Actor-Critic-Reflexion-Lesson loop
- 179 tests PASS, weak VERIFIED = 0

### Cannot Claim ❌
- Real-time 30-min canary (only 5-min proven)
- Real-time 300-min autoloop (only 5-min proven)
- Production autonomous agent (safety contract)
- SSS+++ achieved (TARGET JANGKA PANJANG only)
- Always-on auto-learning (forbidden)
- Universal all-task ability (boundary exists)

### Forbidden Claims (hard block)
- "SSS+++ achieved" — aspirational only
- "Production autonomous agent" — safety contract
- "Always-on auto-learning" — explicitly forbidden
- "Universal all-task ability" — boundary exists
- "1000-file readiness" — unproven
- "Military-grade agent" — only as TARGET

---

## 5. Phase 49 Artifacts

| File | Purpose |
|------|---------|
| `scripts/ilma_runtime_router.py` | Intent → workflow router |
| `scripts/ilma_enhanced_lesson_retrieval.py` | Fixed retrieval (0 → 36) |
| `scripts/ilma_phase49h_optimization_cycles.py` | 15 cycle Actor-Critic loop |
| `scripts/ilma_phase49i_realtime_gate.py` | Real-time canary runner |
| `config/ilma_runtime_body_map.json` | Body metaphor |
| `config/ilma_capability_routing_matrix.json` | 24 cap → workflow/tool/skill |
| `config/ilma_runtime_routing_policy.json` | Task classifier rules |
| `config/ilma_tool_skill_selection_policy.json` | Tool/skill selection rules |
| `config/ilma_phase49_300min_autoloop_contract.json` | Safety contract |
| `config/ilma_judge_reflexion_rubric_v2.json` | Judge v2 + Reflexion |
| `config/ilma_claim_boundary.json` | What can/cannot claim |
| `docs/ILMA_PHASE49_*` | 15 phase docs |

---

## 6. Test Results

| Suite | Count | Result |
|-------|-------|--------|
| Project tests | 118 | ✅ PASS |
| Dedup tests | 5 | ✅ PASS |
| mark_reused tests | 5 | ✅ PASS |
| Router classification | 7/7 | ✅ PASS |
| Lesson retrieval | 5/5 | ✅ PASS |
| Capability registry | 35/35 | ✅ PASS |
| **Grand Total** | **179** | **✅ ALL PASS** |

weak VERIFIED = 0

---

## 7. Phase 50 Recommended Path

To reach READY_FOR_300MIN_OWNER_TRIGGERED_AUTOLOOP:

1. **Phase 50:** Real-time 30-minute canary (duration=1800s)
2. **Phase 51:** Implement background daemon for 300-minute
3. **Phase 52:** Prove 300-minute with checkpoint/resume
4. ... → SSS+++ (TARGET JANGKA PANJANG)

---

*Last Updated: 2026-05-10*
*Decision: READY_FOR_LIMITED_INTERNAL_SELF_OPTIMIZATION*