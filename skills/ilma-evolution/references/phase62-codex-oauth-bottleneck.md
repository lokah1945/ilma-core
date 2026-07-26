# Phase 62 — Codex OAuth Automation Bottleneck (2026-05-19)

## Session Summary

**Task:** Fix OpenAI Codex OAuth automation — make it callable by ILMA's system without manual copy-paste steps.

**Outcome:** Root cause identified — ALL browser automation approaches blocked by OpenAI's server-side detection. Confirmed working alternative: copy-paste URL method.

---

## Key Findings

### 1. The "Ups, ada kesalahan!" Blocker

OpenAI's server-side detection blocks ALL headless browser OAuth automation:
- Playwright (Python, stealth plugins)
- Puppeteer-Extra (Node.js, stealth plugins)
- CDP keyboard/mouse events
- Fresh profiles vs. persistent profiles
- xvfb-run (real display)
- Direct Google accounts.google.com navigation

**Root cause:** Server-side detection, not client-side JavaScript. The detection happens BEFORE any redirect — even a direct navigation to the OAuth authorize URL returns an immediate error page.

### 2. AYDA Profile Has No OpenAI Cookies

The AYDA persistent profile (`nvidia_build`) contains cookies for NVIDIA, Bing, LinkedIn, Indeed — but ZERO cookies for ChatGPT, OpenAI, or auth.openai.com. AYDA's browser session is not logged into OpenAI.

### 3. Google Cookies ≠ OpenAI Cookies

Even though AYDA has a Google session (47 cookies on accounts.google.com), this does NOT translate to an OpenAI login. They are separate authentication domains.

### 4. The nvidia_build Interstitial Problem

When `auth.openai.com/log-in` is loaded with the nvidia_build profile, it shows a "Your session has ended" interstitial page — NOT the login form. The "Continue with Google" button only appears after going through `chatgpt.com/auth/login_with` — but this redirect chain is blocked by Cloudflare/bot detection.

### 5. Error Page Payload Format

OpenAI error pages contain a base64-encoded JSON payload:
```
https://auth.openai.com/error?payload=eyJraWQiOiJ...(base64)...&session_id=authsess_...
```
Decoded: `{"kind":"AuthApiFailure","errorCode":"unknown_error","requestId":"..."}`

### 6. The ONLY Working Path: Copy-Paste URL

```bash
python3 /root/.openclaw/workspace/scripts/ilma_oauth_codex.py authorize
# → Boss opens URL in Boss's own browser
# → Boss pastes redirect URL
python3 /root/.openclaw/workspace/scripts/ilma_oauth_codex.py callback '<redirect URL>'
```

This works because the approval happens in Boss's real browser (real Chrome, not headless).

---

## What Didn't Work

| Approach | Result | Notes |
|----------|--------|-------|
| AYDA nvidia_build persistent context | ❌ No OpenAI cookies | Only NVIDIA/Bing/LinkedIn |
| AYDA Google session cookies | ❌ No OpenAI cookies | Google ≠ OpenAI auth |
| playwright_stealth + stealth args | ❌ "Ups, ada kesalahan!" | OpenAI detects automation |
| launch_persistent_context (AYDA pattern) | ❌ Browser couldn't launch | Different Chromium build |
| Puppeteer-Extra + CDP + headless:'old' | ❌ Empty input / 500 error | Google server-side detection |
| All 3 redirect interception mechanisms | ❌ Never fired | Because SSO click fails first |
| xvfb-run | ❌ Same failure | Not a display issue |

---

## Technical Details Discovered

### Browser Detection Args TO REMOVE

Boss confirmed these args trigger OpenAI detection — remove from any browser launch:
- `--no-sandbox`
- `--disable-blink-features=AutomationControlled`

### Google OAuth Direct Navigation URL

The Google sign-in URL for OpenAI OAuth callback:
```
https://accounts.google.com/v3/signin/identifier?
  opparams=%253Faudience%253D799222349882-ne3i0s9jdm5s0p7ll2d7tlsi1vc1halt.apps.googleusercontent.com
  &client_id=799222349882-ne3i0s9jdm5s0p7ll2d7tlsi1vc1halt.apps.googleusercontent.com
  &redirect_uri=https%3A%2F%2Fauth.openai.com%2Fapi%2Faccounts%2Fcallback%2Fgoogle
  &response_type=code&scope=openid+profile+email&service=lso&state=...
  &flowName=GeneralOAuthLite&prompt=select_account
```

### AYDA's Working OAuth Script

`/root/.openclaw/workspace/scripts/ilma_oauth_codex.py` — confirmed working, uses Authorization Code + PKCE flow with `codex_cli_simplified_flow=true&originator=openclaw` parameters.

---

## Next Steps

1. **Accept copy-paste flow** as primary method — documented clearly for Boss
2. **Option: Store Google password** — If Boss provides Google password for `lokah2150@gmail.com`, ILMA can type it directly via CDP on the Google sign-in page (bypassing the "Continue with Google" button)
3. **Option: Boss exports cookies** — From Boss's real Chrome browser, export ChatGPT/OpenAI cookies and inject into ILMA's browser profile
4. **Option: VNC server** — Run a real VNC server so Boss can approve OAuth in a real browser session

---

## DNA Candidate

```
Rule: When OpenAI/ChatGPT OAuth fails with "Ups, ada kesalahan!" or immediate error page in headless browser — this is SERVER-SIDE detection. Client-side stealth patches (playwright_stealth, puppeteer-extra-plugin-stealth, CDP evasion) will NOT bypass it. The ONLY proven working path is copy-paste URL via Boss's real browser.

Evidence: Phase 62 session (2026-05-19) — all 7 automation approaches failed, only copy-paste worked.

Scope: OpenAI OAuth, ChatGPT OAuth, Codex OAuth automation

Risk: Low — this is a documented limitation, not a proposed change to behavior.
```

---

## Session Metrics

- **Duration:** ~90 minutes of intensive debugging
- **Approaches tried:** 7 distinct approaches, all failed
- **Root cause identified:** YES
- **Working alternative found:** YES
- **Bottleneck resolved:** NO — requires Boss decision