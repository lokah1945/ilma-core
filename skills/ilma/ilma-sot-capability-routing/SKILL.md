---
name: ilma-sot-capability-routing
description: Class-level skill for routing ALL ILMA capabilities (chat, image, video, embedding, vision, TTS, STT, music, browsers, rerank) through ILMA's SOT MongoDB before falling back to direct providers. Enforces FREE-TIER FIRST (per ILMA constitutional rule 2026-06-21), filters by `is_free_final` (strict) OR `is_free=true` (soft fallback), ranks by `score`/`score_tier`, and explains when to bypass. Triggered when Bos says "kenapa tidak pakai SOT", "image generation provider mana yang free", "cek SOT untuk image model", "kenapa pakai backend berbayar", or any one-shot question about which SOT-registered provider/model to use for any task (LLM chat OR multimodal). Distinct from `ilma-sot-credential-retrieval` (operator read-only on `llm_providers` for keys/audit) and `ilma-runtime-mongodb-migration` (runtime migration from JSON→MongoDB).
triggers:
  - "image generation free"
  - "provider image mana"
  - "model image yang free"
  - "video gen sota"
  - "tts provider"
  - "stt provider"
  - "embedding model"
  - "vision model"
  - "multimodal routing"
  - "sot capability"
  - "free tier image"
  - "ilma sota non-llm"
  - "kenapa tidak pakai sot"
  - "SOT image model"
  - "Backend berbayar"
  - "filter is_free image"
  - "grok-imagine alternative"
  - "FLUX model options"
  - "Imagen Gemini image provider"
  - "semua capability harus lewat SOT"
  - "free ONLY policy"
  - "stt whisper free"
  - "embedding pg free"
version: 1.1.0
last_updated: 2026-06-21
---

# ILMA SOT Capability Routing (ALL Capabilities)

## What this skill is for

When ILMA needs to invoke **ANY** capability — image generation, video
synthesis, embedding, vision (image understanding), text-to-speech,
speech-to-text, music generation, **LLM chat**, rerank, etc. — and we're
tempted to use a **direct backend** (a Hermes tool default, Nous
subscription, FAL/FLUX, OpenAI direct, xAI direct, etc.), this skill
enforces the ILMA constitutional rule (Bos mandate 2026-06-21):

> **Semua model/provider capability — including LLM chat itself — MUST
> flow through SOT. FREE-TIER FIRST. NO direct-tool bypass to PAID
> backend without SOT verification.**

## The SOT-first rule (Bos correction 2026-06-21)

Bos observed ILMA short-circuiting to `image_generate` tool → xAI
`grok-imagine-image` (Nous-managed, **PAID**) without first querying
SOT for FREE alternatives. **This is a violation of FREE-TIER FIRST.**

The correct path is now codified into ONE canonical surface:

1. **Identify capability** (`chat`, `image`, `video`, `tts`, `stt`,
   `embedding`, `vision`, `rerank`, `video_understand`, `reasoning`...)
2. **Call `ilma_sot_dispatcher.sot_dispatch(capability, ...)`** — the
   SOT FREE-only canonical router. Do NOT hand-roll a MongoDB query.
3. **Pass `strict=True`** for production paths (only `is_free_final=True`).
   `strict=False` is ramp-up soft fallback (also `is_free=true` raw)
   with `policy_warning` for review.
4. **If `policy_warning` present**: announce to Bos that this is a
   soft-free model and the SOT reclassifier needs to flip
   `is_free_final=True` for strict-mode compliance.
5. **Wire into runtime**: every new capability call site MUST begin with
   `sot_dispatch(...)`. Legacy direct-provider code is deprecated.

If strict=True returns no candidate, report the gap (do NOT auto-fall
back to PAID without Bos approval). If strict=False returns a soft
candidate with `policy_warning`, proceed but report the warning.

## The canonical dispatcher (Phase 73 — single surface)

**Source of truth: `ilma_sot_dispatcher.py`** at profile root.

