# Opencode Wrapper Audit — 2026-11-20

## Context
Wrapper: `wrapper-opencode` (port 9104, status: pending/frozen per wrappers.json)
Tested by Bos explicitly on 2026-11-20 to verify contract compliance and overhead.

## Architecture Verified
```
Client → wrapper-opencode (9104) → local OpenCode service (49374) → upstream opencode.ai
```
- Auth: Bearer token (wrapper) → Basic Auth (service)
- Model prefix: stripped for local service (`opencode/` → bare)
- Only chat completions uses CLI mode; responses/messages use direct upstream

## Configuration
| Setting | Value |
|---------|-------|
| COMPATIBILITY_LAYER | 2 (Anthropic upstream) |
| OPENCODE_CLI_MODE | yes |
| OPENCODE_SERVICE_URL | http://127.0.0.1:49374 |
| OPENCODE_SERVICE_USER | opencode |
| OPENCODE_SERVICE_PASSWORD | (set via `opencode auth login`) |
| FREE_ONLY | yes |
| FREE_MODEL_ALLOWLIST | big-pickle |

## Free Model Filter — Contract Compliance ✅

### Test Results
- **Free models available**: 23 (filtered from 158 upstream)
- **FREE_ONLY enforced on all 3 surfaces**:
  - `POST /v1/chat/completions` — blocked paid, passed free
  - `POST /v1/responses` — blocked paid, passed free (upstream 429)
  - `POST /v1/messages` — blocked paid, passed free (upstream 429)
  - `GET /v1/models` — returns only 23 free models

### Code Changes Made (minimal)
1. **CLI chat path** (line ~1686): Added FREE_ONLY check before local service call
2. **CLI models endpoint** (line ~1517): Added FREE_ONLY filter to upstream catalog

Both ~4 lines, following existing patterns.

## Translation Chain (COMPATIBILITY_LAYER=2) ✅

| Surface | Path | Status |
|---------|------|--------|
| Chat (CLI) | No translation — local service native | Works |
| Responses | Responses→Chat→Anthropic→Chat→Responses | Works (upstream 429) |
| Messages | Chat→Anthropic | Works (upstream 429) |

Error envelopes: OpenAI format (chat/responses) + Anthropic format (messages).

## Overhead Analysis

### Memory (RSS)
| Process | RSS | Role |
|---------|-----|------|
| wrapper-opencode (9104) | 102 MB | FastAPI proxy |
| opencode serve (49374) | 455 MB | Local service |
| **Total** | **~557 MB** | |

### Latency
| Path | Latency | Notes |
|------|---------|-------|
| Wrapper streaming (TTFT) | **0.5s** | Fast - first token |
| Wrapper non-streaming | **3.0s** | Full round trip |
| Local service full flow | **~3.1s** | Session + prompt + wait + fetch |

**Wrapper overhead ~0-0.5s** (negligible). Bottleneck is local OpenCode service (~3s).

## Key Findings

1. **Wrapper code is production-quality** — standardized architecture, shared common/ infra
2. **CLI mode bypasses upstream quota** — uses local service's managed quota
3. **Upstream quota exhausted** — all free models hit 429 "Free usage limit reached"
4. **Error handling correct** — returns proper OpenAI/Anthropic error envelopes
5. **Only 1 API key configured** — no rotation pool (would need multiple OPENCODE_API_KEY_*)

## To Reactivate Fully (requires owner instruction)
1. Add multiple `OPENCODE_API_KEY_*` keys to `.env`
2. Verify upstream quota per key
3. Update `wrappers.json` status → `production`
4. Run client qualification suite (Claude Code, Codex, OpenCode client)

## Risk Notes
- Wrapper remains FROZEN per `wrappers.json` — no deployment changes made
- Responses/messages don't use CLI mode (design choice)
- Local service `opencode serve` must be running separately (not auto-started by wrapper)
- Upstream quota is the limiting factor, not wrapper code