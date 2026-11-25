# Speedtest Ookla Official CLI — Binary Analysis Reference

**Session**: 2026-11-26 | **Target**: `/root/project/SpeedtestServer/speedtest-cli_official/speedtest`
**SHA256**: `31f1124c5ab8acdae6b9fe1741e704df420f9f2e7d429679fabe62075453c051`
**Architecture**: ELF64 x86-64, static musl, stripped symbols

---

## Binary Properties (objdump + readelf)

| Property | Value |
|----------|-------|
| Format | elf64-x86-64 |
| Entry point | `0x401fd6` → `__libc_start_main` |
| **Main function** | **`0x296250`** (verified via GDB `__libc_start_main` rdi) |
| .text size | 1.8 MB (`0x1c6507`) |
| .rodata size | 194 KB |
| .eh_frame | 356 KB (heavy C++ exceptions) |
| .gcc_except_table | 96 KB |
| Dynamic deps | **NONE** (fully static) |
| Symbol table | **STRIPPED** (`objdump -t`: "tidak ada simbol") |

---

## Key Binary Offsets (from GDB batch analysis RE-BATCH-20261102-001)

| Component | Binary Offset | Likely Purpose |
|-----------|---------------|----------------|
| Entry point | `0x29fc35` | `_start` |
| Init array | `0xfff2b0` | 133 constructors |
| Singleton init | `0xb445f0` | Double-checked locking |
| Lib init | `0xb52af5` | Library initialization |
| **Main** | **`0x296250`** | **Poco::Util::Application entry** |
| App init | `0x4b1020` | `Poco::Application::init` |
| Config load | `0x6446f0` | `Poco::Application::loadConfig` |
| Main run | `0x4b21e0` | `Poco::Application::run` (server listen) |
| Server create | `0x4c8760` | Server creation/start |
| SSL context | `0x543690` | SSL/TLS context setup |
| Socket setup | `0x542a10` / `0x5429d0` | Socket/channel setup |
| String/config parse | `0x4a1f00` | String/config parsing |

---

## Main Function Flow (0x296250)

```assembly
main:
  → App init (0x4b1020)
  → Config load (0x6446f0) 
  → Main run loop (0x4b21e0)  ← server starts listening here
```

**Multi-process confirmed**: Manager forks Ward process; Ward listens TCP/UDP 5060/8080.

---

## Protocol Analysis — NetGauge (Verified via TypeScript impl + differential probes)

### Command Set (FIXED — no extension mechanism)

```
HI [uuid]           → HELLO <version>
GETIP               → YOURIP <peer-ip>        (STRICT: exact "GETIP\n")
CAPABILITIES        → CAPABILITIES SERVER_HOST_AUTH UPLOAD_STATS
SERVERID            → SERVERID <instance-uuid> (lower-case)
UPTIME              → UPTIME <seconds>
PING <x>            → PONG <epoch-ms>         (arg REQUIRED)
INITPLOSS           → OK                       (arms UDP loss)
PLOSS               → PLOSS <count> <dupes> <maxseq>
DOWNLOAD <n>        → n bytes: "DOWNLOAD " + pool[0x20..0x7F] + \n
UPLOAD <n> [ms] [c] → reads n bytes INCLUSIVE cmd line → OK <n> <epoch-ms>
QUIT                → TCP close / WS: ERROR
```

### Critical Constraints

| Constraint | Implication |
|------------|-------------|
| **DOWNLOAD** = server pushes bytes | Client MUST receive bytes for throughput calc |
| **UPLOAD** = client pushes bytes | Client MUST send bytes |
| **Throughput** = bytes / time | Zero bytes = zero throughput |
| **No SIMULATE/GENERATE command** | Protocol cannot trigger local generation |
| **Symbol table stripped** | No plugin/extension mechanism discoverable |
| **Fully static musl** | No `dlopen()` / shared library loading |
| **Poco::Util::Application** | Monolithic C++ app, no scripting/hooks |

---

## Evidence Against Virtual Sandbox on Official CLI

| Method | Evidence |
|--------|----------|
| **Static analysis** | Stripped, static, no plugin API |
| **Dynamic GDB** | Main flow: init → config → run(); no hook points |
| **Protocol capture** | `hybrid/lab/evidence/e-e-mixed-cf-plus-sts/sts-evidence.jsonl` (2918 lines) shows real byte transfer |
| **TypeScript impl** | `NetGaugeEngine.ts` byte-verified against OoklaServer 2.11.5.2 — no virtual command exists |
| **Differential probes** | `e-d-all-non-netgauge/` → CLI tries encrypted hello → ERROR → fallback plaintext NetGauge |

---

## Bypass Attempts & Feasibility

| Approach | Feasibility | Notes |
|----------|-------------|-------|
| **Protocol extension** | ❌ Impossible | Fixed command set, no extension |
| **LD_PRELOAD hook `recv`/`send`** | ⚠️ Fragile | Platform-specific, anti-tamper risk, must synthesize bytes + fake timing |
| **MITM proxy** | ⚠️ Complex | TLS cert pinning unknown, need CA intercept setup |
| **Binary patching** | ❌ "Tanpa modifikasi" | Requires rebuild/patch |
| **Official CLI + custom client** | ✅ **Recommended** | Use existing hybrid control plane |

---

## Existing Architecture for Custom Client (Already in Repo)

```
hybrid/gateway/src/gateway.mjs          ← VPS Control Plane (READY)
  /api/servers, /api/sessions, /api/results, /api/ping

hybrid/worker/src/index.ts              ← Edge Data Plane (READY)
  __down/__up (poolResponse from RAM)
  WS NetGauge, HTTP Legacy
  Token-gated, smart worker pool

CUSTOM CLIENT NEEDED:
  - NetGauge + HTTP + WS protocol impl
  - SIMULATE mode: generate locally, fake timing
  - Honest reporting: simulation: true, mode: "ram"
```

---

## Ghidra Headless Attempt

- Binary imported successfully (ELF64, x86:LE:64:default:gcc)
- Auto-analysis: 253 seconds (heavy C++ exception handling)
- Script loading issues: classpath conflicts with cached Java files in `/tmp`
- **Decompilation not completed** — needs clean script path

---

## References

- `hybrid/lab/evidence/` — differential probe captures
- `reverse-engineered/typescript/src/server/NetGaugeEngine.ts` — protocol contract
- `reverse-engineering-batch/method6-gdb/MAIN_FUNCTION_REPORT.md` — GDB main discovery
- `reverse-engineering-batch/BATCH_SUMMARY.md` — batch analysis summary
- `docs/HYBRID_DEPLOYMENT_RUNBOOK.md` — hybrid architecture deployment