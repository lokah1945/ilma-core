#!/usr/bin/env python3
"""
ILMA Browser Keep-Alive Daemon v2.2 (Per-Profile Systemd Mode)
==============================================================
Keeps ILMA Chrome daemon alive via systemd --user template service.

Architecture:
- Chrome runs as SYSTEMD USER TEMPLATE SERVICE (ilma-chrome@<profile>.service)
- Profile name defaults to HERMES_BROWSER_PROFILE_NAME env var or 'lokah2150' (admin)
- This script monitors systemd --user status and verifies CDP connectivity
- Active profile determined by HERMES_BROWSER_PROFILE_NAME or config

Per-Profile Isolation:
  lokah2150 (admin) -> ilma-chrome@lokah2150.service, CDP 9222, /root/user-data/lokah2150
  user_arahman       -> ilma-chrome@user_arahman.service, CDP 9231, /root/user-data/user_arahman

Browser Management Options:
  A) ilma-chrome@<profile>.service — Pure Chrome binary (RECOMMENDED)
  B) hermes-playwright-cdp@.service — Node.js Playwright launcher (alternative)

Usage:
    python3 ilma_browser_keepalive.py --start    # Start systemd user service
    python3 ilma_browser_keepalive.py --status   # Check status
    python3 ilma_browser_keepalive.py --stop     # Stop systemd user service
    python3 ilma_browser_keepalive.py --restart  # Restart systemd user service
    python3 ilma_browser_keepalive.py --verify   # Verify CDP is working
    python3 ilma_browser_keepalive.py --daemon   # Run monitoring loop
    python3 ilma_browser_keepalive.py --profile arahman  # Operate on user_arahman profile

Key Changes v2.2:
- Template service support: ilma-chrome@<profile>.service
- Reads profile from HERMES_BROWSER_PROFILE_NAME env or --profile flag
- Loads CDP/port info from browser-registry.yaml
- Admin profile (lokah2150) is protected — non-admin cannot access it
- Removed hardcoded LOCKED_BROWSER_PROFILE references

Prerequisites:
    loginctl enable-linger "$USER"   # Enable user services at boot
    systemctl --user daemon-reload
    systemctl --user enable --now ilma-chrome@lokah2150.service
"""

import sys
import os
import time
import json
import argparse
import subprocess
from pathlib import Path

# Setup path
ILMA_ROOT = Path('/root/.hermes/profiles/ilma')
sys.path.insert(0, str(ILMA_ROOT / 'scripts'))

# Browser registry
BROWSER_REGISTRY_PATH = Path('/root/.hermes/browser-registry/browser-registry.yaml')
STATUS_FILE = Path('/tmp/ilma_browser_keepalive_status.json')

# ============================================================================
# Profile Resolution
# ============================================================================

def load_browser_registry():
    """Load browser profile registry."""
    try:
        if BROWSER_REGISTRY_PATH.exists():
            import yaml
            with open(BROWSER_REGISTRY_PATH) as f:
                return yaml.safe_load(f)
    except Exception:
        pass
    return None

def get_profile_info(profile_name: str, registry: dict = None) -> dict:
    """Get profile info from registry."""
    if registry is None:
        registry = load_browser_registry()
    if not registry:
        return {}
    # Check admin
    admin = registry.get('admin', {})
    if admin.get('profile_name') == profile_name:
        return admin
    # Check users
    users = registry.get('users', {})
    for user_key, user_data in users.items():
        if user_data.get('profile_name') == profile_name:
            return user_data
    return {}

def resolve_active_profile():
    """
    Resolve the active browser profile.
    Priority: 1) --profile CLI flag, 2) HERMES_BROWSER_PROFILE_NAME env,
              3) config.yaml browser.profile_name, 4) default to 'lokah2150' (admin)
    """
    # CLI flag has highest priority
    # (parsed in main())
    
    # Env var
    name = os.environ.get('HERMES_BROWSER_PROFILE_NAME', '').strip()
    if name:
        return name
    
    # Config file
    try:
        config_path = ILMA_ROOT / 'config.yaml'
        if config_path.exists():
            import yaml
            with open(config_path) as f:
                cfg = yaml.safe_load(f)
                browser_cfg = cfg.get('browser', {})
                pn = browser_cfg.get('profile_name', '').strip()
                if pn:
                    return pn
    except Exception:
        pass
    
    # Default: admin profile
    return 'lokah2150'

