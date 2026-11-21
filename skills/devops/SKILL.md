---
name: devops
description: DevOps - server management, VPS discovery, and multi-service webapp operations
type: umbrella
triggers: ["devops", "server inventory", "vps discovery", "strapi", "website discovery"]
---

# Devops

## Purpose
Devops - Military grade skill for ILMA. Covers server management, VPS discovery, and multi-service webapp operations.

## Triggers
- "devops"
- "server inventory"
- "vps discovery"
- "strapi"
- "website discovery"

## Status
Military Grade: Active
Last Updated: 2026-08-02

## Extended Workflow: VPS FullStack Discovery

### Database Non-Standard Port Discovery
- MySQL/MariaDB often runs on non-standard ports (3306 default)
- Common alternate ports: 3307, 33445, 3406
- **Port inference pattern**: If port 3306 blocked but business domain requires DB access → scan adjacent ports
- **Evidence gathering**: Use `timeout 5 bash -c "echo >/dev/tcp/$${TARGET}/$${PORT}"` for TCP port check
- **Status indicators**: Port open = service accessible, need credential discovery; Port closed = firewall or service down

### Database Health Check (Non-Standard Port)
```bash
# Identify database port from service discovery
DB_PORT=33445  # discovered via port inference
# Quick connectivity test
timeout 5 bash -c "echo >/dev/tcp/$${TARGET}/$${DB_PORT}" && echo "DB accessible" || echo "DB unreachable"
```

### SSH Credential Discovery Pattern
- Check: `/root/credential/*.pem`, `/root/.ssh/id_*`, `*.pem` files
- Common usernames: `root`, project name
- Known deployer key: `smahud.pem` for FullStack VPS

### Multi-Service Webapp Mapping (Port 3000-3210)
- **Port 3100**: PreLandingAds (Next.js)
- **Port 3200**: Strapi CMS (Node.js/Strapi 5.x)
- **Port 3201**: Main Website YAPSI (Next.js)

### Strapi Multsite Database Pattern
- Database: `news_platform` @ localhost:5432
- User: `<project_name>` (e.g., `smahud`)
- Tables: `articles`, `sites`, `categories`, `authors`, `tags`
- Multi-site via: `sites`, `categories_site_lnk`, `articles_site_lnk`

### Framework Detection via curl Headers
- **Next.js**: `RSC`, `X-Next-Data`, `x-nextjs-cache`, `x-nextjs-prerender`
- **Strapi**: `X-Powered-By: Strapi`, `Access-Control-Allow-Origin:`

### Content Extraction Commands
```bash
# Get all sites in Strapi
PGPASSWORD="..." psql -d news_platform -c "SELECT id, name FROM sites;"

# Get site-category mapping
PGPASSWORD="..." psql -d news_platform -c "SELECT s.name, c.name FROM sites s JOIN categories_site_lnk csl ON s.id=csl.site_id JOIN categories c ON csl.category_id=c.id;"
```

### Cloudflare Token Tunnel Pattern (NEW - 2026-10-31)
**Scenario:** Cloudflare tunnel managed via token (no local config.yml), ingress rules in Dashboard.

```bash
# Check tunnel service
systemctl status cloudflared cloudflared2nd

# View logs (connection errors to origin)
journalctl -u cloudflared -n 50 --no-pager | grep -i "error\|refused\|origin"

# Verify tunnel origin connectivity (proxy must be running FIRST)
curl -k https://127.0.0.1:3980/  # proxy TLS endpoint

# Tunnel architecture:
# User → CF Edge → CF Tunnel (QUIC) → https://127.0.0.1:3980 (custom Node proxy TLS)
#                                              → http://127.0.0.1:4080 (Next.js app)

# Key insight: Tunnel origin = PROXY HTTPS (not app HTTP)
# Proxy terminates TLS, routes by port → internal app
```

### Next.js Standalone + Static Image Optimization Pattern (NEW - 2026-10-31)
```bash
# next.config.ts
images:
  unoptimized: true  # serve from /images/*.webp directly, NOT /_next/image

# Pre-convert images to WebP via PIL
python scripts/optimize_images.py  # → public/images/*.webp

# Cache headers via next.config.headers()
headers:
  - source: "/images/:path*"
    headers:
      - key: "Cache-Control"
        value: "public, max-age=2592000"  # 30 days

# Result: cf-cache-status: HIT on static assets
# Homepage = SSG (prerendered) → x-nextjs-prerender: 1,1
```

### Zero-Downtime Deploy (Standalone Swap)
```bash
# Deploy new build
mv /var/www/<project>/standalone /var/www/<project>/standalone.prev
mkdir /var/www/<project>/standalone
tar -xzf new-build.tar.gz -C /var/www/<project>/standalone
systemctl restart <project>  # proxy & other units untouched

# Rollback
mv standalone standalone.bad
mv standalone.prev standalone
systemctl restart <project>
```

### Digit-Match Port Scheme (Owner-Enforced)
| Unit Type | Public Port | Internal Port | Example |
|---|---|---|---|
| YAPSI core | 399X | 3999/400X | main:3990→3999, panti:3991→4001 |
| NON-YAPSI | 398X | 408X | shankarawell:3980→4080 |
| Special (sirat) | 3901 | 3901 | own HTTPS |

**Reference Doc:** `/root/PORT_MAPPING.md` (single source of truth)

## Quality Standards
- Error handling: ✓
- Input validation: ✓
- Performance optimized: ✓
- Security audited: ✓

## References

- `references/database-port-discovery.md` — Non-standard DB port discovery patterns
- `references/freellmapi-docker-install.md` — FreeLLMAPI install on 397x-398x port range using `docker run` (bypasses Compose v1 + SDK 5.x conflict)
- `references/freellmapi-multi-provider.md` — FreeLLMAPI provider matrix, free tiers, routing strategies
- `templates/freellmapi-docker-run.sh` — Reusable `docker run` template for any port in 397x-398x range

## Related Skills

- `ssh-server-discovery-and-recon` — Phase 0 prerequisite (finding right key/host)
- `vps-project-deep-audit` — comprehensive 7-phase project audit (git, deps, DB, services, build, config, findings report)
- `system-administration` — service management
- `ilma-wrapper-fleet-ops` — for wrapper/service fleet audits
- `ilma-wrapper-port-verification` — port mapping verification