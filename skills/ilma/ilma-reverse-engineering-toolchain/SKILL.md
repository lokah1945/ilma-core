---
name: ilma-reverse-engineering-toolchain
description: Reverse Engineering Toolchain Management — Verify, configure, and troubleshoot RE toolchain (radare2, Ghidra, Hopper, IDA, Kuna, REA). Quick health checks, persistent DB patterns, headless Ghidra setup, fallback chains, REA MCP integration.
category: ilma
version: 2.1.0
last_updated: 2026-11-02
tags: [reverse-engineering, binary-analysis, radare2, ghidra, hopper, ida, toolchain, setup, troubleshooting, persistent-database, rea-agents, mcp]
triggers: [rea, reverse engineering, radare2, ghidra, hopper, ida, binary analysis, decompiler, disassembler, RE toolchain, rea-agents, mcp registration]
---

# ILMA Reverse Engineering Toolchain Management

## Overview

Class-level skill for verifying, configuring, and troubleshooting the reverse engineering toolchain on the ILMA host machine. Covers radare2, Ghidra, Hopper, IDA Pro, Kuna, and REA framework — their installation status, configuration gaps, and operational patterns.

**Use when:**
- Bos asks to check RE tool installation
- Need to run binary analysis but tools fail
- Setting up persistent analysis databases
- Configuring headless Ghidra for automation
- Troubleshooting "providers not available" in RE contexts
- Registering REA MCP for Hermes/ILMA

---

## Current Machine State (2026-11-02 — POST PROVIDER SETUP)

| Tool | Status | Path/Detail | Notes |
|------|--------|-------------|-------|
| **radare2 (r2)** | ✅ INSTALLED & WORKING | `/usr/local/bin/radare2` v6.1.5 | Supports `-d <db>` for persistent DB; script file approach (`Po`/`Ps` from `/tmp`) |
| **Ghidra** | ✅ INSTALLED & WORKING | `/opt/ghidra_current` → `/opt/ghidra_12.1.4_PUBLIC` | Headless + `rea analyze`/`decompile-all --provider ghidra` E2E OK; JDK 21 at `/opt/jdk-21` |
| **Kuna** | ✅ INSTALLED v1.988 | `/usr/local/bin/kuna` (musl static) | `REA_KUNA_COMMAND`; `rea decompile --provider kuna` E2E OK; source github.com/Noelo-Lab/kuna |
| **jadx-headless-mcp** | ✅ INSTALLED v0.7.1 | `/opt/rea-providers/jadx-headless-mcp-0.7.1-all.jar` | `REA_JADX_MCP_JAR`; MCP stdio verified; for APK/DEX |
| **Hopper** | ⚠️ INSTALLED, runtime blocked | `/opt/hopper/bin/Hopper` v6.6.1 demo | needs glibc≥2.38 (host 2.36); REA rejects patched launcher (sha). `HOPPER_LAUNCHER_PATH` set, doctor detects it |
| **IDA Pro** | ❌ NO LICENSE | — | needs license + `REA_IDA_MCP_CONFIG`; template `/opt/rea-providers/ida-mcp-registration.template.json` |
| **REA agents (npm)** | ✅ INSTALLED & WORKING | `/root/.npm-global/bin/rea-agents` v6.8.0 | 229 MCP tools; registered for 12 clients (hermes, claude, codex, opencode, qwen, gemini, cursor, …) |

---

## Quick Health Check (Run First)

```bash
# One-liner to verify all RE tools
which radare2 r2 rea-agents 2>/dev/null; \
radare2 -v 2>&1 | head -3; \
export GHIDRA_INSTALL_DIR=/opt/ghidra_current && \
/opt/ghidra_current/support/analyzeHeadless --version 2>&1 | head -3; \
rea-agents doctor --client hermes --json 2>&1 | jq -r '.healthy, .environment_healthy'
```

