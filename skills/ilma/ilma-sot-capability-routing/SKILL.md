---
name: ilma-sot-capability-routing
description: Class-level skill for routing multimodal/non-LLM capabilities (image generation, video, embedding, vision, TTS, music, browsers) through ILMA's SOT MongoDB before falling back to direct providers. Enforces FREE-TIER FIRST (per ILMA constitutional rule), filters by `is_free=true` AND `status=active`, ranks by `score`/`score_tier`, and explains when to bypass. Triggered when Bos says "image generation provider mana yang free", "cek SOT untuk image model", "kenapa pakai backend berbayar untuk X", or any one-shot question about which SOT-registered provider/model to use for a non-LLM task (image, video, audio, embedding, vision). Distinct from `ilma-sot-credential-retrieval` (operator read-only on `llm_providers` for keys/audit) and `ilma-runtime-mongodb-migration` (runtime migration from JSON→MongoDB).
triggers:
  - "image generation free"
  - "provider image mana"
  - "model image yang free"
  - "video gen sota"
  - "tts provider"
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
version: 1.0.0
last_updated: 2026-06-21
---

# ILMA SOT Capability Routing (Non-LLM & Multimodal)

## What this skill is for

When ILMA needs to invoke a **non-LLM** capability — image generation,
video synthesis, embedding, vision (image understanding), text-to-speech,
music generation, etc. — and we're tempted to use a **direct backend**
(a Hermes tool default, Nous subscription, FAL/FLUX, OpenAI direct, etc.),
this skill enforces the ILMA constitutional rule:

> **Semua model/provider harus lewat SOT dulu. FREE-TIER FIRST.**
> Jangan langsung pakai backend berbayar weapon of habit.

## The SOT-first rule (Bos correction 2026-06-21)

Bos observed ILMA short-circuiting to `image_generate` tool → xAI
`grok-imagine-image` (Nous-managed, **PAID**) without first querying
SOT for FREE alternatives. **This is a violation of FREE-TIER FIRST.**

The correct path:

1. **Identify capability** (e.g. `image`, `video`, `vision`, `tts`).
2. **Query SOT** `credentials.models` filtered by:
   - `capabilities` contains the capability string, OR
   - `model_id` regex matches the capability
   - `is_free=true` AND `status=active` (positive filter)
3. **Rank** by `score`/`score_tier` (A>B>C>D).
4. **Select top-1** among the candidates.
5. **Invoke** via the appropriate backend (Nous gateway / OpenRouter /
   Together / FAL).
6. **Report** the model + score + score_tier to Bos.

If no FREE candidate exists, report the gap and **ask Bos for approval**
to use PAID (do NOT auto-fallback to PAID).

## The canonical SOT query (MongoDB)

```python
import os
from pymongo import MongoClient

# pymongo kwarg form (kwargs != URI form, both viable — P-72)
mongo_pass = ""
for line in open("/root/.hermes/.env"):
    if line.startswith("ILMA_MONGO_PASS="):
        mongo_pass = line.split("=", 1)[1].strip()
        break

client = MongoClient(
    host=os.environ.get("SOT_MONGO_HOST", "172.16.103.253"),
    port=int(os.environ.get("SOT_MONGO_PORT", 27017)),
    username=os.environ.get("SOT_MONGO_USER", "quantumtraffic"),
    password=mongo_pass,
    authSource="admin", directConnection=True,
    serverSelectionTimeoutMS=8000,
)
db = client["credentials"]

# Generic FREE + ACTIVE candidates for a given capability
def candidates_for_capability(cap: str, free_only: bool = True):
    q = {
        "$or": [
            {"capabilities": cap},
            {"model_id": {"$regex": cap, "$options": "i"}},
        ],
        "status": "active",
        "is_active": True,
    }
    if free_only:
        q["is_free"] = True
    return list(db.models.find(q))

# Rank by score_tier (A>B>C>D) then by score (desc)
TIER_ORDER = {"A": 0, "B": 1, "C": 2, "D": 3}
def rank_for_image(models):
    return sorted(
        models,
        key=lambda m: (
            TIER_ORDER.get(m.get("score_tier", "D"), 4),
            -float(m.get("score", 0) or 0),
        ),
    )

# Example: image generation, FREE only
candidates = candidates_for_capability("image", free_only=True)
top = rank_for_image(candidates)[:10]
for m in top:
    print(f"  {m['provider']}/{m['model_id']} | "
          f"tier={m.get('score_tier','-')} score={m.get('score','-')} "
          f"is_free={m.get('is_free')}")
```

