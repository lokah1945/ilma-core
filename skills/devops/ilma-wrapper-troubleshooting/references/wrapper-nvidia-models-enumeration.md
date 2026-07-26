# Wrapper-NVIDIA Model Enumeration & Classification

Reproducible recipe + real inventory captured 2026-07-25 on `wrapper-nvidia` (port 9101).

## Recipe
```bash
curl -s -m 10 http://127.0.0.1:9101/v1/models > /tmp/nv_models.json
python3 -c "
import json
from collections import Counter
d=json.load(open('/tmp/nv_models.json'))
data=d.get('data',[])
avail=[m for m in data if m.get('ok')]
unavail=[m for m in data if not m.get('ok')]
print('total',len(data),'usable',len(avail),'unusable',len(unavail))
print('by availability_state:', dict(Counter(m.get('availability_state') for m in unavail)))
print('--- USABLE ---')
for i,m in enumerate(avail,1): print(i, m['id'])
print('--- UNAVAILABLE (id [http|reason_code]) ---')
for i,m in enumerate(unavail,1):
    print(i, m['id'], '['+str(m.get('last_status'))+'|'+str(m.get('reason_code') or m.get('availability_state'))+']')
"
```

## Key fields per model entry
- `id` — model id (e.g. `minimaxai/minimax-m3`)
- `ok` (bool) — **callable now** iff True
- `last_status` — HTTP code of last probe (200/404/0/500/400/None)
- `verified` (bool) — wrapper ran a real probe
- `catalog_listed` (bool) — present in NVIDIA public catalog
- `availability_state` / `availability_scope` / `reason_code` / `reason`

## availability_state taxonomy
| state | reason_code | fix to usable |
|---|---|---|
| `account_unavailable` | `NOT_DEPLOYED_FOR_ACCOUNT` | deploy/subscribe on build.nvidia.com → restart wrapper |
| `wrong_route` | `UPSTREAM_ROUTE_NOT_FOUND` | NVIDIA-side, not account-fixable (embed/retrieval) |
| `mixed` | `MULTIPLE_ACCOUNT_OR_ENDPOINT_STATES` | re-probe; may need correct account context |
| `network_timeout` | `NETWORK_OR_TIMEOUT` | transient; re-verify later |
| `transient_failure` | `UPSTREAM_TRANSIENT` (500) | transient; re-verify later |
| `capability_mismatch` | `INVALID_REQUEST_OR_PARAMETER` (400) | check params |
| `unknown` | `MODEL_NOT_FOUND_OR_UNAVAILABLE` / None | absent or alias stub (`haiku`/`sonnet`/`opus`) |

## Real inventory 2026-07-25 (wrapper-nvidia 9101)
- **Total: 134** | **Usable: 51** | **Unusable: 83**
- Unusable breakdown: 45 `account_unavailable`, 14 `wrong_route`, 10 `mixed`, 5 `network_timeout`, 2 `transient_failure`, 2 `capability_mismatch`, 5 `unknown`/alias.

### 51 Usable
**Text/Chat LLM (25):** abacusai/dracarys-llama-3.1-70b-instruct, bytedance/seed-oss-36b-instruct, google/gemma-2-2b-it, google/gemma-3n-e2b-it, google/gemma-3n-e4b-it, meta/llama-3.1-70b-instruct, meta/llama-3.1-8b-instruct, meta/llama-3.2-11b-vision-instruct, meta/llama-3.2-90b-vision-instruct, meta/llama-4-maverick-17b-128e-instruct, minimaxai/minimax-m2.7, mistralai/mistral-medium-3.5-128b, mistralai/mistral-small-4-119b-2603, mistralai/mixtral-8x7b-instruct-v0.1, openai/gpt-oss-120b, openai/gpt-oss-20b, poolside/laguna-xs-2.1, qwen/qwen3-next-80b-a3b-instruct, sarvamai/sarvam-m, stepfun-ai/step-3.5-flash, upstage/solar-10.7b-instruct, nvidia/llama-3.3-nemotron-super-49b-v1, nvidia/llama-3.3-nemotron-super-49b-v1.5, nvidia/nemotron-3-nano-30b-a3b, nvidia/nemotron-3-nano-omni-30b-a3b-reasoning
**Nemotron/Safety/Guard (11):** nvidia/nemotron-3-super-120b-a12b, nvidia/nemotron-3.5-content-safety, nvidia/nemotron-mini-4b-instruct, nvidia/nemotron-nano-12b-v2-vl, nvidia/nvidia-nemotron-nano-9b-v2, nvidia/llama-3.1-nemoguard-8b-content-safety, nvidia/llama-3.1-nemotron-nano-vl-8b-v1, nvidia/llama-3.1-nemotron-safety-guard-8b-v3, nvidia/ising-calibration-1-35b-a3b, nvidia/ising-calibration-1.5-31b, nvidia/gliner-pii
**VL/Audio/Vision (4):** nvidia/riva-translate-4b-instruct-v1.1, nvidia/fugatto, nvidia/nemotron-nano-12b-v2-vl, google/diffusiongemma-26b-a4b-it
**Image-gen (11):** black-forest-labs/flux.1-dev, flux.1-schnell, flux.1-kontext-dev, flux.1-canny-dev, flux.1-depth-dev, flux.2-klein, stabilityai/stable-diffusion-3.5-large, qwen/qwen-image, qwen/qwen-image-edit, playgroundai/playground-v2.5-1024px-aesthetic, kandinsky-community/kandinsky-3 (+ consistory/consistory)

