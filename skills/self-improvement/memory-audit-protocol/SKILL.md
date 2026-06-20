---
name: memory-audit-protocol
description: Mandatory skeptis-first protocol sebelum menarik kesimpulan dari memory. v10-aligned. Selalu verifikasi lewat source of truth sebelum klaim apa pun tentang state sistem. Default attitude hati-hati dalam menyimpulkan, lebih suka verifikasi daripada menambahkan larangan.
---

# Memory Audit Protocol — Fact First Principle (v10.1 PRODUCTION FREEZE)

## STATUS: v10.1 PRODUCTION FREEZE (2026-06-20, extends v10/v9/v8)

Empat patch sistem bertingkat:

1. **ILMA v8** — Memory Sovereignty + Fact-First Architecture → `references/v8-memory-constitution.md`
2. **ILMA v9** — Evidence-Driven Agent Architecture (extends v8) → `references/v9-evidence-driven-architecture.md`
3. **ILMA v10** — Autonomous Memory Lifecycle (extends v9) → `references/v10-autonomous-memory-lifecycle.md`
4. **ILMA v10.1** — PRODUCTION FREEZE (extends v10) → `references/v101-production-freeze.md`

**v10.1 FINAL LAW:** Stability is a feature. Do not improve what is not failing.

**v10.1 Active Rules:**
- No new layers, daemons, or autonomous mutation.
- Schema/Object Model/Court/TTL **frozen**.
- No cron / scheduler / hidden loops. Actions only on-access / on-write / on-retrieval / on-approval.
- Maintenance allowed: dedup, compression, validation, drift-report. **Disallowed**: auto-repair, auto-rewrite, auto-delete.
- Track only: capacity, dup_ratio, retrieval quality, drift count, false memory.
- Change policy: measured problem → root cause → proposal → approval → rollback → apply.
- Exit conditions: memory saturation >90%, retrieval degradation, drift escalation, production incident.

**v10 Rules:** Object model A0 | State ACTIVE/COMPRESSED/ARCHIVED/DELETED/QUARANTINED | Dedup 0.82 → MERGE not append | Compression >80% | Learning proposes, Court approves, executor executes | Trust half-life 30 epochs | Drift = review ticket (never silent).

**v9 Rule:** Observe → Verify → Understand → Plan → Execute → Validate → Learn → Update. **Never Learn before Validate.**

**v8 F0:** Observed Reality → Runtime State → Source → Files → Contracts → Tests → Validated Memory → Inference → Assumption.

> Memory adalah **konteks kerja**, bukan sumber kebenaran utama.

## F0 Source-of-Truth Priority

```
Observed Reality → Runtime State → Source Code → Current Files →
Contracts → Validated Tests → Verified Memory → Inference → Assumption
```

**Memory tidak boleh override evidence.**

## 3 Prinsip Utama

1. **Memory bukan fakta** — petunjuk awal / hipotesis kerja, bukan kebenaran.
2. **Fakta selalu mengalahkan memory** — runtime state > prose memory.
3. **Wajib verifikasi sebelum simpulkan** — VALID / STALE / UNVERIFIED / CONTRADICTED.

## 4 Langkah Audit

1. **Enumerasi** — kumpulkan memory relevan
2. **Validasi** — bandingkan dengan source code / config / runtime evidence
3. **Reklasifikasi** — Confirmed / Outdated / Unsupported / Invalid
4. **Sinkronisasi** — perbarui representasi internal sesuai fakta terbaru

## Aturan Modifikasi

⛔ Dilarang: ubah code untuk nutupi data hilang / membuat asumsi pengganti bukti / menyatakan config profile lain stale tanpa verifikasi.

✅ Boleh: perbarui interpretasi, perbaiki memory, hapus inferensi yang tidak terbukti.

Lihat juga: `references/memory-audit-example-2026-06-20.md` dan `ilma-false-positive-detection` → Cross-Profile Over-Claim.

## Sikap Operasional

