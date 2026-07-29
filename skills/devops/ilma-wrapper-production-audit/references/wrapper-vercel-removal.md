# Wrapper Vercel Removal — 2026-07-29

## Context
Vercel AI Gateway wrapper (port 9105) was removed entirely from the fleet because the upstream requires a credit card on file to service requests. The free tier is not usable without a payment method, making it non-viable for our FREE-TIER-FIRST policy.

## Removal Scope (Comprehensive)

### Source Code
- `vercel/` directory: `src/main.py`, `key_pool.py`, `metrics.py`, `dashboard.html`, `requirements.txt`, `.env.example`, `README.md`

### Systemd Service
- `wrapper-vercel.service` stopped, disabled, removed from `~/.config/systemd/user/`

### Configuration Files
- `wrappers.json`: removed vercel entry from wrapper list
- `README.md`: removed from wrapper table, documentation links, repository layout
- `update_readmes.py`: removed vercel from wrapper list
- `WRAPPER_CONTRACT.md`: removed section 5 (vercel), updated port mapping table

### Code References
- `openrouter/src/main.py`: removed "Vercel" from model listings comment
- `common/catalog_integration.py`: removed "Vercel" from provider list comment

### Logs
- `model-registry/registry.log`: removed (contained vercel manifest warnings)

### Verification After Removal
```bash
# 1. No vercel references in codebase (except historical audit docs)
grep -r "vercel" /root/wrapper/ --exclude-dir=.git --exclude-dir=audit_report

# 2. Systemd shows only 4 wrapper services
systemctl --user list-unit-files | grep wrapper

# 3. All 4 remaining wrappers healthy
for p in 9101 9102 9103 9104; do curl -s http://127.0.0.1:$p/ready; done
```

## Decision Record
- **Why remove, not disable?** Upstream limitation is permanent (credit card requirement). Keeping a disabled service adds maintenance noise and false inventory.
- **FREE-TIER-FIRST policy**: Our constitutional rule (2026-06-21) mandates free-tier first. Vercel violates this.
- **No fallback needed**: The 4 remaining wrappers (NVIDIA NIM, Nous, OpenCode, Blackbox) provide sufficient free model coverage.

## Audit Update
- Production audit now covers **4 LLM wrappers** (9101-9104) + model-registry (9200)
- Score: **95/100** (minor: OpenCode upstream flaky "No capacity" 503 is expected/external)
- All endpoints verified: `/ready`, `/catalog/health`, `/mcp/sse`, `/v1/models`, streaming (chat/messages/responses)

## Git Commits
1. `2b989e0` - remove: wrapper-vercel (port 9105) - upstream requires credit card
2. `833c852` - cleanup: remove wrapper-vercel comprehensively (port 9105)