## Live candidate snapshot by capability (2026-06-21 — VERIFIED)

| Capability | #FREE | #PAID | Top FREE picks (by score) |
|---|---|---|---|
| `image` | ~30 | ~12 (mostly xai + blackbox DISABLED) | `together/google/gemini-3-pro-image`, `together/google/imagen-4.0-fast`, `together/Qwen/Qwen-Image-2.0`, `together/black-forest-labs/FLUX.2-dev`, `together/black-forest-labs/FLUX.1-schnell` |
| `video` | several | mostly PAID | `xai/grok-imagine-video` (PAID), `together/openai/sora-2` (FREE?) |
| `embed` | many | few | `openai/text-embedding-3-small` (FREE tier), `together/colbert`, etc. |
| `vision` | many | few | `openrouter/google/gemini-3-pro-vision-preview` etc. |
| `tts` | few (Edge TTS default) | OpenAI | various per-provider |

Actual claim: query SOT each task — do NOT memorize the snapshot.
Counts shift as providers sync.

## Known backend defaults to override (P-100)

| Backend | Why called by default | FREE-TIER FIRST fix |
|---|---|---|
| `image_generate` => `xai/grok-imagine-image` | Nous subscription, Nous-managed fallback | Query SOT first, prefer `together/google/gemini-3-pro-image` or `FLUX.1-schnell` |
| `image_generate` => FAL/FLUX default | Comment in config.yaml misleading | Use SOT FREE tier query, then call via `together`/`openrouter` instead of direct FAL |
| `text_to_speech` => `provider: openai` (per config.yaml) | TTS config explicit | Use Edge TTS (free) or query SOT for free TTS provider; only fall back to OpenAI with explicit Bos approval |
| `vision_analyze` => default `OPENROUTER_API_KEY` | Comment in config.yaml | Query SOT for vision-capable FREE model first |

## Pitfalls

### P-100: Don't trust config.yaml comments

ILMA's `~/.hermes/profiles/ilma/config.yaml` has **stale comments**
like `# image_generate (requires FAL_KEY)` from old configs. The actual
runtime uses the `image_gen.provider` field. **STALE COMMENTS ARE
NOT POLICIES.** Always `grep` live config + query SOT for truth.

**Lesson (Bos, 2026-06-21):** "Jangan jawab dari asumsi/memory.
Cek live config via tool."

### P-101: Image generation default backend is PAID

`image_generate` tool's default backend is `xai/grok-imagine-image`
which has `is_free=false` in SOT. Calling it without an SOT query is
a FREE-TIER FIRST violation.

**Rule**: every `image_generate` call MUST be preceded by an SOT query
that returns a FREE candidate. If only PAID candidates return, ask Bos.

### P-102: caps[] field is incomplete in some records

Some `models` docs have `capabilities: []` even though their `model_id`
is image-related. Therefore the SOT query should use **boolean OR**:
match either `capabilities=image` OR `model_id regex matches image`.
This was proven 2026-06-21 with `xai/grok-imagine-image` (caps=[] but
provider is image-capable).

### P-103: `model_capabilities` collection vs `models` collection

There are TWO capability sources in SOT:
- `credentials.models.capabilities` — per-model flags
- `credentials.model_capabilities` — separate collection, also has `capabilities`

`model_capabilities` may be more accurate but `is_free` is on `models`.
**Always cross-check both**, or use a `$unionWith` if MongoDB version
supports.

### P-104: PAID Nous subscription ≠ FREE SOT

