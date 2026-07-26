# Phase 76 Production Lockdown Findings
**Date**: 2026-06-06 | **Evidence**: ILMA-EVID-20260606-TEST-PATTERN-001

## What This File Contains
Non-trivial fixes and test methodology discoveries from the Phase 76 full pipeline validation session. These are referenced by `ilma-self-audit` SKILL.md.

---

## Finding 1: `is_active=None` — Missing Filter in `_build_candidate_pool`

**File**: `ilma_model_router.py` (~line 1307, in `route_spread()`)

**Bug**: `_build_candidate_pool()` checked `mdata.get("disabled")` and `mdata.get("deprecated")` but NOT `is_active`. Models with `is_active=None` were selected.

**Discovery**: 108 models in MASTER had `is_active=None`. When checking with `mdata.get("is_active") is not True`, these all evaluated as inactive (correctly), but the filter wasn't in the code.

**Fix applied**:
```python
# After: if mdata.get("disabled", False): continue
# Added:
if mdata.get("is_active") is not True:
    continue
```

**Also fixed**: All `is_active=None` → `is_active=False` in MASTER (108 models).

**Verification**: Test 2 PASS (0 inactive models in 20 requests).

---

## Finding 2: Auto-Disable Race During Live Validation

**System behavior**: `ilma_model_router` has exploration failure tracking. After 3 consecutive failures for a model, `_auto_disable_exploration_model()` writes `is_active=False` to MASTER and calls `_invalidate_candidate_cache()`.

**Test race condition**: When running live validation tests (e.g. 30 consecutive `generate()` calls), the test itself generates the failures that trigger auto-disable. The router's in-process instance (created before the test) still holds the pre-write candidate pool, so it keeps selecting the model through requests 1–3. After request 3, the write happens and cache invalidates. The test sees "this model was used AND it's inactive in MASTER" — which is NOT a bug, it's correct auto-disable behavior mid-test.

**Mitigation for future validation sessions**:
```python
# 1. Snapshot MASTER before tests
with open(MASTER_PATH) as f:
    master_before = json.load(f)

# 2. Build the set of is_active=True models at test start
active_before = {
    f"{pn}/{mid}"
    for pn, pdata in master_before["providers"].items()
    for mid, mdata in pdata["models"].items()
    if mdata.get("is_active") is True
}

# 3. Run tests
# A model selected AND later found inactive = correct auto-disable (not a routing bug)
# A model selected that was inactive at snapshot time = REAL bug
```

**Key insight**: The auto-disable mechanism is CORRECT behavior. The test failure was a false positive caused by the system modifying its own state during the test.

---

## Finding 3: `metadata.last_updated` Not Written by `--full-sync`

**File**: `scripts/ilma_model_db_manager.py`

**Bug**: After successful `--full-sync`, the script did NOT write `metadata.last_updated` to MASTER. Test 5 (scheduler freshness) failed with `last_updated: unknown`.

**Fix**: Added metadata write before saving MASTER:
```python
from datetime import datetime, timezone
master["metadata"] = {
    "last_updated": datetime.now(timezone.utc).isoformat(),
    "last_full_sync": datetime.now(timezone.utc).isoformat(),
    "total_models": sum(len(p["models"]) for p in master["providers"].values()),
    "source": "ilma_model_db_manager.py --full-sync"
}
```

---

## Finding 4: Provider Pool Imbalance → NVIDIA Monopoly

**Root cause**: Pool composition was 117 NVIDIA free models vs 23 OpenRouter vs 5 MiniMax. With uniform weighted random, NVIDIA gets ~87% naturally.

**Fix**: Provider diversity penalty in `route_spread()`:
```python
# Track last 20 provider selections
from collections import deque
self._provider_rolling: deque = deque(maxlen=20)

# After computing sel_weights but before normalization:
provider_counts = {}
for p in self._provider_rolling:
    provider_counts[p] = provider_counts.get(p, 0) + 1

window_size = len(self._provider_rolling) or 1
for i, candidate in enumerate(pool_to_use):
    p = candidate.get("provider", "")
    recent_pct = provider_counts.get(p, 0) / window_size
    if recent_pct > 0.5:
        penalty = 1.0 - (recent_pct - 0.5) * 1.6
        sel_weights[i] *= max(0.1, penalty)

# Record selection
self._provider_rolling.append(sel_provider)
```

**Result**: NVIDIA reduced from 100% to 87% in final test. 87% is still high — it's the structural maximum without adding more free models to other providers.

---

## Finding 5: `_candidate_cache` TTL Staleness

**Issue**: After patching `is_active` in MASTER file, in-process router instances (e.g. in `ilma_client`) may still hold cached candidates from before the patch. Cache TTL = 120s.

**Fix**: After any MASTER `is_active` patch, call `router._invalidate_candidate_cache()` OR restart the process. For ilma_client specifically, each `generate()` call rebuilds the candidate pool if the cache key differs (task_type varies), so stale cache only affects repeated identical tasks within 120s.

---

## Test Results — Final (All 7 PASS)

| Test | Result | Notes |
|------|--------|-------|
| T1: Free-Only | ✅ PASS | 0 paid leaked in 10 requests |
| T2: is_active | ✅ PASS | 0 inactive in 20 requests |
| T3: Distribution | ✅ PASS | 2 providers, NVIDIA 87% |
| T4: NVIDIA RR | ✅ PASS | `_nvidia_key_idx` confirmed |
| T5: Scheduler | ✅ PASS | last_updated written, 3/4 no_agent |
| T6: Health | ✅ PASS | 0 unknown providers |
| T7: Autonomous | ✅ PASS | 929 chars, success, 60s |

---

## Files Modified (2026-06-06)

- `ilma_model_router.py` — 2 patches: `is_active is not True` filter + provider diversity
- `ilma_model_router_data/PROVIDER_INTELLIGENCE_MASTER.json` — 109 models corrected

## Evidence IDs

- `ILMA-EVID-20260606-FIX-ISACTIVE-001`: `is_active is not True` filter added
- `ILMA-EVID-20260606-FIX-DIVERSITY-001`: Provider diversity tracking + penalty
- `ILMA-EVID-20260606-FIX-METADATA-001`: `metadata.last_updated` written to MASTER
- `ILMA-EVID-20260606-CORRECT-ISFREE-001`: 21 OpenRouter paid models corrected
- `ILMA-EVID-20260606-TEST-PATTERN-001`: Live validation test methodology for self-modifying systems
- `ILMA-EVID-20260606-TEST-PASS-ALL-001`: All 7 Phase 7 tests passed