---
name: hermes-multi-agent-shutdown
description: Shutdown/stop Hermes agents on OpenClaw ILMA system that has dual-layer systemd (root + --user) and watchdog services. Use when you need to stop specific Hermes profiles or reduce resource usage.
version: 1.0.0
author: ILMA
tags: [hermes, systemd, openclaw, ILMA, agent-management]
---

# Hermes Multi-Agent Shutdown

## Problem

Killing Hermes processes directly (`kill -9 PID`) doesn't work - systemd keeps restarting them. The OpenClaw ILMA system has multiple restart mechanisms that must be disabled in the right order.

## Architecture Discovery

### Dual-Layer Systemd
- **Root services**: `/etc/systemd/system/hermes-*.service` - standard systemd services
- **User services**: `systemctl --user` - separate systemd user instance

### Watchdog Services
- `ILMA-gateway-watchdog.service` (root) - Python watchdog that auto-spawns agents
- `gateway-watchdog.py` (child of above) - the actual Python script

### Profiles on this system
```
ilma, master-chief  → KEEP RUNNING
delia, elia, fina, gina, hyra, myra, naila, nara, vera, zara, aura, indra, meli, theo → SHUTDOWN
```

## Shutdown Procedure

### Step 1: Kill Running Processes (except ILMA + master-chief)
```bash
# Kill all hermes processes EXCEPT ilma (PID) and master-chief (PID)
pkill -9 -f "hermes.*profile (delia|elia|fina|gina|hyra|myra|naila|nara|vera|zara|aura|indra|meli|theo)"
```

### Step 2: Stop Root Systemd Services
```bash
for svc in hermes-delia hermes-elia hermes-fina hermes-gina hermes-hyra hermes-myra hermes-naila hermes-nara hermes-vera hermes-zara hermes-aura hermes-indra hermes-meli hermes-theo; do
    systemctl stop "$svc" 2>/dev/null
    systemctl disable "$svc" 2>/dev/null
done
```

### Step 3: Stop --user Systemd Services
```bash
for svc in hermes-gateway-delia hermes-gateway-elia hermes-gateway-fina hermes-gateway-gina hermes-gateway-hyra hermes-gateway-myra hermes-gateway-naila hermes-gateway-nara hermes-gateway-vera hermes-gateway-zara; do
    systemctl --user stop "$svc" 2>/dev/null
    systemctl --user disable "$svc" 2>/dev/null
done
```

### Step 4: Stop Watchdog Services
```bash
# Stop ILMA-gateway-watchdog (root level - this is what keeps respawning agents)
systemctl stop ILMA-gateway-watchdog
systemctl disable ILMA-gateway-watchdog

# Kill any remaining watchdog Python processes
pkill -9 -f "gateway-watchdog\|hermes-watchdog"
```

### Step 5: Remove Cron Entries
```bash
# Remove hermes-watchdog cron
crontab -l 2>/dev/null | grep -v "hermes-watchdog" | crontab -
```

### Step 6: Verify
```bash
# Check running processes - should only show ilma and master-chief
ps aux | grep "hermes.*profile" | grep -v grep

# Check systemd services
systemctl list-units --all --type=service | grep hermes
systemctl --user list-units --all 2>/dev/null | grep hermes
```

## Key Pitfalls

1. **Killing processes isn't enough** - systemd will restart them immediately
2. **Only disabling isn't enough** - must also stop, then verify processes are dead
3. **Two systemd layers** - root and --user services are SEPARATE and BOTH must be managed
4. **Watchdog service auto-restarts** - stop the `ILMA-gateway-watchdog.service` first
5. **Process respawns from different paths** - `.local/bin/hermes` can also spawn agents

## Quick Status Check
```bash
echo "=== RUNNING PROCESSES ===" && ps aux | grep "hermes.*profile" | grep -v grep
echo "=== ROOT SERVICES ===" && systemctl list-units --all --type=service | grep hermes
echo "=== USER SERVICES ===" && systemctl --user list-units --all 2>/dev/null | grep hermes
```
