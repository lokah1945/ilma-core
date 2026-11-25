# SpeedtestServer Reverse Engineering — Session Notes (2026-11-26)

**Repo:** `smahud/SpeedtestServer` → `/root/project/SpeedtestServer`  
**Target Binary:** Official speedtest CLI (`OoklaServer 2.11.5.2` compatible)  
**SHA256:** `31f1124c5ab8acdae6b9fe1741e704df420f9f2e7d429679fabe62075453c051`  
**Path:** `/root/project/SpeedtestServer/speedtest-cli_official/speedtest`

---

## Architecture Overview

| Component | Path | Language | Status |
|-----------|------|----------|--------|
| Canonical TypeScript impl | `reverse-engineered/typescript/` | TypeScript | ✅ Byte-verified |
| Hybrid VPS Gateway | `hybrid/gateway/src/gateway.mjs` | Node.js (ESM) | ✅ Deployed port 8790 |
| Hybrid Cloudflare Worker | `hybrid/worker/src/index.ts` | TypeScript → JS | ✅ Deployed workers.dev |
| Binary RE Batch | `reverse-engineering-batch/` | 6 methods | ✅ COMPLETE |
| Official CLI binaries | `speedtest-cli_official/` | x86_64, arm64, armel, armhf, i386 | ✅ Extracted x86_64 |

---

## 6-Method Binary Analysis (Batch Complete)

| Method | Tool | Status | Key Finding |
|--------|------|--------|-------------|
| 1 | objdump | ✅ | Entry point 0x29fc35, ELF layout |
| 2 | readelf | ✅ | 39,705 relocations, fully static |
| 3 | strings | ✅ | 23,000+ strings, KEY_STRINGS.md cross-ref |
| 4 | rizin | ✅ | Zero dynamic deps |
| 5 | Ghidra | ✅ (2hr) | C++ exception handling bottleneck |
| 6 | GDB | ✅ **MAIN FOUND** | **Main @ 0x296250** via `__libc_start_main` |

**Component Mapping (from BATCH_SUMMARY.md):**
| TypeScript Component | Binary Offset | Notes |
|---------------------|---------------|-------|
| ConfigManager | 0x6446f0 | loadConfig |
| OoklaRequestHandler | 0x4c8760 | server create |
| OoklaDownloader | 0x543690 | SSL context |
| BinaryManager | auto-update | decommissioned in TS |
| InstanceLocker | manager coord | manager coordination |
| ClientAuthTokenValidator | token validation | |
| ConnectionTracker | connection mgmt | |
| IpStatsManager | rate limiting | |
| MetricsUploader | metrics | |
| TLSCertificateManager | 0x543690 | shared with OoklaDownloader |
| TracerouteManager | traceroute | |
| Logger | logging | |
| **OoklaServer main** | **0x296250** | **VERIFIED via GDB** |

---

## REA Toolchain Applied (2026-11-26)

| REA Tool | Command | Evidence ID | Result |
|----------|---------|-------------|--------|
| `inspect-with-objdump` file_headers | `objdump -f` | `ev_fb9945a8e251` | ✅ Entry point 0x401fd6, elf64-x86-64 |
| `inspect-with-objdump` section_headers | `objdump -h` | `ev_759bb9e92f61` | ✅ 17 sections mapped |
| `inspect-with-objdump` symbols | `objdump -t` | `ev_6954745bc237` | ⚠️ Stripped — "tidak ada simbol" |
| `inspect-with-objdump` disassemble_all | `objdump -D` | `ev_f2ecfa02c399` | ⚠️ SIGKILL at ~35MB output |

**Providers:** GNU objdump (via REA pwntools-elf fallback — requires `REA_PWNTOOLS_PYTHON`)

---

## Protocol Flow (Binary → TypeScript Implementation)

### 1. Client Startup & Server Discovery
```
speedtest binary
    │
    ├─► HTTPS GET https://www.speedtest.net/api/js/servers
    │       → JSON server list (id, host, lat/lon, sponsor, url)
    │
    └─► Select server (lowest latency or --server-id)
```

### 2. Native NetGauge Protocol (TCP 5060/8080)
```
Client                          Server (TypeScript: ServerCore + NetGaugeEngine)
  │                                    │
  ├─► TCP Connect                     │
  │                                    │
  ├─► Encrypted Binary Hello (AES-GCM?)│
  │       ← ERROR (our impl)           │  ← Triggers plaintext fallback
  │                                    │
  ├─► HI                              │  → HELLO <version>
  ├─► HI <uuid>                       │  → HELLO <version> + register session
  ├─► GETIP                           │  → YOURIP <peer-ip> (STRICT: exact "GETIP\n")
  ├─► CAPABILITIES                    │  → CAPABILITIES SERVER_HOST_AUTH UPLOAD_STATS
  ├─► SERVERID                        │  → SERVERID <instance-uuid> (LOWER-CASE)
  ├─► UPTIME                          │  → UPTIME <seconds>
  ├─► PING <x>                        │  → PONG <epoch-ms>
  ├─► INITPLOSS                       │  → OK (arm UDP LossRegistry)
  ├─► PLOSS                           │  → PLOSS <count> <dupes> <maxseq>
  │                                    │
  ├─► DOWNLOAD <n>                    │  → exact n bytes:
  │       "DOWNLOAD " prefix (9 bytes)
  │       pool bytes [0x20..0x7F] (daemon charset)
  │       trailing "\n" (counted in n)
  │                                    │
  ├─► UPLOAD <n> [ms] [c]             │  → reads n bytes inclusive of command line
  │       n < cmd_len → ERROR          │  → OK <n> <epoch-ms>
  │       non-numeric/neg → ignored    │
  │                                    │
  └─► QUIT                            │  → TCP close / WS: ERROR reply
```

