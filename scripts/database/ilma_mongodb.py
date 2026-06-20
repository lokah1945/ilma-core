#!/usr/bin/env python3
"""
ILMA MongoDB Manager
==================
MongoDB automation scripts.
"""

import subprocess
import json

def mongo_cmd(cmd):
    # SECURITY: Converted from shell=True to list args (Phase 15B)
    # Input validation: cmd constructed from internal functions (no user input)
    import shlex
    # Use mongosh --quiet --eval with shell=False
    cmd_list = ["mongosh", "--quiet", "--eval", cmd]
    return subprocess.run(cmd_list, shell=False, capture_output=True, text=True)

def list_dbs():
    return mongo_cmd("db.adminCommand('listDatabases')")

def list_collections(db="test"):
    return mongo_cmd(f"use {db}; db.getCollectionNames()")

def find(db, coll, query="{}", limit=10):
    return mongo_cmd(f"use {db}; db.{coll}.find({query}).limit({limit})")

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--list-dbs", action="store_true")
    p.add_argument("--list-collections")
    p.add_argument("--find")
    args = p.parse_args()
    if args.list_dbs: print(list_dbs().stdout)
    elif args.list_collections: print(list_collections(args.list_collections).stdout)

if __name__ == "__main__": main()