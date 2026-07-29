# FREE_ONLY Policy Inconsistency Across Wrappers — 2026-07-29

## Current State
| Wrapper | Port | FREE_ONLY | Source |
|---------|------|-----------|--------|
| wrapper-nous | 9102 | TRUE | `.env` `FREE_ONLY=true` |
| wrapper-opencode | 9103 | TRUE | `.env` `FREE_ONLY=true` |
| wrapper-blackbox | 9104 | TRUE | `.env` `FREE_ONLY=true` |
| wrapper-vercel | 9105 | FALSE | `.env` `FREE_ONLY=false` |
| wrapper-openrouter | 9106 | "no" | `.env` `FREE_ONLY=no` |
| wrapper-nvidia-python | 9101 | N/A | NOT DEPLOYED |

## Problems
1. **Inconsistent values**: `true`, `TRUE`, `false`, `no` — no canonical boolean
2. **No central policy**: Each wrapper decides independently
3. **Vercel/vercel-wrapper** has NO free models (curated list has no `:free` suffix) → returns 0 models when FREE_ONLY=true

## Standard
- **Central config**: `/root/wrapper/common/env_config.py` with `FREE_ONLY_DEFAULT = True`
- **Per-wrapper override**: `.env` can set `FREE_ONLY=true|false` (lowercase canonical)
- **All wrappers import from common**: `from common.env_config import free_only_enabled`

## Fix
1. Create `/root/wrapper/common/env_config.py`:
```python
import os

FREE_ONLY_DEFAULT = True

def free_only_enabled() -> bool:
    val = os.environ.get('FREE_ONLY', '').strip().lower()
    if val in ('1', 'true', 'yes', 'on'):
        return True
    if val in ('0', 'false', 'no', 'off'):
        return False
    return FREE_ONLY_DEFAULT
```

2. Update each wrapper's `.env` to use `FREE_ONLY=true|false` (lowercase)

3. Update wrapper code to import from common:
```python
from common.env_config import free_only_enabled
# replace: if free_only_enabled(): ...
```

## Related
- `references/wrapper-vercel-free-only-zero-models.md` — Vercel edge case
- `ilma-wrapper-production-audit` — Audit checks FREE_ONLY consistency