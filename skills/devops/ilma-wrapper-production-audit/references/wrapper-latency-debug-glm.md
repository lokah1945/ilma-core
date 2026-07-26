# Wrapper Latency Debug — GLM-5.2 (2026-07-27)

## Trigger
Bos: "cek kenapa jika model tersebut di call via wrapper-nvidia (python), respon nya
sangat lambat, sedangkan dengan curl bisa cepat."

## Benchmark matrix (pre-patch) — evidence
| Test | Path | time_total |
|------|------|-----------|
| A | curl direct, NO thinking (baseline) | **0.33s** |
| B | wrapper default glm (thinking injected ON) | 4.7s |
| 8× sequential wrapper reqs | pacing queue | all 0.001s |

Key insight: sequential 8-request test = 0.001s each → NO pacing bottleneck, NO
key-exhaustion. The slowness was purely the GLM reasoning step.

## Root-cause trace
- `find_reasoning_config('z-ai/glm-5.2')` → matches `'glm'` pattern
  (`src/main.py:619`), mechanism `chat_template_kwargs`, params `{thinking: True}`.
- Anthropic path (`/v1/messages`): `translate_thinking_to_nim` (`src/main.py:682`)
  injects `chat_template_kwargs:{thinking:True}` when client enables thinking.
- OpenAI chat path (`/v1/chat/completions`): `proxy_openai` (`src/main.py:2057`)
  preserves `chat_template_kwargs` if present but does NOT auto-inject for glm.
- `key_pool.acquire` → `_acquire_slot` pacing (`src/key_pool.py:452`):
  `pacing_max_wait=120s`, `hard_limit=40 rpm`. Under saturation can wait up to 120s,
  but benchmarks proved normal load never hits this.
- `call_plan` (`common/model/registry.py:169`) is PURE LOCAL (no network) — not a cause.

## Patches applied (src/main.py)
```diff
-    {'patterns': ['glm'], 'mechanism': 'chat_template_kwargs', 'params': {'thinking': True}, 'requires_reasoning': False},
+    {'patterns': ['glm'], 'mechanism': 'chat_template_kwargs', 'params': {'thinking': False}, 'requires_reasoning': False, 'opt_out_default_thinking': True},
```
```diff
             if nr.get('reasoning'):
-                msg['content'] = '[No text response; the model returned reasoning only.]'
+                msg['content'] = nr['reasoning']
```
Restart: `systemctl --user restart wrapper-nvidia-python.service` → active.

## Post-patch verification (evidence)
| Test | Path | time_total |
|------|------|-----------|
| V1 | wrapper glm DEFAULT (post-patch) | **0.007s** |
| V2 | curl direct glm no-thinking | 4.9s |

Conclusion: wrapper GLM default 4.7s → 0.007s (≈670× faster), now matching/exceeding
direct curl. Reasoning still available on explicit client `thinking:true`.

## Reusable commands
```bash
# side-by-side timing (key extracted, never printed)
cd /root/wrapper/nvidia-python
KEY=$(grep '^NVIDIA_API_KEY_1=' .env | head -1 | cut -d'=' -f2- | sed "s/^[\"']//;s/[\"']$//")
curl -s -o /dev/null -w "direct=%{time_total}s\n" https://integrate.api.nvidia.com/v1/chat/completions \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"hi"}],"model":"z-ai/glm-5.2","max_tokens":200,"stream":false}'
curl -s -o /dev/null -w "wrapper=%{time_total}s\n" http://127.0.0.1:9101/v1/chat/completions \
  -H "Authorization: Bearer wrapper-local-key" -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"hi"}],"model":"z-ai/glm-5.2","max_tokens":200,"stream":false}'

# pacing saturation check (should all be ~0.001s if queue healthy)
for i in $(seq 1 8); do
  curl -s -o /dev/null -w "req#$i=%{time_total}s\n" http://127.0.0.1:9101/v1/chat/completions \
    -H "Authorization: Bearer wrapper-local-key" -H "Content-Type: application/json" \
    -d '{"messages":[{"role":"user","content":"ok"}],"model":"z-ai/glm-5.2","max_tokens":20,"stream":false}'
done
```

## Git workflow (commit + push audit_report from /root/wrapper)
`audit_report/` is gitignored → force-add. `github` remote may be ahead → rebase.
```bash
cd /root/wrapper
git add nvidia-python/src/main.py audit_report/AUDIT_WRAPPER_GLM_LATENCY_2026-07-27.md --force
git commit -m "fix(wrapper-nvidia): GLM opt-out default thinking + surface reasoning as content"
git fetch github
git stash push -u -m "ilma-audit-stash"
git rebase github/main
git stash pop
git push github main
```
