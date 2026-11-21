# Agency Agents (msitarzewski/agency-agents) — multi-CLI install, session 2026-11-02

## What was asked
Bos: "Cek /root/agency-agent — apakah berfungsi di mesin ini dan Claude code, codex, dan agent lain bisa menggunakannya."

## Discovery
- `/root/agency-agent` does NOT exist. The repo is `/root/agency-agents` (git clone of github.com/msitarzewski/agency-agents, HEAD 652b269). Always `ls` the exact path first.
- Repo contents: 282 agent .md files across 18 divisions (engineering 65, specialized 59, marketing 37, ...), `tools.json` (per-tool install contract), `divisions.json`, `scripts/convert.sh` + `scripts/install.sh`.
- `integrations/<tool>/` ships with ONLY a README.md — conversion output is NOT pre-generated. Must run convert.sh first.

## Commands actually run (verified working)
```bash
cd /root/agency-agents
bash scripts/convert.sh --tool codex                          # 282 agents -> integrations/codex/agents/*.toml
bash scripts/install.sh --no-interactive --tool codex         # -> /root/.codex/agents/ (282 .toml files)
bash scripts/convert.sh --tool hermes                         # -> integrations/hermes/agency-agents-router/
bash scripts/install.sh --no-interactive --tool hermes        # -> ~/.hermes/profiles/ilma/plugins/agency-agents-router + enabled in that profile's config.yaml
```

## Per-tool status after install (2026-11-02)
| Tool | Binary | Before | After | Destination |
|------|--------|--------|-------|-------------|
| Claude Code 2.1.202 | /root/.local/bin/claude | already had 282 .md (217 agency-prefixed + 65 other) | unchanged, works | ~/.claude/agents/*.md (subagent/Task tool) |
| Codex 0.166.0 | /root/.npm-global/bin/codex | 0 agents | 282 .toml | ~/.codex/agents/*.toml (TUI: /agents) |
| Hermes v0.17.0 (ILMA profile) | /root/.local/bin/hermes | plugin absent | agency-agents-router enabled | ~/.hermes/profiles/ilma/plugins/agency-agents-router + config.yaml plugins.enabled |
| gemini 0.37.1, opencode 1.17.20, qwen 0.19.7, agy 1.3.4 | installed | not installed | not installed | can install with `--tool <name>` |
| openclaw, cursor, aider, windsurf, vibe, dsh | NOT installed | — | — | skip |

## Functional verification results
- Codex TOML parses: `tomllib.load(open('/root/.codex/agents/frontend-developer.toml','rb'))` OK; has `name`, `description`, `developer_instructions` (8953 chars for frontend-developer).
- Hermes plugin: `hermes plugins list` shows `agency-agents-router │ enabled │ 1.0.0`. Exposes 4 tools: `agency_agents_search`, `agency_agents_inspect`, `agency_agents_load`, `agency_agents_delegate`. Index `data/agents.json` = 282 agents. Search test: query "frontend react developer" -> top hit `frontend-developer` score 13.55. **Requires gateway/session restart for tools to appear.**
- Claude Code agents already present and valid (frontmatter name/description/color/emoji/vibe).

## Pitfalls encountered
1. Codex `exec` (non-interactive) has NO `--agent` flag in 0.166 — custom agents are TUI-only via `/agents`; for headless runs inject the TOML `developer_instructions` text into the prompt manually.
2. Hermes plugin installs into the ACTIVE profile dir (~/.hermes/profiles/ilma/), not global ~/.hermes/. Verify with `grep -A10 'plugins:' ~/.hermes/profiles/ilma/config.yaml`.
3. Codex exec against wrapper-nous profile errors on several free models (`unsupported tool type "namespace"` from wrapper, `404 free period ended` for hy3:free) — that is a wrapper-nous issue, NOT an agency-agents issue. Don't record it as an agency-agents limitation.
4. `scripts/convert-outputs.sha256` shipped empty ("no properly formatted checksum lines") — don't rely on it for integrity; verify by file counts instead.
