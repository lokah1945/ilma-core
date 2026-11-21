# NVIDIA Build-page Context Window Parsing — 1M vs 262144 Contradiction (2026-11-02)

## The trap

`mistralai/mistral-large-4-1t-a52b` on build.nvidia.com is **internally contradictory**:

| Source on page | Value | What it actually is |
|---|---|---|
| `specifications.contextLength` (machine-readable) | **262,144** | Parsed by `parse_build_context()` — but this is really the **max_tokens output cap**, not input context |
| `max_tokens.maximum` (OpenAPI spec) | **262,144** | Max OUTPUT tokens per call |
| Prose description | **"combined input/output context window of up to 1M tokens"** | The REAL context window |

`parse_build_context()` in `common/nvidia_model_specs.py` ONLY reads `spec.attributes.specifications.contextLength` → gets 262144 → wrapper reports `context_window: 262144` in `/v1/models`.

## Live probe proof (2026-11-02, direct to integrate.api.nvidia.com with wrapper key)

| Prompt tokens sent | Result |
|---|---|
| 180,021 | ACCEPTED |
| 291,957 | ACCEPTED (> 262,144 — 262K already exceeded) |
| 360,021 | ACCEPTED |
| 967,763 | ACCEPTED |
| 1,129,054 | REJECTED: `{"details":{"type":"context_length","limit":1048576,"actual":1129054}}` |

**Real limit = 1,048,576 (1M tokens).** The 262,144 in the spec is the max output tokens, mislabeled/duplicated as contextLength.

## Three layered bugs that lock in the wrong value

### Bug A — Parser picks the wrong field
`common/nvidia_model_specs.py::parse_build_context` reads `spec.attributes.specifications.contextLength`. On pages where prose says "1M" but spec says "262144", it trusts the spec field. The spec field appears to be max_tokens, not context window.

### Bug B — Context probe "verify_mode" never climbs higher
`common/model/context_probe.py::_probe_model`: when catalog advertises context (262144), it sets `verify_mode=True` and only probes rungs <= advertised. If 262144 is accepted -> `advertised_verified` -> STOP. Never probes 524288 or 1048576. Log evidence: `mistral-large-4-1t-a52b recorded floor=262155 window=None` (repeated every ~6h, always floor only).

### Bug C — Error parser doesn't recognize NVIDIA's rejection format
`common/context_recovery.py::parse_context_error` returns `None` for NVIDIA's format:
```json
{"details":{"type":"context_length","limit":1048576,"actual":1129054}}
```
It looks for `detail.context_length` or regex in message text, but NVIDIA nests it under `details.type` + `details.limit`. So even when a >1M prompt is rejected, the wrapper can't extract `limit:1048576` as the exact window.

## Diagnostic recipe (read-only, no edits)

```bash
# 1. Fetch the build page and check for contradiction
curl -s "https://build.nvidia.com/<org>/<model>/build" > /tmp/build.html
grep -oE '"contextLength":[0-9]+' /tmp/build.html
grep -oE '.{0,80}1M tokens.{0,80}' /tmp/build.html
# If both exist and differ -> page is self-contradictory; trust the LIVE API, not the spec.

# 2. Live-probe the real limit via integrate.api.nvidia.com (wrapper NVIDIA key from .env)
#    Send ascending token counts (ladder 262K -> 524K -> 1M). First rejection's
#    details.limit is the exact window.

# 3. Check what the wrapper currently reports
curl -s http://127.0.0.1:9101/v1/models > /tmp/models.json
python3 -c "
import json
for m in json.load(open('/tmp/models.json'))['data']:
    if 'mistral-large-4' in m['id']:
        cm = m.get('context_metadata',{})
        print('context_window:', cm.get('context_window'), '| probe:', cm.get('probe'))
"

# 4. Check parser behavior on the page
python3 -c "
import sys; sys.path.insert(0,'/root/wrapper')
from common.nvidia_model_specs import parse_build_context
print(parse_build_context(open('/tmp/build.html').read(), 'mistralai/mistral-large-4-1t-a52b'))
"

# 5. Check error parser on NVIDIA rejection
python3 -c "
import sys; sys.path.insert(0,'/root/wrapper')
from common.context_recovery import parse_context_error
err = {'details':{'type':'context_length','limit':1048576,'actual':1129054}}
print(parse_context_error(400, err))  # None = not recognized
"
```

## NGC featured-models.json does NOT cover this model
The primary source (`assets.ngc.nvidia.com/.../featured-models.json`) has only 4 entries (nemotron-3-ultra, nemotron-3.5-super-vl, glm-5-3, deepseek-v4.1-flash) — all 1M context. `mistral-large-4` is NOT there, so it falls through to build-page scraping -> gets the wrong 262144.

## Rule for future sessions
When a wrapper reports a context window that seems low for a frontier model:
1. Fetch the build page — check if prose contradicts `specifications.contextLength`.
2. Live-probe with ascending token counts against the real API.
3. If live probe accepts > advertised -> the published spec field is wrong (usually max_tokens mislabeled as contextLength).
4. Check `model_context_observations` table in `model-state.db` — if only `floor` recorded, probe never climbed past advertised.
5. Check `parse_context_error(400, nvidia_rejection)` — if None, the rejection parser can't extract the real limit from NVIDIA's `details` format.
