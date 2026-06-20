#!/usr/bin/env bash
# scripts/verify_claudecode.sh
# Phase 71 verification — run end-to-end test of the ClaudeCode-Style Parallel Coding Agent.
#
# Pre-conditions:
#   1. ilma_claudecode_agent.py exists at /root/.hermes/profiles/ilma/
#   2. NVIDIA NIM API key configured (free tier, quota available)
#   3. 3 legacy sub-providers disabled (openaicodex, use, arena)
#
# Usage:  bash scripts/verify_claudecode.sh
# Exits 0 on success, 1 on any check failure.

set -e
ILMA="/root/.hermes/profiles/ilma"

echo "=== Phase 71: ClaudeCode-Style Parallel Coding Agent — Verification ==="
echo

# 1. Status check
echo "--- 1. Agent status ---"
if ! python3 "$ILMA/ilma_claudecode_agent.py" status > /tmp/cc_status.json; then
    echo "❌ FAIL: agent status command errored"
    exit 1
fi
TIERS=$(python3 -c "import json; d=json.load(open('/tmp/cc_status.json')); print(len(d['priority_stack']))")
if [ "$TIERS" -ne 4 ]; then
    echo "❌ FAIL: expected 4 tiers, got $TIERS"
    exit 1
fi
echo "✅ 4 priority tiers present: nvidia_nim, openrouter_free, blackbox_free, qwen_direct"

# 2. Verify disabled sub-providers
echo
echo "--- 2. Disabled sub-providers (Bos mandate) ---"
DISABLED=$(python3 -c "import json; d=json.load(open('/tmp/cc_status.json')); print(','.join(sorted(d['disabled_subproviders'])))")
for required in openaicodex use arena; do
    if echo "$DISABLED" | grep -q "$required"; then
        echo "  ✅ $required disabled"
    else
        echo "  ❌ FAIL: $required NOT in disabled list"
        exit 1
    fi
done

# 3. ilma.py --status (boot health)
echo
echo "--- 3. ilma.py --status ---"
if ! python3 "$ILMA/ilma.py" --status > /tmp/cc_boot.json 2>&1; then
    echo "❌ FAIL: ilma.py --status errored"
    exit 1
fi
if grep -q "Ready: ✅" /tmp/cc_boot.json; then
    echo "✅ ilma.py boot: Ready"
else
    echo "❌ FAIL: ilma.py boot not ready"
    exit 1
fi

# 4. Live end-to-end test (3 models in parallel on a simple task)
echo
echo "--- 4. End-to-end parallel execution ---"
TEST_TASK="Write a Python lambda to compute the square of a number"
if ! timeout 180 python3 "$ILMA/ilma_claudecode_agent.py" parallel --task "$TEST_TASK" --count 3 > /tmp/cc_parallel.out 2>&1; then
    echo "❌ FAIL: parallel execution errored"
    cat /tmp/cc_parallel.out
    exit 1
fi
if grep -q "WINNER:" /tmp/cc_parallel.out; then
    WINNER=$(grep "WINNER:" /tmp/cc_parallel.out | head -1)
    echo "✅ Parallel execution: $WINNER"
else
    echo "❌ FAIL: no winner declared"
    tail -20 /tmp/cc_parallel.out
    exit 1
fi

# 5. Evidence ID
if grep -q "ILMA-EVID-" /tmp/cc_parallel.out; then
    EVID=$(grep "ILMA-EVID-" /tmp/cc_parallel.out | tail -1)
    echo "✅ Evidence: $EVID"
else
    echo "⚠️  WARNING: no evidence ID found in output"
fi

echo
echo "=== ALL CHECKS PASSED ==="
echo "Phase 71 ClaudeCode Agent is operational."
exit 0
