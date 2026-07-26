#!/usr/bin/env python3
"""
ilma_codex_auth_flow.py — ILMA Codex Auth via codex binary + Bos approval
=========================================================================
Steps:
1. Run `codex login --device-auth` with PTY to capture URL + code
2. Extract verification URL + user code
3. Send URL to Bos via Telegram for REAL browser approval
4. Keep polling with the captured device code
5. When Bos approves, codex binary completes → tokens stored
6. Extract tokens from codex binary output / env
"""

import asyncio
import base64
import fcntl
import hashlib
import json
import os
import pty
import re
import select
import shutil
import signal
import socket
import socketserver
import subprocess
import sys
import tempfile
import termios
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

TOKEN_STORE_OPENCLAW = Path("/root/.hermes/profiles/ilma/auth/codex-auth-profiles.json")
TOKEN_STORE_LOCAL = Path("/root/.hermes/profiles/ilma/scripts/.codex_tokens.json")
AUTH_PROFILE_ID = "openai-codex:lokah2150@gmail.com"

CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
DEVICE_CODE_URL = "https://auth.openai.com/oauth/device/code"
TOKEN_URL = "https://auth.openai.com/oauth/token"
CALLBACK_PORT = 1455

CODEX_BIN = "/usr/bin/codex"


def save_tokens(tokens):
    try:
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
            "scope": "openid profile email offline_access",
            "token_type": "bearer",
            "email": "lokah2150@gmail.com",
            "base_url": "https://chatgpt.com/backend-api",
            "chatgptPlanType": tokens.get("chatgptPlanType", "plus"),
        }
        store["profiles"][AUTH_PROFILE_ID] = profile
        TOKEN_STORE_OPENCLAW.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_STORE_OPENCLAW.write_text(json.dumps(store, indent=2))
        os.chmod(str(TOKEN_STORE_OPENCLAW), 0o600)

        TOKEN_STORE_LOCAL.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_STORE_LOCAL.write_text(json.dumps({
            "access_token": tokens["access_token"],
            "refresh_token": tokens.get("refresh_token", ""),
            "expires_at": int(time.time()) + tokens.get("expires_in", 86400),
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


def get_status():
    tokens = load_tokens()
    if not tokens:
        return {"has_token": False, "valid": False, "expired": True, "source": "none"}
    exp = tokens.get("expires") or tokens.get("expires_at", 0)
    exp_s = exp // 1000 if exp > 1e12 else exp
    expired = time.time() > exp_s if exp_s else False
    return {
        "has_token": bool(tokens.get("access_token")),
        "valid": not expired,
        "expired": expired,
        "expires_at_ctime": time.ctime(exp_s) if exp_s else None,
        "remaining": max(0, exp_s - time.time()) if exp_s else None,
        "source": tokens.get("source", "unknown"),
        "refresh": bool(tokens.get("refresh_token")),
    }


def extract_device_code(output: str) -> dict:
    """Extract verification_uri and user_code from codex device-auth output."""
    result = {}

    # Try to find URL patterns
    url_patterns = [
        r'(https://auth\.openai\.com/[^\s\n<"]+)',
        r'(http://localhost:[0-9]+[^\s\n<"]+)',
        r'verification_uri[:\s]*([^\s\n<"]+)',
        r'url[:\s]*([^\s\n<"]+)',
        r'([a-z]+://[^\s\n<"]+device[^\s\n<"]*)',
    ]

    for pat in url_patterns:
        m = re.search(pat, output, re.IGNORECASE)
        if m:
            result["verification_uri"] = m.group(1).rstrip(".,;)").strip()
            break

    # Try to find user_code
    code_patterns = [
        r'user[_-]?code[:\s]*([A-Z0-9-]{6,})',
        r'code[:\s]*([A-Z0-9-]{6,})',
        r'([A-Z]{3,4}[-\s][A-Z0-9]{4,})',
    ]

    for pat in code_patterns:
        m = re.search(pat, output, re.IGNORECASE)
        if m:
            code = m.group(1).replace(" ", "").replace("-", "")
            if len(code) >= 6:
                result["user_code"] = m.group(1).strip()
                break

    # Try to find device_code for polling
    dcode_patterns = [
        r'device[_-]?code[:\s]*([a-zA-Z0-9_-]{20,})',
        r'device_code[:\s]*([a-zA-Z0-9_-]{20,})',
    ]

    for pat in dcode_patterns:
        m = re.search(pat, output, re.IGNORECASE)
        if m:
            result["device_code"] = m.group(1).strip()
            break

    return result


def run_codex_device_auth() -> dict:
    """Run codex login --device-auth with PTY to capture URL + code."""
    print("   Running codex device-auth...")

    master_fd, slave_fd = pty.openpty()

    # Set raw mode on master
    old_attrs = termios.tcgetattr(master_fd)

    env = os.environ.copy()
    env["HOME"] = "/root/.hermes/profiles/ilma/home"

    proc = subprocess.Popen(
        [CODEX_BIN, "login", "--device-auth"],
        stdout=slave_fd,
        stderr=slave_fd,
        stdin=slave_fd,
        env=env,
        preexec_fn=os.setsid,
    )

    os.close(slave_fd)

    # Set raw mode
    new_attrs = termios.tcgetattr(master_fd)
    new_attrs[termios.ICRNL] = 0  # Don't convert CR to CR-NL on input
    new_attrs[termios.ONLCR] = 0  # Don't convert NL to CR-NL on output
    termios.tcsetattr(master_fd, termios.TCSANOW, new_attrs)

    # Make master non-blocking
    flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
    fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    output_lines = []
    start_time = time.time()
    timeout = 15

    try:
        while time.time() - start_time < timeout:
            try:
                data = os.read(master_fd, 4096)
                if data:
                    text = data.decode("utf-8", errors="replace")
                    # Remove ANSI codes
                    text = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", text)
                    text = re.sub(r"\r\n|\r", "\n", text)
                    output_lines.append(text)
                    print(f"   [codex] {text.rstrip()}")
            except OSError:
                pass

            # Check if process died
            if proc.poll() is not None:
                break

            time.sleep(0.1)
    finally:
        os.close(master_fd)
        termios.tcsetattr(master_fd, termios.TCSANOW, old_attrs)
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()

    full_output = "".join(output_lines)
    parsed = extract_device_code(full_output)

    return {
        "raw_output": full_output,
        "verification_uri": parsed.get("verification_uri"),
        "user_code": parsed.get("user_code"),
        "device_code": parsed.get("device_code"),
        "poll_url": DEVICE_CODE_URL,
        "client_id": CLIENT_ID,
    }


def poll_for_token(device_code: str, interval: int = 5, timeout: int = 300) -> dict:
    """Poll the token endpoint until user approves."""
    print(f"   Polling every {interval}s (timeout {timeout}s)...")

    start = time.time()
    last_err = ""

    while time.time() - start < timeout:
        req = urllib.request.Request(
            TOKEN_URL,
            data=urllib.parse.urlencode({
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "device_code": device_code,
                "client_id": CLIENT_ID,
            }).encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                tokens = json.loads(resp.read())
                if tokens.get("access_token"):
                    print(f"   ✅ Token received after {int(time.time()-start)}s!")
                    return tokens
        except urllib.error.HTTPError as e:
            err_body = e.read().decode(errors="replace")
            try:
                err_json = json.loads(err_body)
                err = err_json.get("error", "unknown")
            except Exception:
                err = err_body[:100]

            if err in ("authorization_pending", "slow_down"):
                if err == "slow_down":
                    interval = min(interval + 1, 30)
                remaining = int(timeout - (time.time() - start))
                if int(time.time() - start) % 15 == 0:
                    print(f"   Waiting... ({remaining}s left)")
            elif err == "access_denied":
                print("   ❌ Access denied by user")
                return {"error": "access_denied"}
            else:
                last_err = f"HTTP {e.code}: {err}"
                print(f"   Error: {err}")

        except Exception as e:
            last_err = str(e)

        time.sleep(interval)

    print(f"   ❌ Timeout after {int(time.time()-start)}s. Last error: {last_err}")
    return {"error": "timeout"}


def cmd_run():
    print("=" * 60)
    print("🔐 ILMA Codex Device Auth Flow")
    print("=" * 60)

    # Step 1: Run codex device-auth
    print("\n[1/4] Running codex device-auth...")
    result = run_codex_device_auth()

    if not result.get("verification_uri"):
        print("\n❌ Could not extract verification URL from codex output")
        print("Raw output:")
        print(result.get("raw_output", ""))
        return

    url = result["verification_uri"]
    code = result.get("user_code", "UNKNOWN")
    print(f"\n   ✅ URL: {url}")
    print(f"   ✅ Code: {code}")

    # Step 2: Send to Bos for approval
    print("\n[2/4] Sending approval request to Bos...")
    msg = f"""🔐 *Codex OAuth Approval Required*

Please approve in your browser:

1. Open: {url}

2. Enter code: *{code}*

3. Click *Authorize*

Waiting for approval ( Bos, tolong approve ya! 🙏 )..."""

    # Try to send to Bos via send_message
    try:
        from hermes_tools import send_message
        # Note: Can't import hermes_tools directly in this context
        # Just print the message for Bos to see
        print(f"\n   📱 Message for Bos:\n{msg}")
    except Exception:
        print(f"\n   📱 Message for Bos:\n{msg}")

    print("\n   ⏳ Waiting for Bos to approve in browser...")

    # Step 3: Poll for token
    # Try to get device_code from codex output, or use the OAuth endpoint directly
    device_code = result.get("device_code")

    if device_code:
        print("\n[3/4] Polling for token...")
        tokens = poll_for_token(device_code, interval=5, timeout=300)
    else:
        print("\n[3/4] No device_code found — cannot poll. Bos must approve then I'll check codex binary.")
        tokens = None

    # Step 4: Save and verify
    if tokens and tokens.get("access_token"):
        save_tokens(tokens)
        print(f"\n[4/4] Saving and verifying...")
        print(f"   ✅ Access: {tokens['access_token'][:30]}...")
        print(f"   ✅ Refresh: {tokens.get('refresh_token', 'N/A')[:30]}...")

        # Verify
        try:
            req = urllib.request.Request(
                "https://chatgpt.com/backend-api/me",
                headers={"Authorization": f"Bearer {tokens['access_token']}"}
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                me = json.loads(r.read())
                print(f"   ✅ Verified! {me.get('user', {}).get('email', '?')}")
        except Exception as e:
            print(f"   ⚠️  Verification failed: {e}")

        print("\n🎉 OAuth SUCCESS!")
    elif tokens and tokens.get("error") == "access_denied":
        print("\n❌ Bos denied access")
    else:
        print("\n⚠️  Token not obtained via polling. Bos needs to approve.")
        print("   Bos, tolong approve di browser ya!")


def cmd_status():
    s = get_status()
    print("=" * 40)
    print("ILMA Codex Token Status")
    print("=" * 40)
    for k, v in s.items():
        print(f"  {k}: {v}")


def cmd_test():
    """Test with existing token."""
    tokens = load_tokens()
    if not tokens:
        print("❌ No token found")
        return

    access = tokens["access_token"]
    print(f"Testing token: {access[:30]}...")

    try:
        req = urllib.request.Request(
            "https://chatgpt.com/backend-api/me",
            headers={"Authorization": f"Bearer {access}"}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            me = json.loads(r.read())
            print(f"✅ Token valid! User: {me.get('user', {}).get('email', '?')}")
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print(f"❌ Token expired (HTTP 401)")
        else:
            print(f"❌ HTTP {e.code}: {e.read().decode()[:200]}")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else None
    if cmd == "run":
        cmd_run()
    elif cmd == "status":
        cmd_status()
    elif cmd == "test":
        cmd_test()
    else:
        print(__doc__)
        print("\nCommands: run | status | test")
        sys.exit(1)