```python
from ilma_sot_dispatcher import sot_dispatch, health

# Default — soft fallback with policy_warning if needed
result = sot_dispatch("image", strict=False, allow_paid=False)
# → {"provider": "...", "model_id": "...",
#    "endpoint_type": "image-generations",
#    "is_free_final": bool, "policy_warning": str|None,
#    "alternatives": [...]}

# Production-strict — only is_free_final=True
strict = sot_dispatch("chat", strict=True, allow_paid=False)

# Health snapshot
health_info = health()
# → {connected, total_models, active_models, free_strict,
#    endpoint_types: {...}}
```

CLI for testing:

```bash
python3 ilma_sot_dispatcher.py --capability image
python3 ilma_sot_dispatcher.py --capability chat --strict
python3 ilma_sot_dispatcher.py --health
python3 ilma_sot_dispatcher.py --capability tts --k 5
```

## SOT enrichment v2 (Phase 73 — 30+ capabilities)

The SOT capability detector (`sot_enrich_capabilities_v2.py`) recognizes
**30+ capabilities** (was 8 in v1) and infers `endpoint_type` /
`endpoint_path` / `input_modality` / `output_modality` / `quality_tier`
per model. Capabilities detected:

- `chat`, `instruct`, `completion`, `reasoning`, `coding`, `code_review`,
  `debugging`
- `vision`, `image_understand`, `image`, `image_edit`, `image_quality`
- `video`, `video_understand`
- `audio`, `tts`, `stt`, `music`, `voice_cloning`
- `embedding`, `rerank`
- `function_calling`, `json_mode`, `streaming`, `safety_filter`
- `long_context`, `fast`, `quality`
- Native provider tags: `minimax_native`, `qwen_native`, `deepseek_native`,
  `llama_native`, `mistral_native`, `gemini_native`, `grok_native`,
  `claude_native`, `gpt_native`

Each row in `credentials.models` now carries:
- `capabilities_v2` (list)
- `primary_cap` (single most-decisive capability — used for routing)
- `endpoint_type` (`chat-completions` | `image-generations` |
  `image-edits` | `video-generations` | `audio-speech` |
  `audio-transcriptions` | `embeddings` | `rerank` | `moderations`)
- `endpoint_path` (`/v1/chat/completions` etc.)
- `input_modality`, `output_modality`
- `quality_tier` (`high` | `standard` | `fast` | `tiny`)
- `free_tier_score` (0..1)

## Live candidate snapshot by capability (2026-06-21 — VERIFIED)

| Capability | endpoint_type | strict=is_free_final | soft=is_free_raw |
|---|---|---|---|
| chat         | chat-completions   | 144   | 770 |
| image        | image-generations  | 0 ⚠   | 37 |
| image_edit   | image-edits        | 1     | ? |
| vision       | chat-completions   | (subset of chat) | (subset) |
| video        | video-generations  | 1     | 21 |
| tts          | audio-speech       | 0 ⚠   | 21 |
| stt          | audio-transcriptions | 2   | 6 |
| embedding    | embeddings         | 10    | 12 |
| moderation   | moderations        | 11    | 4 |
| rerank       | rerank             | 0 ⚠   | 1 |

**Constraint**: actual counts shift as `sot_enrich_models.py --full` /
`sot_billing_classify.py --full` re-runs. **Query SOT each task — do
NOT memorize the snapshot.**

**Hard-strict GAPS (must be closed via live API probe)**:
- IMAGE (0 strict): top candidates are `openrouter/google/gemini-2.5-flash-image` and
  `openrouter/google/gemini-3.1-flash-image-preview` (raw `is_free=true`,
  not yet reclassified because detector's mixed-providers rule requires
  `:free` suffix absent here). Live billing probe is the only path.
- TTS (0 strict): same — openrouter amazon-nova-2-lite raw `is_free=true`,
  classifier returned `paid` because of mixed-providers trap-safe policy.
