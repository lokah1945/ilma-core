# Browser Cache Storage Cleanup — Playwright Chromium

## Context
During Ponytail full-mode storage cleanup (2026-11-13), significant space was recovered from Playwright Chromium caches in two locations:

### Profile Cache (Active)
**Path:** `/root/.hermes/profiles/ilma/home/.cache/ms-playwright/`
**Before:** 1.3G
**After:** 223M (kept only chromium-1217)

### System Cache (Used by ilma-chrome.service)
**Path:** `/root/.cache/ms-playwright/`
**Before:** 899M
**After:** 641M (kept only chromium_headless_shell-1228)

## Current Active Versions (Verified via systemctl)

```bash
# Check which version the service uses
systemctl --user status ilma-chrome.service
# Output shows: /root/.cache/ms-playwright/chromium_headless_shell-1228/chrome-headless-shell-linux64/chrome-headless-shell
```

**Active:**
- System: `chromium_headless_shell-1228` (used by ilma-chrome.service)
- Profile: `chromium-1217` (used by BrowserEngine in profile context)

**Removed (Safe):**
- `chromium-1208` (old, both locations)
- `chromium_headless_shell-1208` (old, both locations)
- `chromium_headless_shell-1217` (profile only, not used by service)
- `ffmpeg-1011` (duplicate, both locations)

## Cleanup Commands

```bash
# Profile cache cleanup
rm -rf /root/.hermes/profiles/ilma/home/.cache/ms-playwright/chromium-1208
rm -rf /root/.hermes/profiles/ilma/home/.cache/ms-playwright/chromium-1217
rm -rf /root/.hermes/profiles/ilma/home/.cache/ms-playwright/chromium_headless_shell-1208
rm -rf /root/.hermes/profiles/ilma/home/.cache/ms-playwright/chromium_headless_shell-1217
rm -rf /root/.hermes/profiles/ilma/home/.cache/ms-playwright/ffmpeg-1011

# System cache cleanup
rm -rf /root/.cache/ms-playwright/chromium-1208
rm -rf /root/.cache/ms-playwright/chromium_headless_shell-1208
rm -rf /root/.cache/ms-playwright/ffmpeg-1011
```

## Safety Rules

1. **Always check active service first:**
   ```bash
   systemctl --user status ilma-chrome.service
   ps aux | grep chrome-headless
   ```

2. **Keep the version referenced by the running service**
   - System service → `/root/.cache/ms-playwright/chromium_headless_shell-1228`
   - Profile BrowserEngine → `/root/.hermes/profiles/ilma/home/.cache/ms-playwright/chromium-1217`

3. **Never delete the `.links` directory** — contains symlinks Playwright uses for version resolution

4. **After cleanup, verify service still starts:**
   ```bash
   systemctl --user restart ilma-chrome.service
   curl -s http://127.0.0.1:9222/json/version
   ```

## Session Outcome (2026-11-13)
- **Total freed:** ~1.3G (1.3G profile + 258M system)
- **Risk:** Low — old versions not referenced by any active service
- **Verification:** ilma-chrome.service restarted successfully, CDP endpoint responsive