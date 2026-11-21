---
name: system-administration
description: System Administration - Military grade skill for ILMA. Covers storage cleanup, service management, disk auditing, and infrastructure maintenance.
category: system-administration
version: 2.0
last_updated: 2026-11-13
tags:
  - storage-cleanup
  - disk-audit
  - service-management
  - infrastructure
---

# System Administration

## Purpose
System Administration - Military grade skill for ILMA. Covers storage cleanup, service management, disk auditing, and infrastructure maintenance.

## Triggers
- "system-administration"
- "disk cleanup"
- "storage audit"
- "free up space"
- "ponytail"

## Status
Military Grade: Active
Last Updated: 2026-11-13

## Implementation
See associated Python modules in this directory.

## References
- `references/storage-cleanup-patterns.md` — Ponytail full-mode storage cleanup patterns (17GB freed in one session)
- `references/system-storage-cleanup-20261113.md` — Detailed session log with all commands, safety checks, and preserved targets

## Quality Standards
- Error handling: ✓
- Input validation: ✓
- Performance optimized: ✓
- Security audited: ✓

## Quick Commands

### Disk Audit
```bash
du -h /root --max-depth=2 2>/dev/null | sort -hr | head -30
du -h /root/.hermes/profiles/ilma --max-depth=2 2>/dev/null | sort -hr | head -20
```

### Pre-Delete Safety
```bash
lsof /path/to/target 2>/dev/null
systemctl --user status ilma-chrome.service hermes-playwright-cdp.service
ps aux | grep chrome-headless
```