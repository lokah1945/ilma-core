---
name: ilma-policy-compliance-audit
description: Audit kebijakan kepatuhan (policy compliance) pada codebase — verifikasi implementasi kebijakan tanpa memberikan rekomendasi perbaikan. Fokus pada FREE_ONLY, rate limiting, auth, security gates.
category: ilma
---

# ILMA Policy Compliance Audit — Class-Level Skill

## WHEN TO USE
- Bos: "pastikan code mematuhi kebijakan X"
- Bos: "cek kebijakan FREE_ONLY", "audit kebijakan keamanan"
- Verifikasi kepatuhanan kebijakan pada infrastructure atau wrapper services

## CRITICAL PITFALL — Rekomendasi Tidak Diminta (Bos caught this 2026-07-24)
Jangan pernah memberikan rekomendasi perbaikan/koreksi pada saat audit hanya meminta verifikasi kebijakan. 

**Contoh yang SALAH:**
> "Anda harus ubah X ke Y karena Z..."

**Contoh yang BENAR:**
> "✅ Kebijakan X DAPAT dipatuhi. Implementasi berada di file Z, fungsi W."

Jika bos meminta rekomendasi, minta konfirmasi eksplisit: *"Apakah Anda ingin saya berikan rekomendasi perbaikan?"*

## AUDIT WORKFLOW (Policy-Focused)

### Step 0 — Policy Definition
Identifikasi kebijakan yang akan diaudit:
- `FREE_ONLY` — hanya model gratis yang diizinkan
- `RATE_LIMIT_RPM` — limit request per menit
- `AUTH` — bearer token validation
- `SECURITY_GATES` — anti-pattern deteksi

### Step 1 — Policy Implementation Check
Untuk setiap wrapper/service:

1. **Cari fungsi policy checker**
   ```bash
   grep -r "def free_only_enabled\|def is_free_model\|def model_allowed" --include="*.py"
   ```

2. **Verifikasi logika**
   - `free_only_enabled()` → cek environment variable
   - `is_free_model()` → cek kriteria "free"
   - `model_allowed()` → gabungkan keduanya

3. **Cek allowlist mechanism**
   - Apakah `FREE_MODEL_ALLOWLIST` ada?
   - Bagaimana cara kerjanya?

### Step 2 — Policy Enforcement Point
Cari di mana kebijakan DITERAPKAN:

```bash
grep -r "_check_free_only\|free_only_error\|model_allowed" --include="*.py" | grep -v "def "
```

Pastikan ada **middleware atau handler** yang menolak request yang melanggar kebijakan.

### Step 3 — Test Case Verification
Buat test sederhana untuk verifikasi:

```bash
# Test FREE_ONLY enforcement
curl -s http://localhost:PORT/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "paid-model", "messages": []}' \
  | jq '.error.code'
# Harus mengembalikan "free_only_restricted"
```

## OUTPUT FORMAT — Policy Compliance Report

**WAJIB format:**
```
✅ Kebijakan [NAME] [PATATHI/DIPATOK]

**Temuan:**
| # | Komponen | Implementasi | Status |
|---|----------|--------------|--------|
| 1 | wrapper-name/src/main.py | fungsi is_free_model() | ✅ Benar |
| 2 | wrapper-name/src/main.py | fungsi free_only_enabled() | ✅ Benar |
| 3 | wrapper-name/src/main.py | middleware _check_free_only | ✅ Benar |

**Verifikasi:**
- `is_free_model()` memeriksa "free" di nama model + allowlist
- `free_only_enabled()` membaca FREE_ONLY environment variable
- `_check_free_only()` menolak model non-free dengan error 400

**Verdict:** [PATATHI/DIPATOK]
```

## REFERENCES
- `references/free-only-implementation-patterns.md` — pola implementasi FREE_ONLY di berbagai wrapper
- `references/policy-enforcement-points.md` — lokasi middleware untuk policy enforcement