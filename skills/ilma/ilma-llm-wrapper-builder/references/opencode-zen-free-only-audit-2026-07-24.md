# OpenCode Zen — Free-Only Wrapper Integration (audit 2026-07-24)

## Source of truth
Official docs: https://opencode.ai/docs/zen/ (last updated 2026-07-22).

## Zen endpoint map (verified against docs)
| Family | Examples | Zen endpoint |
|---------|----------|-------------|
| OpenAI (GPT) | `gpt-5.x` | `POST {base}/responses` |
| Anthropic / Qwen3.x | `claude-*`, `qwen3.*` | `POST {base}/messages` |
| Google (Gemini) | `gemini-*` | `POST {base}/models/{id}` |
| OpenAI-compatible (Grok, DeepSeek, MiniMax, GLM, Kimi, **all FREE models**) | `deepseek-v4-flash-free`, `mimo-v2.5-free`, `laguna-s-2.1-free`, `nemotron-3-ultra-free`, `north-mini-code-free`, `big-pickle` | `POST {base}/chat/completions` |

Base = `https://opencode.ai/zen/v1`. Model id client-side = `opencode/<id>` (strip prefix before routing).
Catalog fetch: `GET {base}/models`.

## CRITICAL PITFALL (this session)
When building a FastAPI proxy for Zen in **free-only mode**, the model→family
router MUST send free / openai-compatible models to `/chat/completions`, NOT `/responses`.

Wrong (causes Zen 400 "Upstream request failed" on every free model):
```python
def _zen_family(model):
    m = model.lower()
    if m.startswith('gpt-'): return 'responses'
    if m.startswith('claude-'): return 'messages'
    if m.startswith('gemini-'): return 'google'
    if m.startswith('qwen3'): return 'messages'
    return 'responses'   # <-- BUG: free models land here
```

Right:
```python
    if m.startswith('qwen3'): return 'messages'
    if is_free_model(m): return 'chat'   # free = openai-compatible
    return 'chat'                        # all other non-GPT/Claude/Gemini → chat/completions
```
Why it matters: the primary client (Codex v0.145) speaks the **Responses API**
(`/v1/responses`). In free-only mode the proxy must translate Responses→Chat→Responses
and hit Zen `/chat/completions`, because Zen's `/responses` is GPT-only and 400s on free ids.

## FREE_ONLY enforcement recipe (verified working)
- Env `FREE_ONLY=yes` → filter `GET /v1/models` to ids containing "free".
- `FREE_MODEL_ALLOWLIST=big-pickle` → `big-pickle` is a stealth free model with NO
  "free" substring (Zen does not list it in the public catalog either).
- Reject paid model requests on `/v1/chat/completions`, `/v1/responses`, `/v1/messages`
  with OpenAI/Anthropic-shaped 400 envelope (`code: free_only_restricted`).
- `is_free_model()` helper: `'free' in id` OR id in allowlist. Strip `opencode/` prefix first.

## Verification recipe (run after any routing change)
```bash
B="Authorization: Bearer wrapper-local-key"
# 1. health shows free_only:true
curl -s http://127.0.0.1:9107/health
# 2. models list only free (+aliases)
curl -s -H "$B" http://127.0.0.1:9107/v1/models | python3 -m json.tool
# 3. RESPONSES path with free model MUST succeed (was 400 before fix)
curl -s -X POST http://127.0.0.1:9107/v1/responses -H "$B" \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-v4-flash-free","input":"Reply with exactly: OK","stream":false}'
# 4. paid model MUST be blocked (400 free_only_restricted)
curl -s -X POST http://127.0.0.1:9107/v1/responses -H "$B" \
  -d '{"model":"gpt-5.4-mini","input":"hi"}'
```
Live evidence (this session): step 3 returned `{"status":"completed",...}` after fix;
before fix returned `{"error":"Upstream request failed",code:400}`.

## Other gotchas found
- systemd `WorkingDirectory`/`EnvironmentFile` path must match real dir
  (`/root/wrapper/opencode`, NOT `/root/wrappers/opencode`). Mismatch = unit starts
  but loads wrong `.env` / module path.
- README "Score: 100/100" claims are unreliable if routing was never live-tested
  against the actual upstream. Always do step 3 above before claiming verified.
- Deprecated (2026-07-23): all `gpt-5/5.1/5.2-codex` series. Irrelevant in free-only
  mode but matters if wrapper later allows paid models.
- Privacy: Zen free models (incl. `big-pickle`, `deepseek-v4-flash-free`, etc.) MAY
  use submitted data to improve the model during their free period — do NOT send
  confidential data through the free tier.
