# Codex v0.145.0 dynamic `/v1/models` — full ModelInfo enrichment (silence "metadata not found" WITHOUT a static catalog)

Verified 2026-07-24 against `wrapper-nous` @127.0.0.1:9106, Codex CLI v0.145.0.

## Context
The task was "Codex config using wrapper-nous as backend, **dynamic model discovery**, model selectable at runtime." The wrapper already served `/v1/models` with OpenAI-style minimal entries. Codex accepted the models and `codex exec -m <id>` worked, **but** logged:
```
warning: Model metadata for `tencent/hy3:free` not found. Defaulting to fallback metadata
```
This is NOT harmless if you want clean runs. The fix below keeps discovery **fully dynamic** (no `model_catalog_json` freeze) yet makes every model a schema-complete Codex `ModelInfo`, so the warning disappears.

## Root cause (Codex v0.145.0 is strict)
Codex's `codex_models_manager` parses the models response with a full `ModelInfo` struct (~38 fields). The wrapper returned only ~9 fields. Codex surfaced a chain of `missing field 'X'` decode errors, then fell back to degraded metadata per model. Required fields discovered empirically (in decode-error order):
1. Top-level key **`models`** (not just OpenAI-standard `data`) — `failed to decode models response: missing field 'models'`
2. Per-entry **`slug`** — `missing field 'slug'`
3. Per-entry **`base_instructions`** — `missing field 'base_instructions'`
4. Then a full `ModelInfo` (display_name, description, default_reasoning_level, supported_reasoning_levels[4], shell_type, visibility, supported_in_api, priority, supports_reasoning_summaries, default_reasoning_summary, support_verbosity, default_verbosity, apply_patch_tool_type, web_search_tool_type, truncation_policy, supports_parallel_tool_calls, supports_image_detail_original, max_context_window, effective_context_window_percent, experimental_supported_tools, input_modalities, supports_search_tool, use_responses_lite, model_messages, …) → ends at a 40-field entry, warning gone.

## The fix (template-clone technique — stays dynamic)
Do NOT hand-build 40 fields (error-prone) and do NOT use a static `model_catalog.json` (kills discovery). Instead:

**Step 1 — make a metadata template from a real Codex catalog entry:**
```python
# one-time generation
import json
src = json.load(open('/root/.codex/model_catalog.json'))
entry = dict(src['models'][0])          # a schema-complete Codex ModelInfo
json.dump({'models': [entry]}, open('/root/wrapper/nous/model_catalog_template.json', 'w'), indent=2)
```
This `model_catalog_template.json` is used ONLY for the *metadata shape* — the model LIST still comes live from upstream.

**Step 2 — load the template as the base in `get_model_meta`:**
```python
_CATALOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model_catalog_template.json")
_MODEL_INFO_TEMPLATE = {}

def _load_model_info_template():
    global _MODEL_INFO_TEMPLATE
    if _MODEL_INFO_TEMPLATE:
        return _MODEL_INFO_TEMPLATE
    base = { /* 30-ish field fallback if template missing */ }
    try:
        if os.path.exists(_CATALOG_PATH):
            with open(_CATALOG_PATH) as f:
                cat = json.load(f)
            models = cat.get("models", []) if isinstance(cat, dict) else []
            if models:
                _MODEL_INFO_TEMPLATE = dict(models[0])   # full Codex schema
                return _MODEL_INFO_TEMPLATE
    except Exception:
        pass
    _MODEL_INFO_TEMPLATE = base
    return _MODEL_INFO_TEMPLATE

def get_model_meta(mid):
    rooted = resolve_model(mid) if mid else mid
    base = dict(_load_model_info_template())     # full Codex ModelInfo base
    base.update({
        "id": mid,
        "slug": mid,                              # Codex REQUIRES slug == id
        "object": "model",
        "created": 0,
        "owned_by": "alias" if is_alias_name(mid) else "nous",
        "display_name": mid,
        "description": f"{mid} via wrapper-nous (Nous Chat)",
    })
    concrete = rooted if not is_alias_name(rooted) else get_dynamic_alias_target()
    if concrete and concrete in MODEL_METADATA:
        base.update(MODEL_METADATA[concrete])
    if is_alias_name(mid) and concrete:
        base["rooted_model"] = concrete
        base["dynamic_alias"] = True
    return base
```

**Step 3 — endpoint return BOTH `data` and `models` (Codex parses `models`):**
```python
return {"object": "list", "data": enriched, "models": enriched,
        "free_only": free_only_enabled(),
        "dynamic_alias_target": get_dynamic_alias_target() or None}
```

**Step 4 — fix latent `get_token`/`get_session` NameError in `/v1/models`:**
The endpoint called `await get_token()` / `await get_session()` but neither was defined (latent bug, only triggered once discovery actually hit the endpoint). Add:
```python
_SESSION = None
async def get_token():
    return STATIC_KEY                      # env NOUS_API_KEY
async def get_session():
    global _SESSION
    if _SESSION is None or _SESSION.closed:
        _SESSION = aiohttp.ClientSession()
    return _SESSION
```

## Verify
```bash
curl -s http://127.0.0.1:9106/v1/models -o /tmp/m.json
python3 -c "import json;d=json.load(open('/tmp/m.json'));m=d['data'][0];print('models key:', 'models' in d);print('fields:', len(m));print('slug:', 'slug' in m);print('base_instructions:', 'base_instructions' in m)"
# then:
cd /tmp && codex exec --model tencent/hy3:free "Reply with exactly: CLEAN" 2>&1 | grep -iE "warning|metadata not found|missing field"
# → empty grep = success
```
Verified: both `tencent/hy3:free` and `poolside/laguna-s-2.1:free` ran with ZERO warnings.

## Pitfall discovered: Docker overlay-fs persistence
On this host `/root` is a Docker overlay mount. Edits made via the `patch` tool reported success but did NOT persist to the running process (a later `read_file` showed the old code; `grep -c` on disk = 0). Symptoms: you patch `get_model_meta`, restart the wrapper, but `/v1/models` still returns 9-field minimal entries.
**Workaround that worked:** write the patch via a terminal `python3` heredoc (`cat > /tmp/x.py <<'PY' … open(p).write(s) …`) and confirm persistence with terminal `md5sum` / `grep -c` — do NOT trust the `patch` tool's "success" here, and do NOT trust `read_file` which may read a different overlay layer. After a terminal write, `grep -c` on disk must be >0 before restarting the wrapper.

## Blocker that is OUT OF SCOPE (not a config bug)
After discovery is clean, `codex exec` may still fail with:
```
401 Unauthorized: Your API key is invalid, blocked or out of funds … portal.nousresearch.com
```
This means `NOUS_API_KEY` in `/root/wrapper/nous/.env` is empty/expired (upstream auth), NOT a Codex/wrapper wiring problem. Fix belongs to the wrapper's `.env`, not `config.toml`.
