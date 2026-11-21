---
slug: mcp
name: mcp
description: Manage, discover, and wire Model Context Protocol (MCP) servers for agent tooling
category: devops
version: 2.0.0
status: active
mcp_servers: []
trigger_keywords:
  - "mcp"
  - "mcp server"
  - "setup mcp"
  - "mcp catalog"
  - "model context protocol"
  - "mcp wiring"
---

# Mcp

## Purpose
Mcp - Military grade skill for ILMA. Manage, discover, and wire Model Context Protocol (MCP) servers for agent tooling.

## Triggers
- "mcp"
- "mcp server"
- "setup mcp"
- "mcp catalog"
- "model context protocol"
- "mcp wiring"

## Status
Military Grade: Active
Last Updated: 2026-11-14

## Implementation
See associated Python modules in this directory.

## Quality Standards
- Error handling: ✓
- Input validation: ✓
- Performance optimized: ✓
- Security audited: ✓

---

## MCP Server Catalog (AgentEnhancements Source)

**Master catalog:** `/root/project/AgentEnhancements/plugin-catalog/mcp-servers.json` (38 servers total)

### 9 Built In-House Servers (`unified-integration/mcp-servers/`)
All use stdio transport, FastMCP SDK, schema'd tools, health probe, actionable error envelopes.

| Server | Priority | Category | Status | Feeds Plugins | Repo Path |
|--------|----------|----------|--------|---------------|-----------|
| `embeddings-mcp` | P1 | ml | **built** | graphify, understand-anything, agent-reach | `unified-integration/mcp-servers/embeddings-mcp/server.py` |
| `task-router-mcp` | P1 | task | **built** | gsd, bmad-method, rea | `unified-integration/mcp-servers/task-router-mcp/server.py` |
| `ffmpeg-mcp` | P1 | media | **built** | openmontage | `unified-integration/mcp-servers/ffmpeg-mcp/server.py` |
| `vision-mcp` | P1 | core | **built** | anthropic-skills, impeccable, replica-skill | `unified-integration/mcp-servers/vision-mcp/server.py` |
| `graphrag-mcp` | P2 | graph | **built** | graphify, agent-reach | `unified-integration/mcp-servers/graphrag-mcp/server.py` |
| `arxiv-mcp` | P2 | reference | **built** | understand-anything, agent-reach | `unified-integration/mcp-servers/arxiv-mcp/server.py` |
| `google-news-mcp` | P2 | news | **built** | last-30-days | `unified-integration/mcp-servers/google-news-mcp/server.py` |
| `video-mcp` | P2 | media | **built** | openmontage, hyperframes | `unified-integration/mcp-servers/video-mcp/server.py` |
| `style-mcp` | P2 | writing | **built** | humanizer | `unified-integration/mcp-servers/style-mcp/server.py` |

### 29 To-Install Upstream Servers
Require `npx`/`pip` install + API keys. Examples:
- `brave-search-mcp` (P0, search) — BRAVE_API_KEY
- `tavily-mcp` (P0, search) — TAVILY_API_KEY
- `filesystem-mcp` (P0, core) — no key
- `memory-mcp` (P0, memory) — no key
- `firecrawl-mcp` (P1, search) — FIRECRAWL_API_KEY
- `neo4j-mcp` (P1, graph) — NEO4J_URI/USER/PASSWORD
- `heygen-mcp` (P1, media) — HEYGEN_API_KEY (consent gate required)
- `elevenlabs-mcp` (P1, media) — ELEVENLABS_API_KEY (consent gate required)
- `typescript-language-server-mcp` (P1, code)
- `github-issues-mcp` (P1, task) — GITHUB_TOKEN
- `mermaid-mcp` (P1, diagram)
- `figma-mcp` (P1, design) — FIGMA_TOKEN

Full list in `plugin-catalog/mcp-servers.json`.

---

## Setup & Wiring

### Install All Built Servers
```bash
bash /root/project/AgentEnhancements/unified-integration/scripts/setup-mcp.sh
```
Generates `mcp.json` blocks for: Claude Code, Cursor, Continue, Windsurf, Codex, generic `~/.agents/mcp.json`.

### Health Check
```bash
bash /root/project/AgentEnhancements/unified-integration/scripts/setup-mcp.sh --check
```

### Smoke Test (manual)
```bash
python3 /root/project/AgentEnhancements/unified-integration/mcp-servers/smoke_test.py
```

### Run Individual Server (stdio)
```bash
python3 /root/project/AgentEnhancements/unified-integration/mcp-servers/<slug>/server.py
```

### Template Config
`/root/project/AgentEnhancements/unified-integration/mcp-servers/mcp.json.example` — placeholder `PLACEHOLDER_REPO_ROOT` replaced by setup script.

---

## Pitfalls & Gotchas

1. **Upstream servers NOT installed by setup script** — the 29 `to-install` servers need API keys and per-user consent. Follow `docs/MCP_INTEGRATION_CHECKLIST.md` Phase 1/2.

2. **Secrets handling** — keys read from env at call time; `health()` only reports boolean availability, never exposes keys.

3. **Binary dependencies** — `ffmpeg-mcp` and `video-mcp` require `ffmpeg` binary in PATH.

4. **OPENAI_API_KEY** needed for `embeddings-mcp` (OpenAI backend), `vision-mcp`, `graphrag-mcp` (optional LLM extractor layer).

5. **Port conflicts** — stdio transport means no port conflicts, but multiple agent CLIs wiring the same server will spawn separate processes (acceptable).

6. **Test coverage** — `unified-integration/tests/run-tests.py` includes `test_mcp_servers.py`.

---

## Reference Files
- `references/mcp-server-catalog.md` — Full catalog with all 38 servers
- `references/mcp-setup-checklist.md` — Setup steps and verification