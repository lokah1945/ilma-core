# ILMA OAuth Provider — Security Audit Reference
## Version 1.0.0 — Audit Date: 2026-05-20

Full audit report at: `/root/.ilma/oauth/OAUTH_PROVIDER_AUDIT_REPORT.md`

---

## Summary Table

| Category | Status | Notes |
|----------|--------|-------|
| Token Storage | ✅ SECURE | 0o600 permissions, path outside workspace |
| PKCE Implementation | ✅ SECURE | RFC 7636 compliant |
| Callback Server | ✅ SECURE | localhost only, state validation |
| JWT Parsing | ✅ INTENTIONAL | No signature verification (metadata only) |
| CORS | ⚠️ MEDIUM | Allow localhost only — review if exposed |
| OAuth State Store | ⚠️ MEDIUM | 600s TTL, single-use |
| Error Handling | ⚠️ NEEDS WORK | Inconsistent HTML/JSON responses |
| Token Exchange Errors | ⚠️ MEDIUM | HTTP response body could leak info |

**No critical vulnerabilities.** Service is secure for single-user operation.

---

## Critical Issues (MUST FIX)

**NONE** — No critical security vulnerabilities found.

---

## High Priority Issues (SHOULD FIX)

### 1. OAuth Endpoints Hardcoded

**Finding:** OAuth URLs hardcoded in `core/token.py`

```python
AUTH_BASE = "https://auth.openai.com"
TOKEN_URL = "https://auth.openai.com/oauth/token"
AUTH_URL = "https://auth.openai.com/oauth/authorize"
```

**Risk:** If OpenAI changes OAuth endpoints, service breaks silently.

**Recommendation:** Make configurable via `config.json`

---

### 2. Browser User Data Dir Hardcoded

**Finding:** `/root/user-data/lokah2150` hardcoded in `browser/automation.py`

```python
user_data_dir="/root/user-data/lokah2150"  # Hardcoded
```

**Risk:** Path may not exist on all systems.

**Recommendation:** Make configurable with fallback to ephemeral context.

---

### 3. Systemd Service Not Installed

**Finding:** `ilma-oauth-provider.service` provided but not installed

**Risk:** Service must be manually started. No auto-restart on crash.

**Recommendation:** Install systemd service for production.

---

## Medium Priority Issues (NICE TO HAVE)

### 1. Token Refresh Race Condition

**Finding:** Multiple concurrent requests could trigger simultaneous token refresh

**Risk:** If `refresh_token_reused` error occurs, OAuth session is invalidated

**Mitigation:** Client-side caching (30s TTL) reduces concurrent refresh likelihood

**Recommendation:** Add distributed lock for production deployments

---

### 2. Token Exchange Error Messages Not Sanitized

**Finding:** Error responses include raw HTTP body from OpenAI

```python
error_body = e.read(300).decode('utf-8', errors='replace')
return {'type': 'failed', 'error': f'HTTP {e.code}: {error_body}'}
```

**Risk:** Could leak sensitive information from OpenAI error responses

**Recommendation:** Sanitize error messages before returning to client

---

### 3. Error Response Format Inconsistent

**Finding:** Some errors return HTML, some return JSON

```python
# Browser errors → HTML (for display)
return HTMLResponse("<h2>Error</h2>", status_code=400)

# API errors → JSON
raise HTTPException(status_code=400, detail="...")
```

**Risk:** Inconsistent API responses could break programmatic clients

**Recommendation:** Standardize on JSON error responses for `/oauth/*` endpoints

---

## Low Priority Issues (ACCEPTABLE)

| Issue | Status | Notes |
|-------|--------|-------|
| Token expiry buffer (60s) | OK | Conservative default |
| Account ID extraction | OK | Graceful handling if JWT structure changes |
| Browser crash recovery | OK | User intervention acceptable |
| Token revocation on logout | OK | Access tokens short-lived (1 hour) |

---

## Verification Commands

```bash
# Module tests
cd /root/.ilma/oauth/service && python3 main.py --test

# Service health
curl http://127.0.0.1:1456/oauth/health

# Auth status
curl http://127.0.0.1:1456/oauth/status

# Check file permissions
ls -la /root/.ilma/oauth/providers/openai-codex/tokens.json
# Should show: -rw------- (0o600)

# Check service is running
ps aux | grep 'oauth-provider\|main.py.*1456' | grep -v grep
```

---

## Security Hardening Checklist

- [x] Token storage uses 0o600 permissions
- [x] State stored server-side, validated on callback
- [x] PKCE implemented (RFC 7636)
- [x] Callback server only accepts localhost
- [x] CORS restricts to localhost origins
- [ ] OAuth endpoints made configurable (TODO)
- [ ] Browser user data dir configurable (TODO)
- [ ] Systemd service installed (TODO)
- [ ] Error messages sanitized (TODO)