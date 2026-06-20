---
name: bug-hunter
description: "Proactive autonomous bug hunter for ILMA. Detects, diagnoses, fixes, and learns from every bug encountered. Auto-evolves its detection heuristics and fix playbooks over time via persistent bug ledger. Triggered on any bug report, system anomaly, regression, error pattern, or scheduled scan."
version: 1.4.0
author: ILMA (Bos Huda Choirul Anam, 2026-06-21)
license: MIT
metadata:
  hermes:
    tags: [bug, debugging, hunting, autonomous, self-healing, self-evolution, auto-fix, learning]
    triggers:
      - "cari bug"
      - "ada bug"
      - "kenapa error"
      - "bug-nya apa"
      - "fix bug"
      - "scan bug"
      - "debug"
      - "regression"
      - "system anomaly"
      - any stack trace / error message in conversation
      - any "old_text is required" / tool-loop warning in conversation
      - any tool-loop warning (3+ same-tool retries)
    related_skills:
      - systematic-debugging
      - ilma-self-improvement
      - test-driven-development
      - ilma-state-verify-before-report
      - subagent-driven-development
      - ilma-self-improvement
      - test-driven-development
      - ilma-state-verify-before-report
---

# bug-hunter — Autonomous Bug Hunter & Solver (Auto-Evolving)

## Philosophy

> **"Setiap bug adalah data. Setiap fix adalah lesson. Setiap pattern menemukan dirinya lagi adalah bug hunter yang sudah berevolusi."**

Skill ini **BUKAN** dokumentasi pasif. bug-hunter adalah **agen hidup** yang:
1. **Mencari** bug secara proaktif (scanning, anomaly detection)
2. **Mendiagnosis** root cause (bukan symptom)
3. **Menyelesaikan** dengan minimal diff + regression test
4. **Belajar** dari setiap kasus → simpan ke bug ledger
5. **Berkembang** heuristik + playbook dari waktu ke waktu

## When to Use

**Otomatis aktif ketika:**
- ❌ Ada error message / stack trace di percakapan
- ❌ User sebut kata "bug", "error", "kenapa", "gagal", "rusak"
- ❌ Cron scan menemukan anomaly
- ❌ Test gagal / regression terdeteksi
- ❌ User minta "cari bug" / "scan bug" / "kenapa X error"

**Selalu invoked untuk:**
- Investigasi error class apapun (kemudian minta systemic-debugging kalau perlu forensic lebih dalam)
- Validasi bahwa "fix" yang baru dibuat benar-benar menyelesaikan masalah
- Onboarding bug baru ke ledger

## Architecture — Self-Evolving Loop

```
┌─────────────────────────────────────────────────────────────┐
│                       BUG-HUNTER LOOP                       │
│                                                             │
│   DETECT ──► DIAGNOSE ──► FIX ──► VERIFY ──► LEARN ──┐     │
│     ▲                                              │     │
│     └────────────────────── EVOLVE ◄───────────────┘     │
│   (heuristics updat dari lessons)                          │
└─────────────────────────────────────────────────────────────┘
```

### 5-Phase Operation

#### Phase 1 — DETECT
Trigger sources (urut prioritas):
1. **Direct trigger** — user sebut "bug"
2. **Error pattern detection** — regex terhadap error string, stack trace
3. **Anomaly scan** — `bug-hunter scan` jalankan parallel investigator
4. **Regression detection** — test failure / state divergence
5. **Scheduled scan** — cron menjalankan `bug-hunter scan --quiet`

Tools dipakai:
- `grep` / ripgrep — pattern scan
- `shellcheck`, `ruff`, `mypy` — static analysis
- `pytest` — regression catch
- `ps`, `journalctl`, `pm2 logs` — runtime anomaly

#### Phase 2 — DIAGNOSE
Jalan 4-phase systematic-debugging **inline**:
1. Read error full (jangan skip)
2. Reproduce konsisten (counter >1 kalau flaky)
3. Trace data flow (cari upstream cause)
4. Form hypothesis minimal

Jangan **pernah** fix tanpa root cause confirmed. Kalau stuck >3 attempts, escalate.

#### Phase 3 — FIX
Discipline:
- **Minimal diff** — 1 variable, 1 file kecuali memang multi-site
- **Backward compatible** — kalau bisa, kalau tidak ada owner approval
- **With regression test** — tambahkan test case ke `tests/`
- **With audit ID** — `BUGID-YYYYMMDD-NNNN`

#### Phase 4 — VERIFY
- Run regression test (RED → GREEN)
- Run full test suite (no new break)
- Judge system (`ilma_judge_system.py`) pass L1-L3
- Confirm fix benar-benar solves, bukan sym回避

