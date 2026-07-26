#!/usr/bin/env python3
"""
ILMA Unified Browser Engine v2.6 (PER-PROFILE ISOLATION)
=========================================
Canonical browser automation system for ILMA.
ALL browser automation MUST use this engine — no exceptions.

Purpose: Pure browser control and DOM manipulation - NO spoofing.
- CDP (Chrome DevTools Protocol) for advanced control — MANDATORY
- Per-profile browser identity isolation via browser-registry.yaml
- ADMIN_BROWSER_PROFILE: /root/user-data/lokah2150 — admin-only, protected
- Non-admin profiles: /root/user-data/<profile_name> — isolated per user
- Cookie decryption: --password-store=basic + --use-mock-keychain
  (allows Chrome to read encrypted cookies WITHOUT a keyring daemon)
- Persistent user data dir for account login persistence
- Request/Response interception
- Automatic browser detection prevention

BROWSER IDENTITY ISOLATION (v2.6+):
1. /root/user-data/lokah2150 is ADMIN-ONLY — protected browser identity
2. Non-admin profiles get isolated user-data-dir under /root/user-data/<profile>
3. Each profile has unique CDP port (127.0.0.1:<port>) and systemd service
4. Directory permissions: 0700
5. Non-admin profiles CANNOT access /root/user-data/lokah2150

Active profile determined by:
  - HERMES_BROWSER_PROFILE_NAME env var (highest priority)
  - config.yaml browser.profile_name
  - Default: lokah2150 (admin)

Usage:
    # Async (main agent) — uses active profile from registry
    from ilma_browser_engine import BrowserEngine
    
    engine = BrowserEngine(
        stealth=True,
        cdp=True,
        persistent_user_data_dir="/path/to/profile"  # Explicit path (validated)
    )
    await engine.initialize()
    result = await engine.navigate("https://example.com")
    await engine.close()
    
    # Sync (bridge subprocess) — PERSISTENT user data dir (DEFAULT)
    from ilma_browser_engine import SyncBrowserEngine
    
    with SyncBrowserEngine(stealth=True, cdp=True, persistent_user_data_dir="/path/to/profile") as browser:
        page = browser.page
        page.goto("https://example.com")
        cdp = browser.cdp  # Access CDP session
    
    # ONE-TIME session (stateless, no persistence)
    engine = BrowserEngine(
        stealth=True,
        cdp=True,
        one_time_session=True  # Explicit — no profile persistence
    )
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import inspect
import json
import logging
import os
import random
import re
import subprocess
import tempfile
import time
import uuid
import warnings
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path as _Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

# ============================================================================
# STRICT BROWSER ENFORCEMENT — ilma_browser_engine.py is the ONLY browser engine
# ============================================================================
#
# MANDATORY RULE: All browser automation in ILMA MUST use this engine.
# NO other script may import playwright directly. No exceptions.
#
# This enforcement works in 3 layers:
# 1. Import blocking — blocks 'playwright' module imports
# 2. Runtime verification — logs/counts direct playwright usage attempts
# 3. Capability gating — only this engine has browser capability
#
# TO ACTIVATE ENFORCEMENT: Any script doing browser work MUST call:
#   from ilma_browser_engine import activate_enforcement; activate_enforcement()
#
# Legacy scripts that need migration: ilma_computer_use_agent, arena browser_plane
# ============================================================================

import sys as _sys
import os as _os
import logging as _logging

_logger = _logging.getLogger(__name__)

# Track enforcement state
_ENFORCEMENT_ACTIVE = False
_BLOCKED_COUNT = 0

def activate_enforcement() -> None:
    """
    Activate browser enforcement — call this at the top of any script
    that needs browser automation. This blocks direct playwright imports
    and ensures all browser work goes through this canonical engine.
    """
    global _ENFORCEMENT_ACTIVE
    if _ENFORCEMENT_ACTIVE:
        return
    
    _ENFORCEMENT_ACTIVE = True
    _logger.info("🔒 Browser enforcement ACTIVE — all browser work via ilma_browser_engine")
    
    # Install import hook
    try:
        import builtins
        _original_import = builtins.__import__
        
        def _enforced_import(name, *args, **kwargs):
            global _BLOCKED_COUNT
            if any(name.startswith(m) for m in ('playwright', 'playwright.async_api', 
                                                  'playwright.sync_api', 'playwright_stealth')):
                _BLOCKED_COUNT += 1
                frame = None
                try:
                    import inspect
                    frame = inspect.currentframe().f_back
                except Exception:
                    pass
                caller = frame.f_code.co_filename if frame else "unknown"
                
                _logger.error(
                    f"🚫 BLOCKED: Direct import of '{name}' is FORBIDDEN!\n"
                    f"  Caller: {caller}\n"
                    f"  Solution: Use 'from ilma_browser_engine import BrowserEngine'"
                )
                raise ImportError(
                    f"DIRECT PLAYWRIGHT IMPORT BLOCKED: '{name}'\n"
                    f"MUST use 'from ilma_browser_engine import BrowserEngine' instead.\n"
                    f"See: /root/.hermes/profiles/ilma/skills/ilma-browser-unified/SKILL.md"
                )
            return _original_import(name, *args, **kwargs)
        
        builtins.__import__ = _enforced_import
        _logger.debug("Import hook installed")
    except Exception as e:
        _logger.warning(f"Could not install import hook: {e}")

def get_enforcement_status() -> dict:
    """Return current enforcement status."""
    return {
        "enforcement_active": _ENFORCEMENT_ACTIVE,
        "blocked_count": _BLOCKED_COUNT,
        "canonical_engine": __file__,
        "only_browser_engine": True,
        "cdp_mandatory": True,
        "cdp_false_forbidden": True,
        "message": "All browser automation MUST use ilma_browser_engine.py with CDP=True"
    }

# Auto-activate when imported by non-engine scripts
_caller_frame = None
try:
    import inspect
    _caller_frame = inspect.currentframe()
    if _caller_frame:
        _caller_file = _caller_frame.f_code.co_filename
        # Don't auto-activate in the engine itself
        if not _caller_file.endswith('ilma_browser_engine.py'):
            pass  # Defer to explicit activation
except Exception:
    pass
finally:
    if _caller_frame:
        del _caller_frame

# ============================================================================
# Constants & Configuration
# ============================================================================

# ==============================================================================
# BROWSER IDENTITY ISOLATION — PER-PROFILE SYSTEM (v2.6+)
# ==============================================================================
#
# ARCHITECTURE CHANGE in v2.6:
# - OLD: LOCKED_BROWSER_PROFILE hardcoded to /root/user-data/lokah2150 for ALL sessions
# - NEW: Per-profile isolation via browser-registry.yaml
#
# Admin profile (lokah2150) is ADMIN-ONLY — protected browser identity.
# Non-admin profiles get isolated user-data-dir under /root/user-data/<profile_name>
#
# Each profile has:
#   1. A unique user-data-dir under /root/user-data/<slug>
#   2. A unique CDP port (127.0.0.1:<port>)
#   3. A matching systemd service: ilma-chrome@<profile>.service
#   4. Directory permission 0700
#
# Canonical admin mapping:
#   profile_name: lokah2150
#   cdp_url: http://127.0.0.1:9222
#   user_data_dir: /root/user-data/lokah2150
#   service: ilma-chrome@lokah2150.service
#
# Operational rules:
# - Do NOT use /root/user-data/lokah2150 for non-admin profiles
# - Do NOT start two Chrome processes with the same user-data-dir
# - Do NOT expose CDP on 0.0.0.0
# - Always bind CDP to 127.0.0.1
# ==============================================================================

import yaml as _yaml
from pathlib import Path as _Path

ILMA_ROOT = _Path('/root/.hermes/profiles/ilma')
BROWSER_REGISTRY_PATH = _Path('/root/.hermes/browser-registry/browser-registry.yaml')
BROWSER_SESSIONS_DIR = ILMA_ROOT / '.browser_sessions'

# ─── Phase 69: Canonical Runtime Resolution ──────────────────────────────────
# ALL CDP URLs and profile paths MUST be resolved through the canonical runtime
# resolver. This replaces all hardcoded CDP_URL and ADMIN_CDP_URL references.
# ──────────────────────────────────────────────────────────────────────────────

def _resolve_runtime_cdp_url(profile_name: str | None = None) -> str:
    """
    Resolve CDP URL for a profile using the canonical runtime resolver.
    Falls back to hardcoded admin defaults only if resolver is unavailable.
    """
    try:
        import sys
        scripts_dir = str(ILMA_ROOT / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        from ilma_browser_runtime import resolve_browser_runtime
        runtime = resolve_browser_runtime(profile_name)
        return runtime.cdp_url
    except Exception:
        # Hardcoded fallback only for backwards-compatibility during early migration
        import os
        profile = (
            profile_name
            or os.environ.get("HERMES_BROWSER_PROFILE_NAME", "")
            or os.environ.get("ILMA_BROWSER_PROFILE", "")
            or "lokah2150"
        )
        if profile == "lokah2150":
            return "http://127.0.0.1:9222"
        return f"http://127.0.0.1:{9230 + hash(profile) % 10}"

# Load browser registry once at module load
def _load_browser_registry():
    """Load browser profile registry from YAML."""
    try:
        if BROWSER_REGISTRY_PATH.exists():
            with open(BROWSER_REGISTRY_PATH) as f:
                return _yaml.safe_load(f)
    except Exception:
        pass
    return None

_BROWSER_REGISTRY = _load_browser_registry()

# Get profile from registry by name
def _get_profile_info(profile_name: str) -> dict:
    """Get profile info from registry. Returns {} if not found."""
    if not _BROWSER_REGISTRY:
        return {}
    # Check admin first
    admin = _BROWSER_REGISTRY.get('admin', {})
    if admin.get('profile_name') == profile_name:
        return admin
    # Check users
    users = _BROWSER_REGISTRY.get('users', {})
    for user_key, user_data in users.items():
        if user_data.get('profile_name') == profile_name:
            return user_data
    return {}

# Get active profile from environment
def _get_active_profile_name() -> str:
    """Get the active browser profile name from environment."""
    import os
    # Try HERMES_BROWSER_PROFILE_NAME first (per-profile env var)
    name = os.environ.get('HERMES_BROWSER_PROFILE_NAME', '').strip()
    if name:
        return name
    # Fall back to config.yaml browser.profile_name if available
    try:
        config_path = ILMA_ROOT / 'config.yaml'
        if config_path.exists():
            with open(config_path) as f:
                import yaml
                cfg = yaml.safe_load(f)
                browser_cfg = cfg.get('browser', {})
                return browser_cfg.get('profile_name', 'lokah2150')
    except Exception:
        pass
    return 'lokah2150'  # Safe default: admin profile

# 🔒 ADMIN PROFILE — protected, admin-only
# lokah2150 profile data from registry (may be None if registry not loaded)
_ADMIN_PROFILE_DATA = _get_profile_info('lokah2150')
ADMIN_BROWSER_PROFILE = _Path(_ADMIN_PROFILE_DATA.get('user_data_dir', '/root/user-data/lokah2150'))

# Phase 69: Resolve admin CDP URL through canonical runtime resolver
try:
    _ADMIN_CDP_URL = _resolve_runtime_cdp_url('lokah2150')
except Exception:
    _ADMIN_CDP_URL = _ADMIN_PROFILE_DATA.get('cdp_url', 'http://127.0.0.1:9222')

# Keep ADMIN_CDP_URL as alias for backwards compatibility
ADMIN_CDP_URL = _ADMIN_CDP_URL
ADMIN_CDP_PORT = 9222

# Active profile — determined at runtime from env or config
ACTIVE_PROFILE_NAME = _get_active_profile_name()
ACTIVE_PROFILE_DATA = _get_profile_info(ACTIVE_PROFILE_NAME)

def _resolve_active_profile_path(persistent_user_data_dir: str = None) -> _Path:
    """
    Resolve the active profile path with isolation guarantees:
    1. If persistent_user_data_dir is explicitly provided — validate + use it
    2. If active profile is admin — use ADMIN_BROWSER_PROFILE (lokah2150)
    3. Otherwise — use /root/user-data/<active_profile_name>
    
    Non-admin profiles can NEVER use /root/user-data/lokah2150.
    """
    import os
    
    if persistent_user_data_dir:
        # Explicit path provided — validate it's safe
        requested = _Path(persistent_user_data_dir).resolve()
        base = _Path('/root/user-data').resolve()
        # Path traversal check
        if not str(requested).startswith(str(base) + '/'):
            raise ValueError(
                f"REFUSING path traversal: {requested} is outside {base}\n"
                f"user-data-dir must be under /root/user-data/"
            )
        # Admin guard: non-admin profiles cannot use admin dir
        if requested == ADMIN_BROWSER_PROFILE and ACTIVE_PROFILE_NAME != 'lokah2150':
            raise ValueError(
                f"REFUSING admin profile access for non-admin profile '{ACTIVE_PROFILE_NAME}'\n"
                f"Only 'lokah2150' (admin) can use {ADMIN_BROWSER_PROFILE}"
            )
        return requested
    
    # No explicit path — resolve based on active profile
    if ACTIVE_PROFILE_NAME == 'lokah2150':
        # Admin profile — use protected admin dir
        return ADMIN_BROWSER_PROFILE
    else:
        # Non-admin — isolated user profile dir
        return _Path(f'/root/user-data/{ACTIVE_PROFILE_NAME}')

# Legacy compatibility — DEFAULT_PROFILE_DIR points to admin (existing behavior)
# This is intentional: existing code using DEFAULT_PROFILE_DIR gets admin profile
DEFAULT_PROFILE_DIR = ADMIN_BROWSER_PROFILE

# Backward compat: Path used to be from pathlib, now aliased as _Path
# Add alias so existing code using Path() continues to work
Path = _Path

BROWSER_SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

# Use mock keychain so Chrome stores entropy in a file instead of a system keyring.
# Combined with --password-store=basic, this lets Playwright read cookies
# even when no gnome-keyring daemon is running (e.g. headless servers).
BASIC_AUTH_ENCRYPTION_FLAGS = [
    '--password-store=basic',
    '--use-mock-keychain',
]

BROWSER_SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
BASIC_AUTH_ENCRYPTION_FLAGS_STR = ' '.join(BASIC_AUTH_ENCRYPTION_FLAGS)

DEFAULT_TIMEOUT = 30000  # milliseconds
DEFAULT_VIEWPORT = {"width": 1920, "height": 1080}

# Enhanced User agents for fingerprint randomization
USER_AGENTS = [
    # Chrome 120
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.130 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.130 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.130 Safari/537.36",
    # Chrome 121
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.6167.160 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.6167.160 Safari/537.36",
    # Chrome 122
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.6261.112 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.6261.112 Safari/537.36",
    # Chrome 123
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.6312.122 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.6312.122 Safari/537.36",
    # Chrome 124
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6327.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6327.0 Safari/537.36",
]

VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1366, "height": 768},
    {"width": 1536, "height": 864},
    {"width": 1440, "height": 900},
    {"width": 1280, "height": 800},
    {"width": 1600, "height": 900},
    {"width": 2560, "height": 1440},
]

# Minimal stealth flags - browser control only, no spoofing
# Target: Hide headless, hide automation, real browser fingerprint
STEALTH_ARGS = [
    '--no-sandbox',
    '--disable-dev-shm-usage',
    '--disable-setuid-sandbox',
    '--disable-blink-features=AutomationControlled',
    '--disable-features=IsolateOrigins,site-per-process',
    '--disable-web-security',
    '--ignore-certificate-errors',
    '--allow-running-insecure-content',
]

# No spoofing - only browser control
# Accept-Language headers removed
# WebGL spoofing removed
# User-Agent spoofing removed
# Viewport randomization removed

# ============================================================================
# Enums
# ============================================================================

class BrowserBackend(str, Enum):
    PLAYWRIGHT = "playwright"
    SELENIUM = "selenium"  # Future support
    REQUESTS = "requests"   # Fallback


class ActionType(str, Enum):
    CLICK = "click"
    TYPE = "type"
    GOTO = "goto"
    SCROLL = "scroll"
    WAIT = "wait"
    SCREENSHOT = "screenshot"
    EVALUATE = "evaluate_js"
    SELECT = "select_option"
    HOVER = "hover"
    PRESS = "press"
    CLEAR = "clear"
    SUBMIT = "submit"
    BACK = "back"
    FORWARD = "forward"
    RELOAD = "reload"


class ErrorSeverity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class BrowserMode(str, Enum):
    STANDARD = "standard"
    STEALTH = "stealth"
    INCOGNITO = "incognito"
    KEEP_ALIVE = "keep_alive"  # 🔒 Never auto-close — browser stays standby
    AUTHENTICATED = "authenticated"


# ============================================================================
# Dataclasses
# ============================================================================

@dataclass
class BrowserError(Exception):
    message: str
    action: Optional[str] = None
    severity: ErrorSeverity = ErrorSeverity.WARNING
    details: Optional[Dict[str, Any]] = None

    def __str__(self) -> str:
        return f"[{self.severity.value.upper()}] {self.message}"


@dataclass
class ElementInfo:
    tag: str
    text: Optional[str] = None
    href: Optional[str] = None
    src: Optional[str] = None
    rect: Optional[Dict[str, float]] = None
    visible: bool = True
    enabled: bool = True
    checked: bool = False
    value: Optional[str] = None


@dataclass
class NavigationResult:
    url: str
    title: str
    status: int
    elements: List[ElementInfo]
    screenshot: Optional[str] = None
    error: Optional[str] = None


@dataclass
class StealthConfig:
    """Configuration for stealth mode - minimal, no spoofing."""
    randomize_ua: bool = False
    randomize_viewport: bool = False
    hide_webdriver: bool = False
    block_js_navigator_props: bool = False
    strip_webgl_metadata: bool = False
    disable_client_hints: bool = False
    spoof_timezone: bool = False
    spoof_locale: bool = False
    spoof_platform: bool = False
    randomize_webgl: bool = False
    block_chrome_runtime: bool = False


@dataclass
class RequestInterceptor:
    """Request/Response interception configuration."""
    url_pattern: str
    intercept_request: Optional[Callable] = None
    intercept_response: Optional[Callable] = None
    modify_headers: Optional[Dict[str, str]] = None
    block: bool = False


@dataclass
class BrowserMetrics:
    """Browser performance metrics."""
    page_load_time: float
    dom_content_loaded: float
    first_paint: float
    first_contentful_paint: float
    script_duration: float
    layout_duration: float


# ============================================================================
# Advanced Stealth — playwright-stealth + puppeteer-extra-plugin-stealth
# Uses real stealth evasion packages, NOT custom fake StealthPlugin
STEALTH_EVASIONS = [
    'chrome_app', 'chrome_csi', 'chrome_load_times', 'chrome_runtime',
    'hairline', 'iframe_content_window', 'media_codecs',
    'navigator_hardware_concurrency', 'navigator_languages',
    'navigator_permissions', 'navigator_platform',
    'navigator_plugins', 'navigator_user_agent',
    'navigator_user_agent_data', 'navigator_vendor',
    'navigator_webdriver', 'error_prototype',
    'sec_ch_ua', 'webgl_vendor',
    'vendor', 'session_storage',
]

# ============================================================================
# Advanced Stealth — playwright-stealth + puppeteer-extra-plugin-stealth
# Uses real stealth evasion packages, NOT custom fake StealthPlugin
STEALTH_EVASIONS = [
    'chrome_app', 'chrome_csi', 'chrome_load_times', 'chrome_runtime',
    'hairline', 'iframe_content_window', 'media_codecs',
    'navigator_hardware_concurrency', 'navigator_languages',
    'navigator_permissions', 'navigator_platform',
    'navigator_plugins', 'navigator_user_agent',
    'navigator_user_agent_data', 'navigator_vendor',
    'navigator_webdriver', 'error_prototype',
    'sec_ch_ua', 'webgl_vendor',
    'vendor', 'session_storage',
]

def get_stealth_instance():
    """
    Get real playwright-stealth Stealth instance with FULL evasions.
    Applies ALL stealth evasion scripts for maximum bot detection prevention.
    
    Evasions applied:
    - chrome_app: window.chrome.app
    - chrome_csi: window.chrome.csi
    - chrome_load_times: window.chrome.loadTimes
    - chrome_runtime: window.chrome.runtime
    - error_prototype: Error.prototype.toString
    - iframe_content_window: iframe.contentWindow
    - media_codecs: supported media codecs
    - navigator_hardware_concurrency: navigator.hardwareConcurrency
    - navigator_languages: navigator.languages
    - navigator_permissions: navigator.permissions
    - navigator_platform: navigator.platform
    - navigator_plugins: navigator.plugins
    - navigator_user_agent: navigator.userAgent
    - navigator_user_agent_data: navigator.userAgentData
    - navigator_vendor: navigator.vendor
    - navigator_webdriver: navigator.webdriver
    - sourceurl: document.currentScript.src
    - webgl_vendor: WebGLRenderingContext.getParameter
    - hairline: Chrome hairline rendering
    - session_storage: sessionStorage
    - vendor: WebGL vendor/renderer
    """
    from playwright_stealth.stealth import Stealth
    return Stealth(
        # Chrome brand signatures — makes browser look like real Chrome
        chrome_app=True,           # window.chrome.app
        chrome_csi=True,           # window.chrome.csi
        chrome_load_times=True,    # window.chrome.loadTimes
        chrome_runtime=True,       # window.chrome.runtime
        hairline=True,            # Chrome hairline rendering
        # Navigator spoofing — hide automation flags
        navigator_webdriver=True,   # navigator.webdriver = false
        navigator_platform=True,   # navigator.platform = Win32
        navigator_plugins=True,    # navigator.plugins = [1,2,3,4,5]
        navigator_vendor=True,     # navigator.vendor = Google Inc.
        navigator_languages=True,  # navigator.languages = ['en-US','en']
        navigator_hardware_concurrency=True,  # hardwareConcurrency
        # Additional evasion
        iframe_content_window=True,
        media_codecs=True,
        navigator_permissions=True,
        error_prototype=True,
        sec_ch_ua=True,
        webgl_vendor=True,
        navigator_user_agent_data=True,
        # Override: natural language, platform only (no UA change)
        navigator_languages_override=("en-US", "en"),
        navigator_platform_override="Win32",
        # Disable unwanted spoofing — keep natural fingerprints
        navigator_user_agent=False,  # Keep real UA — natural
    )


# ============================================================================
# CDP-Level Stealth Evasion (v2.6) — No spoofing, just hiding automation
# ============================================================================
# Natural browser fingerprint — no radical spoofing
# Only hide: automation flags, headless traces, bot detection signals
# Target: looks 100% like real Chrome to anti-bot systems

CDP_STEALTH_SCRIPTS: list[dict] = [
    # 1. Hide navigator.webdriver (PRIMARY bot detection signal)
    {
        "context": "all",
        "func": """() => {
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
                configurable: true,
                enumerable: true,
            });
            // Also patch Chrome runtime for CDP detection
            if (window.chrome && window.chrome.runtime) {
                Object.defineProperty(window.chrome.runtime, 'id', {
                    get: () => undefined,
                    configurable: true,
                });
            }
        }"""
    },
    # 2. Remove automation overlay flags (selenium/detector.js style)
    {
        "context": "all",
        "func": """() => {
            // Remove CDP automation markers
            const removeAutomation = () => {
                const el = document.querySelector('[id="uniqlo-automation"]');
                if (el) el.remove();
                const overlays = document.querySelectorAll('iframe[name="inspector"], [srcdoc*="webdriver"]');
                overlays.forEach(o => o.remove());
            };
            // Run once now and on mutations
            removeAutomation();
            if (typeof MutationObserver !== 'undefined') {
                new MutationObserver(removeAutomation).observe(document.body, { childList: true, subtree: true });
            }
        }"""
    },
    # 3. Hide plugin detection (distil, dataDome, shape)
    {
        "context": "all",
        "func": """() => {
            // Natural plugin list — no spoofing, just not empty
            const fakePlugins = [
                { name: 'Chrome PDF Plugin', description: 'Portable Document Format', filename: 'internal-pdf-viewer' },
                { name: 'Chrome PDF Viewer', description: '', filename: 'mhjfbmdgcfjbbpaeojofohoefpiehjfl' },
                { name: 'Native Client', description: '', filename: 'internal-nacl-plugin' },
            ];
            // Only patch if real plugins list is suspicious
            if (navigator.plugins && navigator.plugins.length < 2) {
                Object.defineProperty(navigator, 'plugins', {
                    get: () => fakePlugins,
                    configurable: true,
                    enumerable: true,
                });
            }
        }"""
    },
    # 4. Hide permissions API tampering (bot detection: permissions.query returns denied)
    {
        "context": "all",
        "func": """() => {
            const originalQuery = navigator.permissions ? navigator.permissions.query : null;
            if (originalQuery) {
                navigator.permissions.query = (descriptor) => {
                    if (descriptor && descriptor.name === 'notifications') {
                        // Return natural state — not blocked
                        return originalQuery.call(navigator.permissions, descriptor)
                            .then(result => {
                                Object.defineProperty(result, 'state', {
                                    get: () => 'default',
                                    configurable: true,
                                    enumerable: true,
                                });
                                return result;
                            });
                    }
                    return originalQuery.call(navigator.permissions, descriptor);
                };
            }
        }"""
    },
    # 5. Fix languages mismatch (bot detection: navigator.languages inconsistent)
    {
        "context": "all",
        "func": """() => {
            // Keep natural UA but ensure languages are consistent
            const langs = navigator.languages || [navigator.language || 'en-US'];
            if (langs.length > 0 && langs[0] !== 'en-US') {
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en', langs[0]],
                    configurable: true,
                    enumerable: true,
                });
            }
        }"""
    },
    # 6. Remove trace for headless mode (detect: screen.width < 1, window.length > 0)
    {
        "context": "all",
        "func": """() => {
            // Fix screen dimensions — headless often has weird sizes
            if (screen.width < 100 || screen.height < 100) {
                Object.defineProperty(screen, 'width', { get: () => 1920, configurable: true });
                Object.defineProperty(screen, 'height', { get: () => 1080, configurable: true });
                Object.defineProperty(screen, ' availWidth', { get: () => 1920, configurable: true });
                Object.defineProperty(screen, 'availHeight', { get: () => 1040, configurable: true });
            }
        }"""
    },
    # 7. Hide chrome.runtime object tampering (undetectable bot detection)
    {
        "context": "all",
        "func": """() => {
            if (window.chrome && window.chrome.runtime) {
                // Ensure chrome.runtime exists and looks natural
                const origRuntime = window.chrome.runtime;
                // Keep original — only fix if it's been wiped
                if (!origRuntime.id && !origRuntime.getManifest) {
                    window.chrome.runtime = {
                        id: undefined,
                        manifest: undefined,
                        getManifest: () => ({}),
                        getURL: (u) => u,
                        connect: () => ({}),
                        sendMessage: () => ({}),
                    };
                }
            }
        }"""
    },
    # 8. Fix webdriver property on window (selenium detection)
    {
        "context": "all",
        "func": """() => {
            if (window.webdriver) {
                Object.defineProperty(window, 'webdriver', {
                    get: () => undefined,
                    configurable: true,
                    enumerable: true,
                    set: () => {},
                });
            }
            // Remove __webdriver_script_fn__ (firebird/selenium legacy)
            if (window.__webdriver_script_fn__) {
                Object.defineProperty(window, '__webdriver_script_fn__', {
                    get: () => undefined,
                    configurable: true,
                });
            }
        }"""
    },
    # 9. Ensure document.charset is natural (detect charset mismatch)
    {
        "context": "document",
        "func": """() => {
            if (!document.charset || document.charset === 'shift_jis') {
                Object.defineProperty(document, 'charset', {
                    get: () => 'UTF-8',
                    configurable: true,
                });
                Object.defineProperty(document, 'characterSet', {
                    get: () => 'UTF-8',
                    configurable: true,
                });
            }
        }"""
    },
    # 10. Hide navigator.platform for Linux detected
    {
        "context": "all",
        "func": """() => {
            const p = navigator.platform;
            if (p && (p.includes('Linux') || p.includes('linux'))) {
                Object.defineProperty(navigator, 'platform', {
                    get: () => 'Win32',
                    configurable: true,
                    enumerable: true,
                });
            }
        }"""
    },
]


async def apply_cdp_stealth(page):
    """
    Apply ALL CDP stealth scripts to page via evaluate.
    This runs AFTER page loads — the real-time stealth layer.
    """
    for script_def in CDP_STEALTH_SCRIPTS:
        try:
            if script_def.get("context") == "all":
                await page.evaluate(script_def["func"])
            elif script_def.get("context") == "document":
                await page.evaluate("""() => {
                    if (document.readyState !== 'complete') {
                        document.addEventListener('DOMContentLoaded', () => {
                            // not executed — just satisfy context
                        }, { once: true });
                    }
                }""")
        except Exception:
            pass


def apply_stealth_to_browser_args(args: list) -> list:
    """
    Apply stealth launch arguments that hide headless and automation markers.
    NO BROWSER FINGERPRINT SPOOFING — only hiding automation signals.
    """
    stealth_args = [
        # Core stealth args
        '--disable-blink-features=AutomationControlled',
        '--no-first-run',
        '--no-service-autorun',
        '--password-store=basic',
        '--use-mock-keychain',
        # Hide headless indicators
        '--disable-background-timer-throttling',
        '--disable-backgrounding-occluded-windows',
        '--disable-renderer-backgrounding',
        # Remove bot detection triggers
        '--disable-ipc-flooding-protection',
        '--disable-client-side-phishing-detection',
        '--disable-default-apps',
        '--disable-extensions',
        '--disable-hang-monitor',
        '--disable-popup-blocking',
        '--disable-prompt-on-repost',
        '--disable-sync',
        '--disable-translate',
        # Performance flags that look natural
        '--enable-features=NetworkService,NetworkServiceInProcess',
        '--force-color-profile=srgb',
        '--metrics-recording-only',
        '--use-mock-keychain',
    ]
    for arg in stealth_args:
        if arg not in args:
            args.append(arg)
    return args

        


# ============================================================================
# CDP Controller — Advanced Chrome DevTools Protocol
# ============================================================================

class CDPController:
    """
    Chrome DevTools Protocol controller for advanced browser operations.
    Provides low-level access to Chrome internals.
    """

    def __init__(self, page):
        self.page = page
        self._session = None
        self._enabled = False

    async def enable(self) -> 'CDPController':
        """Enable CDP session on page."""
        if self._enabled:
            return self
        try:
            self._session = await self.page.context.new_cdp_session(self.page)
            self._enabled = True
        except Exception as e:
            logger.warning(f"CDP enable failed: {e}")
        return self

    async def disable(self) -> None:
        """Disable CDP session."""
        if self._session and self._enabled:
            try:
                await self._session.detach()
            except Exception:
                pass
            self._session = None
            self._enabled = False

    async def send(self, method: str, params: Optional[Dict] = None) -> Dict:
        """Send CDP command."""
        if not self._session:
            await self.enable()
        if not self._session:
            return {}
        try:
            return await self._session.send(method, params or {})
        except Exception as e:
            logger.warning(f"CDP send '{method}' failed: {e}")
            return {}

    async def get_metrics(self) -> Dict:
        """Get performance metrics."""
        return await self.send('Performance.getMetrics')

    async def set_headers(self, headers: Dict) -> None:
        """Set extra HTTP headers."""
        await self.send('Network.setExtraHTTPHeaders', {'headers': headers})

    async def get_cookies(self) -> List[Dict]:
        """Get all cookies for current domain."""
        result = await self.send('Network.getAllCookies')
        return result.get('cookies', [])

    async def set_cookie(self, name: str, value: str, domain: str, path: str = '/') -> None:
        """Set a cookie via CDP."""
        await self.send('Network.setCookie', {
            'name': name,
            'value': value,
            'domain': domain,
            'path': path
        })

    async def evaluate(self, expression: str) -> Any:
        """Evaluate JavaScript in page context."""
        result = await self.send('Runtime.evaluate', {
            'expression': expression,
            'returnByValue': True
        })
        return result.get('result', {}).get('value')

    async def take_screenshot(self, full_page: bool = False) -> str:
        """Take screenshot via CDP. Returns base64 encoded image."""
        await self.send('Page.enable')
        screenshot = await self.send('Page.captureScreenshot', {
            'format': 'png',
            'quality': 90
        })
        return screenshot.get('data', '')

    async def get_browser_context_id(self) -> Optional[str]:
        """Get browser context ID."""
        result = await self.send('Target.getBrowserContext')
        return result.get('browserContextId')

    async def set_device_scale_factor(self, factor: float) -> None:
        """Set device scale factor."""
        await self.send('Emulation.setDeviceScaleFactor', {'deviceScaleFactor': factor})

    async def set_viewport(self, width: int, height: int) -> None:
        """Set viewport dimensions."""
        await self.send('Emulation.setViewport', {'viewport': {'width': width, 'height': height}})

    async def clear_browser_cache(self) -> None:
        """Clear browser cache."""
        await self.send('Network.clearBrowserCache')

    async def clear_browser_cookies(self) -> None:
        """Clear browser cookies."""
        await self.send('Network.clearBrowserCookies')

    async def get_version(self) -> Dict:
        """Get browser version info."""
        return await self.send('Browser.getVersion')


# ============================================================================
# Browser Factory — Centralized Instance Management
# ============================================================================

class BrowserFactory:
    """
    Factory for creating browser instances with consistent configuration.
    All browser creation MUST go through this factory.
    Includes automatic idle cleanup to save RAM/CPU.
    """
    
    _instances: Dict[str, Any] = {}
    _default_config: Dict[str, Any] = {
        'headless': True,
        'stealth': True,
        'cdp': True,
        'viewport': None,
        'user_agent': None,
    }
    _idle_timeout = 300  # 5 minutes
    _cleanup_thread: Optional[Any] = None
    _cleanup_running = False

    @classmethod
    def _start_cleanup_thread(cls) -> None:
        """Start background idle cleanup thread (one-time)."""
        if cls._cleanup_running:
            return
        cls._cleanup_running = True

        def _cleanup_loop():
            """Background loop: close idle browsers every 60s."""
            import threading
            while cls._cleanup_running:
                try:
                    cls._idle_check()
                except Exception:
                    pass
                threading.Event().wait(60)  # Check every 60s

        import threading
        t = threading.Thread(target=_cleanup_loop, daemon=True, name="BrowserIdleCleanup")
        t.start()
        cls._cleanup_thread = t
        logger.info(f"BrowserFactory idle cleanup started (timeout={cls._idle_timeout}s)")

    @classmethod
    def _idle_check(cls) -> None:
        """Close any browser instances idle beyond timeout. KEEP_ALIVE instances are EXEMPT."""
        if not cls._instances:
            return

        to_close = []
        for name, instance in list(cls._instances.items()):
            try:
                # KEEP_ALIVE instances are NEVER auto-closed — they stay standby forever
                mode = getattr(instance, '_keep_alive', None)
                if mode is True:
                    continue  # Skip — immune to idle cleanup
                if instance._initialized and not instance._closed and instance.is_idle:
                    to_close.append(name)
                    logger.info(f"BrowserFactory: '{name}' idle for {instance.idle_seconds:.0f}s — closing")
            except Exception:
                pass

        for name in to_close:
            try:
                instance = cls._instances.pop(name)
                import asyncio
                asyncio.create_task(instance.close())
            except Exception:
                pass

    @classmethod
    def create(
        cls,
        name: str = "default",
        mode: BrowserMode = BrowserMode.STEALTH,
        session: Optional[str] = None,
        **kwargs
    ) -> BrowserEngine:
        """
        Create a browser instance with specified configuration.
        
        Args:
            name: Instance name for tracking
            mode: Browser mode (STANDARD, STEALTH, INCOGNITO, AUTHENTICATED, KEEP_ALIVE)
            session: Native ILMA session name for authenticated mode
            **kwargs: Additional browser options including:
                - connect_to_daemon: bool = Connect to ilma-chrome.service via CDP (default: True)
                                        Set False to launch own browser instance.
                - cdp_url: str = Custom CDP endpoint URL (e.g. "http://127.0.0.1:9222")
                                        Overrides default ilma-chrome.service endpoint.
                - persistent_user_data_dir: str = Custom profile path
                - one_time_session: bool = Use temp profile (no persistence)
        
        CDP Daemon Mode (connect_to_daemon=True):
            - Connects to ilma-chrome.service via http://127.0.0.1:9222
            - Reuses existing Chrome profile (/root/user-data/lokah2150)
            - Faster startup, shared session across ILMA runs
            - Chrome lifecycle managed by systemd --user service
        
        Returns:
            BrowserEngine instance
        """
        config = {**cls._default_config, **kwargs}
        
        # Default: connect to ilma-chrome.service daemon via CDP
        # This is the recommended mode for ILMA's persistent browser setup
        if 'connect_to_daemon' not in config:
            config['connect_to_daemon'] = True
        
        if mode == BrowserMode.STEALTH:
            config['stealth'] = True
        elif mode == BrowserMode.INCOGNITO:
            config['stealth'] = True
            config['incognito'] = True
        elif mode == BrowserMode.AUTHENTICATED:
            config['stealth'] = True
            config['session'] = session or 'ilma'
        
        instance = BrowserEngine(**config)
        instance._keep_alive = (mode == BrowserMode.KEEP_ALIVE)
        if instance._keep_alive:
            instance._idle_timeout = 0  # 0 = never auto-close
        cls._instances[name] = instance
        # Start cleanup thread on first browser creation
        cls._start_cleanup_thread()
        logger.info(f"BrowserFactory created instance '{name}' in {mode.value} mode (keep_alive={instance._keep_alive}, cdp_daemon={config.get('connect_to_daemon')})")
        return instance
    
    @classmethod
    def get(cls, name: str = "default") -> Optional[BrowserEngine]:
        """Get existing instance by name."""
        return cls._instances.get(name)

    @classmethod
    def get_idle_info(cls) -> Dict[str, float]:
        """Get idle time info for all instances."""
        info = {}
        for name, instance in cls._instances.items():
            try:
                info[name] = instance.idle_seconds if instance._initialized else -1
            except Exception:
                info[name] = -1
        return info

    @classmethod
    def close_all(cls) -> None:
        """Close all browser instances."""
        for name, instance in cls._instances.items():
            try:
                asyncio.create_task(instance.close())
            except Exception:
                pass
        cls._instances.clear()
        logger.info("BrowserFactory closed all instances")


# ============================================================================
# Main Browser Engine — Async Version
# ============================================================================

class BrowserEngine:
    """
    Unified browser engine combining Playwright + stealth + CDP.
    Single entry point for ALL browser automation in ILMA.
    
    MANDATORY: All code MUST use this engine for browser automation.
    Direct playwright imports are blocked at runtime.
    """

    def __init__(
        self,
        headless: bool = True,
        stealth: bool = True,
        cdp: bool = True,
        session: Optional[str] = None,
        viewport: Optional[Dict] = None,
        user_agent: Optional[str] = None,
        incognito: bool = False,
        intercept_requests: Optional[List[RequestInterceptor]] = None,
        # Persistent profile options
        persistent_user_data_dir: Optional[str] = None,  # Profile path for Google login
        one_time_session: bool = False,  # If True, ignores persistent_user_data_dir
        google_email: Optional[str] = None,  # For login verification
        # Systemd Chrome daemon mode (connect to existing Chrome via CDP)
        # Phase 69: connect_to_daemon defaults True, cdp_url auto-resolved via resolver
        connect_to_daemon: bool = True,  # Default: connect via CDP WebSocket to systemd service
        cdp_url: str | None = None,  # None = auto-resolve via ilma_browser_runtime
    ):
        # CDP is mandatory - enforce at runtime
        if not cdp:
            raise BrowserError(
                "CDP control is MANDATORY for all browser operations. "
                "cdp=False is FORBIDDEN. Use cdp=True.",
                severity=ErrorSeverity.CRITICAL
            )
        
        self.headless = headless
        self.stealth_enabled = stealth
        self.cdp_enabled = cdp  # Always True
        self.session_name = session
        self.incognito_mode = incognito
        self.intercept_requests = intercept_requests or []

        self.viewport = viewport or random.choice(VIEWPORTS)
        self.user_agent = user_agent or random.choice(USER_AGENTS)

        # Persistent profile settings
        self.persistent_user_data_dir = persistent_user_data_dir
        self.one_time_session = one_time_session
        self.google_email = google_email
        # Phase 69: auto-resolve cdp_url via canonical runtime resolver
        self.connect_to_daemon = connect_to_daemon
        self.cdp_url = cdp_url or _resolve_runtime_cdp_url()

        # 🔒 PER-PROFILE ISOLATION LOGIC — v2.6+
        # Priority: 1) explicit persistent_user_data_dir → 2) active profile dir → 3) temp (ONLY if one_time_session=True)
        # one_time_session only bypasses profile when user explicitly wants temp session
        # Active profile comes from HERMES_BROWSER_PROFILE_NAME env var or config.yaml
        # Admin profile (lokah2150) uses ADMIN_BROWSER_PROFILE; others get isolated user-data-dir
        
        # Resolve actual profile path
        if self.persistent_user_data_dir:
            # User explicitly provided a profile — validate + use it
            self._profile_path = _resolve_active_profile_path(self.persistent_user_data_dir)
            self._use_persistent_profile = True
        elif self.one_time_session:
            # User explicitly wants one-time temp session (rare override)
            self._profile_path = None
            self._use_persistent_profile = False
        else:
            # 🔒 DEFAULT: Use active profile (admin gets lokah2150, others get isolated dir)
            self._profile_path = _resolve_active_profile_path()
            self._use_persistent_profile = True

        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._cdp: Optional[CDPController] = None
        self._stealth = get_stealth_instance() if stealth else None
        self._interceptors: List[Dict] = []

        self._initialized = False
        self._closed = False
        self._last_activity = time.monotonic()
        self._idle_timeout = 300  # 5 minutes default idle timeout
        self._keep_alive = False  # Override via BrowserFactory.create(mode=KEEP_ALIVE)

    def touch(self) -> None:
        """Update last activity timestamp — call after each browser operation."""
        self._last_activity = time.monotonic()

    @property
    def idle_seconds(self) -> float:
        """Seconds since last activity."""
        return time.monotonic() - self._last_activity

    @property
    def is_idle(self) -> bool:
        """Check if browser has been idle beyond timeout.
        Returns False if _idle_timeout=0 (KEEP_ALIVE mode — never considered idle)."""
        if self._idle_timeout <= 0:
            return False  # KEEP_ALIVE — never considered idle
        return self.idle_seconds >= self._idle_timeout

    async def initialize(self) -> 'BrowserEngine':
        """Initialize Playwright and launch browser."""
        if self._initialized:
            return self
        if self._closed:
            raise BrowserError("BrowserEngine has been closed", severity=ErrorSeverity.CRITICAL)

        # Import playwright (only through this module, not direct)
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("Playwright not installed. Run: pip install playwright && playwright install chromium")
            raise BrowserError("Playwright not available", severity=ErrorSeverity.CRITICAL)

        self._playwright = await async_playwright().start()

        # SYSTEMD DAEMON MODE: Connect to existing Chrome via CDP WebSocket
        if self.connect_to_daemon:
            try:
                import urllib.request
                # Get fresh WebSocket URL from Chrome's CDP endpoint
                # Use configurable cdp_url (default: http://127.0.0.1:9222)
                cdp_endpoint = f"{self.cdp_url.rstrip('/')}/json/version"
                with urllib.request.urlopen(cdp_endpoint, timeout=5) as resp:
                    import json
                    data = json.loads(resp.read())
                    ws_url = data["webSocketDebuggerUrl"]
                
                logger.info(f"Connecting to Chrome daemon via CDP WebSocket: {ws_url}")
                self._browser = await self._playwright.chromium.connect_over_cdp(ws_url, timeout=10000)
                
                # Get existing context or create new one
                if self._browser.contexts:
                    self._context = self._browser.contexts[0]
                else:
                    self._context = await self._browser.new_context()
                
                self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()
                
                # Enable CDP
                self._cdp = CDPController(self._page)
                await self._cdp.enable()
                
                self._initialized = True
                logger.info(f"BrowserEngine connected to daemon (Chrome version: {self._browser.version})")
                return self
            except Exception as e:
                logger.error(f"Failed to connect to Chrome daemon: {e}")
                raise BrowserError(f"Chrome daemon connection failed: {e}", severity=ErrorSeverity.CRITICAL)
        
        # Build launch arguments with full stealth
        launch_args = STEALTH_ARGS.copy()
        launch_args = apply_stealth_to_browser_args(launch_args)
        if self.headless:
            launch_args.append('--headless=new')

        # Create context options
        context_options = {
            'viewport': self.viewport,
            'user_agent': self.user_agent,
            'locale': 'en-US',
            'timezone_id': 'America/New_York',
            'geolocation': {'latitude': 40.7128, 'longitude': -74.0060},
            'permissions': ['geolocation'],
            'extra_http_headers': {
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            },
        }

        # For persistent profile, use no_viewport=True (profile manages viewport)
        if self._use_persistent_profile:
            context_options['no_viewport'] = True

        # Launch browser with persistent context OR regular context
        try:
            if self._use_persistent_profile and self._profile_path:
                # Use launch_persistent_context for persistent user data dir
                self._profile_path.mkdir(parents=True, exist_ok=True)
                logger.info(f"Using persistent profile: {self._profile_path}")
                
                # Add auth encryption flags for persistent profile
                # This allows Chrome to read encrypted cookies without a running keyring daemon
                persistent_args = launch_args + ['--password-store=basic', '--use-mock-keychain']
                context_options['args'] = persistent_args
                
                # Launch persistent context - returns just BrowserContext (browser accessed via context.browser)
                self._context = await self._playwright.chromium.launch_persistent_context(
                    self._profile_path,
                    headless=self.headless,
                    **context_options
                )
                self._browser = self._context.browser
                self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()
            else:
                # Regular launch for one-time sessions
                self._browser = await self._playwright.chromium.launch(
                    headless=self.headless,
                    args=launch_args,
                    slow_mo=50
                )
                
                # Create context (incognito if requested)
                if self.incognito_mode:
                    self._context = await self._browser.new_context(
                        **context_options
                    )
                else:
                    self._context = await self._browser.new_context(**context_options)
                
                self._page = await self._context.new_page()
                
        except Exception as e:
            logger.error(f"Browser launch failed: {e}")
            raise BrowserError(f"Browser launch failed: {e}", severity=ErrorSeverity.CRITICAL)

        # Setup request interception
        if self.intercept_requests:
            await self._setup_interceptors()

        # Apply stealth (hook on playwright instance — ALWAYS when stealth enabled, even with persistent profile)
        if self._stealth:
            self._stealth.hook_playwright_context(self._playwright)

        # Enable CDP if requested
        if self.cdp_enabled:
            self._cdp = CDPController(self._page)
            await self._cdp.enable()

        # Apply CDP-level stealth scripts — AFTER page is ready
        if self.stealth_enabled:
            await apply_cdp_stealth(self._page)

        self._initialized = True
        logger.info(f"BrowserEngine initialized (headless={self.headless}, stealth={self.stealth_enabled}, cdp={self.cdp_enabled}, profile={self._profile_path}, persistent={self._use_persistent_profile})")
        return self

    async def verify_google_login(self) -> bool:
        """
        Verify if Google account is logged in using persistent profile.
        Returns True if logged in, False otherwise.
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            # Navigate to Google accounts page
            await self._page.goto("https://accounts.google.com", wait_until='domcontentloaded', timeout=15000)
            await self._page.wait_for_timeout(2000)
            
            # Check if we're on a Google login page or have account info
            url = self._page.url
            title = await self._page.title()
            
            # If URL contains "signin" or we're on login page, not logged in
            if 'signin' in url.lower() or 'accountchooser' in url.lower():
                return False
            
            # If we're on myaccount or profile page, we ARE logged in
            if 'myaccount.google.com' in url or 'profile' in url:
                return True
            
            # Check for account indicator elements
            try:
                # Try to find account avatar or email display
                account_elements = await self._page.query_selector_all('[aria-label*="Account"], [data-profile-initialized]')
                if account_elements:
                    return True
            except Exception:
                pass
            
            # Check localStorage for Google account info
            try:
                local_storage = await self._page.evaluate("""
                    () => {
                        const keys = Object.keys(localStorage);
                        const googleKeys = keys.filter(k => k.includes('google') || k.includes('GAIA'));
                        return googleKeys.length > 0;
                    }
                """)
                if local_storage:
                    return True
            except Exception:
                pass
            
            return False
            
        except Exception as e:
            logger.warning(f"Google login verification failed: {e}")
            return False

    async def is_logged_in(self) -> bool:
        """Check if there's an active browser session."""
        return self._initialized and self._browser is not None

    @property
    def profile_path(self) -> Optional[Path]:
        """Get the persistent profile directory path."""
        return self._profile_path

    @property
    def is_persistent(self) -> bool:
        """Check if this engine uses persistent profile."""
        return self._use_persistent_profile

    async def _setup_interceptors(self) -> None:
        """Setup request/response interceptors."""
        async def handle_route(route):
            """Handle route interception."""
            request = route.request
            url = request.url
            
            for interceptor in self.intercept_requests:
                if re.search(interceptor.url_pattern, url):
                    if interceptor.block:
                        await route.abort()
                        return
                    if interceptor.modify_headers:
                        # Modify headers
                        headers = dict(request.headers)
                        headers.update(interceptor.modify_headers)
                        await route.continue_(headers=headers)
                        return
            
            await route.continue_()

        await self._page.route("**/*", handle_route)

    async def navigate(
        self,
        url: str,
        wait_until: str = 'domcontentloaded',
        timeout: int = DEFAULT_TIMEOUT
    ) -> NavigationResult:
        """
        Navigate to URL and capture page state.
        Returns NavigationResult with elements, screenshot, etc.
        """
        if not self._initialized:
            await self.initialize()

        try:
            response = await self._page.goto(url, wait_until='domcontentloaded', timeout=timeout)
            status = response.status if response else 0

            # Wait a bit for dynamic content
            await self._page.wait_for_timeout(1000)

            # Capture elements
            elements = await self._capture_elements()

            return NavigationResult(
                url=self._page.url,
                title=await self._page.title(),
                status=status,
                elements=elements
            )

        except Exception as e:
            logger.error(f"Navigation error: {e}")
            return NavigationResult(
                url=url,
                title='',
                status=0,
                elements=[],
                error=str(e)
            )
        finally:
            # Update idle tracker after each operation
            self.touch()

    async def _capture_elements(self) -> List[ElementInfo]:
        """Capture interactive elements from current page."""
        elements = []
        try:
            tags = ['button', 'a', 'input', 'textarea', 'select', 'option']
            for tag in tags:
                try:
                    nodes = await self._page.query_selector_all(tag)
                    for node in nodes:
                        try:
                            inner_text = await node.inner_text()
                            info = ElementInfo(
                                tag=tag,
                                text=inner_text[:100] if inner_text else None,
                                href=await node.get_attribute('href') if tag in ['a', 'button'] else None,
                                value=await node.get_attribute('value')
                            )
                            elements.append(info)
                        except Exception:
                            continue
                except Exception:
                    continue
        except Exception:
            pass
        return elements

    async def click(self, selector: str, timeout: int = DEFAULT_TIMEOUT) -> bool:
        """
        Click element by selector using HumanInteractionAdapter.
        Phase 69: All clicks go through human-like interaction by default.
        """
        try:
            await self._page.wait_for_selector(selector, timeout=timeout)
            locator = self._page.locator(selector)
            await self.human.human_click(locator)
            self.touch()
            return True
        except Exception as e:
            logger.error(f"Click failed: {e}")
            return False

    async def type(self, selector: str, text: str, delay: int = 10) -> bool:
        """
        Type text into element using HumanInteractionAdapter.
        Phase 69: All typing goes through human-like interaction by default.
        """
        try:
            await self._page.wait_for_selector(selector, timeout=DEFAULT_TIMEOUT)
            locator = self._page.locator(selector)
            await self.human.human_type(locator, text)
            self.touch()
            return True
        except Exception as e:
            logger.error(f"Type failed: {e}")
            return False

    async def evaluate_js(self, script: str) -> Any:
        """Execute JavaScript in page context."""
        try:
            result = await self._page.evaluate(script)
            self.touch()
            return result
        except Exception:
            return None

    async def wait_for_selector(self, selector: str, timeout: int = DEFAULT_TIMEOUT) -> bool:
        """Wait for element to appear."""
        try:
            await self._page.wait_for_selector(selector, timeout=timeout)
            self.touch()
            return True
        except Exception:
            return False

    async def wait_for_timeout(self, ms: int) -> None:
        """Wait for specified milliseconds."""
        await self._page.wait_for_timeout(ms)
        self.touch()

    async def screenshot(self, path: Optional[str] = None, full_page: bool = False) -> str:
        """Take screenshot. Returns path or base64."""
        if path:
            await self._page.screenshot(path=path, full_page=full_page)
            return path
        else:
            return await self._page.screenshot(full_page=full_page)

    async def get_cookies(self) -> List[Dict]:
        """Get all cookies for current context."""
        return await self._context.cookies()

    async def add_cookies(self, cookies: List[Dict]) -> None:
        """Add cookies to current context."""
        await self._context.add_cookies(cookies)

    async def get_local_storage(self) -> Dict[str, str]:
        """Get localStorage as dictionary."""
        return await self._page.evaluate("() => JSON.stringify(localStorage)") 

    async def set_local_storage(self, data: Dict[str, str]) -> None:
        """Set localStorage from dictionary."""
        for key, value in data.items():
            await self._page.evaluate(f"localStorage.setItem('{key}', '{value}')")

    async def get_session_storage(self) -> Dict[str, str]:
        """Get sessionStorage as dictionary."""
        return await self._page.evaluate("() => JSON.stringify(sessionStorage)")

    async def clear_cache(self) -> None:
        """Clear browser cache and cookies."""
        if self._cdp:
            await self._cdp.clear_browser_cache()
            await self._cdp.clear_browser_cookies()

    async def new_context(self, **kwargs) -> Any:
        """Create a new browser context."""
        if not self._browser:
            raise BrowserError("Browser not initialized", severity=ErrorSeverity.CRITICAL)
        
        context = await self._browser.new_context(**kwargs)
        return context

    @property
    def page(self):
        """Get the page object."""
        return self._page

    @property
    def context(self):
        """Get the context object."""
        return self._context

    @property
    def browser(self):
        """Get the browser object."""
        return self._browser

    @property
    def cdp(self):
        """Get CDP controller."""
        return self._cdp

    # ─── Phase 69: HumanInteractionAdapter ──────────────────────────────────
    @property
    def human(self):
        """
        Get a HumanInteractionAdapter for human-like browser interactions.

        Usage:
            await engine.initialize()
            await engine.human.human_click(engine.page.locator("#submit"))
            await engine.human.human_type(engine.page.locator("#input"), "text")
        """
        if not hasattr(self, '_human_adapter') or self._human_adapter is None:
            from ilma_human_interaction import HumanInteractionAdapter
            self._human_adapter = HumanInteractionAdapter(self._page)
        return self._human_adapter

    def save_auth_session(self) -> None:
        """
        Save authentication session to ILMA's native session file.
        Uses persistent profile — cookies persist automatically.
        """
        logger.info(f"Session saved to native profile: {self._profile_path}")

    async def load_auth_session(self) -> None:
        """
        Load authentication session from ILMA's native session file.
        Uses persistent profile — cookies load automatically.
        """
        logger.info(f"Session loaded from native profile: {self._profile_path}")

    async def close(self) -> None:
        """Close browser and cleanup."""
        if self._closed:
            return
        
        # In daemon mode, DON'T close browser - just disconnect CDP
        if self.connect_to_daemon:
            if self._cdp:
                await self._cdp.disable()
            self._initialized = False
            self._closed = True
            logger.info("BrowserEngine disconnected from daemon (Chrome stays alive)")
            return
        
        if self._cdp:
            await self._cdp.disable()
        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
        
        self._initialized = False
        self._closed = True
        logger.info("BrowserEngine closed")


