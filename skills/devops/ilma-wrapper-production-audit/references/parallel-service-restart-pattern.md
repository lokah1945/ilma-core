# Parallel Service Restart Pattern (2026-08-01)

## Problem
Restarting multiple wrapper services sequentially causes cumulative timeout delays. Each `systemctl --user restart` + health check takes ~2-5 seconds, totaling 10-30 seconds for 5 services.

## Solution: Background Process Launch + Batch Health Check

### Direct Process Start (Works when systemd units fail or timeout)
```bash
# Stop all existing processes
pkill -f "uvicorn" 2>/dev/null; pkill -f "main.py" 2>/dev/null; pkill -f "model-registry" 2>/dev/null; sleep 2

# Start services in background
cd /root/wrapper/nvidia-python && uvicorn src.main:app --host 127.0.0.1 --port 9101 &
cd /root/wrapper/nous && python -c "import sys; sys.path.insert(0, '.'); from nous.main import app; import uvicorn; uvicorn.run(app, host='127.0.0.1', port=9102, log_level='info')" &
cd /root/wrapper/opencode && python -c "..." &
cd /root/wrapper/blackbox && python -c "..." &
cd /root/wrapper && python model-registry/service.py &

# Batch health check
for port in 9101 9102 9103 9104 9106 9200; do
  echo -n "Port $port: "; curl -s http://127.0.0.1:$port/health 2>/dev/null | jq -r '.status // .ok // "offline"' 2>/dev/null || echo "offline"
done
```

### Health Check Pattern
```bash
curl -s http://127.0.0.1:PORT/health | jq -r '.status // .ok // "offline"'
```

## Evidence
- Session 2026-08-01 verified all 6 services respond with `ok` within 3 seconds of start
- NVIDIA wrapper (9101) version: `8.6.5-py` at commit `26c98409cb13ee016178ac2fda8d7ae2523f10a2`
- NOUS wrapper (9102) version: `2.0.7-audit-hardening`
- Model-registry (9200) version: `1.0.0-contract`

## Pitfall to Avoid
**DO NOT use `systemctl --user restart` in a loop with sleep** - the cumulative timeout causes the Hermes TUI watchdog timeout. Use parallel background launch instead.

## Related
- `references/smoke-and-load-targets.md` for health endpoint formats
- `references/catalog-route-ordering-fix.md` for post-restart verification