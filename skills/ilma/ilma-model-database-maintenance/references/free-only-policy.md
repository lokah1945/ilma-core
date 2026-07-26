# FREE_ONLY Policy — Three-Layer Enforcement (v2.0)

**Date:** 2026-05-24
**Commitment:** Bos MANDATED — no paid model at runtime unless explicitly overridden.

---

## Overview

`FREE_ONLY_MODE=True` by default. No model routing, delegate_task, kanban orchestration, or sub-agent can touch a paid model without `ILMA_ALLOW_PAID=1` set by Bos/admin.

---

## Layer 1 — DB Sync (`scripts/ilma_model_db_manager.py`)

**File:** `ilma_model_router_data/PROVIDER_INTELLIGENCE_MASTER.json`

`PROVIDER_CONFIGS` forces `free_tier=True` at data-ingestion time:

```python
PROVIDER_CONFIGS = {
    "nvidia":      {"free_tier": True,    "ALL FREE — NVIDIA NIM"},
    "minimax":     {"free_tier": True,    "ALL FREE — MiniMax API"},
    "perplexity":  {"free_tier": True,    "ALL FREE — Perplexity"},
    "xai":         {"free_tier": True,    "ALL FREE — xAI"},
    "ollama":      {"free_tier": True,    "local models=FREE"},
    "deepseek":    {"free_tier": True,    "ALL FREE"},
    "meta":        {"free_tier": True,    "ALL FREE"},
    "mistral":     {"free_tier": True,    "ALL FREE"},
    "cohere":      {"free_tier": True,    "ALL FREE"},
    "amazon":      {"free_tier": True,    "ALL FREE"},
    "google":      {"free_tier": True,    "ALL FREE"},
    "anthropic":   {"free_tier": True,    "ALL FREE"},
    "openai":      {"free_tier": True,    "ALL FREE"},
    "alibaba":     {"free_tier": True,    "ALL FREE"},
    "useai":       {"free_tier": True,    "ALL FREE"},
    "openrouter":  {"free_tier": False,  "MIXED — per-model free_or_paid from API"},
    "blackbox":    {"free_tier": True,   "ALL FREE — Bos mandate"},
    # together, groq, cerebras, fireworks → free_tier=False (default) → BLOCKED
}
```

**Result:** MASTER data has correct `free_tier` flags. Data layer is correct by construction.

---

## Layer 2 — Registry Gate (`ilma_model_registry.py`)

```python
FREE_ONLY_MODE    = os.environ.get("ILMA_ALLOW_PAID","0") != "1"  # DEFAULT: True

FREE_PROVIDERS    = {nvidia, minimax, perplexity, xai, ollama,
                     deepseek, meta, mistral, cohere, amazon,
                     microsoft-azure, ai21-labs, google, anthropic,
                     openai, alibaba, useai}  # 17 providers

MIXED_PROVIDERS  = {"openrouter", "blackbox"}  # use is_free from MASTER

# ModelInfo.is_free property:
#   if FREE_ONLY_MODE and provider in FREE_PROVIDERS  → True
#   elif FREE_ONLY_MODE and provider in MIXED_PROVIDERS → free_or_paid=="FREE"
#   elif not FREE_ONLY_MODE                             → stored value

# ModelInfo.is_active property:
#   if FREE_ONLY_MODE and provider not in (FREE_PROVIDERS | MIXED_PROVIDERS) → False
#   elif FREE_ONLY_MODE and provider in MIXED_PROVIDERS → availability=="ACTIVE" and free
#   else → availability=="ACTIVE"
```

**Result:** Access-control layer. Even if router bypasses is_free, is_active blocks unknown/paid-only providers.

---

## Layer 3 — Router (`ilma_subagent_router.py`)

Already filters by `model.is_free` + `model.is_active` in:
- `_select_task_fallback()` (line ~216)
- `_select_emergency_fallback()` (line ~294)

```python
# Health-aware fallback chain (always respects FREE_ONLY_MODE via is_free):
# 1. task-specific healthy models (is_free=True, is_active=True)
# 2. general healthy models (is_free=True, is_active=True)
# 3. ALL healthy models (is_free=True, is_active=True) — emergency only
```

---

## Override (Bos/Admin Only)

```bash
export ILMA_ALLOW_PAID=1
```

All 3 layers lift. Paid models become eligible in routing.

---

## Provider Classification Summary

| Class | Providers | Enforcement |
|-------|-----------|-------------|
| FREE (17) | nvidia, minimax, perplexity, xai, ollama, deepseek, meta, mistral, cohere, amazon, ms-azure, ai21-labs, google, anthropic, openai, alibaba, useai | `is_free=True`, `is_active=True` always |
| MIXED (2) | openrouter, blackbox | `is_free` from per-model `free_or_paid` field in MASTER |
| BLOCKED | together, cerebras, groq, fireworks, ai21, and all others | `is_active=False` under FREE_ONLY_MODE |

---

## Verification

```bash
# Test FREE_ONLY_MODE is active
cd /root/.hermes/profiles/ilma
python3 -c "
from ilma_model_registry import FREE_ONLY_MODE, FREE_PROVIDERS, MIXED_PROVIDERS
print(f'FREE_ONLY_MODE={FREE_ONLY_MODE}')
print(f'FREE_PROVIDERS={len(FREE_PROVIDERS)} providers')
print(f'MIXED_PROVIDERS={MIXED_PROVIDERS}')
"

# Test a paid-only provider is blocked
python3 -c "
from ilma_model_registry import get_model
m = get_model('together/llama-3-70b-chat')
print(f'is_free={m.is_free if m else None}')
print(f'is_active={m.is_active if m else None}')
"

# Expected: is_free=False or is_active=False under FREE_ONLY_MODE
```

---

## Git History

- **Commit c02a510 (2026-05-24):** `feat(free-only): enforce FREE ONLY policy at DB, registry, and router layers`
- **Previous pipeline commit 043fcea:** `feat(end-to-end): solid model-db pipeline v6.0 — single source of truth`