Expected output (after fixes):
```
/usr/local/bin/radare2
/usr/local/bin/r2
/root/.npm-global/bin/rea-agents
radare2 6.1.5 ...
openjdk version "21.0.5" ...
Headless Analyzer Usage: analyzeHeadless
true
true
```

---

## Fix Patterns

### 1. Ghidra Headless Fix (Complete 2026-11-02)

```bash
# Install correct JDK 21 (Temurin) — NOT openjdk-17
# Already present at /opt/jdk-21 from ayda tools
# If missing, download Temurin 21:
# wget -q https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.5%2B11/OpenJDK21U-jdk_x64_linux_hotspot_21.0.5_11.tar.gz
# tar -xzf OpenJDK21U-jdk_x64_linux_hotspot_21.0.5_11.tar.gz -C /opt && ln -sfn /opt/jdk-21.0.5+11 /opt/jdk-21

# Install Ghidra 12.1.4 (REA requirement)
cd /opt && wget -q https://github.com/NationalSecurityAgency/ghidra/releases/download/Ghidra_12.1.4_build/ghidra_12.1.4_PUBLIC_20260921.zip
unzip -q ghidra_12.1.4_PUBLIC_20260921.zip
ln -sfn /opt/ghidra_12.1.4_PUBLIC /opt/ghidra_current

# Set JDK for Ghidra (use Temurin 21)
export JAVA_HOME=/opt/jdk-21
export GHIDRA_INSTALL_DIR=/opt/ghidra_current

# Test
$GHIDRA_INSTALL_DIR/support/analyzeHeadless --version
# Should show JDK 21 + "Headless Analyzer Usage"
```

