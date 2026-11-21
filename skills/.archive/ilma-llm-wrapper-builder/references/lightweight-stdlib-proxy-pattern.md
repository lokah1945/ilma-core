# Lightweight LLM Proxy Pattern (pure Python stdlib, single file)

Captured from the `wrapper-nous` build (2026-07-22). Bos explicitly required the
SIMPLE concept — **NOT** the heavy Node.js/FastAPI wrapper-nvidia shape
(key_pool + metrics.db + dashboard + MongoDB SOT). Use this when Bos says
"pakai konsep yang sama seperti sebelumnya" or "jangan seperti wrapper-nvidia".

## When to use this variant

- Provider exposes ONLY OpenAI `chat/completions` but clients speak OTHER wire
  formats (OpenAI **Responses** API for Codex, **Anthropic `/v1/messages`** for
  Claude Code).
- Bos wants a small, auditable, single-file proxy (no build step, no deps).
- Token/credential is read fresh per-request from a local JSON (e.g. Hermes
  `auth.json`), so OAuth expiry is handled automatically.

## Architecture: 1 port, path-based dispatch

```
Client A (Codex)     -> POST /v1/responses        -> [Responses->chat]  -> upstream
Client B (Claude CD) -> POST /v1/messages         -> [Anthropic->chat]  -> upstream
Client C (OpenAI SDK)-> POST /v1/chat/completions -> pass-through       -> upstream
GET /v1/models        -> proxy upstream model list
GET /healthz          -> {"ok": true}
```

All three translate to the SAME upstream `POST /v1/chat/completions`. The proxy
is the ONLY thing that knows the client format — upstream stays dumb.

**Why one port:** Bos asked "port yang sama bisa handle request keduanya" (mirip
wrapper-nvidia yang 1 port untuk 2 format). Auto-detect by `self.path`, not by
separate listeners.

## Wire-API reality (clients)

| Client | Wire API | Required config |
|--------|----------|-----------------|
| Codex v0.144.5 | OpenAI **Responses** (`wire_api="responses"`) | `base_url` -> proxy, `model="tencent/hy3:free"` |
| Claude Code | **Anthropic** `/v1/messages` | `ANTHROPIC_BASE_URL` -> proxy, `ANTHROPIC_API_KEY` dummy |
| OpenAI SDK | Chat Completions | `base_url` -> proxy |

If the client's native endpoint is missing upstream (Nous returns 404 on
`/v1/responses` and `/v1/messages`), the proxy MUST translate — there is no
pass-through option for those paths.

## Anthropic -> OpenAI request mapping

| Anthropic field | OpenAI mapping |
|-----------------|---------------|
| `system` (string or `[{text}]`) | one `{"role":"system","content":...}` per entry |
| `messages[].content` = string | `{"role", "content": string}` |
| `content[].type=text` | joined into content text |
| `content[].type=image` | `{"type":"image_url","image_url":{"url":"data:<media>;base64,<data>"}}` |
| `content[].type=thinking` | `reasoning_content` (preserved) |
| `content[].type=tool_use` | `tool_calls[]` (id, type:function, function{name, arguments=json.dumps(input)}) |
| `content[].type=tool_result` | SEPARATE `{"role":"tool","tool_call_id":..., "content": text}` |
| `tools[].input_schema` | OpenAI `function.parameters` -> run `normalize_schema()` first |
| `thinking.type="enabled"` | route to REASONING_MODEL |
| `max_tokens` | `max_tokens` (min 1024 to avoid upstream truncation) |
| `stop_sequences` | `stop` |
| `top_p` | `top_p` |

### `normalize_schema()` (critical for OpenAI compatibility)
OpenAI rejects some JSON-Schema constructs Anthropic allows:
- Drop all `null` values from objects.
- Strip `format: "uri"`.
- Recurse into `properties`, `items`, `additionalProperties`, `allOf/anyOf/oneOf`,
  `prefixItems`, `contains`, `not`, `if/then/else`.
- Auto-add `"required": []` to any `type: "object"` missing it; force `required`
  to `[]` if present but not an array.

## OpenAI -> Anthropic response mapping

| OpenAI field | Anthropic mapping |
|-------------|-------------------|
| `choices[].message.content` | `content:[{type:"text", text}]` (only if non-empty) |
| `choices[].message.tool_calls` | `content:[{type:"tool_use", id, name, input: json.loads(arguments)}]` |
| `choices[].finish_reason` | `stop_reason`: `tool_calls->tool_use`, `stop->end_turn`, `length->max_tokens`, else `end_turn` |
| `usage.prompt_tokens` | `usage.input_tokens` |
| `usage.completion_tokens` | `usage.output_tokens` |
| `id` missing | `"msg_proxy"` |
| empty content + tool_calls | emit tool_use block(s) only |

Reasoning models (e.g. `tencent/hy3:free`) may put the answer in `reasoning` /
`reasoning_content` instead of `content` — fall back to that field so the client
never sees empty output.