- Skeptis dulu, simpulkan kemudian.
- Observasi > keyakinan. Verifikasi > ingatan. Fakta > konsistensi narasi.
- **Memory bisa usang. Asumsi bisa salah. Fakta tervalidasi = dasar keputusan.**

⚠️ **Catatan sikap 2026-06-20 (Bos Huda):** Skeptis ≠ legalistic. **Deskriptif > Preskriptif.**

Output dari protocol ini bukan "*hapus semua yang belum terbukti*" melainkan
**"verifikasi dulu, lalu klasifikasi dengan jujur"**. Hati-hati jangan sampai:

- Classify UNVERIFIED → STALE → DELETE (tiga lompatan sekaligus)
- Menambahkan "DILARANG keras" / "JANGAN pernah" hanya karena satu observasi, padahal yang benar adalah **"verifikasi dulu"**
- Menyebut config profil lain stale/salah tanpa bukti cross-profile

Saat ragu, **bukan menambah larangan, tapi menambahkan verifikasi yang lebih teliti**.

**Sikap ideal: Hati-hati dalam menyimpulkan, inkusif dalam klasifikasi.**

❗ **Koreksi gaya 2026-06-20 (Bos):** "Bukankah jangan pernah. Lebih hati-hati dalam menyimpulkan."

Frasa "dilarang keras" / "jangan pernah" hanya dipakai kalau:
1. Ada bukti langsung (bukan inferensi) bahwa X dilarang di profile ini.
2. Ada konfirmasi Bos atau aturan eksplisit di constitutional memory.
3. Bukan generalisasi lintas profile.

**Default behavior: deskriptif (apa adanya), bukan preskriptif (larangan).**

---

## Lessons from Real Audits (Bos Huda 2026-06-20)

### Lesson 1 — Host/port enumeration (T1 self-violation)
- Saya sendiri **melanggar protocol** di audit T1: `127.0.0.1:27017` unreachable → lonjong ke "MongoDB mati" tanpa cek hostname.
- **Real**: MongoDB di `172.16.103.253:27017`, ping 0.3ms.
- **Fix:** Setiap system-probing WAJIB enumerate hostnames & ports. Cek config (bukan asumsi) untuk host service. Query multi-network dulu sebelum simpulkan global state.

### Lesson 2 — Cross-Profile Over-Claim (T2)
- Profile `master-chief` pakai `provider: minimax` (api.minimax.io) → saya named "stale/salah" untuk profile ILMA. **SALAH.** Profile lain valid beda profile.
- **Fix:** Sebelum claim "X stale", cek runtime bukti per profile aktif. → `ilma-false-positive-detection` → **Cross-Profile Over-Claim**.

### Lesson 3 — Claim commit hash tanpa validasi (T2)
- Memory lama: `d8b4351` (commit Phase D). **TIDAK ADA** di git reflog/branch.
- **Fix:** Sebelum quote commit hash → verify via `git show <hash>` atau `git reflog`. Status: NOT FOUND → CONTRADICTED.

### Lesson 4 — Cron drift detection (T2)
- Memory: cron `bf9ad9925449` runs `ilma_model_db_manager.py --full-sync --git-push`. Aktual: `bash scripts/ilma_safe_build_and_push.sh`.
- **Fix:** Dokumentasi script yang di-quote harus compare dengan current `cron/jobs.json`. Drift = common.

### Lesson 5 — MongoDB ground truth (T2)
- "FROZEN 25/978 models/9 WORKING" SALAH total. Real via aggregate: llm_providers=22, models=2039, ZERO LIVE-key.
- **Fix:** Untuk klaim angka storage → query MongoDB aggregate, NEVER trust prose memory.

### Lesson 6 — Working tree ≠ tracked HEAD (T2)
- `ilma_subagent_router.py` hidup di working tree (untracked), tracked-git HEAD tidak punya.
- **Fix:** Lapor berdasarkan LOKASI AKTUAL (working tree / untracked / tracked HEAD) — bukan blanket "ada" atau "tidak ada".

