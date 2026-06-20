---
name: ilma-acp-integration
description: Hermes ACP (Agent Client Protocol) — VS Code, Zed, JetBrains integration via stdio JSON-RPC. Run ILMA inside editors as an agentic coding assistant. SSS Tier.
version: 1.0.0
category: integration
platforms:
  - linux
  - macos
metadata:
  hermes:
    tags: [acp, editor, vscode, zed, jetbrains, stdio, json-rpc]
    category: integration
---

# ILMA ACP Integration — Editor Agent Protocol

## What is ACP?

ACP (Agent Client Protocol) adalah mekanisme untuk menjalankan Hermes sebagai server stdio, memungkinkan ACP-compatible editors (VS Code, Zed, JetBrains) untuk terhubung dan menggunakan Hermes sebagai coding agent native di dalam editor.

### Two-way communication

```
Editor ←→ ACP Server (Hermes) ←→ ILMA
```

Editor sends JSON-RPC commands over stdin → Hermes processes → JSON-RPC responses over stdout.

## What ILMA exposes in ACP mode

```python
hermes-acp  # or: hermes acp

# ILMA in ACP mode gets a curated toolset:
✅ File tools: read_file, write_file, patch, search_files
✅ Terminal tools: terminal, process
✅ Web/browser tools
✅ Memory, todo, session search
✅ Skills
✅ execute_code and delegate_task
✅ vision
❌ NOT: messaging delivery, cronjob management (doesn't fit editor UX)
```

## How ACP Works

### 1. Installation

```bash
# Install Hermes with ACP extra
pip install -e '.[acp]'

# This enables:
# - hermes acp
# - hermes-acp
# - python -m acp_adapter
```

### 2. Starting ACP Server

```bash
# Start Hermes in ACP mode
hermes acp

# Or use the binary name
hermes-acp

# Or via Python
python -m acp_adapter
```

**Note**: Hermes logs to stderr, stdout is reserved for JSON-RPC traffic.

### 3. Editor Setup

#### VS Code
```json
// settings.json
{
  "acp.agents": {
    "ILMA": {
      "command": "hermes",
      "args": ["acp"]
    }
  }
}
```
Install the [ACP Client](https://marketplace.visualstudio.com/items?itemName=formulahendry.acp-client) extension.

#### Zed
```json
// settings.json
{
  "agent_servers": {
    "ilma": {
      "type": "custom",
      "command": "hermes",
      "args": ["acp"]
    }
  }
}
```

#### JetBrains
Point to: `/path/to/hermes-agent/acp_registry`

### 4. Registry Manifest

ACP registry lives at:
```
acp_registry/agent.json
```

It advertises:
```json
{
  "command": "hermes acp"
}
```

## ACP Session Behavior

ACP sessions are tracked by the ACP adapter's in-memory session manager while server is running.

Each session stores:
- session ID
- working directory
- selected model
- current conversation history
- cancel event

## Configuration

ACP mode uses the same Hermes configuration:
```
~/.hermes/.env         — API keys
~/.hermes/config.yaml  — settings
~/.hermes/skills/      — skills directory
~/.hermes/state.db     — session storage
```

Provider resolution uses normal Hermes runtime resolver.

## When to Use ACP vs CLI vs Messaging

| Surface | Best For |
|---------|----------|
| **ACP (Editor)** | Coding-first workflows, file editing, terminal in editor context |
| **CLI** | Direct terminal interaction, batch operations |
| **Telegram/Messaging** | Conversations, async task initiation, voice |
| **Kanban** | Multi-agent collaboration, durable tasks |

## ILMA ACP Implementation Pattern

For ILMA to run as ACP server, the pattern is:

```python
# ACP adapter spawns ILMA with:
# - ACP toolset (curated file + terminal + web + memory + skills)
# - Stdio transport (stdin/stdout JSON-RPC)
# - In-memory session manager

# Example spawn:
subprocess.Popen(
    ["hermes", "acp"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    cwd=workspace_dir
)
```

## Integration with ILMA's Workflow

```
User in VS Code:
  "Review the auth module and add rate limiting"

→ ACP sends to ILMA:
  JSON-RPC: {"method": "chat", "params": {"message": "Review auth..."}}

→ ILMA processes with ACP toolset:
  - read_file(auth.py)
  - search_files(rate limiting patterns)
  - patch(auth.py, add rate limiting)

→ ACP returns response to editor:
  JSON-RPC response with message + tool calls
```

## Future: ILMA ACP Mode

When ILMA fully supports ACP:

```python
# Start ILMA in ACP mode
ilma acp

# Or configure in config.yaml
acp:
  enabled: true
  toolset: hermes-acp  # curated toolset
  registry: ~/.hermes/profiles/ilma/acp_registry/
```

## Benefits of ACP for ILMA

1. **Editor-native** — ILMA feels like a first-class editor feature
2. **Context-aware** — workspace directory, open files are natural context
3. **Streaming** — real-time tool progress in editor UI
4. **Approval integration** — dangerous command prompts in editor
5. **Multi-editor** — VS Code, Zed, JetBrains all supported

## Limitation

- ACP is unidirectional in current design (editor → agent)
- For bi-directional communication, use messaging gateway
- ACP sessions are in-memory (lost on restart)

---

*Hermes v0.13.0 — ACP Editor Integration*
*Integrated into ILMA v3.3*