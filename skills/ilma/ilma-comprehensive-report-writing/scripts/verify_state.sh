#!/bin/bash
# verify_state.sh — ILMA system state verification for comprehensive reports
# Run BEFORE writing any comprehensive report. Captures ground truth via tool.
# Output: structured facts to use in report sections 01, 04, 06.

set -e

echo "=== ILMA SYSTEM STATE VERIFICATION ==="
echo "Tanggal: $(date '+%Y-%m-%d %H:%M:%S WIB')"
echo ""

echo "## 1. CONFIG (line counts only — values go in report)"
wc -l /root/.hermes/profiles/ilma/config.yaml 2>/dev/null || echo "config not found"

echo ""
echo "## 2. PROFILE ROOT"
ls -la /root/.hermes/profiles/ilma/ 2>/dev/null | head -20 || echo "profile not found"

echo ""
echo "## 3. SCRIPTS COUNT"
ls /root/.hermes/profiles/ilma/scripts/ 2>/dev/null | wc -l

echo ""
echo "## 4. SOT DIRS"
ls -la /root/.hermes/profiles/ilma/sot/ 2>/dev/null

echo ""
echo "## 5. RUNNING PROCESSES"
ps aux | grep -E "(hermes|ilma|chrome|pyright|tsserver|main\.py)" | grep -v grep || echo "no relevant processes"

echo ""
echo "## 6. CHROME / CDP"
echo "systemd state:"
systemctl --user is-active ilma-chrome.service 2>&1 || echo "service not found"
echo "CDP probe:"
curl -s -m 3 http://127.0.0.1:9222/json/version 2>&1 | head -5 || echo "CDP not reachable"

echo ""
echo "## 7. LEGACY PROXY :8001 (removed)"
curl -s -m 3 -o /dev/null -w "HTTP %{http_code}\n" http://127.0.0.1:8001/v1/models 2>&1 || echo "proxy removed (expected)"

echo ""
echo "## 8. OAUTH :1456"
curl -s -m 3 -o /dev/null -w "HTTP %{http_code}\n" http://127.0.0.1:1456/ 2>&1

echo ""
echo "## 9. MODEL ROUTER DATA FILES"
ls -la /root/.hermes/profiles/ilma/ilma_model_router_data/ 2>/dev/null | head -20

echo ""
echo "## 10. SOT AUDIT DOCS"
ls -la /root/.hermes/profiles/ilma/sot/*.md 2>/dev/null

echo ""
echo "## 11. CHANNELS"
cat /root/.hermes/profiles/ilma/channel_directory.json 2>/dev/null | head -30 || echo "channel_directory not found"

echo ""
echo "## 12. AUTH STATE"
ls -la /root/.hermes/profiles/ilma/auth.json 2>/dev/null
ls -la /root/.hermes/profiles/ilma/autonomous_loop_state.json 2>/dev/null

echo ""
echo "=== END VERIFICATION ==="
echo "Next: copy relevant facts into report sections 01, 04, 06, 10"
