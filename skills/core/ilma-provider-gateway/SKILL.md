---
name: ilma-provider-gateway
description: "ILMA v5.0 Smart Provider Gateway — L7 API Routing with Dynamic Workload Detection. Routes requests to optimal free tier providers (NVIDIA, OpenRouter, Groq, HuggingFace, Together). Automatic failover and round-robin without sub-agent awareness. SSS Tier."
triggers:
  - provider-router
  - l7-routing
  - api-gateway
  - free-tier
  - failover
  - round-robin
  - workload-classification
version: 5.0.0
tier: SSS-OMEGA
last_updated: 2026-05-07
---

# ILMA v5.0 — SMART PROVIDER GATEWAY

## Overview

**Tier:** SSS-OMEGA  
**Version:** 5.0.0  
**Status:** OPERATIONAL

## Architecture

L7 Application Layer API Gateway that intelligently routes requests to optimal free tier providers.

### Workload Classification

| Type | Keywords | Primary Provider |
|------|----------|------------------|
| CODING | def, class, import, async, try/except | NVIDIA Qwen |
| CONTENT_WRITING | tulis, buat, artikel, blog | OpenRouter Llama |
| RESEARCH | cari, analisa, bandingkan | OpenRouter Mixtral |
| REASONING | jawab, logika, hitung | NVIDIA Qwen |
| CREATIVE | cerita, puisi, sastra | OpenRouter Llama |
| AGENTIC | eksekusi, autonom, workflow | OpenRouter Mixtral |

### Provider Chain (Failover)

```
CODING → NVIDIA Qwen → OpenRouter DeepSeek → Groq Mixtral → HuggingFace Qwen
CONTENT → OpenRouter Llama → NVIDIA Llama → Groq Llama → HuggingFace Llama
REASONING → NVIDIA Qwen → Groq Mixtral → OpenRouter Mixtral
```

### Features

- **Dynamic Workload Detection**: Regex fingerprinting + heuristic analysis
- **Transparent Failover**: Sub-agents don't know about provider switching
- **Rate Limiting**: Token bucket algorithm (RPM + TPM)
- **Health Monitoring**: Tracks latency, failures, rate limit remaining
- **Round-Robin**: Load balancing within priority tiers

## Files

- /root/.hermes/profiles/ilma/scripts/ilma_provider_router.py (1,068 lines)

---

**ILMA v5.0 — ZERO-COST INTELLIGENT ROUTING**