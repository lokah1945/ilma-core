# NVIDIA NIM Model Fetcher — MCP Server Ops

Separate project from `/root/wrapper`. User often bundles "pull wrapper + pull nvidia nim fetcher" in one request — handle each repo with its OWN remote.

## Repo facts
- Path: `/root/project/mode_fetcher`  (RENAMED from `nvidia-nim_model_fetcher` per Bos 2026-07-28; git history kept via `mv nvidia-nim_model_fetcher mode_fetcher` — `git log` still works)
- Branch: `master`
- Remote `origin` = `https://github.com/lokah1945/nvidia-nim_model_fetcher.git`  ← **PULL FROM `origin`** (NOT `github` — that is the wrapper repo)
- No systemd user unit installed. `install.sh` would create `ai-catalog-mcp.service` but it is NOT enabled. MCP server runs as ORPHAN process (see Restart procedure).

## Two different artifacts — don't confuse them
1. **`dashboard.py` = GENERATOR (not a server).**
   `python3 dashboard.py --database data/active_nvidia_nim.sqlite3 --output exports/dashboard.html`
   Writes a STATIC `exports/dashboard.html`. This file is NOT what users see.
2. **`mcp_server.py` = the SERVER (port 9100).**
   `python3 mcp_server.py --transport http --host 0.0.0.0 --port 9100 --database data/active_nvidia_nim.sqlite3`
   The `/dashboard` route renders LIVE from the DB:
   `page = D.render_html(D.build_data(db))` (imports `dashboard` module, calls `build_data` + `render_html`).
   → Regenerating `exports/dashboard.html` does NOT change the served dashboard. Only restarting the MCP server reloads the new `dashboard.py`/templates.

## Port map (avoid confusion)
- 9100 = nvidia-nim fetcher MCP server (THIS project)
- 9101–9105 = /root/wrapper LLM proxies
- 9200 = wrapper model-registry

## Restart procedure after `git pull` (to load new dashboard.py/templates)
The running MCP server is an ORPHAN process (PPID=1), not systemd. `systemctl --user restart ai-catalog-mcp.service` → "Unit not found".
1. Find pid: `ps aux | grep 'mcp_server.py --transport http' | grep -v grep` (or `ss -tlnp | grep ':9100'` → pid).
2. Kill: `kill <pid>`; confirm `ss -tlnp | grep ':9100'` is free.
3. Start (use `terminal(background=true)`, NOT `nohup ... &` — Hermes rejects shell-level background in foreground calls):
   `cd /root/project/nvidia-nim_model_fetcher && python3 mcp_server.py --transport http --host 0.0.0.0 --port 9100 --database data/active_nvidia_nim.sqlite3`
4. Verify: `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:9100/health` → 200; `curl http://172.16.102.11:9100/dashboard` → 200, ~120KB.

## Confirm NEW dashboard is served (not stale)
```bash
curl -s http://172.16.102.11:9100/dashboard -o /tmp/d.html
grep -ciE "catalog|provider|model|transport|publisher" /tmp/d.html   # expect 80+
# vs old static file:
grep -ciE "catalog|provider|model" /root/project/nvidia-nim_model_fetcher/exports/dashboard.html
```
Or render directly to prove `dashboard.py` works after pull:
```bash
cd /root/project/nvidia-nim_model_fetcher && python3 -c "import dashboard as D, sqlite3; db=sqlite3.connect('data/active_nvidia_nim.sqlite3'); print('len', len(D.render_html(D.build_data(db)))); db.close()"
```

## Symptom → fix
"dashboard belum load yang baru" after `git pull` = old MCP server process still serving pre-pull `dashboard.py`. Kill + restart (steps above).

## API Key Injection (fetcher `.env` from wrapper `.env` / SOT)
Fetcher `env_config.py` reads: `NVIDIA_API_KEY, OPENROUTER_API_KEY, NOUS_API_KEY, OPENCODE_API_KEY, BLACKBOX_API_KEY, AI_GATEWAY_API_KEY`.
The fetcher `.env` ships WITHOUT these (only FREE_ONLY/HOST/MCP_PORT/PORT). Bos wants them copied from the active wrapper fleet or SOT.

