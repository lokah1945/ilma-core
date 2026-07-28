# ILMA Dashboard DB Recovery (2026-07-28)

## Symptom
- Dashboard pages show **"no record"** / empty tables.
- OR backend returns `HTTP 500` with traceback:
  `sqlite3.OperationalError: no such column: benchmark_records.canonical_model_id`
- `sqlite3` row counts show `providers=0` while `model_ids` has stale rows.

## Root cause (two layers)
1. **Stale/corrupt SQLite** — the dashboard DB schema changed (new columns added to
   `benchmark_records` etc.) but the on-disk `ilma_dashboard.db` was created under the
   old schema. SQLAlchemy hits the missing column on any `/api/*` query.
2. **Empty seed** — even after recreate, the seeder read source paths that no longer
   exist (`/root/.hermes/profiles/ilma/model_specialization_database.json`,
   `ilma_benchmark.db`), so `providers=0` and every page is empty. The live SOT source
   is `ilma_model_router_data/PROVIDER_INTELLIGENCE_MASTER.json` (22 providers, ~1871 models).

## Fix recipe (verified working)
```bash
cd /root/.hermes/profiles/ilma/dashboard/backend

# 1. Backup the broken DB
cp /root/.hermes/profiles/ilma/data/ilma_dashboard.db \
   /root/.hermes/profiles/ilma/data/ilma_dashboard.db.bak-$(date +%Y%m%d-%H%M%S)

# 2. Delete it so create_all() rebuilds with the current schema
rm -f /root/.hermes/profiles/ilma/data/ilma_dashboard.db

# 3. Run the seeder (now falls back to PROVIDER_INTELLIGENCE_MASTER.json)
python3 scripts/seed_dashboard_db.py
# Expect: Providers: 25, Models: 1871, Benchmarks: 7484, Capabilities: 108, Errors: 0

# 4. Restart backend to load the fresh DB
systemctl --user restart ilma-dashboard-backend.service
sleep 3

# 5. Verify
curl -s http://127.0.0.1:8000/api/overview
# -> {"total_providers":25,"total_models":1871,"total_benchmarks":7484,...}
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/api/providers   # 200
```

## Seeder source-path patch (apply once, already shipped)
`scripts/seed_dashboard_db.py` was patched so `seed_providers()` and
`seed_models_and_benchmarks()` fall back to
`/root/.hermes/profiles/ilma/ilma_model_router_data/PROVIDER_INTELLIGENCE_MASTER.json`
when `model_specialization_database.json` is absent. The MASTER JSON shape is:
```
providers[provider_id] = {
  "status", "auth_validated", "api_key_count",
  "models": { model_id: { "model_name", "is_free", "context_window",
                          "specialization", "score", "score_tier", ... } }
}
```
The seeder flattens `providers[].models[]` and maps `is_free` -> `free_or_paid`,
`score` -> `quality_score`, `score_source` -> `evidence_level`.

## Related fixes in the same session
- All wrapper/dashboard systemd units switched `--host 127.0.0.1` -> `--host 0.0.0.0`
  so they are reachable from a LAN IP (see SKILL.md pitfall #8).
- `vite.config.ts` got `server.host:'0.0.0.0'` + `strictPort:true`; frontend unit
  changed to `--port 3000 --host 0.0.0.0` (see pitfall #7).
- Backend CORS `allow_origins` widened to `[\"*\"]` so a browser on a LAN IP is not
  blocked (see pitfall #10).

## Diagnosis quick-ref
- `providers=0` but `model_ids` > 0 → seeder ran but its source files were missing/empty
  (old `model_specialization_database.json` gone). After the MASTER fallback patch this
  should NOT happen — if it does, check the seeder's printed `Missing Sources:` list.
- `Missing Sources: 4` (ilma_benchmark.db, ILMA_EVIDENCE_LEDGER_2026-05-07.md,
  ilma_workflow_ecc.py, scripts/ilma.py) is EXPECTED and benign — those legacy sources no
  longer exist; the SOT MASTER JSON supplies providers + models + benchmarks instead.
- `sqlite3.OperationalError: no such column: ...` → always delete + reseed (never try to
  ALTER the table by hand). The DB is fully regenerable from source files.

## Seeder → ModelRecord field map (if you edit the seeder)
MASTER `providers[pid].models[mid]` → `ModelRecord`:
| MASTER field            | ModelRecord field   | note                                 |
|-------------------------|---------------------|--------------------------------------|
| `model_name` / mid      | `canonical_model_id`| falls back to model key              |
| `pid` (parent)          | `provider`          | injected via `setdefault("provider")`|
| `is_free`               | `free_or_paid`      | True→FREE, False→PAID                |
| `score`                 | `quality_score`     | also `trust_level = int(score*10)`   |
| `context_window`        | `context_window`    | else `raw_metadata.context_length`   |
| `score_source`          | `evidence_level`    | mapped via `evidence_level_map`      |
| `refreshed_at`/`last_verified` | `last_verified` |                                      |
Missing `providers_seen` local var: the original seeder declared it then removed it — if you
see `NameError: providers_seen`, delete the `if provider in providers_seen` guard block
(the loop already iterates a `set`, so dedup is implicit).
