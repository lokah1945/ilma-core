# Git-Based Hermes Update Workflow

Reference for updating a git-installed Hermes Agent (installed via `curl -fsSL ... | bash` or manual clone) to the latest upstream.

## When to Use

- `hermes --version` shows "Update available: N commits behind"
- You want the absolute latest fixes/features from `NousResearch/hermes-agent:main`
- The PyPI version (pip/uv/pipx) lags behind git main

## Standard Update Procedure

```bash
cd /root/.hermes/hermes-agent

# 1. Ensure origin points to upstream (HTTPS works without SSH keys)
git remote set-url origin https://github.com/NousResearch/hermes-agent.git

# 2. Fetch latest
git fetch origin main --depth=1

# 3. Check what's new
git log --oneline HEAD..FETCH_HEAD

# 4. Handle local changes first
git status
# If you have local modifications, stash or commit them:
git stash   # or git commit -am "local: ..."

# 5. Hard reset to upstream (discards local changes if not stashed)
git reset --hard FETCH_HEAD

# 6. Restore stashed changes (resolve conflicts manually)
git stash pop   # if you stashed
```

## Post-Update Steps

```bash
# 7. Rebuild editable install (updates venv entry points)
cd /root/.hermes/hermes-agent
/root/.hermes/hermes-agent/venv/bin/python -m pip install -e . --force-reinstall --no-deps

# 8. Run transport parity tests (critical for provider routing)
/root/.hermes/hermes-agent/venv/bin/python -m pytest \
  tests/agent/transports/test_chat_completions.py \
  tests/providers/test_transport_parity.py -v

# 9. Verify version
/root/.hermes/hermes-agent/venv/bin/hermes --version
# Should show "Up to date" not "N commits behind"

# 10. Health check
/root/.hermes/hermes-agent/venv/bin/hermes doctor
```

## Common Conflict: Custom Provider Profiles

**Symptom:** `git stash pop` shows conflicts in `plugins/model-providers/custom/__init__.py`

**Cause:** Upstream changed the Ollama detection logic (now uses `_looks_like_ollama_endpoint()` on `base_url` instead of requiring `ollama_num_ctx` to gate Ollama-specific fields like `think` and `options`).

**Resolution:**
```bash
# Accept upstream (recommended — more flexible)
git checkout HEAD -- plugins/model-providers/custom/__init__.py
git checkout HEAD -- tests/providers/test_transport_parity.py
git checkout HEAD -- tests/agent/transports/test_chat_completions.py
```

If you MUST keep local customizations, manually merge the upstream `_looks_like_ollama_endpoint()` function and the new test cases.

## ILMA Integration Note

After Hermes update, verify ILMA still boots:
```bash
cd /root/.hermes/profiles/ilma
/root/.hermes/hermes-agent/venv/bin/python ilma.py --status
/root/.hermes/hermes-agent/venv/bin/python ilma.py --verify /root/.hermes/profiles/ilma/ilma.py
```

The ILMA runtime wiring (38 modules, 9 layers) should report 100% pipeline integrity.

## Quick One-Liner (when no local changes)

```bash
cd /root/.hermes/hermes-agent && \
git fetch https://github.com/NousResearch/hermes-agent.git main --depth=1 && \
git reset --hard FETCH_HEAD && \
/root/.hermes/hermes-agent/venv/bin/python -m pip install -e . --force-reinstall --no-deps && \
/root/.hermes/hermes-agent/venv/bin/hermes --version
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `git fetch` times out | Use `--depth=1` or check network/proxy |
| `fatal: refusing to merge unrelated histories` | You're on a divergent fork; `git reset --hard FETCH_HEAD` is correct |
| Tests fail after update | Check if local test modifications conflict; restore test files from HEAD |
| `hermes` command not found after update | The editable install step (7) was skipped |
| SQLite WAL-reset bug warning | Run `hermes update` (repairs embedded runtime) or wait for system SQLite upgrade |