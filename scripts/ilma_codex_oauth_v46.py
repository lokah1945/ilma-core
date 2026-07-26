#!/usr/bin/env python3
"""
ILMA Codex OAuth v46 — DEBUG LOGIN FLOW
Take screenshots and analyze page structure to fix login.
"""

import base64
import hashlib
import json
import secrets
import time
import urllib.parse
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import sys
import os

sys.path.insert(0, "/root/.hermes/profiles/ilma/scripts")

from playwright.sync_api import sync_playwright

# === CONFIG ===
CODEX_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
TOKEN_FILE = "/root/.hermes/profiles/ilma/scripts/.codex_tokens_v46.json"
GMAIL_USER = "lokah2150@gmail.com"
GMAIL_PASS = "Kucing.2150"

STEALTH_ARGS = [
    '--no-sandbox',
    '--disable-dev-shm-usage',
    '--disable-setuid-sandbox',
    '--disable-blink-features=AutomationControlled',
    '--disable-gpu',
]

# === Callback server ===
callback_data = {}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if '/auth/callback' in self.path:
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            callback_data['code'] = params.get('code', [''])[0]
            callback_data['state'] = params.get('state', [''])[0]
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(b'<html><body><h1>Login Success!</h1><p>You can close this window.</p></body></html>')
            print(f"[CALLBACK] Got code: {callback_data['code'][:30]}...")
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass

def generate_pkce():
    verifier = secrets.token_urlsafe(64)
    challenge = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(challenge).decode().rstrip('=')
    return verifier, challenge

def exchange_code(code, verifier):
    data = urllib.parse.urlencode({
        'grant_type': 'authorization_code',
        'client_id': CODEX_CLIENT_ID,
        'code': code,
        'code_verifier': verifier,
        'redirect_uri': 'http://localhost:1455/auth/callback',
    }).encode('utf-8')
    
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'User-Agent': 'ILMA-Codex-OAuth/1.0',
    }
    
    url = "https://auth.openai.com/oauth/token"
    try:
        req = urllib.request.Request(url, data=data, headers=headers, method='POST')
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"[TOKEN] HTTP {e.code}: {e.read()[:500]}")
        return None
    except Exception as e:
        print(f"[TOKEN] Error: {e}")
        return None

def analyze_page(page, label):
    """Take snapshot and screenshot of current page"""
    print(f"\n=== {label} ===")
    print(f"URL: {page.url}")
    
    # Get accessibility tree
    snapshot = page.accessibility.snapshot()
    if snapshot:
        # Find interactive elements
        print("Interactive elements:")
        def walk(node, depth=0):
            if not node:
                return
            role = node.get('role', '')
            name = node.get('name', '')
            props = node.get('properties', {})
            state = node.get('states', [])
            
            if role in ['button', 'link', 'textbox', 'checkbox', 'radio', 'menuitem']:
                print(f"  {'  ' * depth}[{role}] {name[:60]}")
                if props:
                    print(f"    props: {props}")
                if state:
                    print(f"    states: {state}")
            
            for child in node.get('children', []):
                walk(child, depth + 1)
        
        walk(snapshot)
    
    # Save screenshot
    screenshot_path = f"/root/.hermes/profiles/ilma/scripts/v46_{label.replace(' ', '_').lower()}.png"
    page.screenshot(path=screenshot_path)
    print(f"Saved screenshot: {screenshot_path}")

