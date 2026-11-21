# wrapper-nous FastAPI v2 — streaming bugs found & fixed (2026-07-23)

## Context
Bos pulled `lokah1945/wrappers` commit `3f0f44c` (other agents' fixes). wrapper-nous
was rewritten from v1 (http.server) to **v2.0.0 FastAPI + Uvicorn async** (653 lines).
Pulled via: `git stash` local fixes → `git fetch github` → `git merge --ff-only github/main`.

## Bug A — `async with` closes the proxied stream (streaming empty)
`post_nous()` used `async with sess.post(...) as resp: return 200, resp`. The `async with`
exited on return → aiohttp response closed → `stream_with_heartbeat` read a dead
connection → 0 bytes to client.

Fix: for `stream=True`, `resp = await sess.post(...)` (no `async with`), return raw;
consumer's `finally: await resp.release()` closes it. Non-stream path keeps `async with`.

Verify: `curl -N -X POST :9106/v1/chat/completions '{"stream":true,...}'` → incremental
`data:` chunks (was 0 bytes).

## Bug B — Responses streaming wrong format
`/v1/responses` streaming path passed raw chat.chunks through as SSE. Codex expects
Responses events. Added `ResponsesStreamState.translate_chunk()` (maps delta.content →
`response.output_text.delta`, tool_calls → `response.function_call.delta`,
finish_reason → `response.completed`) and wired it: instantiate state, pass to
`stream_with_heartbeat(result, lambda x: x, state=state)`, emit `state.done()` on `[DONE]`.

Verify: `event: response.created` → `response.in_progress` → `response.output_text.delta`
→ `response.completed` present in streamed body.

## Notes
- v1 STORE_LOCK / ThreadingHTTPServer patterns (Pitfall #48/#49) NO LONGER apply to v2.
- Remote already handles `name:null` deferred tools (filter `if t.get("function",t).get("name")`).
- Codex still fails under upstream Nous "high demand" throttling — that is provider-side,
  not a wrapper bug (test_100.py = 100/100, concurrent 6/6 OK prove wrapper health).
