#!/usr/bin/env python3
"""
ILMA Metrics Collector
=====================
Collect and store metrics.
"""

import psutil
import time
import json
from datetime import datetime
from pathlib import Path

METRICS_FILE = Path("/root/.hermes/profiles/ilma/metrics.json")

def collect():
    """Collect current metrics."""
    return {
        "timestamp": datetime.now().isoformat(),
        "cpu_percent": psutil.cpu_percent(interval=1),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage('/').percent,
        "network_connections": len(psutil.net_connections()),
        "process_count": len(psutil.pids())
    }

def store(metric):
    """Store metric to file."""
    metrics = []
    if METRICS_FILE.exists():
        with open(METRICS_FILE) as f:
            metrics = json.load(f)
    metrics.append(metric)
    # Keep last 1000
    metrics = metrics[-1000:]
    with open(METRICS_FILE, "w") as f:
        json.dump(metrics, f)

def collect_loop(interval=60, count=None):
    """Collect metrics in loop."""
    print(f"Collecting metrics every {interval}s...")
    i = 0
    while count is None or i < count:
        m = collect()
        store(m)
        print(f"[{m['timestamp']}] CPU: {m['cpu_percent']}%, MEM: {m['memory_percent']}%, DISK: {m['disk_percent']}%")
        i += 1
        if count is None or i < count:
            time.sleep(interval)

def report():
    """Generate metrics report."""
    if not METRICS_FILE.exists():
        print("No metrics collected yet")
        return
    with open(METRICS_FILE) as f:
        metrics = json.load(f)
    
    if not metrics:
        print("No metrics data")
        return
    
    print(f"\n📊 Metrics Report ({len(metrics)} samples)")
    print(f"   Period: {metrics[0]['timestamp']} -> {metrics[-1]['timestamp']}")
    print(f"   Avg CPU: {sum(m['cpu_percent'] for m in metrics) / len(metrics):.2f}%")
    print(f"   Avg MEM: {sum(m['memory_percent'] for m in metrics) / len(metrics):.2f}%")
    print(f"   Avg DISK: {sum(m['disk_percent'] for m in metrics) / len(metrics):.2f}%")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--collect", action="store_true")
    parser.add_argument("--interval", type=int, default=60)
    parser.add_argument("--count", type=int)
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()
    
    if args.collect:
        collect_loop(args.interval, args.count)
    elif args.report:
        report()
    else:
        print(collect())