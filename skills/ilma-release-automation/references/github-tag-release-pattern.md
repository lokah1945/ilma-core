# GitHub Tag-Triggered Release Pattern

## The Problem We Found (2026-11-10)

**Repo**: smahud/uaeg  
**Symptom**: v1.0.0 prep commit exists (`9c26340`), all CI green, but **no v1.0.0 tag pushed** → Release workflow never triggered → Releases page shows v0.4.1 as latest.

## Root Cause

The release workflow (`.github/workflows/release.yml`) triggers **only on tag push**:
```yaml
on:
  push:
    tags:
      - "v*"
```

A prep commit with version bumps, updated docs, and runbook changes is **not enough** — the tag must be created and pushed.

## The Fix (Single Command)

```bash
git tag v1.0.0 9c26340 && git push origin v1.0.0
```

## Verification Steps Before Tagging

1. **Confirm prep commit has all version artifacts**:
   - `pyproject.toml` version = 1.0.0
   - `install.sh` pins `UAEG_RELEASE_VERSION="1.0.0"`
   - `README.md` shows "current release: v1.0.0"
   - Runbook renamed: `RELEASE_v0.4.2_RUNBOOK.md` → `RELEASE_1.0.0_RUNBOOK.md`

2. **Confirm CI passes on the prep commit**:
   ```bash
   git log --oneline --all | grep -i "1.0.0"
   # Should show: a9b3ab3 (CI record), 9c26340 (prep)
   ```

3. **Confirm manifest + signature exist for the version** (if using signed releases):
   - `release/manifests/v1.0.0/uaeg-manifest.json`
   - `release/manifests/v1.0.0/uaeg-manifest.json.sig`
   - If missing: run `python3 release/make_release.py --key <private-key>` locally first

## GitHub API Checks (Headless Verification)

```bash
# Check tags exist on remote
git ls-remote --tags https://github.com/OWNER/REPO.git | grep v1.0.0

# Check releases via API
curl -s "https://api.github.com/repos/OWNER/REPO/releases" | grep tag_name

# Check tag refs via API
curl -s "https://api.github.com/repos/OWNER/REPO/git/refs/tags" | grep v1.0.0
```

## Pitfall: Manifest Generation Required

For uaeg specifically, the release workflow **verifies** a pre-committed signed manifest:
```bash
python3 release/verify_release.py  # runs in CI, must pass
```

The manifest must be pre-generated at `release/manifests/v<version>/` and committed **before** tagging. If not, CI will fail with:
```
::error::release/manifests/v1.0.0/uaeg-manifest.json missing
```

## Debug Checklist

| Check | Command | Expected |
|-------|---------|----------|
| Tag exists locally | `git tag -l "v1.0.0"` | v1.0.0 listed |
| Tag exists remote | `git ls-remote --tags origin | grep v1` | v1.0.0 listed |
| Release workflow triggered | GitHub Actions UI | "Release" workflow run appears |
| Assets published | GitHub Releases page | install.sh, upgrade.sh, uaeg-updater-1.0.0.sh, manifest.json, .sig, .sha256 files |

## When to Use This Pattern

- Any repo using **tag-triggered release workflows** (`on.push.tags`)
- Prep commit exists but release not published
- Need to verify release pipeline health before tagging
- Diagnosing "why isn't my release showing up?"

## Related Files in This Skill

- `references/github-tag-release-pattern.md` (this file)
- `templates/release-verification-checklist.md` (if created)