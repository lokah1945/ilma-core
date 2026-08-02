# TEMPLATE AUTO-SUMMARY (CLI / MEMORY INGEST)
> gunakan untuk setiap sesi/ topik penting agar memory tidak bengkak

## SKALA KONTEN
Pilih salah satu:

1. **RINGKASAN INDIVIDU** (topik tunggal)
2. **DAFTAR SESION** (multi-topik)

---

## 1. RINGKASAN INDIVIDU (🕒 ~150-300 chars)
```
#### {{TANGGAL}} — {{TOPIK}}
- **Goal:** {{tujuan utama}}
- **Tools:** {{tool utama}} ({{jika perlu: alternatif}})
- **Result:** {{outcome/akhir}}
- **Evidence:** {{bukti: file/output/commit}}
- **Next:** {{lanjutkan ke mana?}} | ⚠️ {{risiko/hit pause}}
```
Contoh diproyeksikan:
```
#### 2026-06-21 — FullStackVPS Access
- Goal: verifikasi port Next.js+Strapi hidup
- Tools: PM2 + HTTP probe (curl)
- Result: 3/3 service OK (3100/3200/3201)
- Evidence: commit 77a1993, output terminal
- Next: tambah domain yapsid ? | ⚠️ domain tidak ada di server
```

---

## 2. DAFTAR SESION (📋 ≤8 entries)
```
## SESSION SNAPSHOT
| Date | Topik | Status | Poin Kunci |
|------|-------|--------|------------|
| 2026-06-21 | FullStackVPS Access | ✅ OK | 3 service hidup |
| 2026-06-20 | Claude Code Setup | ✅ OK | CLI v2.1.183 |
```

---

## 3. HARDAUTH TRANSFER (📡 CLI Command)
Jalankan:
```bash
# buat folder summaries jika belum ada
mkdir -p "$HOME/.hermes/profiles/ilma/summaries"

# contoh penggunaan
cat > "$HOME/.hermes/profiles/ilma/summaries/{{FILENAME}}.md" <<'AUTOGEN'
#### $(date +%Y-%m-%d) — {{TOPIK}}
- Goal: {{...}}
- Tools: {{...}}
- Result: {{...}}
- Evidence: {{...}}
- Next: {{...}}
AUTOGEN
```

---

## OUTPUT SPOKED
Kalau Anda minta saya **generate summary lengkap** untuk sesi tertentu → beri saya:
1. Semua isi transkrip
2. Pilihan: *individual* atau *list*
3. Saya output otomatis ke `$HOME/.hermes/profiles/ilma/summaries`

Contoh:  
`/generate fullstack-summary --mode individual` ← saya isi template dan push.

Ready untuk apa?