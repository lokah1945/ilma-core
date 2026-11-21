# MCP Server Catalog — Full 38-Server List

Source: `/root/project/AgentEnhancements/plugin-catalog/mcp-servers.json`
Generated: 2026-11-14

---

## Built In-House (9 servers)

| ID | Priority | Category | For Plugins | Status | Implementation |
|----|----------|----------|-------------|--------|----------------|
| embeddings-mcp | P1 | ml | graphify, understand-anything, agent-reach | built | unified-integration/mcp-servers/embeddings-mcp/server.py |
| task-router-mcp | P1 | task | gsd, bmad-method, rea | built | unified-integration/mcp-servers/task-router-mcp/server.py |
| ffmpeg-mcp | P1 | media | openmontage | built | unified-integration/mcp-servers/ffmpeg-mcp/server.py |
| vision-mcp | P1 | core | anthropic-skills, impeccable, replica-skill | built | unified-integration/mcp-servers/vision-mcp/server.py |
| graphrag-mcp | P2 | graph | graphify, agent-reach | built | unified-integration/mcp-servers/graphrag-mcp/server.py |
| arxiv-mcp | P2 | reference | understand-anything, agent-reach | built | unified-integration/mcp-servers/arxiv-mcp/server.py |
| google-news-mcp | P2 | news | last-30-days | built | unified-integration/mcp-servers/google-news-mcp/server.py |
| video-mcp | P2 | media | openmontage, hyperframes | built | unified-integration/mcp-servers/video-mcp/server.py |
| style-mcp | P2 | writing | humanizer | built | unified-integration/mcp-servers/style-mcp/server.py |

---

## To-Install Upstream (29 servers)

### P0 — Required Before Phase 1

| ID | Category | For Plugins | Command | Env Required |
|----|----------|-------------|---------|--------------|
| brave-search-mcp | search | agent-reach, last-30-days, rea, understand-anything | npx -y @modelcontextprotocol/server-brave-search | BRAVE_API_KEY |
| tavily-mcp | search | agent-reach, rea | npx -y tavily-mcp | TAVILY_API_KEY |
| browser-tools-mcp | browser | agent-skills-addyosmani, impeccable, ui-ux-pro-max, replica-skill | npx -y @agent-infra/browser-tools-mcp | — |
| memory-mcp | memory | bmad-method, gsd, rea, anthropic-skills | npx -y @modelcontextprotocol/server-memory | — |
| filesystem-mcp | core | anthropic-skills, all | npx -y @modelcontextprotocol/server-filesystem | — |

### P1 — Phase 2 (Enables Full Plugins)

| ID | Category | For Plugins | Command | Env Required |
|----|----------|-------------|---------|--------------|
| exa-mcp | search | agent-reach, last-30-days | npx -y exa-mcp-server | EXA_API_KEY |
| firecrawl-mcp | search | agent-reach, graphify | npx -y firecrawl-mcp | FIRECRAWL_API_KEY |
| neo4j-mcp | graph | graphify | npx -y neo4j-mcp-server | NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD |
| lighthouse-mcp | browser | agent-skills-addyosmani | npx -y lighthouse-mcp | — |
| pa11y-mcp | browser | agent-skills-addyosmani, ui-ux-pro-max | npx -y pa11y-mcp | — |
| figma-mcp | design | ui-ux-pro-max, impeccable | npx -y figma-mcp-server | FIGMA_TOKEN |
| mermaid-mcp | diagram | diagram-design | npx -y mermaid-mcp | — |
| google-slides-mcp | office | ppt-master | npx -y google-slides-mcp | GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET |
| office-mcp | office | ppt-master | npx -y office-mcp | MICROSOFT_CLIENT_ID, MICROSOFT_CLIENT_SECRET |
| image-search-mcp | media | ppt-master, diagram-design | npx -y image-search-mcp | BING_IMAGE_API_KEY |
| heygen-mcp | media | hyperframes | npx -y heygen-mcp | HEYGEN_API_KEY |
| elevenlabs-mcp | media | hyperframes, openmontage | npx -y elevenlabs-mcp | ELEVENLABS_API_KEY |
| typescript-language-server-mcp | code | mattpocock-skills, agent-skills-addyosmani | npx -y typescript-language-server-mcp | — |
| eslint-mcp | code | mattpocock-skills, agent-skills-addyosmani | npx -y eslint-mcp | — |
| jupyter-mcp | data | karpathy-skills | python -m jupyter_mcp | — |
| python-repl-mcp | data | karpathy-skills | python -m python_repl_mcp | — |
| github-issues-mcp | task | bmad-method, gsd | npx -y github-issues-mcp | GITHUB_TOKEN |
| pdf-mcp | core | anthropic-skills, ppt-master | npx -y pdf-mcp | — |

### P2 — Nice-to-Have (Phase 3+ / Backup)

| ID | Category | For Plugins | Command | Env Required |
|----|----------|-------------|---------|--------------|
| linear-mcp | task | bmad-method | npx -y linear-mcp | LINEAR_API_KEY |
| wikipedia-mcp | reference | understand-anything | npx -y wikipedia-mcp | — |
| newsapi-mcp | news | last-30-days | npx -y newsapi-mcp | NEWSAPI_KEY |
| storybook-mcp | design | ui-ux-pro-max, impeccable | npx -y storybook-mcp | — |
| excalidraw-mcp | diagram | diagram-design | npx -y excalidraw-mcp | — |
| grammar-mcp | writing | humanizer | npx -y grammar-mcp | LANGUAGE_TOOL_URL |

---

## Legend

- **to-install** — upstream package exists; install via npx/pip + env vars
- **to-build** — no upstream package; must be implemented in-house
- **built** — implemented in-house at `unified-integration/mcp-servers/<id>/` (server.py + tests + installer)
- **installed** — deployed in the user environment (flipped after setup)
- **P0** — Wajib sebelum Phase 1 (skills basic tidak jalan tanpa ini)
- **P1** — Phase 2 (mengaktifkan plugin utuh)
- **P2** — Nice-to-have (Phase 3+ / cadangan)