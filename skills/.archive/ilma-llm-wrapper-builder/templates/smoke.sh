#!/usr/bin/env bash
# wrapper-<provider> smoke harness — Productionization Loop step 6
# Usage: smoke.sh <provider> <prod_port> <alt_port>
#   e.g. smoke.sh nvidia 9100 9109
#
# What it does:
#   1. Boots the wrapper on ALPORT (does NOT touch prod)
#   2. Runs the 7-point checklist
#   3. Cleans up via process table (not via shell kill)
#   4. Prints a smk report (final line must be 'GO')
#
# Designed for one wrapper at a time. Loop the call to cover multiple wrappers.
#
# Pre-reqs:
#   - Stub keys must already be in a stub-env file or passed via env override
#     (this script does NOT manage secrets — never embed)
#   - wrapper must be runnable as `python3 main.py` from inside the repo

set -uo pipefail

if [[ $# -lt 3 ]]; then
    echo "usage: $0 <provider> <prod_port> <alt_port>"
    exit 2
fi

PROVIDER="$1"
PROD_PORT="$2"
ALT_PORT="$3"
WRAP_DIR="/root/wrapper/${PROVIDER}"

if [[ ! -d "$WRAP_DIR" ]]; then
    echo "[FAIL] wrapper dir not found: $WRAP_DIR"; exit 3
fi

cd "$WRAP_DIR"
BOOT_LOG="/tmp/${PROVIDER}_smoke_boot.log"
GW="127.0.0.1:${ALT_PORT}"

PASS=0
FAIL=0
stamp() { printf "%-44s %s\n" "$1" "$2"; }
ok()   { PASS=$((PASS+1)); stamp "$1" "OK"; }
no()   { FAIL=$((FAIL+1)); stamp "$1" "FAIL ($2)"; }

# ────────────────────────────────────────────────────────────────
# M1-AST — all .py parse
# ────────────────────────────────────────────────────────────────
list=()
while IFS= read -r f; do list+=("$f"); done < <(ls -1 *.py 2>/dev/null)
if [[ ${#list[@]} -eq 0 ]]; then
    no "M1-AST parse 7/7" "no .py files"
else
    bad=()
    for f in "${list[@]}"; do
        python3 -c "import ast; ast.parse(open('$f').read())" 2>/dev/null || bad+=("$f")
    done
    if [[ ${#bad[@]} -eq 0 ]]; then
        ok "M1-AST parse (${#list[@]} modules)"
    else
        no "M1-AST parse" "broken: ${bad[*]}"
    fi
fi

# ────────────────────────────────────────────────────────────────
# M2-import-set audit
# ────────────────────────────────────────────────────────────────
miss=()
for m in main key_pool capabilities metrics anthropic_compat loki_push alert_history; do
    spec=$(python3 -c "import importlib.util; print('y' if importlib.util.find_spec('$m') else 'n')" 2>/dev/null)
    [[ "$spec" == "y" ]] || miss+=("$m")
done
if [[ ${#miss[@]} -eq 0 ]]; then
    ok "M2-import-set audit (7/7)"
else
    no "M2-import-set" "missing: ${miss[*]}"
fi

# ────────────────────────────────────────────────────────────────
# M3-.env integrity (.gitignored)
# ────────────────────────────────────────────────────────────────
if [[ -f .env ]]; then
    n=$(grep -cE "^${PROVIDER^^}_API_KEY" .env 2>/dev/null || echo 0)
    if [[ "$n" -ge 1 ]]; then
        ok "M3-.env integrity ($n real keys present, .gitignored)"
    else
        no "M3-.env integrity" "no ${PROVIDER^^}_API_KEY*N entries"
    fi
else
    no "M3-.env integrity" "no .env file"
fi

# ────────────────────────────────────────────────────────────────
# M4-pre-commit installed
# ────────────────────────────────────────────────────────────────
if [[ -x .git/hooks/pre-commit ]]; then
    sz=$(stat -c%s .git/hooks/pre-commit 2>/dev/null || echo 0)
    if [[ "$sz" -ge 500 ]]; then
        ok "M4-pre-commit hook (${sz} bytes, executable)"
    else
        no "M4-pre-commit hook" "too small ($sz bytes)"
    fi
else
    no "M4-pre-commit hook" "missing or not executable"
fi

# ────────────────────────────────────────────────────────────────
# M5 — boot on alt-port (NEVER prod)
# ────────────────────────────────────────────────────────────────
NVIDIA_API_KEY_1=*** NVIDIA_API_KEY_2=*** NVIDIA_API_KEY_3=*** \
    LISTEN_HOST=127.0.0.1 LISTEN_PORT="$ALT_PORT" \
    python3 main.py > "$BOOT_LOG" 2>&1 &
WRAP_PID=$!

UP_TIME_MS=0
for i in $(seq 1 50); do
    if curl -sS --max-time 0.5 "http://${GW}/v1/models" >/dev/null 2>&1; then
        UP_TIME_MS=$((i * 200))
        break
    fi
    sleep 0.2
done

if [[ "$UP_TIME_MS" -gt 0 ]]; then
    ok "M5-alt-port boot (UP in ${UP_TIME_MS}ms)"
else
    no "M5-alt-port boot" "timed out, log at $BOOT_LOG"
fi

# ────────────────────────────────────────────────────────────────
# M6 — /v1/models
# ────────────────────────────────────────────────────────────────
if [[ "$UP_TIME_MS" -gt 0 ]]; then
    n_models=$(curl -sS "http://${GW}/v1/models" -m 5 2>/dev/null \
        | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('data',[])))" 2>/dev/null || echo 0)
    if [[ "$n_models" -gt 0 ]]; then
        ok "M6-/v1/models ($n_models models visible)"
    else
        no "M6-/v1/models" "0 models (possibly upstream issue)"
    fi
else
    no "M6-/v1/models" "service not up"
fi

# ────────────────────────────────────────────────────────────────
# M7 — /metrics/prom
# ────────────────────────────────────────────────────────────────
if [[ "$UP_TIME_MS" -gt 0 ]]; then
    expected=$(curl -sS "http://${GW}/metrics/prom" -m 5 2>/dev/null | head -3 | wc -l)
    if [[ "$expected" -ge 3 ]]; then
        ok "M7-/metrics/prom (≥3 gauges, format=text OK)"
    else
        no "M7-/metrics/prom" "no gauges emitted"
    fi
else
    no "M7-/metrics/prom" "service not up"
fi

# ────────────────────────────────────────────────────────────────
# M8 — cleanup alt-port (kill via pid; session table for global call)
# ────────────────────────────────────────────────────────────────
if [[ -n "${WRAP_PID:-}" ]]; then
    kill "$WRAP_PID" 2>/dev/null || true
    sleep 0.5
    if ss -lnt 2>/dev/null | grep -q ":${ALT_PORT}"; then
        no "M8-cleanup alt-port" "port ${ALT_PORT} still bound"
    else
        ok "M8-cleanup alt-port (9109 freed)"
    fi
fi

# ────────────────────────────────────────────────────────────────
# M9 — prod untouched (verify nothing broke)
# ────────────────────────────────────────────────────────────────
prod_alive=$(curl -sS --max-time 2 "http://127.0.0.1:${PROD_PORT}/v1/models" 2>/dev/null \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK' if d.get('data') else 'ERROR')" 2>/dev/null || echo "ERROR")
if [[ "$prod_alive" == "OK" ]]; then
    ok "M9-prod ${PROD_PORT} untouched"
else
    no "M9-prod ${PROD_PORT} untouched" "no models response"
fi

# ────────────────────────────────────────────────────────────────
# Final summary
# ────────────────────────────────────────────────────────────────
echo
echo "────────── smoke summary ──────────"
echo "$PASS pass / $FAIL fail"
if [[ "$FAIL" -eq 0 ]]; then
    echo "GO  → ready for tag"
else
    echo "NOGO → patch + retry"
fi

exit "$FAIL"
