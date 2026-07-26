# SOT Integrity Layer — Implementation Reference (Phase 73)

This reference contains the actual scripts, config snippets, and edge cases discovered while building the SOT integrity layer. The umbrella SKILL.md has the architectural overview; this file has the working code and gotchas.

## File Inventory

| File | Purpose | Mode |
|------|---------|------|
| `scripts/ilma_sot_integrity.py` | Schema validation + auto-rollback | `python3 ilma_sot_integrity.py {--check\|--gate\|--auto-rollback}` |
| `scripts/ilma_safe_build_and_push.sh` | build → verify → push chain | `bash ilma_safe_build_and_push.sh` |
| `ilma_model_router_data/sot_integrity_log.jsonl` | Append-only validation log | auto-generated |
| `ilma_model_router_data/backups/PROVIDER_INTELLIGENCE_MASTER_*.json` | Auto-backup snapshots | auto-generated |

## `ilma_sot_integrity.py` — Core Schema Spec

```python
"""SOT Integrity Layer — validates PROVIDER_INTELLIGENCE_MASTER.json
Phase 73, 2026-06-07. Bos mandate: hati-hati, cross-cek berkali-kali."""

import json
import sys
import shutil
import os
from pathlib import Path
from datetime import datetime

SOT_PATH = "/root/.hermes/profiles/ilma/ilma_model_router_data/PROVIDER_INTELLIGENCE_MASTER.json"
BACKUP_DIR = "/root/.hermes/profiles/ilma/ilma_model_router_data/backups"
LOG_PATH = "/root/.hermes/profiles/ilma/ilma_model_router_data/sot_integrity_log.jsonl"

# CRITICAL = router will break if missing/wrong
CRITICAL_MODEL_KEYS = {"model_id", "provider"}

# WARN = quality/reporting issue, not breaking
WARN_KEYS = {"quality_score", "is_active", "is_free", "context_window"}

ISSUE_CODES = {
    "MISSING_MODEL_ID": "CRITICAL",
    "PROVIDER_MISMATCH": "CRITICAL",
    "MISSING_KEY": "CRITICAL",
    "ENRICHMENT_GAP": "WARN",
    "DRIFT_SIZE": "WARN",
    "BACKUP_FRESHNESS": "WARN",
}
```

## Issue Codes — When Each Fires

