# NVIDIA NIM Model Fetcher — MCP Server Ops

Separate project from `/root/wrapper`. User often bundles "pull wrapper + pull nvidia nim fetcher" in one request — handle each repo with its OWN remote.

## Repo facts
- Path: `/root/project/nvidia-nim_model_fetcher`
- Branch: `master`
- Remote `origin` = `https://github.com/lokah1945/nvidia-nim_model_fetcher.git`  ← **PULL FROM `origin`** (NOT `github` — that is the wrapper repo)
- No systemd user unit installed. `install.sh` would create `ai-catalog-mcp.service` but it is NOT enabled.

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
