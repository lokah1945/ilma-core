# wrapper-vercel Removal — Upstream Provider Blocked

## Date: 2026-07-29

## Decision
Removed `wrapper-vercel` (port 9105) entirely from production deployment.

## Reason
Vercel AI Gateway free tier requires a valid credit card on file to service requests.
Error: `HTTP 403 {"error": "AI Gateway requires a valid credit card on file to service requests."}`

This is an upstream provider constraint, not a wrapper bug. The wrapper code was correct and all integrations worked (catalog, MCP, streaming). The upstream simply blocks all free-tier requests without billing setup.

## Actions Taken
1. Stopped & disabled systemd service: `systemctl --user stop wrapper-vercel && systemctl --user disable wrapper-vercel`
2. Removed systemd unit file: `rm ~/.config/systemd/user/wrapper-vercel.service`
3. Removed wrapper directory: `rm -rf /root/wrapper/vercel/`
4. Updated `wrappers.json` — removed vercel entry
5. Committed & pushed to GitHub

## Current Production Wrappers (4)
| Wrapper | Port | Upstream | Free Tier Working |
|---------|------|----------|-------------------|
| nvidia-python | 9101 | NVIDIA NIM | ✅ |
| nous | 9102 | Nous Research | ✅ |
| opencode | 9103 | OpenCode Zen | ✅ (with transient 503) |
| blackbox | 9104 | BLACKBOX AI | ✅ |

## Decision Rule for Future Providers
Before adding a new wrapper:
1. Verify free tier exists AND works without credit card
2. Run smoke test with `FREE_ONLY=true` against real upstream
3. If upstream blocks free usage → don't add wrapper (or add with `status: "blocked-upstream"` in wrappers.json)

## Related
- `references/2026-07-29-full-audit-summary.md` — session summary
- `references/smoke-and-load-targets.md` — known-good models per wrapper