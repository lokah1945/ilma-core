# SOT Cascade Enforcement Engine — 2026-07-01

## Session Summary

Built and applied a unified 4-phase cascade enforcement engine (`sot_cascade_enforcement.py`)
that resolved ALL T1→T2→T3 integrity violations in a single `--apply` pass.

## Engine Architecture

**File:** `sot/sync/sot_cascade_enforcement.py`
**CLI:**
```bash
python3 sot_cascade_enforcement.py              # dry-run (default)
python3 sot_cascade_enforcement.py --apply       # execute mutations
python3 sot_cascade_enforcement.py --json         # JSON output for CI
```

### Phase A — Zombie Kill (T1 inactive → remove downstream)
- Deactivate T2 zombie: provider exists in T2 but T1 is inactive → `is_active=False, disabled_at=now()`
- Deprecate T2 orphan: provider exists in T2 but NOT in T1 AND not curated → `status='deprecated'`
- Deactivate T3 zombie: models with `is_active=True` but provider inactive in T1 → `is_active=False, disabled_at=now()`
- Safety guard: abort if >50% of active models would be deactivated

### Phase B — Missing Create (T1 active → ensure downstream)
- Create missing T2 from T1 siblings using `_build_t2_from_t1()` fallback
- `_build_t2_from_t1()` respects `free_bypass` (P-CASCADE-26): providers with
  `free_bypass=True` are treated as active even with `key_status=INVALID`
- Update existing T2 where status drifts from T1
- Trigger T3 sync for providers with available endpoints (skipped otherwise)

### Phase C — Data Integrity (contradictions + backfill)
- Fix `is_active=True` + `disabled_at` contradictions → flip `is_active=False`
- Backfill `aggregate_status` on T2 from T1 sibling key_status aggregation
- Clean stale fields (`is_free_final`, `free_tier`)

### Phase D — Verify (post-enforcement alignment)
- Re-runs all checks from Phase A/B/C in verification mode
- Reports remaining violations (if any)
- `aligned=True` = zero violations

## Execution Results

### Dry-Run (2026-07-01T15:02:20)

| Phase | Finding |
|-------|---------|
| A | T2 zombie: opencode → would_deactivate |
| A | T2 orphan: google → would_mark_deprecated |
| A | T3 zombie: byteplus(48) + opencode(20) → would_deactivate |
| B | Missing T2: aimlapi, groq (free_bypass), minimax, ollama, together → would_create |
| B | T3 sync skipped: 8 providers (no sync endpoint) |
| C | Contradictions: 688 active_with_disabled_at |
| C | aggregate_status_backfilled: 19 |

### Apply (2026-07-01T15:11:12)

| Phase | Mutations |
|-------|-----------|
| A | T2: 2 mutations (opencode deactivated, google deprecated) |
| A | T3: 68 mutations (byteplus 48 + opencode 20 deactivated) |
| B | T2: 5 created (aimlapi, groq, minimax, ollama, together — all via fallback) |
| C | T3 contradictions fixed: 620 (68 were already handled by Phase A → overlap) |
| C | aggregate_status backfilled: 23 |
| D | **aligned=True** ✅ |

### Post-Apply Backfill (is_active=None)

19 T2 docs had `status=active` but `is_active=None` (legacy drift, P-CASCADE-27).
Applied:
```python
db.providers.update_many({'status': 'active', 'is_active': None},
    {'$set': {'is_active': True, '_backfilled_is_active_at': now}})
# Result: 19 modified
```

### Final E2E Verification (2026-07-01)

```
═══ FORWARD INTEGRITY (T1→T2→T3) ═══
F1 T1-live→T2-active: 0 ✅
F2 T1-inactive→T2-active: 0 ✅
F3 T1-inactive→T3-active: 0 ✅
F4 Contradictions: 0 ✅

═══ REVERSE INTEGRITY (T3→T2→T1) ═══
R1 T3-active→T2-active: 0 ✅
R2 T2-active→T1-live: 0 ✅
R3 T1-live→T2-inactive: 0 ✅

═══ TOTAL VIOLATIONS: 0 ═══
ALIGNED ✅
```

### Runtime Read Verification (c7)

| Consumer | Query Pattern | Result |
|----------|---------------|--------|
| Model Router | `db.models.find({})` → filter `is_active is True` | ✅ 402 active models, 0 contradictions |
| SubAgent Router | Same as model router, filter `is_free=True` | ✅ 274 free+active models |
| Kanban | `db.providers.find({})` → `is_active is True` | ✅ 36 active, 0 with `is_active=None` |

## Before/After State

| Metric | Before | After |
|--------|--------|-------|
| T3 Contradictions | 688 | 0 |
| T2 Zombie | 1 | 0 |
| T3 Zombie | 68 | 0 |
| Missing T2 | 5 | 0 |
| T2 is_active=None | 19 | 0 |
| aggregate_status set | 0 | 23 |
| Forward/Reverse Integrity | NOT ALIGNED | ALIGNED ✅ |
| T2 Active providers | 28 | 36 |
| T3 Active models | ~1090 | 402 |
| T3 Active providers | 11 | 7 |

**Note:** Active model count dropped 1090→402 because 688 contradictions were fixed
(models that had `is_active=True` + `disabled_at` were actually dead). The 402 is the
TRUE active count.

## Key Patterns Discovered

1. **free_bypass cascade as live** — groq: key_status=INVALID but free_bypass=True →
   cascade engine must treat as live (P-CASCADE-26)

2. **is_active=None is a distinct state from False** — Python `is_active is True`
   returns False for None. Verification scripts must handle this or backfill.

3. **Contradiction count differs between checks** — 688 models have both `is_active=True`
   AND `disabled_at`. When Phase A deactivates 68 zombie models (overlap), Phase C sees
   only 620 remaining. Both numbers are correct — they measure different stages.

4. **Missing T3 after enforcement is acceptable** — 10 providers have T2 active but no
   T3 models because they lack sync endpoints. This is not a violation (P-CASCADE-29).

## Audit Scripts Location

- Cascade enforcement engine: `sot/sync/sot_cascade_enforcement.py`
- E2E integrity verify: `/tmp/sot_c6_verify.py`
- Runtime read verify: `/tmp/sot_c7_test.py`
- is_active backfill: `/tmp/sot_backfill_is_active.py`
