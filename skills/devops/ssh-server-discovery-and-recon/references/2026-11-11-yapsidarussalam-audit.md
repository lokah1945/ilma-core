# Reference: YAPSI Darussalam VPS Audit (2026-11-11)

## Session Context
User requested: "Cek kan vps yapsi 172.16.103.253 - Website yapsi landing page, user password admin nya apa"
Corrected IP from 172.16.103.254 to 172.16.103.253.

## Key Findings

### SSH Access
- **Host:** 172.16.103.253 (YAPSIDarussalam)
- **Working key:** `/root/credential/lokah1945.pem` (OpenSSH format)
- **User:** root
- **Key fingerprint:** ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC7BoHJEwbTdlbHJzTCNXyGYH/u0C6ViyZWIBlyrk3Ubz451fuR1oI3MlwUA7dA2o0emDQ57PXvq7Qv9PyajHxzUEMN2+TghTj68+qvIdGkh/tmH9JvOGRaJJhvTCj+hlZKPwdLyH7/LuwM2hxBl0Iyj4u8wiWADj5ZZYK0UoysSK2W4tOnNylidJA64WnpEcCYiXFBWIHPXKdAocO+f+kY/5gwXwDb1zvu3fxx6Qx/wJ2oyE4AqnLENyLc8AZvs7q6B8OkJG/hCgVs1dfU1ydhjBhE9WXl2lDb77FJI54QUGZccxNTvqK09VtbHBvpjP3IuET9ZDolDe6VQtz2iK9h

### Service Architecture (systemd units)
| Service | Unit | Internal Port | Public Port (HTTPS via proxy) | Subdomain |
|---------|------|---------------|-------------------------------|-----------|
| yapsi-main | Main landing | 3999 | 3990 | www.yapsidarussalam.or.id |
| yapsi-panti | Panti Asuhan | 4001 | 3991 | panti.yapsidarussalam.or.id |
| yapsi-paud | PAUD (KB & RA) | 4002 | 3992 | kb-ra.yapsidarussalam.or.id |
| yapsi-mi | MI Darussalam | 4003 | 3993 | mi.yapsidarussalam.or.id |
| yapsi-mts | MTs Darussalam | 4004 | 3994 | mts.yapsidarussalam.or.id |
| yapsi-masjid | Masjid Nasrullah | 4005 | 3995 | masjid.yapsidarussalam.or.id |
| yapsi-ponpes | Pondok Pesantren | 4006 | 3996 | pondok.yapsidarussalam.or.id |
| yapsi-tahfiz | Rumah Tahfiz | 4007 | 3997 | tahfiz.yapsidarussalam.or.id |

### Reverse Proxy & Edge
- **LiteSpeed** on ports 80/443 (public HTTPS)
- **Node HTTPS proxy** (`https-proxy.js`) on ports 3990-3997
- **cloudflared** tunnels on 20241/20242 → Cloudflare edge
- **Next.js apps** internal only (3999, 4001-4007), not directly exposed

### Databases
- MongoDB: 27017
- MariaDB: 33445 (non-standard)
- PostgreSQL: 5432

### Admin Authentication
**Location:** `/admin` route (Next.js app router: `app/admin/page.tsx` → `components/admin/admin-app.tsx`)

**Auth mechanism:** Custom HMAC JWT (not NextAuth)
- `lib/auth.ts`: `createToken()` / `verifyToken()` using HS256 with `JWT_SECRET`
- Cookie name: `yapsi_admin`
- Session TTL: 7 days
- Credentials checked via `checkCredentials()` using `timingSafeEqual` on `ADMIN_USERNAME` / `ADMIN_PASSWORD` from `.env`

**Credentials (all units share same):**
```
ADMIN_USERNAME=admin
ADMIN_PASSWORD=dXTnywQUHEfaV3kb35ya
JWT_SECRET=O4kIR8PXbGJcwD4PvcN9Yhp1s_jt51MoS8x6fi_v1t1Nf8d9hndkInVis4Z96bSl
```

**Unit-specific notes:**
- Main, panti, mi, mts, masjid, ponpes, tahfiz: have `.env` with above credentials
- PAUD (kb-ra): **NO .env file** → admin login fails (fail-closed design)
- Auth scope: Main = global (news + all sections); Units = only that unit's landing content

### Admin Panel Features
- Multi-language (ID/EN) content editing per section
- News/article management (markdown + front-matter)
- File upload (images → `/api/upload`)
- Settings API: `/api/settings` (GET/PUT), `/api/news` (CRUD), `/api/auth` (POST/DELETE/PUT password)
- Agent integration: `POST /api/agent/articles` with `x-agent-token` header
- Import/export JSON (news + settings)
- Per-unit isolation: `YAPSI_UNIT` env var scopes admin to `units.<key>` sections only

## Updated Infra Map Entry

| Host alias | IP | User | Key (format) | Host-Specific? | Real ports |
|---|---|---|---|---|---|
| `yapsi` | 172.16.103.253 | root | `lokah1945.pem` (OpenSSH) | ✅ REQUIRED | 80/443 (LiteSpeed), 3990-3997 (proxy), 3999/4001-4007 (Next.js internal), 27017 (Mongo), 33445 (MariaDB), 5432 (PG), 20241/20242 (cloudflared) |

## Lessons for Skill

1. **Systemd service discovery > PM2** — This VPS uses systemd, not PM2. Always check `systemctl list-units | grep -i <pattern>` first.

2. **Multi-unit Next.js = multiple systemd services + shared codebase** — Each unit has its own service, port, .env, and subdomain. Admin panel uses `YAPSI_UNIT` env to scope.

3. **Admin credentials in .env per unit** — Not in database, not in central config. Check `/var/www/yapsi-<unit>/.env` for each.

4. **LiteSpeed + Node proxy architecture** — Public HTTPS on 443 (LiteSpeed) → Node proxy on 3990-3997 → Next.js internal on 3999/4001-4007. Never hit Next.js directly from outside.

5. **Cloudflare tunnel masks real ports** — cloudflared on 20241/20242 means public domain may route differently than direct IP.

6. **Fail-closed when .env missing** — PAUD unit has no auth because no .env. This is by design (code checks `if (!U || !P) return false`).

7. **Custom auth ≠ standard patterns** — HMAC JWT in cookie, not NextAuth, not JWT in header. Must read `lib/auth.ts` to understand.

## Commands Used (for replay)
```bash
# SSH matrix scan (Step 2)
for key in /root/credential/*.pem; do
  for user in root huda openclaw ubuntu admin; do
    timeout 6 ssh -i "$key" -o BatchMode=yes -o ConnectTimeout=3 -o StrictHostKeyChecking=accept-new "${user}@172.16.103.253" 'echo CONN_$(hostname)_$(whoami)' 2>&1 | head -1
  done
done

# Service discovery (Step 4)
ssh -i /root/credential/lokah1945.pem root@172.16.103.253 'systemctl list-units | grep -i yapsi'
ssh -i /root/credential/lokah1945.pem root@172.16.103.253 'ss -tlnp | grep -v 127.0.0.1'

# Credential discovery
ssh -i /root/credential/lokah1945.pem root@172.16.103.253 'for u in panti paud mi mts masjid ponpes tahfiz; do cat /var/www/yapsi-$u/.env 2>/dev/null || echo "No .env"; done'

# Admin login test
curl -X POST https://www.yapsidarussalam.or.id/api/auth -H "Content-Type: application/json" -d '{"username":"admin","password":"dXTnywQUHEfaV3kb35ya"}'
```