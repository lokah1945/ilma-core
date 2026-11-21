# Wrapper SDK-Compat Audit — Edge-Case Matrix (2026-07-24)

Reproduction recipe + real crashes found auditing `/root/wrapper` (nvidia/nous/opencode) toward 100/100 OpenAI/Anthropic SDK compatibility.

## Setup (read tokens)
```bash
KNV=$(grep -oE 'BEARER_TOKEN=.+' /root/wrapper/nvidia-python/.env|head -1|cut -d= -f2)
KNO=$(grep -oE 'BEARER_TOKEN=.+' /root/wrapper/nous/.env|head -1|cut -d= -f2)
KOC=$(grep -oE 'BEARER_TOKEN=.+' /root/wrapper/opencode/.env|head -1|cut -d= -f2)
declare -A K=(["9101"]="$KNV" ["9106"]="$KNO" ["9107"]="$KOC")
```

## Edge-case matrix (run per port p in 9101 9106 9107, k=${K[$p]}, B=http://127.0.0.1:$p)
| # | Test | Expected | Why it matters |
|---|------|:---:|----------------|
| 1 | Chat explicit model | 200 | happy path |
| 2 | Chat alias `sonnet` | 200 | dynamic alias (needs warmup) |
| 3 | Chat empty `messages:[]` | 400 | SDK guard |
| 4 | Chat malformed JSON `{bad` | 400 | parser resilience |
| 5 | Chat `tools` (function) | 200 | **catches G1** |
| 6 | Responses alias `sonnet` | 200 | Responses API |
| 7 | Anthropic explicit | 200 | Anthropic happy path |
| 8 | Anthropic `system` as `[{type:text}]` | 200 | SDK sends array |
| 9 | Anthropic `thinking` enabled | 200 | reasoning surface |
| 10 | **Anthropic `tools`** | 200 | **G1: `isinstance(tools)` → 500** |
| 11 | **CORS `OPTIONS` preflight** + `Origin: http://localhost:9106` | 200 + `access-control-allow-origin` | **G2: browser SDK dead without it** |
| 12 | No-auth | 401 | auth enforced |
| 13 | `/v1/capabilities` | 200 | parity |

## G1 — Anthropic tools crash (REAL BUG, 500)
**Symptom:** `POST /v1/messages` with `tools` → `500 Internal Server Error`.
**Traceback:** `anthropic_compat.py` line `if not isinstance(tools) or not tools:` → `TypeError: isinstance expected 2 arguments, got 1`.
**Fix:** `isinstance(tools, list)`.
**Why silent:** happy-path Anthropic calls (no tools) never hit this branch. Only a real tool-using client (Claude Code, Codex) triggers it.

## G2 — CORS preflight blocked (REAL BUG)
**Symptom:** Browser OpenAI/Anthropic SDK → preflight `OPTIONS` → 401 (auth middleware ran before CORS) or 400 (origin not in `allow_origins` list).
**Fix (per wrapper):**
```python
app.add_middleware(CORSMiddleware,
    allow_origin_regex=r'https?://(127\.0\.0\.1|localhost|\[::1\])(:[0-9]+)?$',
    allow_methods=['*'], allow_headers=['*'], expose_headers=['*'])
# in auth middleware:
if request.method == 'OPTIONS':
    return  # preflight passes without auth
```
**Verify:** `curl -s -D - -X OPTIONS $B/v1/chat/completions -H "Origin: http://localhost:9106"` → HTTP 200 + `access-control-allow-origin: http://localhost:9106`.

## Warmup false-negative (CRITICAL)
After `systemctl restart`, wait ~8s (or poll `/health` until `uptime` > 10) before asserting failure. ILMA once reported nvidia alias `sonnet`=404 two seconds post-restart, then 200 after warmup — a false negative from test timing, not a bug.

## Result
89 → **100/100** after G1+G2 fixed. Remaining (non-blocking): `wrapper-core` extraction for scale-safety before wrapper #4.
