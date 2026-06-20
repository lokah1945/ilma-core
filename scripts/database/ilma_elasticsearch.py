#!/usr/bin/env python3
"""
ILMA Elasticsearch Query
======================
Elasticsearch query utilities.
"""

import subprocess
import json

ES_URL = "http://localhost:9200"

def es_get(path):
    # SECURITY: Converted from shell=True to list args (Phase 15B)
    # shlex.split not needed - path is constructed from internal functions
    import shlex
    cmd = ["curl", "-s", f"{ES_URL}{path}"]
    r = subprocess.run(cmd, shell=False, capture_output=True, text=True)
    return r.stdout

def es_post(path, body):
    # SECURITY: Converted from shell=True to list args (Phase 15B)
    import shlex
    cmd = ["curl", "-s", "-X", "POST", f"{ES_URL}{path}", "-H", "Content-Type: application/json", "-d", body]
    r = subprocess.run(cmd, shell=False, capture_output=True, text=True)
    return r.stdout

def list_indices():
    return es_get("/_cat/indices?v")

def search(index, query="{\"query\": {\"match_all\": {}}}"):
    return es_post(f"/{index}/_search", query)

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--indices", action="store_true")
    p.add_argument("--search")
    p.add_argument("--index")
    args = p.parse_args()
    if args.indices: print(list_indices())
    elif args.search and args.index: print(search(args.index, args.search))

if __name__ == "__main__": main()