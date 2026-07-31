---
name: ilma-wrapper-port-verification
description: >
  Verify current port mappings for all wrapper services. Ports can change
  between deployments or after configuration changes. Use this skill when
  wrappers are not responding as expected or after any restart/pull cycle.
tags:
  - verification
  - port-mapping
  - wrappers
category: devops
---

# Wrapper Port Verification

## When to Use
- Wrappers not responding on expected ports
- After `git pull` and restart
- Skeptical of documented port mappings
- Troubleshooting "connection refused" errors

## Discovery Commands

```bash
# List all listening wrapper ports
ss -tlnp | grep 910

# Check systemd wrapper units
systemctl --user list-units --type=service | grep wrapper

# Health check all standard wrapper ports
for port in 9101 9102 9103 9104 9106 9200; do
  echo -n "Port $port: "
  curl -s -m5 http://127.0.0.1:$port/health 2>/dev/null | jq -r '.status // .ok // "offline"' 2>/dev/null || echo "offline"
done
```

## Current Port Mapping (2026-08-01 verified)

| Service | Port | Health Endpoint |
|---------|------|-----------------|
| nvidia-python | 9101 | `/health` → `status: ok` |
| nous | 9102 | `/health` → `status: ok` |
| opencode | 9103 | `/health` → `status: ok` |
| blackbox | 9104 | `/health` → `status: ok` |
| openrouter | 9106 | `/health` → `status: ok` |
| model-registry | 9200 | `/health` → `status: ok` |

**CRITICAL:** OpenRouter is on port **9106** (not 9105/9107 as sometimes seen in legacy docs).

## Common Pitfalls

- **Wrong port assumption:** OpenRouter uses non-standard port 9106
- **systemd vs direct:** Services may be running but on wrong port due to config
- **Port conflict:** Another process may have claimed the expected port
- **Service name mismatch:** `nvidia-python` is the dir, `nvidia` is the systemd unit name

## Post-Verification Actions

If port mismatch found:
1. Check `.env` configuration files in each wrapper directory
2. Verify systemd unit files for correct `LISTEN_PORT` setting
3. Update `ilma-wrapper-production-audit` skill if port mapping changed permanently