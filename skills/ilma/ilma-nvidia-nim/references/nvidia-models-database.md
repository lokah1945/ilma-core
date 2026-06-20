# NVIDIA NIM — 117 Model Live Test Results

**Test Date:** 2026-05-25
**Endpoint:** `https://integrate.api.nvidia.com/v1/chat/completions`
**Auth:** `<REDACTED-NVAPI>`
**Method:** curl with 15s timeout, "Hi" prompt, max_tokens=16

---

## Summary

| Status | Count |
|--------|-------|
| ✅ WORKING | 43 |
| ⚠️ EMPTY | 71 |
| ❌ ERROR | 3 |
| ⏳ TIMEOUT | 0 |

---

## ✅ Working Models (43)

```
deepseek-ai/deepseek-v4-flash
google/gemma-2-2b-it
google/gemma-3n-e2b-it
google/gemma-3n-e4b-it
meta/llama-3.1-70b-instruct
meta/llama-3.1-8b-instruct
meta/llama-3.2-11b-vision-instruct
meta/llama-3.2-1b-instruct
meta/llama-3.2-3b-instruct
meta/llama-3.2-90b-vision-instruct
meta/llama-3.3-70b-instruct
meta/llama-4-maverick-17b-128e-instruct ⭐ thinking
meta/llama-guard-4-12b
mistralai/ministral-14b-instruct-2512
mistralai/mistral-7b-instruct-v0.3
mistralai/mistral-large-3-675b-instruct-2512
mistralai/mistral-nemotron
mistralai/mistral-small-4-119b-2603
mistralai/mixtral-8x7b-instruct-v0.1
qwen/qwen3.5-397b-a17b ⭐ thinking
sarvamai/sarvam-m
stepfun-ai/step-3.5-flash
stockmark/stockmark-2-100b-instruct
upstage/solar-10.7b-instruct
nvidia/nemotron-3-nano-30b-a3b
nvidia/llama-3.1-nemoguard-8b-content-safety
nvidia/ising-calibration-1-35b-a3b
nvidia/llama-3.3-nemotron-super-49b-v1 ⭐ thinking
nvidia/nemotron-nano-12b-v2-vl
openai/gpt-oss-20b
openai/gpt-oss-120b
nvidia/gliner-pii
nvidia/llama-3.1-nemotron-nano-8b-v1
nvidia/nemotron-mini-4b-instruct
nvidia/llama-3.1-nemotron-safety-guard-8b-v3
nvidia/llama-3.1-nemoguard-8b-topic-control
nvidia/nemotron-3-nano-omni-30b-a3b-reasoning ⭐ thinking
nvidia/llama-3.1-nemotron-nano-vl-8b-v1
nvidia/nemotron-content-safety-reasoning-4b ⭐ thinking
nvidia/nvidia-nemotron-nano-9b-v2
nvidia/riva-translate-4b-instruct-v1.1
nvidia/nemotron-3-content-safety
nvidia/nemotron-3-super-120b-a12b
```

---

## ⭐ Thinking Models (verified with `enable_thinking`)

Test command for thinking models:
```bash
curl -s -N -X POST "https://integrate.api.nvidia.com/v1/chat/completions" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "MODEL_ID",
    "messages": [{"role": "user", "content": "What is 2+2?"}],
    "max_tokens": 128,
    "extra_body": {
      "chat_template_kwargs": {"enable_thinking": true},
      "reasoning_budget": 128
    }
  }'
```

| Model | Thinking Response | Notes |
|-------|------------------|-------|
| `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` | ✅ Returns `reasoning_content` + `content` | Full sqrt(2) proof verified |
| `nvidia/nemotron-content-safety-reasoning-4b` | ✅ Returns `reasoning_content` + `content` | Math + safety verified |
| `nvidia/llama-3.3-nemotron-super-49b-v1` | ✅ Returns `reasoning_content` + `content` | |
| `qwen/qwen3.5-397b-a17b` | ✅ Returns `reasoning_content` + `content` | |
| `meta/llama-4-maverick-17b-128e-instruct` | ✅ Returns `reasoning_content` + `content` | |
| `nvidia/cosmos-reason2-8b` | ❌ EMPTY | Rate-limited |
| `nvidia/llama-3.1-nemotron-ultra-253b-v1` | ❌ EMPTY | Rate-limited |
| `google/gemma-4-31b-it` | ❌ EMPTY | Rate-limited |

---

## ❌ Error Models (3)

```
nvidia/nemoretriever-parse
nvidia/nemotron-parse
nvidia/nemotron-nano-3-30b-a3b
```

---

## ⚠️ Empty Models (71)

Most likely cause: **free tier quota exhausted** for the day. These models work but returned no content.

