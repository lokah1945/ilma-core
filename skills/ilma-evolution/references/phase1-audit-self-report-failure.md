# Phase 1 Audit Failure: Self-Reported Data vs. Actual Source
**Created:** 2026-06-03
**Lesson:** Always verify claims against primary source data

---

## What Happened

Phase 1 audit claimed:
- 37 capabilities, 32 verified, **5 provisional**
- Missing modules: `ilma_free_webfetch`, `ilma_web_search`
- 284 skills

Actual `capability_registry.json` inspection revealed:
- **41 capabilities**, **41 verified**, **0 provisional**
- `web_fetch` and `web_search` do NOT appear as capability IDs in registry
- Skills are directory-based, not tracked in capability_registry.json

## Root Cause

Phase 1 audit was generated from **assumed/self-reported data** (possibly from a prior session's summary), NOT from actual file inspection. The audit's "provisional" capability names (planning, longform_writing, etc.) don't exist as capability IDs in the actual registry.

## Key Lessons

1. **Never trust Phase 1 audit claims without source verification.** The audit document itself became unreliable because it wasn't based on actual registry inspection.

2. **Source of truth is `capability_registry.json`.** The real registry lives at `/root/.hermes/profiles/ilma/capability_registry.json` with 41 entries under the `capabilities` key.

3. **Self-reported VERIFIED badge is meaningless without testing.** 56% of "VERIFIED" capabilities had broken implementation paths (23/41 failed smoke test).

4. **Module references in audit were fabricated.** The Phase 1 audit claimed certain modules were missing, but they were never referenced in the actual registry.

## Correct Procedure for Future Phase 1 Audits

```python
# Always verify from primary source FIRST
import json
with open('capability_registry.json') as f:
    registry = json.load(f)
caps = registry['capabilities']  # This is a dict, not a list

# Count actual statuses
statuses = {}
for cap_id, cap_data in caps.items():
    status = cap_data.get('status', 'UNKNOWN')
    statuses[status] = statuses.get(status, 0) + 1

# Then cross-reference with files
import os
for cap_id, cap_data in caps.items():
    path = cap_data.get('implementation_path', '')
    if path and not os.path.exists(path.split(',')[0].strip()):
        print(f"BROKEN: {cap_id} → {path}")
```

## Related Pitfall

This is not unique. Past Phase 14 also had false capability claims (VERIFY BEFORE CLAIMING). This pattern — assuming capability data without checking the actual registry — recurs across sessions.

**Pattern name:** "Self-Report Fallacy" — trusting the system's own claims about itself without external verification.

**Defense:** Always load and parse `capability_registry.json` directly. Never trust `ILMA_CAPABILITY_INVENTORY_AUDIT.md` or similar audit documents as authoritative sources — verify against the JSON.