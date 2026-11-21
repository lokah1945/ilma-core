# Storage Cleanup Patterns — Ponytail Full Mode

## Quick Reference: High-Impact Cleanup Targets

### 1. ILMA Model Router Backups (5.4G → 0)
```bash
rm -rf /root/.hermes/profiles/ilma/ilma_model_router_data/backups/*
```
- Cron runs 4×/day (00:00, 05:00, 09:00, 12:00 WIB)
- Keep only last 7 days if retention needed
- Backups regenerate from live APIs on next sync

### 2. ILMA Logs (3.3G → 35M)
```bash
cd /root/.hermes/profiles/ilma/logs
rm -f *.log.*.gz errors.log.2 gateway.log.2 gateway.log.3 sot_sync_daemon.log two_way_sync.log
```
- Keep: current + 3 rotated (.1, .2, .3)
- Drop: old `.gz` archives, deprecated daemon logs

### 3. Playwright Chromium Caches (Profile: 1.3G → 223M | System: 899M → 641M)
```bash
# Profile cache
rm -rf /root/.hermes/profiles/ilma/home/.cache/ms-playwright/chromium-1208
rm -rf /root/.hermes/profiles/ilma/home/.cache/ms-playwright/chromium-1217
rm -rf /root/.hermes/profiles/ilma/home/.cache/ms-playwright/chromium_headless_shell-1208
rm -rf /root/.hermes/profiles/ilma/home/.cache/ms-playwright/chromium_headless_shell-1217
rm -rf /root/.hermes/profiles/ilma/home/.cache/ms-playwright/ffmpeg-1011

# System cache
rm -rf /root/.cache/ms-playwright/chromium-1208
rm -rf /root/.cache/ms-playwright/chromium_headless_shell-1208
rm -rf /root/.cache/ms-playwright/ffmpeg-1011
```
- Keep only version used by active service (check `systemctl --user status ilma-chrome.service`)
- Current: chromium_headless_shell-1228 (system), chromium-1217 (profile)

### 4. State Snapshots (496M → 0)
```bash
rm -rf /root/.hermes/profiles/ilma/state-snapshots/20260629-132048-pre-update
```
- Single old snapshot from June — safe to delete unless rollback needed

### 5. Global Package Caches
```bash
npm cache clean --force
pip cache purge
uv cache clean
pnpm store prune
```

### 6. OpenCode History (1.1G → ~40K)
```bash
rm -rf /root/.local/share/opencode/snapshot/*
rm -rf /root/.local/share/opencode/tool-output/*
rm -rf /root/.local/share/opencode/log/*
```
- Keep: `opencode.db` (main session DB, 1.1G) — NOT cache

## Pre-Delete Safety Checks

```bash
# 1. Check for open file handles
lsof /path/to/target 2>/dev/null

# 2. Check active services using the path
systemctl --user status ilma-chrome.service hermes-playwright-cdp.service

# 3. Verify current chromium version in use
ps aux | grep chrome-headless
```

## Disk Usage Audit Commands

```bash
# Top consumers at root
du -h /root --max-depth=2 2>/dev/null | sort -hr | head -30

# ILMA profile detail
du -h /root/.hermes/profiles/ilma --max-depth=2 2>/dev/null | sort -hr | head -20

# Logs detail
du -h /root/.hermes/profiles/ilma/logs --max-depth=1 2>/dev/null | sort -hr

# Cache detail
du -h /root/.cache --max-depth=2 2>/dev/null | sort -hr | head -20
```

## Risk Notes
- `opencode.db` (1.1G) = SQLite with session data — do NOT delete. Can vacuum if fragmented: `sqlite3 opencode.db "VACUUM;"`
- Browser service uses `/root/.cache/ms-playwright/chromium_headless_shell-1228` — keep this version
- `agent-enhancements` = external read-only skills repo at `/root/project/AgentEnhancements` — prune `node_modules`/`target` if not developing there
- `wrapper`, `project`, `llama.cpp`, `.rustup`, `.bun`, `.codex` = working infrastructure — skip

## Session Outcome (2026-11-13)
- **Freed:** ~17GB (60G → 43G)
- **Preserved:** `/root/.hermes/profiles/ilma/.git`, `/root/project/AgentEnhancements`
- **Disk after:** 84% used (20G free on 124G)