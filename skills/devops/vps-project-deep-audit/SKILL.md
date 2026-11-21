---
name: vps-project-deep-audit
description: Class-level skill for conducting comprehensive deep audits of application projects running on remote VPS hosts. Covers SSH access, git repo analysis, dependency audit, database schema inspection, running service verification, build log analysis, configuration review, and structured findings report. Trigger when user asks "analisa mendalam project X di VPS", "cek kondisi repo", "audit project", or wants a full health check of a deployed application.
---

# VPS Project Deep Audit — Class Skill

This skill handles the recurring pattern: **user points at a VPS + project name and wants a thorough technical audit** — repo state, database, running services, build health, config, and a structured report with findings/priorities.

## When to Use

- User says "analisa mendalam project [NAME] di VPS [IP/HOST]"
- User asks "cek kondisi repo local saat ini" on a remote host
- User wants "audit project" or "health check" of a deployed app
- Pre-deployment verification, post-incident forensics, or handoff documentation

## Prerequisites

- SSH access to target VPS (use `ssh-server-discovery-and-recon` skill first if credentials uncertain)
- Project path known or discoverable (`/root/project/<name>`, `/var/www/<name>`, `/opt/<name>`)
- Read access to: git repo, database, systemd, logs, config files

---

## The 7-Phase Audit Playbook

### Phase 0: SSH Access & Host Baseline
```bash
# Verify SSH works (reuse ssh-server-discovery-and-recon Step 2-3)
ssh <host-alias> 'hostname && uptime && whoami && df -h / | tail -1'
```
Capture: hostname, uptime, user, disk space.

### Phase 1: Project Discovery & Git Repo State
```bash
# Find project directories
ssh <host> "find / -type d -name '*<project>*' -o -name '*<PROJECT>*' 2>/dev/null | head -20"

# Git status at source repo
ssh <host> "cd <source-path> && git status && git log --oneline -10 && git remote -v && git branch -a"
```
Capture: working tree clean/dirty, current commit, remotes, branches, last 10 commits.

### Phase 2: Application Stack & Dependencies
```bash
# Package manager & lockfile
ssh <host> "cat <source-path>/package.json"   # or pyproject.toml, Cargo.toml, go.mod, etc.
ssh <host> "ls -la <source-path>/node_modules 2>/dev/null | wc -l"  # dep count
```
Capture: framework, version, key deps, lockfile freshness.

### Phase 3: Database Schema & Data Health
```bash
# Prisma / SQLAlchemy / Django / Rails / raw SQL
ssh <host> "cat <source-path>/prisma/schema.prisma"  # or equivalent

# Live counts
ssh <host> "sudo -u postgres psql -d <db> -c 'SELECT count(*) FROM \\\"Table\\\";' ..."

# Migration status
ssh <host> "cd <source-path> && npx prisma migrate status 2>&1"
```

#### 3b: Multi-Database PHP/JIBAS Pattern (NEW - 2026-10-28)
For JIBAS/PHP apps with multiple databases on non-standard ports:
```bash
# 1. Locate DB config (not .env — PHP apps often use config.php)
ssh <host> "cat /var/www/<app>/include/database.config.php"

# 2. Extract: $db_host (may be 'localhost:33445'), $db_user, $db_pass, $db_name

# 3. Enumerate ALL databases on that port
ssh <host> "mysql -h <host> -P <port> -u <user> -p'<pass>' -e 'SHOW DATABASES;'"

# 4. Count tables per DB to understand scope
for db in db1 db2 db3; do
  ssh <host> "mysql -h <host> -P <port> -u <user> -p'<pass>' \$db -e 'SHOW TABLES;' 2>/dev/null | tail -n +2 | wc -l"
done

# 5. Compare live vs installer/backup dump
# Get live tables for target DB
ssh <host> "mysql -h <host> -P <port> -u <user> -p'<pass>' <db> -e 'SHOW TABLES;'" | tail -n +2 | sort > /tmp/live.txt
# Extract from dump
grep -A 1000 "Current Database: \`<db>\`" /path/to/dump.sql | grep "CREATE TABLE" | sed 's/.*\`\([^`]*\)\`.*/\1/' | sort > /tmp/dump.txt
# Diff
comm -23 /tmp/live.txt /tmp/dump.txt   # extra in live
comm -13 /tmp/live.txt /tmp/dump.txt   # missing in live

# 6. Check cross-DB triggers (critical for JIBAS)
ssh <host> "mysql -h <host> -P <port> -u <user> -p'<pass>' <db> -e 'SHOW TRIGGERS;'"
# Look for triggers writing to OTHER databases (e.g., jbsakad → jbsjs.syncdata2)
```
Capture: all DB names, table counts per DB, live vs baseline drift, trigger cross-DB dependencies, FK constraints, charset/engine.

