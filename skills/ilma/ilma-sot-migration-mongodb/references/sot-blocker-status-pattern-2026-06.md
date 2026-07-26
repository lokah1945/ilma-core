# SOT Blocker Status Report Pattern (P-35) — 2026-06-16

## Origin

Master Prompt ILMA v2 (Runtime Readiness Audit) was invoked on
2026-06-16. The audit was blocked at Step-2 (DB inspection) by a
MongoDB authentication failure (see
`sot-credential-rotation-2026-06.md`). The agent had to decide
what to deliver:

1. **Silent failure** — no report, no evidence → bad, violates
   Master Prompt Section 1 (Skepticism) and Section 14 (Tone)
2. **Fabricated "clean" report** — worse, violates Section 1
3. **Honest blocker report** — correct, this is the pattern

This reference documents the BLOCKER_STATUS.md template and
decision rules.

## When to use

Use this pattern when:
- An audit is blocked by **infrastructure** (auth, network,
  dependency missing, server down)
- NOT by **data defects** (those go in the normal 10-file
  audit report)
- The existing 10-file audit report represents a different
  point in time and may still be valid

## The carve-out rule (Constraint-0.2)

Master Prompt v2 Constraint-0.2 says: "JANGAN membuat file baru
— kecuali file REPORT di /root/upload."

A `BLOCKER_STATUS.md` IS a report (it documents the state of
the audit attempt). Therefore it is permitted under
Constraint-0.2.

The file MUST be:
- Saved to `/root/upload/` (or `/root/upload/report/` if it
  fits there)
- Named with a clear "blocker" prefix
- NOT replacing any existing 10-file report (those represent
  a different audit epoch)

## File integrity check (mandatory)

Before writing the BLOCKER_STATUS.md, prove the existing
10-file report is untouched. This protects against "you
overwrote my last report" complaints:

```python
import os
report_dir = "/root/upload/report"
expected_files = [
    "00_INDEX.md", "01_executive_summary.md",
    "02_audit_methodology.md", "03_critical_defects_found.md",
    "04_patches_applied.md", "05_loop_validation.md",
    "06_runtime_smoke_test.md", "07_runtime_queries.md",
    "08_known_issues.md", "09_git_sync.md", "10_appendix.md",
]
for f in expected_files:
    p = os.path.join(report_dir, f)
    if os.path.exists(p):
        size = os.path.getsize(p)
        print(f"  {f}: {size} bytes ✅")
    else:
        print(f"  {f}: MISSING ❌")
```

Include this check result in the BLOCKER_STATUS.md so Bos can
verify.

## Template

```markdown
# ILMA Runtime Audit — BLOCKER STATUS REPORT

**Tanggal:** {ISO timestamp}
**Auditor:** ILMA vX.YY
**Status:** ❌ **BLOCKED — {blocker description}**
**Referensi:** MASTER_PROMPT_ILMA_v2.md

---

## 🎯 RINGKASAN EKSEKUTIF

Audit komprehensif sesuai Master Prompt **TIDAK BISA DIMULAI**
karena blocker kritis pada lapisan {infra component}. Server
{server} reachable, namun {specific symptom}.

Sesuai **Skepticism Protocol Section 1** dan **Tone-14.6** dari
Master Prompt, ILMA tidak melanjutkan dengan asumsi atau data
fabrication. Laporan ini adalah status blocker resmi, bukan
hasil audit.

---

## 📊 EVIDENCE — HASIL VERIFIKASI

### 1. Server Reachability — {✅/❌}
- **Target:** `{host:port}`
- **Version/State:** {actual result, e.g. "MongoDB 7.0.31, server hidup"}
- **Status:** {description}

### 2. {Blocker Type} — {✅/❌}
{Kredensial/dependency/configuration yang diuji:}
- {test 1}: {result}
- {test 2}: {result}
- {test 3}: {result}
- {test 4}: {result}
- **Hasil:** {N}/{N} → {PASS/FAIL}

### 3. Kredensial Source — {✅/❌}
File `{path}` lines {N-M}:
```python
{actual code snippet}
```
Kredensial yang Bos berikan = {match/mismatch}.

### 4. Bukti Historis Sukses — {date}
File `{path}` ({N} bytes) menunjukkan audit
{detail sukses}:
```
{actual log excerpt, max 10 lines}
```

---

## 🎯 ROOT CAUSE HYPOTHESIS

{Explanation of what likely went wrong, with confidence level
and alternatives.}

---

## 📋 STEP YANG SUDAH DIKERJAKAN

| Step | Status | Evidence |
|------|--------|----------|
| Step-1: {desc} | ✅ | {evidence} |
| Step-2: {desc} | ⚠️ Partial | {evidence} |
| Step-3: {desc} | ❌ Blocked | {evidence} |
| ... | ... | ... |

---

## 🛡️ KEUTUHAN DATA EXISTING

Sesuai Constraint-0.13 (JANGAN menghapus data) dan
Constraint-0.2 (JANGAN buat file baru kecuali report):

**TIDAK ADA** data pada `{protected paths}` yang dimodifikasi.
**TIDAK ADA** collection di MongoDB yang disentuh.
**TIDAK ADA** file script di SOT yang dimodifikasi.

{N} file report audit sebelumnya (Phase {N}, {date}) tetap
UTUH dan merepresentasikan state sistem saat itu. Laporan
blocker ini HANYA tambahan informasi.

---

## 📁 DAFTAR FILE REPORT

File existing (TIDAK diubah):
- `{file}` ({N} bytes, {date})
- ...

File BARU (laporan blocker ini):
- `/root/upload/BLOCKER_STATUS.md` (file ini)

---

## 🆕 KNOWN ISSUE BARU

**ISSUE-NEW-{NNN}: {Title} (P0 — Blocker)**
- **Gejala:** {actual error}
- **Target:** {host:port, db name}
- **{Tested config}:** {N}/{N} {result}
- **Historis:** {date} {success/fail}
- **Dampak:** SELURUH audit runtime readiness BLOCKED.
  Tidak bisa inspect, query, atau patch data.
- **Rekomendasi ke Bos:**
  1. {action 1}
  2. {action 2}
- **Status:** OPEN — butuh tindakan dari Bos / admin

---

## 📌 REKOMENDASI AKSI

1. **Bos:** {specific action 1 with file paths to update}
2. **Setelah {trigger}:** Re-run `{specific command}`
3. **Cross-check:** {how to verify}

---

## ✅ COMPLIANCE DENGAN MASTER PROMPT

| Section | Kepatuhan |
|---------|-----------|
| Section 0 — Constraints | ✅ {brief evidence} |
| Section 1 — Skepticism | ✅ {brief evidence} |
| Section 14 — Tone | ✅ {brief evidence} |

---

**Status:** ❌ **NOT READY — Blocker: {blocker description}**
**Timestamp:** {ISO}
**Tanda tangan:** ILMA vX.YY — audit suspended pending {resolution}
```

