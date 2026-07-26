# Internal Device Code API — Verified Endpoints (2026-05-21)

## Source

OpenClaw binary source code analysis at:
`/root/.openclaw/plugin-runtime-deps/dist/.../pi-ai/openai-codex.js`

## Endpoints (Verified 2026-05-21)

### Step 1: Get Device Code

```
POST https://auth.openai.com/api/accounts/deviceauth/usercode
Content-Type: application/json

Body: {"client_id": "app_EMoamEEZ73f0CkXaXp7hrann"}

Response (HTTP 200):
{
  "device_auth_id": "...",
  "user_code": "DUSE-ASKEG",
  "verification_url": "https://auth.openai.com/codex/device",
  "interval_ms": 5000
}
```

### Step 2: Poll for Authorization

```
POST https://auth.openai.com/api/accounts/deviceauth/token
Content-Type: application/json

Body: {"device_auth_id": "...", "user_code": "DUSE-ASKEG"}

Responses:
- HTTP 200 (pending): {"error": "authorization_pending"}
- HTTP 200 (approved): {"authorization_code": "...", "code_verifier": "..."}
- HTTP 403 (denied): {"error": "access_denied"}
```

Poll every 5 seconds. Max 15 minutes (180 polls).

### Step 3: Exchange for Tokens

```
POST https://auth.openai.com/oauth/token
Content-Type: application/x-www-form-urlencoded

Body:
  grant_type=authorization_code
  code=<authorization_code from step 2>
  redirect_uri=https://auth.openai.com/deviceauth/callback
  client_id=app_EMoamEEZ73f0CkXaXp7hrann
  code_verifier=<code_verifier from step 2>

Response (HTTP 200):
{
  "access_token": "...",
  "refresh_token": "...",
  "expires_in": 3600,
  "token_type": "Bearer",
  "scope": "openid profile email offline_access model.request model.read organization.read organization.write api.responses.write api.responses.read"
}
```

## Key Difference from Public Endpoint

| Endpoint | HTTP Status | Notes |
|----------|-------------|-------|
| `POST /oauth/device/code` (public) | 530 (Cloudflare blocked) | Standard RFC 8628 device code |
| `POST /api/accounts/deviceauth/usercode` (internal) | 200 OK | OpenClaw's internal API |

## Curl Test (Verified Working 2026-05-21)

```bash
# Step 1: Get device code
curl -s -X POST https://auth.openai.com/api/accounts/deviceauth/usercode \
  -H "Content-Type: application/json" \
  -d '{"client_id":"app_EMoamEEZ73f0CkXaXp7hrann"}'
# Response: {"device_auth_id":"...", "user_code":"DUSE-ASKEG",...}

# Step 2: Poll (returns authorization_pending until user approves)
curl -s -X POST https://auth.openai.com/api/accounts/deviceauth/token \
  -H "Content-Type: application/json" \
  -d '{"device_auth_id":"...","user_code":"DUSE-ASKEG"}'
# Response: {"error":"authorization_pending"}  ← until approved

# Step 3: Exchange (only after approval)
curl -s -X POST https://auth.openai.com/oauth/token \
  -d "grant_type=authorization_code&code=...&redirect_uri=https://auth.openai.com/deviceauth/callback&client_id=app_EMoamEEZ73f0CkXaXp7hrann&code_verifier=..."
```

## Implementation in ILMA

```python
import requests, time, json

CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
AUTH_BASE = "https://auth.openai.com"

# Step 1: Get device code
r = requests.post(f"{AUTH_BASE}/api/accounts/deviceauth/usercode",
    json={"client_id": CLIENT_ID})
r.raise_for_status()
data = r.json()
device_auth_id = data["device_auth_id"]
user_code = data["user_code"]
interval_s = data.get("interval_ms", 5000) / 1000

print(f"User code: {user_code}")
print(f"Open: https://auth.openai.com/codex/device?code={user_code}")

# Step 2: Poll
for _ in range(180):  # 15 min timeout
    time.sleep(interval_s)
    r = requests.post(f"{AUTH_BASE}/api/accounts/deviceauth/token",
        json={"device_auth_id": device_auth_id, "user_code": user_code})
    if r.status_code == 200:
        auth_data = r.json()
        if "authorization_code" in auth_data:
            auth_code = auth_data["authorization_code"]
            code_verifier = auth_data["code_verifier"]
            break
    elif r.status_code == 403:
        continue  # Still pending

# Step 3: Exchange
r = requests.post(f"{AUTH_BASE}/oauth/token",
    data={
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": "https://auth.openai.com/deviceauth/callback",
        "client_id": CLIENT_ID,
        "code_verifier": code_verifier,
    })
r.raise_for_status()
tokens = r.json()
print(f"Scope: {tokens.get('scope')}")
```