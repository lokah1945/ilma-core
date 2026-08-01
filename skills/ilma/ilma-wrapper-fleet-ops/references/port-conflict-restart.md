# Port Conflict During Wrapper Restart (2026-08-01)

## Incident
During force pull and restart of wrapper services, wrapper-nvidia-python.service failed to start with:
```
ERROR: [Errno 98] error while attempting to bind on address ('0.0.0.0', 9101): address already in use
```

## Root Cause
Port 9101 was still held by a stale uvicorn process from a previous session that didn't fully terminate. The `systemctl --user restart` command cannot bind to an already-used port.

## Diagnosis Steps
1. Check what's using the port:
   ```bash
   lsof -i :9101
   # OR
   ss -tlnp | grep 9101
   ```

2. Verify stale process:
   ```bash
   ps aux | grep uvicorn
   ```

## Resolution
1. Kill stale processes:
   ```bash
   kill -9 <PID_FROM_lsof>
   pkill -f "uvicorn.*9101"
   ```

2. Wait for port release:
   ```bash
   sleep 1  # Allow socket cleanup
   ```

3. Restart service:
   ```bash
   systemctl --user restart wrapper-nvidia-python.service
   ```

4. Verify status:
   ```bash
   systemctl --user is-active wrapper-nvidia-python.service
   systemctl --user status wrapper-nvidia-python.service --no-pager
   ```

## Prevention (add to workflow)
After a force pull or when restarting all wrappers:
1. **ALWAYS** run `lsof -i :9101-9106` before restart to check for stale processes
2. Kill any stale processes BEFORE attempting restart
3. Consider sequential restart of wrappers instead of batch restart (avoids systemd 60s timeout)

## Pattern Template
```bash
# Clean stale processes across all wrapper ports
for port in 9101 9102 9103 9104 9106 9200; do
    pids=$(lsof -t -i :$port 2>/dev/null)
    if [ -n "$pids" ]; then
        echo "Killing stale processes on port $port: $pids"
        kill -9 $pids 2>/dev/null
    fi
done
sleep 2
# Then restart services
```