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

## MongoDB SOT Backup/Restore (2026-11+)

### Full Credential DB Backup via mongoexport

```bash
# Export all collections from remote MongoDB (yapsi: 172.16.103.253)
cd /root/credential
for coll in providers llm_providers search_providers infra_providers crypto_exchanges messaging sessions system_credentials models model_benchmarks model_alias model_stats model_enrichment model_lifecycle_events model_capabilities model_intelligence model_audit_trail provider_lifecycle_events model_benchmark sot_schema_registry sot_backups sot_sync_state sot_jobs; do
  mongoexport --uri="mongodb://quantumtraffic:113333555555@172.16.103.253:27017/credentials?authSource=admin" \
    --collection="$coll" \
    --out="${coll}_$(date +%F_%H%M%S).json"
done
```

### Combine into Single JSON (canonical backup)

```python
import json, glob, os
from datetime import datetime

files = glob.glob('/root/credential/*_2026-11-14_*.json')
coll_map = {}
for f in files:
    if 'mongodb_backup_complete' in f:
        continue
    fname = os.path.basename(f)
    coll = '_'.join(fname.split('_')[:-1])
    if coll not in coll_map or os.path.getsize(f) > os.path.getsize(coll_map[coll]):
        coll_map[coll] = f

combined = {
    'backup_timestamp': datetime.utcnow().isoformat() + 'Z',
    'source': '172.16.103.253:27017/credentials',
    'collections': {}
}

for coll, f in coll_map.items():
    docs = []
    with open(f) as fp:
        for line in fp:
            line = line.strip()
            if line:
                try:
                    docs.append(json.loads(line))
                except json.JSONDecodeError as e:
                    print(f'Error in {f}: {e}')
    combined['collections'][coll] = docs

outfile = '/root/credential/mongodb_backup_complete.json'
with open(outfile, 'w') as f:
    json.dump(combined, f, indent=2, default=str)
```

### Output Format (canonical)

```json
{
  "backup_timestamp": "2026-11-14T16:07:34.953206Z",
  "source": "172.16.103.253:27017/credentials",
  "collections": {
    "llm_providers": [...],
    "search_providers": [...],
    "infra_providers": [...],
    "crypto_exchanges": [...],
    "messaging": [...],
    "providers": [...],
    "models": [...],
    "model_intelligence": [...],
    "model_capabilities": [...],
    ...
  }
}
```

### Restore to Local MongoDB

```bash
# Import single collection
mongoimport --uri="mongodb://localhost:27017/credentials" \
  --collection=llm_providers \
  --file=/root/credential/llm_providers_2026-11-14_230718.json

# Or import from combined (extract collection first)
python3 -c "
import json
with open('/root/credential/mongodb_backup_complete.json') as f:
    data = json.load(f)
import sys
for doc in data['collections']['llm_providers']:
    print(json.dumps(doc))
" | mongoimport --uri="mongodb://localhost:27017/credentials" --collection=llm_providers
```

### Key Collections for Credential Recovery

| Collection | Count | Purpose |
|------------|-------|---------|
| `llm_providers` | 26 | **Primary: LLM API keys** (nvidia, openrouter, minimax, blackbox, qwen, etc.) |
| `search_providers` | 7 | Search API keys (tavily, serper, you, artificial_analysis) |
| `infra_providers` | 13 | Dev/infra credentials (github, cloudflare, nvidia_build) |
| `crypto_exchanges` | 4 | Exchange API keys (nicehash, binance, tokocrypto) |
| `messaging` | 18 | Telegram bot tokens |
| `system_credentials` | 1 | Mikrotik, restricted system creds |
| `providers` | 77 | Provider catalog (metadata, endpoints, free_tier flags) |
| `models` | 1,290 | Full model catalog with capabilities |

### Verification After Restore

```bash
# Check counts match
mongosh "mongodb://localhost:27017/credentials" --eval "
['llm_providers','search_providers','infra_providers','crypto_exchanges','messaging','providers','models'].forEach(c => print(c + ': ' + db[c].countDocuments({})))
"

# Verify specific key format
mongosh "mongodb://localhost:27017/credentials" --eval "
db.llm_providers.find({}, {provider:1, account_email:1, api_key:1, key_status:1}).forEach(printjson)
"
```

## Verification Commands (Legacy pre-SOT)

```bash
# Legacy (pre-SOT) credential discovery — still works for offline restore
ls -la /root/credential/                          # check for local backups
find /root/backup -name "*credential*" -type d     # find credential-containing backup dirs
find /root/backup -name "auth-backup-*.json"      # find OpenClaw auth backups
```

## Trial & Error Findings (2026-04-21)
- `workspace-2026-04-21-0039-backup.tar.gz` → no api_key.json inside (workspace-only)
- `workspace-BACKUP-20260415_172819.tar` → no credential files
- `pre-upgrade-2026-04-13-2346/credential/` → only .md and .pem, no api_key.json
- All api_key.json variants in /root/credential/ had identical masked content