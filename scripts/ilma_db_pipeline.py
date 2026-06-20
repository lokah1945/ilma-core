#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║     ILMA DB PIPELINE — CLI Wrapper                                         ║
║     Canonical entry point for ILMA Model DB Manager                        ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  PURPOSE                                                                      ║
║    Thin CLI wrapper around scripts/ilma_model_db_manager.py                 ║
║    (the SINGLE SOURCE OF TRUTH for model database updates).                  ║
║                                                                              ║
║  WHAT IT DOES                                                                 ║
║    • Runs AA scraper (optional, run first)                                    ║
║    • Sync providers → MASTER                                                  ║
║    • Run passive benchmark                                                     ║
║    • Enrich + AA benchmark merge → MASTER                                     ║
║    • Auto git push on success (--cron mode)                                    ║
║    • Delivers output to origin channel                                        ║
║                                                                              ║
║  CRON SCHEDULE                                                                ║
║    00:00 and 12:00 WIB (17:00 and 05:00 UTC)                                 ║
║    0 0,12 * * * python3 /root/.hermes/profiles/ilma/scripts/ilma_db_pipeline.py --cron
║                                                                              ║
║  USAGE                                                                       ║
║    python3 scripts/ilma_db_pipeline.py --full-sync         # all steps       ║
║    python3 scripts/ilma_db_pipeline.py --cron               # cron mode       ║
║    python3 scripts/ilma_db_pipeline.py --stats             # read stats      ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

LOCK_FILE  = Path("/tmp/ilma_model_db.lock")
PROFILE    = Path(os.environ.get("ILMA_PROFILE", "/root/.hermes/profiles/ilma"))
MANAGER_PY = PROFILE / "scripts" / "ilma_model_db_manager.py"
SCRAPER_PY = PROFILE / "scripts" / "aa_scraper" / "aa_scraper.py"


def _acquire_lock() -> bool:
    """Prevent concurrent runs."""
    if LOCK_FILE.exists():
        pid = LOCK_FILE.read_text().strip()
        # Check if process is still alive
        try:
            os.kill(int(pid), 0)
            print(f"[LOCK] Another instance running (PID {pid}) — exiting")
            return False
        except OSError:
            print(f"[LOCK] Stale lock from PID {pid} — removing")
            LOCK_FILE.unlink(missing_ok=True)
    LOCK_FILE.write_text(str(os.getpid()))
    return True


def _release_lock():
    LOCK_FILE.unlink(missing_ok=True)


def _git_push():
    """Auto commit + push after sync."""
    try:
        subprocess.run(["git", "add",
                        "ilma_model_router_data/PROVIDER_INTELLIGENCE_MASTER.json"],
                       cwd=str(PROFILE), check=True, capture_output=True)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        sub = subprocess.run(
            ["git", "commit", "-m",
             f"chore(model-db): auto-sync {ts}"],
            cwd=str(PROFILE), check=True, capture_output=True, text=True
        )
        subprocess.run(["git", "push", "origin", "master"],
                       cwd=str(PROFILE), check=True, capture_output=True)
        print(f"[GitPush] ✅ {sub.stdout[:200]}")
    except Exception as e:
        print(f"[GitPush] ⚠️  {e}")


def main():
    parser = argparse.ArgumentParser(
        description="ILMA DB Pipeline — CLI Wrapper for ModelDatabaseManager")
    parser.add_argument("--full-sync",  action="store_true",
                        help="Run complete pipeline (default if no flags)")
    parser.add_argument("--sync-all",   action="store_true",
                        help="Sync providers only")
    parser.add_argument("--sync-providers",  action="store_true",
                        help="Cloud APIs → MASTER")
    parser.add_argument("--passive-benchmark", action="store_true",
                        help="Usage log → benchmark DB")
    parser.add_argument("--enrich",     action="store_true",
                        help="Capabilities + scores → MASTER")
    parser.add_argument("--scrape-aa",  action="store_true",
                        help="Run AA scraper → benchmark_aa_cache.json")
    parser.add_argument("--stats",     action="store_true",
                        help="Show current stats")
    parser.add_argument("--dry-run",   action="store_true",
                        help="Preview changes, no writes")
    parser.add_argument("--cron",      action="store_true",
                        help="Cron mode: full-sync + git push + deliver")
    parser.add_argument("--daemon",    action="store_true",
                        help="Daemon mode: loop forever")
    parser.add_argument("--no-git-push", action="store_true",
                        help="Skip git push (even in cron mode)")
    args = parser.parse_args()

    # Default to full-sync if no specific flags given
    if not any([args.full_sync, args.sync_all, args.sync_providers,
                args.passive_benchmark, args.enrich, args.stats, args.cron, args.daemon,
                args.scrape_aa]):
        args.full_sync = True

    # Handle --scrape-aa standalone
    if args.scrape_aa and not args.cron and not args.full_sync:
        if not _acquire_lock():
            sys.exit(1)
        try:
            print(f"[Pipeline] Running AA scraper...")
            result = subprocess.run(
                [sys.executable, str(SCRAPER_PY)],
                cwd=str(PROFILE)
            )
            sys.exit(result.returncode)
        finally:
            _release_lock()

    # Build command for subprocess call
    cmd = [sys.executable, str(MANAGER_PY)]
    if args.full_sync:   cmd.append("--full-sync")
    if args.sync_all:    cmd.append("--sync-all")
    if args.sync_providers:   cmd.append("--sync-providers")
    if args.passive_benchmark: cmd.append("--passive-benchmark")
    if args.enrich:      cmd.append("--enrich")
    if args.stats:       cmd.append("--stats")
    if args.dry_run:     cmd.append("--dry-run")

    # Cron mode → full-sync + git push
    if args.cron:
        cmd = [sys.executable, str(MANAGER_PY), "--full-sync"]
        if args.dry_run:
            cmd.append("--dry-run")
        if not args.no_git_push:
            cmd.append("--git-push")

    # Daemon mode
    if args.daemon:
        print("[ILMA DB PIPELINE] Daemon mode — running every 12 hours")
        while True:
            if not _acquire_lock():
                time.sleep(300)
                continue
            result = subprocess.run(
                [sys.executable, str(MANAGER_PY), "--full-sync", "--git-push"],
                cwd=str(PROFILE)
            )
            _release_lock()
            if result.returncode != 0:
                print(f"[DAEMON] Exit code {result.returncode} — retry in 30 min")
                time.sleep(1800)
            else:
                print("[DAEMON] Done. Sleeping 12 hours...")
                time.sleep(43200)
        return

    # Normal mode: acquire lock + run
    # Note: we skip lock here because ilma_model_db_manager.py handles its own locking
    # when run as a subprocess (pipeline is the parent, manager is the child)
    try:
        print(f"[Pipeline] Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, cwd=str(PROFILE))
        sys.exit(result.returncode)
    finally:
        _release_lock()


if __name__ == "__main__":
    main()