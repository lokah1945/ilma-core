---
name: mongodb-two-way-sync
description: "Build and operate MongoDB two-way sync between a local replica set and a remote instance. Covers: local MongoDB install + rs init, sync engine (change streams bidirectional), anti-loop design (origin tags NOT direction tags), _id preservation on insert, $set/$inc conflict avoidance, resume token flood prevention, conflict resolution per-DB policy, periodic reconcile, systemd service, centralized connection config. 10/10 E2E verified. Engine: scripts/ilma_two_way_sync.py. Config: sot/ilma_mongo_config.py."
triggers:
  - "mongodb two way sync"
  - "mongodb bidirectional replication"
  - "local to remote mongodb sync"
  - "change stream sync"
  - "mongodb replica set sync"
  - "sync daemon mongodb"
  - "ilma-sync-daemon"
  - "mongodb local remote replicate"
  - "ilma_two_way_sync"
  - "ilma_mongo_config"
  - "mongodb anti loop"
  - "resume token flood"
---

# MongoDB Two-Way Sync (class-level)

## When to use

- Bos says: "sync MongoDB lokal dan remote", "two-way sync", "bilateral DB replication",
  "change stream sync", "sync daemon", "local MongoDB harus sama dengan Yapsi"
- You need to keep two MongoDB instances in real-time sync (change stream based)
- You need to debug a sync loop (infinite document replication)
- You need to understand why change stream events are being skipped
- You need to add a new DB/collection to the existing sync

## Architecture overview

```
Yapsi (172.16.103.253:27017)  ←──ilma-sync-daemon──→  VPS Local (127.0.0.1:27017)
      REMOTE                                              LOCAL (PRIMARY READ)
         │                                                      │
         │              Change Stream (bidirectional)           │
         │  ←──────────────────────────────────────────────→    │
         │     local_to_remote  │  remote_to_local              │
         │                                                      │
   credentials DB ───── sync ───── credentials DB               │
   QuantumTrafficDB ── sync ──── QuantumTrafficDB                │
```

- **LOCAL is PRIMARY READ** for all ILMA operations (lowest latency)
- **REMOTE is backup/authoritative for QuantumTrafficDB** (remote_wins policy)
- **CREDENTIALS is local_wins** (local VPS is authoritative for credentials)
- Sync engine: `scripts/ilma_two_way_sync.py`
- Centralized config: `sot/ilma_mongo_config.py`
- Daemon service: `ilma-sync-daemon.service` (systemd --user)

## 10-Phase Build Sequence

| Phase | Description | Key output |
|-------|-------------|------------|
| P1 | Install MongoDB 7.0 local + init replica set rs1 | `mongod` active on 127.0.0.1:27017 |
| P2 | Build sync engine (`ilma_two_way_sync.py`) | Change stream watchers, conflict resolution |
| P3 | Initial seed (remote → local bulk copy) | 82K+ docs copied |
| P4 | Change Stream watchers (2 directions × 2 DBs) | 4 concurrent watcher threads |
| P5 | Conflict resolution (per-DB policy) | `credentials` = local_wins, `QuantumTrafficDB` = remote_wins |
| P6 | Oplog replay / gap recovery | Resume token persistence |
| P7 | Periodic reconcile (6-hourly) | Count-based audit |
| P8 | Systemd services + timers | `ilma-sync-daemon.service` |
| P9 | E2E testing (10 scenarios) | 10/10 PASSED |
| P10 | Update ILMA pipeline wiring | All SOT files read from local |

## CRITICAL pitfalls (the ones that caused real damage)

### P-SYNC-1: MongoDB change stream `ns.coll` vs `ns.collection`

**Bug:** Accessing `change.get("ns", {}).get("collection", "")` returns
`None` for database-level change streams. The actual field name is `coll`,
not `collection`.

```python
# ❌ WRONG — always returns None for db-level streams
coll_name = change.get("ns", {}).get("collection", "")

# ✅ CORRECT — try both keys, MongoDB uses "coll"
ns = change.get("ns", {})
coll_name = ns.get("coll") or ns.get("collection") or ""
```