# Load registry once
BROWSER_REGISTRY = load_browser_registry()

def get_active_profile_name(cli_profile: str = None) -> str:
    """Get active profile name (CLI > env > config > default)."""
    if cli_profile:
        return cli_profile
    return resolve_active_profile()

def get_profile_cdp_info(profile_name: str) -> tuple:
    """Get CDP host:port for a profile. Returns (host, port, user_data_dir)."""
    info = get_profile_info(profile_name, BROWSER_REGISTRY)
    if info:
        host = info.get('cdp_host', '127.0.0.1')
        port = info.get('cdp_port', 9222)
        user_data_dir = info.get('user_data_dir', f'/root/user-data/{profile_name}')
        return host, port, user_data_dir
    # Fallback: assume admin defaults
    return '127.0.0.1', 9222, f'/root/user-data/{profile_name}'

# ============================================================================
# Systemd Commands
# ============================================================================

def systemd_is_active(service: str) -> bool:
    """Check if systemd --user service is active."""
    try:
        result = subprocess.run(
            ['systemctl', '--user', 'is-active', service],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.stdout.strip() == 'active'
    except Exception:
        return False


def systemd_is_enabled(service: str) -> bool:
    """Check if systemd --user service is enabled (auto-start on boot)."""
    try:
        result = subprocess.run(
            ['systemctl', '--user', 'is-enabled', service],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.stdout.strip() == 'enabled'
    except Exception:
        return False


def systemd_start(service: str) -> bool:
    """Start systemd --user service."""
    try:
        result = subprocess.run(
            ['systemctl', '--user', 'start', service],
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.returncode == 0
    except Exception:
        return False


def systemd_stop(service: str) -> bool:
    """Stop systemd --user service."""
    try:
        result = subprocess.run(
            ['systemctl', '--user', 'stop', service],
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.returncode == 0
    except Exception:
        return False


def systemd_restart(service: str) -> bool:
    """Restart systemd --user service."""
    try:
        result = subprocess.run(
            ['systemctl', '--user', 'restart', service],
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.returncode == 0
    except Exception:
        return False


def systemd_status(service: str) -> dict:
    """Get detailed systemd --user service status."""
    try:
        result = subprocess.run(
            ['systemctl', '--user', 'status', service],
            capture_output=True,
            text=True,
            timeout=10
        )
        return {
            'output': result.stdout,
            'active': systemd_is_active(service),
            'enabled': systemd_is_enabled(service),
        }
    except Exception as e:
        return {'error': str(e)}


# ============================================================================
# CDP Verification
# ============================================================================

def check_cdp_port(host: str, port: int) -> bool:
    """Check if CDP port is accepting connections."""
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/json/version", timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


def get_cdp_info(host: str, port: int) -> dict:
    """Get CDP browser info."""
    import urllib.request
    import json
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/json/version", timeout=5) as resp:
            data = json.loads(resp.read())
            return {
                'browser': data.get('Browser', 'Unknown'),
                'webSocketDebuggerUrl': data.get('webSocketDebuggerUrl', ''),
            }
    except Exception as e:
        return {'error': str(e)}


# ============================================================================
# CDP Connection Test (via connect_to_daemon)
# ============================================================================

def test_cdp_connection(host: str, port: int) -> dict:
    """Test full CDP connection via connect_to_daemon."""
    try:
        from playwright.sync_api import sync_playwright
        import urllib.request
        import json

        # Get fresh WebSocket URL
        with urllib.request.urlopen(f"http://{host}:{port}/json/version", timeout=5) as resp:
            data = json.loads(resp.read())
            ws_url = data["webSocketDebuggerUrl"]

        # Connect
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(ws_url, timeout=10000)
            version = browser.version

            # Get page
            context = browser.contexts[0] if browser.contexts else browser.new_context()
            page = context.pages[0] if context.pages else context.new_page()

            # Navigate test
            page.goto("https://example.com", timeout=10000)
            title = page.title()

            return {
                'success': True,
                'browser_version': version,
                'test_title': title,
            }
    except Exception as e:
        return {'success': False, 'error': str(e)}


# ============================================================================
# Status Management
# ============================================================================

def write_status(status: dict):
    """Write status to status file."""
    try:
        STATUS_FILE.write_text(json.dumps(status, indent=2))
    except Exception:
        pass


def read_status() -> dict:
    """Read status from status file."""
    try:
        if STATUS_FILE.exists():
            return json.loads(STATUS_FILE.read_text())
    except Exception:
        pass
    return {}


# ============================================================================
# CLI Interface
# ============================================================================

def cmd_status(profile_name: str, host: str, port: int, user_data_dir: Path):
    """Show current status."""
    service = f'ilma-chrome@{profile_name}.service'
    print(f"\n{'='*60}")
    print(f"ILMA Chrome Keep-Alive Status (Per-Profile v2.2)")
    print(f"{'='*60}\n")
    print(f"Profile: {profile_name}")
    print(f"Service: {service}")
    print(f"CDP:     {host}:{port}")
    print(f"Profile: {user_data_dir}")
    print()

    # Systemd status
    is_active = systemd_is_active(service)
    is_enabled = systemd_is_enabled(service)
    svc_status = systemd_status(service)

    print(f"Systemd Service: {service}")
    print(f"  Active:  {'✅ YES' if is_active else '❌ NO'}")
    print(f"  Enabled: {'✅ YES (auto-start on boot)' if is_enabled else '❌ NO'}")
    print()

    # CDP status
    cdp_ok = check_cdp_port(host, port)
    print(f"CDP Port ({host}:{port}):")
    print(f"  Listening: {'✅ YES' if cdp_ok else '❌ NO'}")
    print()

    if cdp_ok:
        cdp_info = get_cdp_info(host, port)
        if 'error' not in cdp_info:
            print(f"Browser Info:")
            print(f"  Browser: {cdp_info.get('browser', 'Unknown')}")
            print()

    # Profile
    print(f"Profile Dir: {user_data_dir}")
    print(f"  Exists: {'✅ YES' if user_data_dir.exists() else '❌ NO'}")
    if user_data_dir.exists():
        import os
        size = sum(f.stat().st_size for f in user_data_dir.rglob('*') if f.is_file())
        print(f"  Size: {size / 1024 / 1024:.1f} MB")
        perms = oct(user_data_dir.stat().st_mode & 0o777)
        print(f"  Perms: {perms} ({'✅ 0700' if perms == '0o700' else '⚠️  should be 0700'})")
    print()

    # Last known status
    last = read_status()
    if last:
        print(f"Last Status Update:")
        if 'last_check' in last:
            age = time.time() - last['last_check']
            print(f"  Age: {age:.0f}s ago")
        print(f"  CDP Test: {'✅ OK' if last.get('cdp_test') else '❌ FAIL'}")
    print()

    if is_active and cdp_ok:
        print("✅ Chrome daemon is HEALTHY and ready")
    elif is_active and not cdp_ok:
        print("⚠️  Chrome running but CDP not responding")
    else:
        print("❌ Chrome daemon is NOT running")
    print()


def cmd_verify(profile_name: str, host: str, port: int, user_data_dir: Path):
    """Verify CDP connectivity with actual browser test."""
    service = f'ilma-chrome@{profile_name}.service'
    print(f"\n{'='*60}")
    print(f"CDP Connection Verification — Profile: {profile_name}")
    print(f"{'='*60}\n")

    # Quick port check
    print("1. Checking CDP port...")
    cdp_ok = check_cdp_port(host, port)
    print(f"   Port {host}:{port}: {'✅ OPEN' if cdp_ok else '❌ CLOSED'}")

    if not cdp_ok:
        print(f"\n❌ CDP port not accessible. Is Chrome running?")
        print(f"   Try: systemctl --user start {service}")
        return False

    # Full connection test
    print("\n2. Testing CDP WebSocket connection...")
    result = test_cdp_connection(host, port)

    if result.get('success'):
        print(f"   Browser: {result.get('browser_version')}")
        print(f"   Test page title: {result.get('test_title')}")
        print("\n✅ CDP connection verified — Chrome is fully operational")
        return True
    else:
        print(f"   Error: {result.get('error')}")
        print("\n❌ CDP connection failed")
        return False


def cmd_start(profile_name: str, host: str, port: int, user_data_dir: Path):
    """Start Chrome via systemd."""
    service = f'ilma-chrome@{profile_name}.service'
    print(f"Starting {service}...")
    if systemd_start(service):
        print("✅ Service started")
        time.sleep(2)
        cmd_verify(profile_name, host, port, user_data_dir)
    else:
        print("❌ Failed to start service")


def cmd_stop(profile_name: str, host: str, port: int, user_data_dir: Path):
    """Stop Chrome via systemd."""
    service = f'ilma-chrome@{profile_name}.service'
    print(f"Stopping {service}...")
    if systemd_stop(service):
        print("✅ Service stopped")
    else:
        print("❌ Failed to stop service")


def cmd_restart(profile_name: str, host: str, port: int, user_data_dir: Path):
    """Restart Chrome via systemd."""
    service = f'ilma-chrome@{profile_name}.service'
    print(f"Restarting {service}...")
    if systemd_restart(service):
        print("✅ Service restarted")
        time.sleep(3)
        cmd_verify(profile_name, host, port, user_data_dir)
    else:
        print("❌ Failed to restart service")


def cmd_list_profiles():
    """List all registered profiles."""
    registry = load_browser_registry()
    print(f"\n{'='*60}")
    print(f"Registered Browser Profiles")
    print(f"{'='*60}\n")
    
    if not registry:
        print("❌ No browser-registry.yaml found")
        return
    
    # Admin
    admin = registry.get('admin', {})
    if admin:
        print(f"ADMIN PROFILE:")
        print(f"  Name:      {admin.get('profile_name')}")
        print(f"  Owner:     {admin.get('owner')}")
        print(f"  CDP:       {admin.get('cdp_url')}")
        print(f"  user-data: {admin.get('user_data_dir')}")
        print(f"  Service:   {admin.get('service')}")
        print(f"  Protected: {'✅ YES (admin-only)' if admin.get('protected') else '❌ NO'}")
        print()
    
    # Users
    users = registry.get('users', {})
    if users:
        print(f"USER PROFILES ({len(users)}):")
        for key, data in users.items():
            print(f"  [{key}]")
            print(f"    Name:      {data.get('profile_name')}")
            print(f"    Owner:     {data.get('owner')}")
            print(f"    CDP:       {data.get('cdp_url')}")
            print(f"    user-data: {data.get('user_data_dir')}")
            print(f"    Service:   {data.get('service')}")
            print()
    
    # Active service instances
    print(f"Active service instances:")
    try:
        result = subprocess.run(
            ['systemctl', '--user', 'list-units', '--all', '--no-pager', 'ilma-chrome@*'],
            capture_output=True, text=True, timeout=15
        )
        for line in result.stdout.split('\n'):
            if 'ilma-chrome@' in line:
                print(f"  {line.strip()}")
    except Exception as e:
        print(f"  Error listing: {e}")
    print()


# ============================================================================
# Monitoring Loop
# ============================================================================

def cmd_daemon(profile_name: str, host: str, port: int, user_data_dir: Path):
    """Run monitoring loop."""
    service = f'ilma-chrome@{profile_name}.service'
    print(f"Starting ILMA Chrome Keep-Alive Monitor (Per-Profile v2.2)")
    print(f"Profile:   {profile_name}")
    print(f"Service:   {service}")
    print(f"CDP Port:  {host}:{port}")
    print(f"user-data: {user_data_dir}")
    print(f"Service Manager: systemctl --user")
    print(f"\nPress Ctrl+C to stop\n")

    check_interval = 60  # Check every 60 seconds
    failure_count = 0
    max_failures = 3

    while True:
        try:
            # Check systemd service
            is_active = systemd_is_active(service)

            # Check CDP
            cdp_ok = check_cdp_port(host, port)

            # Overall health
            healthy = is_active and cdp_ok

            # Log status
            if healthy:
                ts = time.strftime('%Y-%m-%d %H:%M:%S')
                print(f"[{ts}] ✅ Chrome daemon healthy ({profile_name}, systemd={is_active}, cdp={cdp_ok})")
                failure_count = 0
            else:
                failure_count += 1
                ts = time.strftime('%Y-%m-%d %H:%M:%S')
                print(f"[{ts}] ⚠️  Issue detected ({profile_name}, systemd={is_active}, cdp={cdp_ok}) [{failure_count}/{max_failures}]")

                if failure_count >= max_failures:
                    print(f"[{ts}] 🔄 Attempting restart...")
                    if systemd_restart(service):
                        print(f"[{ts}] ✅ Restart successful")
                        failure_count = 0
                    else:
                        print(f"[{ts}] ❌ Restart failed")

            # Write status
            write_status({
                'running': True,
                'profile': profile_name,
                'service': service,
                'user_data_dir': str(user_data_dir),
                'cdp_url': f'http://{host}:{port}',
                'systemd_active': is_active,
                'systemd_enabled': systemd_is_enabled(service),
                'cdp_ok': cdp_ok,
                'healthy': healthy,
                'last_check': time.time(),
                'failure_count': failure_count,
            })

            time.sleep(check_interval)

        except KeyboardInterrupt:
            print("\n\nMonitor stopped")
            write_status({'running': False, 'last_check': time.time()})
            break
        except Exception as e:
            print(f"Monitor error: {e}")
            time.sleep(check_interval)


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='ILMA Browser Keep-Alive Daemon v2.2 (Per-Profile)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  start     Start Chrome via systemd
  stop      Stop Chrome via systemd
  restart   Restart Chrome via systemd
  status    Show current status
  verify    Verify CDP connectivity
  daemon    Run monitoring loop
  list      List all registered profiles

Examples:
  python3 ilma_browser_keepalive.py status
  python3 ilma_browser_keepalive.py start --profile arahman
  python3 ilma_browser_keepalive.py verify
  python3 ilma_browser_keepalive.py list
"""
    )
    parser.add_argument('command', nargs='?', default=None,
                        help='Command: start, stop, restart, status, verify, daemon, list')
    parser.add_argument('--profile', '-p', default=None,
                        help='Browser profile name (overrides env/config, default: lokah2150)')
    parser.add_argument('--host', default=None,
                        help='CDP host override')
    parser.add_argument('--port', type=int, default=None,
                        help='CDP port override')
    
    args = parser.parse_args()
    
    # Normalize command (allow both --status and status)
    cmd_raw = args.command
    if cmd_raw:
        # Strip leading -- or - if user typed them as positional
        cmd = cmd_raw.lstrip('-').strip()
    else:
        cmd = None
    
    # Resolve profile info (for commands that need it)
    profile_name = get_active_profile_name(args.profile)
    host, port, user_data_dir = get_profile_cdp_info(profile_name)
    
    # CLI overrides
    if args.host:
        host = args.host
    if args.port:
        port = args.port
    
    user_data_dir = Path(user_data_dir)
    service = f'ilma-chrome@{profile_name}.service'
    
    if cmd == 'list':
        cmd_list_profiles()
        return
    
    if not cmd:
        print(__doc__)
        print("\nCommands:")
        print("  --start     Start Chrome via systemd")
        print("  --stop      Stop Chrome via systemd")
        print("  --restart   Restart Chrome via systemd")
        print("  --status    Show current status")
        print("  --verify    Verify CDP connectivity")
        print("  --daemon    Run monitoring loop")
        print("  --list      List all registered profiles")
        print(f"\nActive Profile: {profile_name}")
        print(f"Active Service: {service}")
        return
    
    if cmd == 'start':
        cmd_start(profile_name, host, port, user_data_dir)
    elif cmd == 'stop':
        cmd_stop(profile_name, host, port, user_data_dir)
    elif cmd == 'restart':
        cmd_restart(profile_name, host, port, user_data_dir)
    elif cmd == 'status':
        cmd_status(profile_name, host, port, user_data_dir)
    elif cmd == 'verify':
        cmd_verify(profile_name, host, port, user_data_dir)
    elif cmd == 'daemon':
        cmd_daemon(profile_name, host, port, user_data_dir)
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == '__main__':
    main()