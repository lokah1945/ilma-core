#!/usr/bin/env python3
"""
ILMA Server Setup
================
Server provisioning automation.
"""

import subprocess

def run(cmd):
    import shlex
    cmd_list = shlex.split(cmd)
    return subprocess.run(cmd_list, capture_output=True, text=True)

def check_python():
    """Check Python installation."""
    result = run("python3 --version")
    print(f"Python: {result.stdout.strip()}")

def install_package(package):
    """Install package via apt."""
    print(f"Installing {package}...")
    run(f"apt-get update && apt-get install -y {package}")

def setup_user(username):
    """Create and setup user."""
    run(f"useradd -m -s /bin/bash {username}")
    print(f"✅ User {username} created")

def setup_firewall():
    """Setup basic firewall."""
    run("ufw default deny incoming")
    run("ufw default allow outgoing")
    run("ufw allow ssh")
    run("ufw --force enable")
    print("✅ Firewall configured")

def setup_fail2ban():
    """Setup fail2ban."""
    install_package("fail2ban")
    run("systemctl enable fail2ban")
    run("systemctl start fail2ban")
    print("✅ Fail2ban installed")

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--check-python", action="store_true")
    p.add_argument("--install")
    p.add_argument("--user")
    p.add_argument("--firewall", action="store_true")
    p.add_argument("--fail2ban", action="store_true")
    args = p.parse_args()
    if args.check_python: check_python()
    elif args.install: install_package(args.install)
    elif args.user: setup_user(args.user)
    elif args.firewall: setup_firewall()
    elif args.fail2ban: setup_fail2ban()

if __name__ == "__main__": main()