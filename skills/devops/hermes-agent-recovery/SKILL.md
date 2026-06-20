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