### 83 Unusable (selected notable)
- `account_unavailable` (45): 01-ai/yi-large, adept/fuyu-8b, ai21labs/jamba-1.5-large-instruct, aisingapore/sea-lion-7b-instruct, databricks/dbrx-instruct, deepseek-ai/deepseek-coder-6.7b-instruct, google/codegemma-1.1-7b, google/codegemma-7b, google/deplot, google/gemma-2b, google/gemma-3-12b-it, google/gemma-3-4b-it, google/recurrentgemma-2b, ibm/granite-3.0-3b-a800m-instruct, ibm/granite-3.0-8b-instruct, ibm/granite-34b-code-instruct, ibm/granite-8b-code-instruct, meta/codellama-70b, meta/llama2-70b, microsoft/kosmos-2, microsoft/phi-3-vision-128k-instruct, microsoft/phi-3.5-moe-instruct, mistralai/codestral-22b-instruct-v0.1, mistralai/mistral-7b-instruct-v0.3, mistralai/mistral-large, mistralai/mistral-large-2-instruct, mistralai/mixtral-8x22b-v0.1, moonshotai/kimi-k2.6, nv-mistralai/mistral-nemo-12b-instruct, nvidia/cosmos-reason2-8b, nvidia/llama-3.1-nemotron-51b-instruct, nvidia/llama-3.1-nemotron-70b-instruct, nvidia/llama-3.1-nemotron-ultra-253b-v1, nvidia/llama3-chatqa-1.5-70b, nvidia/mistral-nemo-minitron-8b-8k-instruct, nvidia/nemotron-4-340b-instruct, nvidia/nemotron-4-340b-reward, nvidia/neva-22b, nvidia/riva-translate-4b-instruct, nvidia/vila, writer/palmyra-creative-122b, writer/palmyra-fin-70b-32k, writer/palmyra-med-70b, writer/palmyra-med-70b-32k, zyphra/zamba2-7b-instruct
- `wrong_route` (14): baai/bge-m3, bigcode/starcoder2-15b, nvidia/embed-qa-4, nvidia/llama-3.2-nemoretriever-1b-vlm-embed-v1, nvidia/llama-3.2-nv-embedqa-1b-v1, nvidia/llama-nemotron-embed-1b-v2, nvidia/llama-nemotron-embed-vl-1b-v2, nvidia/nemotron-3-embed-1b, nvidia/nv-embed-v1, nvidia/nv-embedcode-7b-v1, nvidia/nv-embedqa-e5-v5, nvidia/nv-embedqa-mistral-7b-v2, nvidia/nvclip, snowflake/arctic-embed-l
- `mixed` (10): deepseek-ai/deepseek-v4-flash, deepseek-ai/deepseek-v4-pro, google/gemma-4-31b-it, meta/llama-3.3-70b-instruct, meta/llama-3.2-3b-instruct, minimaxai/minimax-m3, mistralai/mistral-nemotron, nvidia/nemotron-3-ultra-550b-a55b, stepfun-ai/step-3.7-flash, z-ai/glm-5.2
- `network_timeout` (5): meta/llama-3.2-1b-instruct, meta/llama-guard-4-12b, mistralai/ministral-14b-instruct-2512, nvidia/llama-3.1-nemotron-nano-8b-v1, thinkingmachines/inkling
- `transient_failure` (2): nvidia/ai-synthetic-video-detector, nvidia/llama-3.1-nemoguard-8b-topic-control
- `capability_mismatch` (2): nvidia/nemoretriever-parse, nvidia/nemotron-parse
- `unknown`/alias (5): nvidia/nemotron-nano-3-30b-a3b, qwen/qwen3.5-397b-a17b, haiku, sonnet, opus

## Case: `minimaxai/minimax-m3` (mixed, not account_unavailable)
- `catalog_listed=true`, `ok=false`, `availability_state=mixed`, `reason_code=MULTIPLE_ACCOUNT_OR_ENDPOINT_STATES`, `last_status=0`, `verified=true`.
- Means: model IS in public catalog + on build.nvidia.com, but wrapper's verify sweep saw differing account/endpoint availability → not callable through THIS account yet.
- Direct call via wrapper returned HTTP 000 (connection failed) — confirms not usable now.
- Fix: deploy/subscribe the model to the NVIDIA account behind the wrapper's key on build.nvidia.com, restart `wrapper-nvidia-python`, let it re-verify → `ok` flips to true (inventory 51→52).
- Do NOT report `mixed` models as "not deployed" — they're "state not settled / wrong account context". Distinct from the 45 clear `account_unavailable`.
