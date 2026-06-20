# Model Context Windows Reference
## Updated: 2026-05-13

## Quick Reference — Common Models

| Model | Context Window | Notes |
|-------|---------------|-------|
| gpt-4o / gpt-4o-mini (2024+) | 1,000,000 | OpenAI latest |
| gpt-4o-2024-05-13 | 1,000,000 | OpenAI May 2024 |
| gpt-4o-2024-08-06 | 1,000,000 | OpenAI Aug 2024 |
| gpt-4o audio/realtime/search | 128,000 | Audio caps |
| claude-3.5-sonnet-20241022 | 200,000 | Anthropic |
| claude-3-haiku-20240307 | 200,000 | Anthropic |
| claude-3-opus-20240229 | 200,000 | Anthropic |
| gemini-1.5-flash | 1,048,576 | Google |
| gemini-1.5-pro | 1,048,576 | Google |
| gemini-2.0-flash-001 | 1,000,000 | Google |
| gemini-3.1-pro-preview | 262,144 | Google preview |
| qwen3-plus/flash/omni | 1,000,000 | Alibaba |
| qwen3-max | 262,144 | Alibaba |
| qwen3-235b | 262,144 | Alibaba large |
| deepseek-v4-pro | 163,840 | Deepseek |
| mistral-large-3 | 262,144 | Mistral |
| openrouter free (most) | 128,000 | Platform cap |

## Database

Source: `/root/.hermes/profiles/ilma/data/ilma_dashboard.db`
- Total: 1,284 models
- Unique contexts: 46 values (2,824 – 2,000,000)
- NULL contexts: 0

Query context distribution:
```sql
SELECT context_window, COUNT(*) as cnt 
FROM model_ids 
GROUP BY context_window 
ORDER BY cnt DESC;
```

## Context Window Pattern Issues

**Problem:** Models without provider prefix (e.g., `gpt-4o` vs `openai/gpt-4o`) often have WRONG context values.

**Fix:** Match orphaned entries to provider-prefixed versions:
```python
cur.execute("""
    UPDATE model_ids 
    SET context_window = (SELECT context_window FROM model_ids WHERE canonical_model_id = 'openai/' || ? LIMIT 1)
    WHERE canonical_model_id = ? AND context_window != (SELECT context_window FROM model_ids WHERE canonical_model_id = 'openai/' || ? LIMIT 1)
""", (model, model, model))
```

## Common Patterns

| Pattern | Context | Reason |
|---------|---------|--------|
| `gpt-4o` (no prefix) | Often 128K ❌ | Registered without provider |
| `openai/gpt-4o` | 1M ✅ | Provider doc based |
| Arena models | 200K default | Benchmark configurations |
| OpenRouter | 128K cap | Platform limitation |
| NVIDIA NIM | Varies | Per-model specs |