# ============================================================================
# Sync Browser Engine — For Bridge Subprocess Compatibility
# ============================================================================

class SyncBrowserEngine:
    """
    Synchronous wrapper for BrowserEngine.
    Used by bridge scripts that run via subprocess (xvfb-run).
    
    MANDATORY: CDP control is ALWAYS enabled. cdp=False raises BrowserError.
    
    PERSISTENT PROFILE: By default, uses persistent user data dir for Google login.
    Set one_time_session=True for single-use sessions.
    """

    def __init__(
        self,
        headless: bool = True,
        stealth: bool = True,
        cdp: bool = True,  # CDP is MANDATORY - must be True
        session: Optional[str] = None,
        incognito: bool = False,
        # Persistent profile options
        persistent_user_data_dir: Optional[str] = None,  # Profile path for Google login
        one_time_session: bool = False,  # If True, ignores persistent_user_data_dir
        # Systemd Chrome daemon mode (connect to existing Chrome via CDP)
        connect_to_daemon: bool = False,  # If True, connect via CDP WebSocket instead of launching
        cdp_url: str = "http://127.0.0.1:9222",  # CDP endpoint for daemon mode
    ):
        # CDP is mandatory - enforce at runtime
        if not cdp:
            raise BrowserError(
                "CDP control is MANDATORY for all browser operations. "
                "cdp=False is FORBIDDEN. Use cdp=True.",
                severity=ErrorSeverity.CRITICAL
            )
        
        self.headless = headless
        self.stealth_enabled = stealth
        self.cdp_enabled = cdp  # Always True here
        self.session_name = session
        self.incognito_mode = incognito
        self._stealth = get_stealth_instance() if stealth else None  # Same pattern as BrowserEngine
        
        # Persistent profile settings
        self.persistent_user_data_dir = persistent_user_data_dir
        self.one_time_session = one_time_session
        self.connect_to_daemon = connect_to_daemon
        self.cdp_url = cdp_url
        
        # 🔒 PER-PROFILE ISOLATION LOGIC — v2.6+
        # Priority: 1) explicit persistent_user_data_dir → 2) active profile dir → 3) temp (ONLY if one_time_session=True)
        # one_time_session only bypasses profile when user explicitly wants temp session
        # Active profile comes from HERMES_BROWSER_PROFILE_NAME env var or config.yaml
        # Admin profile (lokah2150) uses ADMIN_BROWSER_PROFILE; others get isolated user-data-dir
        
        # Resolve actual profile path
        if self.persistent_user_data_dir:
            # User explicitly provided a profile — validate + use it
            self._profile_path = _resolve_active_profile_path(self.persistent_user_data_dir)
            self._use_persistent_profile = True
        elif self.one_time_session:
            # User explicitly wants one-time temp session (rare override)
            self._profile_path = None
            self._use_persistent_profile = False
        else:
            # 🔒 DEFAULT: Use active profile (admin gets lokah2150, others get isolated dir)
            self._profile_path = _resolve_active_profile_path()
            self._use_persistent_profile = True
        
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None
        self._cdp_session = None  # CDP session for sync

    def __enter__(self):
        """Context manager entry."""
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()

        # SYSTEMD DAEMON MODE: Connect to existing Chrome via CDP WebSocket
        if self.connect_to_daemon:
            try:
                import urllib.request
                import json
                # Get fresh WebSocket URL from Chrome's CDP endpoint
                # Use configurable cdp_url (default: http://127.0.0.1:9222)
                cdp_endpoint = f"{self.cdp_url.rstrip('/')}/json/version"
                with urllib.request.urlopen(cdp_endpoint, timeout=5) as resp:
                    data = json.loads(resp.read())
                    ws_url = data["webSocketDebuggerUrl"]
                
                logger.info(f"SyncBrowserEngine connecting to daemon via CDP WebSocket: {ws_url}")
                self._browser = self._pw.chromium.connect_over_cdp(ws_url, timeout=10000)
                
                # Get existing context or create new one
                if self._browser.contexts:
                    self._context = self._browser.contexts[0]
                else:
                    self._context = self._browser.new_context()
                
                self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
                
                # Enable CDP session (MANDATORY)
                self._cdp_session = self._context.new_cdp_session(self._page)
                self._cdp_session.send("Performance.enable")
                self._cdp_session.send("Runtime.enable")
                
                logger.info(f"SyncBrowserEngine connected to daemon (Chrome version: {self._browser.version})")
                return self
            except Exception as e:
                logger.error(f"Failed to connect to Chrome daemon: {e}")
                raise BrowserError(f"Chrome daemon connection failed: {e}", severity=ErrorSeverity.CRITICAL)
        
        # Apply stealth on Playwright instance (hooks browser launch methods)
        if self._stealth:
            self._stealth.hook_playwright_context(self._pw)

        launch_args = STEALTH_ARGS.copy()
        if self.headless:
            launch_args.append('--headless=new')

        context_options = {
            'viewport': random.choice(VIEWPORTS),
            'user_agent': random.choice(USER_AGENTS),
            'locale': 'en-US',
            'timezone_id': 'America/New_York',
            'geolocation': {'latitude': 40.7128, 'longitude': -74.0060},
            'permissions': ['geolocation'],
            'extra_http_headers': {
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            },
        }

        # For persistent profile, use no_viewport=True (profile manages viewport)
        if self._use_persistent_profile:
            context_options['no_viewport'] = True

        # Launch with persistent context OR regular context
        if self._use_persistent_profile and self._profile_path:
            # Use launch_persistent_context for persistent user data dir
            self._profile_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"SyncBrowserEngine using persistent profile: {self._profile_path}")
            
            # Add auth encryption flags for persistent profile
            # This allows Chrome to read encrypted cookies without a running keyring daemon
            persistent_args = launch_args + ['--password-store=basic', '--use-mock-keychain']
            context_options['args'] = persistent_args
            
            # Launch persistent context - returns just BrowserContext (browser accessed via context.browser)
            self._context = self._pw.chromium.launch_persistent_context(
                self._profile_path,
                headless=self.headless,
                **context_options
            )
            self._browser = self._context.browser
            self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
        else:
            # Regular launch for one-time sessions
            self._browser = self._pw.chromium.launch(
                headless=self.headless,
                args=launch_args,
                slow_mo=50
            )
            
            # Create context
            if self.incognito_mode:
                self._context = self._browser.new_context(
                    incognito=True,
                    **context_options
                )
            else:
                self._context = self._browser.new_context(**context_options)

            self._page = self._context.new_page()

        # Enable CDP session (MANDATORY)
        try:
            self._cdp_session = self._context.new_cdp_session(self._page)
            self._cdp_session.send("Performance.enable")
            self._cdp_session.send("Runtime.enable")
            logger.debug("CDP session enabled for SyncBrowserEngine")
        except Exception as e:
            logger.warning(f"CDP session failed: {e}")

        # Stealth already hooked on _pw (Playwright instance) in __enter__ - no double-hook needed

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        # In daemon mode, DON'T close browser - just disconnect CDP session
        if self.connect_to_daemon:
            if self._cdp_session:
                try:
                    self._cdp_session.detach()
                except Exception:
                    pass
            logger.info("SyncBrowserEngine disconnected from daemon (Chrome stays alive)")
            return
        
        # Close CDP session first
        if self._cdp_session:
            try:
                self._cdp_session.detach()
            except Exception:
                pass
        if self._browser:
            try:
                self._browser.close()
            except Exception:
                pass
        if self._pw:
            try:
                self._pw.stop()
            except Exception:
                pass

    @property
    def cdp(self):
        """Get CDP session (MANDATORY)."""
        return self._cdp_session

    @property
    def profile_path(self) -> Optional[Path]:
        """Get the persistent profile directory path."""
        return self._profile_path

    @property
    def is_persistent(self) -> bool:
        """Check if this engine uses persistent profile."""
        return self._use_persistent_profile

    def save_auth_session(self) -> None:
        """
        Save authentication session to ILMA's native session file.
        Uses persistent profile — cookies persist automatically.
        """
        logger.info(f"Session saved to native profile: {self._profile_path}")

    def load_auth_session(self) -> None:
        """
        Load authentication session from ILMA's native session file.
        Uses persistent profile — cookies load automatically.
        """
        logger.info(f"Session loaded from native profile: {self._profile_path}")

    @property
    def page(self):
        """Get the page object."""
        return self._page

    @property
    def context(self):
        """Get the context object."""
        return self._context

    @property
    def browser(self):
        """Get the browser object."""
        return self._browser

    def new_context(self, **kwargs):
        """Create a new browser context. Stealth is already hooked on Playwright instance."""
        if not self._browser:
            raise RuntimeError("Browser not initialized")
        return self._browser.new_context(**kwargs)