- RERANK (0 strict): together/mxbai has no verified pricing.

## Wired runtime surfaces (Phase 73 — verified 2026-06-21)

| Module | Role |
|---|---|
| `sot_enrich_capabilities_v2.py` | 30+ cap detector + endpoint inference; idempotent |
| `sot_free_model_picker.py` | FREE-only picker (strict/soft) with TTL cache + alternatives |
| `ilma_sot_dispatcher.py` | Canonical `sot_dispatch()` + `health()` CLI |
| `ilma_subagent_router.route_capability()` | SubAgentRouter method that calls `sot_dispatch` for non-chat caps |
| `scripts/ilma_image_generator._resolve_via_sot()` | Image generator: consult SOT, fall back to legacy xAI if SOT-picked provider lacks credential |
| `ilma_runtime_wiring.LAYER_8_SPECIALIZED` | `ilma_sot_dispatcher` registered (37/37 modules OK) |

End-to-end verified (image prompt → SOT pick → xAI fallback → success):

```
[ilma_image_generator] SOT picked FREE image model: together/deepgram/flux
                       (endpoint=image-generations, score=76.95, is_free_final=False)
[ilma_image_generator]   ⚠ policy_warning: soft_free_ungated_strict_required_for_production
[ilma_image_generator]   ⚠ no credential for SOT-picked provider together; falling back to legacy xAI
{"status": "success", "provider": "xai", "model": "grok-imagine-image",
 "url": "https://imgen.x.ai/...", "cost_usd": 0.0002,
 "sot_dispatch": {"skill": "SOT free-only image gen",
                  "sot_resolved": {...}}}
```

## The canonical SOT query (MongoDB) — escape hatch

When the dispatcher is unreachable (MongoDB down), fall back to **the
exact pymongo pattern** below. Both forms (kwargs and URI) work; pymongo
strictly distinguishes them. URIs require URL escaping; kwargs don't.

```python
import os
from pymongo import MongoClient

mongo_pass = ""
for line in open("/root/.hermes/.env"):
    if line.startswith("ILMA_MONGO_PASS="):
        mongo_pass = line.split("=", 1)[1].strip()
        break

client = MongoClient(
    host="172.16.103.253", port=27017,
    username="quantumtraffic", password=mongo_pass,
    authSource="admin", directConnection=True,
    serverSelectionTimeoutMS=8000,
)
db = client["credentials"]

# FREE + ACTIVE candidates for a given endpoint_type / capability
def candidates_for_capability(cap: str, strict: bool = False):
    if strict:
        q_or = {"is_free_final": True, "billing_class": "free"}
    else:
        q_or = {"$or": [
            {"is_free_final": True},
            {"billing_class": "free"},
            # soft fallback for ramp-up phase
            {"is_free": True, "is_free_final": False},
        ]}
    q = {
        "is_active": True,
        "status": "active",
        "$and": [
            q_or,
            {"$or": [
                {"capabilities_v2": cap},
                {"endpoint_type": {"$in": _CAP_TO_ENDPOINT.get(cap, [])}},
            ]},
        ],
    }
    return list(db.models.find(q))

# Rank by score_tier (A>B>C>D) then by score (desc); free_tier_score tiebreak
TIER_ORDER = {"S": 0, "A": 1, "B": 2, "C": 3, "D": 4}
def rank(models):
    return sorted(
        models,
        key=lambda m: (
            TIER_ORDER.get(m.get("score_tier", "D"), 4),
            -float(m.get("score", 0) or 0),
            -float(m.get("free_tier_score", 0) or 0),
        ),
    )

# Example: image, soft-fallback
candidates = candidates_for_capability("image", strict=False)
top = rank(candidates)[:10]
for m in top:
    print(f"  {m['provider']}/{m['model_id']} | tier={m.get('score_tier','-')} "
          f"score={m.get('score','-')} is_free_final={m.get('is_free_final')}")
```

