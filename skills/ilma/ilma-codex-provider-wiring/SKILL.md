---
name: ilma-codex-provider-wiring
description: Wire the OpenAI Codex CLI to a custom OpenAI-compatible inference provider that does NOT implement the Responses API (e.g. Nous Research, local LLM servers). Solves the catch-22 where Codex v0.144.x only speaks wire_api="responses" but the provider only serves /v1/chat/completions. Use when a user wants Codex to use the same model/provider as the current Hermes/ILMA session, or any chat-completions-only backend.
---

# Codex ↔ Chat-Only Provider Wiring (translation proxy)

## When to use
- User wants `codex` (OpenAI Codex CLI) to run against a custom provider that exposes OpenAI-style `/v1/chat/completions` but **not** `/v1/responses`.
- Typical trigger: "buat config codex di ~/.codex/config.toml arahkan ke <provider> dengan model yang saya pakai sekarang."
- Verified instance: **Nous Research** inference portal (`https://inference-api.nousresearch.com/v1`) with model `tencent/hy3:free` — the exact model the active ILMA/Hermes session uses.

## The catch-22 (verify before assuming)
Codex v0.144.5 **rejects `wire_api = "chat"`** ("no longer supported") and **requires `wire_api = "responses"`**.
But many OpenAI-compatible providers (Nous confirmed) return **404 on `/v1/responses`** and only implement `/v1/chat/completions`.

**Step 0 — Protocol probe (do this BEFORE writing config; user expects a breakdown first):**
```bash
# Anthropic/Responses protocol (what Codex needs):
curl -s -o /dev/null -w "%{http_code}\n" -X POST <base>/v1/responses \
  -H "Content-Type: application/json" -H "Authorization: Bearer <tok>" \
  -d '{"model":"<m>","input":"hi","max_output_tokens":5}'
# OpenAI chat protocol (what provider may only have):
curl -s -o /dev/null -w "%{http_code}\n" -X POST <base>/v1/chat/completions \
  -H "Content-Type: application/json" -H "Authorization: Bearer <tok>" \
  -d '{"model":"<m>","messages":[{"role":"user","content":"hi"}]}'
```
If responses→404 and chat→200: you MUST use a local translation proxy. Pointing `base_url` directly at the provider will fail at runtime.

## Workflow
1. **Backup first** (user directive: "backup dulu config lama"). Copy existing `~/.codex/config.toml` and `model_catalog.json` with a timestamped `.bak.<ts>` suffix.
2. Stand up a local proxy (see `scripts/nous_proxy.py` as a ready reference impl) on `127.0.0.1:<port>` (e.g. 9191). It must:
   - Accept `POST /v1/responses`, translate the Responses request body to a Chat Completions body, forward to the provider's `/v1/chat/completions`, and translate the reply back into a **Responses-shaped** object.
   - Read a FRESH auth token per request from the credential store (OAuth tokens expire ~1h; do NOT hardcode). For Nous: read `/root/.hermes/profiles/ilma/auth.json` → `providers.nous.access_token`.
   - Handle **streaming**: Codex opens an SSE stream and requires this EXACT ordered event sequence or it errors (`OutputTextDelta without active item`):
     `response.created` → `response.in_progress` → `response.output_item.added` → `response.content_part.added` → `response.output_text.delta` → `response.output_text.done` → `response.content_part.done` → `response.output_item.done` → `response.completed`.
   - **Reasoning-model fallback**: some models (e.g. `tencent/hy3:free`) put the answer in `reasoning` not `content` when `max_tokens` is truncated; proxy must use `content or reasoning`.
   - Bump `max_tokens` to >=1024 so the final content is not cut off before it appears.
   - Expose `GET /healthz` and proxy `GET /v1/models`.
3. **Persist the proxy** as a systemd user service (auto-restart, survives reboot). Unit at `/root/.config/systemd/user/nous-proxy.service`; `systemctl --user enable --now nous-proxy.service`. Kill any manually-backgrounded instance first to avoid port conflict.
4. **Write `config.toml`** pointing Codex at the proxy (template: `templates/config.toml.proxy`):
   - `model = "<provider_model>"`, `model_provider = "nous"` (any name)
   - `[model_providers.nous] base_url = "http://127.0.0.1:9191"`, `experimental_bearer_token = "sk-local-proxy"` (dummy; proxy injects real token), `wire_api = "responses"`.
   - Add `[projects."/root"]` / `[projects."/tmp"]` / `[projects."/path"]` with `trust_level = "trusted"` — Codex refuses to run outside a trusted dir ("Not inside a trusted directory").
