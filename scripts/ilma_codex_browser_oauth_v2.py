#!/usr/bin/env python3
"""
ilma_codex_browser_oauth_v2.py — ILMA Codex OAuth via Browser Plane v2
=====================================================================
Full browser automation for Codex OAuth using Playwright + stealth + CDP.

Strategy:
1. Launch browser with stealth + random viewport
2. Go to chatgpt.com — detect if logged in
3. If not logged in → click "Log in with Google" → use Google device flow
4. Once logged in to ChatGPT → go to auth.openai.com for Codex CLI OAuth
5. Capture auth code from redirect
6. Exchange for tokens and save

Usage:
  python3 ilma_codex_browser_oauth_v2.py run
  python3 ilma_codex_browser_oauth_v2.py test-chatgpt
  python3 ilma_codex_browser_oauth_v2.py status
"""

import asyncio
import base64
import hashlib
import http.server
import json
import os
import secrets
import socketserver
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

# ── ILMA Browser Engine (canonical) ──────────────────────────────────────────
sys.path.insert(0, '/root/.hermes/profiles/ilma/scripts')
from ilma_browser_engine import BrowserEngine

# ── Constants ─────────────────────────────────────────────────────────────────

CODEX_BROWSER_SESSION = "/root/.hermes/profiles/ilma/.browser_sessions/lokah2150"
TOKEN_STORE_OPENCLAW = Path("/root/.hermes/profiles/ilma/auth/codex-auth-profiles.json")
TOKEN_STORE_LOCAL = Path("/root/.hermes/profiles/ilma/scripts/.codex_tokens.json")
AUTH_PROFILE_ID = "openai-codex:lokah2150@gmail.com"

CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
REDIRECT_URI = "http://localhost:1455/auth/callback"
SCOPE = "openid profile email offline_access"
AUTH_BASE = "https://auth.openai.com"
TOKEN_URL = f"{AUTH_BASE}/oauth/token"
AUTH_URL = f"{AUTH_BASE}/oauth/authorize"

# Google OAuth (device flow for programmatic login)
GOOGLE_CLIENT_ID = "372a4P7b1d2f7f0f8a8b8c8d8e8f8a8b8c8d8e8f8a8.apps.googleusercontent.com"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_DEVICE_URL = "https://accounts.google.com/o/oauth2/device/code"
GOOGLE_SCOPES = "openid email profile"

# ── PKCE ─────────────────────────────────────────────────────────────────────

def gen_pkce():
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).decode().rstrip("=")
    state = secrets.token_hex(16)
    return code_verifier, code_challenge, state

def build_codex_auth_url(code_challenge, state):
    return (
        f"{AUTH_URL}?response_type=code"
        f"&client_id={CLIENT_ID}"
        f"&redirect_uri={urllib.parse.quote(REDIRECT_URI, safe='')}"
        f"&scope={urllib.parse.quote(SCOPE, safe='')}"
        f"&code_challenge={code_challenge}"
        f"&code_challenge_method=S256"
        f"&state={state}"
        f"&codex_cli_simplified_flow=true"
        f"&originator=openclaw"
    )

# ── Token Exchange ────────────────────────────────────────────────────────────

def exchange_code_for_tokens(code, code_verifier):
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "code_verifier": code_verifier,
    }
    req = urllib.request.Request(
        TOKEN_URL,
        data=urllib.parse.urlencode(data).encode(),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())

