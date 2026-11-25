# SpeedtestServer Reverse Engineering Session — 2026-11-26

**Session ID**: ILMA-RE-20261126-001
**Target**: `smahud/SpeedtestServer` (GitHub repo)
**Local Path**: `/root/project/SpeedtestServer`
**Binary Analyzed**: Official Ookla CLI `speedtest` v1.2.0.84 (ELF64 x86-64, static musl)

---

## Repository Architecture Summary

| Component | Path | Status |
|-----------|------|--------|
| **Canonical TypeScript Implementation** | `reverse-engineered/typescript/` | ✅ Byte-verified against OoklaServer 2.11.5.2 |
| **Hybrid VPS Gateway** | `hybrid/gateway/src/gateway.mjs` | ✅ Production deployed (port 8790 TLS) |
| **Hybrid Edge Worker** | `hybrid/worker/src/index.ts` | ✅ Production at speedtest-hybrid-worker.lumajangnetworks.workers.dev |
| **Binary RE Batch (6 methods)** | `reverse-engineering-batch/` | ✅ Complete — Main @ 0x296250 |
| **Official CLI Binaries** | `speedtest-cli_official/` | ✅ 5 archs extracted (x86_64 tested) |

---

## Binary Reverse Engineering — Official Ookla CLI

### Binary Properties
- **SHA256**: `31f1124c5ab8acdae6b9fe1741e704df420f9f2e7d429679fabe62075453c051`
- **Format**: ELF64 x86-64, static musl, stripped symbols
- **Entry**: `0x401fd6` → `__libc_start_main` → **Main @ 0x296250** (verified via GDB rdi)

### Key Offsets (from RE-BATCH-20261102-001)

| Component | Binary Offset | TypeScript Component |
|-----------|---------------|---------------------|
| Main | 0x296250 | OoklaServer main |
| App init | 0x4b1020 | ConfigManager / Application::init |
| Config load | 0x6446f0 | ConfigManager / Application::loadConfig |
| Main run | 0x4b21e0 | ServerCore.start / Application::run |
| Server create | 0x4c8760 | OoklaRequestHandler |
| SSL context | 0x543690 | CertificateManager / TLSCertificateManager |
| Socket setup | 0x542a10 / 0x5429d0 | ServerCore listeners |
| String parse | 0x4a1f00 | Config parsing |

### Multi-Process Architecture (Confirmed)
- **Manager process**: Starts first, logs "OoklaServer version 2.11"
- **Ward/Server process**: Forked by manager, listens TCP/UDP 5060/8080
- **Auto-restart**: Manager restarts ward on death

---

## NetGauge Protocol Contract (Verified)

**Source**: `reverse-engineered/typescript/src/server/NetGaugeEngine.ts` + differential probes in `hybrid/lab/evidence/`

### Fixed Command Set (No Extension)

| Command | Direction | Requirement |
|---------|-----------|-------------|
| `HI [uuid]` | C→S | Register session UUID (lower-case) |
| `GETIP` | C→S | **STRICT**: exact "GETIP\n" |
| `CAPABILITIES` | C→S | Returns `SERVER_HOST_AUTH UPLOAD_STATS` |
| `SERVERID` | C→S | Returns instance UUID (lower-case) |
| `PING <x>` | C→S | Arg REQUIRED → `PONG <epoch-ms>` |
| `INITPLOSS` | C→S | Arms UDP loss registry |
| `PLOSS` | C→S | Returns loss stats |
| `DOWNLOAD <n>` | C→S | **Server MUST send n bytes** (prefix + pool[0x20..0x7F] + \n) |
| `UPLOAD <n>` | C→S | **Client MUST send n bytes** (inclusive cmd line) → `OK <n> <epoch-ms>` |
| `QUIT` | C→S | TCP close / WS: ERROR |

### Critical Constraints for Virtual Sandbox

| Constraint | Implication |
|------------|-------------|
| **DOWNLOAD = server push bytes** | Client MUST receive bytes for throughput calculation |
| **UPLOAD = client push bytes** | Client MUST send bytes |
| **Throughput = bytes / time** | Zero bytes = zero throughput |
| **No SIMULATE/GENERATE command** | Protocol cannot trigger local generation |
| **Symbol table stripped** | No plugin/extension mechanism discoverable |
| **Fully static musl** | No `dlopen()` / shared library loading |
| **Poco::Util::Application** | Monolithic C++ app, no scripting/hooks |

---

## Investigation: Server-Triggered Client-Side Virtual Sandbox

### Question
Can Official Ookla CLI run virtual simulation (payload generated locally in RAM) triggered by server, with minimal network transfer?

### Answer: **IMPOSSIBLE without binary modification**

### Evidence
1. **Protocol has no control channel** — all commands are data-plane commands
2. **DOWNLOAD semantic requires bytes on wire** — client counts received bytes
3. **UPLOAD semantic requires bytes sent** — client counts sent bytes  
4. **No extensibility** — stripped, static, no plugin API, no scripting
5. **Bypass attempts all fail "tanpa modifikasi binary"**

### Bypass Feasibility

| Approach | Feasible w/o Mod? | Notes |
|----------|-------------------|-------|
| Protocol extension | ❌ | Fixed command set |
| LD_PRELOAD hook recv/send | ⚠️ Fragile | Platform-specific, anti-tamper risk |
| MITM proxy | ⚠️ Complex | TLS pinning unknown |
| Binary patching | ❌ | Violates constraint |
| **Custom client + existing control plane** | ✅ **RECOMMENDED** | Use hybrid gateway + worker architecture |

---

## Existing Architecture for Custom Client (Ready in Repo)

```
hybrid/gateway/src/gateway.mjs          ← VPS Control Plane (PRODUCTION)
  /api/servers, /api/sessions, /api/results, /api/ping
  HMAC tokens, worker pool routing

hybrid/worker/src/index.ts              ← Edge Data Plane (PRODUCTION)  
  __down/__up via poolResponse (RAM pool)
  WS NetGauge, HTTP Legacy
  Token-gated, smart worker pool, auto-deflection

CUSTOM CLIENT NEEDED:
  - NetGauge + HTTP + WS protocol impl (from TypeScript)
  - SIMULATE mode: generate locally, fake timing
  - Honest reporting: simulation: true, mode: "ram"
```

### Worker poolResponse (Already Implements Local Generation)
```typescript
// hybrid/worker/src/http-legacy.ts → poolResponse()
export function poolResponse(size: number, headers, signal, onDone): Response {
  // Uses FixedLengthStream + backpressure
  // fillFromPool(out, offset) → deterministic printable ASCII [0x20..0x7F]
  // Client disconnect → stream abort → generation STOP
}
```

---

## Ghidra Headless Attempt

| Step | Result |
|------|--------|
| Binary import | ✅ Success (ELF64, x86:LE:64:default:gcc) |
| Auto-analysis | ✅ 253 seconds (heavy C++ exceptions) |
| Script execution | ❌ Classpath conflicts with cached Java files in `/tmp` |
| Decompilation | ❌ Not completed — needs clean script path |

**Issue**: Ghidra scripts in `/tmp` conflict with AgentEnhancements cache. Need isolated script directory.

---

## References

- `references/speedtest-ookla-binary-analysis.md` — Detailed binary analysis (this skill)
- `reverse-engineered/typescript/src/server/NetGaugeEngine.ts` — Protocol contract
- `hybrid/lab/evidence/` — Differential probe captures
- `reverse-engineering-batch/method6-gdb/MAIN_FUNCTION_REPORT.md` — GDB main discovery
- `docs/HYBRID_DEPLOYMENT_RUNBOOK.md` — Production deployment details