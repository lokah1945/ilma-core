# BIG CHANGE — Commit Push Protocol

## Context
Session besar-besaran ("Phase 0–7: Full Pipeline Validation & Production Lockdown") menghasilkan >100 file berubah dan puluhan langkah validasi. Bos menegaskan: **"Tidak JARMIN (jangan ragu mainin) saat besar-besaran... segala hal yg berubah di ilma harus dicommit dan dipush ke repo."**

This file captures the commit-push protocol for big changes so no work is lost.

## Protocol

### 1. Immediate commit on every file change
```bash
git add <file>
git commit -m "<phase>: <what changed>"
# NEVER batch >1 file without committing
```

### 2. Push to two remotes
```bash
git remote add backup origin 2>/dev/null || true
git push origin <branch>
git push backup <branch> 2>/dev/null || true
```

### 3. Verify
```bash
git log --oneline -5
git status  # MUST be clean
```

### 4. Pre-push validation (before final lockdown push)
```bash
python3 -c "import json; json.load(open('ilma_model_router_data/PROVIDER_INTELLIGENCE_MASTER.json'))"
python3 -m py_compile ilma_model_router.py ilma_client.py scripts/ilma_model_db_manager.py
```

### 5. What to include in commit message
Format: `PHASE-##: <component> — <what>`
Example: `PHASE-1B: MASTER — fix is_free logic (2343 models corrected)`

## Pitfalls
- **NEVER leave uncommitted changes after a session** — even if "just testing". Use `git stash` if needed.
- **NEVER `--amend` after push** — use follow-up commit instead.
- **ALWAYS verify repo is clean before starting new phase** — run `git status` and commit any stray changes.
