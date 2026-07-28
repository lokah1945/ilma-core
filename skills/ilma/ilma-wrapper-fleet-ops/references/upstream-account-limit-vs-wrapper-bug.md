# Wrapper bug vs Upstream account limit (diagnosis recipe)

When a wrapper returns 4xx/5xx after a successful restart, FIRST decide whether
the failure is a **wrapper bug** or an **upstream account/quota limit**. Only
wrapper bugs need code fixes — upstream limits need Bos action (add CC, upgrade
plan, pick a deployed model).

## Decision tree
1. **Port listening?** (`ss -tlnp | grep :910X`) — if NOT, it's a wrapper
   startup crash (import error / bind conflict). Fix the wrapper.
2. **`/health` 200?** — if 500, it's a wrapper app bug (see recurring-bugs.md).
3. **`/v1/models` returns data?** — if `{"data":[]}`, check `FREE_ONLY` / key
   entitlement (wrapper-side, fixable). If lists models, key is accepted.
4. **Chat returns error?** Read the error CLASS:
   - `401 Unauthorized` / `authentication_error` → wrapper auth STILL on (pre-auth
     not applied) OR key missing. Fix wrapper `.env` / auth gate.
   - `400 ... blocked by FREE_ONLY=yes` → model is paid but `FREE_ONLY=yes`. Use a
     `:free` model or set `FREE_ONLY=no`.
   - `404 Function '...' Not found for account '...'` → model NOT deployed in that
     upstream account (NVIDIA NIM per-account catalog). Wrapper works; pick a
     different model.
   - `503 No capacity` / `server_error` → upstream provider overloaded / account
     out of quota. NOT a wrapper bug.
   - `503 Circuit breaker is open (Ns remaining)` → wrapper tripped CB after
     repeated upstream failures. Wait for cooldown + retest; if it persists, the
     upstream call itself is failing (see below).
   - `502 Can not decode content-encoding: br` → upstream returned bad encoding;
     wrapper/proxy issue, retry.

## Prove the key is valid (isolates wrapper vs upstream)
Test the SAME key DIRECTLY against the upstream, bypassing the wrapper:
```bash
KEY=$(python3 -c "from dotenv import dotenv_values; print(dotenv_values('/root/wrapper/<wrapper>/.env').get('<WRAPPER>_API_KEY_1',''))")
curl -s -o /dev/null -w "upstream HTTP %{http_code}\n" --max-time 15 \
  -X POST "https://<upstream-host>/v1/chat/completions" \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"model":"<model>","messages":[{"role":"user","content":"hallo"}],"max_tokens":15}'
```
If upstream returns **403 with "requires a valid credit card"** → account-level
limit (Vercel AI Gateway free tier needs CC). If **200 Not Found** for all models
→ account has no deployed models (OpenCode free). These are NOT wrapper bugs.

## 2026-07-28 session findings (all-wrapper "hallo" test)
| Wrapper | Model | Result | Class |
|---------|-------|--------|-------|
| nvidia 9101 | `nvidia/nemotron-3-ultra-550b-a55b` | ✅ 200 "Hallo! Wie..." | works |
| nous 9102 | `tencent/hy3:free` | ✅ 200 | works |
| opencode 9103 | `nemotron-3-ultra-free` | ⚠️ 503 No capacity | upstream account empty |
| blackbox 9104 | `blackboxai/nvidia/nemotron-3-super-120b-a12b:free` | ✅ 200 "Hallo! 😊" | works |
| vercel 9105 | `alibaba/qwen-3-235b` | ⚠️ 503 circuit breaker | upstream 403 needs CC |
| openrouter 9106 | `inclusionai/ling-3.0-flash:free` | ✅ 200 | works |

**Lesson**: 4/6 wrappers work end-to-end. The 2 failures (opencode, vercel) are
upstream account limits, not wrapper config errors. Do NOT "fix" the wrapper for
these — tell Bos the upstream constraint.

## MCP fetcher (mode_fetcher :9100) end-to-end test recipe
The fetcher serves an MCP server (Streamable HTTP) at `/mcp`. Test a fetched
model via the MCP protocol:
```bash
# 1. Initialize session
curl -s -X POST http://127.0.0.1:9100/mcp -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"ilma-test","version":"1.0"}}}' \
  -D /tmp/mcp_hdr.txt -o /tmp/mcp_init.txt
SID=$(grep -i "mcp-session-id" /tmp/mcp_hdr.txt | tr -d '\r' | awk '{print $2}')

# 2. search_models -> get catalog_id
curl -s -X POST http://127.0.0.1:9100/mcp -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" -H "mcp-session-id: $SID" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"search_models","arguments":{"query":"nemotron-3-ultra-550b","limit":1}}}' -o /tmp/r.txt

# 3. get_model(catalog_id=...) and get_usage_example(language=curl) for the endpoint
# 4. REAL inference: pull NVIDIA_API_KEY from mode_fetcher/.env, POST to endpoint from get_usage_example
```
Note: fetcher `get_model` takes `catalog_id` (NOT `served_model_id`). The DB
table is `models` (served_model_id) + `gateway_models` (may be empty if gateway
fetch not run). Real chat completion proves the API key injected from wrapper
`.env` is active.
