---
name: ilma-checkpoints-rollback
description: Hermes Checkpoints v2 — shadow git repos for filesystem safety, automatic snapshots, /rollback command with diff preview, configurable retention. SSS Tier.
version: 1.0.0
category: core
platforms:
  - linux
  - macos
metadata:
  hermes:
    tags: [checkpoints, rollback, git, filesystem, safety, snapshot]
    category: core
---

# ILMA Checkpoints & Rollback — Filesystem Safety

## Overview

Hermes Checkpoints creates shadow git repos alongside real files, automatically committing on detected changes. Enables safe rollback to any previous state without losing work.

```
~/.hermes/checkpoints/
├── <profile_name>/
│   └── .git/
└── ...
~/.hermes/checkpoints/<profile_name>/
```

The shadow repo mirrors the real directory structure. On every checkpoint, Hermes commits the current state.

---

## Configuration

```yaml
# ~/.hermes/config.yaml
checkpoints:
  enabled: true                    # Enable checkpoints
  max_checkpoints: 5              # Max checkpoints per profile (default: 5, 0 = unlimited)
  auto_checkpoint: true            # Auto-checkpoint on file changes
  retention_days: 30              # Auto-delete checkpoints older than N days
  commit_message: "checkpoint"     # Default commit message
  exclude_patterns:               # Patterns to never checkpoint
    - "*.log"
    - "node_modules/**"
    - "__pycache__/**"
    - ".git/**"
    - "*.pyc"
    - ".venv/**"
    - "venv/**"
    - ".env"
```

### Environment Variable Override

```bash
HERMES_CHECKPOINTS_ENABLED=0    # Disable entirely
HERMES_CHECKPOINTS_MAX=10       # Override max
```

---

## How It Works

### 1. Shadow Git Repo

For each profile, Hermes maintains a shadow git repo at:
```
~/.hermes/checkpoints/<profile_name>/
```

Files in the profile directory are **hard-linked** (not copied) to the shadow repo. This means:
- Minimal disk overhead (only metadata changes)
- Fast checkpointing (no file copying)
- Real files and checkpoint files are identical

### 2. Automatic Checkpointing

Hermes detects changes to tracked files and auto-commits:
- File modified → auto-commit with timestamp
- File created/deleted → tracked in git
- Batch changes (multiple files) → single commit

### 3. On-Demand Checkpoint

```bash
hermes checkpoint "before refactoring auth module"
```

Manual checkpoint before risky operations.

---

## Rollback Command

### Basic Usage

```bash
hermes rollback              # Interactive: pick checkpoint to restore
hermes rollback --list      # Show available checkpoints
hermes rollback HEAD~1      # Restore to previous checkpoint
hermes rollback abc1234     # Restore to specific commit
```

### With Diff Preview

```bash
# Preview what will change before rolling back
hermes rollback --diff HEAD~2

# Show files that will change
hermes rollback --diff --stat HEAD~1
```

### Restore Options

```bash
# Restore files (don't commit the restore)
hermes rollback --no-commit HEAD~1

# Restore and auto-commit with message
hermes rollback --message "rolled back to before auth refactor" HEAD~2

# Dry run (show what would happen)
hermes rollback --dry-run HEAD~1
```

---

## Checkpoint Listing

```bash
# List all checkpoints for current profile
hermes checkpoint --list

# Show detailed info
hermes checkpoint --list --verbose

# Filter by date
hermes checkpoint --list --since "2026-01-01"
hermes checkpoint --list --older-than 7d

# Show checkpoint contents
hermes checkpoint show abc1234
```

---

## Automatic Pruning

- **Max checkpoints:** When `--max_checkpoints` reached, oldest non-pinned checkpoint is pruned
- **Retention days:** Checkpoints older than `--retention_days` auto-deleted
- **Orphan cleanup:** Dangling files in shadow repo that no longer exist in main repo are removed

```bash
# Manual prune
hermes checkpoint --prune

# Prune all except last N
hermes checkpoint --prune --keep 3

# Show what would be pruned
hermes checkpoint --prune --dry-run
```

---

## Integration with ILMA Workflow

### Before Risky Operations

```
User: "ILMA, refactor the authentication module"
ILMA:
  1. hermes checkpoint "before auth refactor"
  2. Make changes
  3. Test
  4. If failed: hermes rollback HEAD~1
```

### Rollback Workflow in ILMA

```
User: "Something broke after my last changes. Roll back."
ILMA:
  1. hermes rollback --list
  2. hermes rollback --diff HEAD~1 (show what changed)
  3. hermes rollback --no-commit HEAD~1
  4. Verify files restored
  5. Report to user
```

### CI/CD Integration

```bash
# In CI pipeline
before_script:
  - hermes checkpoint "ci-build-$BUILD_NUMBER"

after_script:
  - hermes rollback HEAD~1  # On failure
```

---

## Git Snapshot Mode

For projects already using git, checkpoints can use the project's own git:

```yaml
checkpoints:
  mode: git          # Use project's .git instead of shadow repo
  auto_commit: true   # Auto-commit on changes
```

This avoids duplicate git repos while still providing checkpoint history.

---

## Safety Features

1. **Non-destructive restore:** Rollback modifies files in-place, but original commit preserved in git history
2. **Commit-before-restore:** Default behavior commits current state before restoring (prevents data loss)
3. **Hard links:** Zero disk overhead for storing checkpoint copies
4. **Configurable retention:** Balance between history depth and disk usage
5. **Exclude patterns:** Never checkpoint temp files, logs, caches, secrets

---

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| No checkpoints exist | Warning message, no action |
| Rollback to deleted commit | Error with list of valid commits |
| Disk full during checkpoint | Error logged, current operation continues |
| Large files in checkpoint | Warning if single file > 100MB |
| Shadow repo corruption | Rebuild from current state, warning displayed |

---

## Auto-Trigger

Load this skill when:
- User mentions "rollback", "restore", "checkpoint", "snapshots"
- User asks to "go back to previous version", "undo all changes"
- User wants "filesystem safety", "version control for workspace"
- Before any risky file operation (refactor, bulk delete, config change)

---

*Hermes v0.13.0 — Checkpoints v2 feature*
*Integrated into ILMA v3.3*