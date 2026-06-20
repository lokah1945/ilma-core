#!/usr/bin/env python3
"""
Probe every AI/LLM provider in /root/credential/api_key.json by reading the
`url_endpoint` field and hitting it with a browser-like User-Agent.

Output columns: provider | status | models | url
Exit codes:
  0 = all probes either 200 OK or had no key/endpoint
  1 = at least one provider with a key AND endpoint returned non-200

Usage:
  python3 scripts/probe_all_ai_llm_endpoints.py
  python3 scripts/probe_all_ai_llm_endpoints.py --provider openai
  python3 scripts/probe_all_ai_llm_endpoints.py --filter working
"""
import json
import urllib.request
import urllib.error
import argparse
import sys
from pathlib import Path

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
CREDS_PATH = Path("/root/credential/api_key.json")
TIMEOUT = 15


def get_first_key(pdata: dict) -> str | None:
    """Extract first usable key from various schemas (keys[], api_key, dict-of-keys, email-keyed)."""
    if not isinstance(pdata, dict):
        return None
    keys = pdata.get("keys", [])
    if isinstance(keys, list) and keys:
        return keys[0]
    if isinstance(pdata.get("api_key"), str):
        return pdata["api_key"]
    if isinstance(pdata.get("auth_token"), str):
        return pdata["auth_token"]
    # dict-of-keys (e.g., nvidia: {"nvapi-...1": {...}, "nvapi-...2": {...}})
    for k, v in pdata.items():
        if isinstance(v, dict) and v.get("api_key") and k.startswith(("nvapi-", "sk-")):
            return v["api_key"]
    # email-keyed nested
    for k, v in pdata.items():
        if isinstance(v, dict) and v.get("api_key"):
            return v["api_key"]
    return None


def probe(url: str, key: str | None, auth_type: str = "Bearer") -> tuple[str, int | None, str | None]:
    """Returns (status_code, model_count_or_None, note_or_None)."""
    if not url:
        return "NO_ENDPOINT", None, "url_endpoint not set"

    # Handle google's ?key=API_KEY pattern
    if "{API_KEY}" in url or "{k}" in url:
        if not key:
            return "SKIP", None, "no key for placeholded URL"
        url = url.replace("{API_KEY}", key).replace("{k}", key)
        key = None  # don't add Authorization header

    try:
        req = urllib.request.Request(url)
        if key:
            if auth_type == "x-goog-api-key":
                req.add_header("x-goog-api-key", key)
            elif auth_type == "none":
                pass
            else:
                req.add_header("Authorization", f"Bearer {key}")
        req.add_header("Accept", "application/json")
        req.add_header("User-Agent", UA)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
            # Try common model list shapes
            for k in ["data", "models"]:
                if k in data and isinstance(data[k], list):
                    return str(resp.status), len(data[k]), None
            if isinstance(data, list):
                return str(resp.status), len(data), None
            return str(resp.status), None, f"keys={list(data.keys())[:3]}"
    except urllib.error.HTTPError as e:
        return str(e.code), None, e.read().decode()[:80].replace("\n", " ")
    except urllib.error.URLError as e:
        return "URL_ERR", None, str(e.reason)[:80]
    except Exception as e:
        return "EXC", None, f"{type(e).__name__}: {str(e)[:60]}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", help="only probe this provider_id")
    parser.add_argument("--filter", choices=["working", "broken", "all"], default="all")
    args = parser.parse_args()

    if not CREDS_PATH.exists():
        print(f"ERROR: {CREDS_PATH} not found", file=sys.stderr)
        sys.exit(2)

    cred = json.loads(CREDS_PATH.read_text())
    ai_llm = {k: v for k, v in cred.items()
              if isinstance(v, dict) and v.get("category") == "AI/LLM" and not k.startswith("_")}

    if args.provider:
        ai_llm = {args.provider: ai_llm[args.provider]} if args.provider in ai_llm else {}

    results = []
    for pid in sorted(ai_llm.keys()):
        pdata = ai_llm[pid]
        url = pdata.get("url_endpoint", "")
        auth = pdata.get("url_endpoint_auth", "Bearer")
        key = get_first_key(pdata)
        status, count, note = probe(url, key, auth)
        results.append((pid, status, count, url, key is not None, note))

    # Print
    print(f"{'Provider':<14} | {'Status':<10} | {'Models':>6} | URL")
    print("-" * 90)
    for pid, status, count, url, has_key, note in results:
        if not has_key and not url:
            line = f"{pid:<14} | {'NO_KEY':<10} | {'':>6} | (no url_endpoint)"
        elif not url:
            line = f"{pid:<14} | {'NO_URL':<10} | {'':>6} | (key present, url_endpoint missing)"
        else:
            models_str = str(count) if count is not None else "?"
            line = f"{pid:<14} | {status:<10} | {models_str:>6} | {url[:60]}"
            if note:
                line += f"  # {note}"
        print(line)

    # Filter
    working = [r for r in results if r[1].startswith("2") and r[3]]
    broken = [r for r in results if not r[1].startswith("2") and r[5] and r[3] and r[4]]
    skipped = [r for r in results if not r[3] or not r[4]]

    print(f"\nSummary: {len(working)} working, {len(broken)} broken-with-key, {len(skipped)} skipped (no key/endpoint)")

    if args.filter == "working":
        for r in working:
            print(f"  ✓ {r[0]}: {r[2]} models")
    elif args.filter == "broken":
        for r in broken:
            print(f"  ✗ {r[0]}: {r[1]} — {r[5]}")

    # Exit code: 1 if any provider with both key AND endpoint failed
    sys.exit(1 if broken else 0)


if __name__ == "__main__":
    main()
