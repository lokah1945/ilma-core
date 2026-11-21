# wrapper-coarena Single-Key Test — 2026-11-17

**Key tested:** `coa_d3d00fc3b5af6afc1aea3831a4007d06` (smahud@gmail.com)
**Second key tested:** `coa_0461f52d8d163ee4796f6495cb03cf68` — same account limits

## Free Tier Limits (verified live)

| Limit | Value | Notes |
|-------|-------|-------|
| Daily budget | **$1/day** | Not $5 as sometimes claimed |
| Requests/minute (key) | **10 RPM** | Hard limit, 429 after 3-4 req in burst |
| Concurrent (in-flight) | **2** | 3rd concurrent → "Too many requests in flight" |
| Pending limit increase | $100/day, 120 RPM, 10 concurrent | YAPSI nonprofit request, status: pending |

## Model Access

| Model | Status | Notes |
|-------|--------|-------|
| `gpt-6-luna` | ✅ Free | Works |
| `gemini-3-8-flash` | ✅ Free | Works |
| `deepseek-v4-1-flash-1017` | ✅ Free | Works |
| `claude-fable-5` | ❌ 402 | `payment_required` / `insufficient_quota` |
| `claude-fable-5-1` | ❌ 402 | `payment_required` / `insufficient_quota` |
| `claude-sonnet-5-5` | ❌ 402 | `payment_required` / `insufficient_quota` |
| `claude-opus-5-5` | ❌ 429 | Rate limited at upstream (free tier hits 10 RPM fast) |

**Only 3 models are actually free.** All Claude, GPT-6 Astra/Sol/Terra, Grok, Kimi, MiMo, Hy4 blocked.

## Wrapper Behavior (verified)

| Scenario | Result |
|----------|--------|
| Free model via `/v1/chat/completions` | ✅ Works (within 10 RPM) |
| Free model via `/v1/messages` (Anthropic) | ✅ Works |
| Streaming (both protocols) | ✅ Works |
| Paid model (Fable, Opus, Sonnet) | ❌ 402 → wrapper transforms to `insufficient_quota` |
| After quota exhausted | Wrapper correctly cools key for 300s (`auth_or_quota`) |
| Key pool sync / hot reload | ✅ Works |

## 60-Minute Sustained Test (stopped at ~13 min)

- **Total requests:** 116
- **USD used:** $0.0109 / $1.00
- **Models tested:** gemini-3-8-flash, gpt-6-luna, deepseek-v4-1-flash-1017 (round-robin)
- **Error rate:** 0% — all 116 requests ✅ OK
- **Rate limit refused:** 32 (from earlier burst before test started)
- **Concurrency refused:** 4 (from earlier burst)
- **RPM sustained:** ~8.6 RPM (well under 10 limit)

## Risk / Skipped

- Full 60 min completion not done
- Streaming under sustained load not tested
- Tool calling, response continuation (`previous_response_id`), cross-dialect translation edge cases — all blocked by tier
- Opus/Sonnet/Fable access — blocked until limit increase approved or paid credits added

## Diagnostic Commands

```bash
# Check account limits
curl -s -X GET https://coarena.ai/api/v1/limits \
  -H "Authorization: Bearer coa_d3d00fc3b5af6afc1aea3831a4007d06" | jq '.data'

# Test free model
curl -s -X POST https://coarena.ai/api/v1/chat/completions \
  -H "Authorization: Bearer coa_d3d00fc3b5af6afc1aea3831a4007d06" \
  -H "Content-Type: application/json" \
  -d '{"model": "gemini-3-8-flash", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 10}'

# Test paid model (expects 402)
curl -s -X POST https://coarena.ai/api/v1/chat/completions \
  -H "Authorization: Bearer coa_d3d00fc3b5af6afc1aea3831a4007d06" \
  -H "Content-Type: application/json" \
  -d '{"model": "claude-fable-5", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 10}'
```