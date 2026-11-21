---
name: ssh-server-discovery-and-recon
description: Class-level skill for the recurring task of finding the right SSH credentials for a target host when given ambiguous or potentially outdated key material, then verifying a service is actually running. Triggers when user mentions checking SSH / VPS / remote server / "lihat service" / debugging access to a host whose keys were lost or mixed up with other credentials, OR when told an outdated config file (vps_project.json, infra map, etc.) for a host's IP/port/key that needs verification against ground truth.
---

# SSH Server Discovery & Infrastructure Recon — Class Skill

This skill handles a recurring pattern ILMA hits in production: the user says "check my project at host X / IP Y / use the key in Z" and the reality does not match the documentation.

## When to use

- User mentions any remote host whose credentials or services are uncertain
- A config file (vps_project.json, infra map, deployment manifest) lists ports/IPs/keys that may be stale
- After a server restart, the infrastructure may have come back on different ports
- You have multiple `.pem` files in `/root/credential/` that you cannot tell apart
- A call to `ssh user@ip` returns "Permission denied (publickey,password)" and the right key/user combo is unknown

## The Core Playbook — 4-step matrix discovery

### Step 1: Probe the host before any key work
Always run TCP-level liveness first. This separates "host unreachable" from "auth failure":

```bash
(timeout 3 bash -c "</dev/tcp/<IP>/22" && echo "PORT_22_OK") 2>&1
ssh-keyscan -H <IP> 2>/dev/null | head -3   # banner + key algo
```

If `ssh-keyscan` returns `ssh-ed25519` but your keys are all RSA, note the mismatch — most likely the key listed in old config was rotated.

### Step 2: Matrix-scan credentials
For each candidate key + user combination in parallel:

```bash
for key in /root/credential/*.pem; do
  for user in root huda openclaw ubuntu admin; do
    out=$(timeout 6 ssh -i "$key" -o BatchMode=yes \
                      -o ConnectTimeout=3 -o StrictHostKeyChecking=accept-new \
                      "${user}@<IP>" 'echo CONN_$(hostname)_$(whoami)' 2>&1 | head -1)
    [[ "$out" == CONN_* ]] && echo "✓ [$key -> $user]: $out"
  done
done | sort -u
```

You rarely need more than 4 keys × 4 users. **Stop as soon as you see one CONN line; do not continue the loop past a match** to avoid noise.

#### Key Format Pre-check (NEW INSIGHT - 2026-06-05)
Before running the matrix scan, check key formats - this saves 50% of auth time:

```bash
# Check key formats in /root/credential/
for key in /root/credential/*.pem; do
  format=$(head -1 "$key")
  echo "$(basename $key): $format"
done

# RSA PEM keys often FAIL when server expects ssh-ed25519
# Prefer OPENSSH PRIVATE KEY format keys
```

Key catalog for `/root/credential/` on Bos's LXC:
| File | Format | Last seen working on |
|---|---|---|
| `smahud.pem` | OpenSSH | 172.16.103.200 FullStackVPS root |
| `lokah1945.pem` | OpenSSH | 172.16.103.253 YAPSIDarussalam root |
| `smahud_new.pem`, `smahud1945.pem` | OpenSSH | usually invalid/rotated |
| `private_key.pem` | RSA PEM | ❌ does NOT work (format mismatch) |
| `~/.ssh/id_ed25519` | OpenSSH ED25519 | may be stale (host-specific binding) |

**Critical:** Key format matters! Server supported `ssh-ed25519` but `private_key.pem` was RSA format - it would never work. **Always check `head -1` of key files first.**

**Always run `ssh-keygen -y -f <pem>` first** to confirm the key parses; some `.pem` files on shared credential dirs are encrypted and need a passphrase.

### Step 3: Persist the winning combo to /root/.ssh/config

Once a working combination is found:

```bash
cat >> /root/.ssh/config <<EOF

Host <shortcut>
    HostName <IP>
    User <user>
    IdentityFile <path>
    IdentitiesOnly yes                # don't offer wrong keys to wrong host
    StrictHostKeyChecking accept-new  # auto-accept on first connect
    ServerAliveInterval 30
    ServerAliveCountMax 4
EOF
chmod 600 /root/.ssh/config
ssh-keyscan -H <IP> 2>/dev/null >> /root/.ssh/known_hosts
ssh <shortcut> 'echo OK_$(hostname) && exit'   # verify
```

Always set `IdentitiesOnly yes` — otherwise ssh-agent will offer every matching key and waste auth attempts.

### Step 4: Verify the actual services (don't trust the docs)

Once in, the breakpoint: **the doc says "service on port X", reality may be on Y**. Use orthogonal signals in this order:

