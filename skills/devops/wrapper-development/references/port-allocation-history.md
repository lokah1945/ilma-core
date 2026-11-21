# Port Allocation History & Decisions

## Current Allocation (as of 2026-11-12)

| Port | Service | Status | Notes |
|------|---------|--------|-------|
| 9100 | model-fetcher MCP HTTP | Fixed | Owned by model_fetcher/mcp_server.py |
| 9101 | nvidia-python | Production | First active inference wrapper |
| 9102 | nous | Production | Second active inference wrapper |
| 9103 | openrouter | Production | Third active inference wrapper |
| 9104 | opencode | Frozen (reserved) | Pending since 2026-10-07 |
| 9105 | blackbox | Frozen (reserved) | Pending since 2026-10-07 |
| 9106 | dashboard | Production | Unified control dashboard |
| 9107 | coarena | Production | Added 2026-11-12 |
| 9200 | model-registry | Internal | Internal dependency |

## Allocation Rules

1. **9100 is untouchable** — Owned by unrelated model-fetcher service
2. **Active inference wrappers sequential** — 9101, 9102, 9103 in order added
3. **Frozen providers keep reserved ports** — 9104-9105 reserved for opencode/blackbox
4. **Dashboard at 9106** — Next after frozen block
5. **New production wrappers** — Sequential after dashboard (9107, 9108, ...)

## Decision: Coarena at 9107

**Rationale**: Next sequential port after dashboard (9106). Follows the pattern:
- Inference wrappers: 9101-9103
- Frozen reserved: 9104-9105
- Dashboard: 9106
- Next production: 9107

**Alternative considered**: Reuse 9104 or 9105 (frozen ports)
**Rejected because**: Frozen wrappers must keep reserved ports; if reactivated they need their ports back. Moving them would break the "frozen = untouched" policy.

## Future Allocation

| Next Wrapper | Assigned Port |
|--------------|---------------|
| (next production) | 9108 |
| (next production) | 9109 |
| ... | ... |

## Reactivation Policy

If opencode or blackbox are reactivated:
1. They keep 9104/9105
2. Any wrapper currently on those ports must move
3. Update `wrappers.json` and all configs atomically
4. Update `port_allocation` string in metadata

## Verification Command

```bash
ss -tlnp | grep -E ':(910[0-9]|911[0-9]|9200)' | sort
```