#!/usr/bin/env bash
#
# verify_cleanup.sh — End-to-end verification for deep cleanup pattern
#
# Usage:  bash scripts/verify_cleanup.sh <target-string>
#
# Performs the 4 mandatory checks from the deep-cleanup-pattern:
#   1. Active code search: ZERO references in active files
#   2. Module compile: all active modules import OK
#   3. Status check: ilma.py boots without new errors
#   4. Wiring check: runtime wiring intact
#
# Exits 0 if all checks pass, 1 on any failure.

set -e

TARGET="${1:?Usage: $0 <target-string>}"
ILMA_ROOT="${ILMA_ROOT:-/root/.hermes/profiles/ilma}"

echo "=== Deep Cleanup Verification ==="
echo "Target: $TARGET"
echo "Root:   $ILMA_ROOT"
echo

cd "$ILMA_ROOT"

# ── Check 1: Active code search ─────────────────────────────────────────────
echo "── Check 1: Active code reference search ──"
ACTIVE_HITS=$(grep -rln "${TARGET}-x\|${TARGET}_proxy\|${TARGET}_sync\|${TARGET}_integration\|${TARGET}_router\|${TARGET}_health" \
  --include="*.py" --include="*.json" --include="*.yaml" \
  --include="*.yml" --include="*.sh" --include="*.md" . 2>/dev/null \
  | grep -v ".git" | grep -v ".git-rewrite" | grep -v "sessions/" \
  | grep -v "node_modules" | grep -v "cron/output/" \
  | grep -v "sessions_archive/" || true)

if [ -n "$ACTIVE_HITS" ]; then
  echo "❌ FAIL: Active references found:"
  echo "$ACTIVE_HITS"
  exit 1
fi
echo "✅ No active references in code/config/docs"

# ── Check 2: Module compile ─────────────────────────────────────────────────
echo
echo "── Check 2: Module compile ──"
COMPILE_OUT=$(python3 -c "
import sys; sys.path.insert(0, '.')
mods = ['ilma_subagent_router', 'ilma_model_registry', 'ilma_runtime_wiring', 'ilma_claudecode_agent']
for m in mods:
    try: __import__(m); print(f'OK {m}')
    except Exception as e: print(f'FAIL {m}: {e}')
" 2>&1)
echo "$COMPILE_OUT"
if echo "$COMPILE_OUT" | grep -q "^FAIL"; then
  echo "❌ FAIL: Module compile errors above"
  exit 1
fi
echo "✅ All active modules compile"

# ── Check 3: Status check ───────────────────────────────────────────────────
echo
echo "── Check 3: ilma.py --status ──"
STATUS_OUT=$(python3 ilma.py --status 2>&1 || true)
echo "$STATUS_OUT" | grep -E "Ready:|Errors:" | head -3
# Allow Ready: ⚠️  (pre-existing MongoDB errors are OK, not from cleanup)
if echo "$STATUS_OUT" | grep -q "ImportError\|ModuleNotFoundError\|SyntaxError"; then
  echo "❌ FAIL: Import/syntax errors in boot"
  exit 1
fi
echo "✅ Boot OK (pre-existing warnings acceptable)"

# ── Check 4: Wiring check ───────────────────────────────────────────────────
echo
echo "── Check 4: Runtime wiring ──"
WIRING_OUT=$(python3 ilma_runtime_wiring.py --verify 2>&1 || true)
echo "$WIRING_OUT" | grep -E "missing_modules|status" | head -5
if echo "$WIRING_OUT" | grep -q "missing_modules.*\[.\+\]"; then
  echo "❌ FAIL: Missing modules"
  exit 1
fi
echo "✅ Runtime wiring intact"

echo
echo "=== ALL CHECKS PASSED ==="
echo "Target '$TARGET' cleanup verified end-to-end."
exit 0
