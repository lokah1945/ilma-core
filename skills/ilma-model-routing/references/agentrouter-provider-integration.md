# AgentRouter Provider Integration Reference
## Session: 2026-10-31 — Provider API Discovery for Routing

---

## Provider Profile: AgentRouter

| Property | Value |
|----------|-------|
| **Name** | `agentrouter` |
| **Type** | Unified LLM Gateway (aggregator) |
| **Free Tier** | Yes (registration required) |
| **Auth** | API Key (Bearer for OpenAI, x-api-key for Anthropic) |
| **Base URLs** | Dual: `https://agentrouter.org` (Anthropic) / `https://agentrouter.org/v1` (OpenAI) |
| **Dashboard** | `https://ps.air-outer.com/console` |
| **Key Source** | `https://ps.air-outer.com/console/token` |
| **Model List** | Dynamic — `https://ps.air-outer.com/console/personal` |
| **Support** | Discord: `https://discord.gg/HgekCyHJqB` |

---

## Routing Rules

### Format Selection Logic
```
IF model IN ["claude-opus-5", "claude-opus-4-8"]:
    USE Anthropic format (base_url = "https://agentrouter.org")
ELSE:
    USE OpenAI format (base_url = "https://agentrouter.org/v1")
```

### Model Name Normalization
- Names **must match dashboard exactly** (case-sensitive, hyphens preserved)
- Examples: `gpt-6-astra`, `gpt-5.6-sol`, `claude-opus-5`, `glm-5.3`, `deepseek-v4-flash`
- Wrong name → 503 "no available channel"

---

## Capability Mapping

| Model | Primary Capability | Tier | Notes |
|-------|-------------------|------|-------|
| `gpt-6-astra` | reasoning, coding, analysis | High | Flagship OpenAI-format model |
| `gpt-5.6-sol` | coding, reasoning | High | OpenAI-format |
| `claude-opus-5` | reasoning, analysis, writing | High | Anthropic-format preferred |
| `claude-opus-4-8` | reasoning, analysis, writing | High | Anthropic-format preferred |
| `glm-5.3` | general, chinese | Medium | Zhipu model |
| `deepseek-v4-flash` | coding, reasoning | Medium | Fast variant |

---

## Health Check Implementation

```python
async def check_agentrouter_health(api_key: str) -> dict:
    """Check AgentRouter API key validity and model availability."""
    results = {}
    
    # Test OpenAI format
    openai_ok, _ = await test_openai_format(api_key, "gpt-6-astra")
    results["openai_format"] = openai_ok
    
    # Test Anthropic format
    anthropic_ok, _ = await test_anthropic_format(api_key, "claude-opus-5")
    results["anthropic_format"] = anthropic_ok
    
    # Overall health
    results["healthy"] = openai_ok or anthropic_ok
    results["models_accessible"] = await fetch_models(api_key) if results["healthy"] else []
    
    return results
```

---

## Credential Structure for SOT

```json
{
  "provider": "agentrouter",
  "api_key": "sk-...",
  "base_url_openai": "https://agentrouter.org/v1",
  "base_url_anthropic": "https://agentrouter.org",
  "format_preference": "dual",
  "models": [
    {"name": "gpt-6-astra", "format": "openai", "capabilities": ["chat", "completion"]},
    {"name": "gpt-5.6-sol", "format": "openai", "capabilities": ["chat", "completion"]},
    {"name": "claude-opus-5", "format": "anthropic", "capabilities": ["chat", "completion"]},
    {"name": "claude-opus-4-8", "format": "anthropic", "capabilities": ["chat", "completion"]},
    {"name": "glm-5.3", "format": "both", "capabilities": ["chat", "completion"]},
    {"name": "deepseek-v4-flash", "format": "both", "capabilities": ["chat", "completion"]}
  ],
  "last_verified": "2026-10-31T00:00:00Z",
  "status": "active"
}
```

---

## Integration with ILMA Provider Kernel

Add to `ilma_provider_kernel.py` FREE_PROVIDERS:
```python
FREE_PROVIDERS = {
    "nvidia": {...},
    "openrouter": {...},
    "minimax": {...},
    "blackbox": {...},
    "qwen": {...},
    "agentrouter": {      # NEW
        "base_url_openai": "https://agentrouter.org/v1",
        "base_url_anthropic": "https://agentrouter.org",
        "requires_registration": True,
        "dynamic_models": True,
        "dashboard_url": "https://ps.air-outer.com/console"
    }
}
```

---

## Caveats & Gotchas

| Issue | Mitigation |
|-------|------------|
| **Key expires/invalidates** | Implement periodic health check (cron hourly) |
| **Models change dynamically** | Cache model list with 5-min TTL; refresh from dashboard API |
| **Dual base URLs** | Route by model name, not by request format |
| **401 on /models** | Can't discover models without valid key — must have key first |
| **Rate limits undisclosed** | Implement exponential backoff; respect 429 |
| **Chinese-origin service** | Docs/UI mixed language; Discord is primary support |

---

## Test Results (2026-10-31)

| Key Tested | `sk-Hze...DyHN` |
|------------|-----------------|
| OpenAI `/v1/chat/completions` | ❌ 401 Unauthorized |
| Anthropic `/v1/messages` | ❌ 401 Unauthorized |
| `/v1/models` (both) | ❌ 401 Unauthorized |
| **Verdict** | **Key invalid — not registered with AgentRouter** |

---

## Next Steps for Integration

1. [ ] Register Bos account at `ps.air-outer.com/console`
2. [ ] Obtain valid API key from `console/token`
3. [ ] Add AgentRouter to `FREE_PROVIDERS` in provider kernel
4. [ ] Implement dual-format routing logic in model router
5. [ ] Add health check to `ilma_health_manager.py`
6. [ ] Update capability registry with AgentRouter models
7. [ ] Test end-to-end with `ilma_claudecode_agent.py` parallel coding

---

## Related Files

- `skills/ilma-research/references/agentrouter-api-discovery.md` — Full discovery notes
- `scripts/ilma_model_db_manager.py` — Provider sync logic
- `scripts/ilma_provider_kernel.py` — Provider kernel (FREE_PROVIDERS)
- `config/ilma_capability_registry.json` — Capability evidence ledger