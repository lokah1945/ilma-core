# SSS Upgrade v3.0 — Session Learnings
**Date:** 2026-05-17
**Type:** End-to-end upgrade implementation

## Context
Executed full SSS+++ upgrade from `/root/konsep/ILMA_UPGRADE_v3.0/` into ILMA profile.
Package contains: 5 Python components + bash installer + YAML config.

---

## Bugs Found & Fixed During Install

### Bug 1: `free_model_allowlist.json` dict structure
**File:** `ilma_provider_intelligence_enricher.py`
**Symptom:** `TypeError: unhashable type: 'dict'` at line 212
**Root cause:** Allowlist is `{"version": "...", "updated": "...", "models": [{...}, ...]}` not flat list. The `_load_all()` method assumed list or flat dict.
**Fix:**
```python
# Before (broken):
self._free_allowlist = set(fl.get("models", []))

# After (fixed):
models_list = fl.get("models", [])
if models_list and isinstance(models_list[0], dict):
    self._free_allowlist = set(
        m.get("model_id", m.get("id", "")) for m in models_list if isinstance(m, dict)
    )
else:
    self._free_allowlist = set(models_list)
```
**When to apply:** Any code that loads `free_model_allowlist.json` must handle `models: [{model_id, provider, ...}, ...]` structure.

### Bug 2: Tuple subscript error in router fallbacks
**File:** `ilma_smart_model_router.py`, line ~603
**Symptom:** `TypeError: 'ModelCandidate' object is not subscriptable`
**Root cause:** `scored` is `List[Tuple[float, ModelCandidate]]`. Buggy code tried `s[1]` on a `ModelCandidate` directly (after sort).
**Fix:**
```python
# Before (broken):
fallbacks = [s[1].to_dict() for _, s in scored[1:n_fallbacks + 1]]

# After (fixed):
fallbacks = [cand.to_dict() for _, cand in scored[1:n_fallbacks + 1]]
```

---

## Installation Workflow (Verified)

1. **Backup first** — `cp -r /root/.hermes/profiles/ilma /root/backups/ilma_sss_upgrade/ilma_backup_$(date +%Y%m%d_%H%M%S)`
2. **Run installer** — `cd /root/konsep/ILMA_UPGRADE_v3.0/ilma_sss_upgrade && chmod +x scripts/ilma_upgrade_installer.sh && bash scripts/ilma_upgrade_installer.sh`
3. **Fix any bugs** caught during install (don't stop at errors)
4. **Enrich DB** — `python3 ilma_provider_intelligence_enricher.py --enrich`
5. **Validate** — `python3 ilma_provider_intelligence_enricher.py --validate`
6. **Test router** — `python3 ilma_smart_model_router.py --stats` + routing test
7. **Test orchestrator** — `python3 ilma_master_orchestrator.py --task "hello world"`
8. **Test quality gate** — inline Python test
9. **Merge config** — update `config.yaml` with SSS overrides (model_router, orchestrator, fallback, security keys)
10. **Final verification** — all 6 Python files parse + import + execute

---

## Key Results
- 1,478 models enriched, 906 with benchmark scores, 22.3% benchmark coverage
- Router routing test: `heavy_coding/developer` → `nvidia/DeepSeek-R1` (score=0.759)
- Orchestrator test: `hello world` → 2 tasks, 2 batches, 0.36s, 100% success
- Quality gate: Verdict=PASS on test input
- All 6 files: syntax ✅ + import ✅ + execute ✅

## Files Installed
| File | Size |
|------|------|
| `ilma_master_orchestrator.py` | 34KB |
| `ilma_quality_gate.py` | 27KB |
| `ilma_smart_model_router.py` | 34KB |
| `ilma_provider_intelligence_enricher.py` | 17KB |
| `ilma_dag_pipeline.py` | 23KB |
| `ilma_fallback_cascade.py` | 18KB |
| `config_sss.yaml` | 10KB |

## Enricher Bug Pattern
The enricher's `_load_all()` method for `free_model_allowlist.json` needs to handle **both** formats:
1. `["model_id_1", "model_id_2", ...]` — flat list
2. `{"models": [{"model_id": "...", "provider": "..."}, ...]}` — dict with list of dicts

Always check `isinstance(data[0], dict)` before deciding the set conversion strategy.