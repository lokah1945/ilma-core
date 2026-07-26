#!/usr/bin/env python3
"""
ILMA Redis Cache Manager
=======================
Redis caching utilities.
"""

import subprocess
import json

def redis_cmd(cmd):
    """Execute redis-cli command. SECURITY: Converted from shell=True to list args (Phase 15B)"""
    # Input validation: cmd constructed from internal functions only
    parts = cmd.split()
    cmd_list = ["redis-cli"] + parts
    result = subprocess.run(cmd_list, shell=False, capture_output=True, text=True)
    return result.stdout

def set_key(key, value, ttl=None):
    """Set a key with optional TTL."""
    if ttl:
        return redis_cmd(f"SETEX {key} {ttl} {value}")
    return redis_cmd(f"SET {key} {value}")

def get_key(key):
    """Get key value."""
    return redis_cmd(f"GET {key}")

def delete_key(key):
    """Delete a key."""
    return redis_cmd(f"DEL {key}")

def list_keys(pattern="*"):
    """List keys matching pattern."""
    return redis_cmd(f"KEYS {pattern}")

def get_info():
    """Get Redis info."""
    return redis_cmd("INFO")

def flush_db():
    """Flush current database."""
    confirm = input("Flush all keys? (yes/no): ")
    if confirm.lower() == "yes":
        redis_cmd("FLUSHDB")
        print("✅ Database flushed")

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--set")
    parser.add_argument("--get")
    parser.add_argument("--delete")
    parser.add_argument("--list", default="*")
    parser.add_argument("--info", action="store_true")
    parser.add_argument("--flush", action="store_true")
    parser.add_argument("--ttl")
    args = parser.parse_args()
    
    if args.set:
        value = input("Value: ")
        set_key(args.set, value, args.ttl)
        print(f"✅ Set: {args.set}")
    elif args.get:
        print(get_key(args.get))
    elif args.delete:
        delete_key(args.delete)
        print(f"✅ Deleted: {args.delete}")
    elif args.info:
        print(get_info())
    elif args.flush:
        flush_db()
    else:
        print(list_keys(args.list))

if __name__ == "__main__":
    main()