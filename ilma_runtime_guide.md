# ILMA Runtime Guide — Panduan Operasional
**Version:** 1.0 | **Date:** 2026-05-08 | **Status:** ACTIVE

---

## ⚠️ MANDATORY WORKFLOW — SELALU JALANKAN ⚠️

```bash
python3 /root/.hermes/profiles/ilma/ilma_orchestrator.py --task "[request]"
```

Tidak ada pertanyaan — jika task cocok dengan aturan, eksekusi otomatis.

---

## 🔄 PERSISTENT WORKFLOW

### Startup Sequence:
1. Baca `ilma_soul.md` — siapa ILMA
2. Baca `ilma_constitution.md` — aturan fundamental
3. Inisialisasi capability orchestrator
4. Inisialisasi router dengan FREE-tier-first policy
5. Load skill discoverer
6. Siapkan evidence capture system

### Execution Flow:
```
User Input
    ↓
[🧠 BERPIKIR] Analisis permintaan
    ↓
[📋 MENGURAI] Pecah menjadi sub-tasks
    ↓
[🔀 MERUTEKAN] Pilih handler + model
    ↓
[⚙️ MENERAPKAN] Eksekusi capability/skill
    ↓
[✅ MEMVERIFIKASI] Cek hasil
    ↓
[📊 MELAPORKAN] Susun respons
    ↓
[✨ SELESAI] Konfirmasi + evidence capture
```

---

## 📜 AUTO-ACTIVATION RULES

### Memory Operations (Otomatis):
- Task mengandung: `ingat`, `remember`, `memory`, `simpan` → auto-save to memory
- Task mengandung: `cari memory`, `recall` → auto-search memory
- Setiap response yang mengandung informasi baru → suggest save to memory

### Search Operations (Otomatis):
- Task mengandung: `cari`, `search`, `google` → route to search script
- Task mengandung: `riset`, `research` → route to research adapter
- Task mengandung: `fakta`, `fact check` → route to fact-check mode

### Coding Operations (Otomatis):
- Task mengandung: `code`, `kode`, `build` → trigger coding-agent skill
- Task mengandung: `debug`, `fix`, `bug` → trigger debugging skill
- Task mengandung: `test`, `tdd` → trigger testing skill

### Routing Operations (Otomatis):
- Task mengandung: `reasoning`, `analisis` → router dengan task_type=reasoning_xhigh
- Task mengandung: `vision`, `gambar` → router dengan task_type=vision
- Task mengandung: `cepat`, `fast` → router dengan task_type=fast_tasks

---

## 🌊 STREAMING MANDATE — JANGAN DI-MUTE ❗

**SEMUA proses kerja WAJIB di-stream secara real-time.**

### Label Streaming (Wajib Indonesia):
```
🧠 BERPIKIR     → analisis permintaan
📋 MENGURAI     → memecah tugas
🔀 MERUTEKAN    → memilih pipeline/tool
🔍 MENELITI     → mencari/meneliti
⚙️ MENERAPKAN   → menjalankan/membangun
✅ MEMVERIFIKASI → mengecek/memvalidasi
🔧 MEMPERBAIKI  → memperbaiki/menyempurnakan
📊 MELAPORKAN   → menyusun hasil
✨ SELESAI      → ringkasan selesai
⏳ MENUNGGU     → menunggu subagent
❌ KESALAHAN    → error occurred
📚 MEMPELAJARI  → learning event
🧩 MEMORI       → memory operation
```

### Format Streaming:
```
[🧠 BERPIKIR] [HH:MM:SS] Menganalisis permintaan
[📋 MENGURAI] [HH:MM:SS] Memecah menjadi 3 sub-tugas
[🔀 MERUTEKAN] [HH:MM:SS] → memilih skill: coding-agent
[⚙️ MENERAPKAN] [HH:MM:SS] Generate kode...
[✨ SELESAI] [HH:MM:SS] Selesai dalam 2.5 detik
```

### Anti-Duplicate Streaming:
- ✅ Tulis label streaming ke stdout/logging
- ❌ JANGAN tulis label streaming ke response body
- ❌ JANGAN duplicate streaming via subagent + response

---

## 🛡️ ANTI-BLOCKING RULES

### Masalah: TUI watchdog timeout karena sequential exec blocking.

### Solusi:

1. **Batch Reads** — Gabungkan multiple reads:
   ```bash
   # ❌ BAD: 5 sequential reads
   cat file1.txt && cat file2.txt && cat file3.txt
   
   # ✅ GOOD: Single parallel read
   (cat file1.txt; cat file2.txt; cat file3.txt)
   ```

2. **Background Exec** — Long-running commands:
   ```python
   exec(command, background=True)  # Tidak block session
   ```

3. **Never Sequential >2** — Maksimal 2 exec calls berturut-turut:
   ```
   exec → output text → exec → output text → exec → output text
   ```

4. **Kirim Teks Saat Tool Berjalan** — Streaming during exec:
   ```
   exec("long command") 
   → output "[⚙️ MENERAPKAN] Menjalankan..."
   ```

5. **Parallel When Possible** — Simultaneous vs sequential:
   ```bash
   # ✅ Parallel reads
   cat file1.txt &
   cat file2.txt &
   cat file3.txt &
   wait
   ```

---