#### Phase 5 — LEARN (auto-update ledger)
Wajib append ke `~/.hermes/profiles/ilma/bug_ledger.jsonl`:
```jsonl
{"bug_id":"BUGID-20260621-0001","detected_at":"2026-06-21T02:34:00Z","trigger":"user_report","symptom":"<apa yg user lihat>","root_cause":"<yang sebenarnya>","fix":"<ringkas diff/file>","files_touched":["..."],"regression_test":"<path>","category":"memory_tool","severity":"medium","resolution_s":"127","lesson":"replace action needs old_text param check before sending","reusable_pattern":"always verify tool action shape via execute_code introspect before send","confidence":"high","verified_by":"ilma_judge_system"}
```

#### EVOLVE Loop (background)
Setiap **N** entries (config: 10), `bug-hunter evolve`:
1. Aggregate lessons by category
2. Update heuristic patterns — bug baru yang match heuristic auto-flag
3. Promote proven fix patterns ke playbook templates
4. Garbage collect verified/resolved entries older than 90 hari
5. Emit evolution report

## CLI Surface

```bash
# Quick scan — proactive hunt dalam scope tertentu
python3 ~/.hermes/profiles/ilma/scripts/bug_hunter.py scan [--scope <path>] [--severity low|medium|high]

# Diagnose — given error message / stack trace, return root cause + suggested fix
python3 ~/.hermes/profiles/ilma/scripts/bug_hunter.py diagnose --error "<err msg>" --file <path>

# Auto-fix — solv e bug directly (with confirmation prompt unless --yes)
python3 ~/.hermes/profiles/ilma/scripts/bug_hunter.py fix --bug-id <id> [--yes]

# Learn — append a bug ke ledger
python3 ~/.hermes/profiles/ilma/scripts/bug_hunter.py learn --bug-id <id> --lesson "<text>"

# Evolve — run evolution cycle (heuristic updat)
python3 ~/.hermes/profiles/ilma/scripts/bug_hunter.py evolve

# List pending bugs
python3 ~/.hermes/profiles/ilma/scripts/bug_hunter.py list [--status open|in_progress|resolved]

# Stats — bug distribution + MTTR + top categories
python3 ~/.hermes/profiles/ilma/scripts/bug_hunter.py stats

# Export playbook — buat panduan fix patterns ter-top
python3 ~/.hermes/profiles/ilma/scripts/bug_hunter.py playbook --top 10

# ── v1.1 (judge hook) ────────────────────────────────────────────────
# Run ilma_judge_system.py quick after verify terhadap setiap files_touched
python3 ~/.hermes/profiles/ilma/scripts/bug_hunter.py verify --bug-id <id> --judge

# ── v1.2 (chat-pattern trigger) ─────────────────────────────────────
# Scan chat text untuk stack trace / Error / NXDOMAIN / port collide dll
# --auto-learn akan langsung append ke ledger (zero-click onboarding)
python3 ~/.hermes/profiles/ilma/scripts/bug_hunter.py trigger-scan --text "<user message>" [--auto-learn]

# ── v1.3 (evidence ledger emission) ─────────────────────────────────
# Otomatis di setiap `verify` — emit ILMA-EVID-YYYYMMDD-AUTO-<CAP>-NNN
# Format sesuai validator: evidence/ilma_evidence_ledger.json
# Skip manual: semua `fix` + `verify` sudah auto-emit.

# ── v1.4 (cron template) ────────────────────────────────────────────
# Generate jobs.json (nightly scan + weekly evolve) idempotent
python3 ~/.hermes/profiles/ilma/scripts/bug_hunter.py cron-template --emit
# → writes ~/.hermes/profiles/ilma/cron/bug_hunter_jobs.json
```

## Python API

```python
from bug_hunter import BugHunter

hunter = BugHunter()
hunter.load_ledger()

# Detect
findings = hunter.scan(scope="scripts/", severity="medium")

# Diagnose
diagnosis = hunter.diagnose(
    error="old_text is required for 'remove' action.",
    file=None,
    context="memory tool loop 5x"
)

# Fix (returns patch plan; doesn't auto-apply unless auto_apply=True)
plan = hunter.fix(bug_id="BUGID-20260621-0001")
# plan = {"bug_id","patches":[...],"regression_test":"->","estimated_lines":int}

# Verify
report = hunter.verify(bug_id="BUGID-20260621-0001")
# report = {"status":"verified","test_passed":True,"judge_score":0.92}

# Learn (writes to ledger)
hunter.learn(bug_id=..., lesson="...", reusable_pattern="...")

# Evolve
evolution = hunter.evolve()
# evolution = {"new_heuristics":[...],"promoted_playbooks":[...],"pruned_count":int}
```

