#!/usr/bin/env python3
"""
ILMA Codex Auto-Refresh + Auto-Reauth System v1.0
===================================================
Detects expired/invalid Codex tokens and automatically:
  1. Try refresh_token-based renewal (preferred)
  2. Fallback to full OAuth browser re-authentication
  3. Update all token stores
  4. Verify and report

Usage:
    python3 ilma_codex_auto_refresh.py          # Auto-detect + act
    python3 ilma_codex_auto_refresh.py --check   # Check status only
    python3 ilma_codex_auto_refresh.py --force   # Force full re-auth
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import time
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

# ── Paths ────────────────────────────────────────────────────────────────────
SCRIPTS_DIR = Path("/root/.hermes/profiles/ilma/scripts")
TOKEN_STORE_CCDIR = Path("/root/.hermes/profiles/ilma/home/.codex/auth.json")
TOKEN_STORE_HERMES = Path("/root/.hermes/profiles/ilma/auth.json")
BROWSER_PROFILE = Path("/root/user-data/lokah2150")
CODEX_CLI = "/usr/bin/codex"

# OAuth config
CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
TOKEN_URL = "https://auth.openai.com/o/token"
AUTH_BASE = "https://auth.openai.com"
REDIRECT_URI = "http://localhost:1455/auth/callback"

# Account
EMAIL = "lokah2150@gmail.com"
PASSWORD = __import__("os").environ.get("ILMA_CODEX_PASSWORD", "")

# ── Logging ──────────────────────────────────────────────────────────────────
LOG_FILE = Path("/root/.hermes/profiles/ilma/logs/codex_auto_refresh.log")

def log(msg: str, level: str = "INFO"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{level}] {msg}"
    print(line)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


# ── Token Management ──────────────────────────────────────────────────────────

def decode_jwt_payload(token: str) -> dict:
    """Decode JWT payload (base64url)."""
    try:
        parts = token.split('.')
        if len(parts) < 2:
            return {}
        payload = parts[1]
        padding = 4 - len(payload) % 4
        if padding < 4:
            payload += '=' * padding
        return json.loads(base64.b64decode(payload))
    except Exception:
        return {}


def get_token_info(path: Path) -> dict:
    """Get token info from codex CLI auth file."""
    try:
        with open(path) as f:
            d = json.load(f)
        if 'tokens' in d:
            tokens = d['tokens']
        elif 'access_token' in d:
            tokens = {'access_token': d['access_token'], 'refresh_token': d.get('refresh_token', '')}
        else:
            return {}
        
        access = tokens.get('access_token', '')
        refresh = tokens.get('refresh_token', '')
        
        info = {'access': access, 'refresh': refresh, 'source': str(path)}
        
        if access:
            claims = decode_jwt_payload(access)
            info['exp'] = claims.get('exp', 0)
            info['scopes'] = claims.get('scp', claims.get('scope', []))
            info['exp_datetime'] = datetime.fromtimestamp(claims['exp']) if claims.get('exp') else None
            info['is_expired'] = claims.get('exp', 0) < time.time()
        
        return info
    except Exception as e:
        return {'error': str(e)}


def check_token_status() -> Tuple[str, str, dict]:
    """
    Check token status across all stores.
    Returns: (status, summary, details)
    Status: 'valid' | 'expired' | 'missing' | 'refresh_needed' | 'reauth_needed'
    """
    details = {}
    
    # Check Codex CLI auth
    if TOKEN_STORE_CCDIR.exists():
        info = get_token_info(TOKEN_STORE_CCDIR)
        details['ccdir'] = info
    else:
        details['ccdir'] = {'error': 'File not found'}

    # Determine overall status
    ccinfo = details.get('ccdir', {})
    if ccinfo.get('error') == 'File not found':
        return 'missing', "No tokens found anywhere", details
    
    if ccinfo.get('is_expired', True):
        # Token expired — check if refresh token available
        if ccinfo.get('refresh'):
            return 'refresh_needed', f"Token expired, refresh available", details
        else:
            return 'reauth_needed', f"Token expired, no refresh token", details
    
    # Check via API
    access = ccinfo.get('access', '')
    if access:
        try:
            import requests
            resp = requests.get(
                "https://api.openai.com/v1/me",
                headers={"Authorization": f"Bearer {access}"},
                timeout=10,
            )
            if resp.status_code == 200:
                return 'valid', "Token valid, API accessible", details
            elif resp.status_code == 401:
                if ccinfo.get('refresh'):
                    return 'refresh_needed', "API 401, refresh available", details
                else:
                    return 'reauth_needed', "API 401, reauth needed", details
            else:
                return 'unknown', f"API status: {resp.status_code}", details
        except Exception as e:
            return 'error', f"API check failed: {e}", details
    
    return 'unknown', "No access token found", details


# ── Token Refresh (via OAuth refresh_token) ────────────────────────────────────

def refresh_tokens(refresh_token: str) -> Optional[dict]:
    """Use refresh_token to get new access_token via OAuth token endpoint."""
    import requests
    
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": CLIENT_ID,
    }
    
    try:
        resp = requests.post(TOKEN_URL, data=data, timeout=30)
        if resp.status_code == 200:
            return resp.json()
        else:
            log(f"Refresh failed: {resp.status_code} {resp.text[:200]}", "ERROR")
            return None
    except Exception as e:
        log(f"Refresh error: {e}", "ERROR")
        return None


def update_token_stores(new_tokens: dict, mode: str = "refresh"):
    """Update all token stores with new tokens."""
    access = new_tokens.get('access_token', '')
    refresh = new_tokens.get('refresh_token', '') or new_tokens.get('refresh_token')
    expires_in = new_tokens.get('expires_in', 2592000)  # ~30 days default
    scope = new_tokens.get('scope', 'openid profile email offline_access api.connectors.read api.connectors.invoke')
    
    expires_at = int(time.time()) + expires_in
    exp_datetime = datetime.fromtimestamp(expires_at).isoformat()
    
    log(f"New token expires at: {exp_datetime}")

    log("Token refresh complete (ccdir + hermes auth.json only)", "OK")

    # 2. Update Codex CLI auth
    if TOKEN_STORE_CCDIR.exists():
        with open(TOKEN_STORE_CCDIR) as f:
            d = json.load(f)
        d['tokens']['access_token'] = access
        if refresh:
            d['tokens']['refresh_token'] = refresh
        d['last_refresh'] = datetime.now(timezone.utc).isoformat()
        with open(TOKEN_STORE_CCDIR, 'w') as f:
            json.dump(d, f, indent=2)
        log("Updated Codex CLI auth", "OK")

    # 3. Update Hermes auth.json
    if TOKEN_STORE_HERMES.exists():
        with open(TOKEN_STORE_HERMES) as f:
            h = json.load(f)
        if 'providers' not in h:
            h['providers'] = {}
        h['providers']['openai-codex'] = {
            'tokens': {
                'access_token': access,
                'refresh_token': refresh,
            },
            'last_refresh': datetime.now(timezone.utc).isoformat(),
            'auth_mode': 'chatgpt',
        }
        if 'credential_pool' not in h:
            h['credential_pool'] = {}
        h['credential_pool']['openai-codex'] = access
        with open(TOKEN_STORE_HERMES, 'w') as f:
            json.dump(h, f, indent=2)
        log("Updated Hermes auth.json", "OK")

    return {
        'access_token': access,
        'refresh_token': refresh,
        'expires_at': expires_at,
        'scope': scope,
        'email': EMAIL,
        'provider': 'openai-codex',
        'model': 'gpt-5.5',
        'last_refresh': datetime.now(timezone.utc).isoformat(),
    }


# ── Full OAuth Re-authentication ─────────────────────────────────────────────

def run_oauth_flow() -> bool:
    """
    Run full OAuth browser flow to re-authenticate.
    Returns True on success.
    """
    sys.path.insert(0, str(SCRIPTS_DIR))
    
    try:
        from playwright.sync_api import sync_playwright
        from playwright_stealth import Stealth
    except ImportError:
        log("playwright not available — cannot re-auth", "ERROR")
        return False
    
    stealth = Stealth(
        chrome_app=True, chrome_csi=True, chrome_load_times=True, chrome_runtime=True,
        hairline=True, iframe_content_window=True, media_codecs=True,
        navigator_hardware_concurrency=True, navigator_languages=True,
        navigator_permissions=True, navigator_platform=True, navigator_plugins=True,
        navigator_user_agent=True, navigator_user_agent_data=True,
        navigator_vendor=True, navigator_webdriver=True,
        error_prototype=True, sec_ch_ua=True, webgl_vendor=True,
    )
    
    oauth_url = None
    oauth_url_captured = None
    
    def capture_url(line):
        nonlocal oauth_url_captured
        match = re.search(r'https://auth\.openai\.com/oauth/authorize[^\s]+', line)
        if match:
            oauth_url_captured = match.group(0)
    
    log("Starting codex login subprocess...")
    proc = subprocess.Popen(
        ["codex", "login"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
        cwd="/root/.hermes/profiles/ilma"
    )
    
    def reader():
        for line in proc.stdout:
            print(f"[codex] {line.rstrip()}")
            capture_url(line)
    
    threading.Thread(target=reader, daemon=True).start()
    
    for _ in range(20):
        if oauth_url_captured:
            break
        time.sleep(1)
    else:
        log("Timeout waiting for OAuth URL", "ERROR")
        proc.terminate()
        return False
    
    oauth_url = oauth_url_captured
    time.sleep(2)
    log(f"Got OAuth URL: {oauth_url[:80]}...")
    
    def safe_text(page, timeout=3000):
        try:
            return page.inner_text("body", timeout=timeout)[:700]
        except:
            return ""
    
    def safe_url(page):
        try:
            return page.url
        except:
            return "unknown"
    
    try:
        with sync_playwright() as p:
            stealth.hook_playwright_context(p)
            
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(BROWSER_PROFILE),
                headless=False,
                args=[
                    '--no-sandbox', '--disable-dev-shm-usage', '--disable-setuid-sandbox',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-features=IsolateOrigins,site-per-process',
                    '--disable-web-security', '--ignore-certificate-errors',
                    '--allow-running-insecure-content',
                    '--password-store=basic', '--use-mock-keychain',
                    '--enable-features=NetworkService,NetworkServiceInProcess',
                    '--disable-background-networking', '--disable-background-timer-throttling',
                    '--disable-backgrounding-occluded-windows', '--disable-breakpad',
                    '--disable-client-side-phishing-detection', '--disable-default-apps',
                    '--disable-hang-monitor', '--disable-ipc-flooding-protection',
                    '--disable-popup-blocking', '--disable-prompt-on-repost',
                    '--disable-renderer-backgrounding', '--force-color-profile=srgb',
                    '--metrics-recording-only', '--no-first-run', '--safebrowsing-disable-auto-update',
                ],
                ignore_https_errors=True,
            )
            
            page = context.pages[0] if context.pages else context.new_page()
            log("Browser launched")
            
            page.goto(oauth_url, timeout=30000, wait_until="domcontentloaded")
            time.sleep(5)
            log(f"URL: {safe_url(page)}")
            
            for _ in range(12):
                url = safe_url(page)
                body = safe_text(page)[:700]
                
                if "localhost:1455" in url:
                    log("✅ Callback received! OAuth SUCCESS!", "OK")
                    break
                
                if "choose-an-account" in url or "Pilih akun" in body:
                    btn = page.query_selector('button:has-text("lokah2150@gmail.com")')
                    if btn and btn.is_visible():
                        btn.click()
                        time.sleep(4)
                    continue
                
                email_input = page.query_selector('input[type="email"], input[name="email"], input[name="identifier"]')
                if email_input:
                    email_input.click()
                    time.sleep(0.5)
                    email_input.fill(EMAIL)
                    time.sleep(1)
                    btn = page.query_selector('button:has-text("Lanjutkan"), button:has-text("Next"), button[type="submit"]')
                    if btn:
                        btn.click()
                    time.sleep(5)
                    continue
                
                if "google.com" in url:
                    btn_next = page.query_selector('button:has-text("Berikutnya")')
                    if btn_next and btn_next.is_visible():
                        btn_next.click()
                        time.sleep(5)
                    continue
                
                if "password" in url.lower() or "Masukkan sandi" in body[:300]:
                    try:
                        pw = page.wait_for_selector('input[type="password"]:visible', timeout=8000)
                        pw.click()
                        time.sleep(0.5)
                        pw.fill(PASSWORD)
                        time.sleep(1)
                        page.keyboard.press("Enter")
                        time.sleep(8)
                    except Exception as e:
                        log(f"Password error: {e}", "WARN")
                    continue
                
                if any(x in body.lower() for x in ['verif', 'xiaomi', 'itel', 'notifikasi', 'google mencoba']):
                    log("⏳ 2FA — waiting 60s...", "WAIT")
                    for i in range(60):
                        time.sleep(1)
                        url_now = safe_url(page)
                        if "localhost:1455" in url_now or "consent" in url_now.lower():
                            break
                        if i % 20 == 0:
                            log(f"  [{i+1}s] {url_now[:60]}", "WAIT")
                    time.sleep(2)
                    continue
                
                if any(x in url.lower() + body.lower() for x in ['consent', 'workspace', 'pilih workspace']):
                    time.sleep(2)
                    for sel in ['button:has-text("Lanjutkan")', 'button:has-text("Continue")',
                                'button:has-text("Authorize")', 'button:has-text("Ya")']:
                        btn = page.query_selector(sel)
                        if btn and btn.is_visible():
                            btn.click()
                            time.sleep(4)
                            break
                    continue
                
                break
            
            for i in range(90):
                time.sleep(1)
                url = safe_url(page)
                if "localhost:1455" in url:
                    log(f"✅ Callback at {i+1}s!", "OK")
                    break
                if "error" in url:
                    log(f"❌ Error: {url}", "ERROR")
                    break
                if i % 20 == 0:
                    log(f"[{i+1}s] {url[:80]}")
            
            try:
                page.screenshot(path="/tmp/codex_auto_refresh_result.png", full_page=True)
            except:
                pass
    
    finally:
        proc.terminate()
    
    # Extract tokens
    if TOKEN_STORE_CCDIR.exists():
        with open(TOKEN_STORE_CCDIR) as f:
            d = json.load(f)
        tokens = d.get('tokens', {})
        if tokens.get('access_token'):
            update_token_stores(tokens, mode="oauth")
            return True
    
    return False


# ── Verification ─────────────────────────────────────────────────────────────

def verify_tokens() -> bool:
    """Verify tokens work via Claude Code wrapper."""
    try:
        import subprocess
        result = subprocess.run(
            ["/root/.hermes/profiles/ilma/scripts/ilma_claude_wrapper.sh", "auth", "status"],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0 and '"loggedIn": true' in result.stdout:
            log("Claude Code auth OK (via wrapper)", "OK")
            return True
        log(f"Claude auth failed: {result.stdout[:200]}", "ERROR")
        return False
    except Exception as e:
        log(f"Token verify exception: {e}", "ERROR")
        return False


def verify_codex_cli() -> bool:
    """Verify via codex exec."""
    try:
        result = subprocess.run(
            ["codex", "exec", "echo OK"],
            capture_output=True, text=True,
            cwd="/root/.hermes/profiles/ilma",
            timeout=30,
        )
        if result.returncode == 0 and "OK" in result.stdout:
            log("Codex CLI: OK", "OK")
            return True
        else:
            log(f"Codex CLI failed: {result.stderr[:200]}", "ERROR")
            return False
    except Exception as e:
        log(f"Codex CLI error: {e}", "ERROR")
        return False


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="ILMA Codex Auto-Refresh")
    parser.add_argument("--check", action="store_true", help="Check status only")
    parser.add_argument("--force", action="store_true", help="Force full re-auth")
    args = parser.parse_args()
    
    log("=" * 60)
    log("ILMA Codex Auto-Refresh Starting")
    log("=" * 60)
    
    # Step 1: Check token status
    status, summary, details = check_token_status()
    log(f"Status: {status} — {summary}")
    
    if args.check:
        print(json.dumps(details, indent=2, default=str))
        return
    
    action_taken = None
    
    if args.force or status in ('reauth_needed', 'missing'):
        log("Action: Full OAuth re-authentication", "ACTION")
        success = run_oauth_flow()
        action_taken = "reauth" if success else "reauth_failed"
    
    elif status == 'refresh_needed':
        log("Action: Token refresh via refresh_token", "ACTION")
        ccinfo = details.get('ccdir', {})
        refresh = ccinfo.get('refresh', '')
        if refresh:
            new_tokens = refresh_tokens(refresh)
            if new_tokens:
                update_token_stores(new_tokens, mode="refresh")
                action_taken = "refresh"
            else:
                log("Refresh failed — falling back to re-auth", "WARN")
                success = run_oauth_flow()
                action_taken = "reauth" if success else "refresh_failed"
        else:
            log("No refresh token available — re-auth required", "WARN")
            success = run_oauth_flow()
            action_taken = "reauth" if success else "reauth_failed"
    
    elif status == 'valid':
        log("No action needed — tokens valid", "OK")
    
    else:
        log(f"Unknown status '{status}' — forcing check", "WARN")
        status2, summary2, _ = check_token_status()
        if status2 in ('refresh_needed', 'reauth_needed'):
            log("Re-checking...", "WARN")
    
    # Verify
    if action_taken and action_taken != "reauth_failed" and action_taken != "refresh_failed":
        log("Verifying tokens...", "VERIFY")
        auth_ok = verify_tokens()
        cli_ok = verify_codex_cli()

        if auth_ok and cli_ok:
            log("✅ ALL VERIFIED — Codex ready!", "OK")
        else:
            log(f"⚠️ Partial verify — cli:{cli_ok}", "WARN")
    
    log("Done", "OK")


if __name__ == "__main__":
    main()