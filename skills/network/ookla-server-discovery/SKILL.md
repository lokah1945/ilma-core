---
name: ookla-server-discovery
description: Discover OoklaServer (speedtest.net) instances in specific IP ranges using Speedtest.net API, DNS resolution, and HTTP verification
version: 1.0.0
category: network
tags: [ookla, speedtest, server-discovery, network-scanning, ip-range]
author: ILMA
created: 2026-11-26
---

# OoklaServer Discovery Skill

Class-level skill for discovering active OoklaServer instances in target IP ranges.

## When to Use

- Need to find OoklaServer instances in specific CIDR ranges
- Auditing speedtest.net infrastructure
- Verifying which IPs in a range run OoklaServer on port 8080
- Mapping OoklaServer deployments for an ISP/region

## Core Technique

**Speedtest.net API → DNS Resolution → HTTP Verification**

1. **Fetch server list** from `https://www.speedtest.net/api/js/servers?engine=js&limit=2000`
2. **Resolve hostnames** to IPs (both IPv4 and IPv6 via `getaddrinfo`)
3. **Filter by target CIDR ranges** (e.g., `103.155.190.0/24`, `103.155.191.0/24`)
4. **Verify via HTTP** with proper `Host: domain:port` header on port 8080
5. **Check for "It worked!"** response body to confirm OoklaServer

## Critical Implementation Details

### Host Header Requirement
OoklaServer **requires** `Host: <domain>:8080` header (with port) for successful response. Raw IP as Host returns 500 or timeout.

```python
# Correct
headers = {"Host": "surabaya.trisuladata.net.id:8080"}

# Wrong - returns 500
headers = {"Host": "103.155.190.76"}
headers = {"Host": "surabaya.trisuladata.net.id"}  # without port
```

### IPv4 vs IPv6
- Many servers bind to both but **IPv6 often works when IPv4 times out** (network routing/firewall)
- Always test both address families
- Use `socket.getaddrinfo(host, port, socket.AF_INET)` and `AF_INET6`

### Response Verification
Success response contains:
```html
<html><head><title>OoklaServer</title></head><body><h1>OoklaServer</h1><p>It worked!<br /></p></body></html>
```
Plus headers: `Content-Type: text/html`, `X-Content-Type-Options: nosniff`, `Strict-Transport-Security`, `Content-Security-Policy` with `connect-src *.ookla.com *.speedtest.net *.speedtestcustom.com`

## Scripts

- `scripts/scan_ookla_range.py` — Main scanner (CIDR ranges → verified servers JSON)
- `scripts/verify_ookla_server.py` — Single server verification (IP + domain → bool + details)

## References

- `references/speedtest-api.md` — Speedtest.net API response structure
- `references/ooklaserver-headers.md` — Required/optional headers for verification
- `references/ipv4-ipv6-notes.md` — IPv4/IPv6 behavior observations

## Pitfalls

1. **Direct IP scan without Host header fails** — Always use domain in Host header
2. **IPv4 timeout ≠ server down** — Check IPv6; many servers only reachable via v6 from cloud VPS
3. **Speedtest.net API limit** — Default 1000, use `limit=2000` for full list
4. **DNS resolution needed** — API returns hostnames, not IPs directly
5. **Port 8080 HTTP only** — HTTPS on 8080 redirects (307); use HTTP for "It worked!" check

## Output Format

```json
{
  "scan_time": "2026-11-26 00:38:00",
  "ranges_scanned": ["103.155.191.0/24", "103.155.190.0/24"],
  "worked_servers": [{
    "ip": "103.155.190.76",
    "ipv6": "2406:7540:1900::190:76",
    "host": "surabaya.trisuladata.net.id",
    "port": 8080,
    "server_id": 69081,
    "sponsor": "TMD - TrusulaData",
    "status": "WORKED",
    "accessible_via": "IPv6 (from this network)"
  }]
}
```