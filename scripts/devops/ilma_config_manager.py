#!/usr/bin/env python3
"""
ILMA Config Manager
=================
Configuration file management.
"""

import json
import yaml
try:
    import tomllib as toml
except ImportError:
    import tomli as toml
from pathlib import Path

def read_config(path):
    """Read config file (json/yaml/toml)."""
    with open(path) as f:
        if path.endswith(".json"):
            return json.load(f)
        elif path.endswith((".yaml", ".yml")):
            return yaml.safe_load(f)
        elif path.endswith(".toml"):
            return toml.load(f)
        return f.read()

def write_config(path, data, format=None):
    """Write config file."""
    if format is None:
        format = path.suffix
    with open(path, "w") as f:
        if format == ".json":
            json.dump(data, f, indent=2)
        elif format in (".yaml", ".yml"):
            yaml.dump(data, f)
        elif format == ".toml":
            toml.dump(data, f)

def merge_configs(base, override):
    """Merge two config dicts."""
    result = base.copy()
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = merge_configs(result[k], v)
        else:
            result[k] = v
    return result

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--read", type=Path)
    parser.add_argument("--write", type=Path)
    parser.add_argument("--merge", nargs=2, type=Path)
    args = parser.parse_args()
    
    if args.read:
        print(read_config(args.read))
    elif args.merge:
        base = read_config(args.merge[0])
        override = read_config(args.merge[1])
        result = merge_configs(base, override)
        print(result)
    elif args.write:
        data = json.loads(input("JSON data: "))
        write_config(args.write, data)

if __name__ == "__main__":
    main()