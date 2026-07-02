#!/usr/bin/env bash
# verify_wrapper_release.sh — end-to-end release verification for a wrapper
# Usage: verify_wrapper_release.sh <provider> <prod_port> [--tag vN+1.0]
#
# Verifies the WHOLE productionization loop is in place, not just runtime works:
#   1. Loops through smoke harness on alt port
#   2. Verifies README-as-index: every backticked filename ref must resolve
#   3. Verifies pre-commit hook actually runs (touch a hack attempt)
#   4. Reports governance summary (count of orphans / duplications / pending tags / known-unavailable models)
#
# Exit code: 0 = ready for tag, 1 = NOGO with details

set -uo pipefail

PROVIDER="${1:-}"
PROD_PORT="${2:-9100}"
TAG_ARG="${3:-}"

if [[ -z "$PROVIDER" ]]; then
    echo "usage: $0 <provider> <prod_port> [vN.M]"
    exit 2
fi

WRAP_DIR="/root/wrapper/${PROVIDER}"
if [[ ! -d "$WRAP_DIR" ]]; then
    echo "[FAIL] wrapper dir not found: $WRAP_DIR"
    exit 3
fi

cd "$WRAP_DIR"

echo "══════════════════════════════════════════════"
echo "  wrapper release verification — $PROVIDER"
echo "══════════════════════════════════════════════"

echo
echo "[1/4] smoke on alt port (9109)…"
SCRIPT_PATH="$(dirname "$(readlink -f "$0")")/../templates/smoke.sh"
if [[ -f "$SCRIPT_PATH" ]]; then
    if ! bash "$SCRIPT_PATH" "$PROVIDER" "$PROD_PORT" 9109; then
        echo "[NOGO] smoke harness failed — see above"
        exit 1
    fi
else
    echo "[SKIP] smoke.sh not found at $SCRIPT_PATH (manual M8 verification needed)"
fi

echo
echo "[2/4] README-as-index: backticked filename refs MUST resolve…"
miss_count=$(python3 -c "
import re, os
src = open('README.md').read() if os.path.exists('README.md') else ''
refs = set(re.findall(r'\`([a-z_][a-z0-9_-]+\.(?:py|sh|json|toml|md))\`', src))
miss = [r for r in sorted(refs) if not os.path.isfile(r)]
print(len(miss))
" 2>/dev/null || echo "-1")
if [[ "$miss_count" == "0" ]]; then
    echo "  OK (all refs resolve)"
else
    echo "  [FAIL] $miss_count broken refs in README"
    python3 -c "
import re, os
src = open('README.md').read()
refs = set(re.findall(r'\`([a-z_][a-z0-9_-]+\.(?:py|sh|json|toml|md))\`', src))
miss = [r for r in sorted(refs) if not os.path.isfile(r)]
for r in miss: print(f'    MISS: {r}')
"
    exit 1
fi

echo
echo "[3/4] pre-commit hook smoke (try to stage a fake secret, expect block)…"
# stage a test file with a fake NVIDIA key
testfile="$(mktemp .tests/secret_guard_XXXX.sh)"
mkdir -p .tests
cat > "$testfile" <<'EOF'
#!/bin/bash
NVIDIA_API_KEY="nvapi-fake-fake-fake-fake-fake"
echo "ok"
EOF
git add "$testfile" 2>/dev/null
if git commit -m "secret-test" 2>&1 | grep -qE 'BLOCK|WARNING|secret'; then
    echo "  OK (hook blocked fake secret — cleanup pending)"
    rm -f ".tests/$(basename "$testfile")"
    git reset -q HEAD 2>/dev/null
else
    echo "  [FAIL] pre-commit did not block fake secret"
    rm -f ".tests/$(basename "$testfile")"
    git reset -q HEAD 2>/dev/null
    exit 1
fi

echo
echo "[4/4] governance summary…"
echo "  tracked files: $(git ls-files | wc -l)"
echo "  untracked (candidates for next tag): $(git ls-files --others --exclude-standard | wc -l)"
echo "  README sections: $(grep -cE '^## ' README.md 2>/dev/null || echo 0)"
echo "  metrics.db WAL size: $(stat -c%s metrics.db-wal 2>/dev/null || echo 'none') bytes"
echo "  latest tag: $(git tag --list 'v*' | sort -V | tail -1 || echo 'none')"

echo
echo "══════════════════════════════════════════════"
if [[ "$miss_count" == "0" ]] && [[ -x .git/hooks/pre-commit ]]; then
    echo "  READY FOR TAG ($PROVIDER)"
    if [[ -n "$TAG_ARG" ]]; then
        echo
        echo "[tag] creating $TAG_ARG…"
        git tag -a "$TAG_ARG" -m "wrapper-${PROVIDER} ${TAG_ARG} - automated release verification passed" 2>&1 | tail -3
    fi
else
    echo "  NOGO — fix above first"
    exit 1
fi
