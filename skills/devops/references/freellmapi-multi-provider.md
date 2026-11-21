# FreeLLMAPI Multi-Provider Support

## Provider Categories (30+)

| Category | Providers | Notes |
|----------|-----------|-------|
| **OpenAI-compatible** | Groq, Together, NVIDIA NIM, OpenRouter, Cerebras, Fireworks, Perplexity, xAI, DeepInfra | Most common; one key → many models |
| **Anthropic** | Claude API | Direct integration |
| **Google** | Gemini (AI Studio, Vertex) | 1M+ context on Flash/Pro |
| **Mistral** | Mistral AI platform | Native |
| **Cohere** | Cohere platform | Native |
| **Hugging Face** | Inference endpoints | Native |
| **Azure / AWS Bedrock** | Enterprise | Native |
| **Local** | Ollama, LM Studio, llama.cpp, vLLM | No API key needed |
| **Custom** | Any OpenAI-compatible base URL | User-defined |

## Free Tier Recommendations (Bos Preference)

1. **NVIDIA NIM** — 80+ free models (Llama, Nemotron, Mistral, Qwen)
2. **OpenRouter** — Aggregator, 100+ free models
3. **Groq** — Ultra-fast, Llama 3.3 70B, Mixtral, Gemma 2
4. **Together AI** — $1 free credit, good variety
5. **Google AI Studio** — Free tier, 1M+ context
6. **Cerebras** — Free, fastest tokens/sec

## Routing Strategies

| Strategy | Behavior |
|----------|----------|
| `balanced` | Balance latency, cost, capability (default) |
| `latency` | Fastest TTFB |
| `cost` | Cheapest per token |
| `capability` | Most capable model for task |
| `round-robin` | Distribute evenly |
| `failover-priority` | Strict priority order |
| `auto` | Router picks based on request |

## Key Endpoints

- `GET /v1/models` — List all models with availability
- `POST /v1/chat/completions` — OpenAI-compatible chat
- `POST /v1/embeddings` — Embeddings
- `POST /v1/responses` — OpenAI Responses API
- `/v1beta/*` — Beta surfaces
- `/mcp` — MCP inference

## Dashboard → Keys Page

Add provider keys → models with keys become `"available": true` in `/v1/models`.