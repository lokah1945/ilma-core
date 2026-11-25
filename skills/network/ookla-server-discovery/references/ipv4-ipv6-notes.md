# IPv4 vs IPv6 Behavior Notes

## Observation from Session (2026-11-26)

### Target Server: surabaya.trisuladata.net.id (ID: 69081)
- **IPv4:** `103.155.190.76` — Port 8080 **times out** from VPS network
- **IPv6:** `2406:7540:1900::190:76` — Port 8080 **works** from VPS network

### Key Findings

1. **Same server, different reachability**
   - Both A and AAAA records resolve correctly
   - IPv6 path works; IPv4 path blocked/timed out
   - Likely VPS network routing or ISP firewall on IPv4

2. **OoklaServer binds to both**
   - Config: `OoklaServer.useIPv4 = true`, `OoklaServer.useIPv6 = true`
   - `OoklaServer.addresses = 0.0.0.0, ::`
   - Both protocols should work from networks with proper routing

3. **Verification strategy**
   - Always test **both** IPv4 and IPv6
   - Don't conclude "server down" from IPv4 timeout alone
   - Use IPv6 as primary verification path from cloud VPS

4. **Host header behavior differs by IP version**
   - IPv6 + `Host: domain:8080` → 200 OK with "It worked!"
   - IPv6 + `Host: [IPv6]:8080` → 307 redirect to HTTPS
   - IPv4 + `Host: domain:8080` → Timeout (network issue, not server)

5. **Practical implication**
   - When scanning from cloud VPS: prioritize IPv6 verification
   - Record both IPs in results with `accessible_via` field
   - Note network-specific reachability, not server health