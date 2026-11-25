# NetGauge Protocol — Ookla Speedtest Native Protocol

**Source**: `reverse-engineered/typescript/src/server/NetGaugeEngine.ts` — byte-verified against OoklaServer 2.11.5.2 (2026-06-04.1737.7d0993d)
**Differential Probes**: `hybrid/lab/evidence/e-e-mixed-cf-plus-sts/sts-evidence.jsonl` (2918 lines)

---

## Protocol Overview

NetGauge is a **plaintext line-based protocol** over TCP (ports 5060, 8080) or TLS-wrapped TCP, also over WebSocket (`/ws`). The official Speedtest CLI first attempts an **encrypted binary hello**; an ERROR reply triggers fallback to this plaintext protocol.

---

## Command Set (FIXED — No Extension Mechanism)

| Command | Direction | Syntax | Response | Notes |
|---------|-----------|--------|----------|-------|
| **HI** | C→S | `HI` or `HI <uuid>` | `HELLO <version>` | Bare HI = no session; UUID = register session (lower-case, verified F-8) |
| **GETIP** | C→S | `GETIP` | `YOURIP <peer-ip>` | **STRICT**: must be exact `GETIP\n`; trailing bytes → mute connection (F-11/F-12) |
| **CAPABILITIES** | C→S | `CAPABILITIES` [args] | `CAPABILITIES SERVER_HOST_AUTH UPLOAD_STATS` | Extra args tolerated |
| **SERVERID** | C→S | `SERVERID` [args] | `SERVERID <instance-uuid>` | Lower-case UUID (daemon parity F-8); extra args tolerated |
| **UPTIME** | C→S | `UPTIME` [args] | `UPTIME <seconds>` | Extra args tolerated |
| **PING** | C→S | `PING <x>` | `PONG <epoch-ms>` | Arg REQUIRED (any value); bare PING → ERROR (F-10) |
| **INITPLOSS** | C→S | `INITPLOSS` | `OK` | Arms UDP loss registry for this session UUID |
| **PLOSS** | C→S | `PLOSS` | `PLOSS <count> <dupes> <maxseq>` | Stats from latest session |
| **UPLOAD_STATS** | C→S | `UPLOAD_STATS` | `ERROR` | Daemon parity (verified 2026-11-04) |
| **DOWNLOAD** | C→S | `DOWNLOAD <n>` | **n bytes** (see below) | Server pushes payload |
| **UPLOAD** | C→S | `UPLOAD <n> [ms] [c]` | `OK <n> <epoch-ms>` | Client pushes payload |
| **QUIT** | C→S | `QUIT` | Close / ERROR (WS) | TCP: close; WS: ERROR reply (F-14) |
| **<unknown>** | C→S | anything else | `ERROR` | Includes CLI encrypted hello → triggers plaintext fallback |

---

## DOWNLOAD Payload Structure (Byte-Exact, Verified F-9)

```
Client: DOWNLOAD <n>\n
Server: <exactly n bytes>\n
```

**Byte composition of n bytes:**
- Bytes 0..min(n-1, 8): `"DOWNLOAD "` prefix (truncated if n < 10)
- Bytes min(n,9)..n-2: Pool data — printable ASCII **[0x20..0x7F]** (daemon charset)
- Byte n-1: `\n` (trailing newline, **counted in n**)

**Special cases:**
- `n = 0` → exactly `"\n"` (1 byte)
- `n < 10` → prefix truncated, no pool bytes, just `\n`
- `n > maxDownloadBytes` (default 2 GiB - 1) → ERROR (safety deviation from daemon unbounded)

---

## UPLOAD Payload Semantics (Inclusive Counting)

```
Client: UPLOAD <n> [ms] [c]\n
       [n bytes total INCLUDING the command line above]
Server: OK <n> <epoch-ms>\n
```