### Phase 4: Running Services & Process Verification
```bash
# Systemd units
ssh <host> "systemctl list-units | grep -i <project>"
ssh <host> "systemctl status <service-name> --no-pager"

# Process tree
ssh <host> "ps aux | grep -E '(next|node|python|java|go|pm2)' | grep -v grep"

# Listening ports
ssh <host> "ss -tlnp | grep -E ':(3000|3001|3100|3200|3201|3900|3901|80|443)\\b'"

# Service logs (last 50 lines)
ssh <host> "journalctl -u <service> -n 50 --no-pager"
ssh <host> "tail -50 /var/log/<project>/*.log 2>/dev/null"
```
Capture: service status (active/failed), PID, memory, CPU, ports, recent errors.

### Phase 5: Build & Deploy Artifacts
```bash
# Build logs
ssh <host> "cat /var/log/<project>-build.log 2>/dev/null | tail -50"
ssh <host> "cat /var/log/<project>-build2.log 2>/dev/null | tail -50"

# Deploy path vs source
ssh <host> "ls -la /var/www/<project>/"
ssh <host> "diff -r <source-path>/<key-files> /var/www/<project>/<key-files> 2>&1 | head -30"
```
Capture: build success/failure, warnings, deploy sync status, standalone vs source.

### Phase 6: Configuration & Secrets Review
```bash
# Environment (sanitized)
ssh <host> "cat /var/www/<project>/.env 2>/dev/null | sed 's/=.*/=***/' | head -30"
ssh <host> "cat <source-path>/.env.example"

# Reverse proxy / TLS
ssh <host> "cat /etc/nginx/sites-enabled/<project> 2>/dev/null || cat /etc/caddy/Caddyfile 2>/dev/null || cat <project-path>/Caddyfile 2>/dev/null"
ssh <host> "ls -la /etc/letsencrypt/live/<domain>/ 2>/dev/null"

# Systemd unit file
ssh <host> "cat /etc/systemd/system/<project>.service"
```
Capture: env vars present (secrets masked), TLS cert validity, proxy config, systemd hardening.

### Phase 7: Structured Findings Report
Generate a markdown report with:
1. **Executive Summary** — one-paragraph health verdict
2. **Architecture Overview** — stack, ports, data flow diagram (text)
3. **Database** — schema, counts, migration status
4. **Services** — systemd, processes, ports, logs
5. **Build/Deploy** — status, warnings, sync
6. **Config/TLS** — env, proxy, certs
7. **Findings Table** — severity (Critical/High/Medium/Low), issue, evidence, recommendation
8. **Strengths** — what works well
9. **Priority Recommendations** — P0/P1/P2 with commands

---

## Pitfalls

