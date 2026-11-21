# OpenHand Architecture Notes (SDK v1.21.0)

## LiteLLM model prefix rewrites (from openhands/sdk/llm/llm.py `_coerce_inputs`)
- `openhands/<x>` → `litellm_proxy/<x>` + base_url defaults to `https://llm-proxy.app.all-hands.dev/`
- `openai/<x>` → keeps base_url as-is (custom OpenAI passthrough). If base_url == `https://api.openai.com`, it's set to None so LiteLLM uses its default `/v1`.
- For a LOCAL custom endpoint, use `openai/<slug>` + explicit `base_url=http://127.0.0.1:PORT/v1`. LiteLLM forwards chat/responses calls there.

## ACP env injection (proven path)
`openhands acp --override-with-envs` reads `LLM_MODEL`, `LLM_BASE_URL`, `LLM_API_KEY` from os.environ.
Without the flag, env vars are ignored. The `LLM` pydantic model has no `env=` population, so only `acp --override-with-envs` (or a settings.json consumed by `web`) supplies config.

## Response shape
`LLM.completion()` returns `openhands.sdk.llm.llm_response.LLMResponse`:
- `.message` → Message(role, content=[TextContent(...), ...], tool_calls, ...)
- `.message.content[0].text` → the actual string
- `.raw_response` → underlying LiteLLM/provider response
Do NOT use `.choices[0].message.content` (OpenAI shape) — raises AttributeError.

## Subcommands
- `acp`  → Agent Client Protocol server (for IDEs like Zed). Flags: `--resume`, `--last`, `--always-approve/--yolo`, `--llm-approve`, `--override-with-envs`, `--cloud`. NO `-t`.
- `web`  → browser UI server. Reads `~/.openhands/settings.json`.
- `serve`→ Docker-based GUI server.
- `mcp`  → MCP server config management.

## Banner suppression
Set `OPENHANDS_SUPPRESS_BANNER=1` to silence the ASCII banner (otherwise printed to stderr on every SDK import).

## Cost warning (benign)
LiteLLM prints `Cost calculation failed: This model isn't mapped yet. model=<slug>, custom_llm_provider=openai` for free/unmapped slugs. This is a warning only — the completion still succeeds.
