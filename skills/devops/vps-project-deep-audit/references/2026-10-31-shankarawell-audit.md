# Shankara Wellness & Sanctuary — Deep Audit Reference (2026-10-31)

**Host:** 172.16.103.253 (YAPSIDarussalam) | **SSH Alias:** `yapsi` (key: `/root/credential/lokah1945.pem`)
**Project Path:** `/var/www/shankarawell`
**Session:** ILMA deep audit + git init + GitHub PAT discovery

---

## 🎯 Executive Summary

**Health: OPERATIONAL** — Production site serving at `https://shankarawell.yapsidarussalam.or.id` with optimized static assets (CF HIT), SSG homepage, and zero-downtime deploy capability. **No source repo on VPS** — deployed from tarball only. **DB outside deploy path** (SQLite at `/home/z/my-project/db/custom.db`). **Service runs as root** (needs hardening).

---

## 🏗️ Architecture Overview

| Component | Technology | Version | Port/Path |
|---|---|---|---|
| Runtime | Node.js | v20.20.2 | — |
| Framework | Next.js | 16.1.1 (standalone) | 127.0.0.1:4080 (HTTP) |
| Database | SQLite | 3.x | file:/home/z/my-project/db/custom.db |
| ORM | Prisma | 6.11.1 | — |
| Reverse Proxy | Custom Node.js HTTPS (`https-proxy.js`) | v11 admin-perunit | 0.0.0.0:3980 (TLS) |
| TLS Cert | Let's Encrypt wildcard `*.yapsidarussalam.or.id` | — | /etc/letsencrypt/live/... |
| Tunnel | Cloudflare (token-based, Akun A) | — | cloudflared.service |
| Process Manager | systemd | — | `shankarawell.service`, `yapsi-main.service` |

**Data Flow:**
```
User (HTTPS) → Cloudflare Edge → Cloudflare Tunnel (QUIC)
  → https://127.0.0.1:3980 (yapsi-main proxy, TLS)
  → http://127.0.0.1:4080 (Next.js app)
```

---

## 🗄️ Database

- **Type:** SQLite (file-based)
- **Location:** `/home/z/my-project/db/custom.db` (symlinked via `.env`)
- **Schema:** Prisma (`prisma/schema.prisma` in source repo, not on VPS)
- **Migrations:** Managed in source repo, applied at build time
- **Tables:** Managed via Prisma models (wellness services, bookings, content)

---

## ⚙️ Services

| Service | Status | PID | Mem | CPU | Ports |
|---|---|---|---|---|---|
| shankarawell | active | 282764 | 51.2M | 3.6s | 127.0.0.1:4080 |
| yapsi-main | active | 282249 | 84.5M | 16.2s | 0.0.0.0:3980, 3990, 3999 |
| cloudflared | active | 672 | 44.4M | 26m | QUIC to CF edge |
| cloudflared2nd | active | 673 | 45.5M | 25m | Backup tunnel |

---

## 📦 Build & Deploy

**Deploy Method:** Tarball → extract to `/var/www/shankarawell/standalone/`

**Zero-Downtime Pattern:**
```bash
mv /var/www/shankarawell/standalone /var/www/shankarawell/standalone.prev
mkdir /var/www/shankarawell/standalone
tar -xzf new-build.tar.gz -C /var/www/shankarawell/standalone
systemctl restart shankarawell  # proxy & other units untouched
```

**Rollback:**
```bash
mv standalone standalone.bad
mv standalone.prev standalone
systemctl restart shankarawell
```

**Build Artifacts in Standalone:**
- `server.js` (Next.js standalone entry)
- `.next/` (prerender manifest, routes, static chunks)
- `public/images/` (14 pre-optimized `.webp` + logo)
- `node_modules/` (production deps only)
- `package.json` (minimal)

---

## 🔐 Config & TLS

| Item | Status |
|---|---|
| `.env` | Present, chmod 600, contains `DATABASE_URL` only |
| TLS Cert | Valid, expires 2027-01-16, Let's Encrypt wildcard |
| Proxy Config | `/var/www/yapsi-landing/https-proxy.js` (v11, per-unit data) |
| Cloudflare Ingress | Managed via Dashboard (token tunnel), NOT local config.yml |
| Security Headers | HSTS (180d), X-Content-Type-Options, X-Frame-Options, CSP via proxy |
| HTTPS Only | Proxy only listens TLS :3980; app middleware 308 HTTP→HTTPS |

