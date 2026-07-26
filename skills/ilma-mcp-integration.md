---
name: ilma-mcp-integration
description: Hermes MCP (Model Context Protocol) — stdio and HTTP MCP server integration, OAuth 2.1 PKCE, tool prefixing, per-server tool filtering. SSS Tier.
version: 1.0.0
category: integration
platforms:
  - linux
  - macos
metadata:
  hermes:
    tags: [mcp, stdio, http, oauth, protocol, tools]
    category: integration
---

# ILMA MCP Integration — Model Context Protocol

## What is MCP?

MCP (Model Context Protocol) is a standardized protocol for connecting AI models to external tools and data sources. It's like USB-C for AI — a universal interface that lets any MCP-compatible server expose tools to any MCP-compatible client.

```
ILMA (MCP Client) ←→ MCP Server (GitHub, Filesystem, Database, etc.)
```

---

## Architecture Overview

### MCP Client (ILMA side)

- Connects to MCP servers via stdio or HTTP
- Receives server's tool manifest
- Exposes tools as callable functions
- Handles authentication (OAuth 2.1 PKCE for HTTP)

### MCP Server (tool provider side)

- Exposes tool manifest to client
- Receives tool call requests
- Returns tool results
- Can be local (stdio) or remote (HTTP)

---

## MCP Tool Naming

Tools from MCP servers are prefixed to avoid collisions:

```
<mcp_server>_<tool_name>

# Example: GitHub MCP server
mcp_github_create_issue
mcp_github_list_repos
mcp_github_search_code

# Example: Filesystem MCP server
mcp_filesystem_read_file
mcp_filesystem_write_file
```

---

## Configuration

### config.yaml Setup

```yaml
mcp:
  servers:
    github:
      command: npx
      args: ["-y", "@modelcontextprotocol/server-github"]
      env:
        GITHUB_TOKEN: "${GITHUB_TOKEN}"
    filesystem:
      command: npx
      args: ["-y", "@modelcontextprotocol/server-filesystem"]
      allowedDirectories:
        - "/home/user/projects"
        - "/home/user/documents"
    postgres:
      type: http
      url: https://mcp.example.com/postgres
      auth:
        type: oauth2
        client_id: "${POSTGRES_CLIENT_ID}"
        client_secret: "${POSTGRES_CLIENT_SECRET}"
        scopes: ["read", "write"]
```

### Environment Variables

```bash
# For stdio servers
GITHUB_TOKEN=ghp_xxx

# For HTTP servers
POSTGRES_CLIENT_ID=xxx
POSTGRES_CLIENT_SECRET=xxx
```

---

## MCP Server Examples

### Official MCP Servers

| Server | Tools | Connection |
|--------|-------|------------|
| GitHub | create_issue, list_repos, search_code, create_pull_request | stdio |
| Filesystem | read_file, write_file, list_directory | stdio |
| Slack | send_message, post_message, list_channels | stdio |
| Postgres | query, execute, list_tables | stdio/HTTP |
| Brave Search | web_search | stdio |
| Google Maps | search_places, get_directions | stdio |
| Sentry | list_issues, create_issue | stdio |
| AWS | ec2_list, s3_upload, lambda_invoke | stdio |

### Community MCP Servers

| Server | Description |
|--------|-------------|
| Claude-MCP-Servers | Official Claude MCP servers |
| VoltAgent/awesome-mcp | Community server directory |
| LobeHub/mcp-servers | Community servers for LLM platforms |
| ModelContextProtocol/servers | Official MCP org servers |

---

## Tool Filtering

### Per-Server Filtering

Limit which tools are exposed from a server:

```yaml
mcp:
  servers:
    github:
      command: npx
      args: ["-y", "@modelcontextprotocol/server-github"]
      tools:
        include:
          - create_issue
          - list_repos
        exclude:
          - delete_*
```

### Wildcard Support

```yaml
# Include all except dangerous ones
tools:
  include:
    - "*"
  exclude:
    - delete_*
    - destroy_*
```

