# ILMA Model DB Singleton Pattern — Integration Notes

## Pattern

Single-writer rule: `scripts/ilma_model_db_manager.py` is the ONLY file that writes to:
- `ilma_model_router_data/PROVIDER_INTELLIGENCE_MASTER.json`
- `ilma_model_router_data/benchmark_database.json`

All other scripts (enricher, autoloop, db_pipeline, optimizer daemon) delegate to this manager.

## Version History

| Version | Date | Key Change |
|---------|------|-----------|
| v5.0 | 2026-05-24 | Initial single-source-of-truth rewrite |
| v6.0 | 2026-05-24 | AYDA credential store integration, OpenRouter management API, all 12 providers |

## Integration Points

### ilma_optimizer_daemon.py
Phase 1b: `model_db_sync` — called after runtime_wiring in `run_optimizer()`.

```python
sys.path.insert(0, str(ILMA_ROOT / "scripts"))
from ilma_model_db_manager import ModelDatabaseManager
mgr = ModelDatabaseManager(dry_run=False, git_push=False)
r = mgr.full_sync()
results["model_db_sync"] = r
```

### ilma_benchmark_autoloop.py
`update_provider_db()` delegates to `ModelDatabaseManager`.

### scripts/ilma_db_pipeline.py
Slim CLI wrapper that acquires lock and calls manager.

### Cron
Schedule: `0 0,12 * * *` — runs manager with `--full-sync --git-push`

## Provider API Key Mapping

```python
# credential store key → env var fallback
openrouter  → OPENROUTER_API_KEY
nvidia      → NVIDIA_API_KEY
together    → TOGETHER_API_KEY
groq        → GROQ_API_KEY
cohere      → COHERE_API_KEY
ollama      → OLLAMA_API_KEY
cerebras    → CEREBRAS_API_KEY
blackbox    → BLACKBOX_API_KEY
aimlapi     → AIMLAPI_KEY
xai         → XAI_API_KEY
perplexity  → PERPLEXITY_API_KEY
you         → YOU_API_KEY
```

## Known Issues

- 403 Cloudflare blocking on: together, groq, cerebras, you, aimlapi — TRANSIENT, IP-based
- blackbox endpoint wrong (404) — needs URL correction
- cohere no API key in credential store