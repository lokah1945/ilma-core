#!/usr/bin/env bash
# ILMA Safe Build & Push Wrapper
# ==============================
# Author: ILMA v3.30 (Phase 73)
# Date:   2026-06-07
#
# Purpose
# -------
# Chain three steps that must succeed in order:
#   1. BUILD:    Run ilma_model_db_manager.py --full-sync   (refresh SOT from live providers/benchmarks)
#   2. VERIFY:   Run ilma_sot_integrity.py --gate           (auto-rollback to last known-good if SOT is invalid)
#   3. PUSH:     Run ilma_model_db_manager.py --git-push   (only if SOT is valid)
#
# Why this wrapper
# ----------------
# The old cron called manager.py directly with --full-sync --git-push. If the build
# step produced a corrupt SOT (e.g. provider dropped to 0, schema broke, drift > threshold),
# the --git-push would still run and the bad SOT would land in the GitHub repo, poisoning
# the source of truth for every consumer on the next pull.
#
# This wrapper inserts a hard gate. If SOT fails validation, it auto-rolls back to the
# last known-good backup and REFUSES to push.
#
# Exit codes
# ----------
#   0  build + verify + push all succeeded
#   1  build failed (manager --full-sync returned non-zero)
#   2  verify failed and rollback also failed (CRITICAL: SOT is bad, no good backup)
#   3  verify failed and rollback succeeded; push was skipped
#
# Usage
# -----
#   bash scripts/ilma_safe_build_and_push.sh         # full chain (cron default)
#   bash scripts/ilma_safe_build_and_push.sh --skip-build   # just verify + push
#
set -uo pipefail

PROFILE="/root/.hermes/profiles/ilma"
MANAGER="$PROFILE/scripts/ilma_model_db_manager.py"
INTEGRITY="$PROFILE/scripts/ilma_sot_integrity.py"
SOT="$PROFILE/ilma_model_router_data/PROVIDER_INTELLIGENCE_MASTER.json"
LOG="$PROFILE/ilma_model_router_data/sot_safe_build.log"

mkdir -p "$(dirname "$LOG")"
ts() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

SKIP_BUILD=0
for arg in "$@"; do
    case "$arg" in
        --skip-build) SKIP_BUILD=1 ;;
        *) log "WARN: unknown arg '$arg' ignored" ;;
    esac
done

# --- 1) BUILD ---
if [ "$SKIP_BUILD" = "1" ]; then
    log "STEP 1: SKIPPED (--skip-build)"
else
    log "STEP 1: BUILD — running $MANAGER --full-sync"
    if ! python3 "$MANAGER" --full-sync; then
        log "STEP 1: BUILD FAILED (exit=$?)"
        exit 1
    fi
    log "STEP 1: BUILD OK"
fi

# --- 2) VERIFY (auto-rollback if FAIL) ---
log "STEP 2: VERIFY — running $INTEGRITY --gate"
gate_out=$(python3 "$INTEGRITY" --gate --file "$SOT" 2>&1)
gate_rc=$?
log "STEP 2: verify output:\n$gate_out"
log "STEP 2: gate exit code = $gate_rc"

case "$gate_rc" in
    0)
        log "STEP 2: VERIFY PASS — SOT is valid"
        ;;
    1)
        log "STEP 2: VERIFY FAIL — auto-rollback succeeded; push will be SKIPPED"
        exit 3
        ;;
    2)
        log "STEP 2: VERIFY FAIL — NO VALID BACKUP. SOT is corrupt and cannot be auto-restored."
        log "STEP 2: Manual intervention required: inspect SOT, restore from external source."
        exit 2
        ;;
    *)
        log "STEP 2: UNEXPECTED exit code $gate_rc from integrity gate"
        exit 2
        ;;
esac

# --- 3) PUSH (only if SOT is valid) ---
# Use raw git commands (NOT manager.py --git-push, which would re-trigger full-sync).
log "STEP 3: PUSH — git add + commit + push"
cd "$PROFILE" || { log "STEP 3: cannot cd to $PROFILE"; exit 1; }

# Add SOT (always tracked). The SOT may be gitignored by design (large file);
# in that case upstream workflow expects force-add so the artifact ships.
if ! git add ilma_model_router_data/PROVIDER_INTELLIGENCE_MASTER.json 2>>"$LOG"; then
    log "STEP 3: plain git add skipped (gitignored) — trying force add"
    if ! git add -f ilma_model_router_data/PROVIDER_INTELLIGENCE_MASTER.json 2>>"$LOG"; then
        log "STEP 3: git add SOT FAILED (even with -f)"
        exit 1
    else
        log "STEP 3: SOT force-added successfully"
    fi
fi
# Try to add benchmark only if not gitignored
if ! git check-ignore ilma_model_router_data/benchmark_database.json >/dev/null 2>&1; then
    git add ilma_model_router_data/benchmark_database.json 2>>"$LOG" || log "STEP 3: (warn) benchmark add skipped"
else
    log "STEP 3: (info) benchmark_database.json is gitignored, skipping"
fi

if ! git diff --cached --quiet; then
    MODEL_COUNT=$(python3 -c "import json; d=json.load(open('$SOT')); print(sum(len(v.get(\"models\",{})) for v in d.get(\"providers\",{}).values()))" 2>/dev/null || echo "?")
    COMMIT_MSG="chore(model-db): safe-build $(date -u +%Y-%m-%d_%H%M) ($MODEL_COUNT models)"
    log "STEP 3: changes detected — committing: $COMMIT_MSG"
    if ! git commit -m "$COMMIT_MSG" 2>>"$LOG"; then
        log "STEP 3: git commit FAILED"
        exit 1
    fi
    if ! git push origin master 2>>"$LOG"; then
        log "STEP 3: git push FAILED"
        exit 1
    fi
    log "STEP 3: PUSH OK — SOT shipped to GitHub"
else
    log "STEP 3: no changes to commit — SOT unchanged since last build, skipping push"
fi
exit 0
