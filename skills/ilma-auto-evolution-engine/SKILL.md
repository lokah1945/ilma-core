---
name: ilma-auto-evolution-engine
description: ILMA Auto Evolution Engine — SSS Tier self-improvement cycle adopted from ILMA v3
category: self-improvement
trigger: "evaluasi dirimu, upgrade ILMA, apa yang kamu pelajari, auto evolution"
---

# ILMA Auto Evolution Engine — SSS Tier

## Origin
Adopted from ILMA v3 Auto Evolution Engine (2026-05-06), modified for ILMA identity.

## Purpose
ILMA mengevaluasi dan mengembangkan dirinya secara otomatis, aman, terdokumentasi, dan berbasis bukti after setiap sesi kerja signifikan.

---

## ACTIVATION TRIGGER

AEC runs when:
- Task uses 3+ tool calls (complex task completed)
- Owner explicitly: "evaluasi dirimu", "upgrade ILMA", "apa yang kamu pelajari?"
- Owner explicitly triggers autonomous learning: "auto learning", "autonomous learning", "120 menit", "self-improvement pilot"

**Owner-triggered autonomous learning format (Indonesian):**
```
"auto learning selama [N] menit fokus [scope]. Jangan [forbidden actions]."
```
Examples:
- "auto learning selama 15 menit fokus registry truth audit"
- "auto learning selama 120 menit fokus safe improvement scope"
- Owner must specify duration and scope. Forbidden actions explicitly listed.

**Auto-learning is NOT always-on.** Only activates via explicit owner command. Cannot self-trigger.

---

## AUTO-EVOLUTION CYCLE (AEC)

```
[TRIGGER]
→ SESSION DEBRIEF
→ PERFORMANCE AUDIT
→ GAP ANALYSIS
→ IMPROVEMENT EXTRACTION
→ ILMA DNA UPDATE
→ UPGRADE BACKLOG UPDATE
→ NEXT SESSION PREP
[COMPLETE]
```

---

## STEP 1 — SESSION DEBRIEF

Q1. Tugas yang diselesaikan?
Q2. Target tercapai? Ya penuh / sebagian / tidak.
Q3. Quality Gate Score: __/100
Q4. Tools used: search/fetch/exec/file/memory/subagent/media
Q5. Error/failure dan solusi.
Q6. Feedback user eksplisit/implisit.
Q7. Output reusable yang dihasilkan.
Q8. Risiko yang ditemukan.

---

## STEP 2 — PERFORMANCE AUDIT

```
Akurasi hasil              : __/10 | target 9
Kelengkapan output         : __/10 | target 9
Kecepatan/efisiensi        : __/10 | target 9
Penggunaan tools           : __/10 | target 9
Evidence-based reasoning   : __/10 | target 9
Self-critique quality      : __/10 | target 8
Communication clarity      : __/10 | target 9
User satisfaction proxy    : __/10 | target 9
TOTAL                      : __/80 | target 71
```

**GRADE:**
- 72–80 = S (Exceptional)
- 64–71 = A (Excellent)
- 56–63 = B (Good)
- 48–55 = C (Adequate)
- <48 = D (Critical)

---

## STEP 3 — GAP ANALYSIS

```
GAP #[n]
Jenis      : Knowledge / Tool / Process / Communication / Reasoning / Speed
Dampak     : HIGH / MEDIUM / LOW
Bukti      : [kapan gap terlihat]
Root cause : [penyebab]
Mitigasi   : [cara menutup]
Prioritas  : P0 / P1 / P2 / P3
```

---

## STEP 4 — IMPROVEMENT EXTRACTION

```
IMPROVEMENT #[n]
Nama   : [nama]
Jenis  : best-practice / SOP / checklist / prompt / tool-combo / recovery
Masalah: [apa yang diselesaikan]
Validasi: [cara test]
```

---

## STEP 5 — ILMA DNA UPDATE

```
DNA UPDATE CANDIDATE
Rule     : [aturan]
Evidence : [bukti]
Scope    : [lingkup]
Risk     : [risiko]
Status   : proposed / applied / rejected
```

---