## Streaming state machine (Anthropic SSE)

OpenAI sends chunks `{choices:[{delta:{content|reasoning|tool_calls}, finish_reason}]}`.
Translate to Anthropic SSE events with a `BlockState` (Idle/Thinking/Text/ToolUse):

```
message_start
  content_block_start (index 0, type: thinking|text|tool_use)
  content_block_delta * (thinking_delta | text_delta | input_json_delta)
  content_block_stop   (index N)
message_delta (stop_reason, usage)
message_stop
```

**Invariant**: every `content_block_start` MUST be followed by exactly one
`content_block_stop` before the next `content_block_start`. Switching block type
(text->tool_use) closes the prior block first. `reasoning`/`reasoning_content`
deltas open a `thinking` block; `content` deltas open a `text` block; `tool_calls`
deltas open a `tool_use` block (emit `input_json_delta` with `partial_json`).

For Responses-API streaming (Codex), the SSE event names differ
(`response.created`, `response.output_text.delta`, `response.completed`, etc.)
but the same accumulation-then-emit approach works: call upstream NON-streaming,
then emit the full SSE sequence in order. (Nous chat endpoint is non-streaming;
accumulate, then flush SSE — keeps proxy simple, no upstream stream parsing.)

## Nous portal specifics (verified 2026-07-22)

- Base: `https://inference-api.nousresearch.com`
- ONLY `/v1/chat/completions` works (200). `/v1/responses` and `/v1/messages`
  return **404**.
- Free models (suffix `:free`) — exactly 4 of 286 total:
  `tencent/hy3:free` (default + reasoning), `poolside/laguna-s-2.1:free`,
  `poolside/laguna-xs-2.1:free`, `stepfun/step-3.7-flash:free`.
- Auth: OAuth bearer token in Hermes `auth.json`
  (`providers.nous.access_token` or `.agent_key`). Read fresh per request so
  expiry is invisible to clients.
- `tencent/hy3:free` returns answer in `reasoning` field when `max_tokens` is
  small — always lift `max_tokens` to >=1024 and fall back to `reasoning`.

## End-to-end verification recipe (must all pass)

```bash
# 1. health
curl -s http://127.0.0.1:PORT/healthz
# 2. Responses (Codex)
curl -s -X POST http://127.0.0.1:PORT/v1/responses -H 'Content-Type: application/json' \
  -d '{"model":"tencent/hy3:free","input":"Reply with exactly: RESP_OK","max_output_tokens":2048}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['output'][0]['content'][0]['text'])"
# 3. Anthropic (Claude Code)
curl -s -X POST http://127.0.0.1:PORT/v1/messages -H 'Content-Type: application/json' \
  -H 'x-api-key: dummy' -H 'anthropic-version: 2023-06-01' \
  -d '{"model":"tencent/hy3:free","max_tokens":2048,"messages":[{"role":"user","content":"Reply with exactly: ANTH_OK"}]}' \
  | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['stop_reason'], d['content'])"
# 4. all 4 free models via BOTH paths
# 5. Anthropic streaming (SSE sequence present)
# 6. tool_use round-trip (stop_reason:tool_use, tool_use block with parsed input)
# 7. systemd active
systemctl --user is-active wrapper-nous-unified.service
```

## Pitfalls (lightweight variant)

**P1: systemd unit location.** `systemctl --user` reads from
`/root/.config/systemd/user/`, NOT from the project dir. `enable --now` fails
with "Unit file does not exist" if you only wrote it to `/root/wrapper/nous/`.
Always `cp` the `.service` into the user systemd dir (then `daemon-reload`).

**P2: nested dict literal bracket bug.** When writing `events.append({"type":...,
"data": {...}})` inline, a missing closing `}` on the inner dict causes
`SyntaxError: closing parenthesis ')' does not match opening parenthesis '{'`.
Write nested dicts in multi-line block style (one level per indent) to avoid
miscounting. Always `python3 -c "import ast; ast.parse(open('x.py').read())"`
before enabling the service.

**P3: streaming SSE + `curl -N | head` hangs.** `curl -N` with `head -N` closes
the pipe early; the proxy already flushed all events but curl waits on the
keep-alive socket -> looks like timeout. Redirect to a file with `-m <secs>` and
inspect, or grep the saved file. The SSE sequence is correct; the hang is a curl
client artifact, not a proxy bug.

## Files produced (wrapper-nous)

```
/root/wrapper/nous/unified_proxy.py              # 1 file, stdlib, dual-format @9107
/root/wrapper/nous/wrapper-nous-unified.service  # systemd unit (copied to ~/.config/systemd/user)
/root/wrapper/nous/nous_proxy.py                 # legacy Responses-only @9106 (retire after 9107 verified)
/root/wrapper/nous/README.md
```

Port note: 9106 was the first free port (exclude 9100-9105); 9107 is the unified
dual-format proxy. 9101/9103/9191 were already taken by other services.
