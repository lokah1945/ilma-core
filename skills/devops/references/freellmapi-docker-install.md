# FreeLLMAPI Docker Install on Port 3970-398x Range

## Session Context: 2026-11-11
**Target**: Install FreeLLMAPI on unused port range 397x-398x (Bos request)
**Finding**: Docker Compose v1 (1.29.2) + Docker Python SDK 5.x conflict with `http+docker` URL scheme

## Problem: Docker Compose v1 + Docker SDK 5.x Incompatibility

```bash
# Error when running docker-compose with Docker SDK 5.x
docker.errors.DockerException: Error while fetching server API version: Not supported URL scheme http+docker
```

**Root cause**: Docker Compose 1.29.2 (system package) uses Docker Python SDK. SDK 5.x changed URL scheme parsing, breaking Compose v1.

## Solution: Use `docker run` Direct (Bypass Compose)

```bash
# 1. Pull image
docker pull ghcr.io/tashfeenahmed/freellmapi:latest

# 2. Run container with custom port (3970)
docker run -d \
  --name freellmapi-397x \
  --restart unless-stopped \
  -p 127.0.0.1:3970:3001 \
  -e PORT=3001 \
  -e NODE_ENV=production \
  -e ENCRYPTION_KEY=<64-char-hex> \
  -v freellmapi-397x-data:/app/server/data \
  ghcr.io/tashfeenahmed/freellmapi:latest

# 3. Verify health
curl -s http://127.0.0.1:3970/api/ping
# {"status":"ok","timestamp":"..."}
```

## Setup Steps

### Generate Encryption Key
```bash
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
```

### Create First Account (Requires Setup Code from Logs)
```bash
# Get setup code from container logs
docker logs freellmapi-397x | grep "First-run setup code"

# Create account with setup code
curl -X POST http://127.0.0.1:3970/api/auth/setup \
  -H "Content-Type: application/json" \
  -d '{"email":"user@domain.com","password":"password","setupCode":"XXXXXX"}'
```

### Login & Get Unified API Key
```bash
# Login
curl -X POST http://127.0.0.1:3970/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@domain.com","password":"password"}'

# Regenerate unified API key (settings endpoint)
curl -X POST http://127.0.0.1:3970/api/settings/api-key/regenerate \
  -H "Authorization: Bearer <dashboard-token>"
```

### Test Chat Completion
```bash
curl -X POST http://127.0.0.1:3970/v1/chat/completions \
  -H "Authorization: Bearer freellmapi-<unified-key>" \
  -H "Content-Type: application/json" \
  -d '{"model":"auto","messages":[{"role":"user","content":"Hello"}]}'
```

## Available Models (Requires Provider Keys in Dashboard)

Key models available in catalog (400+):
- `glm-5.3` (Zhipu AI) - 1M context
- `glm-5.3-flash` - 128K context
- `qwen3.8-max` - 1M context
- `gemini-3.8-flash` - 1M context
- `deepseek-v4.1-flash` - 128K context
- `gpt-oss-120b` - 131K context
- `llama-3.1-8b` - 131K context
- Many more (see `/v1/models` endpoint)

## Port Range Mapping (Owner Convention)

| Service | Public Port | Internal Port |
|---------|-------------|---------------|
| freellmapi-397x | 3970 | 3001 |
| (next) | 3971-3989 | 3001 |

## Adding Provider Keys (Required for Model Access)

1. Open dashboard: `http://127.0.0.1:3970`
2. Go to **Keys** page
3. Add API keys for providers:
   - **NVIDIA NIM** (free: 80+ models)
   - **OpenRouter** (free tier)
   - **Groq** (free tier)
   - **Together AI** (free tier)
   - **Google AI Studio** (free tier)
4. Models with keys become `"available": true`

## Known Issues / Pitfalls

1. **Docker Compose v1 broken** with Docker SDK 5.x → use `docker run` directly (Compose v1 + SDK 5.x = `http+docker` URL scheme error)
2. **Setup code only in logs** → must check `docker logs` for first account creation
3. **Unified API key separate from dashboard token** → regenerate via `/api/settings/api-key/regenerate`
4. **No provider keys = all models unavailable** → must add keys in dashboard before testing
5. **Health check expects internal port 3001** → container PORT must match (3001)
6. **Container naming**: Keep simple (`freellmapi` not `freellmapi-397x`) — avoids confusion when managing multiple services
7. **Network binding**: Use `0.0.0.0:3970` (not `127.0.0.1`) for LAN access — set via `-p 0.0.0.0:3970:3001` and `HOST_BIND=0.0.0.0`

## FreeLLMAPI is a Multi-Provider Gateway (Not Just a Router)

FreeLLMAPI normalizes **30+ providers** into one OpenAI-compatible `/v1` endpoint:

| Provider Category | Examples |
|-------------------|----------|
| **OpenAI-compatible** | Groq, Together, NVIDIA NIM, OpenRouter, Cerebras, Fireworks, Perplexity, xAI, DeepInfra |
| **Anthropic** | Direct Claude API |
| **Google** | Gemini (AI Studio + Vertex) |
| **Mistral** | Mistral AI platform |
| **Cohere** | Cohere platform |
| **Hugging Face** | Inference endpoints |
| **Azure / AWS Bedrock** | Enterprise |
| **Local** | Ollama, LM Studio, llama.cpp, vLLM |
| **Custom** | Any OpenAI-compatible base URL |

**Routing strategies**: `balanced`, `latency`, `cost`, `capability`, `round-robin`, `failover-priority` — or `auto` (router picks).

## Verification Checklist

- [ ] Container running: `docker ps | grep freellmapi`
- [ ] Health endpoint: `curl http://127.0.0.1:3970/api/ping`
- [ ] Dashboard loads: `http://127.0.0.1:3970`
- [ ] Account created: login works
- [ ] Unified key generated: `/api/settings/api-key/regenerate`
- [ ] Provider keys added: dashboard Keys page
- [ ] Model test: `/v1/chat/completions` returns content (not "no_providers_configured")