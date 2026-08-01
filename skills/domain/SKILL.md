---
name: domain
description: Domain reconnaissance including network scanning, website discovery, and multi-service VPS mapping
type: umbrella
triggers: ["domain", "reconnaissance", "network scan", "website inventory", "strapi discovery"]
---

# Domain

## Purpose
Domain - Military grade skill for ILMA. Extended to include network scanning and multi-service VPS discovery.

## Triggers
- "domain"
- "reconnaissance"
- "network scan"
- "website inventory"
- "strapi"

## Status
Military Grade: Active
Last Updated: 2026-08-02

## Extended Scope
Beyond traditional domain recon, now covers:
- Private IP network discovery (172.16.x.x, 10.x.x.x, 192.168.x.x)
- SSH credential discovery from known secure folders
- Database exploration for CMS platforms
- Multi-website mapping via Strapi multisite architecture

## Implementation
See associated Python modules in this directory.

## Common Patterns / Pitfalls

### Private Network Recognition
- IP 172.16.x.x = private AWS VPC network
- Skip reverse DNS lookup for private RFC1918 addresses
- Focus on port scan direct access: `nmap -sT -p 3000-3210,5432 TARGET`

### Next.js Detection
Header indicators: `RSC`, `X-Next-Data`, `x-nextjs-cache`, `x-nextjs-prerender`

### Strapi Detection
- Path `/admin` returns Strapi Admin login page
- Header: `X-Powered-By: Strapi`
- Database: PostgreSQL with table pattern `articles`, `sites`, `categories`

## Quality Standards
- Error handling: ✓
- Input validation: ✓
- Performance optimized: ✓
- Security audited: ✓