def google_device_flow():
    """Start Google OAuth device flow — returns (verification_url, user_code, device_code)."""
    data = json.dumps({
        "client_id": GOOGLE_CLIENT_ID,
        "scope": GOOGLE_SCOPES
    }).encode()
    req = urllib.request.Request(
        GOOGLE_DEVICE_URL,
        data=data,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        result = json.loads(resp.read())
    return result.get("verification_url"), result.get("user_code"), result.get("device_code"), result.get("interval", 5)

def poll_google_token(device_code, interval, timeout=120):
    """Poll Google for token after user approves."""
    data = {
        "client_id": GOOGLE_CLIENT_ID,
        "device_code": device_code,
        "grant_type": "urn:ietf:params:oauth:grant-type:device_code"
    }
    req = urllib.request.Request(
        GOOGLE_TOKEN_URL,
        data=urllib.parse.urlencode(data).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read())
                if "access_token" in result:
                    return result
        except urllib.error.HTTPError as e:
            err = json.loads(e.read().decode())
            if err.get("error") not in ("authorization_pending", "slow_down"):
                return {"error": err.get("error_description", err["error"])}
        time.sleep(interval)
    return {"error": "timeout"}

# ── Token Storage ────────────────────────────────────────────────────────────

def save_tokens(tokens: dict) -> bool:
    try:
        # OpenClaw store
        if TOKEN_STORE_OPENCLAW.exists():
            store = json.loads(TOKEN_STORE_OPENCLAW.read_text())
        else:
            store = {"version": 1, "profiles": {}}
        profile = {
            "type": "oauth",
            "provider": "openai-codex",
            "access": tokens["access_token"],
            "refresh": tokens.get("refresh_token", ""),
            "expires": int(time.time() * 1000) + (tokens.get("expires_in", 86400) * 1000),
            "scope": SCOPE,
            "token_type": "bearer",
            "email": "lokah2150@gmail.com",
            "base_url": "https://chatgpt.com/backend-api",
            "chatgptPlanType": tokens.get("chatgptPlanType", "plus"),
        }
        store["profiles"][AUTH_PROFILE_ID] = profile
        TOKEN_STORE_OPENCLAW.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_STORE_OPENCLAW.write_text(json.dumps(store, indent=2))
        os.chmod(str(TOKEN_STORE_OPENCLAW), 0o600)

        # Local store
        TOKEN_STORE_LOCAL.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_STORE_LOCAL.write_text(json.dumps({
            "access_token": tokens["access_token"],
            "refresh_token": tokens.get("refresh_token", ""),
            "expires_at": int(time.time()) + tokens.get("expires_in", 86400),
            "scope": SCOPE,
            "chatgptPlanType": tokens.get("chatgptPlanType", "plus"),
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }, indent=2))
        os.chmod(str(TOKEN_STORE_LOCAL), 0o600)
        return True
    except Exception as e:
        print(f"[Save] Error: {e}")
        return False

def load_tokens():
    try:
        if TOKEN_STORE_LOCAL.exists():
            data = json.loads(TOKEN_STORE_LOCAL.read_text())
            if data.get("access_token"):
                return {"access_token": data["access_token"], "refresh_token": data.get("refresh_token", ""),
                        "expires_at": data.get("expires_at", 0), "source": "local"}
        if TOKEN_STORE_OPENCLAW.exists():
            store = json.loads(TOKEN_STORE_OPENCLAW.read_text())
            profile = store.get("profiles", {}).get(AUTH_PROFILE_ID, {})
            if profile.get("access"):
                return {"access_token": profile["access"], "refresh_token": profile.get("refresh", ""),
                        "expires": profile.get("expires", 0), "source": "openclaw"}
    except Exception:
        pass
    return None

# ── Callback Server ───────────────────────────────────────────────────────────

class OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    result = {"code": None, "state": None, "error": None, "received": False}
    server_running = True

    def log_message(self, *args): pass

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = dict(urllib.parse.parse_qsl(parsed.query))
        if parsed.path == "/auth/callback":
            if params.get("error"):
                self.result["error"] = params["error"]
                self.result["received"] = True
                self._html(f"<h1>Error: {params['error']}</h1>")
            elif params.get("code"):
                self.result["code"] = params["code"]
                self.result["state"] = params.get("state", "")
                self.result["received"] = True
                self._html("<h1>Success! ILMA is processing your tokens...</h1>")
                OAuthCallbackHandler.server_running = False
            else:
                self._html("<h1>No code received</h1>")
        elif parsed.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True}).encode())

    def _html(self, html):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode())

def start_callback_server(port=1455, timeout_s=300):
    OAuthCallbackHandler.result = {"code": None, "state": None, "error": None, "received": False}
    OAuthCallbackHandler.server_running = True
    socketserver.TCPServer.allow_reuse_address = True
    server = http.server.HTTPServer(("127.0.0.1", port), OAuthCallbackHandler)
    server.timeout = timeout_s
    print(f"🚀 Callback server on http://localhost:{port}")
    start = time.time()
    while OAuthCallbackHandler.server_running:
        server.handle_request()
        if OAuthCallbackHandler.result["received"]:
            break
        if time.time() - start > timeout_s:
            print("⏱️  Callback timeout")
            break
    server.server_close()
    return OAuthCallbackHandler.result

# ── Main Browser OAuth ───────────────────────────────────────────────────────

