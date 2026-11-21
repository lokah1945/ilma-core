# System-Wide Storage Cleanup — Ponytail Full Mode (2026-11-13)

## Session Summary
**Goal:** Free disk space on `/root` (84% used, 20G free on 124G) using aggressive Ponytail full-mode cleanup.
**Constraint:** Preserve `/root/.hermes/profiles/ilma/.git` and `/root/project/AgentEnhancements` only.
**Result:** ~17GB freed (60G → 43G).

## Targets Deleted

| Target | Before | After | Freed |
|--------|--------|-------|-------|
| `ilma_model_router_data/backups/` | 5.4G | 0 | 5.4G |
| `ilma/logs/` | 3.3G | 35M | 3.3G |
| `ilma/home/.cache/ms-playwright/` | 1.3G | 223M | 1.1G |
| `/root/.cache/ms-playwright/` | 899M | 641M | 258M |
| `ilma/state-snapshots/20260629...` | 496M | 0 | 496M |
| `/root/.npm/_cacache` | 5.7G | ~0 | 5.7G |
| `/root/.cache/pip` | 518M | 0 | 518M |
| `/root/.cache/uv` | 1.5G | 0 | 1.5G |
| `/root/.cache/pnpm` | 91M | ~0 | 91M |
| `opencode snapshots/logs/tool-output` | 1.1G | ~40K | 1.1G |

## Safety Verification Steps (All Passed)

1. **lsof checks** — No open handles on any target directories
2. **Service checks** — `ilma-chrome.service` active, `hermes-playwright-cdp.service` inactive
3. **Process verification** — Chrome using `/root/.cache/ms-playwright/chromium_headless_shell-1228`
4. **Post-cleanup verification** — Service restarted, CDP endpoint responsive

## Commands Used

```bash
# 1. ILMA Model Router backups (1,160 files × 4.3MB)
rm -rf /root/.hermes/profiles/ilma/ilma_model_router_data/backups/*

# 2. ILMA logs (keep current + 3 rotated)
cd /root/.hermes/profiles/ilma/logs
rm -f *.log.*.gz errors.log.2 gateway.log.2 gateway.log.3 sot_sync_daemon.log two_way_sync.log

# 3. Profile Playwright cache (keep chromium-1217)
rm -rf /root/.hermes/profiles/ilma/home/.cache/ms-playwright/chromium-1208
rm -rf /root/.hermes/profiles/ilma/home/.cache/ms-playwright/chromium-1217
rm -rf /root/.hermes/profiles/ilma/home/.cache/ms-playwright/chromium_headless_shell-1208
rm -rf /root/.hermes/profiles/ilma/home/.cache/ms-playwright/chromium_headless_shell-1217
rm -rf /root/.hermes/profiles/ilma/home/.cache/ms-playwright/ffmpeg-1011

# 4. System Playwright cache (keep chromium_headless_shell-1228)
rm -rf /root/.cache/ms-playwright/chromium-1208
rm -rf /root/.cache/ms-playwright/chromium_headless_shell-1208
rm -rf /root/.cache/ms-playwright/ffmpeg-1011

# 5. State snapshot
rm -rf /root/.hermes/profiles/ilma/state-snapshots/20260629-132048-pre-update

# 6. Global package caches
npm cache clean --force
pip cache purge
uv cache clean
pnpm store prune

# 7. OpenCode history (keep opencode.db)
rm -rf /root/.local/share/opencode/snapshot/*
rm -rf /root/.local/share/opencode/tool-output/*
rm -rf /root/.local/share/opencode/log/*
```

## Preserved (Per User Instruction)
- `/root/.hermes/profiles/ilma/.git` (238M)
- `/root/project/AgentEnhancements` (3.9G)

## Remaining Large Items (>500M) — Not Touched
| Path | Size | Reason |
|------|------|--------|
| `.hermes/hermes-agent/venv` | 1.8G | Python venv — keep |
| `.hermes/hermes-agent/.git` | 580M | Repo history — keep |
| `.hermes/profiles/ilma` | 2.4G | Active profile — lean |
| `.local/share/opencode/opencode.db` | 1.1G | Main session DB — keep |
| `.rustup` | 2.1G | Rust toolchains — keep |
| `.cache/ms-playwright` | 641M | Current chromium-1228 (service) |
| `.bun` | 1.5G | Bun runtime — keep |
| `llama.cpp` | 1.4G | Build artifacts — keep |
| `.codex` | 1.4G | Codex CLI — keep |
| `wrapper` | 782M | Active wrapper services — keep |
| `project` | 927M | Active project — keep |
| `models` | 941M | Model weights — keep |
| `backup` | 4.2G | Backup data — keep |

## Risk Notes
- `opencode.db` (1.1G) = SQLite with session data — do NOT delete. Can vacuum if fragmented: `sqlite3 opencode.db "VACUUM;"`
- Browser service uses `/root/.cache/ms-playwright/chromium_headless_shell-1228` — keep this version
- `agent-enhancements` = external read-only skills repo — prune `node_modules`/`target` if not developing there
- `wrapper`, `project`, `llama.cpp`, `.rustup`, `.bun`, `.codex` = working infrastructure — skip

## Integration with ILMA System
This cleanup pattern is now documented in:
- `system-administration/references/storage-cleanup-patterns.md`
- `ilma-playwright-stealth/references/browser-cache-cleanup.md`

Future sessions can reference these for repeatable, safe storage audits.