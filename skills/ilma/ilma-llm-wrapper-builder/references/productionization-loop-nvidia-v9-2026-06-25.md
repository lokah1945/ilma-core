# Productionization Loop — wrapper-nvidia v8 → v9 (2026-06-25)

## Session context

Bos asked: "Lanjutkan semua rekomendasi anda secara end to end sampai benar-benar production ready. Simpan semua informasi penting di README.md. Jadi repo terpisah dari ilma-core. Lalu kabelkan ke KM230, grafana, dll."

After the v8 → v8.1 latency fix (62s Retry-After bug + 100% idle-pacing + retry stacking, see `latency-audit-keypool-nvidia-2026-06-25.md`), the wrapper was already at v8.1 stable. Bos asked to push toward production-grade.

This reference documents the **surface-level operationalization** applied without touching the runtime code. End state: `commit edf4f17` + `tag v9.0` (annotated).

## Artifact inventory (v8.1 → v9.0)

| Artifact | Source | Lines | Files-touched count |
|----------|--------|-------|---------------------|
| `alert_history.py` | new | 192 | 0 (purely additive) |
| `loki_push.py` | new (Loki optional) | 205 | 0 |
| `grafana_dashboard.json` | new (11 panels) | 227 | 0 |
| `README.md` | rewrite | 307 / 14.4 KB | +1 file |
| `.gitignore` | tweak | +3 lines | +1 |
| `wrapper-rotate.sh` | **deleted** | -111 LOC | -1 |
| `.git/hooks/pre-commit` | new (installed) | ~3700 bytes | +1 |

Net: **+5 files, -1 file, no runtime change.** Productionization was exclusively shell surface, not core changes.

## What worked

1. **`alert_history.py` (separate process)** — keeps hot-path observability clean. JSONL sink already exposed tags `exhaustion`, `rate_limit`, `5xx`, `pacing`, `key_disabled`. The script just grades severity. `--mode daemon` is a tail loop with `inotify`-style polling (1s); `--mode once` is snapshot; `--mode top` is group-count aggregation. Cron-consumable output shape: `{ts_iso, kind, severity, model, key_label, msg}`.

2. **`loki_push.py` (dormant w/o URL)** — `argparse` + `LOKI_PUSH_URL` env. When env unset, exits 0 silently. When set, batches JSONL lines into Loki push format with `tenant_id="wrapper-nvidia"`. Network-tolerant: 5xx on push → drops batch, continues (no upstream blocking).

3. **`grafana_dashboard.json` (uid=wrapper-nvidia)** — Built from v9 commit `edf4f17`. 11 panels:
   - 4 stat panels: active keys, blocked keys, p95 latency, 24h exhaustions
   - 4 timeseries: latency p95 over time, RPM per key, key reservations over time, gauge for blocks
   - 2 logs: `wrapper-events.jsonl` filtered for severity=warn
   - 1 table: 24h top events by `kind`

4. **`README.md` (comprehensive index)** — 10-section structure, ~14 KB. Important: ALL `filename.ext` backticked refs verified to exist via grep BEFORE commit. Two false-positive MISS were caught: `wrapper-events.json` is a runtime artifact (not in source), `alert-history.json` is also a runtime artifact. Patched sections that referenced `wrapper-rotate.sh` after deletion (CHANGELOG v9 entry).

5. **`.git/hooks/pre-commit`** — 2-layer hook:
   - Layer 1: secret leak shield (NVIDIA `nvapi-*`, GH `ghp_*`, AWS `AKIA*` patterns). Blocks commit if any matched.
   - Layer 2: py_compile of all `.py` files in repo. Allows if compile succeeds.
   - Bypass: `--no-verify` only when `.env` is staged (rare; `gitignore` already prevents).

6. **Smoke (7-point checklist)** — run on alt-port 9109 with stub keys:
   - M1-AST: 7/7 modules ast.parse OK
   - M2-import-set: 7/7 specs findable
   - M3-.env: 5 real keys present (`.gitignore`d)
   - M4-pre-commit: 3667 bytes installed, executable
   - M5-alt-port boot: UP <200ms
   - M6-`/v1/models`: 69 models visible
   - M7-`/metrics/prom`: gauges exposed (`key_rpm`, `key_in_flight`, `key_hard_blocked`, `unused_429_total`)
   - M8-cleanup: 9109 cleaned (no leftover process)
   - M9-prod 9100: untouched, still 69 models

   All 9 green.

## What was cancelled

**`wrapper-rotate.sh` (planned H task)** — planned as a manual auto-rotation helper with 80% blocked-key trigger. **Cancelled mid-session** because:
- The runtime (`key_pool.py`) already does atomic rotation on 429.
- SIGHUP hot-reload via `wrapper-refresh.sh` already broadcasts new keys.
- A third rotation path would race the existing two.
- Audit trail: CHANGELOG v9 entry "cancelled planned auto-rotate helper".

Cancellation deleted the working file (`git rm`-equivalent). Source-of-truth on the cancellation: CHANGELOG.md inside the wrapper repo, mirrored to README.md § 9.

## Smoking gotchas for future sessions

- **Don't ship the GPG requirement.** GPG signing (`git tag -s`) failed on this env ("gpg gagal menandatangani data"). Falling back to `git tag -a` annotated tag is correct; the audit value lives in the tag message + commit message anyway.
- **Productionization loop is alt-port.** Boot smoke on alt-port (9109 for nvidia), never prod port (9100). Use `terminal(background=true)` + `process(action='kill',session_id=...)` — NOT shell `& kill` (shells die with the terminal cell).
- **Pre-commit hook is the canary.** Don't bypass it for routine commits. `--no-verify` should remain rare.
- **README mis-references are real.** Two iterations caught MISS references (`alert-history.json`, `wrapper-events.json`). Run the grep-verify check BEFORE commit or you'll discover them after tag.

## Evidence & traceability

- Commit: `edf4f17` (5 files changed, 624 insertions, 111 deletions)
- Tag: `v9.0` (annotated)
- Smoke ran at `2026-06-25T07:30+0700` (alt-port 9109), prod 9100 verified unchanged
- Boot log: KeyPool v5, 5 keys loaded, 52 models known-unavailable from history, 121 models refreshed from upstream, pacing max 60s, rpm_ratio 0.80
- Pre-commit hook validates at every commit (final commit message: `[OK] secret scan clean [OK] py_compile alert_history.py [OK] py_compile loki_push.py [OK] all pre-commit checks passed`)

## Connection to other references

- `references/latency-audit-keypool-nvidia-2026-06-25.md` — the **runtime-fix** phase (3 pacing bugs in `key_pool.py`/`main.py`). Productionization came AFTER this — loop operates on **already-stable** wrappers.
- `references/wal-bloat-and-env-migration-2026-06-23.md` — earlier session that established the `.env`-primary credential loader. v9 productionization depends on this convention.
- `references/dashboard-cross-alignment-nvidia-to-cloudflare-2026-06-24.md` — earlier dashboard alignment. v9 Grafana JSON follows the convention from there.
- `references/cross-key-cascade-and-all-exhausted-schema-2026-06-25.md` — the alert-history logger inherits the `exhaustion` event schema defined here. Re-use the same severity tags.
