# Git Sync Workflow — 2026-05-17 Session

## Key Finding: Repo Structure

ILMA GitHub repo (`/tmp/ilma-core-update/`) tracks a **subdirectory**, not the root:

```
Local: /root/.hermes/profiles/ilma/        ← ILMA lives here
Repo:  /tmp/ilma-core-update/              ← tracks hermes_profile_ilma/
```

When pushing changes:
1. Copy changed files from `/root/.hermes/profiles/ilma/` → `/tmp/ilma-core-update/hermes_profile_ilma/`
2. Commit and push from `/tmp/ilma-core-update/`

**Do NOT** clone into `/root/.hermes/profiles/ilma/` directly — it would overwrite local files.

## Workflow: Sync Local-Ahead to Remote-Behind

When: local is ahead by 1 commit, remote has 2 new commits. `git pull` needs `--no-edit` flag but fails.

**Solution: Stash + Fetch + Rebase + Pop**

```bash
# 1. Stash local changes
git stash

# 2. Fetch latest remote
GIT_SSH_COMMAND="ssh -o StrictHostKeyChecking=no" git fetch origin master

# 3. Rebase local commits onto remote
git rebase FETCH_HEAD

# 4. Restore stashed changes
git stash pop

# 5. Push
git push origin master
```

**Output from 2026-05-17:**
```
stash
  WIP on master: ee84a3b [origin/master: di depan 1, di belakang 2]
rebase FETCH_HEAD
  Mendasarkan ulang (1/1)
  refs/heads/master didasarkan ulang dan diperbarui dengan sukses
stash pop
  refs/stash@{0} dijatuhkan
push
  4b0f3d1..79e2262  master -> master ✅
```

## `.git-credentials` Location (Container/Sandbox)

**Critical path:** `/root/.hermes/profiles/ilma/home/.git-credentials`

This is NOT `/root/.git-credentials` or `/root/.hermes/.git-credentials`. It's inside the `home/` subdirectory of the ILMA profile.

Content format: `https://ghp_TOKEN@github.com`

When this file exists → git push succeeds.
When missing → push fails with ENXIO (container has no TTY).

## Commands Reference

```bash
# Check branch status (ahead/behind)
git branch -vv
# * master ee84a3b [origin/master: di depan 1, di belakang 2] ...

# Check remotes
git remote -v
# origin  git@github.com:lokah1945/ilma-core.git (fetch)
# origin  git@github.com:lokah1945/ilma-core.git (push)
# push-target https://TOKEN@github.com/... (fetch/push)

# Force check what the remote SHA is
GIT_SSH_COMMAND="ssh -o StrictHostKeyChecking=no" git fetch origin master
# Then check: git log --oneline HEAD..FETCH_HEAD (what remote has that local doesn't)
```

## Git Push Failure Diagnosis

| Symptom | Cause | Fix |
|---------|-------|-----|
| ENXIO on push | No TTY device in container | Use `.git-credentials` with embedded token |
| "failed to push some refs" | local behind remote | `git fetch + rebase` or `git stash + rebase + stash pop` |
| HTTPS 401 | Token wrong or expired | Retrieve from `/root/credential/api_key.json.bak_20260505_203624` |
| Authentication failed | Wrong remote URL format | Use SSH format `git@github.com:owner/repo.git` for fetch, `.git-credentials` for push |