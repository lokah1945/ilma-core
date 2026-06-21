---
name: ilma-capability-registry
description: Lookup Hermes<->ILMA<->SOT capability mapping. Single source of truth in SOT `credentials._meta.capability_registry` and `credentials.models.{capabilities_v2,hermes_caps}`. Use when listing what ILMA can handle, finding models that satisfy a Hermes handle (e.g. vision_analyze, text_to_speech, llm.coding), or auditing capability coverage.
---

# ILMA Unified Capability Registry v1.0.0 (2026-06-21)

## Purpose
Single source of truth for the 25 ILMA capabilities and how they map to:
- Hermes default toolset/skill handles
- SOT `primary_cap` field in `credentials.models`
- Each model's `capabilities_v2` (multi-cap array) and `hermes_caps` (multi-Hermes-handle array)

## The 25 Capabilities

| primary_cap | hermes_default | nous_subscription | ilma_layer | modality |
|---|---|---|---|---|
| chat | ✓ | — | code | text→text |
| coding | ✓ | — | code | text→text |
| reasoning | ✓ | — | code | text→text |
| tts | ✓ | ✓ | voice | text→audio |
| stt | ✓ | — | voice | audio→text |
| embedding | ✓ | — | memory | text→vector |
| image | ✓ | ✓ | creative | text→image |
| image_edit | ✓ | ✓ | creative | image→image |
| vision | ✓ | — | code | image→text |
| rerank | — | — | memory | text→text |
| video | ✓ | — | creative | text→video |
| music | ✓ | — | creative | text→audio |
| browser | ✓ | ✓ | browser | interaction |
| messaging | ✓ | — | platform | io |
| voice_conversation | ✓ | ✓ | voice | full-duplex |
| delegation | ✓ | — | core | control |
| memory | ✓ | — | memory | io |
| cron | ✓ | — | platform | control |
| search | ✓ | — | research | text→text |
| research | ✓ | — | research | text→text |
| computer_use | ✓ | — | browser | control |
| kanban | ✓ | — | platform | control |
| goals | ✓ | — | platform | control |
| mcp | ✓ | — | platform | control |
| file_editing | ✓ | — | core | io |

## Lookup API (preferred)

```python
from ilma_sot_dispatcher import sot_dispatch

# Full registry
reg = sot_dispatch.get_capability_registry()
# -> {taxonomy: {<cap>: {hermes, sot, primary_cap, ilma_layer, modality, ...}}, count, counts_by_layer, ...}

# Find models by Hermes handle (multi-cap aware)
models = sot_dispatch.lookup_models_by_hermes_cap("vision_analyze", strict=True, limit=10)
# -> [{model_id, provider, primary_cap, capabilities_v2, hermes_caps, ...}, ...]

# Find free model for a primary_cap
m = sot_dispatch("chat", strict=True)
# -> {provider, model_id, ...}
```

## SOT Collection Mapping

| SOT field | Type | Purpose |
|---|---|---|
| `credentials._meta.capability_registry` | singleton doc | 25 caps × cross-system wiring |
| `credentials.models.primary_cap` | str | Main capability (denormalized, fast query) |
| `credentials.models.endpoint_type` | str | Provider endpoint shape |
| `credentials.models.input_modality` | str | Source kind |
| `credentials.models.output_modality` | str | Sink kind |
| `credentials.models.capabilities_v2` | list[str] | Multi-cap per model |
| `credentials.models.hermes_caps` | list[str] | Multi-Hermes-handle per model (new) |

## Re-running the seeds (idempotent)

```bash
# 1. Seed the registry doc
python3 /tmp/seed_capability_registry.py

# 2. Enrich every active model with hermes_caps
python3 /tmp/enrich_models_hermes_caps.py
```

After seeding, you can re-run the dispatcher code unchanged — it will read the registry from `_meta`, look up models in O(1) via the indexed `hermes_caps` Array field, and dispatch to the right provider.

## Hermes Default Channels (per v0.16.0)

- **CLI:** 50+ commands, e.g. `chat`, `model`, `fallback`, `gateway`, `setup`, `config`, `cron`, `kanban`, `claw`
- **Toolsets:** 28+ — `terminal, browser, file, web, vision, skills, memory, tts, code_execution, delegation, cron, todo, clarify, moa, image_gen, feishu, discord, yuanbao, spotify, mcp, kanban, messaging, hearing, stepvoice`
- **Skills library:** 218 bundles (`hermes skills list`)
- **Models:** chat-completions, image-generations, audio-speech, audio-transcriptions, embeddings, rerank, image-edits, video-generations, moderations
- **Nous subscription perks:** Firecrawl (web), FAL (image), OpenAI TTS, Whisper STT, Browser Use

## How to verify the registry is intact

```python
from ilma_sot_dispatcher import sot_dispatch
h = sot_dispatch.health()
# h['connected'] == True, h['endpoint_types'] has all 8 types
reg = sot_dispatch.get_capability_registry()
# reg['count'] == 25
```
