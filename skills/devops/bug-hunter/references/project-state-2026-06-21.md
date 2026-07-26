# bug-hunter — Project State (2026-06-21)

## Born
Bos directive: "jika ada bug, langsung saja bereskan, buat skill baru bernama bug-hunter, skill wajib auto learn dan auto improve jadi akan terus berkembang seiring berjalannya waktu ketika menemukan bug, diminta mencari bug, dan apapun yg berhubungan dengan. bug-hunter tidak hanya mencari bug, tapi sekaligus bisa menyelesaikannya"

## v1.0.0 — Shipped
- Skill: `~/.hermes/profiles/ilma/skills/devops/bug-hunter/SKILL.md`
- Script: `~/.hermes/profiles/ilma/scripts/bug_hunter.py` (~31 KB)
- Persistent state:
  - `~/.hermes/profiles/ilma/bug_ledger.jsonl` (append-only)
  - `~/.hermes/profiles/ilma/bug_hunter_heuristics.json` (evolves)

## Operating principle
bug-hunter adalah agen OTONOM, bukan skill dokumentasi. Ia:
1. **Detect** — proactive scan + trigger match
2. **Diagnose** — systematic-debugging inline
3. **Fix** — minimal diff + regression test
4. **Verify** — judge system + test pass
5. **Learn** — append to ledger + auto-promote heuristic
6. **Evolve** — playbook promotion saat threshold

## First two bugs in ledger

### BUGID-20260620-0001 (tool_action_shape, MEDIUM, verified)
- **Symptom:** `memory tool remove/replace actions return 'old_text is required' looped 5x in same turn`
- **Root cause:** Tool shape mismatch — actions with old_text field require string param; sandboxed closure omitted field despite schema hint.
- **Fix:** Workaround `add` shape via batch `operations: [...]`. Confirmed plugins work via add path; replace/remove intermittent.
- **Reusable pattern:** When tool action with old_text loops, fallback to add shape. introspect via execute_code if signature unclear.

### BUGID-20260621-0001 (bug_hunter_self_bug, LOW)
- **Symptom:** `BUGID-YYYYMMDD used UTC.date() — server in WIB so returned 20260620 instead of 20260621`
- **Root cause:** datetime.now(timezone.utc).strftime('%Y%m%d') picks UTC date, but ledger is read by humans in WIB.
- **Fix:** Patched `next_bug_id` to use `today_id_prefix()` (local TZ).
- **Lesson:** bug IDs pakai local TZ untuk konsistensi operator-side; `detected_at` tetap UTC ISO untuk sortable timeline.

## E2E verified

```bash
python3 ~/.hermes/profiles/ilma/scripts/bug_hunter.py init
python3 ~/.hermes/profiles/ilma/scripts/bug_hunter.py diagnose --error "old_text is required for 'remove' action."
python3 ~/.hermes/profiles/ilma/scripts/bug_hunter.py learn --symptom "..." --root-cause "..." --category to...)
python3 ~/.hermes/profiles/ilma/scripts/bug_hunter.py fix --bug-id BUGID-...
python3 ~/.hermes/profiles/ilma/scripts/bug_hunter.py evolve
python3 ~/.hermes/profiles/ilma/scripts/bug_hunter.py stats
```

## Cron wiring (proposed)

```bash
# nightly scan low-severity drift
0 3 * * * python3 ~/.hermes/profiles/ilma/scripts/bug_hunter.py scan --scope scripts/ --severity medium > /tmp/bh.log
0 4 * * 0 python3 ~/.hermes/profiles/ilma/scripts/bug_hunter.py evolve  # weekly evolution
```

## Next milestones
- v1.1: integrate `ilma_judge_system` verify hook setelah `fix`
- v1.2: bug-hunter triggers on chat-pattern detection (regex stack trace)
- v1.3: emit `ILMA-EVID-YYYYMMDD-BUGHUNTER-NNNN` ke evidence ledger setiap resolved
