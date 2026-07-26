#!/usr/bin/env python3
"""
ILMA Browser Startup Guard v1.0 — Phase 69
==========================================
Startup enforcement for ILMA browser runtime.

This script runs BEFORE Hermes gateway starts (via ExecStartPre in the
Hermes systemd service) to ensure the custom browser runtime is active.

If the browser runtime is unreachable, this guard:
  1. Attempts to start/restart the systemd service
  2. Polls for CDP availability
  3. Exits with non-zero status if the browser cannot be started

Exit codes:
  0  — Browser runtime is active and reachable
  1  — Browser runtime unreachable after timeout
  2  — Registry or configuration error

Usage:
  python3 ilma_browser_startup_guard.py
  python3 ilma_browser_startup_guard.py --profile lokah2150
  python3 ilma_browser_startup_guard.py --ensure  # start service if not running
"""

from __future__ import annotations

import subprocess
import sys
import time

# Add scripts dir for imports
import os
from pathlib import Path as _Path

SCRIPTS_DIR = _Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPTS_DIR))

from ilma_browser_runtime import (
    resolve_browser_runtime,
    ensure_browser_runtime,
    is_cdp_reachable,
    REGISTRY_PATH,
)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="ILMA Browser Startup Guard")
    parser.add_argument(
        "--profile", "-p", default=None,
        help="Browser profile name (default: resolve from env/registry)"
    )
    parser.add_argument(
        "--ensure", "-e", action="store_true",
        help="Attempt to start service if CDP is unreachable"
    )
    parser.add_argument(
        "--timeout", "-t", type=int, default=15,
        help="Timeout in seconds (default: 15)"
    )
    parser.add_argument(
        "--quiet", "-q", action="store_true",
        help="Suppress output, only set exit code"
    )
    args = parser.parse_args()

    def log(msg: str) -> None:
        if not args.quiet:
            print(msg, flush=True)

    # ── 1. Resolve runtime ──────────────────────────────────────────────────
    try:
        runtime = resolve_browser_runtime(args.profile)
    except FileNotFoundError:
        log(f"[ERROR] Browser registry not found: {REGISTRY_PATH}")
        return 2
    except RuntimeError as e:
        log(f"[ERROR] {e}")
        return 2

    log(f"[STARTUP] Browser profile: {runtime.profile_name}")
    log(f"[STARTUP] Service: {runtime.service}")
    log(f"[STARTUP] CDP: {runtime.cdp_url}")

    # ── 2. Check if reachable ───────────────────────────────────────────────
    if is_cdp_reachable(runtime):
        log(f"[OK] Browser runtime active: {runtime.profile_name} {runtime.cdp_url}")
        return 0

    if not args.ensure:
        log(f"[WARN] Browser runtime not reachable (--ensure not set)")
        log(f"[WARN] Run with --ensure to attempt auto-start")
        return 1

    # ── 3. Attempt to start service ─────────────────────────────────────────
    log(f"[STARTUP] Attempting to start {runtime.service}...")

    stop_result = subprocess.run(
        ["systemctl", "--user", "stop", runtime.service],
        capture_output=True,
    )
    time.sleep(1)

    start_result = subprocess.run(
        ["systemctl", "--user", "start", runtime.service],
        capture_output=True,
    )

    if start_result.returncode != 0:
        log(f"[ERROR] Failed to start {runtime.service}")
        log(f"  stdout: {start_result.stdout.decode().strip()}")
        log(f"  stderr: {start_result.stderr.decode().strip()}")
        return 1

    log(f"[STARTUP] Service started, waiting for CDP...")

    # ── 4. Poll for CDP availability ────────────────────────────────────────
    deadline = time.time() + args.timeout
    last_error = None

    while time.time() < deadline:
        if is_cdp_reachable(runtime):
            log(f"[OK] Browser runtime active: {runtime.profile_name} {runtime.cdp_url}")
            return 0
        time.sleep(0.5)

    log(f"[ERROR] Browser runtime not reachable after {args.timeout}s")
    log(f"[ERROR] Service: {runtime.service}")
    log(f"[ERROR] CDP: {runtime.cdp_url}")
    return 1


if __name__ == "__main__":
    sys.exit(main() or 0)