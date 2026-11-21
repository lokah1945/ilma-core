# Wrapper-vercel Removal — 2026-07-29

## Decision
Remove wrapper-vercel (port 9105) entirely from the wrapper fleet. Not just disabled — completely removed.

## Rationale
1. **FREE-TIER-FIRST constitutional violation**: Vercel AI Gateway requires a credit card on file to unlock free credits. This violates our 2026-06-21 constitutional rule: "Default to free models unless owner enables paid."
2. **Upstream limitation is permanent**: Not a temporary outage or bug — the credit card requirement is a hard policy.
3. **No fallback needed**: The 4 remaining wrappers (NVIDIA NIM, Nous, OpenCode, Blackbox) provide sufficient free model coverage.
300+ NVIDIA NIM models + Nous free models + OpenCode free models + Blackbox free models = ample free-tier capacity.

## What Was Removed
### Source Code
- `/root/wrapper/vercel/` — entire directory (src/, dashboard.html, requirements.txt, .env.example, README.md)

### Systemd
- `wrapper-vercel.service` — stopped, disabled, removed from `~/.config/systemd/user/`

### Configuration
- `wrappers.json` — removed vercel entry
- `.env.example` — removed vercel entry

### Documentation
- `README.md` — removed from wrapper table, documentation links, repository layout
- `update_readmes.py` — removed from wrapper list
- `WRAPPER_CONTRACT.md` — removed section 5 (vercel), updated port mapping table

### Code References
- `openrouter/src/main.py` — removed "Vercel" from model listings comment
- `common/catalog_integration.py` — removed "Vercel" from provider list comment

### Logs
- `model-registry/registry.log` — removed (contained vercel manifest warnings)

### Git Commits
1. `2b989e0` - remove: wrapper-vercel (port 9105) - upstream requires credit card
2. `833c852` - cleanup: remove wrapper-vercel comprehensively (port 9105)

## Impact on Production Audit
- Audit scope reduced from 5 LLM wrappers to **4 LLM wrappers** (9101-9104)
- Model-registry (9200) unchanged
- Score: **95/100** (minor: OpenCode upstream flaky "No capacity" 503 is expected external outage)
- All endpoints verified on 4 wrappers: `/ready`, `/catalog/health`, `/mcp/sse`, `/v1/models`, streaming (chat/messages/responses)

## Verification After Removal
```bash
# 1. No vercel references in codebase (except historical audit docs)
grep -r "vercel" /root/wrapper/ --exclude-dir=.git --exclude-dir=audit_report
# Should return empty (or only historical .md files)

# 2. Systemd shows only 4 wrapper services
systemctl --user list-unit-files | grep wrapper
# wrapper-blackbox, wrapper-model-registry, wrapper-nous, wrapper-nvidia-python, wrapper-opencode

# 3. All 4 remaining wrappers healthy
for p in 9101 9102 9103 9104; do
  curl -s http://127.0.0.1:$p/ready | jq -c '{ready, upstream_ok, keys, available}'
done

# 4. Catalog works on all 4
for p in 9101 9102 9103 9104; do
  curl -s http://127.0.0.1:$p/catalog/health
done
```

## Lessons for Future Wrapper Evaluation
**Before adding a new wrapper to the fleet, verify:**
1. Upstream has genuine free tier (no credit card, no hidden quotas)
2. Free models are documented and accessible via API
3. Wrapper can enforce FREE_ONLY mode correctly
4. Upstream doesn't require manual dashboard approval per model

Vercel failed #1 and #4. Future candidates must pass these gates.