---

## ⚠️ Findings

| Sev | Issue | Evidence | Recommendation |
|---|---|---|---|
| 🔴 **Critical** | No git repo on VPS | `fatal: bukan sebuah repositori git` | ✅ FIXED: `git init` + `.gitignore` + commit docs/start.sh |
| 🔴 **Critical** | No git remote / backup | No origin, no push path | Add `git remote add origin git@github.com:lokah1945/LandingPage_Shankara.git` + push |
| 🟡 **High** | Service runs as root | `User=root` in systemd unit | Create dedicated user, chown deploy dir, update unit |
| 🟡 **High** | DB outside deploy path | `/home/z/my-project/db/custom.db` | Move to `/var/www/shankarawell/data/` or document backup |
| 🟠 **Medium** | No source repo on VPS | Only tarball deploy artifacts | Maintain source repo separately; document build pipeline |
| 🟢 **Low** | Cloudflare errors in logs | `dial tcp 127.0.0.1:3980: connection refused` (pre-proxy-start) | Harmless (proxy started after tunnel); monitor if persistent |

---

## ✅ Strengths

- ✅ Static WebP optimization → CF `HIT` at all PoPs (30-day cache)
- ✅ SSG homepage (`x-nextjs-prerender: 1,1`) — instant TTFB
- ✅ Zero-downtime deploy via `standalone`/`standalone.prev` swap
- ✅ Centralized TLS proxy for multi-unit (yapsi-main handles 9 units)
- ✅ Digit-match port scheme (398X publik → 408X internal) — predictable
- ✅ Per-unit physical data dirs (v11) — no cross-unit contamination
- ✅ HTTPS-only architecture (no HTTP listeners anywhere)
- ✅ HSTS + security headers on all responses

---

## 🎯 Recommendations

| Priority | Action | Command |
|---|---|---|
| P0 | Add git remote & push | `cd /var/www/shankarawell && git remote add origin git@github.com:lokah1945/LandingPage_Shankara.git && git push -u origin main` |
| P0 | Create deploy user | `useradd -r -s /bin/bash shankarawell && chown -R shankarawell: /var/www/shankarawell && sed -i 's/User=root/User=shankarawell/' /etc/systemd/system/shankarawell.service && systemctl daemon-reload && systemctl restart shankarawell` |
| P0 | Move DB into deploy tree | `mkdir -p /var/www/shankarawell/data && mv /home/z/my-project/db/custom.db /var/www/shankarawell/data/ && update .env DATABASE_URL=file:./data/custom.db` |
| P1 | Document build pipeline | Create `BUILD.md` with `npm run build && tar -czf ...` steps |
| P1 | Add monitoring | `curl -f https://shankarawell.yapsidarussalam.or.id/ || alert` cron |
| P2 | Enable Prisma migration tracking | Add `npx prisma migrate status` to deploy checklist |

---

## 🔑 Key Patterns Discovered (Reusable)

### 1. Custom Node.js HTTPS Proxy (Multi-Tenant)
**File:** `/var/www/yapsi-landing/https-proxy.js`
- Single process holds ALL public ports (3980-3997)
- Terminates TLS with wildcard cert
- Routes by port → internal app port (digit-match: 398X→408X)
- Sets `x-yapsi-site` header for app routing
- Adds security headers (HSTS, CSP, etc.) on ALL responses
- Rewrite non-static paths to `/` for SPA routing

### 2. Cloudflare Token Tunnel (No Config File)
- `cloudflared --no-autoupdate tunnel run --token <TOKEN>`
- Ingress rules managed in Cloudflare ZeroTrust Dashboard
- Origin: `https://127.0.0.1:3980` (proxy TLS, not app HTTP)
- Two tunnels for redundancy (Akun A + Akun B)

### 3. Next.js Standalone + Static Image Optimization
- `next.config.ts`: `images.unoptimized: true`
- All images pre-converted to WebP via PIL (`scripts/optimize_images.py`)
- Served from `/images/*.webp` with `Cache-Control: max-age=2592000`
- CF `cf-cache-status: HIT` on static assets
- Homepage = SSG (prerendered) — no dynamic APIs in RootLayout

### 4. Zero-Downtime Deploy (Standalone Swap)
```
standalone/          ← current (active)
standalone.prev/     ← previous (rollback ready)
start.sh             ← cd standalone && PORT=4080 node server.js
```

