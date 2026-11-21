# D-Gap Taxonomy — residual SDK-compat bugs found across V4–V7

Each "mutlak 100/100" claim was overclaimed until these were closed. Use as a
checklist for the next Vn audit. ✅ = fixed/verified, ❌ = still open.

### Alias & config
- **B1** alias resolver caches invalid model (`definitely-not-a-model-xyz`) →
  must reject, NOT cache. Fix: `_known_models` set + `set_dynamic_alias_target(force=)`.
  nvidia had it; nous/opencode needed porting. ✅
- **RC-1** systemd unit missing `EnvironmentFile=-/root/wrapper/<w>/.env` →
  `DYNAMIC_ALIAS_TARGET` not in env on restart → alias `sonnet`=None → 404.
  nvidia & nous lacked it; opencode had it. ✅ (all 3 now have it)

### Response shape
- **B2** chat response missing `usage` → add
  `{prompt_tokens, completion_tokens, total_tokens}`. nous/opencode returned 0/0/0
  fallback. ✅ (real counts appear)
- **C3** Anthropic `max_tokens` missing → was 200, must be 400. ✅ all 3
- **D3** chat `messages[].role` invalid (e.g. `god`) → nvidia hung (000);
  guard → 400. nous/opencode already 400. ❌ (nvidia still open per V7)
- **D6** Anthropic `system` as number → was 200, must be 400 (spec: string|array). ❌
- **D7** Anthropic tool missing `input_schema` → was 200, must be 400. ❌
- **D10** malformed JSON → nous/opencode returned 500, must be 400 (nvidia 400). ❌
- **D11** unknown `/v1/*` path → nvidia returned 401, should be 404. ❌

### CORS
- **G2/CORS** preflight (`OPTIONS`) must return 204/200 + `Access-Control-Allow-Origin`.
  Required reflective localhost regex (`127.0.0.1|localhost` + any port). ✅
- **D8** preflight must include `Access-Control-Allow-Credentials: true`
  (localhost-only safe via `allow_credentials=True`). ❌

### Healthy (do not regress)
- Chat/Responses/Anthropic alias `sonnet` → 200 (all 3)
- Anthropic `tool_use` block present in response
- Responses SSE events: `response.created/in_progress/completed`
- x-api-key auth → 200; missing `anthropic-version` → 400
- Bad model → 400 `invalid_request_error`, NO cache pollution
- Concurrent ×5–20 → 200 (or 429 rate-limit, which is correct)
- Content-Type `application/json`

### Gotchas that looked like bugs but weren't
- V4/V5 early `404`/`000` on alias = cold-start after restart (env not loaded
  yet). Fix = wait + poll `/health`.
- V6 `Traceback` in harness on nvidia = nemotron latency > curl `--max-time`,
  NOT a wrapper bug. Raw response was valid OpenAI JSON.
