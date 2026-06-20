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