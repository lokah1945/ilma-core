#!/usr/bin/env python3
"""
Test ALL text-to-text LLM chat models on a wrapper with 'hallo', report replies.

Usage:
  python3 scripts/test_all_llm_models.py [--base http://127.0.0.1:9101] \
      [--token wrapper-local-key] [--prompt "hallo"] [--timeout 25] [--out report.json]

Filters OUT non-text models (embedding / vision / image / audio / safety / parse /
retriever / translate) by id substring so only chat-capable LLMs are tested. Writes a
JSON report {total_tested, ok, failed, results:[{model,status,reply,code}]}.

Class-level technique from 2026-07-28 nvidia-python session: 65 models listed, only 18
text-to-text LLMs actually returned a reply (34 = 404 not deployed in account, 9 = timeout
>25s, 3 = model not found upstream). Proves the wrapper works; most "failures" are
upstream account-deployment gaps, NOT wrapper bugs.
"""
import json, urllib.request, urllib.error, time, argparse, sys

SKIP = (
    'embed', 'clip', 'flux', 'stable-diffusion', 'qwen-image', 'diffusion',
    'consistory', 'kandinsky', 'playground', 'vision', '/vl', 'vila', 'neva',
    'guard', 'safety', 'reward', 'parse', 'retriever', 'translate', 'audio',
    'fugatto', 'kosmos', 'deplot', 'recurrentgemma', 'synthetic-video',
    'ising-calibration', 'cosmos', 'codegemma', 'nemoguard', 'nemoretriever',
)

def is_text_llm(mid):
    low = mid.lower()
    return not any(s in low for s in SKIP)

def chat(base, tok, model, prompt, timeout):
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 60,
        "temperature": 0.3,
    }).encode()
    req = urllib.request.Request(f"{base}/v1/chat/completions", data=body, method="POST")
    req.add_header("Authorization", f"Bearer {tok}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read().decode())
            if "choices" in d and d["choices"]:
                return ("OK", d["choices"][0]["message"]["content"][:200],
                        d["choices"][0].get("finish_reason"))
            if "error" in d:
                return ("ERR", str(d["error"].get("message", ""))[:200], d["error"].get("code"))
            return ("UNK", str(d)[:200], None)
    except urllib.error.HTTPError as e:
        try:
            d = json.loads(e.read().decode())
            return ("ERR", str(d.get("error", {}).get("message", ""))[:200], e.code)
        except Exception:
            return ("HTTP", str(e)[:150], e.code)
    except Exception as e:
        return ("FAIL", str(e)[:150], None)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:9101")
    ap.add_argument("--token", default="wrapper-local-key")
    ap.add_argument("--prompt", default="hallo")
    ap.add_argument("--timeout", type=int, default=25)
    ap.add_argument("--out", default="/root/wrapper/nvidia_llm_test_report.json")
    a = ap.parse_args()

    req = urllib.request.Request(f"{a.base}/v1/models")
    req.add_header("Authorization", f"Bearer {a.token}")
    with urllib.request.urlopen(req, timeout=10) as r:
        models = json.loads(r.read().decode()).get("data", [])
    ids = [m["id"] for m in models]
    text_llms = [i for i in ids if is_text_llm(i)]
    print(f"TOTAL models: {len(ids)} | text-to-text LLMs to test: {len(text_llms)}", flush=True)

    results = []
    for i, mid in enumerate(text_llms, 1):
        status, msg, code = chat(a.base, a.token, mid, a.prompt, a.timeout)
        results.append({"model": mid, "status": status, "reply": msg, "code": code})
        tag = "OK" if status == "OK" else "ERR"
        print(f"[{i}/{len(text_llms)}] {tag} {mid}: {status} | {msg[:80]}", flush=True)
        time.sleep(0.3)

    ok = [r for r in results if r["status"] == "OK"]
    err = [r for r in results if r["status"] != "OK"]
    with open(a.out, "w") as f:
        json.dump({"total_tested": len(results), "ok": len(ok), "failed": len(err),
                   "results": results}, f, indent=2)
    print(f"\n=== SUMMARY ===\ntested={len(results)} ok={len(ok)} failed={len(err)}", flush=True)
    print(f"Report: {a.out}", flush=True)

if __name__ == "__main__":
    main()
