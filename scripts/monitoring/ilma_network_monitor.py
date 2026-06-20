#!/usr/bin/env python3
"""
ILMA Network Monitor
==================
Network monitoring utilities.
"""

import psutil
import time

def active_connections():
    """Show active network connections."""
    print("\nActive Connections:")
    print(f"{'Protocol':10} {'Local Address':25} {'Remote Address':25} {'Status':15}")
    print("-" * 80)
    for conn in psutil.net_connections()[:50]:
        proto = "TCP" if conn.type == 1 else "UDP"
        laddr = f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else "-"
        raddr = f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else "-"
        status = conn.status if hasattr(conn, 'status') else "-"
        print(f"{proto:10} {laddr:25} {raddr:25} {status:15}")

def bandwidth():
    """Show bandwidth usage."""
    before = psutil.net_io_counters()
    time.sleep(1)
    after = psutil.net_io_counters()
    
    sent = after.bytes_sent - before.bytes_sent
    recv = after.bytes_recv - before.bytes_recv
    
    print(f"\nBandwidth (1s):")
    print(f"  Sent:     {sent/1024:.2f} KB/s")
    print(f"  Received: {recv/1024:.2f} KB/s")

def watch_connections(interval=5):
    """Watch network activity."""
    print("Watching network (Ctrl+C to stop)...")
    while True:
        active_connections()
        bandwidth()
        time.sleep(interval)

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--connections", action="store_true")
    p.add_argument("--bandwidth", action="store_true")
    p.add_argument("--watch", action="store_true")
    p.add_argument("--interval", type=int, default=5)
    args = p.parse_args()
    if args.connections: active_connections()
    elif args.bandwidth: bandwidth()
    elif args.watch: watch_connections(args.interval)