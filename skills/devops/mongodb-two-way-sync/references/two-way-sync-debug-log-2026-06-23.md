# MongoDB Two-Way Sync Debugging Log (2026-06-23)

## Session context
Building `ilma_two_way_sync.py` — bidirectional MongoDB sync between
VPS local (127.0.0.1:27017, rs1) and Yapsi remote (172.16.103.253:27017).

## Bug progression (chronological)

### Bug 1: Change stream events not reaching _process_change_event
**Symptom:** Daemon log showed "Change stream active" but no "Processing" entries.
Insert events from `_sync_test` collection were silently dropped.

**Root cause:** `ns.get("collection", "")` — MongoDB change stream uses key
name `"coll"`, not `"collection"`. Always returned empty string → early return.

**Diagnosis:** Direct test with `db.watch()` and print of raw change event:
```python
for change in stream:
    print(f"EVENT: op={change['operationType']} ns={change['ns']}")
```
Output showed `ns.coll='?'` (displayed as `?` but actual key is `coll`, value is the collection name).

**Fix:** `ns.get("coll") or ns.get("collection") or ""`

### Bug 2: sot_sync_state events flooding the change stream
**Symptom:** Change stream test captured events from `_sync_test` BUT also
captured thousands of events from `sot_sync_state` (resume token saves).

**Root cause:** Daemon writes resume tokens to `sot_sync_state` collection.
Each write triggers a change stream event. With `full_document="updateLookup"`,
each event includes a full document snapshot. The stream was dominated by
internal state events, hiding user collection events.

**Fix:**
1. Pipeline filter: `ns.coll` `$nin` skip list including `sot_sync_state`
2. Application-level skip in `_process_change_event` (belt + suspenders)
3. Batch resume token saves (every N events, not per-event)

### Bug 3: Infinite replication loop (21,630+ duplicate docs)
**Symptom:** After fixing bugs 1-2, a single insert generated thousands of
duplicate documents across both local and remote within seconds.

**Root cause:** Anti-loop used `_sync_source = direction` ("local_to_remote").
When remote_to_local watcher saw a doc with `_sync_source="local_to_remote"`,
the check `event_source == "remote_to_local"` was False → document NOT skipped →
written back to local with `_sync_source="remote_to_local"` → bounce × ∞.

**Diagnosis:** Inspecting remote `_sync_test` showed thousands of docs with
alternating `_sync_source` values and incrementing `_sync_generation`.

**Fix:** Replace direction tags with origin tags ("local" / "remote") and
add double-sided skip (skip own writes + skip bounces):
```python
source_tag = "local" if direction == "local_to_remote" else "remote"
# Skip own writes (the side we read from)
if direction == "local_to_remote" and event_source == "local": return None
if direction == "remote_to_local" and event_source == "remote": return None
# Skip bounces (doc from target side, already where it needs to be)
if direction == "local_to_remote" and event_source == "remote": return None
if direction == "remote_to_local" and event_source == "local": return None
```

### Bug 4: _id lost on insert → documents get new ObjectId
**Symptom:** Insert sync worked but `_id` changed from string (e.g. `"debug1"`)
to `ObjectId(...)`. `find_one({"_id": "debug1"})` returned None on target.

**Root cause:** `doc.pop("_id", None)` removed _id, `insert_one(doc)` without
_id → MongoDB auto-generates ObjectId.

**Fix:** Put `_id` back before insert:
```python
doc_id_val = doc.pop("_id", None)
doc = _add_sync_metadata(doc, source_tag)
if doc_id_val is not None:
    doc["_id"] = doc_id_val
target_coll.insert_one(doc)
```

### Bug 5: $set and $inc conflict on _sync_generation
**Symptom:** Update sync silently failed (MongoDB error on same field in
both operators).

**Root cause:** Code added `update_fields[SYNC_GEN_FIELD] = 1` to `$set`
payload while also using `$inc: {SYNC_GEN_FIELD: 1}`.

**Fix:** Remove `SYNC_GEN_FIELD` from the `$set` dict, only use `$inc`.

## E2E verification (10/10)

| # | Test | Result |
|---|------|--------|
| 1 | Local insert → remote | ✅ |
| 2 | Remote insert → local | ✅ |
| 3 | Local update → remote | ✅ |
| 4 | Remote update → local | ✅ |
| 5 | Local delete → remote | ✅ |
| 6 | Remote delete → local | ✅ |
| 7 | credentials: local_wins policy | ✅ |
| 8 | QuantumTrafficDB: remote_wins policy | ✅ |
| 9 | Cross-DB insert sync | ✅ |
| 10 | Zero duplicate loop | ✅ |

## Files modified

- `scripts/ilma_two_way_sync.py` — sync engine (5 bug fixes)
- `ilma_mongo_connection.py` — default host → 127.0.0.1
- `sot/ilma_mongo_config.py` — NEW centralized config
- `sot/enrichment/sot_free_model_picker.py` — MONGO → local
- 20+ SOT validator/enrichment/discovery scripts — hardcoded remote → local

## Key lesson

> Change stream field names in pymongo differ from what you'd expect.
> Always print a raw event to verify field structure before writing filters.
> The `ns.coll` vs `ns.collection` mistake is invisible until you test.
