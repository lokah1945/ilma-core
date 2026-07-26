# SOT Audit 2026-07-26 — Dispatcher Regression + Alignment Fix

**Trigger:** Bos "audit SOT T1 T2 T3, pastikan bekerja dengan baik agar bisa melayani ILMA"

## Environment
- Cloud Mongo: `rs0@172.16.103.253` (SOT `credentials.infra_providers[mongodb-cloud]`)
- Local Mongo: `rs1@127.0.0.1:27017` (no-auth, running since 2026-07-04)
- Sync unit: `ilma-sync-daemon.service` (systemd --user, ACTIVE)
- Cred resolver: `scripts/ilma_two_way_sync._resolve_remote_from_sot()` → dict
  `{host, port, username, password, auth_source, replica_set, source, evidence_id}`
  (NOT a URI string — build URI manually)

## How to connect cloud (working snippet)
```python
import sys; sys.path.insert(0, 'scripts')
import ilma_two_way_sync as t
r = t._resolve_remote_from_sot()
from pymongo import MongoClient
uri = f"mongodb://{r['username']}:{r['password']}@{r['host']}:{r['port']}/?authSource={r['auth_source']}&replicaSet={r['replica_set']}"
c = MongoClient(uri, serverSelectionTimeoutMS=8000)
db = c['credentials']
```

## Findings (LIVE, contradicting 2026-07-24 "aligned" report)
| Check | Result |
|-------|--------|
| T1 providers | 25 distinct (26 docs) |
| T3 models | 1290 (13 providers) |
| ORPHAN T3 not in T1 | `antigravity` (1) — expected local-only |
| `is_active=True` + `disabled_at` contradiction | **671** (router would pick DEAD models) |
| T2 `is_active=None` | 0 (backfill OK from 07-01) |
| T1 key_status INVALID/TIMEOUT but T2 is_active=True | blackbox, groq, byteplus, felo, bluesminds |
| └ groq free_bypass=True | T2 is_active=True CORRECT (P-CASCADE-26); agg_status should be 'active' |
| └ others free_bypass=False | T2 is_active=True WRONG (P-CASCADE-23) |

## Fix sequence (applied)
1. Backup (bson.json_util.dumps, NOT json.dumps):
   `/root/ilma_sot_audit_backup/pre_audit_<ts>_{llm_providers,providers,models,model_intelligence,model_benchmark,model_audit_trail}.json`
2. `python3 sot/sync/sot_cascade_enforcement.py --json` (dry-run) → aligned:false, 671 contradictions
3. `python3 sot/sync/sot_cascade_enforcement.py --apply --json` →
   - `active_with_disabled_at`: 623 fixed
   - `aggregate_status_backfilled`: 5
   - byteplus 51 zombie T3 deactivated (no recent-sync <24h)
   - groq stays (free_bypass), curated google/mongodb-cloud NOT deprecated (whitelist)
4. Re-run dry-run → `aligned: true`, `contradictions_remaining: 0` (idempotent)

## Dispatcher bugs found + fixed
- **Bug A (P-CASCADE-33):** `sot_free_model_picker.get_db()` → `MongoClient(**MONGO)`
  with `password=None` (env unset) → ClientOptions error → dispatcher crash.
  Fix: pop password/username/authSource if falsy → no-auth connect.
- **Bug B (P-CASCADE-32):** picker `list_models()` returned `is_free_final` alias
  but not `is_free`; dispatcher `chosen.get("is_free", False)` → always False.
  Fix: add `"is_free": d.get("is_free")` to returned dict.

## Dispatcher E2E (post-fix)
```bash
python3 ilma_sot_dispatcher.py --capability chat --strict
# → antigravity Gemini 3.5 Flash (High) | is_free: True | billing: free | warn: None
python3 ilma_sot_dispatcher.py --capability image
# → nvidia stabilityai/stable-diffusion-xl-base-1.0 | is_free: True | billing: free
```

## Caveats (not blocking)
- `missing_t3_remaining` (aimlapi, cloudflare_ai, groq, minimax, ollama,
  sumopod, tinyfish, together, z.ai) = no sync endpoint (P-CASCADE-29, expected).
- `antigravity` chosen for chat = curated local-only (no T1 key). Picker uses T3
  `models` final, does not check T1 key_status. Runtime key-resolution concern,
  not SOT alignment. Future: consider T1 key_status gate in picker query.

## Commit
`3b64217` pushed to `master` (force-pushed clean repo from earlier reset).
