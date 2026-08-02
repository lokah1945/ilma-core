# Parallel Service Restart Pattern (2026-08-02)

## Problem
Systemd user bus not available in containerized environments. Cannot use `systemctl --user` commands.

## Solution: Manual Process Management

### Technique 1: Sequential Background Launch
```bash
# Start services one by one in background
cd /root/wrapper/nvidia-python && python3 -m uvicorn src.main:app --host 127.0.0.1 --port 9101 &
cd /root/wrapper/nous && python3 -m uvicorn src.main:app --host 127.0.0.1 --port 9102 &
# ... etc
```

### Technique 2: Supervisor Script (Hermes-Compatible)
```bash
# Create supervisor script
python3 /root/wrapper/start_wrappers.py &
```

### Technique 3: Health Check After Restart
```bash
sleep 2
for port in 9101 9102 9103 9104 9106; do
  curl -s --max-time 5 http://127.0.0.1:$port/health | head -c 100
done
```

## Key Learnings (from this session)

1. **Environment check first**: Verify systemd is available before using it
2. **Fallback to manual**: Always have a manual restart plan for containers
3. **Health check mandatory**: Verify each service after restart
4. **PID tracking**: Record PIDs for later reference

## When to use this pattern
- Containerized environments without systemd user bus
- `Failed to connect to bus` errors from systemctl
- systemd services show as inactive despite running processes

## Related
- `hermes-agent-recovery` skill for other Hermes service recovery patterns