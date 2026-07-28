# Session 2026-07-28 — Full Filesystem Redundancy Cleanup (ILMA/AYDA/ClawHub)

## Request
User: "bersih kan komponen atau file redudan yang berhubungan dengan ILMA, scan mulai
dari /root/ karena saya melihat ada banyak file tersebar tidak beraturan"
Follow-up: "lanjutkan. Sekalian semua file test misal /root/test_bytez.py atau file
bekas penggunaan yg tidak sengaja di buat di /root. Ada banyak file yg dibuat disana
tapi sebenarnya redudan dari ilma atau openclaw AYDA"

## What was found
- `find /root -iname '*ilma*'` → **15,050 items** total.
- Distribution triage showed **13,568 (90%) inside `/root/backup/`** — legitimate
  rollback, NOT redundant.
- Remaining ~1,500 spread across: `/root/ilma_audit_reports/` (101), `/root/upload/`
  (42), `/root/konsep/` (26), `/root/.deprecated/` (28), loose `test_*` (34),
  loose `update_*.py` (12, AYDA-era), `/root/ilma_audit_reports`, etc.
- **Biggest single win:** `/root/.hermes/profiles/ilma_test/` — 4.2 GB duplicate
  profile, 1,209 of the 1,209 residual `ilma*` items after excluding backup + active.

## Sequence executed (safe, no rollback-dir loss)
1. Disable+stop+rm-unit+kill-port+rm-code for `ilma-dashboard-backend`/`frontend`
   (ports 8000/3000) and `ilma-command-center` (port 18790) — earlier in session.
2. `/root/.deprecated/` (28) → deleted.
3. `/root/__pycache__/`, `/root/.pytest_cache/` → deleted.
4. 9 loose orphan `/root/ilma_*.py` → deleted; `ilma_intelligence_core.py` KEPT
   (importer found in active profile).
5. 34 `test_*` + 12 `update_*.py` + AYDA artifacts (`confirmed_llm_urls.json`,
   `llm_*_results.json`, `openai_endpoints.json`, `cleanup/patch_orchestrator/
   migrate_credentials.py`) → deleted.
6. OpenClaw/AYDA markers: `clawhub_data/`, `.bashrc.bak.ayda-removal-*` → deleted.
7. ILMA orphan loose: `ilma_modules_analysis.md`, `ILMA_PHASE_4F_*`, empty
   `ilma_model_router_data/` → deleted.
8. Old `journal*.log` (6) + `/root/archive/` → deleted.
9. Historis/state dirs (`ilma_audit_reports`, `hermes_ilma`, `.ilma`, `shared-memory`,
   `project`, `konsep`, `upload`, `audit_report`, `blueprint`, `collab`, `tutorial`)
   → deleted after confirming not referenced by active profile runtime.
10. **`/root/.hermes/profiles/ilma_test/` (4.2 GB)** → deleted (no systemd unit, no
    process, not referenced by active profile runtime).

## Kept (rollback / active / other-agent)
- `/root/backup/`, `/root/backups/`, `/root/backup_archive/`, `/root/ilma_reset_backup/`,
  `/root/ilma_sot_audit_backup/` — rollback points.
- `/root/wrapper/`, `wrapper_remote.git/` — 7 active wrapper services.
- `/root/.hermes/profiles/ilma/` — active profile (intact).
- `/root/.hermes/profiles/master-chief/` — other Hermes profile (skill refs to ILMA).
- 8 systemd units (`hermes-gateway-ilma`, `ilma-chrome`, `ilma-chrome@`, `ilma-sot-sync*`,
  `ilma-sync-*`) — active.
- `ilma_intelligence_core.py` — importer present.
- 46 residual `ilma*` (docs, logs, hermes-agent venv git refs, browser watchdog) —
  legitimate, deleting would break systems.

## Verification (post-cleanup)
- `systemctl --user is-active wrapper-nous wrapper-nvidia-python wrapper-model-registry`
  → all `active`.
- `ls -d /root/.hermes/profiles/ilma` → intact.
- 8 systemd units untouched.
- No system broke.

## Lesson
For "clean up redundant ILMA files across /root": exclude backup dirs + active profile
+ wrapper + other-agent profiles FIRST, triage by distribution, then delete
orphans/deprecated/tests/duplicate-profiles. Never delete backup* on a loose request.
Duplicate *profile* directories (e.g. `ilma_test`) are the highest-value, lowest-risk
targets once confirmed inactive.

## Tools used
- `ss -tlnp | grep ':PORT'` + `cat /proc/<pid>/cmdline` + `readlink /proc/<pid>/cwd`
  to confirm which component owns a port.
- `systemctl --user disable/stop/daemon-reload` to defeat `Restart=always`.
- `find ... | grep -vE EXCLUDE | sed 's|/[^/]*$||' | sort | uniq -c | sort -rn` for
  distribution triage.
- `grep -rl "\b$base\b" profile/*.py profile/scripts/*.py` for orphan import check.