```bash
ssh <shortcut> '
  echo "=== PM2 (preferred runtime marker) ==="
  pm2 list 2>&1 | head -20
  echo "=== Listening TCP ports ==="
  ss -tlnp 2>/dev/null | grep -E ":(3000|3001|3200|3201|1337|8080|80|443)\b"
  echo "=== Node processes (look for next-server, strapi, pnpm) ==="
  ps -eo pid,user,cmd | grep -iE "(next|strapi|node|pm2)" | grep -v grep
  echo "=== Disk + uptime ==="
  df -h / | tail -1; uptime
'
```

For each candidate service port, hit it externally and capture both the HTTP status AND the `<title>` from the HTML — the title is the fastest way to disambiguate which app is actually serving:

```bash
for port in 3000 3100 3200 3201 1337 1338; do
  out=$(curl -s --max-time 6 -o /tmp/p$port.html -w "HTTP=%{http_code} bytes=%{size_download}\n" \
       http://<IP>:$port/)
  title=$(grep -oE '<title>[^<]+</title>' /tmp/p$port.html | head -1)
  echo "  port $port -> $out | $title"
done
```

### Step 4b: Asset existence check (when user names a domain that should exist)

When user asks "is website X built yet / does project Y exist here", verify with FOUR orthogonal signals before claiming "not built":

```bash
# 1. Domain public DNS (is the domain even registered?)
getent hosts <domain> 2>&1   # NXDOMAIN = not registered (yet)
                                  # ip1, ip2 = resolves, often to a reverse proxy

# 2. Multi-domain sweep (catches typos / TLD variants)
for d in <domain> <domain-without-tld> <base-domain> <base-domain-wrong-tld>; do
  out=$(getent hosts "$d" 2>&1 | head -1)
  echo "  $d -> ${out:-NXDOMAIN}"
done

# 3. Source code under /root/multisite-blog/  (or similar source tree)
ssh <shortcut> '
  ls -la /root/multisite-blog/web-nextjs/sites/ 2>&1
  echo "--- grep across sites + configs ---"
  grep -rliE "(<keyword1>|<keyword2>)" \
    /root/multisite-blog/web-nextjs/sites/ \
    /root/multisite-blog/web-nextjs/src/ \
    /root/multisite-blog/cms-strapi/config/ \
    /root/multisite-blog/cms-strapi/src/ 2>/dev/null
'

# 4. Live process check (PM2 / docker / ss)
ssh <shortcut> '
  pm2 list 2>&1 | grep -iE "<app-name>"
  ss -tlnp 2>&1 | grep -E ":(<expected-port>)\b"
'
```

If ALL FOUR signals are negative (DNS NXDOMAIN + no source grep matches + no PM2 process + no listening port), then it is safe to claim **"website belum dibuat"**. If even one matches, escalate to user before concluding — there may be partial state.

### Step 4c: Public IP vs Internal port trap

A resolved DNS `A` record resolving to a public IP (e.g. `103.164.173.46`) does NOT mean the local app on `172.16.103.200:3201` is exposed. DNS often points to a separate LiteSpeed/Nginx reverse-proxy host running something else (often WordPress). Always probe `curl -sI http://<public-ip>/` to see the actual server header and `<title>` before claiming "yes the site is live".

```bash
curl -sI --max-time 8 "http://<public-ip>/" 2>&1 | grep -iE "(server|location|content-type|x-powered)"
```

| Public IP server header | Means |
|---|---|
| `LiteSpeed` + body contains `wp-content` | WordPress host — local Next.js/Strapi NOT exposed at this domain |
| `nginx` + `X-Powered-By: Next.js` | Correct reverse proxy, local app IS exposed |
| `nginx` bare + `<title>Strapi Admin</title>` after `/admin` redirect | Correct, Strapi exposed |

### Step 5: Framework fingerprinting (when title alone isn't enough)

WordPress vs Next.js vs Strapi — quick tells:

| Signal | WordPress | Next.js | Strapi |
|---|---|---|---|
| Server header | `LiteSpeed` / `Apache` / `nginx` (no X-Powered-By) | often `nginx` + `X-Powered-By: Next.js` | usually `nginx` bare |
| `<link rel="...">` | `wp-json/` | `_next/static/css/...` | `<link rel="stylesheet">` `strapi-admin` |
| Body markers | `wp-content/plugins/`, `pagelayer-` CSS, `/?p=` URLs | `__next` div classes, `_app.js` references | `/admin` redirect, `<title>Strapi Admin</title>` |
| Real port bake-in | 80/443 only with LiteSpeed | 3000/3001/3100/3201 (any non-default) | 1337 (default) or 3200/8080 (custom) |

If a doc claims "Next.js at port 3000" but `ss` shows the service at 3201 with frame metadata matching Next.js — the doc is wrong, not the host.

## Known infra map (Bos — last audit 2026-11-11)

Save as starting hypothesis, then verify per Step 4:

