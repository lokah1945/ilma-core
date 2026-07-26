#!/usr/bin/env python3
"""
ILMA Postgres Manager
===================
PostgreSQL management scripts.
"""

import subprocess

def run_sql(sql):
    """Execute SQL query. SECURITY: Converted from shell=True to list args (Phase 15B)"""
    cmd = ["psql", "-c", sql]
    return subprocess.run(cmd, shell=False, capture_output=True, text=True)

def list_databases():
    """List all databases."""
    result = run_sql("\\l")
    print(result.stdout)

def list_tables(db="public"):
    """List tables in database."""
    result = run_sql(f"\\dt {db}.*")
    print(result.stdout)

def backup_db(name, path="/backups"):
    """Backup database. SECURITY: Converted from shell=True (Phase 15B)"""
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"{path}/{name}_{timestamp}.sql"
    cmd = ["pg_dump", name]
    print(f"Backing up: {name} -> {backup_file}")
    with open(backup_file, "w") as out:
        subprocess.run(cmd, shell=False, stdout=out, check=False)
    print(f"✅ Backup complete: {backup_file}")

def restore_db(name, backup_file):
    """Restore database from backup. SECURITY: Converted from shell=True (Phase 15B)"""
    cmd = ["psql", name]
    print(f"Restoring: {backup_file} -> {name}")
    with open(backup_file, "r") as inp:
        subprocess.run(cmd, shell=False, stdin=inp, check=False)
    print(f"✅ Restore complete")

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--list-dbs", action="store_true")
    parser.add_argument("--list-tables", action="store_true")
    parser.add_argument("--backup")
    parser.add_argument("--restore")
    args = parser.parse_args()
    
    if args.list_dbs:
        list_databases()
    elif args.list_tables:
        list_tables()
    elif args.backup:
        backup_db(args.backup)
    elif args.restore:
        import sys
        if len(sys.argv) < 4:
            print("Usage: --restore <db_name> <backup_file>")
        else:
            restore_db(args.restore, sys.argv[3])

if __name__ == "__main__":
    main()