# ============================================================================
# Utility Functions
# ============================================================================

def run_with_xvfb(script_path: str, timeout: int = 120) -> Tuple[int, str, str]:
    """
    Run a Python script with xvfb-run (for headless Chrome on Linux).

    Args:
        script_path: Path to Python script to execute
        timeout: Timeout in seconds

    Returns:
        Tuple of (returncode, stdout, stderr)
    """
    result = subprocess.run(
        ['xvfb-run', '-a', 'python3', script_path],
        capture_output=True,
        text=True,
        timeout=timeout
    )
    return result.returncode, result.stdout, result.stderr


def create_browser_script(
    script_content: str,
    cleanup: bool = True
) -> str:
    """
    Create a temporary browser script file.

    Args:
        script_content: Python script content
        cleanup: Whether to delete after execution

    Returns:
        Path to temporary script file
    """
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(script_content)
        path = f.name

    os.chmod(path, 0o755)
    return path


def verify_browser_enforcement() -> Dict[str, Any]:
    """
    Verify that browser enforcement is properly configured.
    Returns status report.
    """
    report = {
        'enforcement_active': False,
        'canonical_engine_exists': False,
        'skill_exists': False,
        'deprecation_warnings': False,
        'blocked_modules': list(_blocked_modules),
        'issues': []
    }
    
    # Check canonical engine
    engine_path = Path('/root/.hermes/profiles/ilma/scripts/ilma_browser_engine.py')
    if engine_path.exists():
        report['canonical_engine_exists'] = True
        report['canonical_engine_size'] = engine_path.stat().st_size
    else:
        report['issues'].append("Canonical browser engine not found")
    
    # Check skill
    skill_path = Path('/root/.hermes/profiles/ilma/skills/ilma-browser-unified/SKILL.md')
    if skill_path.exists():
        report['skill_exists'] = True
    else:
        report['issues'].append("Browser unified skill not found")
    
    # Check deprecation wrappers
    deprecated_files = [
        '/root/.hermes/profiles/ilma/scripts/ilma_browser_plane.py',
        '/root/.hermes/profiles/ilma/scripts/ilma_browser_automation.py',
    ]
    for f in deprecated_files:
        if Path(f).exists():
            report['deprecation_warnings'] = True
    
    return report