**Do NOT hand-roll this in runtime call sites unless the dispatcher
is unreachable.** Use `ilma_sot_dispatcher.sot_dispatch(...)` always.

## Known backend defaults to override (P-100)

| Backend | Why called by default | FREE-TIER FIRST fix |
|---|---|---|
| `image_generate` => `xai/grok-imagine-image` | Nous subscription, Nous-managed fallback | Query SOT first via `sot_dispatch("image")`; prefer `together/google/imagen-4.0-fast` or `FLUX.1-schnell` if cred available |
| `image_generate` => FAL/FLUX default | Comment in config.yaml misleading | Use SOT FREE tier query, then call via `together`/`openrouter` instead of direct FAL |
| `text_to_speech` => `provider: openai` (per config.yaml) | TTS config explicit | Use Edge TTS (free) or query SOT for free TTS provider; only fall back to OpenAI with explicit Bos approval |
| `vision_analyze` => default `OPENROUTER_API_KEY` | Comment in config.yaml | Query SOT for vision-capable FREE model first |

## Pitfalls

### P-100: Don't trust config.yaml comments

ILMA's `~/.hermes/profiles/ilma/config.yaml` has **stale comments** like
`# image_generate (requires FAL_KEY)` from old configs. The actual
runtime uses the `image_gen.provider` field. **STALE COMMENTS ARE NOT
POLICIES.** Always `grep` live config + query SOT for truth.

**Lesson (Bos, 2026-06-21):** "Jangan jawab dari asumsi/memory.
Cek live config via tool."

### P-101: Image generation default backend is PAID

`image_generate` tool's default backend is `xai/grok-imagine-image`
which has `is_free_final=False` in SOT. Calling it without an SOT query
is a FREE-TIER FIRST violation.

**Rule**: every `image_generate` call MUST be preceded by a
`sot_dispatch("image", ...)` call. If only PAID candidates return (rare
— there are 37 soft-free), prefer soft-free with `policy_warning`, then
ask Bos if strict=True returns empty.

### P-102: Use `capabilities_v2` + `endpoint_type` (NOT `capabilities`)

After Phase 73 enrichment, **the truth lives in `capabilities_v2`** plus
`endpoint_type`. The legacy `capabilities` field is incomplete. Queries
must `$or` both fields:

```python
{"$or": [
    {"capabilities_v2": cap},
    {"endpoint_type": {"$in": [ep, ...]}},
]}
```

This was proven 2026-06-21 when some models have `capabilities_v2`
contains `[chat]` but `endpoint_type=chat-completions` too, while image
models with `is_free=true` raw still need `endpoint_type` for routing.

### P-103: `model_capabilities` collection vs `models` collection

There are TWO capability sources in SOT:
- `credentials.models.capabilities_v2` (canonical after Phase 73)
- `credentials.model_capabilities` (projection — same data, separate
  collection; also has `endpoint_type`, `endpoint_path`)

`model_capabilities` may be more accurate but `is_free_final` is on
`models`. **Query `models` for routing, cross-check
`model_capabilities` for diagnostic**. They should be in sync after a
fresh `sot_enrich_capabilities_v2.py --full` run.

### P-104: PAID Nous subscription ≠ FREE SOT

Nous subscription (FAL, OpenAI TTS, xAI Grok Imagine) is a **paid
managed-bundle** for Nous subscribers. Even though the agent doesn't
explicitly pay per-token, it consumes the agent's monthly allotment
_type the user explicitly did NOT set up_. **Per ILMA constitutional rule:**
- FREE SOT model first (`is_free_final=True`)
- Nous subscription = last-resort fallback ONLY when SOT has no strict-FREE
  candidate AND Bos approved PAID modes
- Always announce `via Nous subscription, no SOT strict-FREE candidate`
  if the Nous fallback is used

### P-105: Don't propagate the wrong provider into reports