def main():
    print("=" * 60)
    print("ILMA CODEX OAUTH v46 — DEBUG LOGIN FLOW")
    print("=" * 60)
    
    # Start callback server
    server = HTTPServer(('127.0.0.1', 1455), Handler)
    thread = threading.Thread(target=server.handle_request)
    thread.start()
    print("[SERVER] Callback server started")
    
    # Generate PKCE
    verifier, challenge = generate_pkce()
    state = "ilma_" + secrets.token_urlsafe(16)
    
    # Build auth URL
    params = {
        'response_type': 'code',
        'client_id': CODEX_CLIENT_ID,
        'redirect_uri': 'http://localhost:1455/auth/callback',
        'scope': 'openid profile email offline_access api.connectors.read api.connectors.invoke',
        'code_challenge': challenge,
        'code_challenge_method': 'S256',
        'state': state,
        'id_token_add_organizations': 'true',
        'codex_cli_simplified_flow': 'true',
        'originator': 'codex_cli_rs',
    }
    
    auth_url = f"https://auth.openai.com/oauth/authorize?{urllib.parse.urlencode(params)}"
    
    with sync_playwright() as p:
        print("[BROWSER] Launching browser...")
        context = p.chromium.launch(headless=True, args=STEALTH_ARGS)
        page = context.new_page()
        page.set_viewport_size({"width": 1280, "height": 800})
        
        print("[NAV] Going to auth URL...")
        page.goto(auth_url, timeout=60000)
        time.sleep(3)
        
        analyze_page(page, "Initial Load")
        
        # Find email input using visible selector
        print("\n[STEP 1] Looking for email input...")
        
        # Try different selectors - Google uses complex structure
        selectors_to_try = [
            "input[type='email']",
            "input[name='identifier']",
            "#identifierId",
            "input[type='text']",
            "input[autocomplete='username']",
        ]
        
        email_filled = False
        for sel in selectors_to_try:
            try:
                inp = page.query_selector(sel)
                if inp and inp.is_visible():
                    print(f"  Trying selector: {sel}")
                    inp.fill(GMAIL_USER)
                    time.sleep(1)
                    email_filled = True
                    break
            except:
                continue
        
        if not email_filled:
            print("  [ERROR] Could not find visible email input")
        
        analyze_page(page, "After Email")
        
        # Try pressing Enter or clicking Next
        print("\n[STEP 2] Clicking Next...")
        page.keyboard.press("Enter")
        time.sleep(4)
        
        analyze_page(page, "After Next Click")
        
        # Now look for password - Google uses visible password input
        print("\n[STEP 3] Looking for password input...")
        password_selectors = [
            "input[type='password'][name='password']",
            "input[name='password']",
            "input[type='password'][autocomplete='current-password']",
            "input[autocomplete='current-password']",
        ]
        
        for sel in password_selectors:
            try:
                inp = page.query_selector(sel)
                if inp and inp.is_visible():
                    print(f"  Found password input with selector: {sel}")
                    inp.fill(GMAIL_PASS)
                    time.sleep(1)
                    page.keyboard.press("Enter")
                    break
            except:
                continue
        
        analyze_page(page, "After Password")
        
        time.sleep(5)
        
        # Wait for callback
        print("[WAIT] Waiting for OAuth callback...")
        for _ in range(60):
            if 'code' in callback_data and callback_data['code']:
                print(f"[CALLBACK] Got code: {callback_data['code'][:30]}...")
                break
            time.sleep(1)
        
        analyze_page(page, "Final State")
        
        context.close()
    
    server.server_close()
    
    # Exchange code for tokens
    if 'code' in callback_data and callback_data['code']:
        print("\n[TOKEN] Exchanging code for tokens...")
        tokens = exchange_code(callback_data['code'], verifier)
        
        if tokens:
            print(f"[SUCCESS] Got tokens!")
            with open(TOKEN_FILE, 'w') as f:
                json.dump(tokens, f, indent=2)
            
            # Check scopes
            at = tokens.get('access_token', '')
            if at:
                parts = at.split('.')
                if len(parts) >= 2:
                    payload_b64 = parts[1]
                    padding = 4 - len(payload_b64) % 4
                    if padding != 4:
                        payload_b64 += '=' * padding
                    payload = json.loads(base64.urlsafe_b64decode(payload_b64))
                    scp = payload.get('scp', [])
                    print(f"\n[SCOPES] {scp}")
                    print(f"  Has api.responses.write: {'api.responses.write' in scp}")
    else:
        print("\n[FAILED] No code received")

if __name__ == "__main__":
    main()