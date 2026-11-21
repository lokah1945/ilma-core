# REA Optional Providers — Setup Session 2026-11-02 (verified E2E)

`rea doctor --json` after setup: `healthy: true`, `environment_healthy: true`, 16/17 checks pass
(only `ida-registration` false — needs a paid IDA Pro license).

## Installed providers

| Provider | Version | Location | Download source | Verified |
|----------|---------|----------|-----------------|----------|
| Ghidra | 12.1.4 | `/opt/ghidra_12.1.4_PUBLIC` (+`/opt/ghidra_current` symlink), JDK 21 Temurin `/opt/jdk-21` | NSA releases | `rea analyze /bin/true --provider ghidra` OK; `decompile-all --output` OK |
| Kuna | 1.988 | `/usr/local/bin/kuna` | `https://github.com/Noelo-Lab/kuna/releases/download/v1.988/kuna-v1.988-linux-x86_64-musl.tar.gz` | `rea decompile /bin/true free --provider kuna` OK (ev_ab5fe6…); `kuna functions /bin/true --json` → 138 fns |
| jadx-headless-mcp | 0.7.1 | `/opt/rea-providers/jadx-headless-mcp-0.7.1-all.jar` (42 MB fat jar) | `https://github.com/1013503897/jadx-headless-mcp/releases/download/v0.7.1/jadx-headless-mcp-0.7.1-all.jar` | MCP stdio `initialize` + `tools/list` OK (tools: status, load_apk, …); needs a real .apk to go further |
| Hopper | 6.6.1 demo | `/opt/hopper/bin/Hopper` | `https://www.hopperapp.com/downloader/public/Hopper-6.6.1-Linux-demo.deb` | doctor detects launcher ✅, but **runtime launch fails**: needs glibc≥2.38, host has 2.36 |
| IDA Pro | — | — | — | no license; template `/opt/rea-providers/ida-mcp-registration.template.json`, activate via `REA_IDA_MCP_CONFIG` |

Kuna specs tarball (13.7 MB) extracted to `/opt/kuna-specs`.
Live status doc: `/opt/rea-providers/STATUS.md`.

## Env vars — must be in EVERY MCP client, not just the shell

MCP servers spawn their own processes; shell exports do not propagate. Set the `env` block on the
`rea` entry in each agent config, plus system-wide files:

```
GHIDRA_INSTALL_DIR=/opt/ghidra_12.1.4_PUBLIC
JAVA_HOME=/opt/jdk-21
REA_KUNA_COMMAND=/usr/local/bin/kuna
REA_JADX_MCP_JAR=/opt/rea-providers/jadx-headless-mcp-0.7.1-all.jar
HOPPER_LAUNCHER_PATH=/opt/hopper/bin/Hopper
```

Applied 2026-11-02 to:
- `/etc/profile.d/rea-providers.sh` (all shells)
- `/root/.config/systemd/user/hermes-gateway-ilma.service.d/rea-env.conf` (Hermes gateway; active on next external restart)
- MCP `rea` env blocks: `~/.claude.json`, `~/.codex/config.toml` (`[mcp_servers.rea.env]`),
  `~/.config/opencode/opencode.jsonc`, `~/.qwen/settings.json`, `~/.gemini/settings.json`,
  `~/.cursor/mcp.json`, `~/.gemini/config/mcp_config.json`, hermes `profiles/ilma/config.yaml` (`mcp_servers.rea.env`)

Note: `~/.claude.json` previously pointed at wrong paths (`/opt/ghidra/ghidra_12.2_PUBLIC`,
`/opt/jadx/jadx-headless-mcp.jar`, `/opt/kuna/...`) — corrected to the canonical paths above.

## Gotchas / pitfalls learned

- **glibc mismatch on prebuilt Linux binaries:** kuna's gnu build needs GLIBC_2.39 → use the **musl**
  build (static). Hopper 6.6.1 needs GLIBC_2.38; host Debian 12 = 2.36. patchelf + bundled glibc-239
  loader makes Hopper start under xvfb, but REA rejects the patched launcher (sha256 must match the
  official feed) → Hopper stays "detected but not runnable" on this host.
- **`rea decompile <path> <fn> --provider ghidra` via CLI → `invalid_request`.** For Ghidra use
  `rea analyze <path> --provider ghidra` or `rea decompile-all <path> --provider ghidra --output <dir>`
  (output dir must NOT pre-exist unless `--resume`). Kuna works with plain `rea decompile … --provider kuna`.
- Omitting `--provider` when several providers fit → `capability_unavailable: Choose one with --provider`.
- **Hopper download returns 403** to bare curl — needs browser `User-Agent` + `-e https://www.hopperapp.com/download`.
- **doctor green ≠ runtime green** for Hopper: doctor checks launcher path+sha only.
- `rea doctor` without the env vars reports ghidra/kuna/jadx as missing — always export them first.
- jadx needs an actual `.apk`/`.dex` to do work (`load_apk`); jar alone only proves MCP handshake.
- Gateway cannot be restarted from inside a gateway session (SIGTERM guard) — systemd drop-in applies
  on next external `systemctl --user restart hermes-gateway-ilma` or reboot.
