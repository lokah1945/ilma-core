# Filesystem Redundancy / Scattered-File Audit + Consolidation

Pattern from 2026-07-28 session: Bos asked to clean `/root` of redundant ILMA/AYDA/openclaw
leftover files, then consolidate `.md`/`.json` in the ILMA profile. Reusable recipe below.

## Audit sequence (ALWAYS do before deleting)
1. **Enumerate** without scanning all of `/root` (broad `grep -r /root` TIMES OUT at 60s):
   ```bash
   # Loose top-level ILMA-ish files
   ls -la /root/ | grep -iE 'ilma|dashboard|command|observ|ayda|claw|openclaw'
   # Count *ilma* everywhere, EXCLUDING backup*/profile/wrapper first
   find /root -iname '*ilma*' 2>/dev/null \
     | grep -vE '/\.hermes/profiles/ilma/|/\.hermes/skills/|/wrapper/|/backup/|/backups/|/backup_archive/|node_modules/' \
     | wc -l
   ```
2. **Classify** each hit into: `ACTIVE_SYSTEM` | `BACKUP_ROLLBACK` | `ORPHAN` | `DEPRECATED` | `HISTORY_STATIC` | `TEST_AYDA_LEFTOVER`.
3. **Verify zero runtime tie** BEFORE touching:
   ```bash
   # (a) importer of a loose module — scoped, NOT whole /root
   for f in audit_ilma.py ilma_benchmark_lookup.py ...; do
     base="${f%.py}"
     grep -rl "\b$base\b" /root/.hermes/profiles/ilma/*.py /root/.hermes/profiles/ilma/scripts/*.py \
       | head -1 && echo "USED $f" || echo "ORPHAN $f"
   done
   # (b) live writer process on a dir?
   lsof +D /root/ilma_reset_backup 2>/dev/null | grep -v '^COMMAND' | wc -l   # 0 = static
   # (c) symlinks pointing INTO candidate dir?
   find . -type l | xargs -I{} sh -c 't=$(readlink "{}"); case "$t" in *candidate*) echo "{}";; esac'
   # (d) referenced by systemd unit / cron?
   grep -rIl 'candidate_dir' /root/.config/systemd/user/ /root/.hermes/profiles/ilma/cron/ 2>/dev/null
   # (e) profile duplicate? active or stale?
   systemctl --user list-units --all | grep -i ilma_test   # none = safe delete
   ps aux | grep -i ilma_test | grep -v grep                  # no proc = safe
   ```
4. **Delete / archive** only after all checks pass.

## NEVER TOUCH (exclude list — deleting breaks systems)
- `whatsapp/session/` — Baileys WhatsApp cache (2400+ tiny JSON keys); deleting kills WA connection.
- `sessions/` — Hermes chat history (`.jsonl`).
- `config/`, `scripts/`, `skills/`, `sot/`, `data/`, `state/` — active runtime.
- Active systemd units (`hermes-gateway-ilma`, `ilma-chrome`, `ilma-sot-sync*`, `ilma-sync*`).
- `cron/output/` — **live** daily job reports (Bos reads them; mtime = today).
- `/root/wrapper/`, `wrapper_remote.git/` — Bos's 7 active proxy services.
- `/root/backup/`, `/backups/`, `/backup_archive/`, `ilma_reset_backup/`, `ilma_sot_audit_backup/` — rollback points (keep UNLESS Bos explicitly says "hapus semua termasuk backup").

## AYDA / openclaw leftover patterns (Bos wants these gone)
- Loose `test_*.py` / `test_*.sh` / `test_*.js` / `test_*.json` at `/root/` top level.
- `update_*.py` (per-provider AYDA-era scripts, e.g. `update_nvidia.py`, `update_bytez.py`).
- `clawhub_data/` directory (OpenClaw plugin cache).
- `.bashrc.bak.ayda-removal-*` markers.
- Stray `confirmed_llm_urls.json`, `llm_*_results.json`, `openai_endpoints.json`, `cleanup_providers.py`.
- Verify none are in a wrapper `ExecStart` via `systemctl --user show <unit> -p ExecStart | grep -oE 'update_|test_'`.

## Duplicate-content detection (most ILMA files have NONE)
Problem is dispersion, not dupes. Confirm with:
```bash
find evidence -type f \( -name '*.md' -o -name '*.json' \) -exec md5sum {} \; \
  | sort | awk '{print $1}' | uniq -d | wc -l   # dup groups count
```
If ~0 dup groups → consolidate by MOVE-to-archive, not delete.

## /root/ vs scripts/ copy divergence
A loose `/root/ilma_intelligence_core.py` may DIFFER from the live
`scripts/ilma_intelligence_core.py`. `diff -q` them; keep the scripts/ one,
delete the /root/ orphan ONLY if no importer references the /root/ path.

## Consolidation: archive + INDEX.md (preferred over delete)
When Bos says "rapikan / kumpulkan di mapping":
```bash
mkdir -p _archive/evidence_evolution_traces _archive/artifacts_phase54 \
         _archive/memory_optimization _archive/INDEX.md
mv evidence/evolution_traces/phase{48b,48c,48c_close,49,50,51,54} _archive/evidence_evolution_traces/
mv artifacts/phase54 _archive/artifacts_phase54/
mv memory/optimization _archive/memory_optimization/
```
Then write `_archive/INDEX.md` with:
- structure tree
- mapping table `asal → _archive/tujuan | file_count | status`
- explicit "TIDAK diarsip (masih aktif)" list (so future agents don't think it's lost)
- restore command (`mv _archive/<sub> <asal>`)

## Gotchas
- **Broad `grep -r /root` / `find /root -exec grep` TIMES OUT (60s).** Scope to profile + config; never scan whole `/root`.
- **`find /root -iname '*ilma*'` = 15k items, ~90% in `/root/backup/`.** Always exclude `backup*` before counting/acting.
- **Profile duplicate:** `ilma_test` (4.2 GB) was a stale testing clone — verify no unit/proc/importer, then `rm -rf` frees huge space.
- **Static backup dirs have no writer** (`lsof +D` = 0) but are rollback safety — keep unless Bos overrides.
- **`cron/output/` looks like history but is LIVE** (mtime = today, 3 active jobs). Don't archive.
- **Don't delete based on static AST scan alone** — dynamic `importlib`/`getattr` and CLI entry via `ilma_orphan_wiring` will false-positive as orphan.

## Result of 2026-07-28 run
- Deleted: `ilma_test` profile (4.2 GB), `.deprecated/` (28), 34 `test_*`, 12 `update_*`,
  `clawhub_data/`, AYDA artifacts, 9 loose orphan `ilma_*.py`, `ilma_audit_reports/`,
  `hermes_ilma/`, `.ilma/`, `shared-memory/`, `project/`, `konsep/`, `upload/`,
  `audit_report/`, `blueprint/`, `collab/`, `tutorial/`, old journals, `ilma_intelligence_core.py` (orphan /root/ copy),
  `ilma_reset_backup/` (1.6 GB), `ilma_sot_audit_backup/` (56 MB).
- Archived (not deleted): `evidence/evolution_traces/phase*`, `artifacts/phase54`, `memory/optimization` → `_archive/` + INDEX.md.
- Kept (active): `wrapper/`, profile `ilma/`, systemd units, `backup*/`, `cron/output/`, `whatsapp/session/`, `sessions/`.
- Verified: wrapper services `active`, profile intact, no broken system.
