# SDK-Compat Audit Matrix — Reference (V1→V5 lessons)

**Purpose:** curl E2E matrix untuk audit wrapper yang klaim "OpenAI/Anthropic SDK compatible / 100/100 production". Copy template, ganti port/key, jalankan.

## 1. Template script (read-only)

```bash
#!/bin/bash
# SDK-compat audit — READ ONLY. Usage: bash audit.sh <port> <bearer>
set -u
P=$1; K=$2; B="http://127.0.0.1:$P"
ck(){ local n="$1" c="$2" w="$3"; [ "$c" = "$w" ] && echo "  [PASS] $n ($c)" || echo "  [FAIL] $n got=$c want=$w"; }
echo "===== :$P ====="
ck "chat explicit" "$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 $B/v1/chat/completions -H "Authorization: Bearer $K" -H 'Content-Type: application/json' -d '{"model":"sonnet","messages":[{"role":"user","content":"ping"}]}')" "200"
ck "chat empty(400)" "$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 $B/v1/chat/completions -H "Authorization: Bearer $K" -H 'Content-Type: application/json' -d '{"model":"sonnet","messages":[]}')" "400"
ck "chat malformed(400)" "$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 $B/v1/chat/completions -H "Authorization: Bearer $K" -H 'Content-Type: application/json' -d '{bad')" "400"
ck "chat tools" "$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 $B/v1/chat/completions -H "Authorization: Bearer $K" -H 'Content-Type: application/json' -d '{"model":"sonnet","messages":[{"role":"user","content":"w?"}],"tools":[{"type":"function","function":{"name":"gw","parameters":{"type":"object","properties":{"c":{"type":"string"}}}}}],"tool_choice":"auto"}')" "200"
ck "responses alias" "$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 $B/v1/responses -H "Authorization: Bearer $K" -H 'Content-Type: application/json' -d '{"model":"sonnet","input":"hi","stream":false}')" "200"
ck "anth tools" "$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 $B/v1/messages -H "Authorization: Bearer $K" -H 'anthropic-version: 2023-06-01' -H 'Content-Type: application/json' -d '{"model":"sonnet","max_tokens":100,"tools":[{"name":"gw","input_schema":{"type":"object","properties":{"c":{"type":"string"}}}}],"messages":[{"role":"user","content":"w?"}]}')" "200"
ck "anth system-array" "$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 $B/v1/messages -H "Authorization: Bearer $K" -H 'anthropic-version: 2023-06-01' -H 'Content-Type: application/json' -d '{"model":"sonnet","max_tokens":20,"system":[{"type":"text","text":"x"}],"messages":[{"role":"user","content":"hi"}]}')" "200"
ck "anth thinking" "$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 $B/v1/messages -H "Authorization: Bearer $K" -H 'anthropic-version: 2023-06-01' -H 'Content-Type: application/json' -d '{"model":"sonnet","max_tokens":200,"thinking":{"type":"enabled","budget_tokens":100},"messages":[{"role":"user","content":"2+2?"}]}')" "200"
ck "cors preflight(200)" "$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 -X OPTIONS $B/v1/chat/completions -H "Origin: http://localhost:9106" -H "Access-Control-Request-Method: POST")" "200"
ck "no-auth(401)" "$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 $B/v1/chat/completions -H 'Content-Type: application/json' -d '{"model":"sonnet","messages":[]}')" "401"
T=$(mktemp); curl -s --max-time 40 $B/v1/chat/completions -H "Authorization: Bearer $K" -H 'Content-Type: application/json' -d '{"model":"sonnet","messages":[{"role":"user","content":"say hi"}],"stream":true}' > "$T"
echo "  [INFO] chat SSE data_lines=$(grep -c '^data:' "$T") done=$(grep -c '^data: \[DONE\]' "$T")"
T3=$(mktemp); curl -s --max-time 40 $B/v1/messages -H "Authorization: Bearer $K" -H 'anthropic-version: 2023-06-01' -H 'Content-Type: application/json' -d '{"model":"sonnet","max_tokens":60,"messages":[{"role":"user","content":"hi"}],"stream":true}' > "$T3"
echo "  [INFO] anth SSE events: $(grep -oE 'event: [a-z_]+' "$T3" | sort -u | tr '\n' ' ')"
echo "  [INFO] usage: $(curl -s --max-time 30 $B/v1/chat/completions -H "Authorization: Bearer $K" -H 'Content-Type: application/json' -d '{"model":"sonnet","messages":[{"role":"user","content":"hi"}],"stream":false}' | python3 -c "import sys,json;d=json.load(sys.stdin);print('present' if d.get('usage') else 'MISSING')")"
echo "  [INFO] bad model: $(curl -s --max-time 25 $B/v1/chat/completions -H "Authorization: Bearer $K" -H 'Content-Type: application/json' -d '{"model":"definitely-not-a-model-xyz","messages":[{"role":"user","content":"hi"}]}' | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('error',{}).get('type','?'))")"
rm -f "$T" "$T3"
```

## 2. Findings patterns (V1→V5)

| Bug | Symptom | Root cause | Fix |
|-----|---------|-----------|-----|
| Anthropic tools 500 | `POST /v1/messages` + `tools` → 500 | `isinstance(tools)` typo (need `isinstance(tools, list)`) | patch 1 line |
| CORS preflight 401/400 | browser SDK preflight fails | auth middleware block OPTIONS; `allow_origins` too narrow | `allow_origin_regex` localhost + auth skip OPTIONS |
| Alias `sonnet` 404 | cold-start → alias None → pass-through → upstream reject | systemd unit missing `EnvironmentFile=` → `.env` not loaded | add `EnvironmentFile=-/path/.env` + `daemon-reload` |
| Alias cache pollution | health `dynamic_alias_target: nonexistent-model-xyz` | resolver caches invalid model | reject unknown, don't cache |
| Usage missing | non-stream chat no `usage` field | handler omits it | add `usage: {prompt,completion,total}` |
| Bad model → upstream 404 | `404 page not found` (Go format) | wrapper forwards upstream error raw | normalize to OpenAI `invalid_request_error` 400 |
| Missing anthropic-version → 404 | should be 400 | guard absent | add header check → 400 |

## 3. Gotchas

- **Warmup**: after `systemctl restart`, wait 8s before testing (uptime 2s → 404/000 false-negative).
- **Alias state**: `curl :port/health | python3 -c "import sys,json;print(json.load(sys.stdin).get('dynamic_alias_target'))"` — must be valid model, not None/polluted.
- **systemd EnvironmentFile**: `grep -c EnvironmentFile /root/.config/systemd/user/<unit>.service` — must be ≥1.
- **Overclaim**: post-audit report claiming 100 ≠ verified. Always re-run matrix independently.

## 4. Score framework

A code correctness · B SDK-compat · C resilience · D observability · E deploy · F security · G docs.
Weighted avg. 100/100 = all matrix PASS + no overclaim + independent re-verify green.
