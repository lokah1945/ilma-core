# Codex-Compat Patches — Implementation & Validation (2026-07-23)

Companion to the SKILL.md "opencode synthetic Responses SSE P1" + "nvidia-py" pitfalls.
This session did NOT stop at analysis: all 8 identified patches were APPLIED and validated.

## Patch inventory (all DONE)

### wrapper-nvidia-python (src/main.py, src/responses_compat.py) — port 9101
1. **CORS (P3):** in `create_app()`, after `app = FastAPI(...)`:
   ```python
   app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
   ```
   (import already present: `from fastapi.middleware.cors import CORSMiddleware`)
2. **previous_response_id (P2):** module-level `_RESPONSE_STORE: Dict[str, list] = {}` in `responses_compat.py`.
   In `handle_responses_api`, after `model = self.resolve_target_model(...)`:
   ```python
   prev = body.get('previous_response_id')
   if prev and prev in _RESPONSE_STORE:
       stored = _RESPONSE_STORE[prev]
       cur = body.get('input')
       if isinstance(cur, list): body['input'] = stored + cur
       elif isinstance(cur, str): body['input'] = stored + [{'role':'user','content':cur}]
   ```
   In `translate_to_nim` non-stream branch, store after `respond_non_streaming`:
   ```python
   rid_store = resp_obj.get('id')
   if rid_store:
       from .main import input_to_messages
       try:
           _RESPONSE_STORE[rid_store] = input_to_messages(chat_body, model)
           if len(_RESPONSE_STORE) > 200: _RESPONSE_STORE.pop(next(iter(_RESPONSE_STORE)))
       except Exception: pass
   ```
3. **function_call.delta (P3):** in `stream_gen` tool-call loop, when a new tool acc is created, emit
   `response.output_item.added` (type=function_call, status=in_progress) BEFORE accumulating, then emit
   `response.function_call.delta` for each name/arguments chunk. At end, emit `response.output_item.done`
   per tool. (Mirrors `wrapper_nous.py` `ResponsesStreamer.tool_delta`.)

### wrapper-opencode (src/main.py) — port 9107
4. **G8 (P1, hang fix):** in `responses()` synthetic `gen()`, BEFORE the first `output_text.delta`, emit
   `response.output_item.added` (output_index=0, item message in_progress) + `response.content_part.added`.
   At end emit `output_text.done` + `content_part.done` + `output_item.done`, then `response.completed`
   (now includes `usage:{input_tokens,output_tokens}` parsed from the upstream chat stream — G9 fix).
5. **G10 (P1, auth):** `_auth_check` — when `BEARER_TOKEN` is set, require a matching token:
   ```python
   if not BEARER_TOKEN:
       if request.headers.get("authorization") or request.headers.get("x-api-key"):
           logger.warning("[auth] BEARER_TOKEN unset but client sent credentials — accepting open (insecure)")
       return
   auth = request.headers.get("authorization","") or request.headers.get("x-api-key","")
   token = auth.replace("Bearer ","",1).strip()
   if not token or token != BEARER_TOKEN:
       raise HTTPException(401, {"error":{"type":"authentication_error","message":"Unauthorized"}})
   ```
6. **G11 (P2, previous_response_id):** module-level `_RESPONSE_STORE: dict = {}`. In `responses_to_chat`,
   prepend stored msgs if `previous_response_id` present. In `responses()` non-stream branch, store
   `chat_body["messages"]` under `resp_obj["id"]` (bounded to 200 entries).

### wrapper-nous (port 9106) — NO PATCH NEEDED
Already purpose-built for Codex v0.145 (output_item.added before delta, function_call.delta,
_RESPONSE_STORE, CORS, port 9106 matches config). Left unchanged.

## Validation recipe (run AFTER patching + `systemctl --user restart`)

```bash
# 1. nvidia-py text + tool-loop (proves P2/P3 live)
cd /tmp && timeout 150 codex exec -p nvidia-py --sandbox=read-only "Read /tmp/wr.json and count lines"
#   → exit 0, tool-loop: function_call → result → multi-turn. No hang.

# 2. opencode text (proves G8 no-hang)
timeout 120 codex exec -p opencode --sandbox=read-only "Say hello in one word"
#   → exit 0, full response, NO hang.

# 3. opencode tool-loop (proves G8 streaming + function_call end-to-end)
timeout 150 codex exec -p opencode --sandbox=read-only "Read /tmp/wr.json and tell me how many lines it has"
#   → exit 0, file read via tool, answer returned.

# 4. opencode auth (G10)
TOK=$(grep '^BEARER_TOKEN=' /root/wrapper/opencode/.env | cut -d= -f2- | tr -d '"')
curl -s -o /dev/null -w "wrong->%{http_code}\n" -X POST http://127.0.0.1:9107/v1/responses \
  -H 'Authorization: Bearer WRONG' -H 'Content-Type: application/json' -d '{"model":"gpt-5.4-mini","input":"hi"}'
curl -s -o /dev/null -w "notoken->%{http_code}\n" -X POST http://127.0.0.1:9107/v1/responses \
  -H 'Content-Type: application/json' -d '{"model":"gpt-5.4-mini","input":"hi"}'
#   → both 401 when BEARER_TOKEN set.

# 5. G11 previous_response_id (unit-test, because Zen upstream is 429-rate-limited)
cat > /tmp/t.py <<'PY'
import sys, asyncio
sys.path.insert(0, '/root/wrapper/opencode')
import src.main as m
async def fake_proxy(*a, **k): return 200, {"id":"c","choices":[{"message":{"role":"assistant","content":"ok"}}],"usage":{"prompt_tokens":1,"completion_tokens":1}}
m.proxy_request = fake_proxy
class P:
    def acquire(self): return {"key":"k"}
    def release(self,k): pass
    @property
    def total_keys(self): return 1
    @property
    def available_keys(self): return 1
m.pool = P()
class R:
    def __init__(s,b): s._b=b; s.headers={"authorization":"Bearer x"}
    async def json(s): return s._b
    @property
    def url(s):
        class U: path="/v1/responses"
        return U()
async def run():
    m._RESPONSE_STORE["resp_test123"]=[{"role":"user","content":"remember X"}]
    cb=m.responses_to_chat({"model":"gpt-5.4-mini","previous_response_id":"resp_test123","input":"what?"})
    assert cb["messages"][0]["content"]=="remember X"
    print("G11_OK")
asyncio.run(run())
PY
python3 /tmp/t.py && rm -f /tmp/t.py
#   → prints G11_OK (previous_response_id injected into messages).
```

## Notes
- Backups before edit: `/root/task/backups/{nvidia-python_main,nvidia-python_responses_compat,opencode_main}_20260723_210136.py`
- `py_compile` passes on all three files. Pyright LSP warnings on dict-assignment / lazy-import are FALSE POSITIVES.
- `systemctl --user restart wrapper-X.service` may time out in the calling terminal (60s) even though it
  succeeds — verify with `systemctl --user is-active` + `ss -ltnp | grep <port>` rather than trusting the timeout.
- Full narrative report: `/root/task/REPORT_WRAPPER_COMPAT_CODEX_FINAL_2026-07-23.md`
