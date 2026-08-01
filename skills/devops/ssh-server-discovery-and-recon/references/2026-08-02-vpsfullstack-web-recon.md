# VPSFullStack Website Recon — 2026-08-02

## Discovery Summary

**Target IP**: `172.16.103.200` (FullStack VPS)

### Key Finding: Internal Network Services (172.16.x.x)

| Service | Port | Framework | HTTP Response | Notes |
|---------|------|-----------|---------------|-------|
| YAPSI Main Website | 3201 | Next.js | HTTP 200 OK | Primary site |
| Strapi CMS | 3200 | Strapi 5.x | HTTP 200 OK | `/admin` endpoint shows Strapi |
| Prelanding Ads | 3100 | Next.js | HTTP 200 OK | Pre landing page |
| SSH | 22 | OpenSSH | Open | Root access available |

### Infrastructure Metadata

Source file: `/root/credential/vps_project.json` (v1.2, last updated 2026-06-20)

```json
{
  "projects": {
    "yapsi-website": {
      "url": "https://yapsi.or.id",
      "vps_ip": "172.16.103.200",
      "services": {
        "main_website": { "port": 3201, "framework": "Next.js", "pm2_name": "nextjs" },
        "strapi_cms": { "port": 3200, "framework": "Strapi", "pm2_name": "strapi" },
        "prelanding_ads": { "port": 3100, "framework": "Next.js", "pm2_name": "prelanding-ads" }
      },
      "private_key_file": "/root/credential/smahud.pem"
    }
  }
}
```

### Key Catalog (Credential Files)

| File | Type | Usage |
|------|------|-------|
| `smahud.pem` | RSA | Works on 172.16.103.200 (FullStackVPS) root |
| `lokah1945.pem` | RSA | For 172.16.103.253 (YAPSIDarussalam) |
| `lokah1945.pem` | RSA | Also present as `/root/credential/id_ed25519` |

### Port Verification Commands

```bash
# Verify ports are listening
nmap -sS -p 3000,3001,3100,3200,3201,80,443,8080,8443 172.16.103.200

# HTTP header verification
curl -sI http://172.16.103.200:3201/
curl -sI http://172.16.103.200:3200/admin
curl -sI http://172.16.103.200:3100/
```

### HTTP Indicators

**Next.js (ports 3100, 3201)**:
```
X-Powered-By: Next.js
Vercel-like headers: X-Vercel-Cache, X-Vercel-ID
```

**Strapi (port 3200)**:
```
X-Powered-By: Strapi <strapi.io>
X-Content-Type-Options: nosniff
```

## Tactics: Probing Internal Domains

When probing `172.16.x.x` addresses:

1. **Use nmap with specific ports** - internal services may not respond to broad scans
2. **Test HTTP directly on discovered ports** - don't rely on port 80/443
3. **Check both HTTP and HTTPS** when uncertain
4. **Extract `<title>` to confirm framework** - Next.js/Strapi have distinct signatures

## Common Failure Patterns

- **NXDOMAIN on Reverse DNS**: Internal IP has no PTR record (common in private networks)
- **nmap shows custom ports**: Service names may show as generic (opcon-xps, tick-port, cpq-tasksmart)
- **HTTP 200 but wrong content**: Verify actual page content, not just status code

## Related
- `vps_project.json-surgical-update.md` — for updating stale infrastructure configs
- `2026-06-20-fullstackvps-audit.md` — previous audit with port reassignments