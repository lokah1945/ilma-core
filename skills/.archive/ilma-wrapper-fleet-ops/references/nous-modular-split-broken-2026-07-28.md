# NOUS Modular Split Broken — 2026-07-28

## Incident
Upstream commit `69af4aa` ("fix: resolve structural inconsistencies and add missing enterprise features") split `nous/src/main.py` into:
- `nous/src/key_pool.py` (extracted KeyEntry, KeyPool + env-watcher + free-only helpers)
- `nous/src/metrics.py` (Metrics)
- `nous/src/main.py` (now imports `from .key_pool import KeyPool` / `from .metrics import metrics`)

The extracted `key_pool.py` was a **broken Frankenstein file** — it kept referencing symbols that only existed in the original `main.py` namespace (or were never imported):
`ModelStateStore`, `MODEL_CATALOG_TTL_SEC`, `asyncio`, `json`, `aiohttp`,
`CircuitBreakerError`, `_UPSTREAM_BREAKER`, `_HAS_CIRCUIT_BREAKER`, `free_only_enabled`,
`get_dynamic_alias_target`, `classify_upstream_error`, etc. (~30 missing symbols per AST scan).

## Symptom
- `systemctl --user is-active wrapper-nous.service` → `activating` (never reaches `active`)
- `curl http://127.0.0.1:9102/health` → `000` (connection refused, process crashed on import)
- Process NOT in `pgrep -af uvicorn` list for port 9102
- Import test (see SKILL.md recipe) → `NameError: name 'Path' is not defined` then `NameError: name 'ModelStateStore' is not defined`

## Root cause
Upstream extracted a slice of `main.py` into `key_pool.py` WITHOUT moving/copying the
imports and module-level definitions those symbols depend on. The audit doc
(`AUDIT_ZERO_BUG_2026-07-28.md`) claimed "syntax validation passed" but never imported/ran it.

## Fix applied (INTENTIONAL divergence)
Reverted nous code to the last working inline commit `7591c70`:
```bash
git checkout 7591c70 -- nous/src/main.py
rm -f nous/src/key_pool.py nous/src/metrics.py
```
Then import-tested, restarted, verified all 6 ports 200. Committed as `0ffe52c`
("fix: pull upstream 69af4aa + revert broken nous modular split").

## Why NOT patch the extracted file
Patching would require adding ~30 missing imports + definitions into `key_pool.py`
(Path, ModelStateStore from common.model_state, asyncio, json, aiohttp, CircuitBreaker,
MODEL_CATALOG_TTL_SEC, etc.) — fragile, and the file also re-defines things main.py
still references. Reverting to the proven inline version is safer and faster.

## Don't re-break it
Future pulls may again try to "modularize" nous. If a new upstream commit re-adds
`nous/src/key_pool.py`, check it imports cleanly FIRST (import-test recipe). If broken,
revert again and note it in the commit message + keep this reference updated.