---

## Authentication

### Stdio Servers

- No authentication needed
- Token passed via `env:` in config

### HTTP Servers

#### OAuth 2.1 PKCE Flow

```yaml
mcp:
  servers:
    remote_api:
      type: http
      url: https://api.example.com/mcp
      auth:
        type: oauth2
        client_id: "${CLIENT_ID}"
        client_secret: "${CLIENT_SECRET}"
        auth_url: https://auth.example.com/authorize
        token_url: https://auth.example.com/token
        scopes: ["read", "write"]
        pkce: true  # PKCE required for OAuth 2.1
```

#### Bearer Token

```yaml
mcp:
  servers:
    api:
      type: http
      url: https://api.example.com/mcp
      headers:
        Authorization: "Bearer ${API_KEY}"
```

---

## MCP in ILMA Workflow

### Example: GitHub Integration

```
User: "Create an issue on my GitHub repo about the auth bug"

→ ILMA calls mcp_github_create_issue:
  {
    "owner": "huda",
    "repo": "myapp",
    "title": "Auth bug fix required",
    "body": "..."
  }

→ MCP server executes GitHub API call
→ Returns issue URL

→ ILMA reports to user
```

### Example: Database Query

```
User: "Show me the last 10 orders from the database"

→ ILMA calls mcp_postgres_query:
  {"sql": "SELECT * FROM orders ORDER BY created_at DESC LIMIT 10"}

→ MCP server executes query
→ Returns results as JSON

→ ILMA formats and displays
```

---

## MCP Server Discovery

### skills.sh (Public Directory)

```bash
# Install from skills.sh
curl -s https://skills.sh/install | sh

# List available MCP servers
hermes skills list --category mcp
```

### Direct NPM Installation

```bash
npx -y @modelcontextprotocol/server-github
npx -y @modelcontextprotocol/server-filesystem
```

### Custom MCP Servers

Write your own MCP server:

```python
# my_server.py
from mcp.server import Server
from mcp.types import Tool

server = Server("my-server")

@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="my_tool",
            description="Does something useful",
            inputSchema={
                "type": "object",
                "properties": {
                    "arg1": {"type": "string"}
                }
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "my_tool":
        return {"result": f"Processed {arguments['arg1']}"}

server.run(transport="stdio")
```

---

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| Server not found | Command not in PATH | Install server, check config |
| Auth failed | Invalid credentials | Check env vars, OAuth flow |
| Tool not found | Server doesn't expose tool | Check server manifest |
| Timeout | Server slow to respond | Increase timeout, check server |
| Connection refused | HTTP server down | Check server is running |

---

## ILMA MCP Pattern

```python
# ilma_mcp_manager.py
class MCPManager:
    def __init__(self, config: dict):
        self.servers = self._init_servers(config)
        self.tools = self._discover_tools()
    
    async def call_tool(self, server: str, tool: str, args: dict):
        """Call MCP server tool."""
        if server not in self.servers:
            raise ValueError(f"Unknown MCP server: {server}")
        
        server_config = self.servers[server]
        if server_config["type"] == "stdio":
            return await self._call_stdio(server, tool, args)
        elif server_config["type"] == "http":
            return await self._call_http(server, tool, args)
    
    async def _call_stdio(self, server, tool, args):
        # Spawn server process, send JSON-RPC, receive result
        pass
    
    async def _call_http(self, server, tool, args):
        # Send HTTP request with auth, receive JSON response
        pass
```

---

## Auto-Trigger

Load this skill when:
- User mentions "MCP", "Model Context Protocol", "MCP server"
- User wants to "connect to GitHub", "use database tools", "add external tools"
- User asks about specific MCP servers (GitHub, Slack, Postgres, etc.)
- User wants to "extend ILMA's capabilities" with custom tools

---

*Hermes v0.13.0 — MCP Integration feature*
*Integrated into ILMA v3.3*