5. **Model catalog: DYNAMIC discovery (preferred) vs STATIC override — CHOOSE ONE.**
   - **DYNAMIC (default, recommended for "dynamic discovery" / "model dipilih saat runtime"):** Do NOT set `model_catalog_json` at all. Codex then calls `GET <base_url>/v1/models` at startup and builds its model list LIVE from the wrapper (Nous upstream + curated fallback). Runtime switch: `codex -m <model_id>` (id MUST be one returned by `/v1/models`). Verified 2026-07-24 against wrapper-nous @9106: `codex exec --model poolside/laguna-s-2.1:free` AND `--model tencent/hy3:free` both returned correct output; `codex doctor` → `16 ok · 0 fail`.
   - **STATIC (only if you need frozen/rich `ModelInfo` metadata):** set `model_catalog_json = "/path/catalog.json"`. This OVERRIDES and FREEZES the list — Codex will NOT re-fetch `/v1/models`. Regenerate via `scripts/setup_nous_codex.py` (clone first existing entry; do NOT hand-build — Codex rejects missing fields like `supports_reasoning_summaries`). If you use `templates/config.toml.proxy`, REMOVE its `model_catalog_json` line for dynamic mode.
   - **Cosmetic-NO-LONGER (was: harmless):** with dynamic discovery Codex < v0.145 logged `Model metadata for '<id>' not found. Defaulting to fallback metadata` and still produced correct output. On **v0.145.0 this is now a hard decode-failure chain** (`missing field 'models'` → `'slug'` → `'base_instructions'` → full `ModelInfo`), and the warning is a real degraded-metadata path. **Fix it, do NOT leave it.** The clean fix keeps discovery dynamic (no static `model_catalog_json`): enrich the wrapper `/v1/models` payload so every model is a schema-complete Codex `ModelInfo`. Concrete recipe (template-clone, stays dynamic): `references/codex-dynamic-models-metainfo-2026-07-24.md` — load a real catalog entry as the metadata base, return BOTH `data` and `models` keys, and add the latent `get_token()`/`get_session()` defs if the `/v1/models` route NameErrors. Verified: zero warnings for `tencent/hy3:free` AND `poolside/laguna-s-2.1:free`.
6. **Verify end-to-end**: `codex exec --model <m> "Reply with exactly: PONG"` from a trusted dir (e.g. a git repo or one listed in `projects`). Expect the literal answer back. If you see reconnect/stream errors → SSE sequence is wrong. If config-load error about `wire_api` → you wrote `"chat"`.

## Pitfalls
- Writing `wire_api = "chat"` → Codex refuses ("no longer supported"). Always `"responses"` + proxy.
- Pointing `base_url` at the provider directly → 404 on `/v1/responses` at first `codex` call.
- Missing SSE ordering (`output_item.added`/`content_part.added` before `delta`) → `OutputTextDelta without active item`.
- Hardcoding an OAuth token → expires in ~1h; read live from credential store per request instead.
- `model_catalog.json` hand-built entry → schema validation error; clone template instead.
- Running `codex` from an untrusted cwd → "Not inside a trusted directory"; add the dir to `projects` or run from a git repo.
- Reasoning models returning `content: null` → proxy must fall back to `reasoning` field.

### STALE-REFERENCE CORRECTION (2026-07-23 → UPDATED 2026-07-25)
The verified instance below was REBUILT TWICE. Do NOT follow the old port/service file:
- **Old (stale, 2026-07-23):** proxy on `:9191`, unit `nous-proxy.service`.
- **Intermediate (stale, 2026-07-23):** proxy is `wrapper-nous` on `:9106`.
- **CURRENT (correct, 2026-07-25, mem_014 override):** canonical wrapper ports are
  **SEQUENTIAL, NO GAPS**: nvidia=**9101**, nous=**9102**, opencode=**9103**, blackbox=**9104**, model-registry=**9200**.
  The `:9106` / `:9107` / `:9100` / `:9910` ports in older docs/configs are VOID.
  Point Codex `base_url` at `http://127.0.0.1:9102` for nous (NOT `:9106`),
  `:9101` for nvidia-py, `:9103` for opencode, `:9104` for blackbox.

