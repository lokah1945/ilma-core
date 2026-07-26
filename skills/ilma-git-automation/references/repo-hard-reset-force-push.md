# Repo Hard-Reset & Force-Push (Clean Slate) — 2026-07-26

Bos: "Reset repo ILMA agar code benar-benar baru dan kedepannya trackable. Hapus all file di repo. Pahami ulang keseluruhan code, lalu buat ulang README.md. Force push ulang semua code ke repo github ILMA setelah memastikan all file di repo github sudah di bersihkan."

## What "reset repo" means here
- Clear **git tracking history** (orphan branch → force push). NOT `rm -rf` disk.
- Code stays on disk (needed for "pahami ulang" + "force push ulang semua code").
- Junk (corrupt JSON, garbage dirs) simply not re-added → effectively gone from repo.

## Pre-flight (MANDATORY)
1. **Inventory**: `git ls-files | wc -l`, top-level dirs, remote, branch.
2. **Secret scan**: confirm `/config.yaml`, `/.env`, `*credential*`, `*secret*`, `*.pem`, `*.key` NOT tracked (or covered by .gitignore).
3. **Big-data scan**: `git ls-files | xargs stat -c%s` → flag >1MB (model DB, caches). These MUST be gitignored or they bloat the clean repo.
4. **Local backup** (safety net, NOT pushed):
   ```bash
   mkdir -p /root/ilma_reset_backup
   tar czf /root/ilma_reset_backup/ilma_before_reset_$(date +%Y%m%d_%H%M%S).tar.gz \
     --exclude='.git' --exclude='ilma_model_router_data' --exclude='node_modules' .
   ```
   Run in **background** (`terminal background=true notify_on_complete=true`) — 5GB disk tar can exceed 60s foreground timeout.

## Step-by-step reset
```bash
cd /root/.hermes/profiles/ilma

# 1. Harden .gitignore FIRST (so data/cache never re-enters)
#    Add: ilma_model_router_data/  models_dev_cache.json  *.sqlite  *.sqlite3
#          *.db  *.db-journal  state-snapshots/  cron/ticker_*  *.bak  *.backup
#          (secrets already covered: /config.yaml /.env *credential* *secret*)

# 2. Orphan branch (clean history)
git checkout --orphan fresh_master
git rm -rf --cached .              # unstage all, KEEP disk
# verify: git ls-files | wc -l  → 0

# 3. Re-add respecting new .gitignore
git add -A
git ls-files | wc -l                # should be < prior count (data excluded)
# SANITY: no secret/data tracked
git ls-files | grep -E "ilma_model_router_data|models_dev_cache|\.sqlite|state-snapshots|cron/ticker_|config\.yaml$|/\.env"
# (empty = good)

# 4. Rewrite README.md from architecture understanding (see template below)

# 5. Commit
git commit -q -m "chore: reset repo — clean codebase, README v3.30
<detail: excluded data/cache, hardened gitignore, verified via audit YYYYMMDD>"

# 6. Swap branch
git branch -D master                 # needs user approval (force delete)
git branch -m fresh_master master

# 7. FORCE PUSH (clears GitHub history)
git push --force origin master
# → "c22f473...693581e master -> master (forced update)"
```

## Verification after push
```bash
git rev-parse HEAD                   # new orphan commit
git log --oneline -1                 # single clean base commit
git ls-files | wc -l                 # clean count
git ls-files | grep -c "^README.md$" # 1
# Remote: force-push confirmed "forced update" = GitHub history cleared.
```

## Pitfalls (learned)
- **Don't `git add -A` before .gitignore hardening** → 1.5GB `ilma_model_router_data/` (incl `model_intelligence.sqlite`) + 5.5MB `PROVIDER_INTELLIGENCE_MASTER.json` + 3.2MB `models_dev_cache.json` would be pushed. Always harden gitignore FIRST.
- **`git branch -D master` requires user approval** (Hermes protects force-delete). It WILL prompt; approve.
- **Force push auth**: SSH key (`/root/.ssh/id_ed25519`) offered but `Permission denied (publickey)` if pubkey NOT on GitHub account. Use HTTPS credential helper: `git remote set-url origin https://github.com/lokah1945/ilma-core.git` then push. PAT lives in `git credential` helper (don't paste into memory/skill).
- **Backup tar can time out foreground** → run background + notify.
- **`state-snapshots/` + `cron/ticker_*` are runtime state** → exclude from clean repo (they're regenerated).
- **Junk dirs (archive/garbage) already removed in prior phases** → don't re-create. If present, simply don't `git add` them.

## README template (post-reset)
Structure from 2026-07-26 reset:
- Title + philosophy (evidence-over-claim, capability-over-tool, pure data-driven routing)
- 8-Layer Canon8 pipeline table (BOOT→ANALYZE→ROUTE→RESOLVE→EXECUTE→EVALUATE→VERIFY→LEARN→REPORT)
- Browser policy table (Phase 66/69: engine='', cdp 127.0.0.1:9222, enforce_custom_browser)
- Model routing (circuit-breaker durable, FREE-tier first)
- Capability registry clarification (37 runtime + 108 evidence ledger — TWO sources, don't conflate)
- Quick start, testing, repo structure, security boundaries, version history

## Result (2026-07-26)
- 1780 → 1769 tracked (data/cache/heartbeat excluded)
- Commit `693581e` "chore: reset repo — clean codebase, README v3.30"
- Force-pushed: `c22f473...693581e master -> master (forced update)`
- Backup: `/root/ilma_reset_backup/ilma_before_reset_20260726_182057.tar.gz` (1.3G)
- Local HEAD == remote HEAD, GitHub history clean.
