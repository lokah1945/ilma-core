# ILMA Audit Defect Bank — 2026-07-09 session

Reusable defect patterns found during the comprehensive audit. Use as a checklist for future audits.

## F1 — HIGH — Duplicate dict key `is_free` (free-classification bug)
- **File:** `ilma_model_router.py:722,725`
- **Root cause:** Two `"is_free":` keys in one `record` dict literal. Line 725
  (`model_meta.get("is_free", False)`) wins over line 722 (which had fallback chain
  `intel.get("is_free", llm_meta.get("free_bypass", False))`).
- **Impact:** Models without `is_free` field in `model_meta` are classified PAID even if free
  in intel/provider. With `allow_paid=False` (ILMA default) they get blocked → wrong routing +
  unnecessary fallback cascade.
- **Fix:** Delete line 725; keep line 722's fallback chain.
- **Detection:** `grep -n '"is_free"' ilma_model_router.py` → count occurrences in one dict.

## F2 — MEDIUM-HIGH — Missing module import silently kills learning loop
- **File:** `ilma_workflow_ecc.py:1840` `from ilma_learning_memory import get_learning_memory`
- **Root cause:** Module `ilma_learning_memory` does NOT exist (0 files). Wrapped in `try/except`
  → workflow prints "⚠️ Learn step skipped" every task. Self-improvement in main pipeline is DEAD.
- **Fix:** Reroute to `ilma_learning_engine.get_learning_engine()` or `ilma_self_improve_integrator`.
- **Detection:** `grep -rn "from ilma_learning_memory import" .` → if only referrer, module missing.

## F3 — MEDIUM — Invalid JSON trailing comma in runtime contract
- **File:** `ilma_integration_manifest.json:32` — trailing comma after `}` in `cli_aliases`.
- **Impact:** `ilma_system_optimizer.py` `json.load` crashes (JS tolerates, Python rejects).
- **Fix:** Remove trailing comma at line 32.
- **Detection:** `python3 -c "import json; json.load(open('ilma_integration_manifest.json'))"`.

## F4 — MEDIUM — Bare except in SOT resolver
- **File:** `ilma_two_way_sync.py:191-192` `_resolve_remote_from_sot()` → `except Exception: pass`
- **Impact:** If SOT lookup fails, silently falls back to .env with no log → masks root cause.
- **Fix:** Log the exception; return structured error.

## F5 — MEDIUM — Bare except (silent swallow) in router + health
- **Files:** `ilma_subagent_router.py:53-54,60`; `ilma_health_manager.py:141,152,221,307`
- **Fix:** At minimum `logger.warning(...)` in the except.

## F6 — MEDIUM — Bare except in autonomous loop
- **File:** `ilma_autonomous_loop_engine.py` (8+ `except: pass` in run_cycle path)
- **Fix:** Log exceptions; surface stuck state.

## F7 — LOW — Boot slowdown from tier auto-fix
- **Symptom:** 85 models `score_tier != computed_tier` auto-fixed every boot → 6.6s boot.
  Cosmetic (record uses computed tier anyway).
- **Fix:** Precompute tier during DB sync; skip boot-time fix loop.

## F8 — LOW — Mongo two-way sync `last_reconcile: null`
- **Symptom:** 6-hourly reconcile safety net never ran; change streams active (resume tokens present).
- **Fix:** Trigger `--reconcile` once; ensure scheduler runs it.

## F9 — LOW — SOUL.md vs registry docs drift
- **Symptom:** SOUL.md lists 33 legacy caps (`search`, `fact_checking`, `debugging`...); registry has
  37 new-taxonomy caps (`web_search`, `research`, `code_analysis`...). 22 names don't match.
- **Impact:** Capability-claim documentation mismatch (not a crash).
- **Fix:** Sync SOUL.md capability list to registry taxonomy.

## Things that were HEALTHY (don't re-audit blindly)
- Boot 10/10, runtime_wiring 37/37 OK, orphan_wiring 22/22 OK
- Browser: Phase69 CDP resolver compliant, profile isolation enforced, no raw-click misuse
- Mongo/SOT: SOT-first resolver active, `mongodb-cloud` doc present, sync daemon alive since Jul04, remote rs0 reachable
- Cron: 3 jobs `scheduled`, 0 error (Phase72 fix stable)
- Router E2E: route_and_execute success, circuit breaker + fallback cascade work
- Judge: `calculate_score` defensive `isinstance(r, dict)` (Phase70 fix intact)
- 110 root modules: 0 syntax errors