### 3. HTTP Legacy Path (Browser/HTML5)
```
GET  /speedtest/latency.txt      → "test=test\n"
GET  /speedtest/random{N}x{N}.jpg → deterministic JPEG sizes (IMAGE_SIZES map)
POST /speedtest/upload.php       → drain body → "size=<bytes>\n"
GET  /hi                         → "hello <version>\n"
GET  /crossdomain.xml            → Flash policy (allowedDomains + defaults)
WS   /ws                         → NetGauge commands as WS frames (1 cmd/frame)
```

---

## Hybrid Architecture (Production Verified)

```
┌─────────────┐     Control Plane      ┌──────────────┐
│   Client    │◄──────────────────────►│  VPS Gateway │
│             │  discovery, tokens,    │  (gateway.mjs)│
│             │  results, ping         │  :8790 TLS   │
└──────┬──────┘                        └──────┬───────┘
       │                                      │
       │         Payload Plane (NO VPS transit)        │
       ▼                                      ▼
┌─────────────────────┐              ┌─────────────────────┐
│  Cloudflare Worker  │              │  Cloudflare Worker  │
│  (index.ts)         │              │  (index.ts)         │
│  __down?bytes=N     │              │  POST __up          │
│  poolResponse()     │              │  countBody()        │
│  fillFromPool()     │              │  (drain + count)    │
└─────────────────────┘              └─────────────────────┘
```

**Key Implementation (Worker edge):**
- `hybrid/worker/src/http-legacy.ts:poolResponse()` — `FixedLengthStream` + backpressure
- `hybrid/worker/src/pool.ts:fillFromPool()` — deterministic printable-ASCII pool [0x20..0x7F]
- `hybrid/worker/src/index.ts:handleDown()` → token-gated, auto-deflection to sibling workers

**Evidence of Offload:** `hybrid/lab/evidence/e-j-real-edge/measure-real-edge-*.json`
- Payload: 117.4 MB transferred
- VPS interface delta: 67.9 KB
- **Offload ratio: ~1:28,000**

---

## Production Deployment (Verified 2026-11-24)

| Component | Status | URL/Endpoint |
|-----------|--------|--------------|
| VPS Gateway | ✅ Active | `https://speedtest.lumajangnetworks.my.id:8790` |
| Worker Prod | ✅ Active | `https://speedtest-hybrid-worker.lumajangnetworks.workers.dev` |
| Worker Test | ❌ Deleted | (was used for conformance) |
| Systemd Unit | ✅ Enabled | `speedtest-hybrid-gateway.service` |
| TLS Cert | ✅ Loaded | `/run/credentials/.../cert` via LoadCredential |

---

## Next Targets for Ghidra Targeted Decompilation

| Priority | Binary Offset | TypeScript Target | Reason |
|----------|---------------|-------------------|--------|
| 1 | 0x296250 | OoklaServer main | Entry point, multi-process fork |
| 2 | 0x6446f0 | ConfigManager.loadConfig | Config parsing, properties file |
| 3 | 0x543690 | OoklaDownloader/SSL | TLS context, cert loading |
| 4 | 0x4c8760 | OoklaRequestHandler | NetGauge dispatch, HTTP routing |
| 5 | 0xb52af5 | Library init sequence | Poco::Util::Application init |
| 6 | 0xb445f0 | Singleton init | Double-checked locking pattern |

---

## REA Workflow Lessons (This Session)

1. **Start with `inspect-with-objdump` file_headers + section_headers** — fast, no provider setup
2. **Symbols stripped** → need Ghidra/Kuna for function recovery (objdump disassemble_all too large)
3. **Use `--detail summary --evidence_output`** for large disassembly to avoid transport truncation
4. **Cross-reference with repo TypeScript impl** — `reverse-engineered/typescript/src/server/` has byte-verified NetGauge/HttpApi
5. **Batch analysis dir** (`reverse-engineering-batch/`) has 6-method cross-validation including GDB main discovery
5. **REA doctor reads env from spawning process** — MCP servers need explicit `env` blocks per agent (§3b in toolchain skill)

---

## Files in Repo for Reference

| Path | Purpose |
|------|---------|
| `reverse-engineered/typescript/src/bin/ooklaserver.ts` | Canonical entry point |
| `reverse-engineered/typescript/src/server/ServerCore.ts` | Listener architecture (1 listener/port, multiplexed) |
| `reverse-engineered/typescript/src/server/NetGaugeEngine.ts` | Protocol engine (verified F-8..F-36) |
| `reverse-engineered/typescript/src/server/HttpApi.ts` | HTTP legacy surface (verified F-15..F-37) |
| `reverse-engineered/typescript/src/server/CertificateManager.ts` | TLS resolution (custom > ACME > dev-self-signed) |
| `reverse-engineered/typescript/src/server/UdpLossEngine.ts` | UDP packet-loss protocol |
| `hybrid/gateway/src/gateway.mjs` | VPS control plane |
| `hybrid/worker/src/index.ts` | Worker edge (NetGauge WS + HTTP __down/__up) |
| `hybrid/worker/src/http-legacy.ts` | Worker HTTP legacy + poolResponse |
| `hybrid/worker/src/pool.ts` | fillFromPool deterministic generator |
| `reverse-engineering-batch/BATCH_SUMMARY.md` | 6-method analysis summary |
| `reverse-engineering-batch/method6-gdb/MAIN_FUNCTION_REPORT.md` | GDB main function discovery |