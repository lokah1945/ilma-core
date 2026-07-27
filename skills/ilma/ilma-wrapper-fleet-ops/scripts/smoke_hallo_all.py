#!/usr/bin/env python3
"""
smoke_hallo_all.py — End-to-end chat smoke test for ALL 5 LLM wrappers.

Sends a short prompt ("hallo") to each wrapper on 127.0.0.1:910X, picks the
first FREE model from /v1/models, and reports whether a non-empty reply came
back. This catches more than /health: it exercises auth, routing, upstream
key validity, and model availability in one pass.

WHY this exists: A wrapper can return /health 200 but still fail chat because
(a) BEARER_TOKEN mismatch (401), (b) FREE_ONLY strips all models (0 models),
(c) upstream API keys exhausted/rate-limited, (d) upstream "No capacity"
(entitlement), (e) wrapper brotli-decode bug. /health alone misses all of these.

Usage:
    python3 scripts/smoke_hallo_all.py
    python3 scripts/smoke_hallo_all.py --token wrapper-local-key --prompt "hallo, jawab singkat"
    python3 scripts/smoke_hallo_all.py --ports 9101,9102

Exit code: 0 if at least one wrapper returned a non-empty reply, 1 if all failed.
"""
import argparse
import json
import sys
import urllib.request
import urllib.error

DEFAULT_PORTS = [9101, 9102, 9103, 9104, 9105]
DEFAULT_TOKEN = "wrapper-local-key"
DEFAULT_PROMPT = "hallo, jawab dalam satu kalimat singkat."


def _post(url, headers, body, timeout=45):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, json.loads(r.read().decode())


def _get(url, headers, timeout=8):
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, json.loads(r.read().decode())


def probe(port, token, prompt, max_tokens=200):
    base = f"http://127.0.0.1:{port}"
    auth = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    out = {"port": port, "auth": None, "model": None, "reply": None, "error": None}

    # 1. auth + model discovery
    try:
        st, data = _get(f"{base}/v1/models", auth)
        out["auth"] = st
        if st != 200:
            out["error"] = f"/v1/models HTTP {st}"
            return out
        models = [m.get("id", "") for m in data.get("data", [])]
        if not models:
            out["error"] = "0 models (FREE_ONLY strips all? or upstream key invalid)"
            return out
        # pick first free-ish model; else first available
        free = [m for m in models if ":free" in m.lower()]
        out["model"] = free[0] if free else models[0]
    except urllib.error.HTTPError as e:
        out["auth"] = e.code
        out["error"] = f"/v1/models HTTP {e.code} ({e.reason})"
        if e.code == 401:
            out["error"] += " — BEARER_TOKEN mismatch (check .env)"
        return out
    except Exception as e:
        out["error"] = f"discovery failed: {e}"
        return out

    # 2. chat completion
    try:
        st, data = _post(
            f"{base}/v1/chat/completions", auth,
            {"model": out["model"], "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens},
        )
        if st != 200:
            out["error"] = f"chat HTTP {st}: {json.dumps(data)[:160]}"
            return out
        if "choices" in data and data["choices"]:
            c = data["choices"][0].get("message", {}).get("content", "")
            out["reply"] = c
            if not c.strip():
                out["error"] = "EMPTY reply (upstream free model returned nothing — try max_tokens>=200 + substantive prompt)"
        elif "error" in data:
            out["error"] = f"chat error: {str(data['error'])[:160]}"
        else:
            out["error"] = f"unexpected: {str(data)[:160]}"
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:160] if e.fp else ""
        out["error"] = f"chat HTTP {e.code}: {body}"
    except Exception as e:
        out["error"] = f"chat failed: {e}"
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--token", default=DEFAULT_TOKEN)
    ap.add_argument("--prompt", default=DEFAULT_PROMPT)
    ap.add_argument("--ports", default=",".join(map(str, DEFAULT_PORTS)))
    ap.add_argument("--max-tokens", type=int, default=200)
    args = ap.parse_args()
    ports = [int(p) for p in args.ports.split(",") if p.strip()]

    print(f"=== SMOKE: 'hallo' to {len(ports)} wrappers (token={args.token[:10]}***) ===")
    ok = 0
    for p in ports:
        r = probe(p, args.token, args.prompt, args.max_tokens)
        if r["reply"] and r["reply"].strip():
            print(f"  OK port {p}: '{r['reply'][:60]}'  (model={r['model']})")
            ok += 1
        elif r["auth"] != 200:
            print(f"  LOCK port {p}: AUTH {r['auth']} — {r['error']}")
        elif r["error"]:
            print(f"  FAIL port {p}: {r['error']}  (model={r['model']})")
        else:
            print(f"  UNK port {p}: no reply  (model={r['model']})")
    print(f"=== {ok}/{len(ports)} wrappers returned a non-empty reply ===")
    sys.exit(0 if ok > 0 else 1)


if __name__ == "__main__":
    main()
