# Wrapper FREE_ONLY Policy Inconsistency — 2026-07-29

## Symptom
FREE_ONLY policy (filter to only free-tier models) inconsistent across wrappers:
- wrapper-nous (9102): `FREE_ONLY=true`
- wrapper-opencode (9103): `FREE_ONLY=true`
- wrapper-blackbox (9104): `FREE_ONLY=true`
- wrapper-vercel (9105): `FREE_ONLY=false`
- wrapper-openrouter (9106): `FREE_ONLY="no"` (string, not boolean)
- wrapper-nvidia-python (9101): No FREE_ONLY concept (uses NVIDIA keys)

## Root Cause
Each wrapper implements FREE_ONLY independently:
- nous/opencode/blackbox: env `FREE_ONLY=true` parsed as boolean
- vercel: env `FREE_ONLY=false` parsed as boolean
- openrouter: env `FREE_ONLY=no` parsed as string comparison
- nvidia-python: No FREE_ONLY at all (all models require NVIDIA account deployment)

## Fix Required
Centralize in `common/env_config.py`:

```python
# common/env_config.py
import os

def free_only_enabled() -> bool:
    """Unified FREE_ONLY policy across all wrappers."""
    val = os.environ.get("FREE_ONLY", "true").lower()
    return val in ("true", "1", "yes", "on")

# Per-wrapper override (optional)
WRAPPER_FREE_ONLY_OVERRIDE = {
    "nvidia-python": False,  # NVIDIA models all require account deployment
    "vercel": False,         # Vercel curated list has no :free models
}
```

Each wrapper imports:
```python
from common.env_config import free_only_enabled
```

## Verification
```bash
# All wrappers should respect FREE_ONLY env consistently
FREE_ONLY=true curl http://localhost:9102/v1/models | jq '.data[].id'  # Only :free models
FREE_ONLY=false curl http://localhost:9102/v1/models | jq '.data[].id'  # All models
```

## Related
- `references/wrapper-nous-missing-endpoints.md`
- `references/wrapper-bind-host-inconsistency.md`