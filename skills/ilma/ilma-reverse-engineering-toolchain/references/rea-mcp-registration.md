# REA MCP Registration for Hermes/ILMA

## Overview
REA (Reverse Engineering Agents) provides an MCP server with 229 tools for reverse engineering. This document covers registration for Hermes/ILMA agent.

## Prerequisites (Verified 2026-11-02)
- Node.js ≥24.22.1 (v24.22.2 installed via NodeSource)
- Ghidra 12.1.x (12.1.4 at `/opt/ghidra_current`)
- JDK 21+ (Temurin-21.0.5+11 at `/opt/jdk-21`)
- REA agents npm package v6.8.0

## Registration Steps

```bash
# 1. Install REA agents (if not present)
npm install -g rea-agents@6.8.0

# 2. Set Ghidra environment for REA
export GHIDRA_INSTALL_DIR=/opt/ghidra_current

# 3. Register for Hermes
rea-agents setup --client hermes --yes

# This does two things:
# - Adds MCP registration to /root/.hermes/profiles/ilma/config.yaml:
#   rea:
#     command: /root/.npm-global/bin/rea
#     args: ["mcp"]
#     enabled: true
# - Installs skill copy to /root/.hermes/profiles/ilma/skills/reverse-engineer-anything

# 4. Verify registration
rea-agents doctor --client hermes --json
# Should show: "healthy": true, "environment_healthy": true
# registrations[].state: "aligned" for hermes

# 5. Restart Hermes gateway to load MCP tools
systemctl --user restart hermes
```

## Config.yaml Entry (Auto-generated)
```yaml
rea:
  command: /root/.npm-global/bin/rea
  args:
    - mcp
  enabled: true
```

## Available MCP Tools (229 tools)
Key tools for reverse engineering:
- `mcp_rea_open_binary` — Open binary for analysis
- `mcp_rea_analyze_binary` — Run analysis pipeline
- `mcp_rea_query_evidence` — Query evidence graph
- `mcp_rea_list_functions` — List functions in binary
- `mcp_rea_get_decompilation` — Get decompiled code
- `mcp_rea_find_references` — Find cross-references
- `mcp_rea_ghidra_headless` — Run Ghidra headless via REA
- `mcp_rea_radare2_script` — Execute radare2 script

Full list: `rea-agents doctor --client hermes --json | jq '.catalog.counts'`

## Common Issues

### Node.js Version Drift
```bash
# REA requires ≥24.22.1
# Fix:
curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && apt-get install -y nodejs
```

### Ghidra Not Found by REA
```bash
# Must set GHIDRA_INSTALL_DIR
export GHIDRA_INSTALL_DIR=/opt/ghidra_current
# Add to ~/.bashrc for persistence
```

### JDK Version Mismatch
```bash
# REA needs JDK 21+, system had JDK 17
# Fix: Use Temurin 21 from /opt/jdk-21
update-alternatives --set java /opt/jdk-21/bin/java
```

### Skill Copy Missing
```bash
# Re-run setup with skill flag
rea-agents setup --skill-client hermes --skill
```

## Verification Commands

```bash
# Full doctor check
rea-agents doctor --client hermes --json

# Check specific provider
rea-agents doctor --client hermes --json | jq '.providerInspections[] | select(.id=="ghidra")'

# List all registered clients
rea-agents doctor --client hermes --json | jq '.identity.registrations[] | .client'
```

## Notes
- REA MCP runs as stdio server (no network exposure)
- 229 tools + 6 prompts registered
- Skill version 49 installed with 229 tools
- Only Ghidra provider configured; IDA/JADX/Kuna optional
- REA CLI `rea-agents analyze-javascript-application` works independently of MCP

## Related Files
- `/root/.hermes/profiles/ilma/config.yaml` — MCP registration
- `/root/.hermes/profiles/ilma/skills/reverse-engineer-anything/` — Skill copy
- `/opt/ghidra_current` — Ghidra 12.1.4 installation
- `/opt/jdk-21` — Temurin JDK 21