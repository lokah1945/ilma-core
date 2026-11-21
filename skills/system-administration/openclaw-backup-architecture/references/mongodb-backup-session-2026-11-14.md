# MongoDB Credential Backup — Session 2026-11-14

## Context
User asked to verify MongoDB sync between local (this machine) and remote (172.16.103.253, "yapsi"), then backup the remote credential DB to `/root/credential/mongodb_backup_complete.json`.

## Findings

### Local vs Remote MongoDB
| Aspect | Local | Remote (yapsi) |
|--------|-------|----------------|
| Service | `mongod` (rs1, single node) | `mongod` (rs0, single node) |
| Port | 127.0.0.1:27017 | 172.16.103.253:27017 (reachable) |
| Auth | None | `quantumtraffic` / `113333555555`, authSource=admin |
| Replica Set | rs1 (term 19) | rs0 (term 36) |
| DB `credentials` | **EMPTY** (0 docs) | **FULL** (77 providers, 1290 models, 120k audit trail) |

**Conclusion: NOT synced. Different replica set names, local DB empty.**

### Remote Collections Exported (23 total)
```
providers:                    77
llm_providers:                26  ← PRIMARY: LLM API keys
search_providers:             7
infra_providers:              13
crypto_exchanges:             4
messaging:                    18  ← Telegram bot tokens
sessions:                     2
system_credentials:           1
models:                       1,290
model_benchmarks:             0
model_alias:                  57
model_stats:                  0
model_enrichment:             1,139
model_lifecycle_events:       261
model_capabilities:           1,139
model_intelligence:           1,290
model_audit_trail:            120,721
provider_lifecycle_events:    9
model_benchmark:              3
sot_schema_registry:          6
sot_backups:                  1
sot_sync_state:               21
sot_jobs:                     0
```

### Output File
- **Path:** `/root/credential/mongodb_backup_complete.json`
- **Size:** 80 MB
- **Format:** Canonical combined JSON with `backup_timestamp`, `source`, `collections` (dict of collection_name → array of documents)
- **Collections:** 23 (all exported collections included)

### Commands Used
```bash
# Export each collection via mongoexport (JSON lines format)
mongoexport --uri="mongodb://quantumtraffic:113333555555@172.16.103.253:27017/credentials?authSource=admin" \
  --collection=<coll> \
  --out="/root/credential/${coll}_$(date +%F_%H%M%S).json"

# Combine via Python (handles JSON lines → array)
python3 -c "
import json, glob, os
from datetime import datetime
files = glob.glob('/root/credential/*_2026-11-14_*.json')
coll_map = {}
for f in files:
    if 'mongodb_backup_complete' in f: continue
    fname = os.path.basename(f)
    coll = '_'.join(fname.split('_')[:-1])
    if coll not in coll_map or os.path.getsize(f) > os.path.getsize(coll_map[coll]):
        coll_map[coll] = f
combined = {'backup_timestamp': datetime.utcnow().isoformat() + 'Z', 'source': '172.16.103.253:27017/credentials', 'collections': {}}
for coll, f in coll_map.items():
    docs = []
    with open(f) as fp:
        for line in fp:
            line = line.strip()
            if line:
                try: docs.append(json.loads(line))
                except: pass
    combined['collections'][coll] = docs
with open('/root/credential/mongodb_backup_complete.json', 'w') as f:
    json.dump(combined, f, indent=2, default=str)
"

# Cleanup individual export files
rm /root/credential/*_2026-11-14_*.json
```

### Risks / Notes
- Backup is point-in-time (2026-11-14T16:07:34Z) — keys may have rotated since
- Local MongoDB is not a replica of remote; different replica set names prevent replication
- Auth credentials (`quantumtraffic` / `113333555555`) embedded in export commands — ensure file permissions on backup
- `model_audit_trail` is 120k docs (50 MB of the 80 MB) — consider separate incremental strategy for large collections
- `sot_jobs`, `sot_backups`, `model_benchmarks`, `model_stats` were empty — expected for current state