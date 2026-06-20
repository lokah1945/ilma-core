#!/usr/bin/env python3
"""
ILMA Backup System — AYDA-style automated backup
Mirrors: ayda_backup functionality
"""
import subprocess
import os
import sys
import tarfile
import json
from datetime import datetime
from pathlib import Path

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
]

def run(cmd, timeout=60):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.returncode == 0, r.stderr.strip()
    except subprocess.TimeoutExpired:
        return "TIMEOUT", False, ""
    except Exception as e:
        return str(e), False, ""

def create_backup():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"ilma_backup_{timestamp}.tar.xz"
    backup_path = f"{BACKUP_DIR}/{backup_name}"
    
    # Create tar.xz archive
    with tarfile.open(backup_path, "w:xz") as tar:
        for name, path in COMPONENTS:
            if os.path.exists(path):
                tar.add(path, arcname=name)
                print(f"  + {name}")
            else:
                print(f"  - {name} (skipped)")
    
    size = os.path.getsize(backup_path)
    print(f"\n✅ Backup created: {backup_name} ({size // 1024} KB)")
    
    # Symlink to latest
    latest = f"{BACKUP_DIR}/ilma_backup_latest.tar.xz"
    if os.path.exists(latest):
        os.remove(latest)
    os.symlink(backup_name, latest)
    
    # Cleanup old backups (keep last 7)
    backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith("ilma_backup_") and f.endswith(".tar.xz") and not f.endswith("_latest.tar.xz")])
    while len(backups) > 7:
        old = backups.pop(0)
        os.remove(f"{BACKUP_DIR}/{old}")
        print(f"  🗑 Removed old backup: {old}")
    
    return backup_path

def restore_backup(backup_name=None):
    if backup_name is None:
        latest = f"{BACKUP_DIR}/ilma_backup_latest.tar.xz"
        if not os.path.exists(latest):
            print("❌ No backup found")
            return False
        backup_name = latest
    
    print(f"⚠️  Restoring from: {backup_name}")
    print("  (this will overwrite current workspace)")
    
    with tarfile.open(backup_name, "r:xz") as tar:
        tar.extractall(WORKSPACE)
    
    print("✅ Restore complete")
    return True

def list_backups():
    if not os.path.exists(BACKUP_DIR):
        print("No backup directory found")
        return
    
    backups = [f for f in os.listdir(BACKUP_DIR) if f.startswith("ilma_backup_") and f.endswith(".tar.xz")]
    backups.sort(reverse=True)
    
    print(f"Backups in {BACKUP_DIR}:")
    for b in backups[:10]:
        path = f"{BACKUP_DIR}/{b}"
        size = os.path.getsize(path)
        mtime = datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M")
        is_latest = os.path.islink(f"{BACKUP_DIR}/ilma_backup_latest.tar.xz") and os.readlink(f"{BACKUP_DIR}/ilma_backup_latest.tar.xz") == b
        marker = " [LATEST]" if is_latest else ""
        print(f"  {mtime}  {b}  ({size // 1024} KB){marker}")

def main():
    if len(sys.argv) < 2:
        print("Usage: ilma_backup.py [create|restore|list]")
        sys.exit(1)
    
    cmd = sys.argv[1].lower()
    
    if cmd == "create":
        create_backup()
    elif cmd == "restore":
        restore_backup(sys.argv[2] if len(sys.argv) > 2 else None)
    elif cmd == "list":
        list_backups()
    else:
        print(f"Unknown command: {cmd}")

if __name__ == "__main__":
    main()