1. **Don't assume source = deploy.** Always compare `/root/project/x` vs `/var/www/x` — drift is common.
2. **Don't trust `git remote -v` alone.** Empty remotes = no backup/sync path. Flag as Critical.
3. **Database user may not be `postgres`.** Check `.env` for `DATABASE_URL` user, or try app user.
4. **Build logs may be in multiple places.** Check `/var/log/`, project dir, journalctl.
5. **Multiple service instances = trouble.** `ps aux | grep next` showing 8 processes usually means stale deploys or duplicate systemd. Flag.
6. **TLS certs ≠ app exposure.** Custom Node proxy (like SIRAT's `https-proxy.js`) means no Caddy/Nginx. Verify actual listening port.
7. **Secrets in `.env` — mask before output.** Never print actual passwords/keys in report.
8. **Permission denied on `sudo -u postgres`?** Try `psql -d <db>` as app user from `.env`.
9. **TypeScript build errors skipped?** Check `next.config.ts` for `ignoreBuildErrors: true` — flag as Medium.
10. **Zero data in prod tables?** Could be fresh deploy or failed seed. Check `bootstrap-admin`, `seed` scripts.

---

## Output Template (Markdown)

```markdown
# 📋 DEEP AUDIT REPORT — <PROJECT> @ <HOST> (<IP>)

**Date:** YYYY-MM-DD | **Auditor:** ILMA | **Session:** <session-id>

## 🎯 Executive Summary
<1 paragraph: overall health, blocker count, deploy readiness>

## 🏗️ Architecture Overview
| Component | Technology | Version | Port/Path |
|---|---|---|---|
| Runtime | Node.js / Python / ... | x.y.z | — |
| Framework | Next.js / FastAPI / ... | x.y.z | — |
| Database | PostgreSQL / MySQL / ... | x.y | 5432 |
| ORM | Prisma / SQLAlchemy / ... | x.y.z | — |
| Reverse Proxy | Custom Node / Caddy / Nginx | — | 3901 (HTTPS) |
| Process Manager | systemd / PM2 / Docker | — | — |

## 🗄️ Database
- **Tables:** N | **Migrations:** N applied / N pending
- **Row Counts:** Table1: N, Table2: N, ...
- **Issues:** [list]

## ⚙️ Services
| Service | Status | PID | Mem | CPU | Ports |
|---|---|---|---|---|---|
| <name> | active/failed | NNN | XXM | X% | NNNN |

## 📦 Build & Deploy
- **Last Build:** SUCCESS/FAIL (timestamp)
- **Warnings:** [list]
- **Source ↔ Deploy Sync:** CLEAN / DRIFT (details)

## 🔐 Config & TLS
- **Env File:** present, chmod 600
- **TLS Cert:** valid, expires YYYY-MM-DD, issuer Let's Encrypt
- **Proxy:** Custom Node.js HTTPS proxy → internal Next.js

## ⚠️ Findings
| Sev | Issue | Evidence | Recommendation |
|---|---|---|---|
| 🔴 Critical | No git remote | `git remote -v` empty | Add origin, push, enable branch protection |
| 🟡 Medium | 8 next-server processes | `ps aux \| grep next` | Kill stale, verify single systemd |
| 🟢 Low | TypeScript checks skipped | `next.config.ts: ignoreBuildErrors: true` | Enable strict build in CI |

## ✅ Strengths
- [bullet list]

## 🎯 Recommendations
| Priority | Action | Command |
|---|---|---|
| P0 | Setup git remote | `cd /root/project/x && git remote add origin ... && git push -u origin main` |
| P0 | Bootstrap admin | `cd /root/project/x && npm run bootstrap-admin` |
| P1 | Enable TS checks | Edit `next.config.ts` → `ignoreBuildErrors: false` |

---

## Related Skills

- `ssh-server-discovery-and-recon` — Phase 0 prerequisite (finding right key/host)
- `devops` — general DevOps patterns
- `system-administration` — service management
- `ilma-wrapper-fleet-ops` — for wrapper/service fleet audits
- `ilma-wrapper-port-verification` — port mapping verification

## Reference Files

- `references/2026-10-27-sirat-audit.md` — Full SIRAT project audit on 172.16.103.253 (YAPSIDarussalam). Worked example of all 7 phases with actual outputs, findings table, and recommendations.
- `references/2026-10-31-shankarawell-audit.md` — Shankara Wellness & Sanctuary audit on same host. Next.js 16 + custom Node proxy (yapsi-main) + Cloudflare token tunnel + SQLite DB. Key patterns: zero-downtime deploy via `standalone`/`standalone.prev` swap, static WebP optimization (CF HIT), SSG homepage, digit-match port scheme (398X→408X), centralized TLS proxy for multi-unit. Findings: no source repo on VPS, DB outside deploy path, service runs as root.
- `references/2026-10-28-jibas-mariadb-recon.md` (in `ssh-server-discovery-and-recon` skill) — JIBAS MariaDB multi-database schema recon on same host. Demonstrates Phase 3 (Database) technique: non-standard port 33445, config.php credential extraction, 16 DB enumeration, live vs installer dump diff (61 vs 63 tables), cross-DB trigger risk (jbsakad→jbsjs.syncdata2). Cross-reference for multi-database JIBAS/PHP app audits.
- `ilma-git-automation/references/2026-10-31-shankarawell-git-init.md` — Git init on production deploy (ShankaraWell). Pattern for initializing git repo on a tarball-deployed project with no source repo on VPS. Covers .gitignore for Next.js standalone, commit docs+scripts only, PAT auth fallback.
- `references/2026-10-31-auto-sync-credential-file.md` — Auto-sync credential file (github.pat.json) to VPS using inotifywait + systemd. Covers: sync script, watch script, systemd service, debounce, initial sync, verification, reusable template for any credential file. Created from Bos directive: "Selalu pastikan file github.pat.json selalu sync dengan VPS" → "Buat otomatis, setiap file berubah, maka auto sync".