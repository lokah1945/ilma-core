# OpenAI Responses API SSE Streaming — Codex v0.145.0 Compatibility

**Context (2026-07-23):** `wrapper-nous` proxies OpenAI **Responses API** (`/v1/responses`)
→ Nous Chat Completions. OpenAI **Codex CLI v0.145.0** (`wire_api = "responses"`)
connects via this proxy. Without strict event ordering, Codex **hangs / emits
"OutputTextDelta without active item" / never finalizes tool calls**.

**Hard rules for the Responses SSE event stream (non-negotiable for Codex):**

### 1. Item lifecycle must be complete for EVERY item
For each output item (text message OR function_call), you MUST emit, in order:
```
response.output_item.added      (item becomes "active")
  ... delta events ...
response.output_item.done       (item closed)
```
Sending `output_text.delta` or `function_call.delta` BEFORE the item's
`output_item.added` → Codex errors `OutputTextDelta without active item` and hangs.

### 2. Text item event order
```
response.created
response.in_progress
response.output_item.added        {item: {id:"msg-1", type:"message", role:"assistant", content:[]}}
response.content_part.added       {item_id:"msg-1", part:{type:"output_text", text:""}}
response.output_text.delta        {item_id:"msg-1", output_index:0, content_index:0, delta:"..."}  (xN)
response.output_text.done         {item_id:"msg-1", text:<full>}
response.content_part.done        {item_id:"msg-1", part:{type:"output_text", text:<full>}}
response.output_item.done         {output_index:0, item:{id:"msg-1", type:"message", status:"completed", content:[{type:"output_text", text:<full>}]}}
response.completed                {response:{id, status:"completed", usage:{...}}}
```

### 3. Tool / function_call item order
```
response.output_item.added        {output_index:1, item:{id:"call_X", type:"function_call", status:"in_progress", call_id:"call_X", name:"...", arguments:""}}
response.function_call.delta      {item_id:"call_X", output_index:1, delta:"{...partial json...}"}
response.output_item.done         {output_index:1, item:{id:"call_X", type:"function_call", status:"completed", call_id:"call_X", name:"...", arguments:"<full json>"}}
```
- NEVER send `function_call.delta` without a preceding `output_item.added` for that id.
- ALWAYS close the tool item with `output_item.done` in the completion phase, or
  Codex waits forever → "proses terhenti".

### 4. Stable tool call ID across chunks
OpenAI chat chunks often only send `tool_calls[].id` on the FIRST chunk; later
chunks have `id: null` but continue `arguments`. Track an `_active_tool_id` and
reuse it so all deltas map to ONE `call_X` item (not N items). Otherwise you get
7 `output_item.added` for one tool call → Codex rejects.

### 5. usage normalization (OpenAI Responses schema REQUIRES all 3)
```
{"input_tokens": N, "output_tokens": M, "total_tokens": N+M}
```
Nous/chat upstream sends `prompt_tokens`/`completion_tokens` (or empty `{}`).
Normalize names AND always add `total_tokens = input + output`. Missing any of
the three → Codex `failed to parse ResponseCompleted: missing field X`.

### 6. Termination
Emit `response.completed` EXACTLY ONCE (idempotent guard `_completed`), then
`data: [DONE]`. If upstream never sends `[DONE]`, emit completion in the stream's
`finally` block so Codex can finalize.

**Verification pattern used (worked):**
```bash
# 1. Raw SSE event order — must show added→delta→done per item
curl -sN -X POST http://127.0.0.1:9106/v1/responses -H "Authorization: Bearer sk-placeholder" \
  -d '{"model":"tencent/hy3:free","input":[...],"tools":[...],"stream":true}' | grep '^event:'

# 2. Real client — must NOT hang, must execute tool, exit 0 (or 1 only on upstream 400)
codex exec --model tencent/hy3:free "create file /tmp/x.txt with HI"
cat /tmp/x.txt   # proves tool ran
```
**Caveat:** Nous free models may return `400` on the 2nd turn (tool-result
round-trip) — that is an upstream limit, not a wrapper bug. Codex still executes
the tool on turn 1.
