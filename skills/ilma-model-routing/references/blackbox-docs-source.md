# BlackBox Docs Source — End-to-End Implementation

> Last Updated: 2026-05-24

## The Problem

BlackBox API is **100% broken** — all endpoints return HTTP 4xx/5xx:

| Endpoint | Status | Error |
|---|---|---|
| `https://api.blackbox.ai/api/models` | ❌ 404 | Not Found |
| `https://api.blackbox.ai/models` | ❌ 500 | Internal Server Error |
| `https://api.blackbox.ai/chat/models` | ❌ 404 | Not Found |
| `https://api.blackbox.ai/v1/models` | ❌ 500 | Internal Server Error |

API key exists (`BLACKBOX_API_KEY` in `.env`) but all endpoints fail.

## The Solution: Docs Page Scraping

**Source URL:** `https://docs.blackbox.ai/api-reference/models/chat-pricing`

This documentation page has an HTML table with model data:
- **339 rows** × **5 columns**
- Columns: Model Name | Model ID | Input Cost | Output Cost | Context Length
- **55 models** marked "Free" in Input Cost column

### Parsing Approach

```python
import re

def _fetch_blackbox_docs_model_list():
    """Fetch from docs page, return list of model IDs."""
    url = "https://docs.blackbox.ai/api-reference/models/chat-pricing"
    response = requests.get(url, timeout=30)
    html = response.text  # 714,381 bytes
    
    # Parse table cells: 5 columns per row
    cells = re.findall(r'<td[^>]*>(.*?)</td>', html)
    rows = [cells[i:i+5] for i in range(0, len(cells), 5)]
    
    # Column 0 = Model Name, Column 1 = Model ID, Column 2 = Input Cost
    free_models = []
    all_models = []
    
    for row in rows[1:]:  # Skip header
        if len(row) >= 3:
            model_id = row[1].strip()
            in_cost = row[2].strip().lower()
            
            if model_id and not model_id.startswith('Model'):
                all_models.append(model_id)
                if in_cost == "free":
                    free_models.append(model_id)
    
    return all_models, free_models  # 339 total, 55 free
```

### Free Model Detection Logic

**CRITICAL:** `in_cost.lower() == "free"` (capital "Free" in HTML text), NOT `pricing == 0.0`.

BlackBox stores **ALL 83 models** with `pricing.input_per_1m=0.0` and `pricing.output_per_1m=0.0` — this is a placeholder, NOT real pricing data. Only the HTML text "Free" in the cost column is the authoritative free indicator.

## Provider Config

```python
PROVIDER_CONFIGS = {
    "blackbox": {
        "url": "https://docs.blackbox.ai/api-reference/models/chat-pricing",
        "fmt": "blackbox-docs",  # Custom format handler
        "env_var": "BLACKBOX_API_KEY",
        "skip_key": True,  # Docs page needs no API key
        "active": True,
    }
}
```

## Format Handler in `_fetch_provider_models()`

```python
elif fmt == "blackbox-docs":
    # No JSON API — fetch HTML docs page
    resp = httpx.get(url, timeout=30.0)
    html = resp.text
    
    # Parse HTML table → model list
    all_mids, free_mids = self._parse_blackbox_docs_html(html)
    
    result = []
    for mid in all_mids:
        minfo = {
            "model_id": mid,
            "free_tier": mid in free_mids,
            "source": "blackbox-docs",
        }
        result.append((mid, minfo))
    return result
```

## Sync Handler in `sync_providers()`

```python
elif fmt == "blackbox-docs":
    models_raw = self._fetch_provider_models("blackbox", blackbox_cfg)
    
    free_ids = {mid for mid, minfo in models_raw if minfo.get("free_tier")}
    paid_ids = {mid for mid, minfo in models_raw if not minfo.get("free_tier")}
    
    self._update_provider_models(
        "blackbox",
        free_model_ids=free_ids,
        paid_model_ids=paid_ids,
        is_active=True,  # Was banned_provider, now active
    )
```

## Results (Post-Fix 2026-05-24)

| Metric | Before | After |
|--------|--------|-------|
| BlackBox models in MASTER | 83 (stale snapshot) | 138 (live sync) |
| BlackBox FREE models | 1 | 56 |
| BlackBox PAID models | 82 | 82 |
| Provider status | `banned_provider` | `active` |
| Total FREE models (all providers) | — | 427/1,339 |

## Key Lessons

1. **Docs page scraping works when API is broken** — check docs first before declaring a provider dead
2. **`pricing=0.0` is never a free indicator** — BlackBox had $0 for ALL models (paid + free)
3. **HTML text "Free" is the actual free signal** — parse the column text, not the JSON pricing field
4. **`skip_key=True` for docs-only providers** — no API key needed when scraping the public docs page
5. **Merge strategy: docs free list + MASTER paid list** — don't lose historical paid model data