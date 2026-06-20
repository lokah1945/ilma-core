# Memory Audit Example — 2026-06-20

Real-world transcript of an end-to-end memory audit using this skill. Reference untuk struktur output dan pitfalls yang muncul.

## Konteks

Bos bertanya: "Anda pakai model apa saat ini, cek config." → jawab dengan run tool (grep, curl, ps, env), bukan dari memory.

Setelah itu Bos minta: "Audit end-to-end semua memory tanpa terkecuali."

## Memory yang diaudit (4 entries × ~17 sub-claim)

| ID | Memory entry | Domain |
|---|---|---|
| M1 | MANDATORY SYNC RULE: git remote = `ilma-core`, push wajib | git/github |
| M2 | SOT LIVE-ONLY 25 providers, 978 models, 9 WORKING, bridge removal | SOT/mongo |
| M3 | ILMA aktif model = minimaxai/minimax-m3, provider=wrapper-nvidia | model/runtime |
| M4 | PHASE D 2026-06-17 score 89.6→99/100, git `d8b4351` | audit history |

## Pattern kerja (end-to-end)

### Phase 1 — Enumerasi
Untuk setiap entry memory, ekstrak semua klaim individual. Contoh untuk M1:
- M1-S1: "GitHub repo = `github.com/lokah1945/ilma-core`"
- M1-S2: "Setiap perubahan WAJIB commit + push"
- M1-S3: "Ada sync helper `.openclaw/scripts/sync_native_providers.py`"

### Phase 2 — Validasi paralel via `execute_code`
Gunakan `execute_code` untuk batch inquiry (jangan satu-satu serial). Contoh:

```python
import subprocess
def R(c): return subprocess.run(c, shell=True, capture_output=True, text=True, timeout=20).stdout.strip()

results = {}
results["M1-S1_repo_remote"] = R("git remote -v | head -2")
results["M1-S2_git_status_porcelain"] = R("git -C /root/.hermes/profiles/ilma status --porcelain")
results["M1-S3_sync_helper_exists"] = R("ls -la /root/.hermes/profiles/ilma/.openclaw/scripts/sync* 2>/dev/null")
# dst...
print(json.dumps(results, indent=2, ensure_ascii=False))
```

### Phase 3 — Tool evidence per klaim (ringkas)

| Tool | Untuk evidence |
|---|---|
| `git log --all --reflog --oneline \| grep <hash>` | verifikasi commit SHA ada atau tidak |
| `git show --stat <hash>` | verifikasi isi commit |
| `find <dir> -name '<pattern>'` | verifikasi file exists |
| `grep -rnE '<pattern>' <dir>` | verifikasi pattern |
| `ss -tlnp \| grep ':<port>'` | verifikasi service hidup |
| `ps -ef \| grep '<proc>'` | verifikasi process |
| `curl -m 5 -X POST <url>` + json grep | live API test |
| `env \| grep <PROVIDER>` | envvar available? |
| `jq '.[] \| keys' <file>` | struktur JSON data |
| `ls -la <file>` + size check | file ada, bukan 0-byte |
| `git ls-files <dir>` | apakah folder tracked atau gitignore'd |

### Phase 4 — Klasifikasi setiap klaim

| Status | Definisi | Contoh audit ini |
|---|---|---|
| **VALID** | Tool evidence cocok dengan klaim | M1-S1, M3-S1 |
| **STALE/DRIFT** | Klaim masih berlaku tapi sudah bergeser | M2-S4 cron script berganti ke `safe_build_and_push.sh` |
| **PARTIAL** | Sebagian cocok sebagian tidak | M4-S4 score "99 final" valid, "89.6 → 99" unverifiable |
| **UNVERIFIED** | Tidak ada bukti positif tapi juga tidak ada kontradiksi | angka SOT 25/978/9 WORKING, repo folder `.git-rewrite/t/` |
| **CONTRADICTED** | Tool evidence aktif membantah klaim | M4-S1 commit `d8b4351` — `git log --all --reflog` kosong |

### Phase 5 — Sinkronisasi

Setelah klasifikasi, update memory via `memory(action='replace')`. Yang perlu diganti adalah:
- **CONTRADICTED** → wajib ganti (hash commit `d8b4351` ganti `7a0bd5f`)
- **STALE/DRIFT** → wajib update (cron script name)
- **UNVERIFIED** → tetap ditulis tapi dengan flag visual ⚠️
- **PARTIAL** → pisahkan VALID vs UNVERIFIED dalam entry memory

