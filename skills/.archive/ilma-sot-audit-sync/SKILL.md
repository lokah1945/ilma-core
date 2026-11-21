---
name: ilma-sot-audit-sync
description: Audit the SOT (System of Truth) MongoDB store end-to-end (Tier-1 credentials → Tier-3 jobs/sync/audit) and debug/recover the local↔cloud two-way sync daemon. Use when Bos asks to "audit SOT", "compare local vs cloud", "check active providers in llm_providers", "sync not syncing / stuck", "T1 T2 T3 audit", or "SOT tidak sinkron".
triggers:
  - "audit SOT"
  - "compare local vs cloud mongo"
  - "provider aktif di llm_providers"
  - "sync daemon stuck / tidak sync"
  - "T1 T2 T3 audit"
  - "SOT tidak identik"
  - "cek infra_providers / system_credentials"
---

# ILMA SOT MongoDB Audit & Two-Way Sync Recovery

SOT = single source of truth, disimpan di MongoDB. Dua instance:
**LOCAL** (127.0.0.1:27017, NO-AUTH / terbuka) dan **CLOUD** (172.16.103.253:27017, butuh auth).
Daemon `ilma_two_way_sync.py --daemon` (systemd `ilma-sync-daemon.service`) menjaga keduanya sinkron.

## Kapan pakai skill ini
- Bos minta audit SOT, hitung provider aktif, atau pastikan local↔cloud identik.
- Sync daemon terlihat stuck (tidak ada perubahan sejak N hari, process sleeping).
- Perlu bandingkan koleksi tertentu antara dua VPS.

## ARSITEKTUR KONEKSI (PENTING — jangan salah)
- **LOCAL selalu no-auth.** Connect tanpa user/pass:
  `pymongo.MongoClient("127.0.0.1", 27017, serverSelectionTimeoutMS=5000)`
  User `ilma_sync` memang ada di `admin.system.users`, tapi password di `.env` (ILMA_MONGO_PASS) **SALAH** → auth gagal. Jangan inject kredensial ke local.
- **CLOUD butuh auth.** Kredensial TIDAK di `.env` (ILMA_MONGO_PASS di .env salah untuk cloud).
  Ambil dari SOT: `credentials.infra_providers[mongodb-cloud].accounts.bos.api_token`
  → berupa URI `mongodb://quantumtraffic:***@172.16.103.253:27017/?authSource=admin&replicaSet=rs0`.
  Parse URI ini dengan `pymongo.MongoClient(uri)` — ini satu-satunya cara connect cloud yang benar.
- **NEVER** pakai `.env` ILMA_MONGO_PASS untuk cloud. Itu fallback berbahaya yang bikin daemon stuck.

## SOT TIER MAP (collections per DB)
DB `credentials` dan `QuantumTrafficDB` (fingerprints, proxies, dll — biasanya identik).

**Tier-1 (Credentials):**
`llm_providers`, `infra_providers`, `system_credentials`

**Tier-2 (Model Intelligence / Catalog):**
`providers`, `models`, `model_intelligence`, `model_capabilities`, `model_enrichment`, `model_benchmark`, `model_alias`

**Tier-3 (Jobs / Sync / Audit / Meta):**
`sot_jobs`, `sot_sync_state`, `model_audit_trail`, `model_lifecycle_events`, `provider_lifecycle_events`, `sot_backups`, `sot_schema_registry`, `_meta`, `_meta_v2_collections`, `sessions`, `crypto_exchanges`, `search_providers`, `messaging`

## CARA CEK PROVIDER AKTIF (llm_providers)
- Filter **`is_active: True`** — BUKAN `status`. Field `status` di semua doc = `None` (tidak dipakai).
- Contoh: 27 docs total, 20 `is_active:True`, 7 `is_active:False`.
- `key_status` (VALID/INVALID/TIMEOUT/UNVERIFIED/SERVER_ERROR) adalah health key, bukan penanda aktif.

## AUDIT RECIPE (banding local vs cloud)
Lihat `references/sot-audit-recipe.md` untuk script Python lengkap. Inti:
1. Connect local (no-auth) + cloud (SOT-URI).
2. Untuk tiap tier, hitung `_id`-set tiap koleksi di kedua sisi.
3. `only_local = L - C`, `only_cloud = C - L` → ini drift nyata.
4. Untuk doc yang ada di dua-duanya, diff field-by-field tapi **exclude field volatile**:
   `_id, _sync_source, _sync_generation, _sync_timestamp, _sync_dirty, verified_at, restored_at, added, updated_at, last_sync, billing_classified_at, refreshed_at, discovered_at, _sot_last_sync`.
   Sisa diff pada field bisnis = data benar-benar tidak sinkron.
5. `model_audit_trail` (120k docs) biasanya identik — jangan jadikan bottleneck visual.

## SYNC DAEMON DEBUG / RECOVERY
Daemon: `systemctl --user status ilma-sync-daemon.service` (enabled, Restart=always).
Log: `run/ilma-sync-daemon.log` (atau `logs/two_way_sync.log`).

