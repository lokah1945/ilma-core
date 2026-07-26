# Phase 16 — ILMA Daily Health Cron Fix

**Date:** 2026-05-31
**Trigger:** Daily Health cron [2] showing `⚠️ FILE NOT FOUND — script not present, skipped`

---

## Root Cause

3 file yang hilang dari root ILMA profile setelah cleanup/archive:

| File | Lokasi backup | Status |
|------|-------------|--------|
| `ilma_self_improve.py` | `scripts/ilma_self_improve.py` | ❌ hilang dari root |
| `ilma_health_check.py` | `scripts/ilma_health_check.py` | ✅ ada di scripts/ |
| `scripts/ilma_evidence_validator.py` | Shim lama hilang | ❌ hilang → deprecation shim hilang |

**Bug argumen:** cron job memanggil `ilma_evidence_validator.py --audit` — arg `--audit` tidak ada di parser. Arg yang benar adalah `--system-check`.

**Backup timeout:** cron job lama pakai `tar ... ilma_model_router_data/` (3.3GB) → timeout setelah 60s. Solusi: gunakan `scripts/ilma_backup.py create` yang sudah exclude `ilma_model_router_data/` dan menghasilkan ~17MB dalam ~1 detik.

---

## Fix Applied

1. **Restore file ke root:** `cp backup/ilma/ilma_backup_20260531_050001/scripts/ilma_self_improve.py ilma_self_improve.py` (file sama, lokasi berbeda)
2. **Recreate shim:** `scripts/ilma_evidence_validator.py` → shim 24-line forwarding ke `scripts.services.evidence.validator` dengan `DeprecationWarning`
3. **Fix cron prompt:** `--audit` → `--system-check`; `tar ... ilma_model_router_data/` → `python3 scripts/ilma_backup.py create`
4. **Commit:** `fe2ac33` — pushed to GitHub

---

## Key Pattern: Root vs Scripts Duality

ILMA memiliki file yang hidup di dua lokasi:
- **Root** (`/root/.hermes/profiles/ilma/`): entry point untuk CLI/cron
- **Scripts** (`scripts/`): kode aktual + services decomposition

File tertentu harus ada di ROOT untuk cron job yang pakai `python3 ilma_X.py` (tanpa `scripts/` prefix). Jika dihapus/cleaned up, restore dari `scripts/` backup.

**Recovery checklist:**
- [ ] `ilma_self_improve.py` exist in root? Jika tidak → restore dari `scripts/`
- [ ] `ilma_health_check.py` exist in root? Jika tidak → restore dari `scripts/`
- [ ] `scripts/ilma_evidence_validator.py` shim exist? Jika tidak → recreate sebagai deprecation shim
- [ ] Backup dalam cron job → pakai `scripts/ilma_backup.py create` (bukan manual tar)
- [ ] Evidence validator CLI args → cek `python3 ilma_evidence_validator.py --help`

---

## Daily Health Cron Canonical Prompt (v16 fix)

```bash
cd /root/.hermes/profiles/ilma && echo "=== ILMA Daily Health (Phase 16) ===" && echo "" && echo "[1] ilma_self_improve.py" && python3 ilma_self_improve.py 2>&1 | head -3 && echo "" && echo "[2] ilma_evidence_validator.py --system-check" && if python3 ilma_evidence_validator.py --system-check 2>&1 | head -10; then echo "✅ SUCCESS — Evidence validation complete"; else echo "⚠️ FAILED"; fi && echo "" && echo "[3] ilma_health_check.py" && if python3 ilma_health_check.py 2>&1 | head -5; then echo "✅ OK"; else echo "⚠️ FAILED"; fi && echo "" && echo "[4] backup create" && if python3 scripts/ilma_backup.py create 2>&1 | tail -2; then echo "✅ OK"; else echo "⚠️ FAILED"; fi && echo "" && echo "✅ ILMA Daily Optimization complete (Phase 16)"
```

---

## Evidence Validator CLI Args (Root Version)

```
python3 ilma_evidence_validator.py --validate FILE       # validate registry JSON
python3 ilma_evidence_validator.py --model-evidence ID  # validate model evidence
python3 ilma_evidence_validator.py --system-check      # FULL system check ✅ (NOT --audit)
python3 ilma_evidence_validator.py --report             # generate validation report
python3 ilma_evidence_validator.py --json               # output as JSON
```

Note: `--audit` is NOT a valid argument. If a script/cron uses `--audit`, fix to `--system-check`.