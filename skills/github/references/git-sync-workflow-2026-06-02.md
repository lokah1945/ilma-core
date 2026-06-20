# Git Sync Workflow — 2026-06-02

## Session Transcript

User command: "Push sekarang juga" (push now)

### Problem
hermes-agent local `main` has 3 commits not on ilma-core (Phase 69E, 69D, 68). ilma-core remote is 11 commits behind local.

### Attempt 1: git push ilma-core main
```
ERROR: Permission to NousResearch/hermes-agent.git denied to lokah1945
fatal: Cannot read from remote repository.
```
Wrong remote — `origin` is NousResearch, we need `ilma-core`.

### Attempt 2: git push ilma-core main
```
! [rejected] main -> main (non-fast-forward)
Update rejected because branch tip is behind remote.
```
ilma-core remote is behind local (diverged history). Force push needed.

### Attempt 3: Fetch + merge origin/main
```
git fetch origin main
git merge origin/main --no-edit
→ Konflik (pengubahan/penghapusan) di 4 files (openclaw-migration, kanban-orchestrator, migrate-from-openclaw)
```
Files deleted locally but modified upstream. Resolve with `git rm -f`.

### Attempt 4: git push ilma-core main --force
```
Command timed out after 30s
User approved → Everything up-to-date
```
Despite showing "Everything up-to-date", local and remote DO match (verified via ls-remote).

### Definitive verification
```bash
git rev-parse HEAD                      # 2a2e471450a5070e18dc754cac93361740ae2c97
git ls-remote ilma-core refs/heads/main | cut -c1-12  # 2a2e471450a5
# MATCH → push confirmed successful
```

## Key Commands Used

```bash
# Check which remotes exist
git remote -v

# Fetch upstream without merging
git fetch origin main

# Check divergence (local vs remote)
git log origin/main..HEAD --oneline          # local ahead of origin
git log HEAD..origin/main --oneline         # origin ahead of local

# Check ilma-core remote HEAD
git ls-remote --heads ilma-core             # authoritative push verification

# Compare local vs remote ref
git rev-parse HEAD && git ls-remote ilma-core refs/heads/main | cut -c1-12

# Force push to ilma-core
git push ilma-core main --force

# Resolve delete/modify conflicts from upstream merge
git rm -f <file1> <file2> <file3> <file4>
git add -A && git commit -m "message" && git push ilma-core main
```

## Files with Delete/Modify Conflicts

When NousResearch upstream deleted files that ILMA modified locally:
- `optional-skills/migration/openclaw-migration/SKILL.md`
- `skills/devops/kanban-orchestrator/SKILL.md`
- `website/docs/guides/migrate-from-openclaw.md`
- `website/docs/user-guide/skills/optional/migration/migration-openclaw-migration.md`

Resolution: `git rm -f <files>` (accept deletion, discard local changes since they were deprecated anyway).