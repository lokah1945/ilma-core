#!/usr/bin/env bash
# teardown-systemd-service.sh — safe decommission of a systemd --user service.
# Defeats Restart=always, unregisters the unit, frees the port, removes files.
# Usage: bash scripts/teardown-systemd-service.sh <service.unit> <port> [extra-files-or-dirs...]
set -u
SVC="${1:?service unit name required (e.g. ilma-dashboard-backend.service)}"
PORT="${2:?port number the service listens on (e.g. 8000)}"
shift 2
EXTRA=("$@")

echo "=== 1. disable (kill boot auto-start) ==="
systemctl --user disable "$SVC" 2>&1 || true

echo "=== 2. stop ==="
systemctl --user stop "$SVC" 2>&1 || true

echo "=== 3. kill lingering procs on port $PORT ==="
for p in $(ss -tlnp 2>/dev/null | grep ":$PORT" | grep -oP 'pid=\K[0-9]+' | sort -u); do
  echo "kill -9 $p"; kill -9 "$p" 2>/dev/null && echo "  killed" || echo "  gone"
done

echo "=== 4. remove unit files ==="
rm -f ~/.config/systemd/user/"$SVC" /etc/systemd/system/"$SVC" 2>&1
echo "  removed unit"

echo "=== 5. daemon-reload ==="
systemctl --user daemon-reload 2>&1

echo "=== 6. remove extra paths ==="
for x in "${EXTRA[@]:-}"; do
  [ -n "$x" ] && rm -rf "$x" && echo "  removed: $x"
done

echo "=== 7. VERIFY ==="
if ss -tlnp 2>/dev/null | grep -q ":$PORT"; then
  echo "  ❌ PORT $PORT STILL BOUND"; ss -tlnp 2>/dev/null | grep ":$PORT"
else
  echo "  ✅ PORT $PORT FREE"
fi
if systemctl --user list-units --all 2>/dev/null | grep -qi "${SVC%%.service}"; then
  echo "  ❌ UNIT STILL PRESENT"
else
  echo "  ✅ UNIT GONE"
fi
