---
name: ilma-genesis-daemon
description: "ILMA v5.0 Genesis Loop Daemon — Zero-Touch Background Operation. Runs as eternal background daemon, wakes at 00:00, triggers Abstract Goal Translator, delegates micro-tasks to Sub-Agents, sleeps safely without Bos intervention. SSS Tier."
triggers:
  - genesis-daemon
  - background-daemon
  - zero-touch
  - autonomous-loop
  - cron-scheduler
version: 5.0.0
tier: SSS-OMEGA
last_updated: 2026-05-07
---

# ILMA v5.0 — GENESIS LOOP DAEMON

## Overview

**Tier:** SSS-OMEGA  
**Version:** 5.0.0  
**Status:** OPERATIONAL

## Lifecycle

```
DORMANT → AWAKENING → EXECUTING → RESTING → (repeat forever)
```

### States

| State | Description |
|-------|-------------|
| DORMANT | Initial state, waiting for first trigger |
| AWAKENING | Waking up at 00:00 |
| EXECUTING | Running daily cycle |
| RESTING | Sleeping until next wake |
| PAUSING | Graceful pause requested |
| PAUSED | Paused state |
| TERMINATING | Shutdown requested |

## Daily Cycle

1. Wake at 00:00 (configurable)
2. Load active goals from memory
3. Generate micro-tasks via Abstract Goal Translator
4. Delegate to 50 parallel workers
5. Execute until complete (max 12 hours)
6. Generate cycle report
7. Sleep until next 00:00

## Worker Pool

- Max 50 concurrent workers
- Priority-based task queue
- Domain-specific handlers (content, SEO, security, etc.)
- Graceful shutdown with 10s grace period

## Persistence

- PID file: `/root/.hermes/profiles/ilma/run/genesis_daemon.pid`
- State file: `/root/.hermes/profiles/ilma/memory/genesis_daemon_state.json`
- Active goals: `/root/.hermes/profiles/ilma/memory/active_goals.json`

## Files

- /root/.hermes/profiles/ilma/scripts/ilma_genesis_daemon.py (980 lines)

---

**ILMA v5.0 — ETERNAL AUTONOMOUS EXECUTION**