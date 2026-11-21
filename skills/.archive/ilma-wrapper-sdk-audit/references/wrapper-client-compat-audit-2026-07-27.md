# Wrapper Client/SDK Compatibility Audit — Findings 2026-07-27

## Scope
Audit of `/root/wrapper` multi-service LLM wrappers for compatibility with agent/clients:
- **Claude Code** → Anthropic Messages API `/v1/messages`
- **Codex CLI** → OpenAI Responses API `/v1/responses` (`wire_api=responses`)
- **Hermes Agent** → OpenAI Chat + Anthropic
- **OpenClaw** → OpenAI-compatible `/v1/chat/completions`

## Audit recipe (independent, read-only)
1. `git pull github` (NOT `origin` — origin is local bare repo `/root/wrapper_remote.git`)
2. Live probe each service: `/health` + `/v1/models` + functional E2E chat (curl, bypass assumptions)
3. Read translation layers: `nvidia-python/src/responses_compat.py`, `anthropic_compat.py`, `common/translations/shared.py`, `nous/wrapper_nous.py`
4. Check control-plane wiring: is `MODEL_REGISTRY_URL` set? (see production-audit reference)
5. Check in-memory stores for bounds (`_RESPONSE_STORE`, `_bounded_store`)

## Client-compat matrix (verified by code path)
| Client | Endpoint | Wrapper path | Status |
|--------|----------|--------------|--------|
| Claude Code | /v1/messages | anthropic_to_openai → upstream; stream via stream_openai_to_anthropic | ✅ |
| Codex CLI | /v1/responses | ResponsesStreamState (Codex-spec events: output_item.added before delta, response.completed once) | ✅ |
| Hermes | /v1/chat/completions + /v1/messages | all wrappers | ✅ |
| OpenClaw | /v1/chat/completions | all wrappers | ✅ |

## Bug patterns affecting clients (file:line)
- **B1** `nous/wrapper_nous.py:822` `_RESPONSE_STORE` UNBOUNDED → OOM under Codex/OpenClaw long multi-turn. nvidia caps at 200 (`_bounded_store` in responses_compat.py). FIX: bound nous store identically.
- **B5** `nous/wrapper_nous.py:790-795` `responses_to_chat` maps `developer` role → `user` (not `system`) → system prompt loss if Claude Code/Codex send `developer` role. FIX: map developer→system (mirror responses_compat.py:174 `normalized_role = 'system' if role == 'developer'`).
- **B6** `nvidia-python/src/anthropic_compat.py:175-192` context truncation can orphan `tool_calls` (no guard on assistant+tool pair boundary). FIX: run repair_orphan_tool_messages after truncation.
- **B7** `nvidia-python/src/responses_compat.py:420-431` `is_nvidia_model` returns True when cache empty → accepts non-nvidia models, fails upstream with confusing 404/401. FIX: prefix-check fallback (`model_id.startswith('nvidia/')`) when cache empty.

## Future-risk table
| Risk | Trigger | Sev | Mitigation |
|------|---------|-----|------------|
| B1 leak | Codex/OpenClaw long sessions | CRIT | bound store (cap ~200-500 + TTL) |
| B5 dev role | Claude Code/Codex send developer role | MED | map→system |
| B6 tool orphan | >100k ctx truncation | MED | repair orphans post-truncation |
| Responses schema change | OpenAI/Codex version bump | MED | pin Codex version + schema test |
| Anthropic cache_control | future SDK requires passthrough | LOW | monitor SDK changes |

## Bos convention
Audit reports → `/root/wrapper/audit_report/` (gitignored). Overrides older `/root/audit_report/` guidance.