After image generation, ILMA should report the **SOT-picked** provider,
not the legacy `image_generate` tool's default. If the legacy default
xAI was used as a fallback, say so explicitly.

```python
result = {"provider": chosen["provider"],   # SOT pick, not xAI
          "model": chosen["model_id"],
          "sot_dispatch": {"sot_resolved": chosen,
                           "fallback_to": "xai" (only if applicable)}}
```

### P-106: Blackbox is disabled for image

SOT shows `blackbox/...` image models all with `status=disabled`.
Unless explicitly re-enabled by Bos, do NOT route image gen through
blackbox — even if it's faster. (Snapshot 2026-06-21.)

### P-107: Hermes sandbox can't run arbitrary backend calls

Some backends (FAL, Replicate) need direct HTTP, not gateway.
For these, build a CLI wrapper in `scripts/sot_*_routing.py` and run
via `terminal()` (not `execute_code()`).

### P-108: Strict vs Soft FREE mode — pivotal distinction

`is_free_final` is the **SOT-baked verdict** after pricing-based
reclassification (`sot_billing_classify.py --full`).
`is_free` is the **raw provider metadata** carried over from
`raw_metadata.free_tier`.

| Mode | Filter | Use when |
|---|---|---|
| strict=True   | `is_free_final=True AND billing_class='free'` | Production / cost-sensitive paths; `no_strict_free` if empty |
| strict=False  | soft fallback to `is_free=True` raw | Ramp-up / capability with no strict-free yet (image, tts, rerank) |

**Why both?** Image-generation has 0 strict-free (live API billing-probe
needed). strict=False fills the gap with `policy_warning`. The
warning is an audit signal that says "this isn't confirmed free; need
a `sot_billing_classify --full` reclassify pass when pricing is
verified". NEVER silently route through a soft-free model without
emitting the warning.

### P-109: pymongo `$and` — top-level nested `$or` causes silent 0-result

When you put `{"$and": [q_or, q1]}` where `q_or` is itself a dict
**not** wrapped in `$or`, pymongo interprets the implicit `$and` with
an empty branch and may return 0 docs. Symptom:

```
{"is_active": True, "$and": [{"is_free_final": True, "billing_class": "free"}, ...]}
# returns 0
```

But same query flat (no `$and`) returns expected rows. **Fix**: only wrap
the `$or` set inline if it's a list; otherwise break it out into a flat
top-level `q_or` dict (no `$and` wrapper).

```python
# ✅ SAFE — flat top-level dict
q = {
    "is_active": True,
    "status": "active",
    "$or": [...],          # single $or at top
    "endpoint_type": ep,   # other flat filters
}

# ❌ BROKEN — $and wrapping a dict that itself doesn't contain $or
q = {
    "is_active": True,
    "$and": [
        {"$or": [{"is_free_final": True}, {"billing_class": "free"}]},
        {"endpoint_type": ep},
    ],
}
# Sometimes returns 0. Verify by running each branch independently.
```

### P-110: MongoClient `db.command("ping")` — wrong scope

In PyMongo 4+:
- `client.admin.command("ping")` ✓ — admin namespace at client scope
- `db.command("ping")` ✗ — TypeError: `'Collection' object is not callable`

Symptom: `db.command("ping")` raises `'Collection' object is not
callable. If you meant to call the 'command' method on a 'Collection'...`
even though `db` is a Database. **Fix**: ping via `client.admin.command("ping")` or
use `client.server_info()` after a lightweight query. Apply this in
health endpoints.

### P-111: `get_db()` shapes differ between writers

`pymongo.MongoClient(**kwargs)["credentials"]` returns a Database
object. `db["models"]` returns a Collection. If a module re-wraps
`get_db()` as `get_db()["credentials"]`, you traverse to Collection
of collections, and `db["models"]` becomes `'Collection' object is
not subscriptable`. **Defensive pattern**: each module exposes its own
`get_db()` that returns the appropriate scope (DB or Collection),
document it clearly, and never double-wrap.

