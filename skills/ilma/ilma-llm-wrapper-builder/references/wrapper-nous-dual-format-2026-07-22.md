# wrapper-nous — Dual-Format Lightweight Proxy (Nous portal)

Session evidence: 2026-07-22. Build of a single-port proxy that handles BOTH
OpenAI Responses (Codex) and Anthropic Messages (Claude Code) clients, translating
both to Nous Research `/v1/chat/completions`.

## Why this exists

- Codex v0.144.5 only speaks OpenAI **Responses** wire API (`wire_api="responses"`).
- Claude Code / Anthropic SDK only speak **Anthropic `/v1/messages`**.
- Nous portal implements **only** `/v1/chat/completions` (`/v1/responses` and
  `/v1/messages` both return 404).
- One proxy on `:9107` auto-detects by path and translates both to Nous chat.

## Source studied (concepts only, NOT 1:1 port)

`github.com/m0n0x41d/anthropic-proxy-rs` (Rust, MIT). We took ONLY the
translation concepts (Anthropic↔OpenAI mapping, block-lifecycle streaming state
machine, tool/stop_reason mapping) and re-implemented in pure Python stdlib
integrated with the already-verified Responses translator. No Rust/Cargo/Docker.

## Key translation rules (verified end-to-end)

### Request: Anthropic → OpenAI chat
- `system` (string OR array) → separate `role:system` message(s)
- `messages[].content` may be string OR blocks:
  - `text` → content string
  - `image` → `{"type":"image_url","image_url":{"url":"data:<media>;base64,<data>"}}`
  - `thinking` → `reasoning_content` (joined)
  - `tool_use` → `tool_calls[]` (function, arguments JSON-serialized)
  - `tool_result` → separate `role:tool` message with `tool_call_id`
- `tools[]` → OpenAI function tools; run `normalize_schema()`:
  - drop null values, drop `format:"uri"`, recurse `properties/items/allOf/...`
  - auto-add `required:[]` to object schemas missing it
- `thinking.enabled` → route to `REASONING_MODEL` (we use `tencent/hy3:free`)
- `max_tokens` → `max_tokens`

### Response: OpenAI chat → Anthropic
- `choices[].message.content` → `content:[{type:text,text}]`
- `tool_calls` → `content:[{type:tool_use,id,name,input}]` (parse `arguments` JSON)
- `finish_reason` → `stop_reason`: `tool_calls→tool_use`, `stop→end_turn`, `length→max_tokens`
- `usage.prompt_tokens→input_tokens`, `completion_tokens→output_tokens`

### Streaming: OpenAI SSE → Anthropic SSE (state machine)
- `BlockState`: Idle / Thinking / Text / ToolUse (one active block at a time)
- Sequence per block: `content_block_start` → `content_block_delta*` → `content_block_stop`
- Top-level sequence: `message_start` → (blocks) → `message_delta` → `message_stop`
- `reasoning` / `reasoning_content` → `thinking_delta`; `content` → `text_delta`;
  `tool_calls` → `input_json_delta`
- INVARIANT: every `content_block_start` is followed by exactly one `content_block_stop`
  before the next `content_block_start`.

## Nous-specific
- Upstream: `https://inference-api.nousresearch.com/v1/chat/completions`
- Auth: fresh OAuth bearer read per-request from Hermes `auth.json`
  (`providers.nous.access_token` or `agent_key`) — handles token expiry automatically
- Free models (suffix `:free`, total 4 of 286): `tencent/hy3:free` (default+reasoning),
  `poolside/laguna-s-2.1:free`, `poolside/laguna-xs-2.1:free`, `stepfun/step-3.7-flash:free`
- Proxy passes through whatever model the client requests (not hardcoded)

## Files (final)
```
/root/wrapper/nous/wrapper_nous.py          # single-file proxy (stdlib)
/root/wrapper/nous/wrapper-nous.service     # systemd user unit @ :9107
/root/wrapper/nous/README.md
/root/.config/systemd/user/wrapper-nous.service   # symlink target
```

## Client integration
- Codex `~/.codex/config.toml`: `model_provider.nous.base_url = "http://127.0.0.1:9107"`
- Also patch `setup_nous_codex.py` to write `:9107` so re-runs don't regress to `:9191`
- Retire legacy `nous-proxy.service` (:9191) — `systemctl --user disable --now`

## Verification checklist (all passed)
- `curl :9107/healthz` → `{"ok":true}`
- `POST /v1/responses` (Codex) → `output[0].content[0].text` non-empty
- `POST /v1/messages` (Claude Code) → `type:message`, `stop_reason:end_turn`
- All 4 free models via BOTH paths
- Anthropic streaming SSE: full `message_start…message_stop` sequence
- Tool use round-trip: `stop_reason:tool_use`, `tool_use` block with parsed input
- Live `codex exec` returns correct answer via `:9107`

## Pitfalls (new, lightweight-specific)
- P-L1: `event: …` SSE framing for Anthropic must be `event: X\ndata: {…}\n\n`
  (two newlines). A single `\n` after data breaks Claude Code parsing.
- P-L2: non-streaming upstream (Nous chat is non-streaming) → accumulate full
  response, then emit the FULL Anthropic SSE sequence in one flush. Client `-N`
  curl may hit `-m` keep-alive timeout AFTER stream completes; that's expected,
  not a failure.
- P-L3: bracket-balance bug — when assembling nested dicts (e.g. `message_start`
  with `data:{message:{…}}`), count `{`/`}` carefully. `ast.parse` before enabling
  the service catches this.
- P-L4: systemd unit for a USER service MUST live in `/root/.config/systemd/user/`,
  not just the project dir. `systemctl --user enable` only sees that path. Copy
  the `.service` file there (or symlink) before `daemon-reload`.