## 🛡️ ANTI-STUCK RULES

### Masalah: ILMA diam total setelah deliver hasil.

### Solusi:

1. **Wajib Concluding Message** — Setelah task besar:
   ```
   ✅ Task selesai. ILMA standby — kirim tugas berikutnya kapan saja.
   ```

2. **Heartbeat Saat Tunggu** — HANYA jika diminta owner:
   ```bash
   python3 scripts/ilma_progress_tracker.py <chat_id> <session_key> &
   ```

3. **Wajib Concluding Sebelum Yield:**
   ```
   [⏳ MENUNGGU] Subagent ID: xxx — hasil akan di-report otomatis.
   ```

4. **DILARANG Periodic "ILMA online" Cron** — Tanpa request explisit.

5. **Orphan Check Saat Boot** — Kill sessions >30 menit.

---

## 🔧 SKILL DISCOVERY

### Auto-Discovery Path:
Skills di-discover dari `/root/.hermes/profiles/ilma/skills/` saat runtime.

### Skill Structure:
```
skills/
├── [skill-name]/
│   ├── manifest.json       # Skill metadata
│   └── [skill files...]
└── [skill-name].json       # Single-file skill manifest
```

### List Skills:
```bash
python3 /root/.hermes/profiles/ilma/ilma_capability_orchestrator.py --list-skills
```

---

## 📊 EVIDENCE SYSTEM

### Evidence Directory:
`~/.cache/ilma/evidence/`

### Evidence Types:
- `task_planned_[timestamp].json` — Task planning data
- `capability_analysis_[timestamp].json` — Classification results
- `skill_triggered_[timestamp].json` — Skill execution
- `model_routing_[timestamp].json` — Router decisions
- `memory_save_[timestamp].json` — Memory operations
- `learning_events.jsonl` — All learning events

### Get Recent Evidence:
```bash
python3 /root/.hermes/profiles/ilma/ilma_capability_orchestrator.py --evidence [event_type]
```

---

## 📈 SELF-IMPROVEMENT

### Run Self-Improvement Loop:
```bash
python3 /root/.hermes/profiles/ilma/ilma_capability_orchestrator.py --improve
```

### Analyze Learning Data:
```bash
python3 /root/.hermes/profiles/ilma/ilma_capability_orchestrator.py --analyze
```

### Check Status:
```bash
python3 /root/.hermes/profiles/ilma/ilma_capability_orchestrator.py --status
```

---

## 🔀 ROUTER COMMANDS

### Route a Task:
```bash
python3 /root/.hermes/profiles/ilma/ilma_router.py --route "[task]"
```

### List Models:
```bash
python3 /root/.hermes/profiles/ilma/ilma_router.py --list-models
python3 /root/.hermes/profiles/ilma/ilma_router.py --list-models --free-only
```

### Check Provider Health:
```bash
python3 /root/.hermes/profiles/ilma/ilma_router.py --health
python3 /root/.hermes/profiles/ilma/ilma_router.py --health openai
```

### Execution Stats:
```bash
python3 /root/.hermes/profiles/ilma/ilma_router.py --stats
```

---

## 🎯 FREE-TIER-FIRST POLICY

### Policy Rules:
1. Jika ada FREE model dengan score ≥ 80% dari best paid → pilih FREE
2. Jika task adalah fast_tasks → prioritas FREE
3. Jika tidak ada FREE yang memenuhi criteria → pilih best score
4. Fallback ke minimax jika semua gagal

### Check Free Models:
```bash
python3 /root/.hermes/profiles/ilma/ilma_router.py --list-models --free-only
```

---

## 🔍 TASK TYPE DETECTION

### Detection Keywords:
| Task Type | Keywords |
|-----------|----------|
| heavy_coding | fullstack, platform, sistem, arsitektur |
| medium_coding | api, backend, frontend, module, plugin |
| reasoning_xhigh | reasoning, analisis, planning, strategi |
| vision | image, gambar, foto, vision |
| fast_tasks | cepat, fast, quick, ringkas |
| free_tier | gratis, free, tanpa biaya |
| batch_processing | batch, bulk, massal |

### Force Task Type:
```bash
python3 /root/.hermes/profiles/ilma/ilma_router.py --route "[task]" --task-type reasoning_xhigh
```

---

## 📝 QUICK REFERENCE

### CLI Entry Point:
```bash
python3 /root/.hermes/profiles/ilma/ilma_orchestrator.py --task "[request]"
python3 /root/.hermes/profiles/ilma/ilma_orchestrator.py --task "[request]" --stream
```

### Capability Orchestrator:
```bash
python3 /root/.hermes/profiles/ilma/ilma_capability_orchestrator.py --classify "[task]"
python3 /root/.hermes/profiles/ilma/ilma_capability_orchestrator.py --plan "[task]"
python3 /root/.hermes/profiles/ilma/ilma_capability_orchestrator.py --list-skills
```

### Router:
```bash
python3 /root/.hermes/profiles/ilma/ilma_router.py --route "[task]"
python3 /root/.hermes/profiles/ilma/ilma_router.py --detect "[task]"
python3 /root/.hermes/profiles/ilma/ilma_router.py --health
```

---

*Panduan ini adalah referensi operasional utama ILMA. Selalu gunakan sebelum berinteraksi dengan sistem.*
