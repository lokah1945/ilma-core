---
name: ilma-comprehensive-optimizer
description: "ILMA Comprehensive Optimizer Daemon v2.0 — End-to-end system optimization: Hermes update, capability scan, auto-wire, workflow/pipeline E2E, health check, self-improvement. Runs hourly via cron or on-demand via CLI."
triggers:
  - optimize
  - optimalisasi
  - system check
  - auto wire
  - update hermes
  - pipeline check
  - capability audit
---

# ILMA Comprehensive Optimizer Daemon v2.0

**Version:** 2.0 (Production)
**File:** `/root/.hermes/profiles/ilma/ilma_optimizer_daemon.py`
**Trigger:** Hourly cron (`a115de75d3ef`) + manual command
**Purpose:** Fully automated system optimization — Hermes update → capability scan → auto-wire → workflow/pipeline connect → verify → health check → self-improve → git sync

## 8-Step Pipeline

Each run executes all 8 steps in sequence:

| Step | Function | What it does |
|------|----------|--------------|
| 1 | Hermes Update | Check Hermes version, scan skills, detect new capabilities |
| 2 | Capability Scan | Scan all modules (317+), detect orphaned files, missing integrations |
| 3 | Auto-Wire | Detect unwired modules → add to appropriate layer in ilma_runtime_wiring.py |
| 4 | Workflow E2E | Verify all 8 pipeline layers are connected, check for disconnections |
| 5 | Wiring Verify | Import all 32 wired modules, report missing/errors |
| 6 | Health Check | Model health, direct API probe, disk, git sync, wiring integrity |
| 7 | Self-Improve Cycle | Run AutonomousLoopEngine (DISCOVERY→EVOLUTION 9-state loop) |
| 8 | Git Sync | Auto-commit if 5+ uncommitted files |

## CLI Commands

```bash
# One-shot full optimization (manual trigger)
python3 ilma_optimizer_daemon.py

# Continuous hourly mode
python3 ilma_optimizer_daemon.py --daemon

# Status check only (no changes)
python3 ilma_optimizer_daemon.py --status

# E2E verification only
python3 ilma_optimizer_daemon.py --verify

# Hermes update only
python3 ilma_optimizer_daemon.py --update-hermes
```

## Output Summary

