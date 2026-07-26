---
name: ilma-cron-no-agent
description: ILMA Cron No-Agent Mode — Hermes v0.13.0 Cron watchdog with no_agent mode. Pure background automation without agent overhead. Background tasks, monitoring, cron jobs that run without active agent. SSS Tier. Auto-trigger for background automation, scheduled tasks, monitoring, cron jobs.
trigger_conditions:
  - "cron"
  - "schedule"
  - "background task"
  - "automated"
  - "watchdog"
  - "periodic"
  - "recurring"
  - "scheduler"
  - "daemon"
category: autonomous
created: 2026-05-09
hermes_version: v0.13.0
source: hermes-agent cron --no-agent
---

# ILMA Cron No-Agent Mode — Pure Background Automation

## Overview

Hermes v0.13.0 cron gains `no_agent` watchdog mode. This allows pure background tasks **without** the agent overhead — just pure automation.

**Use case:** ILMA can now set up watchers, monitors, and background tasks that run silently without agent context.

## CLI Commands

```bash
# Create no-agent cron (pure background)
hermes cron create \
  --name "ilma-health-monitor" \
  --prompt "Monitor ILMA test suite health; if failures > 5, alert" \
  --schedule "*/15 * * * *" \
  --no-agent

# Create agent-mode cron (with full agent context)
hermes cron create \
  --name "ilma-daily-report" \
  --prompt "Generate daily ILMA status report" \
  --schedule "0 9 * * *"

# List all cron jobs
hermes cron list

# List no-agent cron jobs only
hermes cron list --no-agent

# Pause cron job
hermes cron pause <job_id>

# Resume cron job
hermes cron resume <job_id>

# Remove cron job
hermes cron remove <job_id>

# Run job immediately
hermes cron run <job_id>

# View job history
hermes cron history <job_id>

# View job logs
hermes cron logs <job_id>
```

## No-Agent vs Agent Mode

| Aspect | `--no-agent` | Default (Agent) |
|--------|-------------|-----------------|
| Agent context | None | Full Hermes agent |
| Resource usage | Minimal | Full model calls |
| Latency | Fast | Slow |
| Use case | Background watchers | Complex tasks needing LLM |
| Can use tools | No (pure script) | Yes (full toolset) |

## ILMA Use Cases

### 1. Health Monitor (No-Agent)

```bash
# Monitor test suite every 15 minutes
hermes cron create \
  --name "ilma-test-health" \
  --prompt "cd /root/.hermes/profiles/ilma/test_projects/phase10_250file_codebase && python3 -m pytest -q | tail -1" \
  --schedule "*/15 * * * *" \
  --no-agent \
  --notify-on-fail "telegram:-100XXXXX:CHAT_ID"
```

### 2. Disk Usage Monitor (No-Agent)

```bash
# Alert if disk > 90%
hermes cron create \
  --name "ilma-disk-monitor" \
  --prompt "df -h / | tail -1 | awk '{print \$5}' | sed 's/%//'" \
  --schedule "0 * * * *" \
  --no-agent \
  --alert-threshold 90
```

### 3. Git Sync Monitor (No-Agent)

```bash
# Auto-pull Hermes updates daily
hermes cron create \
  --name "hermes-git-sync" \
  --prompt "cd /root/.hermes/hermes-agent && git pull" \
  --schedule "0 3 * * *" \
  --no-agent
```

### 4. Evidence Ledger Backup (Agent Mode)

```bash
# Daily backup with full agent context
hermes cron create \
  --name "ilma-evidence-backup" \
  --prompt "Backup ILMA evidence ledger; compress old entries; report status" \
  --schedule "0 2 * * *"
  # Full agent context to handle compression, archival, reporting
```

## Cron Expression Guide

| Schedule | Expression | Use |
|----------|------------|-----|
| Every 15 min | `*/15 * * * *` | Health monitoring |
| Every hour | `0 * * * *` | Disk/network |
| Daily 2 AM | `0 2 * * *` | Backup tasks |
| Daily 9 AM | `0 9 * * *` | Reports |
| Weekly Sunday | `0 0 * * 0` | Deep clean |
| Monthly 1st | `0 0 1 * *` | Archival |

## ILMA Integration Pattern

```python
# ILMA cron management
def create_background_monitor(
    name: str,
    script: str,
    schedule: str,
    notify_on: str = None
):
    """Create no-agent cron for ILMA background monitoring"""
    
    cmd = [
        "hermes", "cron", "create",
        "--name", name,
        "--prompt", script,
        "--schedule", schedule,
        "--no-agent"
    ]
    
    if notify_on:
        cmd.extend(["--notify-on-fail", notify_on])
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout

# Example: Test suite health monitor
create_background_monitor(
    name="ilma-test-health",
    script="cd /root/.hermes/profiles/ilma/test_projects/phase10_250file_codebase && python3 -m pytest -q --tb=no 2>&1 | tail -1 | tee /tmp/ilma_test_health.log",
    schedule="*/15 * * * *",
    notify_on="telegram:-100XXXXX:CHAT_ID"
)
```

## Watchdog Pattern (No-Agent)

For critical background tasks:

```bash
# Create watchdog that auto-restarts if fails
hermes cron create \
  --name "ilma-watchdog" \
  --prompt "python3 /root/.hermes/profiles/ilma/scripts/watchdog.py" \
  --schedule "continuous" \
  --no-agent \
  --auto-restart \
  --max-restarts 5
```

## Delivery Options

```bash
# Deliver to origin (current chat)
hermes cron create \
  --name "ilma-status-report" \
  --prompt "Generate status report" \
  --schedule "0 9 * * *" \
  --deliver origin

# Deliver to local file only
hermes cron create \
  --name "ilma-evidence-backup" \
  --prompt "Backup and compress" \
  --schedule "0 2 * * *" \
  --deliver local

# Deliver to specific chat
hermes cron create \
  --name "ilma-alert" \
  --prompt "Critical alert" \
  --schedule "*/5 * * * *" \
  --deliver "telegram:-100XXXXX:ALERT_CHANNEL"
```

## Pitfalls

1. **Don't use no-agent for LLM tasks** — No-agent = no model. Use default for complex tasks.
2. **Script must be self-contained** — No-agent can't use tools. Script must do everything.
3. **Timeout issues** — Long scripts may timeout. Split into chunks.
4. **Notification spam** — Set reasonable thresholds. Don't alert on every ping.
5. **Resource contention** — Don't run too many no-agent jobs simultaneously.

## Related Skills

- `ilma-autonomous-loops` — Background task management
- `ilma-auto-recovery` — Error recovery for cron jobs
- `ilma-health-monitor` — ILMA health monitoring patterns
- `hermes-agent` — Hermes CLI reference

## Verification

```bash
# List all cron jobs
hermes cron list

# Check specific job
hermes cron status <job_id>

# View job history
hermes cron history <job_id>

# Test cron health
hermes doctor --component cron

# Run job immediately to test
hermes cron run <job_id>
```

## Status

✅ INTEGRATED (2026-05-09) — Hermes v0.13.0 Cron no_agent mode