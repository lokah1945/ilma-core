# wrapper-vercel Removal (2026-07-29)

## Reason
Vercel AI Gateway free tier requires a valid credit card on file to service requests.
Error: `"AI Gateway requires a valid credit card on file to service requests."` (HTTP 403)

This is an upstream provider constraint, not a wrapper bug. The wrapper code is correct;
the upstream simply does not provide free access without billing setup.

## Actions Taken
1. Stopped & disabled systemd service: `systemctl --user stop wrapper-vercel && systemctl --user disable wrapper-vercel`
2. Removed systemd unit file: `rm ~/.config/systemd/user/wrapper-vercel.service`
3. Removed wrapper directory: `rm -rf /root/wrapper/vercel/`
4. Updated `wrappers.json` — removed vercel entry (port 9105)
5. Committed & pushed to GitHub

## Impact
- **4 wrappers remain** (nvidia-python:9101, nous:9102, opencode:9103, blackbox:9104)
- Port 9105 now free
- All remaining wrappers production-ready with catalog + streaming

## Decision Rule for Future Providers
Before adding a new wrapper:
1. Verify free tier exists AND works without credit card
2. Run smoke test with `FREE_ONLY=true` against real upstream
3. If upstream blocks free usage → don't add wrapper (or add with `status: "blocked-upstream"` in wrappers.json)

## Related
- `references/smoke-and-load-targets.md` — known-good models per wrapper