**Rules:**
- `n` includes the command line length (bytes sent on wire)
- `n < command-line length` → ERROR (includes n=0)
- Non-numeric/negative `n` → **silently ignored** (connection continues, daemon parity)
- `n > maxUploadBytes` (default 2 GiB - 1) → ERROR (safety deviation)

---

## UDP Packet Loss Protocol (Parallel Plane)

| Command | Direction | Purpose |
|---------|-----------|---------|
| `INITPLOSS` | C→S | Register session UUID, arm loss accounting |
| `LOSS <uuid> <seq> <timer>` | C→S (UDP) | 4-field: counted, no reply; 5-field: `RECV <seq> <timer> [<count> <seq> <dupes>]` |
| `PLOSS` | C→S (TCP) | Query latest session stats |

**LossRegistry bounds (F-33):**
- Global session cap: 2048
- Per-source-IP cap: 64
- Eviction: LRU (least recently seen)

---

## WebSocket Transport (Verified F-13/F-14)

- Upgrade on `/ws` (HTTP → WS)
- **One command per frame** while idle
- Upload payload frames exempt (count as data)
- Frame without newline → newline synthesized for line engine
- **Real wire length passed** to UPLOAD inclusive counting
- Oversized frame (> `wsFrameSizeLimitBytes`, default 5242880) → **no reply, connection torn down** (daemon parity intent F-27)
- `QUIT` → `ERROR` reply (WS), not close (daemon parity F-14)

---

## Three-Strikes Error Rule (Verified F-24)

- TCP connection closed **after 3rd cumulative ERROR reply**
- Valid commands do NOT reset counter
- HI bad-argument ERROR does NOT count
- WebSocket sessions: **no limit**

---

## Version Banner

```
DEFAULT_VERSION_STRING = "2.11 (2.11.5) 2026-06-04.1737.7d0993d"
```
Verified against OoklaServer 2.11.5.2 build 2026-06-04.1737.7d0993d on 2026-11-04.

---

## Client Behavior (Official CLI)

1. **Encrypted binary hello** → Server ERROR → fallback to plaintext
2. **HI <uuid>** → Register session
3. **GETIP** → Get peer IP
4. **CAPABILITIES** → Check server features
5. **SERVERID** → Get instance UUID
6. **PING loop** → Latency measurement (multiple PING/PONG)
7. **INITPLOSS** → Arm UDP loss
8. **DOWNLOAD <n>** → Receive payload, measure throughput
9. **UPLOAD <n>** → Send payload, measure throughput
10. **PLOSS** → Get UDP loss stats
11. **QUIT** → Close

---

## Constraints for Virtual Sandbox

| Constraint | Protocol Basis | Implication |
|------------|----------------|-------------|
| **No SIMULATE command** | Command set fixed | Server cannot trigger local generation |
| **DOWNLOAD = bytes on wire** | Client counts received bytes | Zero bytes = zero throughput |
| **UPLOAD = bytes sent** | Client counts sent bytes | Zero bytes = invalid test |
| **No plugin mechanism** | Binary stripped, static | Cannot extend protocol |
| **No scripting** | Poco::Util::Application | Monolithic C++ |

---

## Implementation References

| Component | Path |
|-----------|------|
| Protocol Engine (TS) | `reverse-engineered/typescript/src/server/NetGaugeEngine.ts` |
| HTTP Legacy (TS) | `reverse-engineered/typescript/src/server/HttpApi.ts` |
| Worker Edge (TS) | `hybrid/worker/src/netgauge.ts` |
| Worker HTTP (TS) | `hybrid/worker/src/http-legacy.ts` |
| Pool Generator | `hybrid/worker/src/pool.ts` → `fillFromPool()` |
| Evidence Captures | `hybrid/lab/evidence/e-e-mixed-cf-plus-sts/` |
| Binary Main | `0x296250` (GDB verified) |

---

## Related Skills

- `reverse-engineer-anything` → Binary analysis, REA tools
- `ilma-reverse-engineering-toolchain` → Toolchain management, Ghidra/radare2/REA setup