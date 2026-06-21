# Phase 73 — Canonical SOT Dispatcher Build (2026-06-21)

Session detail: how `ilma_sot_dispatcher.py` + `sot_free_model_picker.py` +
`sot_enrich_capabilities_v2.py` were built and verified end-to-end.

## Why this was built

Bos observed ILMA short-circuiting to `image_generate` tool → xAI
`grok-imagine-image` (Nous-managed, **PAID**) without first querying
SOT for FREE alternatives. Quote: *"kenapa tidak pakai jalur SOT? provider
SOT ada yang bisa digunakan untuk image generation, ini melanggar aturan
ILMA yg wajib pakai model free terbaik yang di sediakan oleh SOT"*

Three mandates were issued:
1. ALL capability MUST go through SOT FREE-only.
2. SOT enrichment must be more robust — capability per model comprehensively.
3. All wiring / workflow / pipeline / runtime must be solidly connected.

## What was built (Phase 73 deliverables)

### Module 1 — `sot/enrichment/sot_enrich_capabilities_v2.py`

30+ capability patterns (vs 8 in v1). Run:

```bash
cd /root/.hermes/profiles/ilma/sot
python3 enrichment/sot_enrich_capabilities_v2.py --full
# 1888 models enriched in 42.1s
```

### Module 2 — `sot/enrichment/sot_free_model_picker.py`

FREE-only picker with strict/soft modes.

### Module 3 — `ilma_sot_dispatcher.py` (CANONICAL)

```python
from ilma_sot_dispatcher import sot_dispatch, sot_dispatch_strict_free, health
result = sot_dispatch("image", strict=False, allow_paid=False)
```

### Wired runtime modules (Phase 73 patches)

- `ilma_subagent_router.route_capability()` — SOT-first routing for any non-chat capability
- `scripts/ilma_image_generator.py` — patched for SOT consultation with multi-provider endpoint caller + xAI fallback
- `ilma_runtime_wiring.LAYER_8_SPECIALIZED` — `ilma_sot_dispatcher` registered (37/37 modules OK)

## E2E verification (2026-06-21)

Image prompt kucing → SOT picked `together/deepgram/flux` (no cred) →
fallback xAI → success + `sot_dispatch` trace. Cost $0.0002.

## Bugs discovered during build (worth keeping handy)

### Bug A — Pyright false positives on `dict(host=...)` literal
Pyright warns "Argument of type 'str | int' cannot be assigned to
parameter 'host'". False positive at runtime — pymongo accepts mixed-
type dicts. Don't fix with `# type: ignore`; runtime is correct.

### Bug B — `MongoClient.command()` scope
PyMongo 4+: `db.command("ping")` fails with `'Collection' object is not
callable.` even when `db` is a Database. **Use `client.admin.command("ping")`
or `client.server_info()`.**

### Bug C — pymongo `$and` silent 0-result
When `$and` branch is a dict that itself doesn't contain `$or`, implicit
single-dict collapses and may bypass filters. Use flat queries or
explicit `"$and": [{"$or": [a, b]}, {c}]`.

### Bug D — `get_db()` double-wrap
If a module does `get_db()["credentials"]` and `get_db()` already returns
a Database → traversal breaks. Document return type clearly, never double-
wrap.

## SOT data-plane state (2026-06-21)

```bash
python3 ilma_sot_dispatcher.py --health
{connected: true, total_models: 2039, active_models: 1888, free_strict: 169,
 endpoint_types: {chat-completions: 1455, image-generations: 158,
                  video-generations: 103, audio-speech: 85, embeddings: 36,
                  audio-transcriptions: 27, moderations: 17, image-edits: 6,
                  rerank: 1}}
```

Strict-free breakdown: 144 chat, 11 moderation, 10 embedding, 2 stt, 1
video, 1 image-edit. **Image/tts/rerank have 0 strict-free** — need
Phase 73a (live billing probe).

## Phase 73a (next phase) — recommended roadmap
| Todo | Approach |
|---|---|
| Live billing probe openrouter+together image | `sot_live_billing_probe.py` (10-model sample POST test, flip `is_free_final` on 200) |
| Wire SOT for TTS / STT modules in ilma.py | Same `sot_dispatch(capability)` pattern |
| Cron: reclassify billing every 12h | Update cron `bf9ad9925449` to also run `sot_billing_classify --full` after sync |
| Strict-mode enforcement | Add `allow_soft_free: bool = False` config; default OFF |
| Audit/dashboard | Add SOT page to `ilma-web-observability-dashboard` |