| Host alias | IP | User | Key (format) | Host-Specific? | Real ports |
|---|---|---|---|---|---|
| `yapsi` | 172.16.103.253 | root | `lokah1945.pem` (OpenSSH) | ✅ REQUIRED | 80/443 (LiteSpeed), 3990-3997 (Node HTTPS proxy), 3999/4001-4007 (Next.js internal), 27017 (MongoDB), 33445 (MariaDB), 5432 (PostgreSQL), 20241/20242 (cloudflared) |
| `fullstack` | 172.16.103.200 | root | `smahud.pem` (OpenSSH) | ✅ REQUIRED | 3100 (prelanding), 3200 (Strapi), 3201 (Next.js blog) |
| `localhost` | 127.0.0.1 | bos-user varies | n/a | N/A | 9100 (model-wrapper), 8642 (Hermes API), 9222 (browser CDP) |

**IMPORTANT - Updated 2026-06-05:** Keys are HOST-SPECIFIC. Each VPS has different `authorized_keys` with different key fingerprints:
- `lokah1945.pem` works **ONLY** on `172.16.103.253` (yapsi)
- `smahud.pem` works **ONLY** on `172.16.103.200` (fullstack)
- `~/.ssh/id_ed25519` does NOT work on either (likely expired)
- `private_key.pem` (RSA format) does NOT work at all (format mismatch)

**Never trust `vps_project.json` key field alone - always verify with matrix scan (Step 2) or check this table.**

Documented vs real port deltas are common — re-verify every time.

### Step 6: Database Service Discovery & Recon (NEW - 2026-10-28)

Once SSH access is verified (Step 1-3), if the user asks about a database service (MariaDB/MySQL/PostgreSQL) on the remote host:

#### 6.1 Locate DB credentials
- Check common config paths: `/var/www/**/include/database.config.php`, `/var/www/**/config/database.php`, `/root/.my.cnf`, `~/.pgpass`, `/etc/mysql/debian.cnf`
- For JIBAS/PHP apps: look for `$db_host`, `$db_user`, `$db_pass`, `$db_name` in config files
- Note: port may be non-standard (e.g., `33445` not `3306`)

#### 6.2 Verify connectivity & enumerate
```bash
# Test connection
ssh <shortcut> "mysql -h <host> -P <port> -u <user> -p'<pass>' -e 'SELECT 1;'"

# List all databases
ssh <shortcut> "mysql -h <host> -P <port> -u <user> -p'<pass>' -e 'SHOW DATABASES;'"

# For each DB of interest, count tables
for db in db1 db2 db3; do
  ssh <shortcut> "mysql -h <host> -P <port> -u <user> -p'<pass>' \$db -e 'SHOW TABLES;' 2>/dev/null | tail -n +2 | wc -l"
done
```

#### 6.3 Compare live schema vs reference dump (installer/backup)
```bash
# Get live tables for target DB
ssh <shortcut> "mysql -h <host> -P <port> -u <user> -p'<pass>' <db> -e 'SHOW TABLES;'" | tail -n +2 | sort > /tmp/live_tables.txt

# Extract tables from dump for same DB
grep -A 1000 "Current Database: \`<db>\`" /path/to/dump.sql | grep "CREATE TABLE" | sed 's/.*\`\([^`]*\)\`.*/\1/' | sort > /tmp/dump_tables.txt

# Diff
comm -23 /tmp/live_tables.txt /tmp/dump_tables.txt   # tables in live but not dump
comm -13 /tmp/live_tables.txt /tmp/dump_tables.txt   # tables in dump but not live
comm -12 /tmp/live_tables.txt /tmp/dump_tables.txt   # common tables
```

#### 6.4 Deep schema comparison for specific tables
```bash
# Get CREATE TABLE from live
ssh <shortcut> "mysql -h <host> -P <port> -u <user> -p'<pass>' <db> -e 'SHOW CREATE TABLE <table>\\G'"

# Get CREATE TABLE from dump
sed -n '/CREATE TABLE \`<table>\`/,/UNLOCK TABLES/p' /path/to/dump.sql | head -50
```

#### 6.5 Check for triggers, FK constraints, charset/engine
```bash
# Triggers
ssh <shortcut> "mysql -h <host> -P <port> -u <user> -p'<pass>' <db> -e 'SHOW TRIGGERS;'"

# Foreign keys
ssh <shortcut> "mysql -h <host> -P <port> -u <user> -p'<pass>' <db> -e 'SELECT TABLE_NAME, CONSTRAINT_NAME, REFERENCED_TABLE_NAME FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE WHERE REFERENCED_TABLE_NAME IS NOT NULL AND TABLE_SCHEMA = \"<db>\";'"

# Charset/Engine
ssh <shortcut> "mysql -h <host> -P <port> -u <user> -p'<pass>' <db> -e 'SHOW TABLE STATUS;'"
```