| Code | Severity | Trigger |
|------|----------|---------|
| `MISSING_MODEL_ID` | CRITICAL | Model entry has empty/None `model_id` field |
| `PROVIDER_MISMATCH` | CRITICAL | Model's `provider` field doesn't match its key prefix (e.g., `nvidia/x` in `minimax` section) |
| `MISSING_KEY` | CRITICAL | A `CRITICAL_MODEL_KEYS` field is absent entirely |
| `ENRICHMENT_GAP` | WARN | Model has no `quality_score` or `benchmark_profile` (won't route well) |
| `DRIFT_SIZE` | WARN | SOT size changed > 10% between snapshots (suggests mass delete or corruption) |
| `BACKUP_FRESHNESS` | WARN | Latest backup is > 7 days old (rollback candidates may be stale) |

## Auto-Rollback Algorithm

```python
def find_rollback_candidate(backup_dir):
    """Scan backups newest-first, return first one that passes the gate."""
    backups = sorted(Path(backup_dir).glob("PROVIDER_INTELLIGENCE_MASTER_*.json"),
                      reverse=True)
    for backup in backups:
        result = check_file(backup)
        if result["status"] == "PASS":
            return backup
    return None

def restore_atomic(backup_path, live_path):
    """Atomic restore: write to .new, validate, rename over live."""
    new_path = live_path + ".new"
    shutil.copy2(backup_path, new_path)
    # Validate the .new file before replacing
    if check_file(new_path)["status"] != "PASS":
        os.remove(new_path)
        raise RuntimeError(f"Backup {backup_path} failed validation — refusing to restore")
    os.replace(new_path, live_path)  # atomic on POSIX
```

## `ilma_safe_build_and_push.sh` — Full Script

```bash
#!/bin/bash
set -euo pipefail

# ILMA Safe Build & Push — Phase 73 SOT Integrity Layer
# Bos mandate: hati-hati, cross-cek berkali-kali.
# Chain: pipeline --full-sync → integrity --gate → git add/commit/push
# On gate failure: auto-rollback, no push

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ILMA_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$ILMA_ROOT"

echo "=== Step 1: Pipeline --full-sync (writes SOT + auto-backup) ==="
python3 scripts/ilma_db_pipeline.py --full-sync

echo "=== Step 2: Gate the result ==="
if ! python3 scripts/ilma_sot_integrity.py --gate; then
    echo "GATE FAILED — attempting auto-rollback"
    python3 scripts/ilma_sot_integrity.py --auto-rollback
    exit 1
fi

echo "=== Step 3: Commit + push ==="
git add ilma_model_router_data/PROVIDER_INTELLIGENCE_MASTER.json
git commit -m "ILMA Phase 73 sync: SOT validated + gated"
git push origin master
```

## Cron Job Pattern (no_agent + deliver=local)

```json
{
  "id": "bf9ad9925449",
  "name": "ILMA Model DB Sync (00:00 & 12:00 WIB)",
  "schedule": "0 0,12 * * *",
  "no_agent": true,
  "script": "scripts/ilma_db_pipeline.py --full-sync --git-push",
  "deliver": "local",
  "enabled": true,
  "workdir": "/root/.hermes/profiles/ilma"
}
```

**Why no_agent=True:** The pipeline is fully deterministic. The LLM agent previously triggered prompt-injection scanners (the `prompt=` field was flagged). Switching to `script=` + `no_agent=true` makes it a pure watchdog.

**Why deliver=local:** Output stays in scheduler state for inspection. WARN-level issues don't spam Telegram; only the daily optimization agent reads the log.

## Edge Cases Discovered (Phase 73)

### 1. `ilma_model_db_manager.py --git-push` re-runs `--full-sync` internally

When `ilma_db_pipeline.py --full-sync --git-push` runs, the manager's `--git-push` step internally calls `--full-sync` again before pushing. The integrity gate runs 2-3 times per cron tick. This is intentional (defense in depth) but means the log will have duplicate entries. Don't be alarmed.

### 2. `git add -A` fails when `backups/` is in `.gitignore`

```bash
# WRONG — backups/ is intentionally untracked
git add -A
# error: pathspec 'backups/PROVIDER_INTELLIGENCE_MASTER_20260607_xxx.json' did not match

# RIGHT — target only the SOT file
git add ilma_model_router_data/PROVIDER_INTELLIGENCE_MASTER.json
```

### 3. Rollback must use backups, NOT git history

Git HEAD may already contain the bad SOT if the gate was bypassed. Rolling back to a git commit would re-introduce the bad SOT. Always rollback to a backup file from `ilma_model_router_data/backups/`.

### 4. The integrity script reads SOT once at startup

If the script also performs rollback, the in-memory `master` dict is stale. Always re-load:

```python
if rollback_occurred:
    master = json.load(open(SOT_PATH))  # re-read after rollback
```

### 5. WARN issues don't block the gate but do show in `sot_integrity_log.jsonl`

When `deliver=local`, cron output is saved to scheduler state but NOT sent to Telegram. To surface WARNs, use a separate watchdog cron that reads the log and alerts on `level=WARN` accumulation.

## Validation Workflow

```bash
# 1. Run gate manually — should exit 0
python3 scripts/ilma_sot_integrity.py --gate
echo "Exit: $?"  # expect 0

# 2. Read-only check with full report
python3 scripts/ilma_sot_integrity.py --check | jq .

# 3. Run the full safe-build chain (manual cron simulation)
bash scripts/ilma_safe_build_and_push.sh

# 4. Inspect the log
tail -20 ilma_model_router_data/sot_integrity_log.jsonl | jq .

# 5. List available rollback candidates
ls -lt ilma_model_router_data/backups/PROVIDER_INTELLIGENCE_MASTER_*.json | head -5

# 6. Verify cron wiring
hermes cron list 2>/dev/null | grep -i "sot\|model db" || \
  cat ~/.hermes/profiles/ilma/cron/jobs.json | jq '.jobs[] | select(.name | contains("Model DB"))'
```

## When to Update This Layer

| Trigger | Action |
|---------|--------|
| New SOT field becomes routing-critical | Add to `CRITICAL_MODEL_KEYS` |
| New quality/reporting metric needed | Add to `WARN_KEYS` |
| New production incident reveals a missing check | Add new `ISSUE_CODES` entry with handler |
| Backup cadence changes | Update `BACKUP_FRESHNESS` threshold (default: 7 days) |
| SOT structure changes (new top-level key) | Update `check_file()` to validate new structure |

## Related Files

- `references/db-pipeline-architecture.md` — the 5-step pipeline that WRITES the SOT
- `references/phase-72-validation-patterns.md` — validation patterns that complement integrity
- `references/status-registry-sot.md` — `is_active`/`status` lifecycle (where CRITICAL/WARN interact)
- `references/sot-deep-analysis.md` — Phase 73 SOT analysis that motivated the integrity layer
