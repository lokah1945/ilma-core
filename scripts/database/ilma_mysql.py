#!/usr/bin/env python3
"""
ILMA MySQL Manager
================
MySQL database operations.
"""

import subprocess

def run_mysql(sql):
    # SECURITY: Converted from shell=True to list args (Phase 15B)
    # Input validation: SQL is passed to internal functions only, not from user
    cmd = ["mysql", "-e", sql]
    return subprocess.run(cmd, shell=False, capture_output=True, text=True)

def list_dbs():
    return run_mysql("SHOW DATABASES;")

def list_tables(db):
    return run_mysql(f"USE {db}; SHOW TABLES;")

def backup_db(name, path="/backups"):
    from datetime import datetime
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    f = f"{path}/{name}_{ts}.sql"
    # SECURITY: Converted from shell=True to list args (Phase 15B)
    cmd = ["mysqldump", name]
    with open(f, "w") as out:
        subprocess.run(cmd, shell=False, stdout=out, check=False)
    print(f"✅ Backed up: {f}")

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--list-dbs", action="store_true")
    p.add_argument("--backup")
    args = p.parse_args()
    if args.list_dbs: print(list_dbs().stdout)
    elif args.backup: backup_db(args.backup)

if __name__ == "__main__": main()