**Impact:** Without this fix, ALL events are skipped (coll_name is empty
→ early return None), making the sync completely silent except for deletes
(which don't need `fullDocument` to extract collection name).

### P-SYNC-2: Anti-loop must use ORIGIN tags, NOT direction tags

**Bug:** Tagging synced documents with `_sync_source = direction`
(e.g. `"local_to_remote"`) causes infinite replication loops.
When the opposite watcher sees the document, `direction` is different
so the anti-loop check passes → re-sync → infinite loop (21K+ duplicate
docs created in seconds).

**Root cause:** The direction model fails because:
1. Local user inserts doc (no `_sync_source`)
2. `local_to_remote` watcher processes it, writes to remote with `_sync_source="local_to_remote"`
3. `remote_to_local` watcher sees the remote doc, `_sync_source="local_to_remote"` ≠ `"remote_to_local"` → NOT skipped!
4. Document written back to local with `_sync_source="remote_to_local"` → bounce begins

**Fix:** Use **origin tags** (`"local"` or `"remote"`) + **double-sided skip**:

```python
# Tag with ORIGIN, not direction
source_tag = "local" if direction == "local_to_remote" else "remote"

# Anti-loop: skip if doc was originally from EITHER side
# (it already exists where it needs to be)
if direction == "local_to_remote" and event_source == "local":
    return None  # Our own write on remote
if direction == "remote_to_local" and event_source == "remote":
    return None  # Our own write on local
# ALSO prevent bounce (doc already on target side)
if direction == "local_to_remote" and event_source == "remote":
    return None  # Remote doc already on remote — no need to send
if direction == "remote_to_local" and event_source == "local":
    return None  # Local doc already on local — no need to send
```

**Golden rule:** If a document has `_sync_source` set at all, it has already
been synced by one direction or the other. Only documents WITHOUT
`_sync_source` (fresh user writes) should be processed.

### P-SYNC-3: _id must be preserved on insert

**Bug:** `doc.pop("_id", None)` removes the _id, then `insert_one(doc)`
lets MongoDB generate a new ObjectId. The synced document has a DIFFERENT
_id from the source.

```python
# ❌ WRONG — loses original _id
doc_id_val = doc.pop("_id", None)
doc = _add_sync_metadata(doc, source_tag)
target_coll.insert_one(doc)  # Gets new ObjectId!

# ✅ CORRECT — put _id back before insert
doc_id_val = doc.pop("_id", None)
doc = _add_sync_metadata(doc, source_tag)
if doc_id_val is not None:
    doc["_id"] = doc_id_val
target_coll.insert_one(doc)   # Preserves original _id
```

### P-SYNC-4: $set and $inc on the same field causes MongoDB error

**Bug:** Using `$set: {_sync_generation: 1}` AND `$inc: {_sync_generation: 1}`
in the same update operation causes a conflicting operator error.

```python
# ❌ WRONG — $set and $inc conflict on _sync_generation
update_fields[SYNC_GEN_FIELD] = 1
set_obj = {"$set": update_fields, "$inc": {SYNC_GEN_FIELD: 1}}

# ✅ CORRECT — only $inc for the generation counter
# Remove _sync_generation from $set payload
set_obj = {"$set": update_fields, "$inc": {SYNC_GEN_FIELD: 1}}
# (don't add SYNC_GEN_FIELD to update_fields)
```

### P-SYNC-5: Resume token writes to sot_sync_state cause stream flood

**Bug:** Every change stream event saves a resume token to `sot_sync_state`.
This write generates a NEW change stream event, which saves another token,
creating an exponential flood. With `full_document="updateLookup"`, each
token-save event also carries a snapshot, filling the change stream buffer.

**Fix:**
1. Filter `sot_sync_state` from the pipeline (`ns.coll` `$nin` skip list)
2. Also skip `sot_sync_state` in application-level processing (belt + suspenders)
3. Batch resume token saves (write every N events or every T seconds, not per-event)

### P-SYNC-6: Resume tokens reference pre-fix events

After patching the sync engine (e.g. fixing P-SYNC-1 or P-SYNC-2), old
resume tokens still point to events generated by the buggy code. These
stale events may have wrong `ns.coll` values, missing `_sync_source`, etc.

**Fix:** Clear all resume tokens after a sync engine code change:
```python
for db_name in ["credentials", "QuantumTrafficDB"]:
    local[db_name]["sot_sync_state"].delete_many({})
```
Then restart the daemon. Change streams will start from "now" with no
resume token, missing only events during the restart gap.

## Centralized connection config

All ILMA modules MUST import MongoDB connection params from `sot/ilma_mongo_config.py`:

```python
from ilma_mongo_config import MONGO, MONGO_LOCAL, MONGO_REMOTE, get_local_client, get_remote_client

# READ from local (default)
client = get_local_client()

# ADMIN on remote
remote = get_remote_client()

# Legacy code that does `from X import MONGO` — MONGO = MONGO_LOCAL now
```

**Never hardcode** `host="172.16.103.253"` or `username="quantumtraffic"` in
new code. The `ilma_mongo_config.py` module reads all values from env vars
or `.env` file, with sensible defaults pointing to LOCAL.

## Batch-patching existing files

When migrating from remote-hardcoded to local-default, use this pattern:

```bash
# Find all files with hardcoded remote MongoDB
grep -rn "172.16.103.253" sot/ --include="*.py" | grep -v __pycache__ | grep -v "ilma_mongo_config.py"

# Batch replace via sed
find sot/ -name "*.py" -exec sed -i 's/MONGO_HOST = "172.16.103.253"/MONGO_HOST = "127.0.0.1"/g' {} +
find sot/ -name "*.py" -exec sed -i 's/host="172.16.103.253"/host="127.0.0.1"/g' {} +
find sot/ -name "*.py" -exec sed -i 's/username="quantumtraffic"/username="ilma_sync"/g' {} +

# Verify zero remaining
grep -rn "172.16.103.253" sot/ --include="*.py" | grep -v "ilma_mongo_config.py" | wc -l
# Should be 0
```

## E2E test script (10 scenarios)

```python
# Run after any sync engine change to verify correctness
WAIT = 5  # seconds per operation

# T1: Local insert → remote
tl.insert_one({"_id": "t1", "val": "from_local"})
time.sleep(WAIT)
assert tr.find_one({"_id": "t1"})["val"] == "from_local"

# T2: Remote insert → local
tr.insert_one({"_id": "t2", "val": "from_remote"})
time.sleep(WAIT)
assert tl.find_one({"_id": "t2"})["val"] == "from_remote"

# T3: Local update → remote
tl.update_one({"_id": "t1"}, {"$set": {"updated": True}})
time.sleep(WAIT)
assert tr.find_one({"_id": "t1"})["updated"] is True

# T4: Remote update → local
tr.update_one({"_id": "t2"}, {"$set": {"updated": True}})
time.sleep(WAIT)
assert tl.find_one({"_id": "t2"})["updated"] is True

# T5: Local delete → remote
tl.insert_one({"_id": "t5", "val": "del_me"}); time.sleep(WAIT)
tl.delete_one({"_id": "t5"}); time.sleep(WAIT)
assert tr.find_one({"_id": "t5"}) is None

# T6: Remote delete → local
tr.insert_one({"_id": "t6", "val": "del_r"}); time.sleep(WAIT)
tr.delete_one({"_id": "t6"}); time.sleep(WAIT)
assert tl.find_one({"_id": "t6"}) is None

# T7-T8: Conflict policies
assert _get_conflict_policy("credentials") == "local_wins"
assert _get_conflict_policy("QuantumTrafficDB") == "remote_wins"

# T9: Cross-DB insert
tl2.insert_one({"_id": "qt1", "val": "q_local"})
time.sleep(WAIT)
assert tr2.find_one({"_id": "qt1"})["val"] == "q_local"

# T10: No duplication loop
assert tl.count_documents({}) <= 4
assert tr.count_documents({}) <= 4
```

## Service management

```bash
# Check status
systemctl --user status ilma-sync-daemon.service

# Restart after code change
systemctl --user restart ilma-sync-daemon.service

# View logs
tail -f /root/.hermes/profiles/ilma/run/ilma-sync-daemon.log

# Health check (both local and remote)
python3 sot/ilma_mongo_config.py
```

## Verified status

**2026-06-23** — Full two-way sync operational:
- 10/10 E2E scenarios PASSED
- Zero duplication loop (P-SYNC-2 verified)
- _id preservation confirmed (P-SYNC-3 verified)
- 20+ SOT files migrated from remote to local reads
- Centralized config (`ilma_mongo_config.py`) in use
- `ilma-sync-daemon.service` active, watching 2 DBs × 2 directions

## Support files

- `references/two-way-sync-debug-log-2026-06-23.md` — Full debugging log
  with 5 root causes found and fixed (ns.coll, anti-loop, _id, $set/$inc,
  resume token flood), chronological diagnosis steps, E2E results
- `scripts/sync_e2e_test.py` — Re-runnable 10-scenario E2E test script.
  Run after any sync engine change: `cd /root/.hermes/profiles/ilma && python3 scripts/sync_e2e_test.py`

## Cross-references

- `ilma-runtime-mongodb-migration` — P-75: local-read default after sync install
- `ilma-sot-cascade-pipeline` — data reconciliation (one-shot), whereas this
  skill covers real-time continuous sync
- `ilma-sot-credential-retrieval` — read-only credential lookup against SOT
