#!/usr/bin/env python3
"""
ILMA Browser Daemon v3.0 — Persistent Context Architecture
==========================================================
Chrome runs as a STANDALONE subprocess. ILMA connects via Playwright CDP WebSocket.
Browser NEVER dies across ILMA restarts. ILMA hanya connect/disconnect via CDP.

Core principle:
- Chrome是一次启动，长期运行 (start once, run forever)
- ILMA每次只是连接/断开CDP session，不是重启浏览器
- Tab管理通过CDP Target domain，ILMA创建的tab自己负责关闭

Pipe vs WebSocket untuk Linux:
- Chrome Linux TIDAK support --remote-debugging-pipe (Windows only)
- Chrome Linux hanya support WebSocket via --remote-debugging-port=9222
- WebSocket adalah "pipe equivalent" untuk Linux — bidirectional, persistent
- Efficiency: WebSocket tidak lebih boros dari pipe; keduanya sama-sama IPC

Profile: LOCKED_BROWSER_PROFILE=/root/user-data/lokah2150
"""

import asyncio
import atexit
import json
import os
import re
import signal
import socket
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any

ILMA_ROOT = Path('/root/.hermes/profiles/ilma')
sys.path.insert(0, str(ILMA_ROOT / 'scripts'))

import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger('browser_daemon')

# ─── Constants ────────────────────────────────────────────────────────────────

LOCKED_BROWSER_PROFILE = Path('/root/user-data/lokah2150')
HEADLESS_SHELL = '/root/.cache/ms-playwright/chromium_headless_shell-1217/chrome-headless-shell-linux64/chrome-headless-shell'
CHROME_PATH = os.environ.get('ILMA_CHROME_PATH', HEADLESS_SHELL)
CDP_PORT = 9222
CDP_HOST = '127.0.0.1'
PROFILE_ARGS = [
    f'--user-data-dir={LOCKED_BROWSER_PROFILE}',
]

# Stealth: only hide automation signal, NO fingerprint spoofing
CHROME_STEALTH_ARGS = [
    '--remote-debugging-port=9222',
    '--disable-blink-features=AutomationControlled',
    '--no-first-run',
    '--no-service-autorun',
    '--password-store=basic',
    '--use-mock-keychain',
    '--headless=new',
    '--hide-scrollbars',
    '--mute-audio',
    '--no-sandbox',
    '--disable-dev-shm-usage',
    '--disable-setuid-sandbox',
    '--disable-background-networking',
    '--disable-background-timer-throttling',
    '--disable-backgrounding-occluded-windows',
    '--disable-renderer-backgrounding',
    '--disable-ipc-flooding-protection',
    '--disable-client-side-phificate',
    '--disable-default-apps',
    '--disable-extensions',
    '--disable-hang-monitor',
    '--disable-popup-blocking',
    '--disable-prompt-on-repost',
    '--disable-sync',
    '--disable-translate',
    '--enable-features=NetworkService,NetworkServiceInProcess2',
    '--force-color-profile=srgb',
    '--metrics-recording-only',
]

# ─── Singleton Browser Process ─────────────────────────────────────────────────

_chrome_process: Optional[subprocess.Popen] = None
_chrome_lock = threading.Lock()


def _ensure_chrome_running() -> subprocess.Popen:
    """Ensure Chrome is running. Returns existing process if already running."""
    global _chrome_process

    with _chrome_lock:
        # Check if already running
        if _chrome_process and _chrome_process.poll() is None:
            return _chrome_process

        # Check if port 9222 is already listening (another Chrome instance)
        if _is_port_open(CDP_HOST, CDP_PORT):
            logger.info(f'Chrome already running on port {CDP_PORT} (external)')
            # We don't own this process
            _chrome_process = None
            return None

        # Launch new Chrome
        cmd = [CHROME_PATH] + PROFILE_ARGS + CHROME_STEALTH_ARGS
        logger.info(f'Launching Chrome: {" ".join(cmd[:5])} ...')

        _chrome_process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        logger.info(f'Chrome launched, PID={_chrome_process.pid}')
        return _chrome_process


