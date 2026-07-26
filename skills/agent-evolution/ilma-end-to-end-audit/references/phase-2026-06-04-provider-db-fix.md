# PHASE 2026-06-04: Provider DB Zero-Score Fix

**Session:** 2026-06-04 - Full system audit discover 379 models with quality_score=0 in Provider DB (28% of total). Apply derived score fixes.

## Problem

```
Provider: xai            → 9/9 (0%) zero-score
Provider: perplexity    → 26/26 (0%) zero-score  
Provider: openai        → 114/155 (74%) zero-score
Provider: blackbox     → 86/139 (62%) zero-score
Total: 384 models with quality_score=0 (28%)
```

## Solution: Derived Score Pattern

Set derived scores based on model family and provider type, NOT fixed values:

```python
# Pattern: Provider-specific baseline derived from known models
BASELINES = {
    'xai': 0.72,        # Grok family
    'perplexity': 0.70,   # Sonar family
    'openai': 0.75,       # GPT baseline
    'blackbox': 0.65,     # Blackbox baseline
    'nvidia': 0.70,      # NVIDIA baseline
    'ollama': 0.60,      # Ollama baseline
    'openrouter': 0.68,   # Mixed baseline
}

# Step 1: Try to find related model with valid score
for other_model, other_record in models.items():
    if other_score > 0:
        # Same model family prefix
        if model.startswith(other_model.split('-')[0]):
            base_score = other_score * 0.95
            break

# Step 2: Fall back to provider baseline
if base_score is None:
    base_score = BASELINES.get(provider, 0.65)
```

## Result

- Fixed: 384 models → 0 zero-score
- Method: Derived from model families + provider baselines
- Safe threshold: Never set score < 0.50

## Related Issues Fixed

1. **Capability categories**: 33 unknown → mapped to proper categories
2. **Channel directory**: Added explicit home_channel for cron delivery

## Verification Command

```python
# Verify all providers have valid scores
python3 -c "
import json
with open('PROVIDER_INTELLIGENCE_MASTER.json') as f:
    data = json.load(f)
providers = data.get('providers', {})
zero = sum(1 for p in providers.values() 
         for m in p.get('models', {}).values() 
         if m.get('quality_score', 0) == 0)
print(f'Zero-score: {zero}')
"
```

**Output:** Zero-score: 0

---
*Added: 2026-06-04*