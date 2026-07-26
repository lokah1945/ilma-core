# Phase 72 Router Audit Findings
**Date:** 2026-06-05
**Mode:** Observation-only, no system changes
**Method:** Tool verification (grep, read_file, terminal) — zero assumptions

---

## CRITICAL: is_active Promotion Pipeline MISSING

**Fakta terverifikasi:**
```
is_active=True  :  27 model (hanya ini yang ikut routing)
is_active=False: 909 model (tidak pernah di-promote)

production_allowlist: 156 model
  → is_active=True:   27 (17%)    ← BUG: 129 yang bagus TIDAK aktif
  → is_active=False: 129 (83%)

Models baru setelah 2026-05-01: 108
  → is_active=True:   0          ← TIDAK ADA yang di-promote
```

**Akar masalah:**
- `is_active` di-set SATU KALI saat bootstrap (2026-04-20 s/d 2026-04-25)
- Setelah itu, tidak ada code path yang auto-promote model baru
- `ilma_enrich_pim.py`: enrich benchmark/capability, TIDAK set `is_active`
- `ilma_db_pipeline.py`: sync provider API, TIDAK ubah `is_active`
- `ilma_benchmark_autoloop.py`: benchmark model, TIDAK promote `is_active`

**Fix requirement:** Tambahkan `set_active` call di pipeline enrichment step, atau buat dedicated auto-promotion job.

---

## CRITICAL: HealthTracker.is_healthy() — unknown DIANGGAP healthy

**Lokasi:** `scripts/ilma_unified_model_router.py` ~HealthTracker.is_healthy()

**Bug:**
```python
def is_healthy(self, model_id: str) -> bool:
    status = self.get_status(model_id)
    return status != "unavailable"   # ← unknown juga returns True
```

**Dampak:**
- 1173 model di model_health_state.json → semua `unknown`
- is_healthy() → True untuk SEMUA → circuit breaker TIDAK BEKERJA

**Fix:** `return status == "available"` — strict check.

---

## HIGH: Single-Winner Routing (bukan Top-K Pool)

**Lokasi:** `ilma_subagent_router.py` — get_best_model() return 1 model

**Flow:**
```
get_best_model(task) → 1 model → execute → success/fail
                                           ↓ fail
                                      fallback[0] → execute → ...
```

**Tidak ada:**
- Top-K candidate pool
- Round-robin antar model
- Load balancing

**Dampak:** Nemotron (nvidia/nemotron) overload karena selalu dicoba pertama.

---

## HIGH: Dual Health System Tidak Sinkron

**Dua sistem independent:**
1. `ilma_model_router.py._failure_count` (in-memory) → `_is_healthy()`
2. `ilma_unified_model_router.py._health` (HealthTracker) → `is_healthy()`

**Masalah:**
- `mark_failure` ditulis async (try/except pass) — bisa fail tanpa propagasi
- `_is_healthy` baca dari file — baca stale state jika write gagal
- Dual source of truth → race condition

---

## MEDIUM: NVIDIA Key Pool — Reactive Rotation Only

**Lokasi:** `ilma_subagent_router.py` — NvidiaKeyPoolManager

**Masalah:**
- Rotation hanya SETELAH 429, bukan sebelum (tidak proactive)
- mark_healthy dipanggil SETELAH successful call — key lain idle
- Tidak ada concurrent request tracking
- Tidak ada load-aware distribution

**3 key aktif, tapi utilisation tidak merata.**

---

## MEDIUM: Scheduler Failures

**DB Sync (bf9ad9925449):**
```
Error: "Script not found: /root/.hermes/profiles/ilma/scripts/python3 scripts/ilma_model_db_manager.py"
```
`no_agent=True` + relative path → Hermes prepends `scripts/` → invalid path. Fix: `script: "python3 ilma_model_db_manager.py ..."`

**Benchmark Autoloop (77a171f68d82):**
Paused. Prompt trigger scanner false-positive. Fix: `no_agent=True` + script-only mode.

---

## MEDIUM: MASTER JSON Loading Tanpa Cache

**Lokasi:** `_load_master()` dipanggil setiap router instantiation

**Dampak:** ~50-200ms overhead per session (1MB+ JSON, disk I/O)

---

## Priority Matrix (Phase 72)

| # | Severity | Root Cause |
|---|----------|------------|
| 1 | CRITICAL | unknown=healthy → circuit breaker fail |
| 2 | HIGH | is_active static → 909 model dormant |
| 3 | HIGH | single-winner routing → model overload |
| 4 | HIGH | sk-cp- key ≠ direct API → false availability |
| 5 | MEDIUM | NVIDIA key underutilization |
| 6 | MEDIUM | DB sync broken → stale MASTER |
| 7 | MEDIUM | Benchmark autoloop paused |
| 8 | MEDIUM | MASTER JSON loading tanpa cache |

---

## Quick Wins (No New Files)

| ID | Fix | File | Line |
|----|-----|------|------|
| QW-1 | `return status == "available"` (strict health check) | ilma_unified_model_router.py | ~420 |
| QW-2 | Fix scheduler path: `scripts/ilma_` → `ilma_` | cron/jobs.json | job bf9ad9925449 |
| QW-3 | Add `no_agent=True` to benchmark autoloop job | cron/jobs.json | job 77a171f68d82 |