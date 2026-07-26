# Production Hardening Session — 2026-06-06

## Commit History
- `0f624d0` — PHASE 1-3: Latency cache, exploration safety, feedback loop
- `6d31f08` — PHASE FINAL: Master reliability update fix + score-change trigger

## Key Metrics (Pre → Post)
| Metric | Before | After |
|--------|--------|-------|
| Routing latency (warm) | 21.65ms | 15.5ms (−28%) |
| Candidates per query | 516 | 64 |
| Active models | 27 | 82 |
| NVIDIA dominance | 100% | 67% |
| Unique models in Monte Carlo | 1 | 5+ |
| Production readiness score | 90/100 | **100/100** |

## Master Key Format Discovery
```
Provider ≠ intuitive name. Must search.
deepseek-v4-pro   → ollama provider (not deepseek-ai!)
minimax-m2.7      → nvidia provider (not minimaxai!)
MiniMax-M3        → minimax provider ✓
```
Always verify with:
```python
for pname, pdata in master["providers"].items():
    if target in pdata["models"]:
        print(f"Found in {pname}")
```

## Double-Prefix Bug (model_id already has provider prefix)
```python
# WRONG: creates "minimax/minimax/MiniMax-M3"
key = f"{provider}/{model_id}"

# CORRECT: strip bare model_id first
bare_id = model_id.rsplit("/", 1)[-1]
key = f"{provider}/{bare_id}"  # → "minimax/MiniMax-M3"
```

## Exploration Models (top_k=30 required)
```
top_k=5:  exploration models at rank 12-15 → NOT in pool ❌
top_k=30: exploration models at rank 12-15, 27-30 → in pool ✅
```
Also need `is_free=True` so `route_spread(allow_paid=False)` includes them.

## Score Change Trigger
- Job ID: `a115de75d3ef` (Hourly Optimizer from cron/jobs.json)
- Threshold: >10% absolute reliability change between flushes
- Command: `subprocess.run(["hermes", "cron", "run", JOB_ID])`