## STEP 6 — UPGRADE BACKLOG

```
UPGRADE #[n]
Nama     : [nama]
Priority : CRITICAL / HIGH / MEDIUM / LOW
Permission: YES / NO
Status   : proposed / approved / implemented
```

---

## STEP 7 — NEXT SESSION PREP

```
Last task           : [tugas terakhir]
Current state       : [state sekarang]
Open todos         : [todo belum selesai]
Known risks        : [risiko]
Recommended next   : [action]
```

---

## Critical Patterns Learned

### Claim Inflation Anti-Pattern (Phase 53-55)
When claiming test counts, categorize honestly:
- "159 pytest unit/integration tests PASS" + "368 parallel job validators PASS" = Correct
- "545/545 tests PASS" = WRONG (inflated, misleading)

Also: Do NOT claim SSS+++ achieved unless independently verified. Aspirational target only.

### Evidence ID Ledger Integrity (Phase 53-55)
When adding `evidence_id` to any capability:
1. Create ledger entry first
2. Then add evidence_id to capability registry
3. Verify both exist before moving on

Judge v4 `fabrication` criterion: evidence ID not in ledger = FAIL.

Pre-existing test failure fix: Changed `ILMA-EVID-20260510-JUDGE-001` → `ILMA-EVID-20260509-P30-QA_CRITIC-001` (exists in ledger). Got 212/212 PASS.

## References

- `references/phase56-production-entrypoint-activation.md` — **Phase 56: Production Entrypoint Activation.** `scripts/ilma.py` fully functional (1304-line rewrite), 3 bugs fixed (actor callback signature, mark_reused typo, validate/doctor imports), 254 tests PASS. ILMA v3.25.
- `references/phase53-55-internal-production-candidate.md` — Full Phase 53-55 lessons (evidence ledger integrity, claim inflation, blockers-first, judge v4 fabrication, service decomposition)
- `references/owner-triggered-autonomous-learning.md` — Full API reference, bug fixes, session trace schema, and Phase 48A-C learnings
- `references/phase48c-close-bug-fixes.md` — CRITICAL: Bug fixes for create_session API mismatch and negative scope parser (Phase 48C → Phase 48C-CLOSE). Required reading before writing any autonomous learning runner.
- `references/phase48e-lesson-retrieval-fix.md` — 4 bugs fixed: (1) `retrieve_for_task()` task_type filter excluded seeded lessons, (2) `sys.modules` cache not cleared after patch, (3) priority sort missing — seeded lessons lost, (4) `_extract_keywords()` missing composite phrases. Phase 48E session de5ec5e7.
- `references/phase48h-real-time-canary-reference.md` — First real-time canary (300.00s). Decision: lesson reuse must be proven in real-time to advance.
- `references/phase49-session-log.md` — Phase 49 agent body integration: runtime router, tool/skill selector (NEW), 16-phase workflow (NEW), 36 lessons (targeted). 179 tests, weak VERIFIED=0. Next: 30-min canary.
- `references/phase50-session-log.md` — **Phase 50 REAL-TIME 30-MIN CANARY PASSED (1800.03s wall-clock).** 5 critical bugs fixed: RoutingDecision namedtuple vs dict, TaskClass enum vs string, count_lessons() missing, TargetedLessonRetrieval import wrong, search() method missing. Ongoing gap: lesson query mapping (workflow_type → task_type). Decision: READY_FOR_300MIN_PREP.
- `references/realtime-canary-pattern.md` — **Real-time canary pattern (5-min ×3 proven, 30-min ×1 proven).** Wall-clock via `time.monotonic()`, canary runner template, 5 critical integration bugs, lesson query mapping gap, claim rules. Next: Phase 51 (300-min = 5 hours).

## Storage
- Reports: `~/.hermes/profiles/ilma/memory/auto_evolution/`
- DNA: `~/.hermes/profiles/ilma/memory/DNA_UPDATES.md`
- Backlog: `~/.hermes/profiles/ilma/memory/UPGRADE_BACKLOG.md`

## Trigger
After task with 3+ tool calls OR owner request "evaluasi dirimu" OR owner-triggered autonomous learning command