Each run produces:
- **Health Score** (0.0-1.0) — weighted across all components
- **Pipeline Integrity** (%) — E2E layer connections
- **Wired Modules** (N/32) — import verification
- **Auto-wired** (count) — newly added to wiring
- **Hermes Version** — current Hermes Agent version
- **Skills Count** — total modules scanned
- **Self-Improve Cycle** (#N) — loop count from AutonomousLoopEngine
- **Optimizer Log** → `.learnings/optimizer_log.md`

## Cron Jobs

| Job ID | Name | Schedule | Action |
|--------|------|----------|--------|
| `a115de75d3ef` | ILMA Hourly Optimizer | `0 * * * *` | `python3 ilma_optimizer_daemon.py` |

## Key Features

1. **Hermes System Update** — Scans for new Hermes capabilities, skills, patterns on every run
2. **Auto-Wire Engine** — Detects unwired modules via layer keyword matching, auto-adds to wiring
3. **Pipeline E2E Check** — Regex-parses LAYER_* definitions, verifies each layer has expected modules
4. **Orphaned Module Detection** — Compares file list vs wiring content to find unwired files
5. **Missing Integration Detection** — Cross-references capability registry with actual file presence
6. **Self-Improvement Loop** — Runs AutonomousLoopEngine 9-state loop
7. **Health Score Calculation** — Weighted composite: model health, direct API probe, disk, git sync, wiring integrity
8. **PID Lock** — Prevents concurrent runs, auto-cleans stale locks

## Health Score Components

| Component | Weight | What it checks |
|-----------|--------|---------------|
| Model Health | ~20% | Unavailable rate in model_health_state.json |
| Bridge Proxy | ~20% | HTTP 200 on localhost:8001/health |
| Disk | ~20% | Usage < 90% |
| Git Sync | ~20% | Uncommitted files < 20 |
| Wiring Integrity | ~20% | Imported modules / total wired |

## Known Behaviors

- "Orphaned modules" count (268) is high because many files in ILMA root aren't in the wiring contract — utilities, monitoring tools, etc.
- Auto-wire currently logs would-add but doesn't actually modify wiring (safety check)
- Pipeline E2E shows "Issues: 1" — means one workflow issue detected (WORKFLOW_ECC references)
- Self-Improve cycle count shows #0 because engine.run_cycle() is called fresh each time
- **NumPy/matplotlib ABI note**: If wiring shows 38/39 with 1 error in `ilma_chart_generator`, this is a NumPy 2.x + system matplotlib 3.6.3 ABI mismatch. Fix: `pip install 'numpy<2' --break-system-packages`. See `ilma-optimization-pattern` skill, pitfall #25.

## Runtime readiness check (Phase 76+ addition)

The optimizer is **data plane aware** but not **business logic aware**. Wiring integrity + health score = "is the system structurally sound", but does NOT = "can the router actually pick a model". 

For full production-ready gate, also run `ilma-runtime-readiness-audit` skill:

```bash
cd /root/.hermes/profiles/ilma/sot
python3 sot_runtime_audit.py --all
python3 sot_runtime_audit.py --loop 1000
```

**Why both are needed**: SOT governance audit (Phase 74-76) checks data shape (schema, indexes, datetime, dedup). Runtime audit (Phase 76+) checks business logic (composite_score range, status/is_active consistency, alias resolution, 1000x loop). SOT pass ≠ runtime ready. The 2026-06-15 session found 2 critical logic defects (score 0-1 vs 0-100, status/is_active contradiction) that SOT governance missed entirely.

Add to optimizer's Step 6 (Health Check):
- 12/12 runtime audit checks pass
- 8/8 smoke test scenarios pass
- 1000/1000 loop iterations clean

These complement the existing health score (model health, direct API probe, disk, git sync, wiring integrity) by adding "data is usable by runtime, not just well-formed".

## SOT Runtime Audit Cleanup Recipe (2026-07-02)

When `sot_runtime_audit.py --audit` reports defects that `--patch` cannot auto-fix, apply these manual fixes in order. Each is idempotent.

### 1. Orphan aliases (pointing to removed providers)

Symptom: `[7/12] alias integrity... N defects` where `--patch` reports `Patch alias incomplete... 0 fixed`.

Root cause: aliases reference providers that no longer exist in `models` collection (e.g. `minimax`, `together` after provider purge).

Fix:
```python
import pymongo, os
MONGO_PASS = os.environ.get('ILMA_MONGO_PASS') or next(
    (_l.split('=',1)[1].strip() for _l in open('/root/.hermes/.env') if _l.startswith('ILMA_MONGO_PASS=')), ''
)
client = pymongo.MongoClient(host='127.0.0.1', port=27017, username='ilma_sync', password=MONGO_PASS)
db = client['credentials']

valid_provs = set(d['provider'] for d in db['models'].find({}, {'provider': 1, '_id': 0}))
deleted = 0
for a in db['model_alias'].find({}):
    if a.get('canonical_provider') and a['canonical_provider'] not in valid_provs:
        db['model_alias'].delete_one({'_id': a['_id']})
        deleted += 1
print(f'Deleted {deleted} orphan aliases')
```

### 2. Out-of-range composite_score

Symptom: `[2/12] intelligence.score invalid... N defects` (typically 1).

Root cause: a model has `composite_score > 100` or `< 0` (e.g. `antigravity/sarvamai/sarvam-m: 386`).

Fix:
```python
db['model_intelligence'].update_many({'composite_score': {'$gt': 100}}, [{'$set': {'composite_score': 100}}])
db['model_intelligence'].update_many({'composite_score': {'$lt': 0}}, [{'$set': {'composite_score': 0}}])
```

### 3. Missing TTL index on model_benchmark

Symptom: smoke test fails on `benchmark_ttl_present: False`.

Root cause: `fetched_at` stored as ISO string, not BSON datetime — TTL index requires BSON datetime.

Fix:
```python
from datetime import datetime
# Convert string → BSON datetime
for doc in db['model_benchmark'].find({'fetched_at': {'$type': 'string'}}):
    try:
        dt = datetime.fromisoformat(doc['fetched_at'].replace('Z', '+00:00'))
        db['model_benchmark'].update_one({'_id': doc['_id']}, {'$set': {'fetched_at': dt}})
    except Exception: pass

# Create TTL index (30 days)
db['model_benchmark'].create_index('fetched_at', expireAfterSeconds=2592000, name='bm_fetched_ttl')
```

### 4. Smoke test hardcoded model assumption

Symptom: `MiniMax-M3_intel: False` even though system is healthy.

Root cause: smoke test hardcoded `model_id = "MiniMax-M3"` but that provider was removed. Also had `0 <= (score or -1) <= 100` bug — `0.0 or -1` returns `-1` because `0.0` is falsy.

Fix in `sot/sot_runtime_audit.py` smoke test section:
```python
# Replace hardcoded MiniMax-M3 lookup with dynamic active model
active_model = db["models"].find_one({"status": "active", "is_active": True})
if active_model:
    m3 = db["model_intelligence"].find_one({"model_id": active_model["model_id"]})
    results["active_model_intel"] = m3 is not None
    if m3:
        score = m3.get("composite_score")
        results["active_model_score"] = score
        # Explicit None check (0.0 is valid score, not falsy fallback)
        results["active_model_in_range"] = score is not None and 0 <= score <= 100
```

### Verification sequence

```bash
cd /root/.hermes/profiles/ilma
python3 sot/sot_runtime_audit.py --audit   # expect 0 defects
python3 sot/sot_runtime_audit.py --smoke   # expect SMOKE TEST PASS
python3 sot/sot_runtime_audit.py --loop 100 # expect 100/100 clean
```

### Git push gotcha

`state.db.compact` (251MB) exceeds GitHub's 100MB limit. Add to `.gitignore` before pushing:
```bash
git rm --cached state.db.compact
echo "state.db.compact" >> .gitignore
git add .gitignore && git commit --amend --no-edit
git push origin master  # branch is 'master', not 'main'
```

Evidence: `ILMA-EVID-RUNTIME-AUDIT-20260702-031622` — 192 defects → 0, smoke PASS, 100/100 loop clean.

**Session detail**: See `references/sot-runtime-audit-cleanup-2026-07-02.md` for the full transcript, defect table, and evidence IDs from this cleanup session.