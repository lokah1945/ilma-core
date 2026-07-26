# Reference: 2026-06-20 Audit — FullStackVPS Next.js + Strapi Verification

## What happened
Bos asked ILMA to "Check project saya terkait blog berbasis nextjs strapi."
ILMA initially concluded the project was dead (because vps_project.json said ports 3000/1337 which were not listening) and reported that `yapsi.or.id` was WordPress + LiteSpeed, not Next.js+Strapi.
Bos clarified: "Server mati. Sudah saya nyalakan lagi" — i.e. the host had been restarted, that's why no services were up.
After re-probing, the project was fully alive.

This case study captures the resolution path and the verification matrix for future similar cases.

## The crucial lesson
**Don't audit infrastructure once and report "dead".** When a service is unresponsive, check whether the host itself is up (TCP-only probe), and ask the user if they recently restarted/changed the host BEFORE concluding "dead / migrated / project killed". vps_project.json is at least 2 months stale in Bos's infra.

## Probe sequence (verbatim, from this session)

### Step 1 — when service was unreachable on first probe
```bash
# User said "blog Next.js + Strapi" with credential key dir /root/credential

# Initial state — server appears DOWN
for ip in 172.16.103.200 172.16.103.201 172.16.103.250 172.16.103.253; do
  ssh -i /root/credential/lokah1945.pem root@$ip 'echo OK_$(hostname)_$(whoami)' 2>&1 | head -1
done
# → only 172.16.103.253 (YAPSIDarussalam) responded with OK
# → all others: Permission denied (publickey,password)
```

### Step 2 — when user said "server sudah dinyalakan lagi"
```bash
# Re-probe with full matrix
for key in /root/credential/{smahud,private_key,smahud_new,smahud1945,lokah1945}.pem; do
  for user in root huda openclaw; do
    out=$(timeout 5 ssh -i "$key" -o BatchMode=yes -o ConnectTimeout=3 -o StrictHostKeyChecking=accept-new \
                  "${user}@172.16.103.200" 'echo CONN_$(hostname)_$(whoami)' 2>&1 | head -1)
    [[ "$out" == CONN_* ]] && echo "✓ [$key -> $user]: $out"
  done
done | sort -u

# → 2 matches: smahud.pem -> root, private_key.pem -> root (fullstack)
# → smahud.pem and private_key.pem have IDENTICAL SHA256 fingerprint (duplicate keys)
# → vps_project.json said smahud.pem was the right key — CORRECT
# → previous attempt using lokah1945.pem was wrong because that key belongs to 172.16.103.253 (a different host)
```

### Step 3 — once SSH works, verify services
```bash
ssh -i /root/credential/smahud.pem root@172.16.103.200 '
  pm2 list
  ss -tlnp
  ps -eo pid,user,cmd | grep -iE "(next|strapi|node|pm2)" | grep -v grep
'

# → Port real: 3100, 3200, 3201 (NOT 3001, 1337, 3000 as vps_project.json said)
# → Strapi v5.38.0 on 3200 (default 1337 was reassigned)
# → Next.js v15.5.12 blog on 3201 (default 3000 was reassigned)
# → Pre-landing Next.js v15.5.12 on 3100 (default 3001 was reassigned)
```

### Step 4 — HTTP fingerprint to disambiguate apps
```bash
for port in 3000 3100 3200 3201 1337 3001; do
  out=$(curl -s --max-time 8 -o /tmp/p$port.html -w "HTTP=%{http_code} bytes=%{size_download}\n" "http://172.16.103.200:$port/")
  title=$(grep -oE '<title>[^<]+</title>' /tmp/p$port.html | head -1)
  echo "  port $port -> $out | $title"
done

# → 3100: HTTP=200, title="Glepseit.Online" → prelanding
# → 3200: HTTP=302→/admin, title="Strapi Admin" → CMS
# → 3201: HTTP=200, title="GlimpseIt — Smart Navigation in the Financial World" → main blog
```

### Step 5 — public DNS check (often misleading)
```bash
getent hosts yapsi.or.id       # → 103.164.173.46 (public IP, NOT 172.16.103.200)
curl -sI https://yapsi.or.id/  # → server: LiteSpeed, Body shows wp-content/plugins/pagelayer → WordPress, NOT Next.js

# Lesson: yapsi.or.id resolves to a SEPARATE public host running WordPress.
# Internal blog Next.js+Strapi is not (yet) fronted at yapsi.or.id.
# Reverse proxy / DNS routing for glanceit.online or similar (TBD) is what links them publicly.
```

## Final working state (operational hand-off)
- SSH shortcut saved to `/root/.ssh/config`:
  ```
  Host fullstack
      HostName 172.16.103.200
      User root
      IdentityFile /root/credential/smahud.pem
      IdentitiesOnly yes
      StrictHostKeyChecking accept-new
      ServerAliveInterval 30
      ServerAliveCountMax 4
  ```
- Workspace on the remote: `/root/multisite-blog/{web-nextjs,cms-strapi}/`
- Audit log: `/root/conversation-bos/2026-06-20_claude-code-test/AUDIT-multisite-blog-2026-06-20.md`

## Approval-gate side-effect
The Hermes runtime's security scanner fires on EVERY curl to a private IP and asks the user to approve. Don't be surprised mid-stream — it's a known cost of retrieving HTTP from private ranges and the user does approve in seconds. Mention proactively in your report that this will happen so the user understands the gate is expected, not your bug.

## Stack snapshot for the blog framework
- Next.js 15.5.12, React 19, Tailwind, lucide-react, class-variance-authority, @strapi/blocks-react-renderer
- Strapi v5.38.0, PostgreSQL (localhost:5432), Redis (localhost:6379)
- PM2 v6.0.14 (God Daemon at /root/.pm2), node v22.22.0 via NVM
- WS-tracked directory has `sites/` (multi-tenant hint) but unclear which domains
- No git repo! `/root/multisite-blog/` is not under version control — flagged in the audit, awaiting Bos authorization to `git init`
