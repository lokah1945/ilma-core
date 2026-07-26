---
name: openclaw-backup-architecture
description: OpenClaw credential/backup architecture discovery — how to find files outside workspace backups
triggers:
  - backup credential search
  - find api_key.json backup
  - restore credential files
  - workspace backup missing files
---

# OpenClaw Backup Architecture Discovery

## Key Discovery (2026-04-21)

### CRITICAL: `/root/credential/` is OUTSIDE workspace
- Workspace backups (`/root/backup/openclaw/workspace-*.tar.xz`) **DO NOT** include `/root/credential/`
- Credential directory lives at `/root/credential/` which is a sibling to `.openclaw/` — NOT inside workspace
- This means credential files (api_key.json, .pem files, etc.) are **never** in workspace backup archives

### Credential Backup Locations
```
/root/credential/                          ← Primary credential store
  api_key.json                              ← Current (may be partial/truncated)
  api_key.json.backup-YYYYMMDD-HHMMSS       ← Local timestamped backups
  api_key.json.save                         ← Named backup (often more complete)
  *.pem                                     ← Certificates/keys
```

### Backup Search Order for Credentials
1. `/root/credential/` — local backups with timestamp naming
2. `/root/backup/openclaw/pre-upgrade-YYYY-MM-DD-HHMM/` — these directories sometimes contain credential folders
3. `/root/backup/openclaw/auth-backup-*.json` — OpenClaw auth format (different from api_key.json)

### Important File Formats
- `api_key.json` — ILMA format: `{"provider": {"keys": ["key1", "key2"], "description": "...", "env_var": "..."}}`
- `auth-backup-*.json` — OpenClaw profiles format: `{"profiles": {"name:global": {"type": "api_key", "provider": "...", "key": "..."}}}`
- These are **different formats** — cannot merge directly

### Key Masking in Backups
Many backup files contain masked keys (e.g., `sk-pro...PVAA`) — actual key values were replaced before backup. Full keys may only exist in current active file or environment variables.

## ILMA SOT (2026-06+) — supersedes this for runtime credentials

Since 2026-05, the **canonical** credential store for ILMA is MongoDB:

```
host: 172.16.103.253  port: 27017
db:   credentials
user: quantumtraffic   pass: ***REDACTED-SEE-.env***   authSource: admin   directConnection: True
collection: llm_providers  (8-field credential-only shape since 2026-06-19)
```

Schema (post-2026-06-19 cleanup):
```
{_id, provider, account_email, api_key, key_status, is_active,
 added, added_by, restored_at, restored_by, account_status}
```

See `ilma-sot-credential-retrieval` for read-only audit/retrieval recipes,
cross-provider format anomaly scan, and masking detection.
See `ilma-runtime-mongodb-migration` for runtime code that joins this
with `models`, `providers`, and `model_intelligence` collections.

### CRITICAL PITFALL (2026-06-19): restored keys may be PLACEHOLDERS

`restored_by: 'sot_reverse_restore'` on a doc means the API key was
inserted by the reverse-restore script (typical around hard DB
transitions). The value often **looks like a key** but is actually a
literal placeholder (`sk-cp-...S-Ig`, len 125, prefix `sk-cp-` which
is not a known provider standard).

**Detection:**

```python
docs = list(db.llm_providers.find({}, {"_id": 0, "provider": 1, "api_key": 1, "key_status": 1}))
for d in docs:
    k = d.get("api_key", "") or ""
    if d.get("key_status") in ("UNVERIFIED", "TIMEOUT") or k.startswith("***...") or "..." in k[:8]:
        flag(f'{d["provider"]} key looks MASKED — restored_at/audit required')
```

**Cross-provider format comparison** (audit pattern): for `minimax` in
2026-06-19 audit, `api_key` started with `sk-cp-` and was 125 chars,
but every other provider in the DB used a brand-matching prefix
(`sk-pro-` openai, `sk-or-` openrouter, `wrappe` wrapper-nvidia, `xai-`
xai). **The single anomalous shape is the red flag** — it almost
certainly is a placeholder, not a live key.

**Always verify-before-using:** do not trust any UNVERIFIED/TIMEOUT key
that came from `sot_reverse_restore`. Run the platform's own
`auth status` / a real API smoke test against the key's claimed provider
before declaring it usable. For `minimax` specifically, `mmx-cli auth
status` or a direct `curl` to `https://api.minimax.io/anthropic/v1/messages`
proves validity.

---

## Verification Commands

```bash
# Legacy (pre-SOT) credential discovery — still works for offline restore
ls -la /root/credential/                          # check for local backups
find /root/backup -name "*credential*" -type d     # find credential-containing backup dirs
find /root/backup -name "auth-backup-*.json"      # find OpenClaw auth backups

## Verification Commands

```bash
# Legacy (pre-SOT) credential discovery — still works for offline restore
ls -la /root/credential/                          # check for local backups
find /root/backup -name "*credential*" -type d     # find credential-containing backup dirs

## Trial & Error Findings (2026-04-21)
- `workspace-2026-04-21-0039-backup.tar.gz` → no api_key.json inside (workspace-only)
- `workspace-BACKUP-20260415_172819.tar` → no credential files
- `pre-upgrade-2026-04-13-2346/credential/` → only .md and .pem, no api_key.json
- All api_key.json variants in /root/credential/ had identical masked content
