# MCP Setup Checklist & Verification

Source: `/root/project/AgentEnhancements/unified-integration/scripts/setup-mcp.sh`
Generated: 2026-11-14

---

## Prerequisites

1. **AgentEnhancements repo cloned** at `/root/project/AgentEnhancements`
2. **Python 3.10+** with `mcp` package: `pip install mcp`
3. **Node.js 18+** with `npx` for upstream servers
4. **ffmpeg binary** in PATH (for `ffmpeg-mcp`, `video-mcp`)
5. **API keys** in environment for servers that require them

---

## Step 1: Install Built Servers

```bash
cd /root/project/AgentEnhancements
bash unified-integration/scripts/setup-mcp.sh
```

**What it does:**
- Renders `mcp.json` for each target CLI:
  - Claude Code: `~/.claude/mcp.json`
  - Cursor: `~/.cursor/mcp.json`
  - Continue: `~/.continue/mcp.json`
  - Windsurf: `~/.windsurf/mcp.json`
  - Codex: `~/.codex/mcp.json`
  - Generic: `~/.agents/mcp.json`
- Replaces `PLACEHOLDER_REPO_ROOT` with absolute clone path
- Only includes the 9 **built** in-house servers
- Does NOT install upstream `to-install` servers

**Expected output:**
```
[setup-mcp] Resolved repo root: /root/project/AgentEnhancements
[setup-mcp] Rendering mcp.json for 6 targets...
[setup-mcp] Wrote ~/.claude/mcp.json
[setup-mcp] Wrote ~/.cursor/mcp.json
[setup-mcp] Wrote ~/.continue/mcp.json
[setup-mcp] Wrote ~/.windsurf/mcp.json
[setup-mcp] Wrote ~/.codex/mcp.json
[setup-mcp] Wrote ~/.agents/mcp.json
[setup-mcp] Done. Restart your editor/CLI to pick up MCP servers.
```

---

## Step 2: Verify Health

```bash
bash unified-integration/scripts/setup-mcp.sh --check
```

**What it does:**
- Spawns each built server via stdio
- Calls `health()` tool
- Reports status: OK / FAIL / SKIP (missing deps)

**Expected output:**
```
[health] embeddings-mcp: OK (backends: local=true, openai=false)
[health] task-router-mcp: OK (workers=4, tasks_known=0)
[health] ffmpeg-mcp: OK (ffmpeg found at /usr/bin/ffmpeg)
[health] vision-mcp: SKIP (OPENAI_API_KEY not set)
[health] graphrag-mcp: OK (store=/tmp/ae-graphrag, corpora_cached=0)
[health] arxiv-mcp: OK (offline API, no key needed)
[health] google-news-mcp: OK (RSS, no key needed)
[health] video-mcp: OK (ffmpeg found)
[health] style-mcp: OK (offline, no key needed)
```

---

## Step 3: Smoke Test

```bash
python3 unified-integration/mcp-servers/smoke_test.py
```

**What it does:**
- Runs a quick functional test against each built server
- Exercises 1-2 tools per server
- Validates request/response shapes

---

## Step 4: Install Upstream Servers (Manual)

For each `to-install` server you need:

1. **Check prerequisites** — API keys, npx/pip availability
2. **Install package**:
   ```bash
   # npx-based
   npx -y @modelcontextprotocol/server-brave-search
   
   # pip-based
   pip install mcp-server-github
   ```
3. **Set env vars** in your shell/profile:
   ```bash
   export BRAVE_API_KEY=...
   export TAVILY_API_KEY=...
   ```
4. **Add to mcp.json** manually or extend setup script
5. **Test**: restart CLI, call a tool

---

## Step 5: Wire Into Hermes / ILMA

### Via Hermes Config (`config.yaml`)
```yaml
mcp:
  servers:
    embeddings-mcp:
      command: "python3"
      args: ["/root/project/AgentEnhancements/unified-integration/mcp-servers/embeddings-mcp/server.py"]
      env: {}
    # ... repeat for each server
```

### Via CLI (one-off)
```bash
# Start server manually for testing
python3 /root/project/AgentEnhancements/unified-integration/mcp-servers/embeddings-mcp/server.py
```

### Via ACP (editor integration)
- Ensure `mcp.json` is in the right location for your editor
- Restart editor/language server
- Tools appear in agent tool palette

---

## Common Issues & Fixes

| Issue | Cause | Fix |
|-------|-------|-----|
| `health()` returns SKIP for vision-mcp | OPENAI_API_KEY not set | `export OPENAI_API_KEY=...` |
| `ffmpeg-mcp` health FAIL | ffmpeg not in PATH | `apt install ffmpeg` or add to PATH |
| `setup-mcp.sh` permission denied | Script not executable | `chmod +x unified-integration/scripts/setup-mcp.sh` |
| Tools not appearing in Claude Code | mcp.json not reloaded | Restart Claude Code completely |
| Upstream server "command not found" | npx package not installed | Run `npx -y <package>` once to install |
| GraphRAG corpus not persisting | /tmp cleared on reboot | Expected — lexical mode is in-memory + /tmp persistence |

---

## Verification Checklist

- [ ] Built servers installed via `setup-mcp.sh`
- [ ] Health check passes for all 9 built servers
- [ ] Smoke test runs without errors
- [ ] Required upstream servers installed manually
- [ ] API keys set in environment
- [ ] Target CLI/editor picks up mcp.json
- [ ] At least one tool call works end-to-end

---

## Files to Reference

- `/root/project/AgentEnhancements/plugin-catalog/mcp-servers.json` — Master catalog
- `/root/project/AgentEnhancements/unified-integration/scripts/setup-mcp.sh` — Installer
- `/root/project/AgentEnhancements/unified-integration/mcp-servers/mcp.json.example` — Template
- `/root/project/AgentEnhancements/docs/MCP_INTEGRATION_CHECKLIST.md` — Official checklist
- `~/.claude/mcp.json` (or relevant editor config) — Active wiring