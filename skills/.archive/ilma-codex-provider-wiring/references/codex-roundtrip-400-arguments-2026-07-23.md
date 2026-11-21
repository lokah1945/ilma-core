# Codex ↔ wrapper-nous: 400 on tool round-trip (double-encoded arguments)

**Date:** 2026-07-23
**Context:** Bos reported "proses codex terhenti" + repeated `400 Provider returned error` from
Codex CLI v0.145.0 against `wrapper-nous` (FastAPI proxy, `:9106`, translates OpenAI
Responses API → Nous `/v1/chat/completions`).

## Symptom
Codex 1st turn works (tool gets invoked, file gets written), but after the tool result is
sent back to the model, Codex errors:
```
■ {"error":{"message":"This request is not valid. Check the model name and other parameters. Additional info: Provider returned error","type":"api_error","code":400}}
exit: 1
```
The final synthesis ("Created `/tmp/x` with...") never appears.

## Investigation trail (evidence-first, no assumptions)
1. `wrapper-nous` `/metrics` showed `total_requests: 0` while Codex "running" → Codex was
   NOT hitting the proxy during some calls. Ruled out: proxy itself was fine (curl tests passed).
2. Reproduced Codex's 2nd-turn payload with curl (FULL input array, no `previous_response_id`):
   `[message(user), function_call, function_call_output]` → proxy returned **400**.
   Reproduced 2nd-turn WITH `previous_response_id` + `function_call_output` → proxy returned **200**.
   ⇒ The failure is specific to the full-array 2nd-turn shape Codex actually sends.
3. Unit-tested `responses_to_chat()` directly with that payload:
   ```python
   out = responses_to_chat(body)
   out['messages'][1]['tool_calls'][0]['function']['arguments']
   # → "\"{\\\"path\\\":\\\"...\\\"}\""   ← DOUBLE-ENCODED string
   ```
   Root cause: `arguments` from Codex is already a JSON **string**; `json.dumps()` wrapped it
   again → Nous rejected the string-in-string.
4. Verified the fix (type-check) makes `arguments` a valid JSON object; repro curl → **200**;
   real `codex exec` tool task → **exit 0** with final synthesis.

## The exact fix (in `responses_to_chat`, the `function_call` branch)
BEFORE (buggy):
```python
msgs.append({"role":"assistant","content":None,
             "tool_calls":[{"id":it.get("call_id"),"type":"function",
                            "function":{"name":it.get("name"),
                                        "arguments": json.dumps(it.get("arguments", {}))}}]})
```
AFTER (fixed):
```python
raw_args = it.get("arguments", "")
args_out = raw_args if isinstance(raw_args, str) else json.dumps(raw_args)
msgs.append({"role":"assistant","content":None,
             "tool_calls":[{"id":it.get("call_id"),"type":"function",
                            "function":{"name":it.get("name"),"arguments":args_out}}]})
```

## Full fix chain for "Codex terhenti" (all in `wrapper_nous.py` ResponsesStreamState)
| # | Error seen | Fix |
|---|-----------|-----|
| 1 | `missing field input_tokens` | Single idempotent `response.completed`; `_normalize_usage()` maps `prompt_tokens→input_tokens`, `completion_tokens→output_tokens` |
| 2 | `missing field total_tokens` | `_normalize_usage()` returns `input_tokens + output_tokens + total_tokens` |
| 3 | `OutputTextDelta without active item` (hang) | `start()` emits `output_item.added` + `content_part.added` before deltas; `done()` emits `output_text.done` + `content_part.done` + `output_item.done` |
| 4 | `400 Provider returned error` on round-trip | `tool_delta()` emits `output_item.added` (type=function_call) + stable `_active_tool_id` across chunks; `done()` closes every tracked tool; AND the `arguments` double-encode type-check above |

## Verified end-to-end result
```
$ codex exec --model tencent/hy3:free "create file /tmp/codex_e2e.txt with exact text E2E_OK, then tell me the file was created"
exec /bin/bash -lc "printf 'E2E_OK' > /tmp/codex_e2e.txt && cat /tmp/codex_e2e.txt"  → succeeded
codex: Created `/tmp/codex_e2e.txt` with the exact contents `E2E_OK` (no trailing newline). Verified the file content matches.
tokens used 17.768
exit: 0
$ cat /tmp/codex_e2e.txt  → E2E_OK
```

## Gotcha: systemd user journal may not persist
`journalctl --user -u wrapper-nous.service` returned "No journal files were found" on this box.
To capture proxy-side payloads, point the logger at a file:
```python
logging.basicConfig(level=logging.INFO, format="%(asctime)s [nous] %(message)s",
                    handlers=[logging.FileHandler("/root/wrapper/nous/wrapper_nous.log"),
                               logging.StreamHandler()])
```
Then tail `/root/wrapper/nous/wrapper_nous.log` after a failing Codex call.