### PITFALL: port drift after mem_014 (2026-07-25)
Bos OVERRODE the wrapper port rule on 2026-07-24: **sequential 9101-9104 (NO gaps)**.
Old convention (nous=9106, opencode=9107, nvidia=9100/9910) is VOID.
**Always re-sync Codex configs to live ports before declaring "Codex wired":**
```bash
# 1. confirm live ports (never trust config)
for p in 9101 9102 9103 9104; do printf "port %s: " "$p"; curl -s -m4 -o /dev/null -w "%{http_code}\n" http://127.0.0.1:$p/health; done
# 2. grep ALL codex configs for stale ports
grep -rniE 'base_url.*910[0-9]' /root/.codex/config.toml /root/.codex-homes/*/config.toml
# 3. fix any 9106/9107/9100 -> 9102/9103/9101 respectively
```
This session found `config.toml` (nous 9106→9102), `nous` home (9106→9102),
`nvidia` home (9100→9101), `opencode` home (9107→9103) ALL stale and fixed.
Codex fails silently (connection refused) if its `base_url` points at a dead port.

### Pitfall: Codex sends `name:null` deferred/discovery tools → upstream 400
Codex (Responses API) sends ~2 tools shaped `{"type":"function","function":{"name":null,
"description":"...deferred tool discovery..."}}`. A chat/completions upstream (Nous) rejects
`tools[].function.name = null` → `400 "Provider returned error"`. The proxy MUST drop
tools whose `name` is null/empty before forwarding. wrapper-nous v2 already filters via
`if t.get("function", t).get("name")` — if you rebuild a proxy, replicate this or Codex
fails with the misleading 400.

### Clarification: "Codex error 400 from wrapper" is usually NOT a wrapper bug
The `400` from Nous upstream is almost always one of: (a) a `name:null` tool (above,
proxy-side fix), or (b) malformed `tools` array missing `parameters`/`type:object` when
yOU hand-craft a raw curl — Codex itself sends well-formed tools. Always reproduce with a
real Codex call + inspect the proxy's normalized payload before editing the proxy.

### Pitfall: `model_catalog_json` static override SILENTLY DISABLES dynamic model discovery
Most common mistake when the task is "dynamic discovery + runtime model selection": a stale `model_catalog_json = "..."` left in `config.toml`.

- Codex treats `model_catalog_json` as a HARD override. If present, it loads that file and does NOT call `GET /v1/models` at startup — so newly-added/updated upstream models never appear, and `codex -m <new_model>` fails with "model not found" / falls back to degraded metadata.
- The tell: `config.toml` has `model_catalog_json` set AND the user reports models are "stuck" or can't be switched. Fix: DELETE the `model_catalog_json` line (and the file if it exists only for Codex).
- Verified 2026-07-24: removing `model_catalog_json` from an existing `config.toml` made Codex fetch `GET http://127.0.0.1:9106/v1/models` live; `codex -m` then worked for every id in that response. `codex doctor` → `16 ok · 0 fail`.
- Runtime selection is INDEPENDENT of the catalog mechanism: `codex exec -m <model_id> "prompt"` picks the model per invocation. The id MUST exist in whatever catalog Codex loaded — so for dynamic selection the catalog MUST be dynamic (NO `model_catalog_json`).
- `wire_api = "responses"` is still required (Codex v0.145 rejects `chat`). `experimental_bearer_token` can be any value when the wrapper runs "open" (BEARER_TOKEN env unset) — `wrapper-local-key` matches `/root/wrapper/nous/.env.example` default and is future-proof if auth is later enabled.

### Pitfall: Codex `base_url` MUST include `/v1` prefix — else 404 `Unsupported: responses`

This is the **most common Codex↔wrapper-nous wiring break** and has a DIFFERENT signature from the "point base_url at provider" 404.

- Codex config: `base_url = "http://127.0.0.1:9106"` (NO `/v1`), `wire_api = "responses"`.
- Codex builds the request as `base_url + "/responses"` → `POST http://127.0.0.1:9106/responses`.
- `wrapper-nous` only registers `POST /v1/responses` (plus a catch-all `{path}`). The bare `/responses` falls into the catch-all → **404 with body `Unsupported: responses`**.
- Error string in Codex: `■ unexpected status 404 Not Found: Unsupported: responses, url: http://127.0.0.1:9106/responses`.

**Diagnostic (reproduce before editing anything):**
```bash
# Broken path (what Codex sends without /v1) → 404
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:9106/responses -d '{}'
# Correct path → 400 (route exists, needs auth/payload) or 200 if valid
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:9106/v1/responses -d '{}'
```
404 on `/responses` + 400/200 on `/v1/responses` = **prefix bug, not a provider/wrapper capability bug**.

**Fix (config-only, no restart needed):**
```toml
[model_providers.nous]
base_url = "http://127.0.0.1:9106/v1"   # ← add /v1
experimental_bearer_token = "sk-…"
wire_api = "responses"
```

**Why this is easy to miss:** the wrapper DOES serve the Responses API, so you'd assume the path is fine. The trap is purely the missing `/v1` segment between host:port and `/responses`. Any OpenAI-SDK-based client that appends `/responses` / `/chat/completions` / `/messages` to `base_url` needs the `/v1` prefix present in `base_url` when the proxy mounts routes under `/v1/...`.

