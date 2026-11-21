# Cross-Key Cascade 429 Resilience + All-Exhausted Schema

> **Session**: 2026-06-25 (wrapper-nvidia v7 patch)
> **Why this doc exists**: Bos's standing spec — wrapper must be invisible plumbing. Caller NEVER sees 429 except when ALL configured keys have genuinely exhausted for the requested model. Audit confirms this is achievable; this doc records the architectural rules and the all-exhausted response schema that makes it production-grade.

## Architectural Rule: Same-Model, Cross-Key Rotation Only

A wrapper proxy that fronts multiple API keys for one provider MUST follow this cascade:

```
client → POST /v1/chat/completions {model: <M>}

loop MAX_RETRIES + 1 attempts:
  1. acquire_slot(<M>)             # per-(key, model) tracker
  2. POST upstream with chosen key
  3. status=200 → return response, release_slot. DONE.
  4. status=429 → register_rate_limit(state, <M>)   # block ONLY this key for <M>
                  release_slot(state)
                  continue                          # pick another key for SAME <M>
  5. status=500 → release, backoff, continue
  6. attempt exhausted → JSONResponse 429 with full schema
```

**Hard rule**: `acquire_slot(<M>)` always passes the SAME model. We do NOT fall back to a different model when `<M>` is rate-limited. Reasons:
- The caller asked for `<M>` (model-specific logic, output format, reasoning behaviour)
- Swapping models silently would corrupt the caller contract
- If `<M>` is fundamentally unavailable (provider outage), the caller should be told via the structured 429 schema so they can decide (add keys, switch provider, abort)

## Per-(key, model) Block Tracking

Reason: a single upstream provider (NVIDIA NIM) keeps **shared accounts** but **per-model quotas**. Key-A may rate-limit on `glm-5.1` while Key-A is fine for `mixtral-8x`. Tracking RPM only at key granularity treats both as "key blocked" and dodges the model.

```python
# In KeyState
class KeyState:
    rpm: dict[str, float]           # model → rolling RPM
    model_blocks: dict[str, float]  # model → epoch-seconds when block expires
    # ... plus in_flight (concurrency counter)
```

`register_rate_limit(state, model, retry_after_seconds)` writes ONLY `model_blocks[model] = now + retry_after_concise`. Then `_pick_key(model)` skips that key only when considering this specific `model`.

## Pacing: Latency vs 429 Trade-off

Default values for NVIDIA-grade providers with shared per-key QUOTA:

| Knob | Default | Rationale |
|------|---------|-----------|
| `SOFT_LIMIT_RPM` | 30 | Provider's nominal RPM quota (~80% of typical free-tier 40 RPM) |
| `HARD_LIMIT_RPM` | 40 | Tight ceiling — never burst above |
| `PACING_MAX_WAIT` | 60s | If pacing exceeds this, fall back to 429 rather than starve caller |
| `QUEUE_LIMIT` | 1.0 / sec / key | Admission control (resepsionis). FIFO queue, in-flight is unlimited |
| `MAX_RETRIES` | 5 | 1 initial + 5 retries. With 5 keys → covers all-keys-exhausted edge case |

**The pacing-as-latency rule**: caller sees LATENCY, not 429, until genuine exhaustion. This is a *feature*, not a bug — and it's why average latency may look high even on an idle system. Tune by lowering `SOFT_LIMIT_RPM` (less aggression) or raising `QUEUE_LIMIT` (more parallel admits).

## All-Exhausted Response Schema

When `MAX_RETRIES` cycles out with no successful key, return a structured 429 that gives the caller everything needed to make an informed decision (vs. the v6 generic string which left callers blind):

```python
# Inside the proxy retry loop, after the for-loop exits with all_rate_limited:
_pool = pool  # narrow Optional[KeyPool] before attribute access
if _pool is None:
    return JSONResponse(429, {"error": "wrapper-nvidia: pool unavailable"})

secs, scope = _pool.retry_hint(model)
keys_attempted = [s.label for s in _pool.all_stats()        # type: ignore[attr-defined]
                  if s.get("total_429s", 0) > 0
                  or s.get("hard_blocked") or s.get("model_blocks")]
if not keys_attempted:
    keys_attempted = [s.label for s in getattr(_pool, "_states", [])][:MAX_RETRIES]

log.error("All-key rotation exhausted: model=%s retries=%d scope=%s keys=%s",
          model, MAX_RETRIES, scope, ",".join(keys_attempted) or "(none)")

return JSONResponse(
    status_code=429,
    content={
        "error": "wrapper-nvidia: all API keys exhausted for this model",
        "scope": scope,                              # "model" | "all_keys" | "capacity"
        "model": model,
        "keys_attempted": keys_attempted,
        "retries_used": MAX_RETRIES,
        "retry_after": secs,
        "hint": "Add more keys (.env) or wait Retry-After seconds for blocks to expire."
    },
    headers={"Retry-After": str(secs)})
```

### Schema field semantics

| Field | Meaning |
|-------|---------|
| `error` | Human-readable root cause |
| `scope` | "model" = this model-only-blocked on all keys; "all_keys" = all keys browned out; "capacity" = provider returning 429s globally |
| `model` | Echo of requested model (helps caller decide if they should retry with a different model) |
| `keys_attempted` | Key labels that were tried. Empty list = `acquire_slot` rejected every key before even trying (overload, no eligible key) |
| `retries_used` | Number of inner retry attempts (equals `MAX_RETRIES + 1` if it ran to completion) |
| `retry_after` | Seconds until the soonest block expires (or 0 if no blocks) |
| `hint` | Operator action suggestion |

### Pair with `pool.retry_hint()` and `pool.all_stats()`

Both helpers must exist on `KeyPool` for the schema to work. Minimal contract:

```python
def retry_hint(self, model: str) -> tuple[int, str]:
    """Compute (seconds_until_recovery, scope_label)."""
    # scope_label: "model" when model-specific blocks dominate,
    #              "all_keys" when every key hard-blocked,
    #              "capacity" when queue full / pacing overloaded
    ...

def all_stats(self) -> list[dict]:
    """List of dicts, one per key, with fields:
       label, current_rpm, in_flight, hard_blocked, model_blocks (dict), total_429s"""
    ...
```

### Why header + body pair?

`Retry-After` HTTP header is the RFC-7231 standard. Smart clients (`httpx` retry libraries, Envoy, HAProxy, request-middleware boxes) read it without needing body parsing. The body is for human/agent callers that want details.

## Optional[pool] Narrowing Pattern

`pool` is declared `Optional[KeyPool]` and initialized inside FastAPI `lifespan`. Inside request handlers it's referenced many times. Pyright/linters flag `pool.retry_hint` with `reportOptionalMemberAccess`. Pattern to satisfy type-checker without runtime risk:

```python
_pool = pool
if _pool is None:
    return JSONResponse(429, {"error": "wrapper-nvidia: pool unavailable"})
# Now safe to use _pool.retry_hint, _pool.all_stats, etc.
```

Don't blanket-`cast()`. Don't `assert pool is not None`. The narrowing pattern is concise and survives partial-pool conditions (rare but real — crash recovery during lifespan).

## Hot-Reload Pattern (Dynamic Key Count for ELT-staged Credentials)

NVIDIA Free tier rotates expected quota as well as keys. Adding more keys to `.env` while wrapper is running, without restart, uses:

```python
async def _reload_keys_loop():
    """Hot-reload .env keys (additions/removals take effect next cycle)."""
    while True:
        await asyncio.sleep(KEYS_RELOAD_S)
        try:
            load_dotenv(dotenv_path=ENV_PATH, override=False)  # only adds new vars
            new_keys = load_keys_from_env()                   # reads NVIDIA_API_KEY_1..50 + plain
            if new_keys:
                changed = await pool.sync_keys(new_keys)      # idempotent: missing keys dropped,
                                                               # new keys appended, existing kept
        except Exception as e:
            log.error("key reload cycle failed: %s", e)
```

`load_keys()` template (handles any provider by replacing prefix):

```python
def load_keys() -> list[str]:
    keys = []
    for i in range(1, 51):                          # support 1..50 keys dynamically
        k = os.getenv(f"{PREFIX}_API_KEY_{i}", "").strip()
        if k:
            keys.append(k)
    plain = os.getenv(f"{PREFIX}_API_KEY", "").strip()
    if plain:
        keys.append(plain)
    # de-dupe, preserve order
    seen, out = set(), []
    for k in keys:
        if k not in seen:
            seen.add(k); out.append(k)
    return out
```

End-user effect: drop new `NVIDIA_API_KEY_5=***` into `.env`, save, wait `KEYS_RELOAD_S` (60s default), then `/stats` shows `total_keys` increased. No service restart.

## Pitfall Specific to Cross-Key Cascade (Don't Repeat)

1. **`acquire_slot` ignores future model — pass at every call**. A common mistake: `_pick_key()` returns first key but THEN the caller proxies without re-checking the model-limit per key. Always call `pool.acquire_slot(model)` (not `pool.get_best_key()` even if it exists) when downstream proxy needs the model-specific block bitmap.

2. **`all_stats` returns mutable references — never mutate dicts from caller code**. The stats list is the canonical truth read by `/stats`, `/health`, and the dashboard. A request handler that adds fields will leak into the dashboard's response and break consumers.

3. **`Retry-After: 0` is invalid per RFC 7231**. If `retry_after` seconds rounds to 0, emit at minimum 1, or omit the header entirely. Use `secs if secs > 0 else None`.

4. **Don't `try/except` the all-exhausted branch — let it log loudly**. Logging the exhaustion at `ERROR` (not `WARNING`) is intentional: ops needs dashboards to alert on this. Wrap it in noise-suppression only after correlation with the alerting system is verified.

5. **`pacing_ms_total` is per-request, not per-attempt**. If you stack pacing across retries (Pitfall #8 in SKILL.md), the metric explodes and breaks observability. Reset on key-switch.

## Verification Procedure (After Patch)

1. **py_compile**: `python3 -m py_compile main.py && python3 -m py_compile key_pool.py`
2. **FastAPI startup**: `systemctl restart nvidia-wrapper.service; systemctl is-active nvidia-wrapper.service` → `active`
3. **/health returns healthy JSON**: `curl -s http://127.0.0.1:9100/health | jq` → `"status":"ok"`, `total_keys` matches .env count
4. **E2E smoke**: `curl -X POST http://127.0.0.1:9100/v1/chat/completions -d '{"model":"<test>","messages":[...]}'` → `200`
5. **All-exhausted schema** (manual force): temporarily set `MODEL_BLOCK_DEFAULT_SECS=99999`, run 6 parallel requests with 3 keys → all should 429 with the structured body shape

## Cross-Reference: Existing Skill Knowledge

This doc pairs with the existing knowledge in `ilma-llm-wrapper-builder`:
- **Pitfall #6**: `MODEL_BLOCK_DEFAULT_SECS` + `MODEL_BLOCK_CAP` cap — needed so the cross-key cascade stays fast
- **Pitfall #7**: Idle-key (RPM<3) bypass pacing — without this, all-keys cascade triggered despite capacity left
- **Pitfall #8**: Pacing reset (not accumulate) on key-switch — needed so 5-retry cascade doesn't present fake latency
- **References**: `references/latency-audit-keypool-nvidia-2026-06-25.md` — pre/post metrics around the cascade fix