**Pitfall:** Ghidra 12.0.4 has `application.java.compiler=25` (needs JDK 25, doesn't exist). 12.1.4 has `application.java.compiler=21` (works with JDK 21).
**Pitfall:** The wrapper `/usr/local/bin/ghidra` forces `bg` mode. Use support script directly: `$GHIDRA_INSTALL_DIR/support/analyzeHeadless`.

### 2. radare2 Persistent Database (Verified Working)

```bash
# Create analysis DB (script file approach for project creation)
r2 -i /tmp/script.r2 - <<< 'Po /tmp/ls.r2db; Ps /tmp/ls.r2db; q'  # Creates project
# Or use the ILMA wrapper script
python3 scripts/ilma_reverse_engineering.py /bin/ls --tool radare2 --json
```

**Key finding:** Must run `Po`/`Ps` commands FROM `/tmp` directory for project creation to work. The ILMA script handles this.

### 3. REA Agents + MCP Registration (Complete 2026-11-02)

```bash
# Upgrade Node.js to ≥24.22.1
curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && apt-get update && apt-get install -y nodejs
# Verified: v24.22.2

# Install REA agents
npm install -g rea-agents@6.8.0

# Register for Hermes/ILMA
rea-agents setup --client hermes --yes
# Installs skill copy + adds MCP registration to config.yaml

# Set Ghidra env for REA
export GHIDRA_INSTALL_DIR=/opt/ghidra_current

# Verify
rea-agents doctor --client hermes --json
# healthy: true, environment_healthy: true
```

**Result:** 229 MCP tools available in Hermes after gateway restart.

### 3b. Optional Providers + per-client env injection (Complete 2026-11-02)

**KEY LESSON:** `rea doctor` reads env from the *process that spawns it*. MCP servers spawn their
own processes — shell exports do NOT reach them. Every agent's `rea` MCP entry needs an explicit
`env` block, plus system-wide files for CLI use:

```bash
# 1. System-wide (all shells)
cat > /etc/profile.d/rea-providers.sh <<'EOF'
export GHIDRA_INSTALL_DIR=/opt/ghidra_12.1.4_PUBLIC
export JAVA_HOME=/opt/jdk-21
export REA_KUNA_COMMAND=/usr/local/bin/kuna
export REA_JADX_MCP_JAR=/opt/rea-providers/jadx-headless-mcp-0.7.1-all.jar
export HOPPER_LAUNCHER_PATH=/opt/hopper/bin/Hopper
EOF

# 2. Hermes gateway systemd drop-in (applies on next external restart)
mkdir -p /root/.config/systemd/user/hermes-gateway-ilma.service.d
cat > /root/.config/systemd/user/hermes-gateway-ilma.service.d/rea-env.conf <<'EOF'
[Service]
Environment=GHIDRA_INSTALL_DIR=/opt/ghidra_12.1.4_PUBLIC
Environment=JAVA_HOME=/opt/jdk-21
Environment=REA_KUNA_COMMAND=/usr/local/bin/kuna
Environment=REA_JADX_MCP_JAR=/opt/rea-providers/jadx-headless-mcp-0.7.1-all.jar
Environment=HOPPER_LAUNCHER_PATH=/opt/hopper/bin/Hopper
EOF
systemctl --user daemon-reload
# NOTE: gateway cannot restart itself from inside a gateway session (SIGTERM guard)

# 3. Each agent's rea MCP env block — e.g. codex config.toml:
# [mcp_servers.rea.env]
# GHIDRA_INSTALL_DIR = "/opt/ghidra_12.1.4_PUBLIC"  … etc
# Same for .claude.json (mcpServers.rea.env), opencode.jsonc, qwen/gemini/cursor settings, hermes config.yaml
```

Provider installs (2026-11-02, all verified):
- **Kuna 1.988** (musl static — gnu build needs glibc 2.39): from github.com/Noelo-Lab/kuna releases → `/usr/local/bin/kuna`
- **jadx-headless-mcp 0.7.1** fat jar: `…/1013503897/jadx-headless-mcp/releases/download/v0.7.1/…-all.jar` → `/opt/rea-providers/`
- **Hopper 6.6.1 demo deb**: needs browser UA+referer (bare curl → 403); installs to `/opt/hopper` but launch needs glibc≥2.38 (host=2.36) → detected by doctor, not runnable
- **IDA**: license required; template at `/opt/rea-providers/ida-mcp-registration.template.json`

Full session detail: `references/rea-providers-2026-11-02.md`

### 4. JDK Path Fix (Complete 2026-11-02)

```bash
# System had openjdk 17 on PATH — WRONG for REA
# Fix: Use Temurin 21 from /opt/jdk-21 via update-alternatives
update-alternatives --install /usr/bin/java java /opt/jdk-21/bin/java 2000
update-alternatives --install /usr/bin/javac javac /opt/jdk-21/bin/javac 2000
update-alternatives --set java /opt/jdk-21/bin/java
update-alternatives --set javac /opt/jdk-21/bin/javac

# Verify
java --version
# openjdk 21.0.5 2024-10-15 LTS (Temurin-21.0.5+11)
```

---

## Fallback Chain (Operational Priority)

When running binary analysis, prefer in order:

1. **radare2 + persistent DB** — Free, installed, scriptable, works headless
2. **Ghidra analyzeHeadless (12.1.4 + JDK 21)** — Powerful, free, now fully configured
3. **REA agents (JavaScript/Electron)** — `rea-agents analyze-javascript-application`
4. **radare2 without DB** — Quick one-off, no persistence
5. **Online decompilers** — dogbolt.org, decompiler.com (requires upload)
6. **Hopper/IDA** — Only if licenses available

---

## Integration Pattern for Agents

### ILMA Capability Registry Entry (VERIFIED)

The `reverse_engineering` capability is registered in ILMA's capability registry:

| Field | Value |
|-------|-------|
| primary_cap | reverse_engineering |
| category | analytical |
| status | **verified** |
| primary_tool | radare2 |
| fallback_tools | ghidra, rea_agents, execute_code, terminal |
| script_fallback | scripts/ilma_reverse_engineering.py |
| evidence_id | rea_capability_verified_20261102 |
| confidence_score | 0.85 |

### Python API Usage

```python
from scripts.ilma_reverse_engineering import ReverseEngineering

re = ReverseEngineering()

# Auto-detect best tool
result = re.analyze("/bin/ls", tool="auto")  # Uses capability registry

# Specific tool
result = re.radare2_analyze("/bin/ls")      # Persistent DB
result = re.ghidra_analyze("/bin/ls", project_dir="/tmp/ghidra_proj")
result = re.rea_analyze_javascript("/path/to/electron-app")
```

### REA MCP Tools (Available After Gateway Restart)

```bash
# 229 tools available via MCP in Hermes
# Examples: mcp_rea_open_binary, mcp_rea_analyze_binary, mcp_rea_query_evidence, etc.
```

---

## Pitfalls & Lessons Learned

### Pitfall 1: Ghidra JDK Interactive Prompt
**Symptom:** `ERROR: Unable to prompt user for JDK path, no TTY detected`
**Cause:** Ghidra needs `GHIDRA_JAVA_HOME` set before running headless, OR JDK version mismatch
**Fix:** Install Temurin JDK 21 + export `JAVA_HOME=/opt/jdk-21` + use Ghidra 12.1.x (not 12.0.x)

### Pitfall 2: Ghidra Version Mismatch (12.0.4 vs 12.1.x)
**Symptom:** REA flags `config_drift` for Ghidra version
**Cause:** Ghidra 12.0.4 requires JDK 25 (not released); 12.1.x requires JDK 21
**Fix:** Upgrade to Ghidra 12.1.4 + Temurin JDK 21

### Pitfall 3: radare2 -F + -p Conflict
**Symptom:** `You cannot use -F (fast scan) with -p (explicit port selection)`
**Cause:** nmap-style flags confused with radare2
**Fix:** radare2 doesn't use `-F`/`-p` like nmap. Use radare2 native commands (`a`, `aa`, `aaa`)

### Pitfall 4: REA Package Name Confusion
**Symptom:** `pip install rea` installs radio astronomy package
**Cause:** PyPI `rea` = "REceiver Array Analysis"
**Fix:** REA is npm package `rea-agents`, not Python. Install via `npm install -g rea-agents`

### Pitfall 5: Analysis Not Persisting (radare2)
**Symptom:** radare2 analysis lost between invocations
**Cause:** Not using `-d <database>` flag or wrong working directory for project creation
**Fix:** Use `r2 -d analysis.r2db <binary>` OR script file approach with `Po`/`Ps` from `/tmp`

### Pitfall 6: Node.js Version Drift
**Symptom:** REA doctor flags `missing_dependency` for Node.js 24.22.0
**Cause:** REA requires ≥24.22.1
**Fix:** Upgrade via NodeSource repo: `curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && apt-get install -y nodejs`

### Pitfall 7: REA MCP Not Registered for Hermes
**Symptom:** REA doctor shows `registration:hermes` = false, `state: "missing"`
**Cause:** Never ran `rea-agents setup --client hermes`
**Fix:** `rea-agents setup --client hermes --yes` then restart Hermes gateway

---

## Safety Boundaries

- ❌ Do NOT install Hopper/IDA without Bos explicit approval (paid licenses)
- ❌ Do NOT upload binaries to online decompilers without authorization
- ❌ Do NOT run destructive analysis on production systems
- ✅ radare2, Ghidra, REA agents are free/open-source — safe to use
- ✅ Always use persistent DB for multi-session analysis
- ✅ REA MCP registration only adds stdio MCP server — no network exposure

---

## Related Skills

- `ilma-pentest` — Security assessment (may use RE tools for malware analysis)
- `ilma-system-audit` — System-level auditing (different scope)
- `ilma-capability-registry` — Lookup capability mappings for RE tools

### Pitfall 8: MCP env vars don't propagate from shell (2026-11-02)
**Symptom:** `rea doctor` from shell says healthy, but agents (claude/codex/opencode/hermes) report ghidra/kuna/jadx missing
**Cause:** MCP servers spawn separate processes; `export` in .bashrc does not reach them
**Fix:** Add `env` block to each agent's `rea` MCP registration + `/etc/profile.d/rea-providers.sh` + systemd drop-in for gateway. See §3b.

### Pitfall 9: glibc mismatch on prebuilt Linux binaries (2026-11-02)
**Symptom:** `weak version 'GLIBC_2.39' not found` (kuna gnu build), `GLIBC_2.38 not found` (Hopper 6.6.1) on Debian 12 (glibc 2.36)
**Fix:** use the **musl/static** build when available (kuna). For Hopper: patchelf+bundled glibc can start it under xvfb, but REA rejects the patched launcher because its sha256 no longer matches the official feed → Hopper = detected-not-runnable on glibc<2.38 hosts.

### Pitfall 10: Ghidra `rea decompile` via CLI (2026-11-02)
**Symptom:** `rea decompile /bin/true free --provider ghidra` → `invalid_request`
**Cause:** single-function decompile needs an opened session; CLI path differs from MCP
**Fix:** use `rea analyze <path> --provider ghidra` (overview) or `rea decompile-all <path> --provider ghidra --output <dir>` (output dir must not pre-exist unless `--resume`). Kuna works with plain `rea decompile … --provider kuna`.

### Pitfall 11: Hopper download 403 (2026-11-02)
**Symptom:** curl to hopperapp.com/downloader returns 403 HTML
**Fix:** add browser User-Agent + `-e https://www.hopperapp.com/download` referer
### SpeedtestServer Reverse Engineering (2026-11-26)

**Target:** `smahud/SpeedtestServer` — Hybrid speedtest server (VPS gateway + Cloudflare Workers)

**Status:** Repo pulled, architecture mapped, binary offsets cataloged

**Key Findings:**
- Canonical TypeScript implementation byte-verified against OoklaServer 2.11.5.2
- 6-method binary RE batch complete: **Main function at 0x296250** (via GDB + `__libc_start_main`)
- 13 TypeScript components mapped to binary offsets (ConfigManager 0x6446f0, OoklaRequestHandler 0x4c8760, etc.)
- Multi-process confirmed: Manager forks Ward, Ward listens TCP/UDP 5060/8080
- Hybrid architecture: VPS control plane (gateway.mjs) + Edge data plane (worker/index.ts)
- Production deployed: gateway on port 8790 TLS, worker at speedtest-hybrid-worker.lumajangnetworks.workers.dev

**Next Targets:** Targeted Ghidra decompilation of 13 mapped functions, Manager/Ward IPC trace, auto-update flow verification, perf profiling.

**Detail:** `references/speedtestserver-reverse-engineering-2026-11-26.md`

---

## References

- `references/radare2-persistent-db.md` — Detailed radare2 DB workflow
- `references/ghidra-headless-setup.md` — Full Ghidra headless configuration (updated for 12.1.4 + JDK 21)
- `references/rea-mcp-registration.md` — REA MCP setup for Hermes/ILMA
- `references/rea-package-search.md` — PyPI/npm search results for RE frameworks
- `references/reverse-engineering-capability.md` — ILMA capability registry entry (single source of truth)
- `references/rea-providers-2026-11-02.md` — Session detail: all optional providers installed (Kuna 1.988, jadx 0.7.1, Hopper 6.6.1, Ghidra 12.1.4), per-client env injection, E2E evidence, gotchas
- `references/speedtestserver-reverse-engineering-2026-11-26.md` — SpeedtestServer hybrid architecture RE session: repo pull, binary offsets, protocol flow, production deployment verification

---

*Last Updated: 2026-11-02 — v2.1.0 — Optional providers wired (Kuna/jadx/Hopper/Ghidra), per-agent MCP env injection pattern, glibc pitfall, CLI-vs-MCP decompile distinction; see references/rea-providers-2026-11-02.md*