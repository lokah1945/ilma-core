---
name: ilma-delegate
description: When to delegate a subtask to ILMA's free-only capability runtime (image/tts/stt/embedding/rerank/video generation, bulk parallel free-model work, SOT capability dispatch) instead of doing it inline. Use for media generation and high-volume free-model delegation.
tags:
  - delegation
  - capability
  - free-tier
  - media
  - military
triggers:
  - "generate image"
  - "buatkan gambar"
  - "text to speech"
  - "transcribe"
  - "embedding"
  - "rerank"
  - "generate video"
  - "delegate to ilma"
  - "free model"
  - "bulk generate"
---

# ILMA Capability Delegation

The live gateway agent (you) is the strongest model. Keep reasoning/writing/coding for
yourself, but **delegate these to ILMA's verified free-only runtime** — they have a real,
tested SOT-driven path that always picks the best FREE model (no paid fallback unless asked):

## When to delegate

| Need | Delegate via | Free backend (verified) |
|---|---|---|
| Generate an image | `execute_capability("image", prompt)` | nvidia FLUX.1-schnell (wrapper-nvidia genai) |
| Text → speech | `execute_capability("tts", input_text=...)` | edge-tts (local) |
| Speech → text | `execute_capability("stt", audio_path=...)` | groq whisper-large-v3 |
| Embeddings | `execute_capability("embedding", input_text=...)` | wrapper-nvidia nv-embedqa |
| Rerank documents | `execute_capability("rerank", prompt=query, documents=[...])` | embedding-cosine (free) |
| Video (if MiniMax credits) | `execute_capability("video", prompt)` | MiniMax Hailuo (quota-gated) |
| Bulk/parallel free-model work | `ilma_orchestrator.execute(prompt, task_type=...)` | best free model per task, self-healing router |
| Pick best free model for a capability | `ilma_sot_dispatcher.sot_dispatch(cap, strict=True)` | SOT `models` (is_free_final gate) |

## How to call

```bash
# media / capability (returns saved path or text):
/root/.hermes/hermes-agent/venv/bin/python3 - <<'PY'
import sys; sys.path.insert(0,'/root/.hermes/profiles/ilma')
from ilma_subagent_router import execute_capability
print(execute_capability("image", "a red apple, product photo"))
PY

# full research-grounded academic doc (skripsi/tesis/disertasi/paper) with citations:
/root/.hermes/hermes-agent/venv/bin/python3 ilma_scriptorium.py --topic "..." --type skripsi --scope external

# verified coding (generate→sandboxed-test→repair→adjudicate):
/root/.hermes/hermes-agent/venv/bin/python3 - <<'PY'
import sys; sys.path.insert(0,'/root/.hermes/profiles/ilma')
from ilma_coding_worker_adapter import run_coding_task
print(run_coding_task("implement <spec>", files=["x.py"], repo="/tmp/work"))
PY
```

## Rules
- ILMA capability runtime is **free-only by default** (`allow_paid=False`). Honors the constitution's free-tier-first rule.
- For academic work, ILMA grounds claims against real retrieved sources and reports a grounding score — prefer it over writing citations yourself (no fabrication).
- These paths are verified working (2026-06-22): image, stt, embedding, tts, rerank, chat-generation, skripsi BAB I–V, coding loop. Video/music are wired but MiniMax-quota-gated.