## Auto-Learn Triggers

Skill ini **auto-update** setiap kali:

| Event | Source |
|-------|--------|
| Bug reported by user | Conversation pattern |
| Test fail | `pytest` exit code |
| Loop / retry 3+ | Tool telemetry |
| Stack trace di output | Regex match |
| `bug_ledger.jsonl` ada entry baru | Watcher |
| Cron scan menemukan anomaly | Scheduled |
| Fix sukses recorded | `ilma_judge_system.py` L1-L3 PASS |

## Bug Ledger Schema

Path: `~/.hermes/profiles/ilma/bug_ledger.jsonl`

```json
{
  "bug_id": "BUGID-YYYYMMDD-NNNN",
  "detected_at": "ISO8601",
  "resolved_at": "ISO8601|null",
  "trigger": "user_report|scan|regression|cron|auto",
  "status": "open|in_progress|verified|resolved|won't_fix",
  "symptom": "user-visible description",
  "root_cause": "actual cause (Phase 1 result)",
  "files_touched": ["path1","path2"],
  "fix_diff": "unified diff or summary",
  "regression_test": "tests/test_xxx.py::test_yyy",
  "category": "memory_tool|runtime|config|race_condition|...",
  "severity": "low|medium|high|critical",
  "resolution_s": 127,
  "attempt_count": 1,
  "lesson": "what we learned",
  "reusable_pattern": "generalized rule",
  "heuristic_signature": "regex for similar future bugs",
  "confidence": "low|medium|high",
  "verified_by": "ilma_judge_system|manual|test",
  "tags": ["freeform","labels"]
}
```

## Evolved Heuristics DB

Path: `~/.hermes/profiles/ilma/bug_hunter_heuristics.json`

```json
{
  "version": 1,
  "last_evolved": "ISO8601",
  "heuristics": [
    {
      "signature": "old_text is required for",
      "category": "tool_action_shape",
      "first_seen": "2026-06-21",
      "occurrences": 1,
      "auto_classify": "MEDIUM",
      "suggested_action": "introspect tool via execute_code before retry; use batch shape as workaround",
      "playbook_ref": "playbook/tool_action_shape/v1"
    }
  ],
  "playbooks": {
    "playbook/tool_action_shape/v1": {
      "steps": ["1. introspect tool signature", "2. send via documented shape", "3. fallback ke add shape"],
      "proven_count": 3
    }
  }
}
```

## Pitfalls (jangan dilanggar)

### ❌ Jangan Fix Tanpa Root Cause
Symptom-fix = anti-pattern. **Selalu** jalankan Phase 1 systematic-debugging.

### ❌ Jangan Bunuh Diri Sendiri
Kalau `bug-hunter fix` mau edit file ILMA core, **WAJIB** konfirmasi Bos (kecuali rule eksplisit). Auto-apply hanya untuk `scripts/` dan `tests/`.

### ❌ Jangan Loop Diri Sendiri
Kalau bug-hunter sendiri stuck atau error, **STOP** dan lapor ke Bos. Jangan auto-retry indefinitely.

### ❌ Jangan Asumsi
Verify always. "Bekerja" ≠ "Bener". Selalu test regression-nya.

### ❌ Jangan Lupa Category & Severity
Tanpa kategori → ledger tidak bisa di-aggregate. Tanpa severity → tidak bisa priority.

## Self-Improvement Mandate

Skill ini **WAJIB** berevolusi. Auto-triggers:
- Setiap lesson baru → update heuristic signature
- Setiap playbook baru → cek apakah perlu dipromosikan
- Weekly evolution run (cron opsional)
- Manual override: `bug-hunter evolve --force`

## Evidence Dispatch

Setiap fix → emit evidence ID `ILMA-EVID-YYYYMMDD-BUGHUNTER-NNNN` ke evidence ledger.

## Related Skills

- `systematic-debugging` — 4-phase root cause (inline use saat diagnose)
- `ilma-self-improvement` — high-level learning pattern
- `ilma-state-verify-before-report` — verify before claim "sudah fix"
- `test-driven-development` — regression test discipline
- `subagent-driven-development` — kalau perlu parallel investigation

## First Class Citizens

bug-hunter bukan feature — ini **warga kelas satu** di ILMA. Dipercaya untuk:
- Scan malam hari (cron)
- Onboard bug baru otomatis
- Solve sendiri kalau low-risk
- Escalate kalau architectural

Authored 2026-06-21 oleh Bos Huda Choirul Anam. "Jika ada bug, langsung saja bereskan" — bosverdict.
