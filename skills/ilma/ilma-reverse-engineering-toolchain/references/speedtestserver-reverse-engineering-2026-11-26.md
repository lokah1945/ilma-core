# SpeedtestServer Reverse Engineering — Session 2026-11-26

## Target
**Repo:** `smahud/SpeedtestServer` (already pulled at `/root/project/SpeedtestServer`)
**Branch:** `master` (latest commit `410ea9f`)
**Architecture:** Hybrid VPS (gateway) + Cloudflare Workers (edge workers)

---

## Key Components Mapped

### 1. Canonical TypeScript Implementation (`reverse-engineered/typescript/`)
**Status:** Byte-verified against OoklaServer 2.11.5.2 (2026-06-04 build)

| Component | File | Purpose |
|-----------|------|---------|
| Entry Point | `src/bin/ooklaserver.ts` | CLI, config validation, TLS resolution, signal handlers |
| Server Core | `src/server/ServerCore.ts` | **Canonical listener architecture** — single multiplexed listener per port, protocol detection (TLS/HTTP/WS/NetGauge), fail-closed binds, bounded shutdown |
| NetGauge Engine | `src/server/NetGaugeEngine.ts` | Transport-agnostic Ookla native protocol (HI, GETIP, CAPABILITIES, SERVERID, UPTIME, PING, INITPLOSS/PLOSS, DOWNLOAD, UPLOAD, QUIT) |
| HTTP API | `src/server/HttpApi.ts` | Legacy HTTP surface byte-verified (F-15..F-22): Host validation, CSP, UA filter, upload.php, random*.jpg, crossdomain.xml |
| TLS/ACME | `src/server/CertificateManager.ts`, `AcmeProvisioner.ts` | Custom cert precedence, ACME issuance/renewal, hot reload (§9.7) |
| UDP Loss | `src/server/UdpLossEngine.ts`, `LossRegistry.ts` | Packet-loss protocol with bounded session registry (F-33) |

**Protocol Contract Verified:** `validation/PROTOCOL_CONTRACT.md` (revision 3, 2026-11-04 differential probes)

---

### 2. Hybrid Architecture (`hybrid/`)
**Control Plane (VPS):** `hybrid/gateway/src/gateway.mjs`
- Discovery (`/api/servers`), Session tokens (`POST /api/sessions`), Results intake (`POST /api/results`)
- Worker pool routing with live `.env` hot-reload (v1.5)
- HMAC-SHA256 token minting (shared secret with Workers)
- Auto-deflection to sibling workers when saturated

**Data Plane (Edge Workers):** `hybrid/worker/src/index.ts`
- NetGauge over WebSocket (`/ws`)
- HTTP `__down`/`__up` endpoints (token-gated)
- Legacy HTTP surface (OFF by default, `LEGACY_HTTP_ENABLED=true` for testing)
- Autonomous deflection (302/307 with `hop` guard)
- Per-isolate load gauge (in-flight + EWMA)

**Worker Legacy HTTP:** `hybrid/worker/src/http-legacy.ts` — Daemon-parity with documented platform deviations (D-W2, D-W5, D-W6)

---

### 3. Binary Reverse Engineering Batch (`reverse-engineering-batch/`)
**6 Methods Executed (Complete):**

| Method | Status | Key Finding |
|--------|--------|-------------|
| 1. objdump | ✅ | Entry point 0x29fc35, section layout |
| 2. readelf | ✅ | 39,705 relocations, fully static binary |
| 3. strings | ✅ | 23,000+ strings, cross-ref KEY_STRINGS.md |
| 4. rizin (dynamic) | ✅ | Zero dynamic dependencies |
| 5. Ghidra | ✅ (2hr) | C++ exception handling bottleneck |
| 6. GDB | ✅ **MAIN FOUND** | **Main @ 0x296250** (via `__libc_start_main`) |

**Component → Binary Offset Mapping:**
- ConfigManager → 0x6446f0 (loadConfig)
- OoklaRequestHandler → 0x4c8760 (server create)
- OoklaDownloader → 0x543690 (SSL context)
- BinaryManager → auto-update logic
- InstanceLocker → manager coordination
- ClientAuthTokenValidator → token validation
- ConnectionTracker → connection mgmt
- IpStatsManager → rate limiting
- MetricsUploader → metrics collection
- TLSCertificateManager → 0x543690
- TracerouteManager → traceroute logic
- Logger → logging system
- **OoklaServer main → 0x296250**

**Multi-process:** Manager forks Ward, Ward listens TCP/UDP 5060/8080 (confirmed via GDB dynamic run)

---

## Evidence Artifacts

