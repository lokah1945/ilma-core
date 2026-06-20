#!/usr/bin/env python3
"""
ILMA SSL Check
============
SSL certificate monitoring.
"""

import subprocess
import json
from datetime import datetime, timedelta
from pathlib import Path

def check_cert(domain, port=443):
    """Check SSL certificate. SECURITY: Converted from shell=True to list args (Phase 15B)"""
    cmd = ["openssl", "s_client", "-connect", f"{domain}:{port}", "-servername", domain]
    proc1 = subprocess.run(cmd, stdin=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           shell=False, capture_output=True, text=True)
    cmd2 = ["openssl", "x509", "-noout", "-dates"]
    proc2 = subprocess.run(cmd2, shell=False, input=proc1.stdout, capture_output=True, text=True)
    return proc2.stdout

def check_expiry(domain, port=443):
    """Check certificate expiry."""
    dates = check_cert(domain, port)
    not_after = None
    for line in dates.split("\n"):
        if "notAfter=" in line:
            not_after = line.split("=")[1].strip()
    if not_after:
        from datetime import datetime
        exp = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
        days_left = (exp - datetime.now()).days
        return days_left
    return None

def monitor_domains(domains_file):
    """Monitor SSL for list of domains."""
    with open(domains_file) as f:
        domains = [line.strip() for line in f if line.strip()]
    
    print("\n🔒 SSL Certificate Status")
    print("="*60)
    for domain in domains:
        days = check_expiry(domain)
        if days is not None:
            status = "✅" if days > 30 else "⚠️" if days > 7 else "🔴"
            print(f"{status} {domain:30} {days:4} days")
        else:
            print(f"❌ {domain:30} Unknown")

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--domain")
    p.add_argument("--check-expiry", action="store_true")
    p.add_argument("--monitor")
    args = p.parse_args()
    if args.domain:
        if args.check_expiry:
            days = check_expiry(args.domain)
            print(f"Days until expiry: {days}")
        else:
            print(check_cert(args.domain))
    elif args.monitor:
        monitor_domains(args.monitor)

if __name__ == "__main__": main()