Nous subscription (FAL, OpenAI TTS, xAI Grok Imagine) is a **paid
managed-bundle** for Nous subscribers. Even though the agent doesn't
explicitly pay per-token, it consumes the agent's monthly allotment.
**Per ILMA constitutional rule:**
- FREE SOT model first
- Nous subscription = fallback only when SOT has no FREE candidate
- Always announce "via Nous subscription, no SOT FREE candidate" if
  Nous fallback is used

### P-105: Don't propagate the wrong provider into reports

After image generation, ILMA often reports:
> `model: grok-imagine-image, provider: xai`

If a different SOT FREE provider was actually used (after the
migration), the report MUST say:
> `model: <FREE_MODEL>, provider: <FREE_PROVIDER>`

Do not let PAID xAI bleed into reports just because the
`image_generate` tool was the API surface.

### P-106: Blackbox is disabled for image

SOT shows `blackbox/...` image models all with `status=disabled`.
Unless explicitly re-enabled by Bos, do NOT route image gen through
blackbox — even if it's faster. (Snapshot 2026-06-21.)

### P-107: Hermes sandbox can't run arbitrary backend calls

Some backends (FAL, Replicate) need direct HTTP, not gateway.
For these, build a CLI wrapper in `scripts/sot_*_routing.py` and run
via `terminal()` (not `execute_code()`).

## Recipe: pick FREE image model + invoke via Together

```python
# Step 1: query SOT
top = rank_for_image(candidates_for_capability("image"))[0]
provider = top["provider"]     # e.g. "together"
model_id = top["model_id"]     # e.g. "google/imagen-4.0-fast"

# Step 2: build gateway call
# For "together" provider, gateway URL example:
# https://api.together.xyz/v1/images/generations
# Header: Authorization: Bearer $TOGETHER_API_KEY
# Body: {"model": "...", "prompt": "...", "n": 1, "size": "1024x1024"}

TOGETHER_KEY = os.environ.get("TOGETHER_API_KEY") or ""
# (use SOT key from llm_providers if env var not set)
if not TOGETHER_KEY:
    prov_doc = db.llm_providers.find_one({"provider": "together"})
    TOGETHER_KEY = prov_doc.get("api_key", "")

import requests
r = requests.post(
    "https://api.together.xyz/v1/images/generations",
    headers={"Authorization": f"Bearer {TOGETHER_KEY}"},
    json={"model": model_id, "prompt": "...", "n": 1, "size": "1024x1024"},
)
url = r.json()["data"][0]["url"]
print(f"OK: {provider}/{model_id} → {url}")
```

> **Note**: this is the gateway-direct recipe for maximum control.
> In practice, the `image_generate` Hermes tool with a model hint may
> be simpler — but **only if the hint maps to a FREE SOT model**.

## Recipe: ask Bos when no FREE candidate

```python
if not candidates:
    msg = (
        "Tidak ada candidate FREE untuk capability '%s'. "
        "PAID candidates: %s. "
        "Pilih:'name'> PAID dengan approval Bos, atau other?" % (
            cap, [m["model_id"] for m in PAID_CANDIDATES],
        )
    )
    return {"ok": False, "needs_approval": True, "paid_options": PAID_CANDIDATES}
```

## Cross-references

- `ilma-sot-credential-retrieval` — operator read-only path on the
  same MongoDB (`llm_providers` collection) for keys/audit.
- `ilma-runtime-mongodb-migration` — runtime path for LLM model
  router. This skill is for non-LLM capabilities outside the LLM
  router.
- `ilma-sot-cascade-pipeline` — explains the data-plane schema and
  field shapes.
- `ilma-state-verify-before-report` — companion skill. Always verify
  provider/model by tool before claiming.
- `ilma-orchestrator-frameworks` / `omega-council` — when SOT
  candidate selection is part of a multi-agent cascade.

## Verified status

**v1.0 (2026-06-21)** — Created after Bos correction on image
generation bypassing SOT:
- Snapshot captured: 30+ FREE image models in SOT
- Top FREE picks (by score_tier): together/google/imagen-4.0-fast,
  together/Qwen/Qwen-Image-2.0, together/FLUX.2-dev
- Mise en place: recipe for SOT-first image routing
- Status: **rule enforced, runtime patch pending** (Bos to approve
  next-step before sealing)