def _is_port_open(host: str, port: int) -> bool:
    """Check if a port is open."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


def _wait_for_cdp_ready(host: str = CDP_HOST, port: int = CDP_PORT, timeout: float = 10.0) -> bool:
    """Wait for CDP port to be ready."""
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        if _is_port_open(host, port):
            # Give Chrome a moment to fully initialize WebSocket endpoint
            time.sleep(0.5)
            return True
        time.sleep(0.2)
    return False


def _kill_chrome(pid: int) -> None:
    """Kill Chrome process by PID."""
    try:
        os.kill(pid, signal.SIGTERM)
        time.sleep(0.3)
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    except ProcessLookupError:
        pass


def _get_chrome_pid_from_port(port: int = CDP_PORT) -> Optional[int]:
    """Get Chrome PID from debugging port."""
    try:
        # Try lsof first
        result = subprocess.run(
            ['lsof', '-ti', f':{port}'],
            capture_output=True, text=True, timeout=5
        )
        pids = [p.strip() for p in result.stdout.splitlines() if p.strip()]
        if pids:
            return int(pids[0])
    except Exception:
        pass

    # Fallback: parse ps output
    try:
        result = subprocess.run(
            ['ps', 'aux'],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.splitlines():
            port_str = str(port)
            if ('--remote-debugging-port=' + port_str) in line or (':' + port_str) in line:
                parts = line.split()
                if len(parts) > 1:
                    return int(parts[1])
    except Exception:
        pass

    return None


# ─── CDP Target Operations ─────────────────────────────────────────────────────

async def _cdp_targets_list(ws_url: str) -> List[Dict]:
    """List all browser targets via CDP WebSocket."""
    import websockets
    try:
        async with websockets.connect(ws_url, ping_interval=None) as ws:
            msg_id = 1
            await ws.send(json.dumps({
                'id': msg_id,
                'method': 'Target.getTargets',
                'params': {}
            }))
            resp = await asyncio.wait_for(ws.recv(), timeout=5.0)
            data = json.loads(resp)
            return data.get('result', {}).get('targetInfos', [])
    except Exception:
        return []


async def _cdp_create_target(ws_url: str, url: str = 'about:blank') -> Optional[str]:
    """Create a new target (tab) via CDP."""
    import websockets
    try:
        async with websockets.connect(ws_url, ping_interval=None) as ws:
            msg_id = 1
            await ws.send(json.dumps({
                'id': msg_id,
                'method': 'Target.createTarget',
                'params': {'url': url}
            }))
            resp = await asyncio.wait_for(ws.recv(), timeout=10.0)
            data = json.loads(resp)
            target_id = data.get('result', {}).get('targetId')
            logger.info(f'CDP created target: {target_id}')
            return target_id
    except Exception as e:
        logger.error(f'CDP create target failed: {e}')
        return None


async def _cdp_close_target(ws_url: str, target_id: str) -> bool:
    """Close a target (tab) via CDP."""
    import websockets
    try:
        async with websockets.connect(ws_url, ping_interval=None) as ws:
            await ws.send(json.dumps({
                'id': 1,
                'method': 'Target.closeTarget',
                'params': {'targetId': target_id}
            }))
            resp = await asyncio.wait_for(ws.recv(), timeout=5.0)
            data = json.loads(resp)
            return data.get('result', {}).get('success', False)
    except Exception as e:
        logger.error(f'CDP close target failed: {e}')
        return False


# ─── WebSocket URL Resolution ──────────────────────────────────────────────────

def _resolve_cdp_ws_url(port: int = CDP_PORT) -> str:
    """
    Get the CDP WebSocket debugger URL from Chrome's JSON endpoint.
    Returns ws:// URL ready for Playwright connectOverCDP.
    
    Strategy:
    1. Try /json/version → browser-level WS URL (always works)
    2. Fallback: construct ws://host:port/devtools/browser/<uuid>
    """
    import urllib.request

    # Chrome's JSON version endpoint — gives browser-level WS URL
    json_url = f'http://{CDP_HOST}:{port}/json/version'

    try:
        with urllib.request.urlopen(json_url, timeout=5) as resp:
            data = json.loads(resp.read())
            ws_url = data.get('webSocketDebuggerUrl')
            if ws_url:
                logger.info(f'CDP WS URL resolved: {ws_url}')
                return ws_url
    except Exception as e:
        logger.warning(f'Could not fetch /json/version: {e}')

    # Fallback: construct browser-level WS URL manually
    # Chrome creates a fixed browser target ID on startup
    fallback = f'ws://{CDP_HOST}:{port}/devtools/browser'
    logger.info(f'CDP WS URL fallback: {fallback}')
    return fallback


# ─── CDP Browser Connection (low-level) ──────────────────────────────────────

async def _get_cdp_browser_ws_url(port: int = CDP_PORT) -> str:
    """Get the browser-level CDP WebSocket URL (for Target domain commands)."""
    import urllib.request

    json_url = f'http://{CDP_HOST}:{port}/json/version'
    try:
        with urllib.request.urlopen(json_url, timeout=5) as resp:
            data = json.loads(resp.read())
            return data.get('webSocketDebuggerUrl', f'ws://{CDP_HOST}:{port}')
    except Exception:
        return f'ws://{CDP_HOST}:{port}'


# ─── Main BrowserDaemon Class ─────────────────────────────────────────────────

class BrowserDaemon:
    """
    ILMA Browser Daemon — Connects to standalone Chrome via Playwright CDP.

    Lifecycle:
    1. ensure_running() — Launch Chrome if not already running (idempotent)
    2. connect() — Playwright connectOverCDP to existing Chrome
    3. new_tab() / close_tab() — manage tabs
    4. disconnect() — disconnect Playwright, Chrome stays alive
    5. shutdown(kill_chrome=False) — disconnect, Chrome stays alive for next session
       shutdown(kill_chrome=True) — kill Chrome completely

    Key behavior:
    - Chrome is launched ONCE and runs forever until kill_chrome=True
    - ILMA dapat connect/disconnect berkali-kali tanpa mempengaruhi Chrome
    - Tab yang ILMA buka = ILMA tanggung jawab menutup
    - Browser tetap hidup bahkan setelah ILMA restart
    """

    def __init__(
        self,
        profile: Optional[Path] = None,
        chrome_path: Optional[str] = None,
        port: int = CDP_PORT,
    ):
        self.profile = profile or LOCKED_BROWSER_PROFILE
        self.chrome_path = chrome_path or CHROME_PATH
        self.port = port
        self.host = CDP_HOST

        # Playwright objects
        self._playwright = None
        self._browser = None
        self._context = None  # Persistent context

        # State
        self._connected = False
        self._owns_chrome = False  # True only if WE launched Chrome
        self._chrome_pid: Optional[int] = None

        # Tab tracking: page_id -> playwright Page
        self._pages: Dict[str, Any] = {}
        self._next_page_id = 1

        # CDP endpoint for low-level ops
        self._cdp_ws_url: Optional[str] = None

        logger.info(f'BrowserDaemon init: profile={self.profile}, port={self.port}')

    # ─── Properties ────────────────────────────────────────────────────────────

    @property
    def is_connected(self) -> bool:
        return self._connected and self._browser is not None

    @property
    def is_chrome_running(self) -> bool:
        return _is_port_open(self.host, self.port)

    @property
    def tracked_tab_count(self) -> int:
        return len(self._pages)

    # ─── Chrome Lifecycle ───────────────────────────────────────────────────────

    def ensure_running(self) -> 'BrowserDaemon':
        """
        Ensure Chrome is running. Idempotent.
        - If Chrome already running → do nothing, don't claim ownership
        - If Chrome not running → launch it, claim ownership
        """
        proc = _ensure_chrome_running()
        if proc is None:
            # Chrome already running (external) — we don't own it
            self._owns_chrome = False
            logger.info('Connected to existing Chrome (not owned)')
        else:
            # We launched it
            self._owns_chrome = True
            self._chrome_pid = proc.pid
            logger.info(f'We own Chrome, PID={self._chrome_pid}')

        # Wait for CDP
        if not _wait_for_cdp_ready(self.host, self.port):
            raise RuntimeError(f'CDP port {self.port} not ready')

        return self

    # ─── Playwright Connection ─────────────────────────────────────────────────

    async def connect(self) -> 'BrowserDaemon':
        """
        Connect to Chrome via Playwright connectOverCDP.
        Can be called multiple times — idempotent.
        """
        if self._connected and self._browser:
            logger.info('Already connected')
            return self

        # Resolve WebSocket URL
        ws_url = _resolve_cdp_ws_url(self.port)
        self._cdp_ws_url = ws_url
        logger.info(f'Connecting to Chrome CDP: {ws_url}')

        # Import playwright
        from playwright.async_api import async_playwright

        p = await async_playwright().start()

        try:
            # Connect via CDP
            browser = await p.chromium.connect_over_cdp(ws_url)
            self._playwright = p
            self._browser = browser

            # Create a persistent context
            self._context = await browser.new_context(
                no_viewport=False,
            )

            # Handle disconnect events
            browser.on('disconnect', self._on_browser_disconnect)

            self._connected = True
            logger.info('Connected to Chrome via CDP (Playwright)')
            return self

        except Exception as e:
            logger.error(f'CDP connect failed: {e}')
            await p.stop()
            raise

    def _on_browser_disconnect(self) -> None:
        """Called when browser disconnects."""
        logger.warning('Browser disconnected')
        self._connected = False
        self._playwright = None
        self._browser = None
        self._context = None
        self._pages.clear()

    async def disconnect(self) -> None:
        """
        Disconnect Playwright from Chrome. Chrome stays alive.
        """
        if not self._connected:
            return

        logger.info('Disconnecting Playwright from Chrome (browser stays alive)')

        # Close tracked pages
        for page_id, page in list(self._pages.items()):
            try:
                if not page.is_closed():
                    await page.close()
            except Exception:
                pass
        self._pages.clear()

        # Close context
        if self._context:
            try:
                await self._context.close()
            except Exception:
                pass
            self._context = None

        # Disconnect browser
        if self._browser:
            try:
                await self._browser.disconnect()
            except Exception:
                pass
            self._browser = None

        # Stop playwright
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None

        self._connected = False
        logger.info('Disconnected. Chrome still running.')

    # ─── Tab Management ────────────────────────────────────────────────────────

    async def new_tab(self, url: str = 'about:blank') -> Any:
        """
        Create a new tab/page. Returns Playwright Page object.
        Tab is tracked — close_tab() or shutdown(close_tabs=True) will close it.
        """
        if not self.is_connected:
            raise RuntimeError('Not connected. Call connect() first.')

        page_id = f'page_{self._next_page_id}'
        self._next_page_id += 1

        page = await self._context.new_page()
        self._pages[page_id] = page

        if url != 'about:blank':
            await page.goto(url, wait_until='domcontentloaded')

        logger.info(f'New tab created: {page_id} → {url}')
        return page

    async def close_tab(self, page_or_id: Any) -> bool:
        """
        Close a tracked tab. Accepts Page object or page_id string.
        """
        page_id = None
        page = None

        if isinstance(page_or_id, str):
            page_id = page_or_id
            page = self._pages.get(page_id)
        else:
            page = page_or_id
            # Find by page object
            for pid, p in list(self._pages.items()):
                if p == page:
                    page_id = pid
                    break

        if page is None:
            logger.warning(f'Tab not found: {page_or_id}')
            return False

        try:
            if not page.is_closed():
                await page.close()
            if page_id and page_id in self._pages:
                del self._pages[page_id]
            logger.info(f'Tab closed: {page_id or "unknown"}')
            return True
        except Exception as e:
            logger.error(f'Close tab failed: {e}')
            return False

    async def close_all_tabs(self) -> None:
        """Close all tracked tabs."""
        for page_id, page in list(self._pages.items()):
            try:
                if not page.is_closed():
                    await page.close()
            except Exception:
                pass
        self._pages.clear()
        logger.info('All tracked tabs closed')

    async def get_current_tabs(self) -> List[str]:
        """List tracked tab IDs."""
        return list(self._pages.keys())

    # ─── CDP Low-Level Ops ─────────────────────────────────────────────────────

    async def cdp_list_targets(self) -> List[Dict]:
        """List all browser targets via CDP."""
        ws_url = await _get_cdp_browser_ws_url(self.port)
        return await _cdp_targets_list(ws_url)

    async def cdp_create_tab(self, url: str = 'about:blank') -> Optional[str]:
        """Create a new browser tab via CDP Target domain (no Playwright)."""
        ws_url = await _get_cdp_browser_ws_url(self.port)
        return await _cdp_create_target(ws_url, url)

    async def cdp_close_tab(self, target_id: str) -> bool:
        """Close a browser tab via CDP Target domain."""
        ws_url = await _get_cdp_browser_ws_url(self.port)
        return await _cdp_close_target(ws_url, target_id)

    # ─── Full Shutdown ────────────────────────────────────────────────────────

    async def shutdown(self, kill_chrome: bool = False, close_tabs: bool = True) -> None:
        """
        Shutdown browser session.

        kill_chrome=False (default):
            Disconnect Playwright, Chrome stays alive for next session.
            This is the DEFAULT — browser survives ILMA restarts.

        kill_chrome=True:
            Kill Chrome process completely.

        close_tabs=True:
            Close all tabs created by ILMA before disconnecting.
        """
        logger.info(f'Shutdown: kill_chrome={kill_chrome}, close_tabs={close_tabs}')

        # Close tracked tabs
        if close_tabs:
            await self.close_all_tabs()

        # Disconnect Playwright
        await self.disconnect()

        # Kill Chrome if requested
        if kill_chrome:
            await self._kill_chrome_process()

    async def _kill_chrome_process(self) -> None:
        """Kill Chrome process."""
        if self._owns_chrome and self._chrome_pid:
            logger.info(f'Killing Chrome PID={self._chrome_pid}')
            _kill_chrome(self._chrome_pid)
            self._chrome_pid = None
            self._owns_chrome = False
        elif not self._owns_chrome:
            # Find and kill Chrome on our port
            pid = _get_chrome_pid_from_port(self.port)
            if pid:
                logger.info(f'Killing Chrome PID={pid}')
                _kill_chrome(pid)

    # ─── Context Manager ───────────────────────────────────────────────────────

    async def __aenter__(self) -> 'BrowserDaemon':
        self.ensure_running()
        await self.connect()
        return self

    async def __aexit__(self, *args) -> None:
        await self.shutdown(kill_chrome=False)

    # ─── Class-Level Methods ──────────────────────────────────────────────────

    @classmethod
    def quick_start(cls) -> 'BrowserDaemon':
        """
        Quick start: ensure Chrome running + connect in one call.
        Synchronous helper.
        """
        daemon = cls()
        daemon.ensure_running()
        return daemon

    @classmethod
    async def create(cls) -> 'BrowserDaemon':
        """Async factory: ensure Chrome running + connect."""
        daemon = cls()
        daemon.ensure_running()
        await daemon.connect()
        return daemon


# ─── CLI Entry Point ──────────────────────────────────────────────────────────

def main():
    """CLI for daemon management."""
    import argparse
    parser = argparse.ArgumentParser(description='ILMA Browser Daemon')
    parser.add_argument('--start', action='store_true', help='Start Chrome and keep alive')
    parser.add_argument('--stop', action='store_true', help='Stop Chrome completely')
    parser.add_argument('--status', action='store_true', help='Show browser status')
    parser.add_argument('--demo', action='store_true', help='Run demo: start → use → stay alive')
    args = parser.parse_args()

    if args.status:
        running = _is_port_open(CDP_HOST, CDP_PORT)
        if running:
            pid = _get_chrome_pid_from_port(CDP_PORT)
            print(f'Chrome: RUNNING (PID={pid}, port={CDP_PORT})')
        else:
            print(f'Chrome: STOPPED (port={CDP_PORT} free)')
        return

    if args.stop:
        pid = _get_chrome_pid_from_port(CDP_PORT)
        if pid:
            _kill_chrome(pid)
            print(f'Chrome PID={pid} killed')
        else:
            print('No Chrome found on port 9222')
        return

    if args.start or args.demo:
        print('Starting ILMA Browser...')
        daemon = BrowserDaemon()
        daemon.ensure_running()
        print(f'Chrome running on port {CDP_PORT}')

        if args.demo:
            async def demo():
                await daemon.connect()
                page = await daemon.new_tab('https://example.com')
                print(f'Demo tab title: {await page.title()}')
                print(f'Tracked tabs: {daemon.tracked_tab_count}')
                print('Keeping Chrome alive — no shutdown() called')
                print('Chrome will survive this process exit.')

            asyncio.run(demo())

        return

    parser.print_help()


if __name__ == '__main__':
    main()