**Optional robustness (wrapper-side, only if you also control the proxy):** add alias routes so the proxy answers both `/responses` and `/v1/responses`:
```python
@app.post(["/responses", "/v1/responses"])
async def responses_endpoint(request: Request): ...
```
This prevents the same class of bug for any future client that forgets `/v1`. Apply only if you intend the wrapper to serve prefix-less OpenAI-SDK clients; otherwise keep the strict `/v1` mount and fix the client config (preferred — least surprise).

### Pitfall: 400 on tool round-trip (2nd turn) from DOUBLE-ENCODED `arguments` ← most common "Codex terhenti / 400" after wiring works
Once 1st-turn + SSE ordering are fixed, Codex still dies on the **tool-result round-trip** with:
`■ {"error":{"message":"This request is not valid... Provider returned error","type":"api_error","code":400}}`
This is almost always the proxy, NOT Nous. Root cause in `responses_to_chat()`:

```python
# WRONG — Codex sends arguments as a JSON STRING already
msgs.append({"role":"assistant","content":None,
             "tool_calls":[{"id":it.get("call_id"),"type":"function",
                            "function":{"name":it.get("name"),
                                        "arguments": json.dumps(it.get("arguments", {}))}}]})
# json.dumps("{\"path\":\"/x\"}")  →  "\"{...}\""  (double-encoded string)
# Nous receives arguments as a string-in-string → 400.
```

**Fix — type-check before encoding:**
```python
raw_args = it.get("arguments", "")
args_out = raw_args if isinstance(raw_args, str) else json.dumps(raw_args)
msgs.append({"role":"assistant","content":None,
             "tool_calls":[{"id":it.get("call_id"),"type":"function",
                            "function":{"name":it.get("name"),"arguments":args_out}}]})
```

**Reproduce the exact 2nd-turn payload (isolate before editing proxy):**
```bash
# Codex 2nd turn sends a FULL input array (NO previous_response_id) with
# [message(user), function_call, function_call_output]:
curl -s -X POST http://127.0.0.1:9106/v1/responses -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-placeholder" -d '{
    "model":"tencent/hy3:free",
    "input":[{"type":"message","role":"user","content":[{"type":"input_text","text":"write file /tmp/zz.txt HI"}]},
             {"type":"function_call","call_id":"call_abc","name":"write_file","arguments":"{\"path\":\"/tmp/zz.txt\",\"content\":\"HI\"}"},
             {"type":"function_call_output","call_id":"call_abc","output":"file written"}],
    "tools":[{"type":"function","name":"write_file","description":"w",
              "parameters":{"type":"object","properties":{"path":{"type":"string"},"content":{"type":"string"}},"required":["path","content"]}}],
    "tool_choice":"auto","stream":false,"max_output_tokens":300}'
# 400 here ⇒ inspect the proxy-normalized payload (print chat_body["messages"]) — you'll see arguments double-encoded.
```

**Debugging chain that resolved "Codex terhenti" (4 ordered fixes, all in `wrapper_nous.py`):**
1. `response.completed` emitted twice (one with empty `usage`) → Codex `missing field input_tokens`. Fix: idempotent `done()` + normalize `prompt_tokens→input_tokens`, `completion_tokens→output_tokens`.
2. Missing `total_tokens` in `usage` → Codex `missing field total_tokens`. Fix: `_normalize_usage()` returns `input+output+total`.
3. SSE ordering: `output_text.delta` before `output_item.added` → Codex `OutputTextDelta without active item` (hangs). Fix: `start()` emits `output_item.added`+`content_part.added`; `done()` emits `output_text.done`+`content_part.done`+`output_item.done` per item.
4. Tool item never closed + double-encoded `arguments` → Codex 400 on round-trip. Fix: `tool_delta()` emits `output_item.added` (type=function_call) + `done()` closes every tracked tool; AND the `arguments` type-check above.
Full transcripts & the verified e2e result are in `references/codex-roundtrip-400-arguments-2026-07-23.md`.

