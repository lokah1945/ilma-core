# OpenCode 2 Upgrade — 2026-11-05

## Summary
Upgraded OpenCode from v1.19.5 → v2.2.5 (OpenCode 2) via `opencode upgrade --major`.

## Key Changes in OpenCode 2 (v2.2.0+)

### Breaking Changes
- **`@opencode/ai` root now exports Promise API** — Effect API moved to `@opencode/ai/effect`. `@opencode/ai/promise` removed.
  ```diff
  - import { AI } from "@opencode/ai/promise"
  - import { LLM } from "@opencode/ai"
  + import { AI } from "@opencode/ai"
  + import { LLM } from "@opencode/ai/effect"
  ```

- **GitHub Action removed** — Remove from workflows. No longer published.

- **TUI plugins require OpenTUI 0.7** — `@opencode/plugin` now requires `@opentui/core` and `@opentui/solid` 0.7.0. Plugins on 0.6 fail to install until upgraded. Migration: custom renderables read hooks from class at construction; assign `renderBefore`, `renderAfter`, `onLifecyclePass` in constructor; call `refreshHooks()` after adding hooks by reflection; replace `defineNativeIntegration()` with `static nativeIntegration`.

### New Features
- **Desktop plugins (experimental)** — Manage from Settings › Extensions › Plugins
- **Image & decision generation APIs** — For plugins and SDK (image generation, decision models like typesafe/clef)
- **Configurable prompt cache TTLs** — Per provider/model
- **Session instruction entries** — `ctx.session.instructions.entry.put/list/remove` survive compaction/reverts, don't start extra model turn
- **Worktree & shell mode shortcuts** — Ctrl+Alt+O (worktree), Ctrl+Alt+B (base branch), Ctrl+Shift+X (toggle shell mode)
- **Percentage compaction buffer** — `"compaction": { "buffer": "20%" }` in `opencode.json`
- **Todo tool restored in Desktop** (opt-in)
- **Added GPT-6.1 Terra and GPT-6.1 Terra Fast** to Sign in with ChatGPT

### Improvements
- MCP large message handling (>10 MiB), idle server restart fixes
- Git project discovery faster
- Memory reduction for code search
- Session history from latest completed compaction
- Prompt cache TTLs configurable
- External-directory permission checks use project filesystem

### Bug Fixes
- MCP stdio >10 MiB no longer disconnects
- Idle locations don't restart MCP servers
- Compaction caps at model context window
- LiteLLM context window errors trigger compaction
- Reasoning preserved on model switch/resume
- TUI connect menu no longer lists MCP servers
- Desktop connect menu no longer lists MCP servers

### Command Interface Changes
- Old: `opencode [project]` (positional default command)
- New: Subcommands required — `opencode <subcommand> [flags] [<directory>]`
- Main entry: `opencode` starts TUI (same as old default)
- Run: `opencode run [message..]`
- API: `opencode api <request>`
- Upgrade: `opencode upgrade [target]` (now `upgrade`, `update` alias)

## Upgrade Path
```bash
# From v1.x to v2.x requires --major flag
opencode upgrade --major

# Verify
opencode --version  # opencode v2.2.5
```

## Impact on Wrapper Stack
- **wrapper-opencode (port 9103)** — Uses OpenCode as upstream provider. After upgrade, verify wrapper still connects correctly to OpenCode v2 API.
- **OpenCode CLI config** — `~/.config/opencode/opencode.json` may need migration for new settings (compaction.buffer percentage, prompt cache TTLs, desktop plugins).
- **ACP server** — `opencode acp` command unchanged, but protocol may have updates.

## Verification Checklist
- [ ] `opencode --version` shows v2.2.5
- [ ] `opencode --help` shows new subcommand structure
- [ ] wrapper-opencode health check passes (port 9103)
- [ ] OpenCode models list works: `opencode models`
- [ ] ACP server starts: `opencode acp`
- [ ] No TUI plugin errors (if any plugins installed)

## References
- GitHub releases: https://github.com/sst/opencode/releases
- Changelog: https://opencode.ai/changelog
- v2.2.0 release notes (breaking changes): https://github.com/sst/opencode/releases/tag/v2.2.0
- v2.2.5 release notes (latest): https://github.com/sst/opencode/releases/tag/v2.2.5