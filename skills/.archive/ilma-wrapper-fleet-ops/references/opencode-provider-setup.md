# OpenCode Custom Provider Setup (all wrappers)

Binary: `/root/.opencode/bin/opencode` (v1.17.20). Config: `~/.config/opencode/opencode.jsonc`.

## Why custom providers don't appear
1. `@ai-sdk/openai-compatible` npm package NOT installed in `~/.config/opencode/`.
   → `opencode models` shows zero `wrapper-*` lines.
   Fix: `cd ~/.config/opencode && npm install @ai-sdk/openai-compatible`
2. Missing `"npm": "@ai-sdk/openai-compatible"` field in the provider block.
3. Models NOT auto-fetched — must be listed manually under `"models"`.

## Minimal provider block
```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "wrapper-nous": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Wrapper Nous (free)",
      "options": {
        "baseURL": "http://localhost:9102/v1",
        "apiKey": "wrapper-local-key"
      },
      "models": {
        "tencent/hy3:free": { "name": "tencent/hy3:free", "limit": { "context": 200000, "output": 8192 } }
      }
    }
  }
}
```

## Sync model list from a wrapper
```bash
KEY=wrapper-local-key
curl -s -H "Authorization: Bearer $KEY" http://127.0.0.1:9102/v1/models \
  | python3 -c "import sys,json;[print(m['id']) for m in json.load(sys.stdin)['data']]"
```
Build the `"models"` dict from that list (every entry needs `{"name": id, "limit": {...}}`).

## Verify
- `opencode models | grep '^wrapper-'` → shows `wrapper-<name>/<model>` lines.
- Smoke test: `opencode run "reply exactly: PONG" -m wrapper-nous/tencent/hy3:free` → should print `PONG`.

## Notes
- If a model returns "Internal Server Error" via OpenCode but works via curl,
  it's an upstream model issue, NOT a config issue (e.g. Nous `ling-3.0-flash-free`
  ived 400 from upstream while `tencent/hy3:free` worked).
- Re-sync `opencode.jsonc` whenever a wrapper's model set changes.
- Old config pointed nvidia at port **9100** (not listening) — correct port is **9101**.
