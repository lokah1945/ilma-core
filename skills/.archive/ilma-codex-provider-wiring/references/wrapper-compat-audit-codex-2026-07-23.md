# Wrapper Compat Audit — Codex (Responses API) | 2026-07-23

Condensed knowledge bank from a full Layer-1..7 audit of the three ILMA wrappers
(wrapper-nvidia-python, wrapper-nous, wrapper-opencode) for OpenAI Codex CLI
v0.145.0 compatibility. Driven by a master-prompt-style audit that ASSUMED codex
uses Chat Completions — which turned out to be WRONG.

## 0. Verify the protocol BEFORE trusting any spec
A task spec / master prompt may state the wrong protocol. Codex v0.145.0 uses
**OpenAI Responses API** (`wire_api = "responses"` → `/v1/responses`), NOT
`/v1/chat/completions`. Confirm with:
```bash
# (a) what wire_api does codex actually send?
grep -rE 'wire_api|base_url' /root/.codex/config.toml /root/.codex-homes/*/config.toml
# (b) which port is REALLY listening (config lies — service may bind elsewhere)
ss -ltnp 2>/dev/null | grep -E '910[0-9]'
# (c) live end-to-end — the only proof that matters
cd /tmp && timeout 150 codex exec -p nvidia-py --sandbox=read-only "list files in one line"
#     → look for streamed response + "tokens used N"; check wrapper log for
#        "[DBG responses] model=..." (NOT "[DBG chat]")
```
Empirical result 2026-07-23: nvidia-py @9101 and nous @9106 both serve codex via
`/v1/responses` and pass tool-loop live. opencode @9107 serves `/v1/responses` but
has gaps (below).

## 1. Port map (verified via ss, NOT config)
| Wrapper | Config says | Actually listening | Notes |
|---------|-------------|-------------------|-------|
| wrapper-nvidia-python | LISTEN_PORT=9101 | 127.0.0.1:9101 | ✅ match |
| wrapper-nous | LISTEN_PORT=9107 (service file) | 127.0.0.1:9106 | codex config points 9106 → MATCH (service file port is stale/irrelevant) |
| wrapper-opencode | LISTEN_PORT=9107 | 127.0.0.1:9107 | ✅ match |
| wrapper-nvidia (NodeJS) | 9100 | DEAD (no listener) | Phase-3 eliminasi target; Python fully replaces |
| wrapper-codex | — | 127.0.0.1:9103 | separate daemon managing codex subprocesses (not a model wrapper) |

Lesson: trust `ss -ltnp`, not the service-file `Environment=LISTEN_PORT=`.

## 2. opencode synthetic-Responses-SSE ordering bug (P1, Codex v0.145 hang)
`wrapper-opencode/src/main.py` `responses()` → for non-GPT families it builds a
synthetic Responses SSE in `gen()`:
```
response.created → response.in_progress → response.output_text.delta (FIRST) → response.completed
```
It emits `output_text.delta` **WITHOUT** first emitting `response.output_item.added`
+ `response.content_part.added`. Codex v0.145 throws `OutputTextDelta without active
item` and HANGS. (Identical root cause to the legacy-proxy bug the main skill documents
for `wrapper_nous.py` — but opencode's synthetic path was never fixed.)
FIX (mirror nous `ResponsesStreamer.start()`):
```python
# before first output_text.delta in gen():
yield emit("response.output_item.added", {"output_index":0,
    "item":{"id":"msg-1","type":"message","status":"in_progress","role":"assistant","content":[]}})
yield emit("response.content_part.added", {"item_id":"msg-1","output_index":0,
    "content_index":0,"part":{"type":"output_text","text":""}})
```
Also: synthetic `response.completed` omits `usage` (Codex may expect it) — add
`usage:{input_tokens,output_tokens}` parsed from upstream chat stream.

## 3. opencode auth-default gap (P1)
`_auth_check()` in opencode returns early (no auth) if `BEARER_TOKEN` env is empty.
If set, it enforces. Codex sends `experimental_bearer_token` — when BEARER_TOKEN is
set this works (verified: curl without token → 401). But empty-BEARER = open door.
Fix: require token when request carries an `authorization` header; warn if BEARER_TOKEN
unset.

## 4. opencode previous_response_id not handled
Unlike nous (`_RESPONSE_STORE`), opencode `responses_to_chat` rebuilds from the full
`input` array each call — relies on codex sending full history (verified: codex DOES
send full `input`, so low risk). nvidia-py likewise ignores `previous_response_id`
but codex client-side history makes it safe.

## 5. nvidia-py Responses handler — already codex-ready
`nvidia-python/src/responses_compat.py` `ResponsesHandler`:
- `input_to_messages` handles `function_call` + `function_call_output` ✓
- `convert_tools` drops `name:null` ✓
- streaming `stream_gen` emits full ordered events incl. `output_item.added` before
  delta (for text), `function_call` as accumulated `output_item.added` (no
  `function_call.delta` event — codex tolerates this; live tool-loop passed) ✓
- `reasoning` field → NIM `chat_template_kwargs`/`reasoning_effort` ✓
Verdict: COMPATIBLE, no P1 patches. Only optional: `previous_response_id` store
(low risk), `function_call.delta` event (low risk), CORS `add_middleware` (localhost
fine).

## 6. nous — most codex-compatible
`wrapper_nous.py` `ResponsesStreamer` is purpose-built for Codex v0.145:
`output_item.added` before delta, `function_call.delta`, `_RESPONSE_STORE` for
`previous_response_id`, CORS `*`, port 9106 matches codex config. COMPATIBLE, 0 patches.

## 7. Audit output format (reusable for future compat audits)
For each wrapper: Layer 1 (arch) → 2 (request lifecycle) → 3 (tool call) → 4
(streaming) → 5 (error) → 6 (auth) → 7 (target-agent gap, quantified). Then patch
plan (PATCH_ID/wrapper/layer/file/current/problem/solution/affected/dependency/
validation/risk/priority), validation plan (5 concrete steps), risk table, phase-gate.
Full example: `/root/task/REPORT_WRAPPER_COMPAT_CODEX_2026-07-23.md`.
