# SOT Runtime Audit Cleanup — 2026-07-02 Session

## Context

User requested: "optimalkan system anda secara end to end dan komprehensif"

Ran `ilma_optimizer_daemon.py` → Health Score 0.974, 36/36 wired, but SOT runtime audit had 243 defects that auto-patch could not fully resolve.

## Defects Found & Fixed

| # | Defect Type | Count | Fix |
|---|-------------|-------|-----|
| 1 | Orphan aliases (provider removed) | 187 | Delete aliases where `canonical_provider` not in valid providers |
| 2 | Out-of-range composite_score | 1 | Clamp `antigravity/sarvamai/sarvam-m: 386 → 100` |
| 3 | String datetime in model_benchmark | 1358 | Convert ISO string → BSON datetime |
| 4 | Missing TTL index | 1 | Create `bm_fetched_ttl` (30 days) |
| 5 | Smoke test hardcoded model | 1 | Use dynamic active model lookup |
| 6 | Falsy `0.0 or -1` bug | 1 | Explicit `score is not None` check |

## Final Result

- **Defects**: 243 → 0
- **Smoke test**: FAIL → PASS
- **Loop validation**: 100/100 clean (21.8s)
- **Health Score**: 0.974 → 0.981
- **Commit**: `d103ad7` pushed to `master`

## Key Learnings

1. **`--patch` is not magic** — it handles common cases (score scaling, datetime conversion, score_tier consistency) but cannot infer business intent for orphan aliases or hardcoded test assumptions.

2. **Provider purge leaves aliases behind** — when removing a provider from MASTER, aliases pointing to it become orphans. Need explicit cleanup or a cascade-delete trigger.

3. **TTL indexes require BSON datetime** — ISO strings won't trigger expiration. Always convert before creating TTL.

4. **Smoke tests should be data-driven** — hardcoded model IDs break when the model is removed. Use `find_one({"status": "active"})` instead.

5. **Python falsy trap** — `0.0 or -1` returns `-1` because `0.0` is falsy. Use explicit `x is not None` for nullable numeric checks.

6. **Git push gotcha** — `state.db.compact` (251MB) exceeds GitHub limit. Must `.gitignore` before push. Branch is `master`, not `main`.

## Commands Used

```bash
# Initial optimizer run
python3 ilma_optimizer_daemon.py

# SOT audit (timed out at 120s, ran in background)
python3 sot/sot_runtime_audit.py --all

# Manual cleanup scripts (inline python3 -c)
# See SKILL.md "SOT Runtime Audit Cleanup Recipe" for full snippets

# Verification
python3 sot/sot_runtime_audit.py --audit
python3 sot/sot_runtime_audit.py --smoke
python3 sot/sot_runtime_audit.py --loop 100

# Git
git rm --cached state.db.compact
echo "state.db.compact" >> .gitignore
git add .gitignore && git commit --amend --no-edit
git push origin master
```

## Evidence IDs

- `ILMA-EVID-RUNTIME-AUDIT-20260702-030511` — initial audit (243 defects)
- `ILMA-EVID-RUNTIME-AUDIT-20260702-031209` — post-patch (192 remaining)
- `ILMA-EVID-RUNTIME-AUDIT-20260702-031434` — after alias cleanup (1 remaining)
- `ILMA-EVID-RUNTIME-AUDIT-20260702-031504` — after score clamp (0 defects)
- `ILMA-EVID-RUNTIME-AUDIT-20260702-031508` — smoke test (TTL fail)
- `ILMA-EVID-RUNTIME-AUDIT-20260702-031611` — smoke test (model fail)
- `ILMA-EVID-RUNTIME-AUDIT-20260702-031622` — smoke test PASS, 100/100 loop clean
