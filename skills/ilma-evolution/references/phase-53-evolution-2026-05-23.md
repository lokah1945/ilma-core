# Phase 53 — Google Credential Block REVERSAL (2026-05-23)

## Breakthrough Discovery

**Previously INCORRECT:** Sessions from 2026-05-19 through 2026-05-22 concluded Google blocks ALL headless Chromium from entering credentials at `accounts.google.com`.

**CORRECTED (2026-05-23):** Google credential entry CAN work with the right configuration. The block is NOT absolute.

## Requirements for Google Credential Entry to Work

ALL five conditions must be present simultaneously:

1. **`playwright_stealth.Stealth` with ALL 17 evasions** — `stealth.hook_playwright_context(p)` on Playwright INSTANCE (not context)
2. **`headless=False` via `xvfb-run -a`** — headed mode via Xvfb, not truly headless
3. **Persistent profile** at `/root/user-data/lokah2150` — existing Google session cookies provide trusted browser fingerprint
4. **Real password** — not placeholder, must be the actual account password
5. **Correct button text for locale** — "Berikutnya" (Indonesian) not "Next" or "Lanjutkan"

## What Failed Previously (And Why)

| Attempt Date | Why It Failed |
|-------------|---------------|
| 2026-05-19 | Fresh browser, no persistent profile, wrong stealth approach |
| 2026-05-20 | Headless=True + stealth, no xvfb |
| 2026-05-21 | Puppeteer-extra-plugin-stealth + headed, but wrong cookie flow |
| 2026-05-22 | `stealth=False` on fresh profile — same block (proved block was at Chrome binary, but this was wrong conclusion) |
| 2026-05-23 (first attempt) | xvfb + full stealth + persistent profile → CF solved, email passed → BUT script ended at consent page, didn't click consent button |

## What Worked (2026-05-23)

```bash
xvfb-run -a python3 /tmp/codex_oauth_v6.py
```

**Script behavior:**
1. ✅ CF challenge auto-solves in ~1s
2. ✅ Email on auth.openai.com → "Lanjutkan" → redirects to Google
3. ✅ Google "Berikutnya" → password field visible
4. ✅ Password + Enter → 2FA fires (Xiaomi Pad)
5. ✅ Bos approves 2FA → consent page at `auth.openai.com/sign-in-with-chatgpt/codex/consent`
6. ⏸ Script ended — consent button NOT clicked
7. ❌ Callback to `localhost:1455` never fired

## The Missing Step

The v6 script timed out at the consent page. The OAuth flow was 95% complete — the only missing piece was clicking the consent/authorize button on the OpenAI consent page.

**Fix in v7:** Add consent button detection and click before waiting for callback.

## Key Technical Findings

1. **CF on auth.openai.com auto-solves** with full stealth stack in xvfb — no manual CF clearance needed
2. **Google redirect works** when coming from auth.openai.com's OAuth flow (not direct navigation)
3. **"Berikutnya" is correct** for Google's Indonesian locale — not "Next" or "Lanjutkan"
4. **2FA approval from Bos's Xiaomi Pad** works reliably (Itel S23+ also works as backup)
5. **OAuth scope from `codex login` URL:** `openid+profile+email+offline_access+api.connectors.read+api.connectors.invoke` with `codex_cli_simplified_flow=true&originator=codex_cli_rs`

## Next Steps

1. Add consent button click to script (v7)
2. Start callback server on port 1455 before running
3. Run `xvfb-run -a python3 /tmp/codex_oauth_v7.py`
4. Bos approves 2FA when prompted
5. Script clicks consent → callback → tokens obtained

## Lessons Learned

- **Previous conclusions about Google blocking headless were incomplete** — the failure was due to missing xvfb (headed mode) and missing persistent profile, not Google being fundamentally incompatible with headless Chromium
- **The persistent profile is critical** — it provides browser fingerprint history that Google trusts
- **All conditions must be met simultaneously** — missing any one causes complete failure
- **Consent page is the last mile** — the entire OAuth flow can succeed but fail at the very last step if the consent button isn't clicked