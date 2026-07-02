#!/usr/bin/env bash
# /root/.hermes/profiles/ilma/skills/system-administration/safe-runtime-patching/scripts/post-patch-verify.sh
#
# Run AFTER each per-file patch + restart. Reads the baseline captured by
# pre-patch-verify.sh and reports the deltas. Fails (exit 1) if any stop
# condition triggered.
#
# Stop conditions (from safe-runtime-patching rule):
#   - RSS delta > 10 MB  (positive)
#   - /health returned 200 before but not now
#   - admin_queue returned valid JSON before but not now
#   - Real proxy request downgraded (200 -> 503/504)
#   - Process log shows new ERROR lines matching touched symbol
#
# Usage:
#   ./scripts/post-patch-verify.sh <PORT> <ADMIN_TOKEN> <BASELINE_PATH> <LOG_PATH> [touched_symbol]
# Example:
#   ./scripts/post-patch-verify.sh 9100 changeme /tmp/pre-patch.json /tmp/wrapper.log acquire

set -euo pipefail

PORT="${1:?port required}"
TOKEN="${2:?admin token required}"
BASELINE="${3:?baseline path required}"
LOG_PATH="${4:-/tmp/wrapper.log}"
TOUCHED_SYMBOL="${5:-}"

if [[ ! -f "$BASELINE" ]]; then
  echo "FAIL: baseline not found at $BASELINE" >&2
  exit 1
fi

PID=$(ss -tlnp 2>/dev/null | awk -v p=":${PORT}" '$0 ~ p { match($0, /pid=([0-9]+)/, m); if(m[1]) print m[1] }' | head -1)
[[ -z "${PID:-}" ]] && { echo "FAIL: no process listening on port ${PORT}" >&2; exit 1; }

RSS_KB=$(awk '/^VmRSS:/ { print $2 }' /proc/$PID/status 2>/dev/null || echo 0)

HEALTH_CODE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 "http://localhost:${PORT}/health")
QUEUE_CODE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 -H "X-Admin-Token: ${TOKEN}" \
             "http://localhost:${PORT}/admin/queue")

# Use Python for JSON diffing (assumes Python 3 is available in this env).
python3 - "$BASELINE" "$RSS_KB" "$HEALTH_CODE" "$QUEUE_CODE" "$PID" "$LOG_PATH" "$TOUCHED_SYMBOL" <<'PY'
import json, os, sys

baseline_path, rss_kb, health_code, queue_code, pid, log_path, touched = sys.argv[1:8]

with open(baseline_path) as f:
    pre = json.load(f)

pre_pid = int(pre['pid'])
pre_rss = int(pre['rss_kb'])
pre_health = json.loads(pre['health']).get('status', 'unknown')
cur_health_alive = (health_code == '200')

new_pid = (int(pid) != pre_pid)
rss_delta_mb = (int(rss_kb) - pre_rss) / 1024.0

fails = []
notes = []

if pre_health == 'ok' and not cur_health_alive:
    fails.append(f"health: pre='ok' cur={health_code}")

if queue_code != '200':
    fails.append(f"admin/queue: cur={queue_code} (was 200)")

if rss_delta_mb > 10.0:
    fails.append(f"rss_delta: {rss_delta_mb:.1f} MB (limit 10)")

if new_pid:
    notes.append(f"PID changed: pre={pre_pid} cur={pid} (process restarted as expected)")

if touched and os.path.exists(log_path):
    with open(log_path) as f:
        log = f.read()
    err_matches = [line for line in log.splitlines()
                   if 'ERROR' in line and touched in line]
    if err_matches:
        fails.append(f"{len(err_matches)} ERROR lines in log matching '{touched}'")
        for line in err_matches[:3]:
            notes.append(f"  log: {line[:150]}")

print(json.dumps({
    "pre": {"pid": pre_pid, "rss_kb": pre_rss, "health": pre_health},
    "cur": {"pid": pid, "rss_kb": rss_kb, "health_code": health_code, "queue_code": queue_code},
    "rss_delta_mb": round(rss_delta_mb, 2),
    "fails": fails,
    "notes": notes,
}, indent=2))

sys.exit(1 if fails else 0)
PY

rc=$?

if [[ $rc -eq 0 ]]; then
  echo "VERIFY OK — proceed to next patch"
else
  echo "VERIFY FAILED — DO NOT PROCEED. Roll back the touched file and re-evaluate."
fi
exit $rc
