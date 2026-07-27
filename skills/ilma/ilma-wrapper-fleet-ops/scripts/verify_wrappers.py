#!/usr/bin/env python3
"""Verify all /root/wrapper LLM proxies: port bound + /health + /v1/models count.

Usage: python3 verify_wrappers.py
Run from anywhere; needs no args. Prints a table and exits non-zero if any
wrapper is down.
"""
import json
import sys
import urllib.request

WRAPPERS = {
    "nvidia":   9101,
    "nous":     9102,
    "opencode": 9103,
    "blackbox": 9104,
    "vercel":   9105,
}
KEY = "wrapper-local-key"
TIMEOUT = 8


def probe(port: int) -> dict:
    out = {"port": port, "bound": False, "health": None, "commit": None, "models": None}
    # bind check via /health
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/health")
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            out["bound"] = True
            data = json.load(r)
            out["health"] = data.get("status")
            out["commit"] = (data.get("git_commit") or "?")[:7]
    except Exception:
        return out
    # models count (needs auth)
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/v1/models",
            headers={"Authorization": f"Bearer {KEY}"},
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            out["models"] = len(json.load(r).get("data", []))
    except Exception:
        pass
    return out


def main():
    print(f"{'WRAPPER':<10}{'PORT':<6}{'BOUND':<7}{'HEALTH':<9}{'COMMIT':<9}{'MODELS'}")
    print("-" * 50)
    ok = True
    for name, port in WRAPPERS.items():
        r = probe(port)
        bound = "yes" if r["bound"] else "NO"
        health = r["health"] or "-"
        commit = r["commit"] or "-"
        models = r["models"] if r["models"] is not None else "-"
        if not r["bound"] or r["health"] not in ("ok", "degraded"):
            ok = False
        print(f"{name:<10}{port:<6}{bound:<7}{health:<9}{commit:<9}{models}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