### Lesson 7 — `.git-rewrite/t/` VALID pitfall
- BFG Repo-Cleaner staging folder **tracked** in HEAD. Berisi copies: `backups/deep_opt_20260601_153719/`, `archive/garbage/`, `hermes_profile_ilma/`.
- **Fix:** Sebelum `rm -rf` folder "archive" → ALWAYS `git ls-files .git-rewrite/t/`. Lost files previously happen.

### Lesson 8 — V8/V9/V10 patch chain
- Patch-system cares tentang chain v10→v9→v8. Patch baru EXTENDS, jangan override eksplisit. Selalu tulis referensi ke chain di intro skill.
- **Fix:** Skill baru yang adds behaviour → refer ke patch chain di status block.

---

## Pola Kegagalan yang Harus Dihindari

| ❌ Pola salah | ✅ Pola benar |
|---|---|
| Jawab langsung dari memory tanpa verifikasi | Ambil memory SEBAGAI hipotesis, lalu verify |
| Lihat profil A pakai provider X → simpulkan provider X salah di profil B | Cek runtime bukti, jangan menyamaratakan lintas profil |
| `127.0.0.1:PORT` unreachable → simpulkan service mati global | Enumerate hostname, cek config, query multi-network |
| Header session bilang Y → simpulkan Y pasti config | Header bisa inheritance / stale; cek config + runtime |
| Menyebut config "stale/salah" tanpa tool | Wajib `grep`, `cat`, `read_file`, atau curl |
| Quote commit hash tanpa `git show` verify | `git show <hash>` or `git reflog` dulu |
| Classify UNVERIFIED → STALE → DELETE tiga lompatan sekaligus | UNVERIFIED dulu; validasi bukti; baru klasifikasi |
| Menambah "DILARANG keras" hanya karena satu observasi | Default DESKRIPTIF; "dilarang" hanya kalau ada bukti langsung |
| Buang `archive/`/`backup/`/`fresh-installation/` folder tanpa verify tracked | `git ls-files` folder dulu; `.git-rewrite/t/` may have only-tracked copy |
| Buru-buru menarik kesimpulan final | Tandai UNVERIFIED dulu sampai bukti kuat |

---

## Verifikasi Runtime — Tool Cepat

```bash
# Config aktif
grep -nE "model|provider" ~/.hermes/profiles/<profile>/config.yaml | head

# Live HTTP test
curl -s -m 5 -X POST http://127.0.0.1:9100/v1/chat/completions \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"model":"...","messages":[{"role":"user","content":"balas 1 kalimat"}],"max_tokens":50}'

# Service hidup?
ss -tlnp | grep -E ":<port>"
ps -ef | grep "<proc>"

# Env / API key aktif
env | grep -E "<PROVIDER>_" | sed 's/=.*/=***/'

# Commit hash verify
git show <hash> --stat | head -5
git log --all --oneline | grep <hash>

# MongoDB ground-truth via aggregate
python3 -c "from pymongo import MongoClient; c=MongoClient(host='<host>', port=<port>); db=c['<db>']; print(list(db.<coll>.aggregate([{'\$group':{'_id':'\$status','count':{'\$sum':1}}}])))"

# Tracked-files check
git ls-files | grep <pattern>
git ls-tree HEAD <path>
```

## Output Wajib Saat Apply

Setiap apply protocol ini ke pertanyaan / klaim besar, jawab dengan:

```
1. Memory yang relevan (kalau ada)
2. Bukti runtime aktual (config, curl, ps, dsb.)
3. Status: VALID / STALE / UNVERIFIED / CONTRADICTED
4. Kesimpulan (hanya dari data tervalidasi)
5. Label FACT / LIKELY / UNKNOWN jika klaim besar (v9 G6)
```

## Trigger Pemakaian

Skill ini auto-trigger setiap kali:
- Bos tanya "Anda pakai apa?" / "Cek config" / "Model apa?" / "Verified?"
- Ada klaim tentang state sistem dari memory lama
- Lintasan memory tampak tidak konsisten dengan indikasi runtime
- Sebelum commit / push / sync perubahan apa pun
- Ketika sebut commit hash / cron ID / file path dari memory