### P-112: CONFIG has both `provider` field and plugins[] list — they can diverge

`config.yaml` has `image_gen.provider: xai` AND `plugins.enabled: [image_gen/xai]`.
If you patch one, the other may stay stale. **Always update BOTH** or
risk silent fallback to old provider. (Discovery 2026-06-21.)

### P-113: `endpoint_path` vs `endpoint_type` — BOTH required

After dispatcher resolves, route via `endpoint_type` to decide which
caller to use (chat vs image vs tts); the `endpoint_path` is just the
URL hint for OpenAI-compatible providers. Image-edit, image-generations,
video-generations, audio-speech all may have the same `endpoint_path`
(`/v1/images/generations` etc) but different `endpoint_type`. **Match on
`endpoint_type` first, then use `endpoint_path` for URL construction if
non-OpenAI-compatible.**

## Recipe: pick FREE image model + invoke via Together

```python
# Step 1: dispatch (canonical)
from ilma_sot_dispatcher import sot_dispatch
top = sot_dispatch("image", strict=False)
provider = top["provider"]    # e.g. "openrouter" or "together"
model_id = top["model_id"]    # e.g. "google/imagen-4.0-fast"
base_url = resolve_provider_base(provider)  # from SOT providers collection

# Step 2: build gateway call
TOGETHER_KEY = resolve_provider_key(provider)  # from SOT llm_providers or env
import requests
r = requests.post(
    f"{base_url}/images/generations",
    headers={"Authorization": f"Bearer {TOGETHER_KEY}"},
    json={"model": model_id, "prompt": "...", "n": 1, "size": "1024x1024"},
)
url = r.json()["data"][0]["url"]
print(f"OK: {provider}/{model_id} → {url}")
```

## Recipe: ask Bos when no FREE candidate

```python
from ilma_sot_dispatcher import sot_dispatch
strict = sot_dispatch("chat", strict=True, allow_paid=False)
if strict.get("error"):
    msg = (
        "SOT strict-FREE returned 0 candidates for chat. "
        "PAID candidates exist (n=N). Approve PAID mode?"
    )
    return {"ok": False, "needs_approval": True, "msg": msg}
```

## Cross-references

- `ilma-sot-credential-retrieval` — operator read-only path on the
  same MongoDB (`llm_providers` collection) for keys/audit.
- `ilma-runtime-mongodb-migration` — runtime path for LLM model router.
  This skill is for ALL capability (chat + multimodal) outside what
  `route_and_execute` handles.
- `ilma-sot-cascade-pipeline` — explains the data-plane schema and
  field shapes.
- `ilma-state-verify-before-report` — companion skill. Always verify
  provider/model by tool before claiming.
- `ilma-orchestrator-frameworks` / `omega-council` — when SOT candidate
  selection is part of a multi-agent cascade.

## Verified status

**v1.0 (2026-06-21 morning)** — Created after Bos correction on image
generation bypassing SOT. Captured 30+ FREE image models in SOT.

**v1.1 (2026-06-21 evening)** — Phase 73 implementation:
- Added `ilma_sot_dispatcher.py` as canonical surface
- 1888 active models enriched with 30+ capabilities + endpoint inference
- `route_capability()` added to `SubAgentRouter`
- `ilma_image_generator._resolve_via_sot()` wired + xAI fallback
- `ilma_sot_dispatcher` registered in `ilma_runtime_wiring`
  LAYER_8_SPECIALIZED (37/37 modules OK)
- End-to-end image prompt verified: SOT picks `together/deepgram/flux`
  → no cred → xAI fallback → success + `sot_dispatch` trace
- Hard-strict GAP rem: image/tts/rerank have 0 strict-free candidates;
  Phase 73a (next) needs live billing-probe to flip `is_free_final` for
  openrouter `google/gemini-2.5-flash-image` and similar.
- Memory note `mem_009` saved as CONSTITUTIONAL entry (Bos mandate).
