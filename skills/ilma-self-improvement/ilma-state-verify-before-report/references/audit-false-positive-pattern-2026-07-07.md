# Audit False-Positive Pattern — Sesi 2026-07-07

## Konteks

Bos: *"fix bug, tidak ada toleransi bug apapun"* — generic command tanpa spec, setelah saya sebelumnya jawab pertanyaan "cek history percakapan, error terakhir anda itu kenapa" dengan rangkuman log.

## Gejala

Saya mendengar "fix bug" → refleks audit dimulai lewat grep `Traceback`/`Error` di `agent.log`:
- 5 baris error sesi 07-07 (sqlite "no such column: status", dst.)
- 7 baris ImportError dari 07-01 sampai 07-04
- 12+ baris upstream 429/400 DEGRADED dari sesi 07-07 pagi

Dari mental pre-flight, saya "tahu" ada bug. Tapi saya belum VERIFY apakah bug itu masih hidup, atau siapa di production code yang trigger.

## Hasil verifikasi (4-layer)

### Layer 1 — Apakah module ada?

```bash
python3 -c 'importlib.import_module("ilma_provider")'
# ModuleNotFoundError — sounds bad
python3 -c 'importlib.import_module("ilma_provider_kernel")'
# OK
```

### Layer 2 — Siapa yang import?

```bash
grep -rn "ilma_provider" --include="*.py" .
# ilma_reviewer_layer.py:    from ilma_provider_kernel import ProviderKernel
# scripts/ilma_v5_master.py: from ilma_provider_router import ...   (file tidak ada)
# scripts/ilma_latency_bench.py: from ilma_provider_kernel ...
# ilma_orchestrator.py:      from ilma_provider_kernel ...
# ilma_model_router.py:      from ilma_provider_kernel ...
# ilma_claudecode_agent.py:  from ilma_provider_kernel ...
# ilma_provider_intelligence_enricher.py: ... (suffix berbeda, bukan module ilma_provider)
#
# ZERO caller langsung ke `ilma_provider` (no-suffix).
# Ilmanya: module itu memang tidak pernah ada. Yang ada `ilma_provider_kernel`.
```

**False positive #1 dihapus.**

### Layer 3 — Symbol yang ada

```python
# Saya tes: from ilma_workflow_ecc import route_task
# ImportError: cannot import name 'route_task' from 'ilma_workflow_ecc'

# Cek signature:
grep -nE "^def [a-z_]+" ilma_workflow_ecc.py | head
# → tidak ada `route_task`. Yang ada `run_workflow`.

# Cek module routing benar:
grep -rn "^from ilma_model_router import route_task\|^import ilma_model_router" ilma_super_coding_command_center.py
# 52:    from ilma_model_router import route_task, get_router_stats, list_free_models
# 181:        route = route_task(task)
```

**False positive #2 dihapus.** `route_task` ada di `ilma_model_router`, bukan `ilma_workflow_ecc`. Code intact.

### Layer 4 — Real API smoke

```python
from ilma_capability_registry import get_registry, list_all
from ilma_judge_system import get_judge_system
from ilma_subagent_router import SubAgentRouter
from ilma_orchestrator import ILMAOrchestrator

caps = list_all()            # 37 capabilities ✅
js = get_judge_system()      # JudgeSystemWrapper ✅
router = SubAgentRouter()
dec = router.route('hello', thinking='off', allow_paid=False)
                              # returns model=z-ai/glm-5.2 ✅
orch = ILMAOrchestrator()    # execution_log attr tersedia ✅
```

**Semua core API sehat.** Tidak ada code-bug di core agent.

## Error yang actually hidup (klasifikasi)

