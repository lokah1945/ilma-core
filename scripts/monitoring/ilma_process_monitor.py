#!/usr/bin/env python3
"""
ILMA Process Monitor
==================
Process monitoring and management.
"""

import psutil
import time

def list_processes(sort_by="cpu", limit=20):
    """List top processes."""
    processes = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            processes.append(p.info)
        except Exception:
            pass
    
    if sort_by == "cpu":
        processes.sort(key=lambda x: x.get("cpu_percent", 0), reverse=True)
    else:
        processes.sort(key=lambda x: x.get("memory_percent", 0), reverse=True)
    
    print(f"\nTop {limit} processes by {sort_by}:")
    print(f"{'PID':>8} {'Name':30} {'CPU%':>8} {'MEM%':>8}")
    print("-" * 60)
    for p in processes[:limit]:
        print(f"{p['pid']:>8} {p['name'][:30]:30} {p['cpu_percent']:>8.1f} {p['memory_percent']:>8.1f}")

def watch_process(pid, interval=2):
    """Watch a specific process."""
    try:
        p = psutil.Process(pid)
        print(f"Watching process: {p.name()} (PID: {pid})")
        while True:
            cpu = p.cpu_percent(interval=interval)
            mem = p.memory_percent()
            print(f"CPU: {cpu:>6.2f}% | MEM: {mem:>6.2f}%")
    except psutil.NoSuchProcess:
        print(f"Process {pid} not found")

def kill_process(pid):
    """Kill a process."""
    try:
        p = psutil.Process(pid)
        p.kill()
        print(f"✅ Killed process {pid}")
    except psutil.NoSuchProcess:
        print(f"Process {pid} not found")

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--list", action="store_true")
    p.add_argument("--sort", default="cpu", choices=["cpu", "mem"])
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--watch")
    p.add_argument("--kill", type=int)
    args = p.parse_args()
    if args.list: list_processes(args.sort, args.limit)
    elif args.watch: watch_process(int(args.watch))
    elif args.kill: kill_process(args.kill)

if __name__ == "__main__": main()