### Lab Evidence (`hybrid/lab/evidence/`)
- `e-a-cf-edge-probes.jsonl` — Cloudflare edge probes
- `e-b-workerd-probes.jsonl` — Workerd probes
- `e-d-all-non-netgauge/` — Non-NetGauge traffic analysis
- `e-e-mixed-cf-plus-sts/` — Mixed CF + STS (sts-evidence.jsonl: 2918 lines)
- `e-g-host-tester-vs-worker/` — Host tester comparison
- `e-i-production-gateway/` — Production gateway sessions
- `e-j-real-edge/` — **Real edge measurements** (measure-real-edge-2026-11-24T01-57-50-889Z.json: 1050 lines)
- `e-k-speedtest-front/` — Speedtest front test evidence
- `e-l-post-push-verification/` — Post-deployment verification
- `e-m-official-cli-campaign/` — Official CLI campaign (10 runs, summary.json)

### Reports
- `hybrid/reports/HYBRID_RESEARCH_REPORT.md` — Full research report
- `hybrid/reports/Hybrid_VPS_Cloudflare_Workers_Speedtest_Report.pdf` (611 KB)
- `hybrid/reports/WORKERS_LIMITS.md` — Workers Free tier limits
- `hybrid/reports/assets/architecture-diagram.{html,png}`

---

## Operational Runbooks

### Deployment (Production Active as of 2026-11-24)
- **Gateway VPS:** `speedtest-hybrid-gateway.service` on port 8790 TLS
  - URL: `https://speedtest.lumajangnetworks.my.id:8790`
  - Env: `/etc/speedtest-hybrid/gateway.env`
- **Worker:** `speedtest-hybrid-worker` at `https://speedtest-hybrid-worker.lumajangnetworks.workers.dev`
  - Conformance: 55/55, Token: 11/11, Hardening: 17/17
- **Speedtest Front:** Legacy HTTP at gateway with edge offload (docs/§front)

### Key Environment Variables
```bash
# Gateway
HYBRID_GATEWAY_PORT=8790
HYBRID_GATEWAY_TLS_CERT=/run/credentials/speedtest-hybrid-gateway.service/cert
HYBRID_WORKER_BASE=https://speedtest-hybrid-worker.lumajangnetworks.workers.dev
HYBRID_SHARED_SECRET=<32-byte hex>
HYBRID_FRONT_ENABLED=true
HYBRID_FRONT_RATE_LIMIT_MPM=90

# Worker (wrangler vars)
WORKER_ID=1, WORKER_POOL_MAX=100
MAX_DOWNLOAD_BYTES=26214400 (25 MiB)
MAX_UPLOAD_BYTES=26214400
LEGACY_HTTP_ENABLED=false
HYBRID_SHARED_SECRET=<same as gateway>
```

---

## Next Reverse Engineering Targets

| Priority | Target | Rationale |
|----------|--------|-----------|
| HIGH | **Ghidra targeted decompilation** of 13 mapped functions (ConfigManager, OoklaRequestHandler, OoklaDownloader, etc.) | Binary offsets known; auto-analysis too generic |
| HIGH | **Manager/Ward IPC** (fork logic, shared memory) | Multi-process confirmed but not decompiled |
| MEDIUM | **Auto-update binary flow** (BinaryManager decommissioned in TS but may exist in binary) | Verify decommission claim |
| MEDIUM | **Perf profiling** of binary under load | Baseline for hybrid edge comparison |
| LOW | **Protocol edge cases** (invalid HI args, GETIP strictness, DOWNLOAD bounds) | Already verified in TS; binary diff would confirm |

---

## Toolchain Used
- **radare2 6.1.5** — Binary inspection, strings, entry tracing
- **Ghidra 12.1.4 + Temurin JDK 21** — Decompilation (headless)
- **GDB** — Dynamic analysis, breakpoint at `__libc_start_main` → main discovery
- **readelf/objdump** — ELF structure, relocations
- **rizin** — Dynamic linking analysis
- **Custom harnesses** (`hybrid/lab/harness/*.mjs/.py`) — Differential probes against live daemon

---

## Files of Interest for Deep Dive

```
reverse-engineered/typescript/src/bin/ooklaserver.ts         # Entry
reverse-engineered/typescript/src/server/ServerCore.ts       # Core multiplexer (1130 lines)
reverse-engineered/typescript/src/server/NetGaugeEngine.ts   # Protocol engine (565 lines)
reverse-engineered/typescript/src/server/HttpApi.ts          # HTTP surface (624 lines)
reverse-engineered/typescript/src/server/CertificateManager.ts
reverse-engineered/typescript/src/server/AcmeProvisioner.ts
hybrid/gateway/src/gateway.mjs                               # VPS control plane (561 lines)
hybrid/worker/src/index.ts                                   # Edge worker (481 lines)
hybrid/worker/src/http-legacy.ts                             # Worker HTTP parity (434 lines)
hybrid/worker/src/netgauge.ts                                # Worker NetGauge port
reverse-engineering-batch/method6-gdb/MAIN_FUNCTION_REPORT.md
reverse-engineering-batch/comparison/BATCH_COMPARISON_REPORT.md
```

---

*Session: 2026-11-26 — ILMA v3.32 — Repo pulled, architecture mapped, binary offsets cataloged*