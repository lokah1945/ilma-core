---
name: hermes-agent-recovery
description: Recover and restart Hermes agents when they're down or not running properly after OpenClaw updates. Only ILMA + MASTER-CHIEF should run.
---

# Hermes Agent Recovery

## CRITICAL: Only 2 Agents Should Run

**HARUS HANYA 2 AGENT:**
- `ilma` (PID biasanya 692)
- `master-chief` (PID biasanya 693)

**14 AGENT LAIN DIHENTIKAN:** aura, delia, elia, fina, gina, hyra, indra, meli, myra, naila, nara, theo, vera, zara

## When to Use

When Hermes agents show as STOPPED in watchdog/status scripts, or when ILMA reports agent_down status after an OpenClaw update.

## Diagnosis Steps

```bash
# 1. Check actual process status
ps aux | grep "hermes_cli.main" | grep -v grep

# 2. Count running agents - HARUS 2, BUKAN 16
ps aux | grep "hermes_cli.main" | grep -v grep | wc -l
# Expected: 2 (ilma + master-chief ONLY)

# 3. Check OpenClaw Gateway
ps aux | grep "openclaw" | grep -v grep
```

## Recovery Procedure

### Problem: More than 2 agents running (user wants only ILMA + MASTER-CHIEF)

**Kill excess agents:**
```bash
# Find PIDs of all hermes agents
ps aux | grep "hermes_cli.main" | grep -v grep | awk '{print $2}'

# Kill specific agent (example: vera)
kill <PID>
```

### Problem: ILMA or MASTER-CHIEF is DOWN

**Recovery Command:**
```bash
# Use FULL venv path - critical!
/root/.hermes/hermes-agent/venv/bin/python -m hermes_cli.main --profile {AGENT_NAME} gateway run --replace
```

**Agent Profiles (ONLY use these 2):**
```
ilma, master-chief
```

### Problem: ILMA orchestrator fails with `AttributeError: 'str' object has no attribute 'priority'`

**Root Cause:** String entries (`browser_url`, `browser_search`) misplaced in TASK_TYPES dict instead of proper TaskType objects.

**Fix in `/root/.openclaw/workspace/scripts/ILMA_intelligent_orchestrator.py`:**
```python
# Find and remove these MISPLACED string entries from TASK_TYPES:
# - "browser_url" 
# - "browser_search"
# They should NOT be in TASK_TYPES - remove them
```

**Verification:**
```bash
cd /root/.openclaw/workspace
python3 scripts/ILMA_intelligent_orchestrator.py status
# Should show: 21 task types, 231 intent patterns (NO errors)
```

### Problem: Credential path corruption in ILMA_credentials.py

**Symptom:** CREDENTIAL_FILE path shows truncated string like `"...on"`

**Fix:** Update path in `ILMA_credentials.py`:
```python
CREDENTIAL_FILE = "/root/credential/api_key.json"
```

**Verification:**
```bash
ls -la /root/credential/api_key.json
# Should exist and be readable
```

## ILMA Full Verification Checklist

After any recovery, run these in order:

```bash
cd /root/.openclaw/workspace

# 1. API smoke test
python3 scripts/ILMA_api_smoke_test.py

# 2. Orchestrator status
python3 scripts/ILMA_intelligent_orchestrator.py status

# 3. Heartbeat
python3 scripts/ILMA_heartbeat.py

# 4. Skill health
python3 scripts/ILMA_skill_health.py

# 5. Unit tests
python3 -m unittest discover -s tests

# 6. Release gate
python3 scripts/ILMA_release_gate.py

# 7. Workflow ECC
python3 scripts/ILMA_workflow_ecc_integration.py --status

# 8. Verify agents (MUST be 2)
ps aux | grep "hermes_cli.main" | grep -v grep | wc -l
# Expected: 2
```

## Update ILMA State After Recovery

