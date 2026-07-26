---
name: hermes-agent-shutdown
description: How to cleanly shut down specific Hermes agent profiles — stops processes, disables systemd services, and neutralizes auto-restart watchdogs. Use when asked to disable, turn off, or kill specific Hermes agents.
version: 1.0.0
author: ILMA
tags: [hermes, shutdown, systemd, watchdog, multi-agent]
---

# Hermes Agent Shutdown

When asked to shut down specific Hermes agent profiles, you must address **three layers** of restart protection, otherwise agents respawn immediately.

## The Three Layers

| Layer | Mechanism | How to Neutralize |
|-------|-----------|-------------------|
| 1 | Python watchdog daemon | `kill -9 <pid>` (PID 626: `gateway-watchdog.py`) |
| 2 | Cron watchdog script | Remove from crontab |
| 3 | systemd `auto-restart` | `systemctl disable <service>` |

**Critical lesson:** A plain `kill` or `systemctl stop` alone does NOT work — the watchdog daemon and systemd restart policies will respawn them within seconds.

## Complete Shutdown Procedure

### Step 1: Find the watchdog daemon

```bash
ps aux | grep gateway-watchdog | grep -v grep
# Usually PID 626: /usr/bin/python3 /root/.openclaw/workspace/scripts/gateway-watchdog.py
```

### Step 2: Kill the watchdog daemon + any running hermes processes

```bash
# Kill watchdog daemon (PID 626)
kill -9 626

# Kill all hermes gateway processes except the ones you want to keep
# Example: keeping ilma (694) and master-chief (700)
pkill -9 -f "hermes.*profile (delia|elia|fina|gina|hyra|myra|naila|nara|vera|zara|aura|indra|meli|theo)"

# Or by PID list:
kill -9 <PID1> <PID2> ... <PIDn>
```

### Step 3: Disable the cron watchdog

The cron only runs the script every 5 minutes, but it's still active:
```bash
crontab -l | grep hermes-watchdog
# It's usually just a comment - no actual cron line for the script
# But the script itself can be invoked by other processes
```

### Step 4: Disable systemd services (CRITICAL)

```bash
# Stop AND disable each unwanted agent's systemd service
services="hermes-delia hermes-elia hermes-fina hermes-gina hermes-hyra hermes-myra hermes-naila hermes-nara hermes-vera hermes-zara hermes-aura hermes-indra hermes-meli hermes-theo"

for svc in $services; do
    systemctl stop "$svc"
    systemctl disable "$svc"
done
```

### Step 5: Verify

```bash
# Only your target agents should remain
ps aux | grep "hermes.*gateway run" | grep -v grep

# Check systemd services
systemctl list-units --all | grep "hermes-.*service"
# Only your target services should be active/enabled
```

## Common Agent Names to Disable

```
delia, elia, fina, gina, hyra, myra, naila, nara, vera, zara,
aura, indra, meli, theo
```

## Verify a Service is Properly Disabled

```bash
systemctl is-enabled <service>   # Should say "disabled"
systemctl is-active <service>    # Should say "inactive" or "failed"
```

## Notes

- The hermes-watchdog.sh script is called by a different mechanism (it's a 1-minute health check that restarts via systemctl)
- The actual watchdog that respawns quickly is `gateway-watchdog.py` running as PID 626
- After disabling services, some may show "failed" in `systemctl list-units` — this is OK if the process is no longer running
- To start them again: `systemctl enable <service> && systemctl start <service>`
