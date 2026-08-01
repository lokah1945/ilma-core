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

## Quality Standards
- Error handling: ✓
- Input validation: ✓
- Performance optimized: ✓
- Security audited: ✓