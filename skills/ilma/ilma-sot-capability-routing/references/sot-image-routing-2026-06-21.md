# SOT Image Generation Routing — Evidence & Eigenvalue Reference

**Session captured:** 2026-06-21 (Bos correction on FREE-TIER FIRST for image generation)

## Snapshot (verified live)

Collections inspected: `credentials.models` & `credentials.model_capabilities`.

### FREE image models in SOT (top 10 by score)

```
together/google/gemini-3-pro-image                 | fast caps | tier=? score=?
together/google/imagen-4.0-fast                    | fast caps | 1k best for fast
together/google/imagen-4.0-ultra                   |   -       | high quality
together/Qwen/Qwen-Image-2.0                       |   -       | Qwen
together/Qwen/Qwen-Image-2.0-Pro                   |   -       |
together/Qwen/Qwen-Image                           |   -       |
together/black-forest-labs/FLUX.2-dev              | code caps | FLUX
together/black-forest-labs/FLUX.2-flex             |   -       |
together/black-forest-labs/FLUX.2-pro              |   -       |
together/black-forest-labs/FLUX.2-max              |   -       |
together/black-forest-labs/FLUX.1.1-pro            |   -       |
together/black-forest-labs/FLUX.1-kontext-pro      |   -       |
together/black-forest-labs/FLUX.1-kontext-max      |   -       |
together/openai/gpt-image-1.5                      |   -       |
together/openai/gpt-image-2                        |   -       |
together/openai/sora-2                             |   -       |
together/google/flash-image-3.1                    | fast caps |
together/Wan-AI/Wan2.6-image                       |   -       |
together/stable-diffusion-xl-base-1.0              | instruct  |
together/google/flash-image-2.5                    | fast caps |
openrouter/openai/gpt-5-image                      |   -       |
openrouter/openai/gpt-5.4-image-2                  |   -       |
openrouter/openai/gpt-5-image-mini                 | fast caps |
openrouter/google/gemini-3.1-flash-image-preview   | fast caps |
openrouter/google/gemini-3-pro-image-preview       | fast caps |
openrouter/google/gemini-3-pro-image               | fast caps |
openrouter/google/gemini-3.1-flash-image           | fast caps |
openrouter/google/gemini-2.5-flash-image           | fast caps |
```

### PAID + DISABLED image models (DO NOT use by default)

```
PAID:
xai/grok-imagine-image              | free=False | active | selected by Nous default
xai/grok-imagine-image-quality      | free=False | active
xai/grok-imagine-video              | free=False | active
xai/grok-imagine-video-1.5          | free=False | active

DISABLED (skip):
bluesminds/grok-imagine-image-lite  | status=disabled
blackbox/*| status=disabled (all image models)
```

## Lesson recap

Bos: "kenapa tidak pakai jalur SOT? provider SOT ada yang bisa digunakan untuk
image generation, ini melanggar aturan ILMA yg wajib pakai model free terbaik
yang di sediakan oleh SOT"

→ ILMA `image_generate` defaulted to xAI (`grok-imagine-image`) WITHOUT:
1️⃣ Querying SOT for FREE alternatives.
2️⃣ Filtering by `is_free=True`.
3️⃣ Applying `score_tier` ranking.

→ Violation of constitutional `FREE-TIER FIRST` rule.

## Concrete fix (pending Bos approval)

Modify ILMA runtime so that:
- `image_generate` call first runs `candidates_for_capability("image", free_only=True)`.
- If ≥1 FREE candidate exists → select top-by-tier, override `provider` hint.
- If 0 FREE candidate → ask Bos approval before PAID.

For now: this is a SKILL-LEVEL rule; runtime enforcement is a Phase 73+
task tracked separately.
