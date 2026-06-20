#!/usr/bin/env python3
"""
ILMA Backup Script — Self-contained backup tool.
Phase 36G: Services decomposition (self-contained rewrite).
"""
import sys
import os
import json
import shutil
import tarfile
import hashlib
from datetime import datetime

WORKSPACE = "/root/.hermes/profiles/ilma"
BACKUP_DIR = "/root/backup/ilma"
PROFILE = "ilma"

COMPONENTS = [
    ("SOUL.md", f"{WORKSPACE}/SOUL.md"),
    ("USER.md", f"{WORKSPACE}/USER.md"),
    ("skills/", f"{WORKSPACE}/skills/"),
    ("scripts/", f"{WORKSPACE}/scripts/"),
    ("config/", f"{WORKSPACE}/config/"),
    ("memory/", f"{WORKSPACE}/memory/"),
    ("cron/", f"{WORKSPACE}/cron/"),
    ("cache/", f"{WORKSPACE}/.cache/"),
    ("state/", f"{WORKSPACE}/state/"),
    ("docs/", f"{WORKSPACE}/docs/"),
    ("tests/", f"{WORKSPACE}/tests/"),
]


def ensure_backup_dir():
    os.makedirs(BACKUP_DIR, exist_ok=True)


def create_backup():
    """Create a timestamped backup archive."""
    ensure_backup_dir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"backup_{PROFILE}_{ts}.tar.gz"
    backup_path = os.path.join(BACKUP_DIR, backup_name)

    with tarfile.open(backup_path, "w:gz") as tar:
        for name, path in COMPONENTS:
            if os.path.exists(path):
                tar.add(path, arcname=os.path.join(PROFILE, name))
                print(f"  + {name}")
            else:
                print(f"  - {name} (missing)")

    size = os.path.getsize(backup_path)
    print(f"\nBackup created: {backup_path} ({size} bytes)")
    return backup_path


def list_backups():
    """List all backups in backup directory."""
    ensure_backup_dir()
    backups = []
    for f in sorted(os.listdir(BACKUP_DIR)):
        if f.startswith(f"backup_{PROFILE}_") and f.endswith(".tar.gz"):
            path = os.path.join(BACKUP_DIR, f)
            backups.append({
                "file": f,
                "size": os.path.getsize(path),
                "modified": datetime.fromtimestamp(os.path.getmtime(path)).isoformat()
            })
    return backups


def restore_backup(backup_name):
    """Restore from a backup archive."""
    backup_path = os.path.join(BACKUP_DIR, backup_name)
    if not os.path.exists(backup_path):
        print(f"Backup not found: {backup_name}")
        return False

    # Extract to temp location first
    temp_dir = os.path.join(BACKUP_DIR, "restore_temp")
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir)

    with tarfile.open(backup_path, "r:gz") as tar:
        tar.extractall(temp_dir)

    # Copy back
    restore_root = os.path.join(temp_dir, PROFILE)
    for item in os.listdir(restore_root):
        src = os.path.join(restore_root, item)
        dst = os.path.join(WORKSPACE, item)
        if os.path.isdir(src):
            if os.path.exists(dst):
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)

    shutil.rmtree(temp_dir)
    print(f"Restored from: {backup_name}")
    return True


def run(args=None):
    """CLI entry point."""
    if args is None:
        args = sys.argv[1:]

    if not args or args[0] == "--help":
        print("ILMA Backup")
        print("Usage: python3 ilma_backup.py [create|list|restore <backup_name>]")
        print("  create   — Create a new backup")
        print("  list     — List available backups")
        print("  restore  — Restore from a backup")
        return 0

    cmd = args[0]
    if cmd == "create":
        create_backup()
        return 0
    elif cmd == "list":
        backups = list_backups()
        for b in backups:
            print(f"  {b['file']}  {b['size']:>10} bytes  {b['modified']}")
        return 0
    elif cmd == "restore":
        if len(args) < 2:
            print("Error: restore requires backup name")
            return 1
        return 0 if restore_backup(args[1]) else 1
    else:
        print(f"Unknown command: {cmd}")
        return 1


if __name__ == "__main__":
    sys.exit(run())