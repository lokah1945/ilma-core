# Phase 13 Remaining Work — ILMA v3.1

> Plan Date: 2026-05-09
> Status: PLANNED (execution pending)

## 📊 Current Baseline

| Metric | Value | Notes |
|--------|-------|-------|
| Tests | 345/345 PASS | ✅ All fixed |
| Production files | 216 | Unique count |
| Test count | 345 | All passing |
| Duplicate pairs analyzed | 35 | 0 false positives |
| Duplicate classes merged | 6 | Phase 12G done |
| Placeholder files removed | 37 | Phase 12H done |
| Orphan modules integrated | 14 | Phase 12I done |
| Phase 13A Baseline | ✅ DONE | 345 tests, 216 files |
| Phase 13B Duplicate Triage | ⚠️ PARTIAL | 35 pairs analyzed, decisions pending |
| Phase 13C-K | ❌ NOT STARTED | 9 phases remaining |

## 🎯 Phase 13B — Duplicate Resolution Decisions

### MERGE (Safe) — Execute Phase 13C
| Class | Source | Target | Reason |
|-------|--------|--------|--------|
| `CircuitState` | `services/circuit_breaker.py` | `resilience/circuit_breaker.py` | Same functionality, resilience is canonical |

### KEEP_NAMESPACED — Architectural Decision
| Class | Reason |
|-------|--------|
| `DeliveryResult` | `@dataclass` vs `Enum` — different types, same name |
| `WebhookDelivery` | Class vs dataclass — different interfaces |
| `RateLimiter` | 3 versions in different domains (api_gateway, middleware, api_integration) |
| `MetricsCollector` | Different implementations per domain |
| `HealthStatus` | Already merged in Phase 12G |
| `CacheEntry` | Already merged in Phase 12G |
| `Alert` | Already merged in Phase 12G |
| `WorkflowState` | Already merged in Phase 12G |

### DECISION: Execute ONLY `CircuitState` merge for Phase 13C

## 📋 Phase 13 Tasks

### Phase 13C: Safe Deduplication (CircuitState only)
```
Files: services/circuit_breaker.py → deprecate, import from resilience/
Steps:
1. Create import alias in services/circuit_breaker.py
2. Mark CircuitState as deprecated
3. Update imports across codebase
4. Run tests
```

### Phase 13D: Services Hub Decomposition
```
Problem: services/ has 36 files (target: ≤20)
Approach:
1. Categorize services into subdirectories
   - api_services/ (8 files)
   - data_services/ (6 files)
   - integration_services/ (5 files)
   - monitoring_services/ (4 files)
2. Create __init__.py exports
3. Update all import references
4. Verify tests pass
```

### Phase 13E: Orphan/Dead Code Classification
```
Status: 34 orphan modules identified
Action: Classify each as:
- VALID_ORPHAN (intentionally isolated) → document
- NEEDS_INTEGRATION → add imports
- DEAD_CODE → remove
- DEPRECATED_CANDIDATE → add deprecation warning
```

### Phase 13F: Test Depth Expansion
```
Current: 345 tests, 73.5% module coverage
Target: 400+ tests, 85%+ module coverage
Priority: auth/, api_gateway_ext/, data_pipeline_ext/
```

### Phase 13G: Capability Registry Evidence Hardening
```
35 capabilities verified in Phase 12E
5 PROVISIONAL need evidence
Action: Add evidence_id to all 35, verify runtime behavior
```

### Phase 13H: Dependency Graph Health
```
Current: 117 internal edges, 158 isolated files (73%)
Target: ≥120 internal edges, ≤150 isolated (≤69%)
Action: Add cross-module imports for key modules
```

### Phase 13I: Security Review v4
```
Phase 12 found 3 HIGH (expected in test files)
Action: Run full security scan on production code
Target: 0 HIGH severity in production
```

### Phase 13J: Performance Regression Check
```
Run benchmark on critical paths:
- 216 file compilation time
- 345 test execution time
- Import resolution speed
```

### Phase 13K: Documentation Update
```
Update:
- docs/ILMA_PHASE13A-K_REMAINING_WORK_*.md (this file)
- SOUL.md Phase 13 status
- capability_registry.json
```

### Phase 13L: Regression Check
```
Final: Run full test suite, verify 345/345 PASS
```

### Phase 13M: Final Report
```
Create: docs/ILMA_PHASE13_FINAL_REPORT_2026-05-09.md
Include: All metrics, decisions, evidence
```

## 🕐 Time Estimate

| Phase | Estimated Time |
|-------|---------------|
| 13C (dedup) | 15 min |
| 13D (services) | 45 min |
| 13E (orphan) | 20 min |
| 13F (tests) | 30 min |
| 13G (capability) | 15 min |
| 13H (dependency) | 20 min |
| 13I (security) | 15 min |
| 13J (performance) | 15 min |
| 13K (docs) | 20 min |
| 13L (regression) | 10 min |
| 13M (report) | 15 min |
| **TOTAL** | **~3.5 hours** |

## 🚀 Execution Approach

Use `subagent-driven-development` pattern:
- Phase 13C: Direct execution (1 file change)
- Phase 13D: Dispatch subagent (complex refactoring)
- Phase 13E-G: Direct execution (classification + updates)
- Phase 13H-I: Direct execution (imports + scan)
- Phase 13J: Benchmark run (no subagent)
- Phase 13K-M: Direct execution (docs)

## ✅ Completion Criteria

- [ ] 345/345 tests PASS
- [ ] 1 duplicate class merged (CircuitState)
- [ ] Services hub ≤20 files per subdirectory
- [ ] All 35 capabilities have evidence_id
- [ ] 0 HIGH severity in production security scan
- [ ] Benchmark within ±10% of baseline
- [ ] Phase 13M final report written