#!/usr/bin/env python3
"""
ILMA Security Scanner
====================
Vulnerability scanning utilities.
"""

import subprocess
import re

def check_open_ports():
    """Check for open ports. SECURITY: Converted from shell=True to list args (Phase 15B)"""
    # Try netstat first, fallback to ss
    result1 = subprocess.run(["netstat", "-tuln"], shell=False, capture_output=True, text=True)
    if result1.returncode != 0:
        result1 = subprocess.run(["ss", "-tuln"], shell=False, capture_output=True, text=True)
    print("Open Ports:")
    print(result1.stdout)

def check_running_processes():
    """Check running processes. SECURITY: Converted from shell=True to list args (Phase 15B)"""
    result = subprocess.run(["ps", "aux"], shell=False, capture_output=True, text=True)
    lines = result.stdout.split("\n")[:21]
    print("Top Processes:")
    print("\n".join(lines))

def check_ssh_config():
    """Check SSH hardening."""
    print("\nSSH Security Check:")
    try:
        with open("/etc/ssh/sshd_config") as f:
            content = f.read()
            if "PermitRootLogin yes" in content:
                print("  ⚠️ Root login enabled")
            if "PasswordAuthentication yes" in content:
                print("  ⚠️ Password authentication enabled")
            print("  ✅ SSH config reviewed")
    except IOError:
        print("  ⚠️ Cannot read sshd_config")

def check_firewall():
    """Check firewall status. SECURITY: Converted from shell=True to list args (Phase 15B)"""
    result = subprocess.run(["ufw", "status"], shell=False, capture_output=True, text=True)
    if result.returncode != 0:
        result = subprocess.run(["iptables", "-L", "-n"], shell=False, capture_output=True, text=True)
        lines = result.stdout.split("\n")[:11]
        print("\nFirewall Status:")
        print("\n".join(lines))
    else:
        print("\nFirewall Status:")
        print(result.stdout or "Unknown")

def full_scan():
    """Run full security scan."""
    print("\n" + "="*50)
    print("ILMA Security Scan")
    print("="*50)
    check_open_ports()
    check_running_processes()
    check_ssh_config()
    check_firewall()
    print("\n✅ Scan complete")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--ports", action="store_true")
    parser.add_argument("--processes", action="store_true")
    args = parser.parse_args()
    
    if args.full:
        full_scan()
    elif args.ports:
        check_open_ports()
    elif args.processes:
        check_running_processes()
    else:
        full_scan()