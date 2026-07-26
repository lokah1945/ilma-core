# Post-Pull Wrapper Audit Recipe (from scratch)

Condensed, reusable recipe used in the 2026-07-27 audit. Read-only; no restart
(per audit-only convention mem_013 — ILMA audits, a separate agent/session restarts).

## 0. Pull (correct remote)
```bash
cd /root/wrapper
git fetch github
git pull github main        # NOT origin (local bare /root/wrapper_remote.git)
```

## 1. Verify topology (tool, not memory)
```bash
ss -tlnp | grep -E "910[0-9]|9200"
systemctl --user list-units --type=service | grep wrapper
```
Ports drift between sessions — never trust stored numbers. 2026-07-27 confirmed
nous=9102, opencode=9103, nvidia-python=9101 (old memory said 9106/9107/9100).

## 2. Health probe (all 5)
```bash
for p in 9101 9102 9103 9104 9200; do
  curl -s --max-time 5 http://127.0.0.1:$p/health; echo
done
```

## 3. Staleness check (runtime vs HEAD)
```bash
HEAD=$(git rev-parse HEAD)
for svc in nvidia-python nous opencode blackbox model-registry; do
  rc=$(cat runtime/$svc.commit 2>/dev/null)
  if git merge-base --is-ancestor "$rc" "$HEAD" 2>/dev/null && [ "$rc" != "$HEAD" ]; then
    echo "$svc STALE: $rc < $HEAD  (restart needed to load pulled fixes)"
  else
    echo "$svc current"
  fi
done
```

## 4. Functional probe (auth + chat)
```bash
KEY=wrapper-local-key
curl -s -m30 -X POST http://127.0.0.1:9102/v1/chat/completions \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"model":"tencent/hy3:free","messages":[{"role":"user","content":"Reply with exactly: HELLO_TEST"}],"max_tokens":40,"stream":false}'
```
Use `max_tokens:40` (not 5) — see hybrid-reasoning pitfall below.

## 5. Classify errors
- body contains `"All API keys exhausted"` / `"No capacity"` → **BLOCKED** (external upstream quota/capacity). NVIDIA returns HTTP 200 + error body; opencode.ai returns 503. Both = external.
- HTTP 503 → **BLOCKED** (external).
- real content + `finish_reason:"stop"` → **PASS**.
- empty `content` at `max_tokens<=10` → re-probe with `max_tokens:40` (hybrid-reasoning models put the answer in the `reasoning` field and get truncated before emitting content).

## 6. Report
Bos-explicit path honored on 2026-07-27: `/root/wrapper/audit_report/AUDIT_REBUILD_2026-07-27.md`
(default elsewhere to avoid repo pollution: `/root/audit_report/`). If Bos names a path, follow it.
