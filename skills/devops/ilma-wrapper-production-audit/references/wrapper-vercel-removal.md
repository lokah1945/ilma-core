# Wrapper Ecosystem Cleanup & Removal Protocol

## When to Use
- Removing a non-viable wrapper (e.g., vercel requires credit card)
- Cleaning up stale/legacy artifacts across the monorepo
- Ensuring zero references remain after removal

## Comprehensive Removal Checklist

### 1. Source Code & Directories
```bash
rm -rf /root/wrapper/vercel/          # Source directory
rm -f /root/.config/systemd/user/wrapper-vercel.service  # Systemd unit
systemctl --user daemon-reload
```

### 2. Configuration & Metadata
- `wrappers.json` — remove entry
- `.env.example` — remove vercel section
- `README.md` — remove from wrapper table, docs list, repo layout
- `update_readmes.py` — remove from wrapper dict
- `WRAPPER_CONTRACT.md` — remove section, port mapping table
- `.claude/settings.local.json` — remove service commands

### 3. Code References (grep -r "vercel")
- `common/catalog_integration.py` — comments, provider lists
- `openrouter/src/main.py` — model listing comments
- `nvidia-python/src/main.py` — any vercel references
- All audit reports (historical, keep but note removal)

### 4. Git Workflow
```bash
cd /root/wrapper
git add -A
git commit -m "remove: wrapper-vercel (port 9105) - upstream requires credit card

- Remove vercel/ directory and systemd service
- Update wrappers.json, README.md, WRAPPER_CONTRACT.md
- Remove vercel references from code comments
- Update update_readmes.py wrapper list

Co-authored-by: openhands <openhands@all-hands.dev>"

# Proper rebase workflow (github/main may have advanced):
git fetch github
git stash push -u -m "ilma-cleanup-stash"
git rebase github/main
git stash pop
git push github main
```

### 5. Verification
```bash
# No vercel references remain (except historical audit reports)
grep -r "vercel" /root/wrapper/ --exclude-dir=.git --exclude-dir=audit_report

# No systemd unit
systemctl --user list-unit-files | grep vercel

# No directory
ls /root/wrapper/vercel 2>&1  # should error

# Remaining wrappers healthy
for p in 9101 9102 9103 9104; do curl -s http://localhost:$p/ready | jq .ready; done
```

## Lessons Learned (2026-07-29)
- **vercel upstream requires credit card** — not viable for free-tier automation. Trap: "free models" but 403 without CC.
- **Cleanup must be comprehensive** — missed references cause confusion in future audits
- **Systemd unit must be stopped+disabled+removed** before directory deletion
- **Git rebase, never force-push** — preserves history if remote advanced
- **All 4 remaining wrappers verified** post-cleanup: health, catalog, MCP, streaming