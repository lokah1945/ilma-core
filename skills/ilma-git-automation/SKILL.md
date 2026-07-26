---
name: ilma-git-automation
description: Patterns and best practices for git automation
---

# Git Automation

Version: 2.0
Enhanced: 2026-05-06

## Purpose
Patterns and best practices for git automation

## When to Use
This skill activates when task contains:
- `git`
- `automation`
- Related technical context

## Core Functions

### 1. Problem Analysis
- Identify the core problem type
- Assess complexity and scope
- Determine appropriate approach

### 2. Implementation Pattern
- Follow established best practices
- Consider edge cases and error handling
- Ensure maintainability

### 3. Verification
- Test basic functionality
- Verify edge cases handled
- Check performance implications

## Usage

### Direct Usage
```bash
# Not typically called directly
# Used by ILMA's skill auto-trigger system
```

### Integration Points
- Triggered by skill auto-loader when relevant keywords detected
- Can be manually invoked via skill_view()
- Referenced by orchestrator for task routing

## Related Skills
- ilma-problem-solve (general problem solving)
- ilma-learning (knowledge acquisition)
- ilma-assessment (evaluation)

## Critical Patterns

### Git Push with Token from Credential Store

**Problem:** Git push fails with "could not read Password" even when credential.helper is set and token is embedded in remote URL.

**Root Cause:** Token in remote URL or credential store can be truncated. Token must be the FULL 40-character key from `/root/credential/api_key.json` → `github.keys[0]`.

**Solution Pattern:**
```python
import subprocess
import os

token = "ghp_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"  # FULL 40-char token

remote_url = f"https://{token}@github.com/{owner}/{repo}.git"

subprocess.run(
    ["git", "-C", "/", "push", "ilma-core", "main"],
    env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    capture_output=True, text=True
)
```

**Key Points:**
- Use `GIT_TERMINAL_PROMPT=0` in env to suppress interactive prompt fallback
- Always verify token length: 40 chars for GitHub personal access tokens
- If `git config credential.helper` returns store path, check the file — tokens can be truncated on write
- Root repo location (`/.git`) means `git -C /` is needed for all operations
- When pushing from non-standard .git locations, always specify `-C /path/to/repo`

---

### Repo Cleanup Pattern (git rm --cached)

**Problem:** Repo is bloated with binary cache, runtime artifacts, or legacy files that should not be committed. Files must be removed from git tracking BUT kept on disk (Hermes needs them to run).

**When to Use:**
- Repo has Chrome browser cache committed (`.browser_profile/`)
- Legacy migration folders committed (e.g. `hermes_profile_ilma/docs/`, `hermes_profile_ilma/scripts/`)
- UUID artifact files committed (e.g. `artifacts/application/json/*.txt`)
- Archive/garbage files committed (e.g. `archive/garbage/`)
- Any file that should never have been committed but was

**Critical Rule:** Use `git rm --cached` (NOT `git rm`). `--cached` removes from git tracking but leaves the file on disk. Without `--cached`, Hermes runtime breaks.

**Step-by-Step:**

```
# 1. Backup .gitignore first
cp .gitignore .gitignore.backup_$(date +%Y%m%d_%H%M%S)

# 2. Identify what to remove (count files first)
git ls-files | grep -E '\.browser_profile/|archive/garbage/|artifacts/application/|hermes_profile_ilma/docs/|hermes_profile_ilma/scripts/' | wc -l

# 3. Remove each category from git tracking (--cached = keep on disk)
git rm -r --cached .browser_profile/
git rm -r --cached archive/garbage/
git rm -r --cached artifacts/application/
git rm -r --cached hermes_profile_ilma/docs/
git rm -r --cached hermes_profile_ilma/scripts/

# 4. Update .gitignore — rewrite with complete runtime exclusions
# Include: .browser_profile/, archive/, artifacts/, evidence/, sessions/, 
# backups/, hermes_profile_ilma/ runtime state files, .benchmark/, .deprecated/,
# .meta_cognition_state.json, etc.

# 5. Stage changes
git add .gitignore
git add -A  # or stage individual modified files

# 6. Commit with descriptive message including impact metrics
git commit -m "CLEANUP: Remove binary cache, obsolete archives, phase reports

Impact:
- Remove .browser_profile/ (Chrome cache - 736 files, ~50MB binary)
- Remove archive/garbage/ (obsolete debug scripts)
- Remove artifacts/application/json/ (UUID artifact files)
- Remove hermes_profile_ilma/docs/ (internal phase reports)
- Remove hermes_profile_ilma/scripts/ (legacy migration scripts)
- Fix .gitignore: add all runtime exclusion paths

Source code stays tracked. Reference docs stay tracked.

Bos: Huda Choirul Anam
ILMA-EVID-YYYYMMDD-REPO-CLEANUP-NNN"

# 7. Push
git push origin <branch>

# 8. Verify
git log -1 --oneline
git status --short
git ls-files | wc -l  # should be significantly reduced
```

**Verification Checklist:**
```
Total tracked files before cleanup: ~7,700
Total tracked files after cleanup: ~5,000-6,000
Expected deletion count: 2,000+ files
Push status: success (no 502/timeout)
```

**Pitfalls:**
- ❌ `git rm` (without `--cached`) → file DELETED from disk, Hermes breaks
- ❌ Commented-out paths in .gitignore → `.browser_profile/` was commented out, caused Chrome cache to be committed
- ❌ `git add .` before updating .gitignore → untracked garbage files enter staging
- ✅ Always `git add .gitignore` explicitly before commit
- ✅ Rewrite .gitignore completely for complex cleanups — don't try to patch line-by-line

> **References:** `references/repo-cleanup-pattern.md` — comprehensive session transcript: file counts per category (736 Chrome cache, 75 archive/garbage, 833 phase reports, etc.), full .gitignore PHASE 72 CLEANUP section, two-phase workflow (Phase A: `git rm --cached` for tracked files, Phase B: direct delete + `.gitignore` update for untracked), index.lock error fix, and verification commands. Applied to `lokah1945/ilma-core` (`b2e08c3` + `839127b`, removed 2,164 files, repo reduced from ~7,700 → 5,536 tracked files).

---

## Git index.lock Error

**Symptom:**
```
fatal: Tidak dapat membuat '/path/to/repo/.git/index.lock': Berkas telah ada.
```

**Fix:**
```bash
rm -f /path/to/repo/.git/index.lock
git add .
git commit ...
```

**Root cause:** Prior git process crashed or was interrupted. Lock file persists until manually removed.

---

## Sensitive Files — Never Track in Any Repo

These patterns MUST be in `.gitignore` for any ILMA profile repo:

| Pattern | Why |
|---------|-----|
| `whatsapp/session/*` | WhatsApp session keys, device credentials |
| `scripts/.codex_oauth_*` | CodeX OAuth tokens |
| `scripts/.codex_pkce_*` | CodeX PKCE verifier state |
| `scripts/codex_cookies.json` | Browser cookies for CodeX auth |
| `scripts/.chatgpt_session.json` | ChatGPT session tokens |
| `scripts/.oauth_state.json` | Generic OAuth state |
| `.env`, `*.env` | Environment variables with API keys |
| `auth.json` | Credentials store |
| `config.yaml` | Runtime config (may contain API keys) |

**Rule:** If a file contains a token, key, cookie, or credential → it MUST be in `.gitignore`. The cost of leaking one OAuth token outweighs any benefit from tracking the file.

---

## Quality Standards
- Minimum SKILL.md size: 600 bytes
- Must have clear trigger conditions
- Must have actionable content
- Must integrate with ILMA ecosystem
