# Wrapper Audit & SOT Sync Pattern (2026-06-29)

## When to use

Auditing local AI wrapper services (NVIDIA, Antigravity, Cloudflare, etc.) and syncing their models into MongoDB SOT.

## The canonical 4-step pattern

### Step 1: Probe wrapper health

```bash
curl -s http://127.0.0.1:PORT/health
curl -s http://127.0.0.1:PORT/v1/models | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'{len(d.get(\"data\",[]))} models')"
```

### Step 2: Live chat test (light model)

```bash
curl -s --max-time 30 -X POST http://127.0.0.1:PORT/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"LIGHT_MODEL","messages":[{"role":"user","content":"OK"}],"max_tokens":5}'
```

Use a light model (meta/llama-3.2-3b-instruct, deepseek flash) — NOT heavy models like glm-5.1 which timeout on 30s.

### Step 3: Sync models to T3 (`credentials.models`)

```python
from pymongo import MongoClient
from datetime import datetime

client = MongoClient("mongodb://localhost:27017/")
db = client["credentials"]
now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

for model_id in wrapper_model_list:
    existing = db["models"].find_one({"model_id": model_id, "provider": PROVIDER_NAME})
    doc = {
        "model_id": model_id, "provider": PROVIDER_NAME,
        "model_name": model_id, "is_active": True,
        "is_free": True, "free_bypass": True,
        "free_reason": "wrapper_local", "free_tier_score": 1.0,
        "price_per_m_input": "0", "price_per_m_output": "0",
        "discovered_at": now, "discovered_via": "ilma_phase_73_sync",
        "updated_at": now
    }
    if existing:
        db["models"].update_one({"_id": existing["_id"]}, {"$set": {"updated_at": now, "is_active": True}})
    else:
        db["models"].insert_one(doc)
```

### Step 4: Register/update provider in T1 (`credentials.llm_providers`)

```python
db["llm_providers"].insert_one({
    "provider": PROVIDER_NAME,
    "endpoint": "http://127.0.0.1:PORT",
    "api_base": "http://127.0.0.1:PORT/v1",
    "account_email": "wrapper",
    "api_key": "***",
    "key_status": "VALID",
    "is_active": True,
    "key_purpose": "inference",
    "free_bypass": True,
    "added": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
    "added_by": "ilma_phase_73",
    "note": "..."
})
```

To update existing: use `$set` (not plain dict):
```python
db["llm_providers"].update_one(
    {"provider": PROVIDER_NAME},
    {"$set": {"endpoint": "...", "port": PORT, "updated_at": now}}
)
```

## Verified wrappers (2026-06-29)

| Wrapper | Port | Models | Process | Systemd |
|---------|------|--------|---------|---------|
| wrapper-nvidia | 9100 | 121 | Node.js v4.6.0, PID 138632 | ❌ manual |
| wrapper-antigravity | 9101 | 147 (8 native + 139 NIM) | uvicorn, PID 140647 | ❌ manual |
| wrapper-cloudflare | 9104 | — | — | ✅ systemd |

Both nvidia + antigravity run MANUALLY (no unit file). If server reboots, they won't auto-start.

## SOT tiering (Bos 2026-06-29)

```
T1 = llm_providers    (primary — provider list + credentials)
T2 = providers         (secondary — detail config)
T3 = models            (tertiary — model catalog)
```

All in DB `credentials` at `mongodb://localhost:27017/`.

## Pitfall: pymongo `update_one` without `$set`

```python
# ❌ BROKEN
db["llm_providers"].update_one({"provider": "X"}, {"endpoint": "..."})
# ValueError: update only works with $ operators

# ✅ CORRECT
db["llm_providers"].update_one({"provider": "X"}, {"$set": {"endpoint": "..."}})
```