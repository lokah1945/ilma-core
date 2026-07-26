references/verification-recipes.md

# Verification Recipes — "Verify State Before Report" Cheat-Sheet

This is the **operator-style reference** for the skills in
`ilma-state-verify-before-report`. It condenses the most common
state-claims that the agent has to verify, and shows the exact tool
calls. Use these recipes **before** answering any question that
asserts current state.

> Rule: never answer "what model am I running / what provider am I
> using / what's the active config" from memory alone. Always run one
> of these recipes first.

---

## 1. Active model + provider (Hermes profile)

```bash
PROFILE=ilma
grep -nE '^\s*default:|^\s*provider:|^\s*fallback_providers:' \
  /root/.hermes/profiles/$PROFILE/config.yaml | head -20
```

**Output to read:**
- `model.default` — name like `minimaxai/minimax-m3` (this is *what* runs)
- `model.provider` — often a wrapper (`wrapper-nvidia`, `ollama-cloud`)
- `providers.*.model` — for fallback routing
- `custom_providers.*.model` — for ad-hoc routing

**Pitfall:** `minimaxai/minimax-m3` + `provider: minimax` ≠ `provider:
wrapper-nvidia`. The model name may include a vendor prefix; the
provider is the actual upstream call target.

---

## 2. env-style secrets (without echoing them)

```bash
PROFILE=ilma
grep -E '^MINIMAX_|=sk-|=eyJ' \
  /root/.hermes/profiles/$PROFILE/.env \
  /root/.hermes/.env 2>/dev/null | head -30
```

For the *literal* value (e.g. when validating with the provider's
CLI), capture into a variable, never echo:

```bash
KEY=$(grep -E '^MINIMAX_API_KEY=' /root/.hermes/profiles/ilma/.env | cut -d= -f2-)
mmx auth login --api-key "$KEY"
```

---

## 3. Service / port / systemd state

```bash
systemctl --user is-active ilma-chrome.service
systemctl --user is-active hermes-agent.service
ss -tlnp | grep -E ':9222|:9223' || true
```

---

## 4. MongoDB collection existence + sample schema

```bash
python3 - <<'PY'
from pymongo import MongoClient
c = MongoClient(host='172.16.103.253', port=27017,
    username='quantumtraffic', password='***REDACTED-SEE-.env***',
    authSource='admin', directConnection=True)
db = c['credentials']
print('collections:', sorted(db.list_collection_names()))
sample = db.llm_providers.find_one({})
print('llm_providers schema:', sorted(sample.keys()) if sample else 'EMPTY')
PY
```

---

## 5. Cron jobs

```bash
crontab -l 2>/dev/null | head -30
test -f /root/.hermes/cron/jobs.json && cat /root/.hermes/cron/jobs.json
```

For jobs clean view: `python3 -c "import json; print(json.dumps(json.load(open('/root/.hermes/cron/jobs.json'))['jobs'], indent=2))" | head -40`

---

## 6. Browser active profile / CDP

```bash
grep -nE 'profile_name|active_profile|cdp_url|user-data-dir' \
  /root/.hermes/profiles/$PROFILE/config.yaml

curl -sS http://127.0.0.1:9222/json/version | python3 -m json.tool
```

---

## 7. Capability claims (after `ilma --status`)

```bash
python3 - <<'PY'
import json
# ilma_runtime_wiring.py --verify prints 31 modules + statuses.
import subprocess
r = subprocess.run(['python3', '/root/.hermes/profiles/ilma/ilma_runtime_wiring.py', '--verify'],
                   capture_output=True, text=True)
print(r.stdout[-1500:])
PY
```

---

## 8. Reconciling memory vs tool

When memory says X, but tool says Y:

1. Print both side by side.
2. The tool wins. Example:
   - Memory: "minimax from provider minimax"
   - Tool: `model.provider = wrapper-nvidia`
   - **Answer:** "Tool says provider=wrapper-nvidia. Memory saya
     perlu di-update (atau saya mis-baca header)."
3. Update memory with the diff so future sessions don't repeat the error.

---

## Common mistakes caught by these recipes

| Mistake | Catch |
|---|---|
| "I'm running provider `foo`" (asserted from header) | Tool says `wrapper-bar` — wrong |
| "API key `sk-...` exists" (from memory) | Tool says `***` shortcut literal — masked |
| "Service is running" (assumed) | `is-active`: `inactive`/`failed` |
| "Model `minimax-m3` is reachable" (assumed) | `mmx auth status`: 401 — actually gateway down |
| "We have 1374 models" (from old memory) | DB count now 978 — purged |

The pattern is always the same: **first tool, then claim**.

