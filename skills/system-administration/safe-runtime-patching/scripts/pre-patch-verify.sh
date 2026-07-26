#!/usr/bin/env bash
# /root/.hermes/profiles/ilma/skills/system-administration/safe-runtime-patching/scripts/pre-patch-verify.sh
#
# Phase-3 lesson distillation (2026-07-01 wrapper-nvidia):
#   NEVER ship a multi-file patch without first establishing a runtime baseline.
#   This script records the BEFORE state — RSS, uptime, /health response,
#   observability snapshot — so the next script (post-patch-verify.sh) can
#   detect regressions without needing session memory.
#
# Usage:
#   ./scripts/pre-patch-verify.sh <PORT> <ADMIN_TOKEN> <OUTPUT_PATH>
# Example:
#   ./scripts/pre-patch-verify.sh 9100 changeme /tmp/pre-patch.json

set -euo pipefail

PORT="${1:?port required}"
TOKEN="${2:?admin token required}"
OUT="${3:?output path required}"

# 1. Process state — find the node daemon by listening port
PID=$(ss -tlnp 2>/dev/null | awk -v p=":${PORT}" '$0 ~ p { match($0, /pid=([0-9]+)/, m); if(m[1]) print m[1] }' | head -1)
[[ -z "${PID:-}" ]] && { echo "FAIL: no process listening on port ${PORT}" >&2; exit 1; }

# 2. RSS and uptime from /proc
RSS_KB=$(awk '/^VmRSS:/ { print $2 }' /proc/$PID/status 2>/dev/null || echo 0)
START_TICKS=$(awk '/^starttime:/ { print $2 }' /proc/$PID/stat 2>/dev/null || echo 0)
UPTIME_S=$(awk -v ticks="$START_TICKS" 'BEGIN { printf "%d", systime() - ticks / 100 }')

# 3. /health response
HEALTH=$(curl -fs --max-time 3 "http://localhost:${PORT}/health")

# 4. /admin/queue response (or best-effort admin snapshot)
QUEUE=$(curl -fs --max-time 3 -H "X-Admin-Token: ${TOKEN}" \
        "http://localhost:${PORT}/admin/queue" 2>/dev/null || echo '{}')

# 5. JSON output as a single baseline record
cat > "$OUT" <<EOF
{
  "captured_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "port": "${PORT}",
  "pid": "${PID}",
  "rss_kb": ${RSS_KB},
  "uptime_s": ${UPTIME_S},
  "health": ${HEALTH},
  "admin_queue": ${QUEUE}
}
EOF

echo "BASELINE OK — recorded to $OUT"
echo "  PID=${PID}  RSS=${RSS_KB}KB  uptime=${UPTIME_S}s"