**Gejala STUCK (terjadi 2026-07-20):**
- Process hidup tapi `State: S (sleeping)`, tidak ada log sejak N hari.
- Log penuh `E11000 duplicate key` pada `models`/`model_intelligence` (retry loop macet).
- `LOCAL MongoDB connection failed: Authentication failed` → daemon inject `.env` pass ke local no-auth.
- `REMOTE MongoDB connection failed` → `_resolve_remote_from_sot()` connect local pakai auth → gagal → fallback `.env` untuk remote (pass salah).

**Fix (sudah diterapkan ke `scripts/ilma_two_way_sync.py`):**
- `_get_local_client()` → probe **no-auth dulu**, fallback auth hanya jika no-auth gagal.
- `_resolve_remote_from_sot()` → probe local **no-auth dulu** saat baca SOT cred (sebelumnya selalu auth → gagal → fallback `.env` salah).
- Setelah patch: `LOCAL: rs=rs1 ismaster=True` + `REMOTE: rs=rs0 ismaster=True`, 4 watchers ACTIVE.

**Recovery steps:**
1. `systemctl --user restart ilma-sync-daemon.service`
2. Cek log: harus muncul `LOCAL:` + `REMOTE:` ismaster=True + "All 4 watchers started".
3. Jika masih gagal remote → verifikasi URI SOT masih valid (cloud mungkin ganti password).
4. Jalankan reconcile: `python3 scripts/ilma_two_way_sync.py --reconcile --db credentials QuantumTrafficDB`
   (lambat ~7+ min karena scan 120k `model_audit_trail`; jalankan background + notify).

## SPLIT-BRAIN DEDUP PROCEDURE (post-reconcile drift sisa)
Reconcile sering sisa drift karena **cross-side duplicates**: kedua sisi punya doc dengan
`provider+model_id` SAMA tapi `_id` BEDA → unique index `models_provider_model_id_unique`
di cloud bentrok (E11000) saat daemon mau push. Gejala: `models`/`model_intelligence`/
`model_capabilities`/`model_enrichment` muncul `+N_local +N_cloud` dengan count sama.

**Step (gunakan `references/sot-splitbrain-dedup.md` script):**
1. Identifikasi cross-dups: `cloud_only = C_ids - L_ids`. Cek apakah `provider+model_id`
   dari tiap cloud_only **SUDAH ADA** di local → jika ya, itu duplikat.
2. **Drop cloud dups** (`delete_many` by `_id`) — local adalah canonical (lebih baru).
3. **Push local-only ke cloud** via `replace_one(filter={"_id": i}, doc, upsert=True)`
   — aman karena cloud tidak punya `_id` itu.
4. **Verify**: `L_ids == C_ids` → drift=0.
5. Untuk `infra_providers` dup (same provider, beda _id): drop cloud's old doc, upsert local's.
6. Untuk `model_benchmark` (volatile cache, 3-10 docs): drop cloud stale by (provider,model_id),
   push local-only. Bukan source of truth — jangan jadikan blocker.

**ObjectId pitfall:** `delete_one({"_id": "6a358e..."})` → **0 deleted** (string ≠ ObjectId).
Gunakan `from bson import ObjectId; delete_one({"_id": ObjectId("...")})`.

## FINAL VERIFY CHECKLIST (pass/fail)
Setelah dedup + reconcile, jalankan diff final. Kriteria **PASS**:
- T1: `infra_providers`, `system_credentials` IDENTICAL; `llm_providers` -1 OK (antigravity by-design).
- T2: `providers`,`models`,`model_intelligence`,`model_capabilities`,`model_enrichment`,`model_benchmark`,`model_alias` ALL IDENTICAL.
- T3: `model_audit_trail`,`model_lifecycle_events`,`provider_lifecycle_events`,`sot_backups`,`sot_schema_registry`,`_meta`,`_meta_v2_collections`,`sessions`,`crypto_exchanges`,`search_providers`,`messaging` ALL IDENTICAL.
- T3 per-side (NOT required identical): `sot_jobs`,`sot_sync_state`.
- QuantumTrafficDB: all 15 collections IDENTICAL.
Drift pada collection data = 0 → sync restored.

## PITFALLS
- ❌ Jangan filter `status` untuk provider aktif → pakai `is_active`.
- ❌ Jangan inject kredensial ke local mongod → no-auth, akan Authentication failed.
- ❌ Jangan pakai `.env` ILMA_MONGO_PASS untuk cloud → salah, bikin daemon stuck.
- ❌ Jangan langsung `kill` daemon tanpa `systemctl stop` → systemd Restart=always langsung respawning, membingungkan.
- ⚠️ `antigravity/wrapper` (api_key=`***`) **lokal-only by design** — cloud punya JSON Schema validator `minLength:5` yang menolak `***`. Daemon log `reason='no_api_key'` & skip. Biarkan, kecuali Bos mau isi key asli.
- ⚠️ Field timestamp (`_sot_last_sync`, `refreshed_at`, dll) wajar berbeda antar sisi — bukan drift data bisnis.

## REFERENSI
- `references/sot-audit-recipe.md` — script Python audit + sync-daemon fix patch.
- `references/sot-splitbrain-dedup.md` — post-reconcile split-brain dedup + final verify script (drop cloud dups, push local-only, ObjectId cast pitfall).
