# Reusable Deep E2E SDK-Compat Audit Script (version-bump per audit)

Copy this, rename to `/tmp/vN_audit.sh`, bump the version string + matrix as
needed. READ-ONLY (no edits to /root/wrapper). Run with `bash` (foreground or
background; SSE tests are slow — use background + notify).

```bash
#!/bin/bash
# Vn DEEP E2E SDK AUDIT — READ ONLY. Writes /tmp/vn_audit.txt
set -u
KNV=$(grep -oE 'BEARER_TOKEN=.+' /root/wrapper/nvidia-python/.env|head -1|cut -d= -f2)
KNO=$(grep -oE 'BEARER_TOKEN=.+' /root/wrapper/nous/.env|head -1|cut -d= -f2)
KOC=$(grep -oE 'BEARER_TOKEN=.+' /root/wrapper/opencode/.env|head -1|cut -d= -f2)
declare -A K=(["9101"]="$KNV" ["9106"]="$KNO" ["9107"]="$KOC")
OUT=/tmp/vn_audit.txt; : > "$OUT"
echo "===== Vn DEEP E2E SDK AUDIT $(date) =====" >> "$OUT"
for p in 9101 9106 9107; do
  k=${K[$p]}; B="http://127.0.0.1:$p"
  EXP=$( [ "$p" = 9101 ] && echo "nvidia/llama-3.3-nemotron-super-49b-v1.5" || ([ "$p" = 9106 ] && echo "tencent/hy3:free" || echo "big-pickle") )
  { echo; echo "############ WRAPPER :$p ############"
  echo "[C3] anth no max_tokens: $(curl -s -o /dev/null -w '%{http_code}' --max-time 15 $B/v1/messages -H "Authorization: Bearer $k" -H 'anthropic-version: 2023-06-01' -H 'Content-Type: application/json' -d '{"model":"sonnet","messages":[{"role":"user","content":"hi"}]}')"
  echo "[D1] chat no max_tokens: $(curl -s -o /dev/null -w '%{http_code}' --max-time 30 $B/v1/chat/completions -H "Authorization: Bearer $k" -H 'Content-Type: application/json' -d '{"model":"sonnet","messages":[{"role":"user","content":"hi"}],"stream":false}')"
  echo "[D2] chat empty msgs: $(curl -s --max-time 15 $B/v1/chat/completions -H "Authorization: Bearer $k" -H 'Content-Type: application/json' -d '{"model":"sonnet","messages":[]}' | python3 -c "import sys,json;print(json.load(sys.stdin).get('error',{}).get('type','?'))" 2>&1 | head -1)"
  echo "[D3] chat invalid role: $(curl -s -o /dev/null -w '%{http_code}' --max-time 20 $B/v1/chat/completions -H "Authorization: Bearer $k" -H 'Content-Type: application/json' -d '{"model":"sonnet","messages":[{"role":"god","content":"hi"}]}')"
  echo "[D6] anth system as number: $(curl -s -o /dev/null -w '%{http_code}' --max-time 15 $B/v1/messages -H "Authorization: Bearer $k" -H 'anthropic-version: 2023-06-01' -H 'Content-Type: application/json' -d '{"model":"sonnet","max_tokens":20,"system":123,"messages":[{"role":"user","content":"hi"}]}')"
  echo "[D7] anth invalid tool: $(curl -s -o /dev/null -w '%{http_code}' --max-time 15 $B/v1/messages -H "Authorization: Bearer $k" -H 'anthropic-version: 2023-06-01' -H 'Content-Type: application/json' -d '{"model":"sonnet","max_tokens":20,"tools":[{"name":"x"}],"messages":[{"role":"user","content":"hi"}]}')"
  echo "[D8] cors preflight creds: $(curl -s -D - -o /dev/null --max-time 10 -X OPTIONS $B/v1/chat/completions -H "Origin: http://localhost:9106" -H "Access-Control-Request-Method: POST" -H "Access-Control-Request-Headers: authorization" | grep -iE 'access-control-allow-(origin|methods|credentials)' | tr -d '\r' | tr '\n' ' ')"
  echo "[D9] burst x20:"; for i in $(seq 1 20); do curl -s -o /dev/null -w "%{http_code} " --max-time 40 $B/v1/chat/completions -H "Authorization: Bearer $k" -H 'Content-Type: application/json' -d '{"model":"sonnet","messages":[{"role":"user","content":"hi"}],"max_tokens":5}' & done; wait; echo
  echo "[D10] malformed JSON: $(curl -s -o /dev/null -w '%{http_code}' --max-time 15 $B/v1/chat/completions -H "Authorization: Bearer $k" -H 'Content-Type: application/json' -d 'this is not json')"
  echo "[D11] unknown path: $(curl -s -o /dev/null -w '%{http_code}' --max-time 10 $B/v1/nonexistent)"
  echo "[T2] chat alias sonnet: $(curl -s -o /dev/null -w '%{http_code}' --max-time 40 $B/v1/chat/completions -H "Authorization: Bearer $k" -H 'Content-Type: application/json' -d '{"model":"sonnet","messages":[{"role":"user","content":"ping"}]}')"
  echo "[T3] responses alias sonnet: $(curl -s -o /dev/null -w '%{http_code}' --max-time 40 $B/v1/responses -H "Authorization: Bearer $k" -H 'Content-Type: application/json' -d '{"model":"sonnet","input":"hi","stream":false}')"
  echo "[T4] anth tools alias: $(curl -s -o /dev/null -w '%{http_code}' --max-time 30 $B/v1/messages -H "Authorization: Bearer $k" -H 'anthropic-version: 2023-06-01' -H 'Content-Type: application/json' -d '{"model":"sonnet","max_tokens":100,"tools":[{"name":"gw","input_schema":{"type":"object","properties":{"c":{"type":"string"}}}}],"messages":[{"role":"user","content":"w?"}]}')"
  Tt=$(mktemp); curl -s --max-time 40 $B/v1/messages -H "Authorization: Bearer $k" -H 'anthropic-version: 2023-06-01' -H 'Content-Type: application/json' -d '{"model":"sonnet","max_tokens":200,"tools":[{"name":"get_weather","input_schema":{"type":"object","properties":{"city":{"type":"string"}}}}],"messages":[{"role":"user","content":"weather in paris?"}]}' > "$Tt"; echo "[T7] anth tool_use present: $(grep -c 'tool_use' "$Tt")"; rm -f "$Tt"
  Tr=$(mktemp); curl -s --max-time 40 $B/v1/responses -H "Authorization: Bearer $k" -H 'Content-Type: application/json' -d '{"model":"sonnet","input":"hi","stream":true}' > "$Tr"; echo "[T8] responses SSE: $(grep -oE '\"type\": \"response\.[a-z_]+\"' "$Tr" | sort -u | tr '\n' ' ')"; rm -f "$Tr"
  echo "[T5] usage(explicit): $(curl -s --max-time 30 $B/v1/chat/completions -H "Authorization: Bearer $k" -H 'Content-Type: application/json' -d "{\"model\":\"$EXP\",\"messages\":[{\"role\":\"user\",\"content\":\"say hello world\"}],\"stream\":false}" | python3 -c "import sys,json;d=json.load(sys.stdin);u=d.get('usage');print(u if u else 'MISSING')" 2>&1 | head -1)"
  curl -s -o /dev/null --max-time 25 $B/v1/chat/completions -H "Authorization: Bearer $k" -H 'Content-Type: application/json' -d '{"model":"definitely-not-a-model-xyz","messages":[{"role":"user","content":"hi"}]}' >/dev/null
  echo "[T14] alias after bad model: $(curl -s --max-time 8 $B/health | python3 -c "import sys,json;print(json.load(sys.stdin).get('dynamic_alias_target'))" 2>/dev/null)"
  } >> "$OUT" 2>&1
done
echo "===== Vn AUDIT DONE $(date) =====" >> "$OUT"
```

### Pitfalls (read before running)
- `sonnet` → nemotron is SLOW (reasoning). `--max-time` < 40 on chat/anth =
  false "000". Use 40+.
- NEVER pipe SSE to `head -c` — SIGPIPE kills curl → misleading 000/empty.
  Save to temp file, then `grep`.
- After restart: `sleep 8` + poll `/health` before the matrix.
- `grep -oE 'BEARER_TOKEN=.+'` reads the key from `.env` (read-only, safe).