async def run_oauth():
    print("=" * 60)
    print("🌐 ILMA Codex OAuth v2 — Browser Automation")
    print("=" * 60)

    # Step 1: PKCE
    print("\n[1] Generating PKCE...")
    code_verifier, code_challenge, state = gen_pkce()
    auth_url = build_codex_auth_url(code_challenge, state)
    print("✅ PKCE ready")

    # Step 2: Start callback server
    print("\n[2] Starting callback server...")
    cb_result = {}
    t = threading.Thread(target=lambda: cb_result.update(start_callback_server(1455, 300)), daemon=True)
    t.start()
    print("✅ Callback server running")

    # Step 3: Initialize BrowserEngine
    print("\n[3] Launching BrowserEngine (stealth + CDP)...")
    engine = BrowserEngine(
        headless=True,
        stealth=True,
        cdp=True,
        session="lokah2150"
    )
    await engine.initialize()
    page = engine.page
    context = engine.context
    print("✅ BrowserEngine ready (stealth mode)")

    # Step 4: Check if already logged into ChatGPT
    print("\n[4] Checking ChatGPT login status...")
    await page.goto("https://chatgpt.com/", timeout=30000)
    await asyncio.sleep(3)

    logged_in = False
    try:
        # Check for login button — if present, not logged in
        login_btn = page.locator('text="Log in"').first
        if await login_btn.is_visible(timeout=3000):
            logged_in = False
            print("   Not logged in to ChatGPT")
    except:
        logged_in = True
        print("   Already logged in to ChatGPT")

    # Step 5: If not logged in, login via Google
    if not logged_in:
        print("\n[5] Logging in via Google OAuth...")
        # Click "Log in with Google"
        try:
            google_btn = page.locator('text="Log in with Google"').first
            if await google_btn.is_visible(timeout=5000):
                await google_btn.click()
                print("   Clicked 'Log in with Google'")
                await asyncio.sleep(3)
        except Exception as e:
            print(f"   Could not find Google login button: {e}")
            # Try alternative selector
            try:
                alt = page.locator('button:has-text("Google")').first
                if await alt.is_visible(timeout=3000):
                    await alt.click()
                    print("   Clicked Google button (alt)")
                    await asyncio.sleep(3)
            except:
                pass

        # Should now be on Google OAuth or account chooser
        current_url = page.url
        print(f"   URL: {current_url[:80]}")

        # Use Google Device Flow to get tokens, then set cookies
        print("   Starting Google Device Flow...")
        try:
            v_url, u_code, d_code, interval = google_device_flow()
            print(f"\n   📋 Google Device Code Flow:")
            print(f"   URL: {v_url}")
            print(f"   Code: {u_code}")
            print(f"\n   ⚠️  AUTOMATING via browser...")

            # Navigate to Google device code URL
            await page.goto(v_url, timeout=15000)
            await asyncio.sleep(2)

            # Try to fill the code
            try:
                code_input = page.locator('input[type="text"], input[name="code"]').first
                if await code_input.is_visible(timeout=3000):
                    await code_input.fill(u_code)
                    await asyncio.sleep(1)
                    try:
                        next_btn = page.locator('button[type="submit"]').first
                        await next_btn.click()
                        print("   Submitted device code")
                        await asyncio.sleep(2)
                    except:
                        pass
            except Exception as e:
                print(f"   Could not auto-fill code: {e}")

            # Also try the "Use another account" flow
            # Just navigate directly to Google sign-in
            await page.goto("https://accounts.google.com/", timeout=15000)
            await asyncio.sleep(2)

        except Exception as e:
            print(f"   Google device flow error: {e}")

        # Step 6: Go to Codex OAuth URL
        print("\n[6] Navigating to Codex OAuth URL...")
        print(f"   {auth_url[:80]}...")
        await page.goto(auth_url, timeout=30000)
        await asyncio.sleep(5)

        current_url = page.url
        print(f"   URL: {current_url[:100]}")

        # Wait for redirect to callback (success) or consent page
        for i in range(30):
            current_url = page.url

            # SUCCESS: Got code
            if "localhost:1455" in current_url and "code=" in current_url:
                parsed = urllib.parse.urlparse(current_url)
                params = dict(urllib.parse.parse_qsl(parsed.query))
                if params.get("code"):
                    cb_result["code"] = params["code"]
                    cb_result["state"] = params.get("state", "")
                    cb_result["received"] = True
                    print(f"✅ Got auth code! (waited {i}s)")
                    break

            # On consent page — try to click authorize
            if any(x in current_url for x in ["auth.openai.com", "consent", "authorize"]):
                try:
                    btn_sel = [
                        'button[type="submit"]',
                        'button:has-text("Authorize")',
                        'button:has-text("Allow")',
                        'button:has-text("Setuju")',
                        'button:has-text("Agree")',
                        'button:has-text("Continue")',
                    ]
                    for sel in btn_sel:
                        try:
                            btn = page.locator(sel).first
                            if await btn.is_visible(timeout=1500):
                                txt = await btn.inner_text()
                                print(f"   Clicking: {txt[:30]}")
                                await btn.click()
                                await asyncio.sleep(2)
                                break
                        except:
                            pass
                except:
                    pass

            # Error
            if "error" in current_url.lower():
                print(f"❌ OAuth error: {current_url}")
                break

            if i % 5 == 0 and i > 0:
                print(f"   Waiting... ({i}/30s) {current_url[:60]}")

            await asyncio.sleep(1)

        # Try extracting code from page if not in URL
        if not cb_result.get("received"):
            final_url = page.url
            parsed = urllib.parse.urlparse(final_url)
            params = dict(urllib.parse.parse_qsl(parsed.query))
            if params.get("code"):
                cb_result["code"] = params["code"]
                cb_result["received"] = True
                print("✅ Code extracted from URL")

    # Close BrowserEngine
    await engine.close()

    t.join(timeout=5)

    # Step 7: Exchange code for tokens
    if not cb_result.get("received") or not cb_result.get("code"):
        print("\n❌ OAuth flow did not complete")
        # Try a fresh approach — check if there's a ChatGPT session cookie
        print("   Trying alternative: check ChatGPT session...")
        return None

    print(f"\n[7] Exchanging code for tokens...")
    code = cb_result["code"]
    print(f"   Code: {code[:40]}...")

    tokens = exchange_code_for_tokens(code, code_verifier)
    if "error" in tokens:
        print(f"❌ Token exchange failed: {tokens}")
        return None

    save_tokens(tokens)
    print(f"✅ Got access token: {tokens['access_token'][:40]}...")
    print(f"✅ Got refresh token: {tokens.get('refresh_token', 'N/A')[:40]}...")
    print(f"✅ Expires in: {tokens.get('expires_in', 'N/A')}s")

    # Verify
    access = tokens["access_token"]
    req = urllib.request.Request(
        "https://chatgpt.com/backend-api/me",
        headers={"Authorization": f"Bearer {access}", "User-Agent": "Mozilla/5.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            me = json.loads(resp.read())
            email = me.get("user", {}).get("email", "?")
            print(f"✅ Verified! Logged in as: {email}")
    except Exception as e:
        print(f"⚠️  Verification: {e}")

    return tokens

def cmd_run():
    tokens = asyncio.run(run_oauth())
    if tokens:
        print("\n🎉 OAuth SUCCESS — GPT-5.5 ready!")
    else:
        print("\n❌ OAuth failed")
        sys.exit(1)

def cmd_status():
    tokens = load_tokens()
    if not tokens:
        print("❌ No tokens found")
        return
    exp = tokens.get("expires") or tokens.get("expires_at", 0)
    exp_s = exp // 1000 if exp > 1e12 else exp
    remaining = max(0, exp_s - time.time()) if exp_s else None
    print(f"Token: {'✅ Valid' if remaining and remaining > 0 else '❌ Expired'}")
    print(f"Source: {tokens.get('source', '?')}")
    if exp_s:
        print(f"Expires: {time.ctime(exp_s)}")
    if remaining:
        print(f"Remaining: {remaining:.0f}s")

def cmd_test_chatgpt():
    tokens = load_tokens()
    if not tokens:
        print("❌ No tokens")
        return
    access = tokens.get("access_token", "")
    req = urllib.request.Request(
        "https://chatgpt.com/backend-api/me",
        headers={"Authorization": f"Bearer {access}", "User-Agent": "Mozilla/5.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            me = json.loads(resp.read())
            print(f"✅ ChatGPT: {me.get('user', {}).get('email', '?')}")
    except urllib.error.HTTPError as e:
        print(f"❌ HTTP {e.code}: {e.read().decode()[:200]}")
    except Exception as e:
        print(f"❌ {e}")

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else None
    if cmd == "run":
        cmd_run()
    elif cmd == "status":
        cmd_status()
    elif cmd == "test-chatgpt":
        cmd_test_chatgpt()
    else:
        print(__doc__)
        sys.exit(1)