---
name: ilma-wrapper-fleet-ops
description: Manage the /root/wrapper LLM proxy fleet — git pull from github, restart systemd user units, register all wrappers as OpenCode custom providers, and fix recurring upstream bugs by adapting the healthy sibling wrappers (nvidia-python/blackbox) as reference. Use when user says "pull wrapper", "update local", "restart service", "sync wrappers", or when a wrapper 500s after a pull.
---

# ILMA Wrapper Fleet Ops

## When to use
- User says "pull wrapper repo", "update local file", "restart service", "sync wrappers".
- User wants all `/root/wrapper` proxies visible in OpenCode as provider choices.
- A wrapper returns HTTP 500 or fails to bind its port after a `git pull`.
- User says "abaikan local" (discard local fixes, reset to pure remote).

## Repo conventions (FACT — verified 2026-07-28)
- Repo: `/root/wrapper`, branch `main`.
- `git remote -v`: `github` = https://github.com/lokah1945/wrappers.git (**PULL FROM THIS**); `origin` = /root/wrapper_remote.git (LOCAL bare — **NEVER pull from origin**).
- Each wrapper is a Python FastAPI/uvicorn service on `127.0.0.1:910X`, managed as a **systemd user unit** in `~/.config/systemd/user/` (NOT a system unit).
- Unit `ExecStartPre` writes `runtime/<name>.commit` (git HEAD) — auto-generated, safe to stash/ignore.

## Wrapper inventory (commit 4706765)
| Wrapper | Port | systemd unit | LLM? |
|---------|------|--------------|------|
| nvidia  | 9101 | wrapper-nvidia-python | yes |
| nous    | 9102 | wrapper-nous           | yes |
| opencode| 9103 | wrapper-opencode       | yes |
| blackbox| 9104 | wrapper-blackbox       | yes |
| vercel  | 9105 | wrapper-vercel         | yes |
| model-registry | 9200 | wrapper-model-registry | control plane (not an LLM provider) |

Client auth for all LLM wrappers: `Authorization: Bearer wrapper-local-key` (BEARER_TOKEN in each `.env`).

## Standard pull → update → restart workflow
1. `cd /root/wrapper && git status --short` — check uncommitted local fixes BEFORE pulling.
2. If local fixes exist and must be kept: `git stash push -u -m "ilma-fix-$(date +%s)"`, pull, then `git checkout stash@{0} -- <specific-file>` to restore only the needed fix (discard `runtime/*.commit` from stash).
3. If user says **"abaikan local"**: `git reset --hard github/main` (destroys ALL local commits/edits), then `git pull github main` (no-op if already at remote). Do NOT re-apply local patches unless user later asks.
4. `git fetch github main` + `git rev-list --left-right --count HEAD...github/main` → left=local-only, right=remote-only commits.
5. Restart: `systemctl --user restart wrapper-<name>.service` for each changed wrapper.
6. Verify with `scripts/verify_wrappers.py` (probes `/health` on every port).

## User preferences (embedded — do not re-ask)
- **"abaikan local"** = reset hard to `github/main`, discard local fixes. Wait for user to push real fixes to github.
- **"fix error 500, acuan pakai code dari repo github, sesuaikan saja"** = when fixing wrapper bugs, **ADAPT the pattern from the healthy sibling wrappers in the same repo** (nvidia-python & blackbox are the reference-stable ones). Do NOT invent a new method. Concretely: if `/health` calls `metrics.snapshot()` but the class lacks it, do what nvidia/blackbox do — call `await metrics.summary()` instead of adding a new `snapshot()` method.

## Recurring upstream bugs (knowledge bank → references/recurring-bugs.md)
Check these FIRST when a wrapper 500s after pull:
1. `Metrics.snapshot()` called in `/health` but class has no `snapshot()` → `AttributeError`. Fix: change to `await metrics.summary()` (matches nvidia/blackbox) OR add a `snapshot()` method.
2. `_dynamic_alias_lock = asyncio.Lock()` used with `with` (sync) → `TypeError: 'Lock' object does not support the context manager protocol`. Fix: `threading.Lock()`.
3. Vercel wrapper (flat `vercel/wrapper_vercel.py`, no `src/`) has 3 bugs: relative imports (`from .key_pool`), wrong uvicorn entrypoint (`src.main:app`), wrong repo-root detection (`parents[2]` → `/root` instead of `/root/wrapper`). See references for exact fixes.
4. New wrapper in `wrappers.json` but no systemd unit → create `~/.config/systemd/user/wrapper-<name>.service` from the wrapper-nous template, adjust WorkingDirectory/port/ExecStart, then `daemon-reload && enable && start`.

## OpenCode custom provider registration (references/opencode-provider-setup.md)
- Binary `/root/.opencode/bin/opencode`, config `~/.config/opencode/opencode.jsonc`.
- Custom OpenAI-compatible providers REQUIRE `"npm": "@ai-sdk/openai-compatible"` (install: `cd ~/.config/opencode && npm install @ai-sdk/openai-compatible`).
- Models MUST be registered manually under `"models"` (OpenCode does NOT auto-fetch `/v1/models` for custom providers).
- Verify: `opencode models` lists `wrapper-<name>/<model>` lines; smoke test `opencode run "reply exactly: PONG" -m wrapper-nous/tencent/hy3:free`.

## Pitfalls
- Never pull from `origin` (local bare repo) — only `github`.
- `git reset --hard` destroys uncommitted work — only on explicit "abaikan local".
- After `reset --hard`, recurring bug fixes are GONE → wrappers 500 until re-fixed or user pushes to github.
- `/health` returning 500 ≠ port not listening. Check both: `ss -ltnp` for bind, `/health` for app errors.
- OpenCode model list is static — re-sync `opencode.jsonc` when models change in a wrapper.

## Support files
- `references/recurring-bugs.md` — exact bug transcripts + diffs.
- `references/opencode-provider-setup.md` — jsonc template + install + verify.
- `scripts/verify_wrappers.py` — probe all wrapper ports, print health table.