⚠️ Hati-hati memory tool punya limit 2200 char. Pakai `replace_all` dengan str_replace individual, atau batching multiple replace separate (sequential, satu per satu).

## Output laporan audit (format final)

```markdown
# 📋 LAPORAN AUDIT MEMORY — END-TO-END
Tanggal: YYYY-MM-DD
Metode: Memory Audit Protocol (Fact First)

## Total: <n> entry / <n> bagian × <n> klaim individual

| ID | Klaim di Memory | Bukti Runtime | Status | Aksi |
|---|---|---|---|---|
| M1-S1 | Repo name | `git remote -v` remote=... | **VALID** | — |
| M4-S1 | Commit d8b4351 | `git log --all \| grep d8b4351` empty | **CONTRADICTED** | ⚠️ Replace |

## Rekap Prioritas
| Severity | Item |
|---|---|
| 🔴 CONTRADICTED | ... |
| 🟠 STALE/DRIFT | ... |
| 🟠 UNVERIFIED | ... |
| 🟢 VALID | ... |

## Sinkronisasi yang dilakukan
1. ✓ Skill baru ... (tercatat permanen)
2. ✓ 4 entry memory di-replace
3. ✓ Repo local sudah di-push ke `ilma-core/master`

## Temuan besar yang perlu aksi Bos
...
```

## Pitfalls

1. **Jangan over-claim lintas profile.** Lihat `ilma-false-positive-detection` → Cross-Profile Over-Claim (lesson 2026-06-20).
2. **Jangan trust commit hash di memory.** Wajib cross-check with `git log --all --reflog`. Sesepele apapun SHA terlihat, memory bisa menyimpan hash dari previous rebase.
3. **Cron schedule drift.** Memory mungkin sebut cron `bf9ad9925449` dengan script X, tapi selama update runtime script-nya bisa diganti ke Y. Wajib grep `cron/jobs.json` actual.
4. **Memory size limit (2200).** Saat replace gagal karena overflow, pecah jadi beberapa replace terpisah (jangan tambah entry baru dulu). Atau drop whitespace dan singkatan yang tidak load-bearing.
5. **Yang bukti-nya dari `execution_log`/runtime cache tidak permanen.** Memory audit hanya boleh klaim yang source-of-truth-nya persisten (file, git, env, code). Runtime evidence seperti `execution_log`/`memory_crash.log`/ephemeral state harus di-flush ke file kalau mau dianggap VALID.

## Tools yang dipakai di audit 2026-06-20

```bash
# 1. Repo state
git remote -v
git status --porcelain  
git log --all --reflog --oneline | grep d8b4351   # → negative
git log --oneline -30 | head                       # → latest = 0dfe2a2 (Optimizer v2)

# 2. Config & runtime
ss -tlnp | grep ":<port>"        # e.g. :9100 LISTEN, pid 217040
ps -ef | grep "<proc>"           # e.g. /root/wrapper/nvidia/main.py
env | grep -E "^<PROVIDER>_"     # env keys informational (redact value)

# 3. Config drift
grep -nE "model|provider|base_url" config.yaml
grep -nE "provider:" profiles/*/config.yaml  # cross-profile check

# 4. Live API curl
curl -s -m 5 -X POST http://127.0.0.1:9100/v1/chat/completions \
  -H "Authorization: Bearer *** \
  -H "Content-Type: application/json" \
  -d '{"model":"...","messages":[{"role":"user","content":"balas 1 kalimat"}],"max_tokens":40}'

# 5. File + data
find /root/.hermes/profiles/ilma/sot -name "llm_providers*"  # data file existence
jq '.keys' /root/.hermes/profiles/ilma/data/benchmark_real_scores.json
ls -la AUDIT/  # what's actually in the audit dir
```

## Pelajaran user-facing untuk audit berikutnya

1. **Audit = leverage:** Audit sekali dapat knowledge bersama. Pakai reference file ini di audits selanjutnya sebagai template, suppress re-discovery biaya.
2. **Update skill langsung:** Begitu ada lesson baru (over-claim lintas profile, cron drift, dsb.), embed ke skill yang relevan. Jangan tinggalkan di memory saja — skill dipakai di session berikutnya sedangkan memory tool entry bisa dipangkas/diverlauf.
3. **Honesty with annotation:** Apapun status (VALID/STALE/UNVERIFIED/CONTRADICTED), jangan sembunyikan. Format `⚠️ unverifiable: <reason>` lebih jujur daripada drop the claim silently.