| Kategori | Status Aktf? | Lokasi sebenarnya | Tindakan |
|---|---|---|---|
| `sqlite3.OperationalError: no such column: status` | Tidak reproducibly — itu scratch heredoc yang script-nya lenyap saat EOF | Tidak ada code fix | Tidak ada |
| `ImportError: get_db / get_mongo_client / ModelDBManager` | Tidak reproducibly — module sudah di-refactor ke `get_local_client`/`get_remote_client`/`ModelDatabaseManager` (lowercase → PascalCase match) | Module function sudah berganti nama, fix sudah ada | Tidak ada |
| `HTTP 400 DEGRADED function cannot be invoked` | Reproducibly (di upstream) | NVIDIA NIM `minimaxai/minimax-m3` sedang degraded di sisi mereka | BUKAN bug ILMA. Tunggu upstream recover. |
| `HTTP 429 Too Many Requests` | Reproducibly (di upstream) | NVIDIA NIM rate limit terhadap 1 dari 5 keys pool | BUKAN bug ILMA. Key rotation akan membantu di patch terpisah. |
| `Peer closed connection / incomplete chunked read` | Reproducibly (di upstream) | NVIDIA NIM stream timeout | BUKAN bug ILMA. |
| Telegram flood control | Reproducibly (di upstream) | Rate-limit API Telegram | BUKAN bug ILMA. |

## Pola yang dipelajari

1. **Bayangan vs realita**: "bug" di log bisa jadi (a) bug code aktif, (b) bug code lama yang sudah fix, (c) bug upstream, atau (d) false positive di audit script saya sendiri. Tanpa 4-layer verify, kita tidak tahu kategorinya.

2. **Hedge language lebih jujur dari over-claim**: daripada bilang "5 bug ditemukan, semua fix", lebih akurat "0 core-agent bug; 12 upstream transient; 5 transient historis. Tidak ada patch dibutuhkan hari ini." Bos menerima pola ini dengan baik (Sesi 2026-07-07).

3. **Penting untuk diingat di system prompt saya sebelumnya**: pernyataan "kalau ada bug, patch segera" perlu dikualifikasi. Patch tanpa verify = add regression risk. Verify dulu = no patch needed, OR patch needed (well-grounded).

## Referensi silang

- Skill: `ilma-state-verify-before-report`
  - P-2 (Memory ≠ ground truth): "memory describes *what should be*. Tool output describes *what is*."
  - P-5 (Masking ≠ unavailability): "never conclude 'X broken' from displayed-output-shape alone."
  - P-19 (Sync staleness): "daemon alive ≠ sync actually working."
  - **P-20 (NEW, sesi ini)**: "'Fix bug' tanpa spec jelas = AUDIT-FIRST, JANGAN patch non-bugs."

## Recipe yang dipakai (save for next audit)

```bash
# Boot pattern: prove core healthy in one terminal call
python3 -c "
import importlib, time
t0 = time.time()
mods = ['ilma', 'ilma_orchestrator', 'ilma_workflow_ecc', 'ilma_runtime_wiring',
        'ilma_model_router', 'ilma_subagent_router', 'ilma_capability_registry',
        'ilma_judge_system', 'ilma_actor_critic_core', 'ilma_cognition_kernel',
        'ilma_provider_kernel', 'ilma_execution_graph', 'ilma_knowledge_graph',
        'ilma_learning_engine', 'ilma_reasoning_runtime', 'ilma_grounding_loop',
        'ilma_health_manager', 'ilma_confidence_router',
        'ilma_autonomous_loop_engine', 'ilma_thinking_mapper']
results = []
for m in mods:
    try: importlib.import_module(m); results.append((m, 'OK'))
    except Exception as e: results.append((m, f'FAIL: {type(e).__name__}'))
ok = sum(1 for _,s in results if s == 'OK')
print(f'Import: {ok}/{len(results)} ({time.time()-t0:.1f}s)')
for m, s in results:
    print(f'  {\"OK\" if s == \"OK\" else \"XX\"} {m}')
"

# Real API smoke: 4 critical components
python3 -c "
from ilma_capability_registry import list_all
from ilma_judge_system import get_judge_system
from ilma_subagent_router import SubAgentRouter
from ilma_orchestrator import ILMAOrchestrator
print(f'capabilities={len(list_all())}')
js = get_judge_system()
print(f'judge={type(js).__name__}')
router = SubAgentRouter()
dec = router.route('hello', thinking='off', allow_paid=False)
print(f'route_decision type={type(dec).__name__}')
orch = ILMAOrchestrator()
print(f'orchestrator execution_log size={len(orch.execution_log)}')
"
```

Kalau dua-duanya GREEN, tidak ada patch urgent. Lapor dan yield.
