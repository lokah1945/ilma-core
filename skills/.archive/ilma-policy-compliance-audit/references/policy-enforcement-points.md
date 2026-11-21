# Policy Enforcement Points

## OpenAI-Compatible Endpoints

### /v1/chat/completions
- **OpenCode (9103)**: Lines 767-769
- **Nous (9102)**: Lines 767-769 (similar pattern)
- **Blackbox (9104)**: Lines 767-769
- **OpenRouter (9106)**: Lines 767-769

### /v1/responses
- **All wrappers**: Same pattern as chat/completions

### /v1/messages (Anthropic)
- **All wrappers**: Transcoded from OpenAI format

## Enforcement Flow

```
Request → Auth Middleware → Rate Limit → FREE_ONLY Check → Proxy
```

### Code Location Matrix

| Wrapper | FREE_ONLY Check Location | Error Response |
|---------|--------------------------|----------------|
| opencode | `_check_free_only()` line 767 | `free_only_error()` line 230 |
| nous | `_check_free_only()` line 767 | `free_only_error()` line 505 |
| blackbox | `model_allowed()` line 353 | `free_only_error()` line 306 |
| openrouter | `_check_free_only()` line 745 | Inline JSONResponse line 749 |

## Test Commands

```bash
# Test FREE_ONLY enforcement
for port in 9102 9103 9104 9106; do
  echo "=== Port $port ==="
  curl -s http://localhost:$port/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{"model": "gpt-4", "messages": []}' | jq '.error.code // "no error"'
done
```