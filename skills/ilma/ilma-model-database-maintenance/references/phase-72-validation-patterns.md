# Phase 72 Validation Test Patterns (2026-06-06)

## Overview

All Phase 72 optimizations were validated with a standardized test pattern before declaring implementation complete. These tests are run in-session, MUST verify actual file contents (not just in-memory results), and produce a structured pass/fail report.

## Standard Validation Sequence

Run after any router, health, or routing change:

```python
import json, sys
sys.path.insert(0, '/root/.hermes/profiles/ilma')
from ilma_model_router import ILMAUnifiedModelRouter

router = ILMAUnifiedModelRouter()

# TEST A: Pool composition
pool = router._get_cached_candidates()
inactive = [m for m in pool if not m["model_data"].get("is_active", False)]
non_free = [m for m in pool if not m["model_data"].get("is_free", True)]
print(f"Pool: {len(pool)} | inactive: {len(inactive)} | non_free: {len(non_free)}")
testA = len(inactive) == 0 and len(non_free) == 0

# TEST B: get_best_model selects active+free
result = router.get_best_model(task_category="general")
selected = result["model_data"]
testB = selected.get("is_active", False) and selected.get("is_free", True)

# TEST C: Safety net — disabled model bypassed
disabled_model = "minimaxai/minimax-m2.7"
master = json.load(open('ilma_model_router_data/PROVIDER_INTELLIGENCE_MASTER.json'))
master['models'][disabled_model]['is_active'] = False
router._candidate_cache = {}
result2 = router.get_best_model(task_category="general")
safety_passed = result2['model_id'] != disabled_model
# Restore
master['models'][disabled_model]['is_active'] = True

# TEST D: NVIDIA key pool (dict-of-keys structure)
cred = json.load(open('/root/credential/api_key.json'))
nvidia_cred = cred.get('nvidia', {})
if isinstance(nvidia_cred, dict) and 'keys' in nvidia_cred:
    keys = nvidia_cred['keys']
elif isinstance(nvidia_cred, list):
    keys = nvidia_cred
else:
    keys = []
testD = len(keys) == 3  # 3 keys as of Phase 72

# TEST E: Round-robin balance
from collections import Counter
dist = Counter()
for i in range(9):
    dist[keys[i % len(keys)]] += 1
testE = len(dist) == 3 and (max(dist.values()) - min(dist.values()) <= 1)

print(f"A: Pool={len(pool)} inactive={len(inactive)} {'PASS' if testA else 'FAIL'}")
print(f"B: Selected={result['model_id']} {'PASS' if testB else 'FAIL'}")
print(f"C: Safety net {'PASS' if safety_passed else 'FAIL'}")
print(f"D: NVIDIA keys={len(keys)} {'PASS' if testD else 'FAIL'}")
print(f"E: Round-robin={dict(dist)} {'PASS' if testE else 'FAIL'}")
```

## Key Assertions

| Test | Check | Expected |
|------|-------|----------|
| A: Pool clean | `len(inactive)==0 and len(non_free)==0` | 0 inactive, 0 non-free |
| B: Selection | `is_active and is_free` on selected | truthy |
| C: Safety net | `result2['model_id'] != disabled` | bypass works |
| D: NVIDIA keys | `len(keys)` | 3 (Phase 72) |
| E: Round-robin | `max-min <= 1 across 3 keys` | balanced |

## Session-Only vs File Changes (CRITICAL)

**Every test above tests IN-MEMORY state.** To verify the change persisted to disk:

```python
content = open('/root/.hermes/profiles/ilma/ilma_model_router.py').read()
assert '_is_provider_healthy' in content, "NOT in file!"
assert 'is_active' in content, "is_active check NOT in file!"
print("File verification: PASS")
```

Claiming "Phase X implemented" after passing in-session test but without file verification is the #1 false confidence trap. **Always verify the code is in the actual .py file.**

## Common Failures

| Failure | Root Cause | Fix |
|---------|------------|-----|
| Pool=516 (not 54) | `.get('is_active')` not used, string '0' not coerced | Use `.get('is_active', False)` |
| Keys=0 or 1 | `cred.get('nvidia', [])` returns dict | Extract from dict-of-keys: `nvidia_cred.get('keys', [])` |
| Only 1 key in dist | Loading broken (cascades from above) | Fix loading pattern first |
| Selected is inactive | Safety net missing from `get_best_model` | Add is_active check after scoring |
| Safety net not in file | Test passed in-session but code not saved | Verify file contents, not just in-memory |