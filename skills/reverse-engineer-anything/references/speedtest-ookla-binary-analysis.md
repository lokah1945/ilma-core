# Speedtest/OoklaServer Binary Analysis — Session Notes

**Date:** 2026-11-26  
**Target:** Official speedtest CLI binary (Ookla 1.2.0.84, ea6b6773cf)  
**SHA256:** 31f1124c5ab8acdae6b9fe1741e704df420f9f2e7d429679fabe62075453c051  
**Path:** `/root/project/SpeedtestServer/speedtest-cli_official/speedtest`  
**Repo:** `/root/project/SpeedtestServer` (smahud/SpeedtestServer)

---

## REA Toolchain Used

| Tool | Command | Evidence ID | Status |
|------|---------|-------------|--------|
| `inspect-with-objdump` file_headers | `objdump -f` | `ev_fb9945a8e251` | ✅ Complete |
| `inspect-with-objdump` section_headers | `objdump -h` | `ev_759bb9e92f61` | ✅ Complete |
| `inspect-with-objdump` symbols | `objdump -t` | `ev_6954745bc237` | ✅ Stripped (no symbols) |
| `inspect-with-objdump` disassemble_all | `objdump -D` | `ev_f2ecfa02c399` | ⚠️ SIGKILL at ~35MB output |

**Providers:** GNU objdump (via REA pwntools-elf fallback)

---

## Binary Layout (from objdump)

```
Format: elf64-x86-64
Architecture: i386:x86-64
Entry point: 0x0000000000401fd6
Flags: EXEC_P, D_PAGED
```

**Key Sections:**
| Idx | Name | Size | VMA | Flags |
|-----|------|------|-----|-------|
| 1 | .text | 0x1c6507 (~1.8MB) | 0x400170 | CODE, READONLY |
| 3 | .rodata | 0x30db0 (~197KB) | 0x5c6680 | DATA, READONLY |
| 4 | .eh_frame | 0x5746c (~350KB) | 0x5f7430 | DATA, READONLY |
| 5 | .gcc_except_table | 0x175c7 (~95KB) | 0x64e89c | DATA, READONLY |
| 7 | .init_array | 0x1f8 | 0x866380 | DATA |
| 11 | .data.rel.ro | 0x15a30 (~88KB) | 0x8665a0 | DATA |
| 14 | .data | 0x1b10 | 0x87c020 | DATA |
| 15 | .bss | 0x7d98 | 0x87db40 | ALLOC |

**Note:** Symbol table stripped (`objdump -t` → "tidak ada simbol").

---

## Cross-Reference: Prior GDB Analysis (from repo batch)

From `reverse-engineering-batch/method6-gdb/MAIN_FUNCTION_REPORT.md`:
- **Main function at 0x296250** (verified via `__libc_start_main` argument tracing)
- Entry point traced: 0x29fc35
- 133 global constructors in `.init_array`
- Singleton init at 0x0b445f0 (double-checked locking)
- Library init sequence: 0xb52af5 → 0xb52ebc
- Pattern: `Poco::Util::Application` (init → loadConfig → run)
- Multi-process: Manager forks Ward, Ward listens TCP/UDP 5060/8080

**Component Mapping (from BATCH_SUMMARY.md):**
| TypeScript Component | Binary Offset |
|---------------------|---------------|
| ConfigManager | 0x6446f0 (loadConfig) |
| OoklaRequestHandler | 0x4c8760 (server create) |
| OoklaDownloader | 0x543690 (SSL context) |
| BinaryManager | auto-update logic |
| InstanceLocker | manager coordination |
| ClientAuthTokenValidator | token validation |
| ConnectionTracker | connection management |
| IpStatsManager | rate limiting |
| MetricsUploader | metrics collection |
| TLSCertificateManager | 0x543690 |
| TracerouteManager | traceroute logic |
| Logger | logging system |
| OoklaServer main | **0x296250** |

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
  │       "DOWNLOAD " prefix (9 bytes, truncated if n<10)
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

## Hybrid Architecture (VPS + Cloudflare Workers)

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

## REA Workflow Lessons

1. **Start with `inspect-with-objdump` file_headers + section_headers** — fast, no provider setup
2. **Symbols stripped** → need Ghidra/Kuna for function recovery (objdump disassemble_all too large)
3. **Use `--detail summary --evidence_output`** for large disassembly to avoid transport truncation
4. **Cross-reference with repo TypeScript impl** — `reverse-engineered/typescript/src/server/` has byte-verified NetGauge/HttpApi
5. **Batch analysis dir** (`reverse-engineering-batch/`) has 6-method cross-validation including GDB main discovery

---

## Next Steps for Deeper Analysis

| Goal | Tool | Target |
|------|------|--------|
| Decompile main (0x296250) | Ghidra `analyze_function` | Config loading, server discovery, protocol init |
| Decompile SSL context (0x543690) | Ghidra | Certificate handling, ACME flow |
| Decompile request handler (0x4c8760) | Ghidra | NetGauge command dispatch |
| Trace network calls | Frida `instrument-with-frida` | `curl`/`libcurl` usage for server list + result upload |
| Compare binaries | REA `compare` | x86_64 vs aarch64/armel builds |

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