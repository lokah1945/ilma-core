#!/usr/bin/env python3
"""
ILMA Log Aggregator
==================
Aggregate and analyze logs.
"""

import subprocess
import re
from pathlib import Path
from collections import Counter

def tail_log(path, lines=100):
    """Tail last N lines of log. SECURITY: Converted from shell=True to list args (Phase 15B)"""
    # Input validation: ensure path exists and lines is positive integer
    from pathlib import Path
    p = Path(path)
    if not p.exists():
        return f"Error: path does not exist: {path}"
    if not isinstance(lines, int) or lines < 1:
        return f"Error: lines must be positive integer, got {lines}"
    cmd = ["tail", "-n", str(lines), str(path)]
    result = subprocess.run(cmd, shell=False, capture_output=True, text=True)
    return result.stdout

def search_log(path, pattern):
    """Search log for pattern. SECURITY: Converted from shell=True to list args (Phase 15B)"""
    # Input validation: path must exist, pattern is basic string (not shell special chars)
    from pathlib import Path
    import shlex
    p = Path(path)
    if not p.exists():
        return f"Error: path does not exist: {path}"
    # Basic validation: reject patterns with shell metacharacters
    if any(c in pattern for c in [';', '&&', '||', '|', '`', '$', '>', '<', '\n']):
        return f"Error: pattern contains unsafe characters: {pattern}"
    cmd = ["grep", "--", pattern, str(path)]
    result = subprocess.run(cmd, shell=False, capture_output=True, text=True)
    return result.stdout

def error_summary(path):
    """Summarize errors in log."""
    result = tail_log(path, 1000)
    errors = re.findall(r'ERROR|CRITICAL|Exception|FATAL', result)
    return Counter(errors)

def http_status_summary(path):
    """Summarize HTTP status codes."""
    result = tail_log(path, 1000)
    codes = re.findall(r'\s([1-5]\d{2})\s', result)
    return Counter(codes)

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", default="/var/log/syslog")
    parser.add_argument("--tail", type=int, default=100)
    parser.add_argument("--search")
    parser.add_argument("--errors", action="store_true")
    parser.add_argument("--http", action="store_true")
    args = parser.parse_args()
    
    if args.search:
        print(search_log(args.path, args.search))
    elif args.errors:
        print(error_summary(args.path))
    elif args.http:
        print(http_status_summary(args.path))
    else:
        print(tail_log(args.path, args.tail))

if __name__ == "__main__":
    main()