## Decision rules

| Situation | Action |
|---|---|
| Audit blocked by infra (this pattern) | BLOCKER_STATUS.md |
| Audit completed with defects | Normal 10-file report |
| Audit completed clean | Normal 10-file report (clean) |
| Audit partially completed (some steps blocked) | Normal 10-file report with KNOWN ISSUES section |
| Blocker resolved mid-session | Run full audit, BLOCKER_STATUS.md remains as historical artifact |

## Evidence JSON (optional but recommended)

Save a machine-readable evidence JSON alongside the
BLOCKER_STATUS.md for future automated analysis:

```python
evidence = {
    "timestamp": ts,
    "status": "BLOCKED",
    "blocker": "MongoDB authentication failure",
    "mongo_target": "172.16.103.253:27017",
    "database": "credentials",
    "credentials_tested": [
        {"user": "quantumtraffic", "authSource": "admin", "directConnection": True, "result": "FAIL"},
        ...
    ],
    "server_reachable": True,
    "mongo_version": "7.0.31",
    "historical_success": {
        "date": "2026-06-15 00:36:54",
        "evidence": "/tmp/loop_1000.log",
        "result": "1000/1000 clean, 115.8s"
    },
    "files_created": ["/root/upload/BLOCKER_STATUS.md"],
    "files_modified": [],
    "compliance": {
        "constraint_0_2": "PASS - report file only",
        "section_1_skepticism": "PASS - no fabricated data",
        "section_14_tone": "PASS - honest blocker report"
    }
}
```

Save to `/root/upload/blocker_evidence.json` (1-2 KB typical).

## Worked example (2026-06-16)

- Master Prompt v2 invoked by Bos
- Step-2 DB inspection: MongoDB reachable ✅
- Step-2 continued: Auth failed ❌ (4/4 combinations)
- Decision: generate BLOCKER_STATUS.md (preserve old 10-file
  report from 2026-06-15)
- Files created:
  - `/root/upload/BLOCKER_STATUS.md` (6844 bytes)
  - `/root/upload/blocker_evidence.json` (1284 bytes)
- Files modified: NONE
- Status verdict: `❌ NOT READY — Blocker: MongoDB Authentication Failure`
- Compliance: Constraint-0.2 ✅, Section 1 ✅, Section 14 ✅

## What NOT to do

❌ **Don't write a 10-file report with all "0 defects" when
you never ran the audit** — that's fabrication, not
"inheriting from last run". The 10-file report structure
implies a completed audit.

❌ **Don't overwrite the old 10-file report** — it represents
a different audit epoch (2026-06-15). Overwriting destroys
historical evidence.

❌ **Don't silently wait for the blocker to resolve** — Bos
needs to know the audit didn't run.

❌ **Don't claim "audit complete" or "RUNTIME READY"** when
the audit didn't run. The Master Prompt Section 11 verdict
is binary: `RUNTIME READY` or `NOT READY`. Blocked = NOT
READY.

❌ **Don't add the BLOCKER_STATUS.md to the 10-file report
directory** (`/root/upload/report/`) — keep it separate
(`/root/upload/`) so it's clearly distinguished from a
normal audit report.