### 5. Port Mapping Scheme (Owner-Enforced)
| Unit Type | Public Port | Internal Port | Example |
|---|---|---|---|
| YAPSI core | 399X | 3999/400X | main:3990→3999, panti:3991→4001 |
| NON-YAPSI | 398X | 408X | shankarawell:3980→4080 |
| Special (sirat) | 3901 | 3901 | own HTTPS |

**Reference Doc:** `/root/PORT_MAPPING.md` (single source of truth)

### 6. GitHub PAT Multi-Account + Repo Creation via API (NEW - 2026-10-31)
When gh CLI is unavailable or token scope needs verification:

```bash
# 1. PAT stored in JSON credential file
cat /root/credential/github.pat.json
# { "lokah1945": "github_pat_...", "smahud": "github_pat_..." }

# 2. Verify token scope BEFORE repo creation
TOKEN=$(cat /root/credential/github.pat.json | grep <account> | sed 's/.*: "//; s/".*//')
curl -s -I -H "Authorization: token $TOKEN" https://api.github.com/user | grep -i "x-oauth-scopes"

# 3. Create repo via REST API (works without gh CLI)
curl -s -X POST -H "Authorization: token $TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/user/repos \
  -d '{"name":"LandingPage_Shankara","private":true,"description":"..."}'

# 4. Push with PAT-embedded remote URL
ssh <host> "cd <project> && git remote add origin https://${TOKEN}@github.com/<owner>/<repo>.git && git push -u origin main"
```

**Account Selection Rule:** Check which account owns existing `LandingPage_*` repos → use that account for consistency.

```bash
# Quick check
for acct in lokah1945 smahud; do
  TOKEN=$(get_pat $acct)
  curl -s -H "Authorization: token $TOKEN" https://api.github.com/users/$acct/repos?per_page=100 | grep -c "LandingPage_"
done
```

---

## 📋 Audit Commands Used (Reference)

```bash
# Phase 0: SSH & Host
ssh yapsi 'hostname && uptime && whoami'

# Phase 1: Project Discovery
ssh yapsi "find / -maxdepth 3 -name 'shankarawell' -type d 2>/dev/null"

# Phase 2: Stack
ssh yapsi "cat /var/www/shankarawell/standalone/package.json"

# Phase 3: DB
ssh yapsi "cat /var/www/shankarawell/standalone/.env"

# Phase 4: Services
ssh yapsi "systemctl status shankarawell yapsi-main cloudflared cloudflared2nd"
ssh yapsi "ss -tlnp | grep -E '3980|3990|4080|3999'"

# Phase 5: Build/Deploy
ssh yapsi "ls -la /var/www/shankarawell/standalone/"

# Phase 6: Config
ssh yapsi "cat /var/www/shankarawell/start.sh"
ssh yapsi "cat /var/www/yapsi-landing/https-proxy.js | head -100"
ssh yapsi "cat /etc/systemd/system/shankarawell.service"

# Phase 7: Verification
curl -I https://shankarawell.yapsidarussalam.or.id/
curl -k https://127.0.0.1:3980/
curl http://127.0.0.1:4080/
```

---

## 🔗 Cross-References

- **Same Host, Different App:** `references/2026-10-27-sirat-audit.md` — SIRAT audit (custom HTTPS proxy v10, Prisma/PostgreSQL, no git remote)
- **Same Host, DB Recon:** `ssh-server-discovery-and-recon/references/2026-10-28-jibas-mariadb-recon.md` — JIBAS MariaDB on port 33445
- **Git Init Pattern:** `ilma-git-automation/references/2026-10-31-shankarawell-git-init.md` — Git init on tarball-deployed project
- **Port Scheme Doc:** `/root/PORT_MAPPING.md` on VPS

---

## 💡 Lessons for Future Audits

1. **Check for git repo FIRST** — many tarball deploys have zero version control on VPS
2. **Verify DB location** — SQLite often lives outside deploy path (`/home/...`)
3. **Proxy architecture matters** — custom Node proxy means no Nginx/Caddy config to check
4. **Cloudflare token tunnels** — no local `config.yml`; ingress = Dashboard
5. **Digit-match ports** — predictable, document in `PORT_MAPPING.md`
6. **Root service user** — common in quick deploys, flag for hardening
7. **Static asset strategy** — unoptimized + manual WebP + CF cache = GTmetrix A achievable