# FullStackVPS Session Summary (2026-06-20–21)

## SESI 1 — Claude Code Integration Setup
- **Goal:** gunakan Claude Code CLI sebagai subagent coding via ILMA
- **CLI location:** `/root/.local/bin/claude v2.1.183`
- **Cara kerja:** ILMA → `claude -p "task"` → hasil return ke ILMA
- **Pilihan penggunaan:**
  - Heavy coding → Claude CLI (Sonnet/Opus)
  - Task kecil → ILMA SubAgentRouter (free-tier)
  - Parallel 4-model → `ilma_claudecode_agent`
- **Pre-check wajib:** Auth, WD, Quota

## SESI 2 — FullStackVPS Access
- **Host:** `fullstack` = 172.16.103.200
- **Status semua service:** hidup (3/3 PM2 online)
- **Endpoint (REAL PORTS):**
  - Strapi CMS: http://172.16.103.200:3200 → `/admin`
  - Next.js Blog: http://172.16.103.200:3201 → *GlimpseIt*
  - Pre-landing Ads: http://172.16.103.200:3100 → *Glipseit.Online*
- **Last commit:** `77a1993` (Phase D, 2026-06-20)
- **Domain `yapsidarussalam.or.id`:** **TIDAK ada di server ini**

## SSH Shortcut
- `fullstack` — 172.16.103.200, pem: smahud.pem, user: root
- `yapsi` — 172.16.103.253, pem: lokah1945.pem, user: root