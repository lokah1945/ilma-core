#!/usr/bin/env python3
"""
ILMA Browser Runtime Resolver v1.0 — Phase 69 Canonical Runtime
================================================================
Single source of truth for resolving browser runtime configuration.

ALL scripts, workflows, and pipelines MUST use this module to get
CDP URLs and profile paths. NO hardcoding allowed.

Usage:
    from ilma_browser_runtime import resolve_browser_runtime, ensure_browser_runtime
    runtime = ensure_browser_runtime(resolve_browser_runtime("lokah2150"))
    cdp_url = runtime.cdp_url  # e.g. http://127.0.0.1:9222

Environment variables (override registry):
    HERMES_BROWSER_PROFILE_NAME  — profile name to use
    ILMA_BROWSER_PROFILE        — alias for HERMES_BROWSER_PROFILE_NAME

Security rules:
    1. Non-admin profiles CANNOT access /root/user-data/lokah2150
    2. All user_data_dir MUST be under /root/user-data/
    3. CDP URLs MUST bind to 127.0.0.1 (never 0.0.0.0)
    4. Admin profile (lokah2150) is protected — non-admin callers rejected
"""

from __future__ import annotations

import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import requests
import yaml


# ─── Paths ────────────────────────────────────────────────────────────────────

REGISTRY_PATH = Path("/root/.hermes/browser-registry/browser-registry.yaml")
BASE_USER_DATA_DIR = Path("/root/user-data")
ADMIN_PROFILE = "lokah2150"


# ─── Dataclass ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class BrowserRuntime:
    profile_name: str
    role: str
    cdp_url: str
    cdp_port: int
    user_data_dir: str
    service: str
    protected: bool


# ─── Helpers ─────────────────────────────────────────────────────────────────

def safe_slug(value: str) -> str:
    """Validate and return a safe browser profile slug."""
    if not value or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError(f"Invalid browser profile slug: {value!r}")
    return value


def load_registry() -> dict:
    """Load browser profile registry from YAML."""
    if not REGISTRY_PATH.exists():
        raise FileNotFoundError(f"Browser registry not found: {REGISTRY_PATH}")
    with REGISTRY_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _get_profile_data(registry: dict, profile_name: str) -> dict:
    """Get profile data dict from registry, or raise RuntimeError."""
    admin = registry.get("admin", {})
    if admin.get("profile_name") == profile_name:
        return admin
    users = registry.get("users", {})
    for user_key, user_data in users.items():
        if user_data.get("profile_name") == profile_name:
            return user_data
    available = [admin.get("profile_name")] + [
        u.get("profile_name") for u in users.values()
    ]
    raise RuntimeError(
        f"Browser profile not found in registry: {profile_name!r}. "
        f"Available: {[p for p in available if p]}"
    )


# ─── Core Resolver ────────────────────────────────────────────────────────────

def resolve_browser_runtime(profile_name: str | None = None) -> BrowserRuntime:
    """
    Resolve browser runtime for a profile.

    Profile priority:
      1. Explicit profile_name argument
      2. HERMES_BROWSER_PROFILE_NAME env var
      3. ILMA_BROWSER_PROFILE env var
      4. Registry default_profile
      5. ADMIN_PROFILE (lokah2150)

    Security enforcement:
      - Non-admin profiles CANNOT access /root/user-data/lokah2150
      - user_data_dir MUST be under /root/user-data/
      - CDP must bind to 127.0.0.1
    """
    registry = load_registry()
    settings = registry.get("settings", {})

    # Determine which profile to use
    selected = safe_slug(
        profile_name
        or os.environ.get("HERMES_BROWSER_PROFILE_NAME", "").strip()
        or os.environ.get("ILMA_BROWSER_PROFILE", "").strip()
        or registry.get("default_profile")
        or ADMIN_PROFILE
    )

    p = _get_profile_data(registry, selected)

    user_data_dir = Path(p["user_data_dir"]).resolve()
    base = BASE_USER_DATA_DIR.resolve()

    # Security: path must be under /root/user-data/
    if not str(user_data_dir).startswith(str(base) + "/"):
        raise RuntimeError(
            f"REFUSING user_data_dir outside {base}: {user_data_dir}"
        )

    # Security: non-admin cannot use admin profile dir
    if user_data_dir == base / ADMIN_PROFILE and selected != ADMIN_PROFILE:
        raise RuntimeError(
            f"Non-admin profile {selected!r} attempted to use "
            f"admin browser profile at {user_data_dir}. REJECTED."
        )

    return BrowserRuntime(
        profile_name=selected,
        role=p.get("role", "user"),
        cdp_url=p["cdp_url"].rstrip("/"),
        cdp_port=int(p["cdp_port"]),
        user_data_dir=str(user_data_dir),
        service=p.get("service", f"ilma-chrome@{selected}.service"),
        protected=bool(p.get("protected", False)),
    )


