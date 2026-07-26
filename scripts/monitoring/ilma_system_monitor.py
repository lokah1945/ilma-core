#!/usr/bin/env python3
"""
ILMA System Monitor
==================
Real-time system monitoring.
"""

import psutil
import time
from datetime import datetime

def get_cpu():
    return psutil.cpu_percent(interval=1)

def get_memory():
    mem = psutil.virtual_memory()
    return {
        "total": mem.total,
        "available": mem.available,
        "percent": mem.percent,
        "used": mem.used
    }

def get_disk():
    disk = psutil.disk_usage('/')
    return {
        "total": disk.total,
        "used": disk.used,
        "free": disk.free,
        "percent": disk.percent
    }

def format_bytes(b):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if b < 1024:
            return f"{b:.2f} {unit}"
        b /= 1024
    return f"{b:.2f} PB"

def monitor(interval=5, count=None):
    """Monitor system resources."""
    print(f"\n{'='*60}")
    print(f"ILMA System Monitor - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    i = 0
    while count is None or i < count:
        cpu = get_cpu()
        mem = get_memory()
        disk = get_disk()
        
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}]")
        print(f"  CPU:     {cpu:>6.2f}%")
        print(f"  Memory:  {mem['percent']:>6.2f}% ({format_bytes(mem['used'])} / {format_bytes(mem['total'])})")
        print(f"  Disk:    {disk.percent:>6.2f}% ({format_bytes(disk['used'])} / {format_bytes(disk['total'])})")
        
        i += 1
        if count is None or i < count:
            time.sleep(interval)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=int, default=5)
    parser.add_argument("--count", type=int)
    args = parser.parse_args()
    monitor(args.interval, args.count)