---

## Pitfalls

1. **Don't keep scanning past first success.** Once one CONN_ line prints, stop the loop. Repeated auth attempts can trip fail2ban.
2. **`Connection refused` ≠ wrong key.** Check `ssh-keyscan -p 22 <IP>` first; SSH port may simply not be open from your network. Try a different IP first.
3. **`Permission denied (publickey,password)` after a server restart** can be transient (init script failures). Try once more after 30s.
4. **Don't trust `vps_project.json` blindly.** That file is 2 months stale in many Bos projects. Always re-probe.
5. **Internal port vs Public IP.** A Next.js app at `172.16.103.200:3201` is NOT exposed at `yapsi.or.id` — DNS for the public site points to a different IP (often via Nginx/LiteSpeed reverse proxy). Verify the public IP separately.
6. **Avoid destructive ops on first contact.** No `rm -rf`, no service restarts, no log clears until the user explicitly approves. Initial recon is read-only.
7. **Approval gates will fire on HTTP requests to private IPs.** The Hermes runtime's security scanner prompts the user even for `http://172.16.103.200:3201/` curls. That's expected and will pass — but make sure the message is informed (mention you're doing recon, what IP, what host).
8. **Per-host key pinning: a same-named .pem can authorize only one host.** Verified 2026-06-20: `lokah1945.pem` works on `172.16.103.253` (YAPSIDarussalam) but is REJECTED on `172.16.103.200` (FullStackVPS); conversely `smahud.pem` works on `.200` but is rejected on `.253`. Each `authorized_keys` on each host has different fingerprints. **Updated 2026-06-05:** This is the #1 cause of "Permission denied" after finding the right key format. Always verify key-host binding with a quick test run, don't assume.

9. **Don't trust ~/.ssh/id_ed25519 as the "canonical" key.** Even if format matches, the key may be expired or not authorized on target hosts. Verify each key file against the actual server's `authorized_keys` via Step 2 matrix scan.

10. **Key format mismatch is a common silent failure.** Server advertising `ssh-ed25519` support will reject RSA PEM-format keys (`-----BEGIN RSA PRIVATE KEY-----`) outright. Always check `head -1` of key files before testing - this saves 50% of auth tries.
9. **Don't fabricate a working combo when evidence says otherwise.** If Step 2 produces zero CONN lines, your answer is "no match found — escalate to user" not "I assume key X works because vps_project.json says so". The skill's contract is evidence, not intent.
10. **Don't claim "website belum dibuat" until all 4 assets are verified negative.** Single-signal saying "no process" is not enough when source code, DNS, or sibling app may be present. Always run Step 4b. Quick test: if user asks "apakah website X sudah dibuat?" and you only check PM2, you will miss the case where the source is staged but not deployed — and you'll give a wrong answer that's hard to recover from once the user believes it.

## Related skills
- `claude-code` — Claude Code CLI orchestration; especially see Pitfall #3 about running as root, which fits this server-discovery context
- `system-administration` — unread stub; not useful yet
- `devops` — unread stub; not useful yet
- `cf-bypass-browser-ua-pattern` — for HTTP provider API key rotation, unrelated
- `domain` — Hermes ingested skill for domain reconnaissance and website discovery

## Reference files
- `references/2026-06-20-fullstackvps-audit.md` — full transcript of the 2026-06-20 matrix-scan on FullStackVPS (smahud.pem + 172.16.103.200 + port reassignments 3100/3200/3201). Use as a worked example when port docs say 3000/3001/1337 but reality disagrees.
- `references/vps-project-json-surgical-update.md` — recipe for safely updating `vps_project.json` (or any SOT-infra JSON) when ports/keys have drifted from doc reality.
- `references/2026-08-02-vpsfullstack-web-recon.md` — VPSFullStack website reconnaissance (2026-08-02). Documents 3 active Next.js/Strapi websites on internal IP 172.16.103.200 with port mappings 3100/3200/3201. Use this after a Step 4 service audit discovers mismatch.
- `references/2026-06-05-172.16.103.253-key-discovery.md` — NEW: SSH key format analysis and host-specific binding discovery for 172.16.103.253 (YAPSIDarussalam). Documents why RSA PEM vs OpenSSH format matters and which keys work on which hosts.
- `references/2026-10-27-sirat-audit.md` (in `vps-project-deep-audit` skill) — Full SIRAT project audit on 172.16.103.253 (YAPSIDarussalam) using this skill's methodology. Demonstrates Phase 0-4 execution with actual outputs: SSH config alias `yapsi` with `lokah1945.pem`, git repo clean but no remote, 23-model Prisma schema, systemd service active with custom Node HTTPS proxy on :3901, fresh DB with 4 users/6 units/0 letters, 8 stale next-server processes from previous deploy. Cross-reference for VPS audit workflows.