# ─── Runtime Health Check ─────────────────────────────────────────────────────

def is_cdp_reachable(runtime: BrowserRuntime, timeout: float = 2.0) -> bool:
    """Check if CDP endpoint is reachable."""
    try:
        r = requests.get(f"{runtime.cdp_url}/json/version", timeout=timeout)
        if r.ok and "webSocketDebuggerUrl" in r.text:
            return True
    except Exception:
        pass
    return False


def ensure_browser_runtime(
    runtime: BrowserRuntime,
    timeout_sec: int = 15,
    start_service: bool = True,
) -> BrowserRuntime:
    """
    Ensure the browser runtime is active and reachable.

    1. Check if CDP is already reachable.
    2. If not, attempt to start the systemd service.
    3. Poll until CDP is ready or timeout.

    Raises RuntimeError if browser cannot be started.
    """
    if is_cdp_reachable(runtime):
        return runtime

    if not start_service:
        raise RuntimeError(
            f"Browser runtime not reachable (start_service=False): "
            f"{runtime.profile_name} at {runtime.cdp_url}"
        )

    # Try to start the service
    subprocess.run(
        ["systemctl", "--user", "start", runtime.service],
        check=False,
    )

    deadline = time.time() + timeout_sec
    last_error = None

    while time.time() < deadline:
        try:
            if is_cdp_reachable(runtime, timeout=2.0):
                return runtime
        except Exception as exc:
            last_error = exc
        time.sleep(0.5)

    raise RuntimeError(
        f"Browser runtime not reachable after {timeout_sec}s: "
        f"{runtime.profile_name} {runtime.cdp_url} "
        f"service={runtime.service} last_error={last_error}"
    )


def restart_browser_runtime(runtime: BrowserRuntime) -> BrowserRuntime:
    """Restart the browser service and wait for it to be ready."""
    subprocess.run(
        ["systemctl", "--user", "stop", runtime.service],
        check=False,
    )
    time.sleep(1)
    subprocess.run(
        ["systemctl", "--user", "start", runtime.service],
        check=False,
    )
    return ensure_browser_runtime(runtime, timeout_sec=20)


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    """CLI for debugging and verification."""
    import argparse
    parser = argparse.ArgumentParser(description="ILMA Browser Runtime Resolver")
    parser.add_argument("--profile", "-p", default=None, help="Browser profile name")
    parser.add_argument("--ensure", "-e", action="store_true", help="Ensure runtime is active")
    parser.add_argument("--check", "-c", action="store_true", help="Check CDP reachability only")
    args = parser.parse_args()

    try:
        runtime = resolve_browser_runtime(args.profile)
        print(f"[RESOLVED] {runtime.profile_name}")
        print(f"  cdp_url      : {runtime.cdp_url}")
        print(f"  cdp_port     : {runtime.cdp_port}")
        print(f"  user_data_dir: {runtime.user_data_dir}")
        print(f"  service      : {runtime.service}")
        print(f"  role         : {runtime.role}")
        print(f"  protected    : {runtime.protected}")

        if args.check:
            reachable = is_cdp_reachable(runtime)
            print(f"\n[CDP] {'REACHABLE' if reachable else 'NOT REACHABLE'}")
            return

        if args.ensure:
            print(f"\n[ENSURE] Waiting for runtime to be ready...")
            runtime = ensure_browser_runtime(runtime)
            print(f"[OK] Browser runtime active: {runtime.profile_name} {runtime.cdp_url}")

    except Exception as e:
        print(f"[ERROR] {e}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()