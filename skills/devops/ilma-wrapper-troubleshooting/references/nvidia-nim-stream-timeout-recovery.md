# NVIDIA NIM Large-Model `stream:true` + ≥60s Timeout Recovery

Reusable harness + results from the 2026-07-28 "retry all failed nvidia-python models" sweep.

## When to use
A model on `wrapper-nvidia` (port 9101) failed a non-stream 25s probe with a client
timeout (`curl: (28)`) or you suspect a large model is callable but the first probe
timed out. Bos: *"Bukan masalah key exhaustion, tp cara anda call upstream pasti salah."*
→ The fix is the CALL METHOD (stream + longer timeout), not the keys.

## Harness: `retry_nvidia_failed.py`
Run from `/root/wrapper`. Reads `nvidia_llm_test_report.json` (first-sweep failures),
retries each with `stream:true`, `max_tokens=150`, `timeout=60s`, collects SSE deltas.

```python
#!/usr/bin/env python3
import json, urllib.request, urllib.error, time
BASE = "http://127.0.0.1:9101"
TOK = "wrapper-local-key"

def chat(model, timeout=60):
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "hallo"}],
        "max_tokens": 150, "temperature": 0.3, "stream": True,
    }).encode()
    req = urllib.request.Request(f"{BASE}/v1/chat/completions", data=body, method="POST")
    req.add_header("Authorization", f"Bearer {TOK}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            chars = 0; buf = ""
            for raw in r:
                line = raw.decode().strip()
                if line.startswith("data:") and line != "data: [DONE]":
                    try:
                        chunk = json.loads(line[5:].strip())
                        delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                        if delta:
                            chars += len(delta); buf += delta
                    except Exception:
                        pass
            return ("OK", buf[:200], chars) if chars > 0 else ("EMPTY", "(stream ended no content)", 0)
    except urllib.error.HTTPError as e:
        try:
            d = json.loads(e.read().decode())
            return ("ERR", str(d.get("error", {}).get("message", ""))[:180], e.code)
        except Exception:
            return ("HTTP", str(e)[:120], e.code)
    except Exception as e:
        return ("FAIL", str(e)[:120], None)

def main():
    rep = json.load(open("/root/wrapper/nvidia_llm_test_report.json"))
    failed = [r["model"] for r in rep["results"] if r["status"] != "OK"]
    results = []
    for i, mid in enumerate(failed, 1):
        st, msg, code = chat(mid)
        results.append({"model": mid, "status": st, "reply": msg, "code": code})
        tag = "✅" if st == "OK" else ("⚠️" if st == "EMPTY" else "❌")
        print(f"[{i}/{len(failed)}] {tag} {mid}: {st} | {msg[:70]}", flush=True)
        time.sleep(0.4)
    ok = [r for r in results if r["status"] == "OK"]
    with open("/root/wrapper/nvidia_retry_report.json", "w") as f:
        json.dump({"retried": len(results), "ok_stream": len(ok), "results": results}, f, indent=2)
    print(f"\nretried={len(results)} ok_stream={len(ok)}")

if __name__ == "__main__":
    main()
```

Run: `python3 retry_nvidia_failed.py > /root/wrapper/nvidia_retry.log 2>&1`
(background; ~5-7 min for 47 models).

## Results (2026-07-28)
47 retried → **5 recovered to OK**, 42 still failed.

**Recovered (stream:true + 60s):**
| Model | Reply |
|---|---|
| `google/gemma-4-31b-it` | "Hallo! Wie kann ich dir heute helfen?" |
| `meta/llama-3.1-70b-instruct` | "Hallo! How can I assist you today?" |
| `meta/llama-3.2-3b-instruct` | "Hallo! Wie kann ich Ihnen helfen?" |
| `openai/gpt-oss-120b` | "Hallo! Wie kann ich dir weiterhelfen? 😊" |
| `poolside/laguna-xs-2.1` | "Hello! How can I assist you today?" |

**Still failed — categories:**
| Reason | Count | Meaning |
|---|---|---|
| `Function not found for account` (404) | 34 | Legit not-deployed in NVIDIA account — NOT a call error |
| Timeout >60s even streamed | 5 | Genuinely overloaded/slow upstream |
| `Model not found at upstream` (400) | 2 | Wrong id format |
| Embedding model, no stream | 1 | Filter error (not a chat model) |

## Id-format disambiguation (llama-3.3-70b-instruct)
| id tried | result |
|---|---|
| `meta/llama-3.3-70b-instruct` | 404 account-scoped (CORRECT format, not deployed) |
| `nvdev/meta/llama-3.3-70b-instruct` | 404 account-scoped (same NVCF fn, not deployed) |
| `ai/llama-3.3-70b-instruct` | 400 not found at upstream (wrong prefix) |
| `llama-3.3-70b-instruct` | 400 not found at upstream (missing provider) |
| `nvidia/llama-3.3-70b-instruct` | 400 not found at upstream (wrong prefix) |

→ Use the exact id from `GET /v1/models`. A 404 "not found for account" is deployment
state, NOT a call-format bug.
