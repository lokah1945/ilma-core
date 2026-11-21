# OpenCode Zen Wrapper — Pitfalls & FREE_ONLY Pattern (2026-07-23)

## Source of truth
- Official doc: https://opencode.ai/docs/zen/#endpoints
- Base URL (CORRECT): `https://opencode.ai/zen/v1`
- WRONG base (NVIDIA NIM!): `https://integrate.api.OPENCODE.com` or `integrate.api.nvidia.com`

## Endpoint map (OpenCode Zen)
| Capability | Endpoint |
|------------|----------|
| OpenAI Responses | `{base}/responses` |
| Anthropic Messages | `{base}/messages` |
| Chat Completions | `{base}/chat/completions` |
| Models | `{base}/models` |

## Model format
- Doc format: `opencode/<model-id>` (e.g. `opencode/gpt-5.5`)
- Wrapper should strip `opencode/` prefix before proxying, OR accept bare id (`gpt-5.5`)

## Free models (suffix `-free`, price 0 upstream)
- `mimo-v2.5-free`, `laguna-s-2.1-free`, `nemotron-3-ultra-free`
- `deepseek-v4-flash-free`, `north-mini-code-free`
- Paid examples (BLOCKED if FREE_ONLY=yes): `gpt-5.5`, `claude-*`, `gemini-*`, `deepseek-v4-flash` (no -free)

## CRITICAL PITFALL: editable pip install → module namespace collision
**Symptom:** `wrapper-opencode` service logs `[wrapper-nvidia]` and proxies to `integrate.api.nvidia.com` even though `opencode/src/main.py` is correct OpenCode Zen code.

**Root cause:** `wrapper_nvidia` was once `pip install -e` → creates
`/usr/local/lib/python3.11/dist-packages/_editable_impl_wrapper_nvidia.pth`
which injects `/root/wrapper/nvidia-python` into `sys.path`.
Because `nvidia-python/src/` has `__init__.py` (formal package) but `opencode/src/`
has NO `__init__.py` (namespace package), Python ALWAYS resolves `import src.main`
to **nvidia-py**, never opencode.

**Debug recipe:**
```bash
python3 -c "import importlib.util; print(importlib.util.find_spec('src.main').origin)"
# → /root/wrapper/nvidia-python/src/main.py  ❌ (should be opencode)
```

**Fix:**
1. `rm -f /usr/local/lib/python3.11/dist-packages/_editable_impl_wrapper_nvidia.pth`
2. `touch /root/wrapper/opencode/src/__init__.py`  (make opencode `src` a formal package)
3. Restart service, verify: `curl /health` → `"base": "https://opencode.ai/zen/v1"`

**Rule:** NEVER `pip install -e` a wrapper under /root/wrapper — it pollutes sys.path
and collides with sibling wrappers sharing the `src` module name.

## systemd EnvironmentFile does NOT inject into process
Symptom: `OPENCODE_BASE_URL` set in `.env` but runtime `os.environ.get(...)` = None,
`/health` shows `base=None`.
Fix: `load_dotenv()` with explicit path at import time:
```python
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))
if not os.environ.get('OPENCODE_BASE_URL'):
    load_dotenv()
```

## Zen rejects brotli (Accept-Encoding: br)
Symptom: `400, message: Can not decode content-encoding: br`
Fix: set `"Accept-Encoding": "identity"` in proxy request headers (`_auth_headers`).

## FREE_ONLY dynamic detection (NO hardcoded allowlist)
- Do NOT hardcode a free-model list in `.env` or code.
- Detect via: (a) model id contains "free" substring, OR (b) upstream price = 0.
- Upstream `/v1/models` does NOT expose price fields → only substring "free" works.
- `is_free_model(m)`: `return 'free' in m.lower()`
- `model_allowed(m)`: if `FREE_ONLY=yes` and not `is_free_model(m)` → reject.
- nvidia-py: NO FREE_ONLY needed (NVIDIA NIM upstream is 100% free).
- nous: FREE_ONLY=yes (has `tencent/hy3:free` etc).
- opencode: FREE_ONLY=yes (Zen free = `-free` suffix).

## Verification checklist (opencode after fix)
```bash
curl /health        # base=https://opencode.ai/zen/v1, free_only=True
curl /v1/models     # only 5 *-free models, paid absent
curl -X POST /v1/responses -d '{"model":"opencode/deepseek-v4-flash-free","input":"hi"}'
                    # status:completed (when not rate-limited; Zen free = 429 sometimes)
```
