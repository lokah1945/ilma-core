---
name: wrapper-restart
description: Restart wrapper services using systemd or manual fallback for containerized environments
---

# Wrapper Service Restart

## Trigger
- `git pull` on wrapper repo
- Service health check fails
- Container environment (no systemd user bus)
- `Failed to connect to bus` from systemctl

## Environment Check

First verify the deployment environment:

```bash
# Check systemd availability
systemctl --user status 2>&1 | head -3

# Check for running wrapper processes
ps aux | grep uvicorn | grep -v grep

# Check port bindings
ss -tlnp | grep 910
```

## Restart Patterns

### Pattern 1: Systemd User (Standard)
```bash
# Restart all wrappers via systemd
systemctl --user restart wrapper-nvidia-python \
  wrapper-nous \
  wrapper-opencode \
  wrapper-blackbox \
  wrapper-openrouter

# Verify all healthy
for port in 9101 9102 9103 9104 9106; do
  curl -s http://127.0.0.1:$port/health | python3 -c "import sys,json;d=json.load(sys.stdin);print(f'Port $port: {d.get(\"status\")}')" 
done
```

### Pattern 2: Manual Process (Container/Fallback)
When systemd user bus unavailable:

```bash
# Kill existing processes
for pid in $(pgrep -f "uvicorn.*910"); do kill $pid 2>/dev/null; done

# Start all wrappers in background
cd /root/wrapper/nvidia-python && python3 -m uvicorn src.main:app --host 127.0.0.1 --port 9101 &
cd /root/wrapper/nous && python3 -m uvicorn src.main:app --host 127.0.0.1 --port 9102 &
cd /root/wrapper/opencode && python3 -m uvicorn src.main:app --host 127.0.0.1 --port 9103 &
cd /root/wrapper/blackbox && python3 -m uvicorn src.main:app --host 127.0.0.1 --port 9104 &
cd /root/wrapper/openrouter && python3 -m uvicorn src.main:app --host 127.0.0.1 --port 9106 &

# Wait and verify
sleep 2
curl -s http://127.0.0.1:9101/health && echo " ✓"
curl -s http://127.0.0.1:9102/health && echo " ✓"
curl -s http://127.0.0.1:9103/health && echo " ✓"
curl -s http://127.0.0.1:9104/health && echo " ✓"
curl -s http://127.0.0.1:9106/health && echo " ✓"
```

### Pattern 3: Supervisor Script
For persistent container deployments:

```python
# /root/wrapper/start_all.py
import subprocess, sys, os, signal

WRAPPERS = [
    ("nvidia-python", 9101), ("nous", 9102), ("opencode", 9103),
    ("blackbox", 9104), ("openrouter", 9106)
]

processes = []
for name, port in WRAPPERS:
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "src.main:app", 
         "--host", "127.0.0.1", "--port", str(port)],
        cwd=f"/root/wrapper/{name}",
        stdout=open(f"/tmp/{name}.log", "a"),
        stderr=subprocess.STDOUT
    )
    processes.append(proc)
    print(f"Started {name} on port {port} (PID: {proc.pid})")
```

## Post-Restart Verification

```bash
# Health check all services
curl -s http://127.0.0.1:9101/health | grep -o '"status":"[^"]*"'
curl -s http://127.0.0.1:9102/health | grep -o '"status":"[^"]*"'
curl -s http://127.0.0.1:9103/health | grep -o '"status":"[^"]*"'
curl -s http://127.0.0.1:9104/health | grep -o '"status":"[^"]*"'
curl -s http://127.0.0.1:9106/health | grep -o '"status":"[^"]*"'

# Verify git commits match HEAD
HEAD=$(git -C /root/wrapper rev-parse HEAD)
echo "Expected HEAD: $HEAD"
for svc in nvidia-python nous opencode blackbox openrouter; do
    RC=$(cat /root/wrapper/runtime/$svc.commit 2>/dev/null || echo "MISSING")
    echo "$svc: runtime=$RC"
done
```

## Pitfalls

- **Do NOT trust `systemctl --user` in containers** — bus often unavailable
- **Health check must come after 2s delay** — services need time to start
- **Always verify git_commit** — ensures restart loaded the new code
- **Don't forget openrouter on port 9106** — common mistake is assuming 9105
- **PID file tracking helps** — record PIDs for later termination