**SOT auth FAILED in this session** (`Authentication failed` on mongodb://172.16.103.253 despite ILMA_MONGO_* in /root/.hermes/.env — token stale/expired). Do NOT rely on SOT for key retrieval. Fallback: scrape from wrapper `.env` files.

**Working recipe (copy `_1` key from each wrapper into fetcher `.env`):**
```python
import os
wrap = {}
for f in ['nvidia-python','nous','opencode','blackbox','vercel','openrouter']:
    for line in open(f'/root/wrapper/{f}/.env'):
        line=line.strip()
        if line and not line.startswith('#') and '=' in line:
            k,v=line.split('=',1); wrap[k]=v
mapping = {
  'NVIDIA_API_KEY_1':'NVIDIA_API_KEY', 'OPENROUTER_API_KEY_1':'OPENROUTER_API_KEY',
  'NOUS_API_KEY_1':'NOUS_API_KEY', 'OPENCODE_API_KEY_1':'OPENCODE_API_KEY',
  'BLACKBOX_API_KEY_1':'BLACKBOX_API_KEY', 'VERCEL_API_KEY_1':'AI_GATEWAY_API_KEY',
}
lines = open('/root/project/mode_fetcher/.env').read().splitlines()
existing = {l.split('=',1)[0]:i for i,l in enumerate(lines) if l and not l.startswith('#') and '=' in l}
for src,dst in mapping.items():
    val = wrap.get(src,'')
    if not val: continue
    if dst in existing: lines[existing[dst]] = f"{dst}={val}"
    else: lines.append(f"{dst}={val}")
open('/root/project/mode_fetcher/.env','w').write('\n'.join(lines)+'\n')
```
Verify: `cd /root/project/mode_fetcher && python3 -c "import os; from dotenv import load_dotenv; load_dotenv('.env'); print([k for k in ['NVIDIA_API_KEY','OPENROUTER_API_KEY','NOUS_API_KEY','OPENCODE_API_KEY','BLACKBOX_API_KEY','AI_GATEWAY_API_KEY'] if os.environ.get(k)])"` → all 6 present.

⚠️ **CRITICAL: do NOT `git add .env` / `git push` the fetcher `.env`.** It is tracked in the upstream repo (`git ls-files .env` → `.env`). Pushing it exposes Bos's API keys to GitHub (lokah1945/nvidia-nim_model_fetcher is a real remote). Leave `.env` uncommitted (working-tree dirty) after key injection. If a future session must commit, use `git update-index --assume-unchanged .env` or add to `.gitignore`.

## OpenRouter wrapper — NEW from pull (2026-07-28, commit 5373697)
Upstream added `openrouter/` to `/root/wrapper` (port **9106**). It was NOT pre-installed. Setup steps that worked:

1. **Create venv + install deps** (no venv shipped):
   `cd /root/wrapper/openrouter && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`
2. **systemd unit** `~/.config/systemd/user/openrouter.service` (copy from `openrouter/systemd/openrouter.service`, then FIX it — see bugs below).
3. **Gotchas / bugs found (4 layers):**
   - **(a) `ProtectHome=true` + `ProtectSystem=strict`** in the shipped unit BLOCK `/root/wrapper` (WorkingDirectory + venv live under /root). Symptom: silent failure, `journalctl` empty, status flips `activating`. FIX: delete those 3 hardening lines (other wrappers don't use them).
   - **(b) `PYTHONPATH` wrong.** Shipped `Environment=PYTHONPATH=/root/wrapper/openrouter` → `import openrouter` fails (double path). FIX: `PYTHONPATH=/root/wrapper` (so `openrouter/` and `common/` both resolve from /root/wrapper).
   - **(c) `WantedBy=multi-user.target`** → does not exist in user systemd. FIX: `WantedBy=default.target`.
   - **(d) UPSTREAM BUG in `openrouter/src/main.py:491`**: `app.add_middleware(RequestSizeLimiter, max_size=50*1024*1024)` — but `common/middleware.py::RequestSizeLimiter.__init__(self, app, max_bytes=...)` takes `max_bytes`, NOT `max_size`. → `TypeError: unexpected keyword argument 'max_size'` → /health 500. FIX: change `max_size=` → `max_bytes=`. (Patched locally + committed `f95921a`, pushed to github — this is a legitimate upstream fix, safe to push.)
4. **Pre-auth**: openrouter `.env` ships `BEARER_TOKEN=your-secure-random-token-here`. Set `BEARER_TOKEN=wrapper-local-key` + add `DISABLE_AUTH=1` (same pattern as other 5 wrappers). OpenRouter already honors `DISABLE_AUTH` (line 496/505 in main.py).
5. **Verify**: `curl http://127.0.0.1:9106/health` → 200; `curl http://127.0.0.1:9106/v1/models` → lists models (no auth needed with DISABLE_AUTH=1).

## Backup-before-massive-pull (Bos directive 2026-07-28)
When Bos says "backup dulu kedua project karena update massive", snapshot BOTH repos to /root BEFORE pulling:
```bash
TS=$(date +%Y%m%d_%H%M%S)
tar czf "/root/backup_nvidia_fetcher_$TS.tar.gz" -C /root/project mode_fetcher 2>&1
tar czf "/root/backup_wrapper_$TS.tar.gz" --warning=no-file-changed -C /root wrapper 2>&1 | grep -v "model-state.db"
```
The `--warning=no-file-changed` flag avoids tar aborting when `model-state.db` (live SQLite) changes mid-archive. Always backup before a "massive" upstream update.