**Telemetry tip:** if `wrapper-nous` `/metrics` shows `total_requests: 0` while Codex is "running", Codex is NOT hitting the proxy (it's stuck at startup/auth or a different path) — don't blame the proxy. Reproduce with the curl above to confirm the proxy path works, then check Codex config/`base_url`.

### Multi-wrapper sequential verification protocol (2026-07-23, Bos mandate)
When the task is "make ALL wrappers work as Codex custom providers" (nous, nvidia-py, opencode — and later Claude Code / OpenCode CLI against the same set), do NOT parallel-test all at once. The mandated order:
1. **Focus ONE wrapper** (start with `wrapper-nous`). Run full Codex e2e — text AND tool use (`codex exec "create file X with exact text Y"`) — until fully green (exit 0 + file created).
2. **Propagate every fix** discovered in step 1 to the OTHER wrappers **BEFORE** testing them (prevents the same error recurring when they become Codex providers).
3. Then test the next wrapper (nvidia-py), then opencode — each must reach the same green state.
4. Only after ALL Codex e2e are green, repeat the entire sequence for **Claude Code CLI**, then **OpenCode CLI**.
Skipping ahead (testing wrapper N before wrapper 1 is proven) or testing all 4 in parallel wastes cycles and hides which wrapper caused which failure.

### Pitfall: opencode ≠ nvidia — SEPARATE wrappers, never conflate
`wrapper-opencode` is an **OpenCode-cloud proxy** (API keys `OPENCODE_API_KEY_1/2/3`, base `https://integrate.api.OPENCODE.com`). `wrapper-nvidia-python` is a **NVIDIA NIM proxy** (100% free upstream, no `OPENCODE_API_KEY_*`). They are DIFFERENT backends.
- If `opencode /v1/models` returns NVIDIA-style model ids, that is the OpenCode-cloud **Zen fallback** (OpenCode Zen backend is NVIDIA-backed) — NOT proof that "opencode is nvidia". The `fallback_all` list in `opencode/src/main.py` even lists OpenCode Zen free models (`mimo-v2.5-free`, `nemotron-3-ultra-free`, `deepseek-v4-flash-free`).
- Their CODE STRUCTURE differs: opencode has `responses_to_chat()` inline in `main.py`; nvidia-py has a separate `src/responses_compat.py`. Fixes do NOT copy-paste verbatim — read each file.
- Conflating them (e.g. testing opencode with a NVIDIA model and calling it "nvidia") is a **fatal classification error** — verify which backend each wrapper proxies before asserting anything.

### Pitfall: FREE_ONLY enforcement — no hardcoded allowlist, nous+opencode ONLY
- `FREE_ONLY=yes` belongs in `.env` of **wrapper-nous** and **wrapper-opencode** ONLY. `wrapper-nvidia-python` needs NO `FREE_ONLY` (NVIDIA NIM upstream is 100% free by default — Bos explicit).
- Do NOT add `FREE_MODEL_ALLOWLIST` with hardcoded model ids — **Bos rejected this**. Free detection must derive from upstream: model id contains `"free"` OR upstream token price = 0. Since upstream `/v1/models` metadata carries NO price field, the operative signal is the `"free"` substring in the model id (already implemented in `is_free_model`).
- **Verify enforcement** after setting `FREE_ONLY=yes`:
  (a) a free model (e.g. `tencent/hy3:free` for nous) → 200 OK;
  (b) a paid model (e.g. `nvidia/llama-3.3-nemotron-super-49b-v1`) → 400 `blocked by FREE_ONLY=yes`;
  (c) `GET /v1/models` lists ONLY free ids (`all_free: True`).
- **NEVER test a FREE_ONLY wrapper with a paid model** (e.g. nemotron). Doing so invalidates the test and hides whether FREE_ONLY actually filters. Use a real free model from the allowlist-by-name.

### Pitfall: restarting a uvicorn wrapper can leave an orphan process holding the port
`systemctl --user restart wrapper-X.service` may hang in `deactivating` if a stale uvicorn PID (started before the unit existed) still holds the port. Symptom: `systemctl is-active` → `deactivating`, port shows FREE in `ss` but service never reaches `active`. Fix: kill the holder by PID (read `/proc/*/cmdline` for the port arg — do NOT `pkill -f "port 9101"` because that pattern matches the shell running the command itself and self-kills with exit -9), then `systemctl reset-failed` + `start`.

### CRITICAL Pitfall: editable pip install creates `.pth` that hijacks `src` module import
If ANY wrapper was ever `pip install -e .` (editable), it writes a `.pth` file (e.g. `/usr/local/lib/python3.11/dist-packages/_editable_impl_wrapper_nvidia.pth`) that injects its root dir into `sys.path`. Consequence: **every wrapper with `src/main.py` + `src/__init__.py` becomes a formal package named `src`**, and Python resolves `import src.main` to the **FIRST** `src` package found in `sys.path` — NOT the one in the wrapper's own cwd.

**Symptom (fatal, hard to spot):** `wrapper-opencode` service logs `[wrapper-nvidia]` and proxies to `integrate.api.nvidia.com` even though its code says OpenCode Zen. Root cause: `wrapper_nvidia` editable `.pth` put `/root/wrapper/nvidia-python` on `sys.path`; its `src/` has `__init__.py` (formal package); `opencode/src/` had NO `__init__.py` (namespace) → `src.main` always resolved to nvidia-py.

**Detection (run before trusting any wrapper's identity):**
```bash
# Does any .pth inject a wrapper path?
ls /usr/local/lib/python3.11/dist-packages/*.pth 2>/dev/null | xargs grep -l "wrapper" 2>/dev/null
# Which src.main will Python actually load?
cd /root/wrapper/opencode && python3 -c "import importlib.util; print(importlib.util.find_spec('src.main').origin)"
# → if it prints /root/wrapper/nvidia-python/src/main.py, you have the conflict
```

**Fix (apply once, persistent):**
1. `rm -f /usr/local/lib/python3.11/dist-packages/_editable_impl_wrapper_*.pth` (remove all editable wrapper .pth files)
2. Add `src/__init__.py` to EVERY wrapper that runs `uvicorn src.main:app` (so each is a distinct formal package; the cwd/PYTHONPATH still disambiguates at launch, but the namespace-vs-formal trap is gone)
3. NEVER `pip install -e` a wrapper. Use `WorkingDirectory=` + `Environment=PYTHONPATH=` in the systemd unit instead.
4. After fix, re-verify: `importlib.util.find_spec('src.main').origin` must point to the wrapper's OWN `src/main.py`, and `/health` must report the correct `base` (e.g. `https://opencode.ai/zen/v1` for opencode, not None/NVIDIA).

### Pitfall: opencode synthetic Responses SSE has the SAME ordering bug as the legacy proxy (P1, Codex v0.145 hang)
`wrapper-opencode/src/main.py` `responses()` builds a **synthetic** Responses SSE in `gen()` for non-GPT families (translating chat→Responses). It emits `response.created` → `response.in_progress` → **`response.output_text.delta` (first, with NO `output_item.added`/`content_part.added` before it)** → `response.completed`. Codex v0.145 throws `OutputTextDelta without active item` and HANGS — the identical root cause documented above for `wrapper_nous.py`, but opencode's synthetic path was never fixed.
FIX (mirror `ResponsesStreamer.start()` in wrapper_nous.py): before the first `output_text.delta`, emit `response.output_item.added` (output_index=0, item message in_progress) + `response.content_part.added`. Also: synthetic `response.completed` omits `usage` → add `usage:{input_tokens,output_tokens}` from the upstream chat stream.
Companion gaps in opencode: (a) `_auth_check` returns early (no auth) when `BEARER_TOKEN` env is empty — require token when the request carries an `authorization` header; (b) `previous_response_id` not stored (unlike nous `_RESPONSE_STORE`) — low risk because Codex sends full `input` client-side.
Full audit + empirical proof: `references/wrapper-compat-audit-codex-2026-07-23.md`.

### VERIFY-THE-PROTOCOL FIRST (don't trust the task spec)
A master-prompt / audit spec may state the **wrong** protocol for the target agent. Codex v0.145.0 uses **OpenAI Responses API** (`wire_api="responses"` → `/v1/responses`), NOT `/v1/chat/completions`. Confirm empirically BEFORE writing any patch:
```bash
grep -rE 'wire_api|base_url' /root/.codex/config.toml /root/.codex-homes/*/config.toml   # → wire_api = "responses"
ss -ltnp 2>/dev/null | grep -E '910[0-9]'                                                  # real listening port (config lies)
cd /tmp && timeout 150 codex exec -p nvidia-py --sandbox=read-only "list files in one line"  # live proof
# check wrapper log for "[DBG responses]" (not "[DBG chat]")
```
2026-07-23 audit result: nvidia-py (@9101) + nous (@9106) are COMPATIBLE with codex end-to-end (live tool-loop passed); opencode (@9107) needs the two P1 fixes above. Full report: `/root/task/REPORT_WRAPPER_COMPAT_CODEX_2026-07-23.md`.

### Pitfall: OpenCode Zen `_zen_family` must route ALL models to `responses` or tool calls are silently dropped
`wrapper-opencode` proxies to OpenCode Zen (`https://opencode.ai/zen/v1`). Zen's OpenAI-compatible **Responses API** (`/responses`) supports tool calls for ALL models. BUT the wrapper's `_zen_family(model)` originally returned `"chat"` for any non-`gpt-*` model (e.g. `nemotron-*`, `deepseek-*`, `mimo-*`). The `chat` branch translates Responses→Chat→Responses and **loses the `function_call` item** — Codex gets a text-only reply and never invokes the tool (exit 0, no file created).

**Fix:** `_zen_family()` must return `"responses"` for every model except `claude-*` (→`messages`) and `gemini-*` (→`google`):
```python
if m.startswith('claude-'): return 'messages'
if m.startswith('gemini-'): return 'google'
return 'responses'   # ← was 'chat'; this is the fix
```

**Also required for Zen:**
- `_auth_headers()` MUST send `"Accept-Encoding": "identity"` — Zen rejects `br`/`gzip` with `400 Can not decode content-encoding: br`.
- `OPENCODE_BASE_URL` in `.env` MUST be `https://opencode.ai/zen/v1` (NOT `https://integrate.api.OPENCODE.com` — that is the NVIDIA-backed fallback and returns NVIDIA model ids, which misleads you into thinking opencode "is nvidia").
- Zen free models (`mimo-v2.5-free`, `laguna-s-2.1-free`, `nemotron-3-ultra-free`, `deepseek-v4-flash-free`, `north-mini-code-free`) are **frequently rate-limited (429) or return `Internal server error` at the Zen upstream**. This is NOT a wrapper bug. Verify the wrapper itself with direct curl (tools → expect `function_call` in `output`), then accept that Codex e2e may fail purely on Zen quota. Wrapper error handling must pass Zen errors through as JSON (status + body), never return a bare 500.
- `model_catalog.json` for the Codex home MUST contain a schema-complete entry per Zen free model (clone an existing entry; missing fields like `shell_type`, `base_instructions` cause Codex catalog-parse errors). Set `supports_tool_calls: true`.

**End-to-end check for opencode as a Codex provider:**
```bash
# 1. wrapper identity correct?
curl -s http://127.0.0.1:9107/health | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['base'],d['free_only'])"
#    → must be https://opencode.ai/zen/v1 + True
# 2. free models only?
curl -s -H "Authorization: Bearer $TOK" http://127.0.0.1:9107/v1/models | python3 -c "import sys,json;d=json.load(sys.stdin);print([m['id'] for m in d['data']])"
#    → 5 Zen free ids, no paid
# 3. tool call forwarded? (direct, bypasses Codex quota)
curl -s -X POST http://127.0.0.1:9107/v1/responses -H "Authorization: Bearer $TOK" -H "Content-Type: application/json" \
  -d '{"model":"opencode/mimo-v2.5-free","input":"use calculator","tools":[{"type":"function","name":"calculator","description":"add","parameters":{"type":"object","properties":{"a":{"type":"number"},"b":{"type":"number}},"required":["a","b"]}}]}' \
  | python3 -c "import sys,json;d=json.load(sys.stdin);print([o.get('type') for o in d.get('output',[])])"
#    → must include 'function_call' (proves wrapper forwards tools; if missing, _zen_family bug)
```

### Pitfall: Docker overlay-fs — `patch` tool edits may NOT persist to the running process
On hosts where `/root` is a Docker overlay mount, edits made via the `patch` tool can report success but fail to reach the layer the process actually reads (a later `read_file` shows the old code; `grep -c` on disk = 0). Symptom specific to this skill: you patch `get_model_meta`/`/v1/models` in `wrapper_nous.py`, restart the wrapper, but `/v1/models` still returns the 9-field minimal entries — discovery "didn't take."
**Workaround that worked:** write the patch via a terminal `python3` heredoc (`cat > /tmp/x.py <<'PY' … open(p).write(s) …`) and CONFIRM persistence with terminal `md5sum` / `grep -c` on disk — do NOT trust the `patch` tool's "success" message here, and do NOT trust `read_file` (may read a different overlay layer). Restart the wrapper only after `grep -c` on disk > 0. Full recipe: `references/codex-dynamic-models-metainfo-2026-07-24.md` (see "Pitfall discovered: Docker overlay-fs persistence").

### Pitfall: 401 after clean discovery = upstream key, NOT a wiring bug
Once `/v1/models` is schema-clean and `codex exec` selects the model without warnings, you may still get:
`401 Unauthorized: Your API key is invalid, blocked or out of funds … portal.nousresearch.com`.
That is `NOUS_API_KEY` in `/root/wrapper/nous/.env` empty/expired — an **upstream auth** failure, not a Codex/wrapper transport problem. Fix the wrapper's `.env`, not `config.toml`. (Do not waste cycles re-patching the proxy for a 401 that is really missing credentials.)

## Files produced / referenced
- `scripts/nous_proxy.py` — **RETIRED** (2026-07-23): replaced by `wrapper-nous` FastAPI
  proxy @ :9106. Quarantined to `archive_garbage/` under `/root/wrapper/nous/`.
- `scripts/setup_nous_codex.py` — regenerates `config.toml` + `model_catalog.json` (re-run to resync catalog).
- `templates/config.toml.proxy` — known-good Codex config pointing at the proxy.
- `/root/.config/systemd/user/wrapper-nous.service` — persistence unit (**NOT** `nous-proxy.service`, deleted).
- `references/nous-portal-2026-07-22.md` — session-specific verified probes & live-test transcript.
- `references/codex-roundtrip-400-arguments-2026-07-23.md` — full 2nd-turn 400 debug chain + e2e proof.
- `references/codex-dynamic-models-metainfo-2026-07-24.md` — **dynamic** `/v1/models` enrichment so Codex v0.145 stops logging `metadata not found` / `missing field` WITHOUT a static `model_catalog.json`. Template-clone recipe, `models`+`data` return keys, latent `get_token`/`get_session` fix, overlay-fs persistence pitfall, 401-out-of-scope note.
- `references/multi-wrapper-codex-freeonly-2026-07-23.md` — wrapper matrix (nous/nvidia-py/opencode are SEPARATE), FREE_ONLY rules (nous+opencode only, no allowlist), sequential verification protocol, root-cause bug list.
- `references/opencode-zen-wrapper-2026-07-23.md` — OpenCode Zen condensed knowledge bank: correct base URL, free-model list, `Accept-Encoding: identity` requirement, `_zen_family` routing fix, editable-pip `.pth` module-conflict trap, verification recipe.
- `references/wrapper-compat-audit-codex-2026-07-23.md` — full Layer-1..7 wrapper-compat audit for Codex (Responses API): port map (via `ss`, not config), opencode synthetic-SSE ordering bug + auth-default gap, nvidia-py/nous COMPATIBLE verdict, reusable audit output format. Pair with `/root/task/REPORT_WRAPPER_COMPAT_CODEX_2026-07-23.md`.
- `references/opencode-nvidipy-codex-patches-2026-07-23.md` — concrete patch diffs (CORS, previous_response_id store, function_call.delta, G8/G9/G10/G11) + live validation recipe + the upstream-429 unit-test technique for G11. Pair with the IMPLEMENTATION STATUS block below.
**Current canonical proxy:** `/root/wrapper/nous/wrapper_nous.py` (FastAPI, port 9106,
`wrapper-nous.service`). Codex `base_url = http://127.0.0.1:9106`.

## IMPLEMENTATION STATUS — patches APPLIED & validated (2026-07-23)

The gaps documented in the pitfalls above were NOT left as analysis. All were implemented and
verified live. Summary (full diffs + validation recipe in `references/opencode-nvidipy-codex-patches-2026-07-23.md`):

| Wrapper | Fix | Validation |
|---------|-----|------------|
| nvidia-py (9101) | CORS middleware added; `_RESPONSE_STORE` + `previous_response_id` inject/store; `function_call.delta` stream events | `codex exec -p nvidia-py` text + tool-loop → exit 0, no hang |
| opencode (9107) | G8: `output_item.added`+`content_part.added` BEFORE first `output_text.delta` (no-hang); G9: `usage` in `response.completed`; G10: 401 on wrong/empty token when `BEARER_TOKEN` set; G11: `_RESPONSE_STORE` + inject | `codex exec -p opencode` text + tool-loop → exit 0, NO hang; curl wrong/no token → 401; unit-test G11 → injected |
| nous (9106) | none — already Codex-v0.145-ready | unchanged, compatible |

**Verdict: all 3 wrappers are FULLY COMPATIBLE with `codex-cli` (Responses API) after patches.**
Backup: `/root/task/backups/*_20260723_210136.py`. `py_compile` clean; Pyright LSP warnings are false positives.

**Reusable validation technique when upstream is rate-limited (429):** you cannot always run a full
`codex exec` against opencode because OpenCode Zen free models 429. To still verify `previous_response_id`
logic, stub `proxy_request` + `pool`, import `src.main`, and call `responses_to_chat()` directly with a
seed in `_RESPONSE_STORE` (see the reference file's step 5). This isolates wrapper logic from upstream quota.

**systemctl restart timeout is cosmetic:** `systemctl --user restart wrapper-X.service` may hit the
60s caller timeout even on success. Confirm via `systemctl --user is-active wrapper-X.service` +
`ss -ltnp | grep <port>` instead of trusting the timeout.

## Relation to other skills
Complementary (not overlapping) with `autonomous-ai-agents > codex` (delegating coding tasks to Codex) and `ilma-codex-stdio-agent` (spawning the Codex binary as a subprocess). This skill owns the *provider/transport wiring*; those own *orchestration*.