```bash
cd /root/.openclaw/workspace
python3 -c "
import json
with open('ILMA_RUNTIME_STATE.json') as f:
    state = json.load(f)
state['swarm_system']['agents_total'] = 2
state['swarm_system']['agents_active'] = 2
state['swarm_system']['agent_down'] = None
with open('ILMA_RUNTIME_STATE.json', 'w') as f:
    json.dump(state, f, indent=2)
"
```

## Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| `ModuleNotFoundError: hermes_cli` | Using `python3` instead of venv python | Use `/root/.hermes/hermes-agent/venv/bin/python` |
| Orchestrator `AttributeError: 'str'` | String entries in TASK_TYPES | Remove misplaced `browser_url`/`browser_search` strings |
| Credential file not found | Path corruption | Set `CREDENTIAL_FILE = "/root/credential/api_key.json"` |
| 16 agents running | Legacy config | Kill excess agents, keep only ilma + master-chief |
| Status shows STOPPED but process running | Watchdog checks systemd, not processes | Use `ps aux` to verify actual state |

## Systemd Service Crash-Loop Recovery (exit 209 / missing log dirs)

### Symptom
ILMA user-level systemd services show `activating (auto-restart)` with `Result: exit-code` and exit status **209**. The service binary/script exists and Python deps are fine, but the service keeps crashing.

### Root Cause
When a `.service` unit has `StandardOutput=append:/path/to/logfile.log` or `StandardError=append:`, but the **parent directory of the log file does not exist**, systemd fails to open the file for output redirection and exits with code 209. This creates a crash-loop because `Restart=always` keeps retrying the same impossible path.

### Affected Services (as of 2026-06-23)
| Service | Binary | Log Dir | Port |
|---------|--------|---------|------|
| `ilma-command-center.service` | `ilma_command_center.py` | `run/` | 18790 |
| `ilma-dashboard-backend.service` | `uvicorn app.main:app` | `run/` | 8000 |
| `ilma-dashboard-frontend.service` | `vite --port 3001` | `run/` | 3001 |

All three write to `$BASE_DIR/run/` (`/root/.hermes/profiles/ilma/run/`).

### Fix
```bash
# 1. Create the missing log directory
mkdir -p /root/.hermes/profiles/ilma/run

# 2. Restart all affected services
systemctl --user restart ilma-command-center.service
systemctl --user restart ilma-dashboard-backend.service
systemctl --user restart ilma-dashboard-frontend.service

# 3. Wait and verify they stay active (not crash-looping)
sleep 5
systemctl --user is-active ilma-command-center.service
systemctl --user is-active ilma-dashboard-backend.service
systemctl --user is-active ilma-dashboard-frontend.service
# All should return "active"

# 4. Health check endpoints
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:18790/  # 303 (login redirect)
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/  # 200
curl -s -o /dev/null -w "%{http_code}" http://localhost:3001/   # 200 (note: localhost, not 127.0.0.1 for Vite)
```

### Pitfall: Vite Binds to localhost Only
The Vite dev server (frontend) binds to `localhost` by default, not `0.0.0.0`. Health checks using `127.0.0.1:3001` will return connection refused (exit code 7 / HTTP 000). Use `http://localhost:3001/` instead.

### Diagnostic Pattern for Any systemd Crash-Loop
```bash
# 1. Check service status + exit code
systemctl --user status <service>.service
# Look for: Process exit code, Result line

# 2. Check if log directory exists
ls -la /path/to/log/parent/dir/

# 3. Check if binary/script actually exists
ls -la <ExecStart binary path>

# 4. Check Python/Node dependencies
python3 -c "import <module>"  # for Python services

# 5. If exit 209 → 99% chance it's a missing log/output directory
mkdir -p /path/to/log/dir && systemctl --user restart <service>
```

### Prevention
The `run/` directory under the ILMA profile should be created during setup or via `tmpfiles.d` rule. If the directory gets cleaned (e.g. reboot clearing `/run`), the services will crash-loop again. Consider adding `ExecStartPre=mkdir -p /root/.hermes/profiles/ilma/run` to the service unit files, or adding a `RuntimeDirectory=run` directive.