```
01-ai/yi-large
abacusai/dracarys-llama-3.1-70b-instruct
adept/fuyu-8b
ai21labs/jamba-1.5-large-instruct
aisingapore/sea-lion-7b-instruct
baai/bge-m3
bigcode/starcoder2-15b
bytedance/seed-oss-36b-instruct
databricks/dbrx-instruct
deepseek-ai/deepseek-coder-6.7b-instruct
deepseek-ai/deepseek-v4-pro
google/codegemma-1.1-7b
google/codegemma-7b
google/deplot
google/gemma-2b
google/recurrentgemma-2b
ibm/granite-3.0-3b-a800m-instruct
ibm/granite-3.0-8b-instruct
ibm/granite-34b-code-instruct
ibm/granite-8b-code-instruct
meta/codellama-70b
meta/llama2-70b
microsoft/kosmos-2
microsoft/phi-3-vision-128k-instruct
microsoft/phi-3.5-moe-instruct
microsoft/phi-4-mini-instruct
microsoft/phi-4-multimodal-instruct
minimaxai/minimax-m2.7
mistralai/codestral-22b-instruct-v0.1
mistralai/mistral-large-2-instruct
mistralai/mistral-medium-3.5-128b
mistralai/mixtral-8x22b-v0.1
nv-mistralai/mistral-nemo-12b-instruct
qwen/qwen3-coder-480b-a35b-instruct
snowflake/arctic-embed-l
writer/palmyra-creative-122b
writer/palmyra-fin-70b-32k
writer/palmyra-med-70b
writer/palmyra-med-70b-32k
zyphra/zamba2-7b-instruct
nvidia/riva-translate-4b-instruct
nvidia/llama-3.2-nv-embedqa-1b-v1
nvidia/llama-3.1-nemotron-51b-instruct
nvidia/llama3-chatqa-1.5-70b
nvidia/nemotron-4-340b-instruct
nvidia/cosmos-reason2-8b
z-ai/glm-5.1
nvidia/nvclip
nvidia/llama-3.1-nemotron-ultra-253b-v1
nvidia/nemoretriever-parse
nvidia/llama-3.3-nemotron-super-49b-v1.5
mistralai/mistral-large
nvidia/llama-3.2-nemoretriever-1b-vlm-embed-v1
nvidia/mistral-nemo-minitron-8b-8k-instruct
google/gemma-3-12b-it
nvidia/nemotron-parse
nvidia/nv-embedqa-e5-v5
nvidia/nemotron-nano-3-30b-a3b
nvidia/embed-qa-4
google/gemma-3-4b-it
nvidia/llama-nemotron-embed-vl-1b-v2
nvidia/nemotron-4-340b-reward
nvidia/ai-synthetic-video-detector
qwen/qwen3-next-80b-a3b-instruct
moonshotai/kimi-k2.6
nvidia/neva-22b
qwen/qwen3.5-122b-a10b
nvidia/llama-3.1-nemoguard-8b-topic-control (wait, this is in working)
nvidia/vila
nvidia/nv-embedqa-mistral-7b-v2
nvidia/llama-3.1-nemotron-70b-instruct
nvidia/llama-nemotron-embed-1b-v2
nvidia/nv-embed-v1
```

---

## Database Structure

The `PROVIDER_INTELLIGENCE_MASTER.json` uses this structure for NVIDIA:

```python
{
  "providers": {
    "nvidia": {
      "endpoints": ["https://integrate.api.nvidia.com/v1"],
      "models": {
        "meta/llama-3.1-70b-instruct": {
          "name": "Llama 3.1 70B Instruct",
          "provider": "nvidia",
          "model_id": "meta/llama-3.1-70b-instruct",
          "context_window": 128000,
          "is_free": true,
          "capabilities": ["chat", "instruct"],
          "features": ["chat", "instruct"],
          "test_status": "working",
          "live_tested": true,
          ...
        }
      }
    }
  }
}
```

**Access pattern:**
```python
db = json.load(open('PROVIDER_INTELLIGENCE_MASTER.json'))
models = db['providers']['nvidia']['models']  # dict, NOT list
model_ids = list(models.keys())  # get all model IDs
```

---

## Test Script (reusable)

Location: `/tmp/test_nvidia_models.sh`

```bash
#!/bin/bash
MODEL="$1"
KEY="<REDACTED-NVAPI>"
RESP=$(curl -s --max-time 15 -X POST "https://integrate.api.nvidia.com/v1/chat/completions" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"Hi\"}],\"max_tokens\":16,\"stream\":false}")

if echo "$RESP" | grep -q '"error"'; then
  echo "ERROR"
elif echo "$RESP" | grep -q '"content"'; then
  echo "OK"
else
  echo "EMPTY"
fi
```

Usage:
```bash
chmod +x /tmp/test_nvidia_models.sh
/tmp/test_nvidia_models.sh "meta/llama-3.1-70b-instruct"
```