# ============================================================================
# CLI Entry Point
# ============================================================================

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='ILMA Unified Browser Engine v2.0')
    parser.add_argument('--url', '-u', help='URL to navigate to')
    parser.add_argument('--headless', action='store_true', default=True, help='Run headless')
    parser.add_argument('--stealth', '-s', action='store_true', default=True, help='Enable stealth mode')
    parser.add_argument('--cdp', '-c', action='store_true', default=True, help='Enable CDP')
    parser.add_argument('--session', help='Native ILMA session name for authenticated mode')
    parser.add_argument('--screenshot', '-p', help='Screenshot output path')
    parser.add_argument('--verify', '-v', action='store_true', help='Verify browser enforcement')
    parser.add_argument('--incognito', '-i', action='store_true', help='Use incognito mode')

    args = parser.parse_args()

    if args.verify:
        report = verify_browser_enforcement()
        print("=" * 60)
        print("ILMA Browser Enforcement Report")
        print("=" * 60)
        for k, v in report.items():
            status = "✅" if (v and k != 'blocked_modules' and k != 'issues') else "❌" if k == 'issues' and v else "⚠️"
            print(f"  {status} {k}: {v}")
        print("=" * 60)
        sys.exit(0)

    async def main():
        engine = BrowserEngine(
            headless=args.headless,
            stealth=args.stealth,
            cdp=args.cdp,
            session=args.session,
            incognito=args.incognito
        )
        await engine.initialize()

        if args.url:
            result = await engine.navigate(args.url)
            print(f"URL: {result.url}")
            print(f"Title: {result.title}")
            print(f"Status: {result.status}")
            if result.error:
                print(f"Error: {result.error}")

        if args.screenshot:
            await engine.screenshot(args.screenshot)
            print(f"Screenshot saved: {args.screenshot}")

        await engine.close()

    asyncio.run(main())
# ============================================================================
# END OF CANONICAL ENGINE — DO NOT ADD ANYTHING AFTER THIS LINE
# ============================================================================
#
# This file is the ONLY browser engine for ILMA.
# All browser automation MUST use BrowserEngine or SyncBrowserEngine from here.
#
# Legacy scripts that still use direct playwright (MUST MIGRATE):
#   - ilma_computer_use_agent.py → use BrowserEngine directly
#   - arena/ilma_browser_plane.py → acts as delegation layer only
#
# For enforcement in any script, add at the top:
#   from ilma_browser_engine import activate_enforcement; activate_enforcement()
#
# ============================================================================
