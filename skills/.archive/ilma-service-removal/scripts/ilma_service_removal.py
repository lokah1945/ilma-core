#!/usr/bin/env python3
"""
ILMA Service Removal Script v1.0
Comprehensive removal of application services (Ookla, Speedtest, etc.)
"""

import subprocess
import sys
import argparse
from pathlib import Path

def run_cmd(cmd, check=True):
    """Run shell command and return output"""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Warning: {cmd} returned {result.returncode}")
    return result.stdout.strip(), result.returncode

def discover_service(service_name):
    """Discover all files related to a service"""
    print(f"=== Discovering {service_name} files ===")
    
    # Find processes
    out, _ = run_cmd(f"ps aux | grep -v grep | grep -i {service_name}")
    if out:
        print(f"Processes found:\n{out}")
    else:
        print("No processes found")
    
    # Find files
    patterns = [
        f"/root/{service_name}",
        f"/snap/{service_name}",
        f"/var/lib/snapd/snaps/{service_name}_*.snap",
        f"/etc/systemd/system/snap-{service_name}*.mount",
        f"/etc/systemd/system/multi-user.target.wants/snap-{service_name}*.mount",
        f"/var/lib/snapd/inhibit/{service_name}.lock",
        f"/var/lib/snapd/cookie/{service_name}",
    ]
    
    for pattern in patterns:
        out, code = run_cmd(f"ls -la {pattern} 2>/dev/null", check=False)
        if out:
            print(f"Files: {out}")

def stop_processes(service_name):
    """Stop all processes for the service"""
    print(f"=== Stopping {service_name} processes ===")
    
    # Try pkill first
    run_cmd(f"pkill -f {service_name}")
    run_cmd("sleep 1")
    
    # Check if still running
    out, code = run_cmd(f"pgrep -f {service_name}")
    if out:
        print(f"Processes still running, using kill -9: {out}")
        run_cmd(f"kill -9 $(pgrep -f {service_name})", check=False)
        run_cmd("sleep 2")
    
    # Verify
    out, _ = run_cmd(f"ps aux | grep -v grep | grep -i {service_name}")
    if out:
        print(f"Warning: Processes still running:\n{out}")
    else:
        print("✓ All processes stopped")

def remove_files(service_name, binary_path=None):
    """Remove service files"""
    print(f"=== Removing {service_name} files ===")
    
    # Remove binary if specified
    if binary_path:
        run_cmd(f"rm -f {binary_path}")
        run_cmd(f"rm -f {binary_path}.pid")
    
    # Remove snap packages
    run_cmd(f"snap remove {service_name} --revision=all 2>/dev/null", check=False)
    
    # Remove snap directory
    run_cmd(f"rm -rf /snap/{service_name}")
    
    # Remove snap files
    run_cmd(f"rm -f /var/lib/snapd/snaps/{service_name}_*.snap")
    
    # Remove systemd mount files
    run_cmd(f"rm -f /etc/systemd/system/snap-{service_name}-*.mount")
    run_cmd(f"rm -rf /etc/systemd/system/multi-user.target.wants/snap-{service_name}-*.mount")
    run_cmd(f"rm -f /etc/systemd/system/snapd.mounts.target.wants/snap-{service_name}-*.mount")
    
    # Remove cache and lock files
    run_cmd(f"rm -rf /var/cache/apparmor/*{service_name}*")
    run_cmd(f"rm -f /var/lib/snapd/seccomp/bpf/{service_name}*.bin")
    run_cmd(f"rm -f /var/lib/snapd/inhibit/{service_name}.lock")
    run_cmd(f"rm -rf /var/lib/snapd/cookie/{service_name}*")
    
    print(f"✓ Files removed")

def verify_removal(service_name):
    """Verify complete removal"""
    print(f"=== Verifying {service_name} removal ===")
    
    # Check processes
    out, code = run_cmd(f"ps aux | grep -v grep | grep -i {service_name}", check=False)
    if out:
        print(f"✗ Process still running:\n{out}")
        return False
    print("✓ No processes running")
    
    # Check binary
    out, code = run_cmd(f"ls -la /root/{service_name} 2>/dev/null", check=False)
    if out:
        print(f"✗ Binary still exists:\n{out}")
        return False
    print("✓ Binary removed")
    
    # Check snap directory
    out, code = run_cmd(f"ls -la /snap/{service_name} 2>/dev/null", check=False)
    if out:
        print(f"✗ Snap directory still exists:\n{out}")
        return False
    print("✓ Snap directory removed")
    
    # Check snap files
    out, code = run_cmd(f"ls -la /var/lib/snapd/snaps/{service_name}_*.snap 2>/dev/null", check=False)
    if out:
        print(f"✗ Snap files still exist:\n{out}")
        return False
    print("✓ Snap files removed")
    
    # Check systemd files
    out, code = run_cmd(f"ls -la /etc/systemd/system/snap-{service_name}-*.mount 2>/dev/null", check=False)
    if out:
        print(f"✗ Systemd files still exist:\n{out}")
        return False
    print("✓ Systemd files removed")
    
    print(f"\n=== {service_name} FULLY REMOVED ===")
    return True

def main():
    parser = argparse.ArgumentParser(description="ILMA Service Removal")
    parser.add_argument("--service", required=True, help="Service name")
    parser.add_argument("--binary", help="Binary path")
    parser.add_argument("--discover", action="store_true", help="Discovery mode only")
    parser.add_argument("--verify", action="store_true", help="Verify mode only")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    
    args = parser.parse_args()
    
    if args.discover:
        discover_service(args.service)
        return
    
    if args.verify:
        verify_removal(args.service)
        return
    
    if args.binary:
        stop_processes(args.service)
        remove_files(args.service, args.binary)
    else:
        # Try removing snapd (removes all snaps)
        print(f"=== Attempting snapd removal for {args.service} ===")
        out, code = run_cmd("snap list | grep -i speedtest", check=False)
        if out:
            print("Removing snapd (will remove all snaps)...")
            run_cmd("apt-get remove --purge -y snapd", check=False)
        
        # Manual cleanup
        remove_files(args.service)
    
    verify_removal(args.service)

if __name__ == "__main__":
    main()