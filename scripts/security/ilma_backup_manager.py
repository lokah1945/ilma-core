#!/usr/bin/env python3
"""
ILMA Backup Manager
=================
Automated backup management.
"""

import subprocess
import tarfile
import gzip
from pathlib import Path
from datetime import datetime

BACKUP_DIR = Path("/root/.hermes/profiles/ilma/backups")
BACKUP_DIR.mkdir(exist_ok=True)

def backup_files(src, name=None):
    """Backup files to tar.gz."""
    if name is None:
        name = src.replace("/", "_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"{name}_{timestamp}.tar.gz"
    
    with tarfile.open(backup_file, "w:gz") as tar:
        tar.add(src)
    print(f"✅ Backup: {backup_file}")
    return backup_file

def backup_git(repo_path):
    """Backup git repository."""
    import git
    repo = git.Repo(repo_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"git_{Path(repo_path).name}_{timestamp}.tar.gz"
    
    with tarfile.open(backup_file, "w:gz") as tar:
        tar.add(repo_path, arcname=repo.working_dir)
    print(f"✅ Git backup: {backup_file}")

def list_backups():
    """List all backups."""
    for f in sorted(BACKUP_DIR.iterdir(), reverse=True)[:20]:
        size = f.stat().st_size / 1024
        print(f"  {f.name:50} {size:.1f} KB")

def restore_backup(backup_file, dest):
    """Restore from backup."""
    with tarfile.open(backup_file, "r:gz") as tar:
        tar.extractall(dest)
    print(f"✅ Restored to: {dest}")

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--backup", help="Path to backup")
    parser.add_argument("--git", help="Git repo to backup")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--restore", type=Path)
    parser.add_argument("--dest", type=Path)
    args = parser.parse_args()
    
    if args.backup:
        backup_files(args.backup)
    elif args.git:
        backup_git(args.git)
    elif args.list:
        list_backups()
    elif args.restore and args.dest:
        restore_backup(args.restore, args.dest)

if __name__ == "__main__":
    main()