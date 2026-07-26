---
name: super-coding
description: Maximum performance coding toolkit for ILMA — orchestrates parallel subagents, JIT compilation, vectorized computation, and intelligent caching for super heavy coding tasks on 16-core Xeon (2.8GB RAM, no GPU).
triggers:
  - "super heavy coding"
  - "super coding"
  - "optimize coding"
  - "heavy computation"
  - "paralel coding"
  - "intensive coding"
category: software-development
---

# Super Coding Toolkit — ILMA Maximum Performance Mode

## System Spec
- **CPU:** 16-core Intel Xeon E5-2665 @ 2.40GHz (NO AVX2/FMA/bmi1/bmi2/lzcnt/movbe!)
- **RAM:** ~1GB available at start (TIGHT — aggressive optimization mandatory)
- **GPU:** None
- **Python:** `/root/.hermes/hermes-agent/venv/bin/python3` (3.11.2)
- **Compilers:** GCC 12.2.0, G++ 12.2.0 (C/C++ native acceleration available)
- **Other runtimes:** Node.js v24.14.1, Go 1.19.8
- **Package managers:** uv 0.11.7, pip (via uv)
- **execute_code sandbox:** `/tmp/hermes_sandbox_*/script.py`

## Verified Working Libraries (execute_code)
```
numpy      2.4.4     — vectorized operations, array computing
numba      0.65.0    — JIT compilation for numerical loops (prange for parallelism)
pandas     3.0.2     — DataFrame operations (CRITICAL: memory-efficient usage required)
scipy      1.17.1    — scientific computing (FFT, sparse, optimization)
joblib     1.5.3     — parallel processing (Pipeline, Parallel)
rapidfuzz  3.14.5    — ultrafast fuzzy string matching (10x faster than fuzzywuzzy)
```

## CRITICAL: What DOES NOT Work
- **polars** — SIGILL crash on this CPU (no AVX2 support). DO NOT use.
- **numba on polars** — same AVX2 issue
- Any library requiring AVX2/FMA/bmi1/bmi2/lzcnt/movbe will crash with SIGILL

---

## Core Principles (Priority Order)

### 1. PARALLEL EXECUTION via delegate_task
- `max_concurrent_children=3` — queue extras
- Subagents CANNOT spawn more subagents (no recursion)
- Pass ALL context explicitly (subagents are isolated)

### 2. MEMORY FIRST — ~1GB Available is CRITICAL CONSTRAINT
- **Use pandas efficiently** — never load full big CSV into memory if you can avoid it
- **`pd.read_csv(chunksize=...)`** for large files — process row by row
- **Process and discard** — don't keep all intermediate results
- **`gc.collect()`** after EVERY heavy operation
- **Swap available:** 6GB swap (use for emergency, but it's slow)
- Monitor: `with open('/proc/meminfo') as f: ... if 'MemAvailable' in line`
- **Memory-efficient dtypes** — use `float32` instead of `float64` when precision allows, `int32` instead of `int64`

### 3. numba JIT — Numerical loops ONLY
- `@jit(nopython=True)` for pure numerical functions
- `@jit(nopython=True, parallel=True)` + `prange` for auto-parallelization on 16 cores
- DO NOT use numba for string manipulation, I/O, or complex objects
- numba compatible: numpy arrays, floats, ints, homogeneous lists
- **First call always JIT compiles** — subsequent calls are fast

### 4. C/C++ ACCELERATION (GCC)
- For hot paths that can't use numba: write C extension
- Compile: `gcc -O3 -shared -fPIC -o libname.so name.c -lm`
- Python ctypes FFI for calling compiled C

### 5. Go for CPU-intensive pipelines
- Go 1.19.8 available — excellent for concurrent/parallel CPU tasks
- Compile to binary, call from Python subprocess

### 6. VECTORIZATION ALWAYS
```python
# BAD — Python loop
result = [x**2 for x in data]

# GOOD — NumPy vectorized
result = np.array(data, dtype=np.float64) ** 2
```

---

## execute_code Best Practices

### Standard Header (ALWAYS include)
```python
import numpy as np
from numba import jit, prange
import pandas as pd
import gc
```

### Memory-Efficient Numba Pattern
```python
@jit(nopython=True, parallel=True)
def parallel_process(data):
    n = len(data)
    result = np.empty(n, dtype=np.float64)
    for i in prange(n):
        result[i] = heavy_calc(float(data[i]))
    return result

gc.collect()
result = parallel_process(large_array)
gc.collect()  # Clean up after
```

### Memory-Efficient Pandas Pattern
```python
# For very large CSV files
CHUNK_SIZE = 50_000
results = []
for chunk in pd.read_csv('bigfile.csv', chunksize=CHUNK_SIZE):
    processed = chunk[['col1', 'col2']].astype(np.float32)
    results.append(processed.sum())
    del chunk, processed
    gc.collect()
final = pd.concat(results, axis=0)
del results
gc.collect()
```

---

## delegate_task Strategy

### When to Delegate
- Task has ≥5 tool calls AND is splittable
- Multiple independent workstreams
- Debugging across multiple files
- Research + implementation parallel

### How to Delegate
```python
delegate_task(
    goal="""Complete task description with all specifics.
    File: /path/to/file.py
    Error: full error message here
    Expected: what should happen""",
    context="""Environment: 16-core Xeon, ~1GB RAM available, Python 3.11
    Available: numpy 2.4.4, numba 0.65.0, pandas 3.0.2, scipy 1.17.1
    DO NOT USE polars (crashes on this CPU)
    Working dir: /root/project""",
    toolsets=['terminal', 'file'],
    max_iterations=50
)
```

### Max 3 Concurrent
Always respect limit. Queue remaining tasks.

---

## Heavy Computation Patterns

### Pattern A: Large array numerical computation (numba)
```python
import numpy as np
from numba import jit, prange
import gc

@jit(nopython=True, parallel=True)
def matrix_multiply(A, B, n):
    C = np.empty((n, n), dtype=np.float64)
    for i in prange(n):
        for j in range(n):
            s = 0.0
            for k in range(n):
                s += A[i, k] * B[k, j]
            C[i, j] = s
    return C

A = np.random.randn(500, 500)
B = np.random.randn(500, 500)
C = matrix_multiply(A, B, 500)
del A, B, C
gc.collect()
```

### Pattern B: Chunked CSV processing (pandas)
```python
import pandas as pd
import numpy as np
import gc

def process_chunk(chunk):
    # Only keep what you need
    return chunk.select_dtypes(include=[np.number]).sum()

CHUNK = 100_000
results = []
for chunk in pd.read_csv('huge.csv', chunksize=CHUNK):
    results.append(process_chunk(chunk))
    del chunk
    gc.collect()

final = sum(results)
print('Result:', final)
```

### Pattern C: Fast string matching (rapidfuzz)
```python
from rapidfuzz import fuzz, process

# 10x faster than fuzzywuzzy
matches = process.extract(query, candidates, scorer=fuzz.WRatio, limit=10)
exact = process.extractOne(query, candidates, scorer=fuzz.partial_ratio)
```

### Pattern D: scipy optimization
```python
from scipy.optimize import minimize
from numba import jit
import numpy as np

@jit(nopython=True)
def rosen(x):
    return sum(100.0 * (x[1:] - x[:-1]**2)**2 + (1 - x[:-1])**2)

result = minimize(rosen, np.zeros(10), method='BFGS')
```

### Pattern E: joblib parallel
```python
from joblib import Parallel, delayed
import numpy as np

def heavy_task(item):
    return item ** 2

results = Parallel(n_jobs=4)(delayed(heavy_task)(i) for i in range(1000))
```

---

## Workflow: Super Heavy Task

```
1. ANALYZE   → Break into parallelizable chunks
              → Identify memory bottlenecks
              → Choose: numba? pandas? C? Go? delegate?

2. DELEGATE  → Spawn up to 3 subagents for independent workstreams
              → Pass complete context to each

3. EXECUTE   → Use execute_code with standard header
              → numba JIT for numerical loops
              → pandas chunked processing for large data
              → ALWAYS call gc.collect() after heavy ops

4. MERGE     → Combine subagent results
              → Final aggregation pass

5. CLEANUP   → Explicit gc.collect()
              → Delete intermediate files
              → Verify output
```

---

## Performance Anti-Patterns (NEVER DO)

❌ `for i in range(len(list))` → use `for item in list:` or `enumerate`
❌ List concatenation in loop → `result.append()` + `list.extend()`
❌ `pd.read_csv('big.csv')` for huge files → use `chunksize=`
❌ Materialize full dataset → use chunked processing
❌ Nested Python loops on numbers → numpy/numba
❌ Deepcopy large objects → use view/reference
❌ Load full file into memory → stream/chunk
❌ **polars** — crashes with SIGILL on this CPU
❌ float64 when float32 is enough (double RAM usage)
❌ Keep large DataFrames alive when done — `del df; gc.collect()`

---

## Opportunistic Installation

To add packages mid-task:
```python
import subprocess, sys
subprocess.run(
    ['uv', 'pip', 'install', '--python', '/root/.hermes/hermes-agent/venv/bin/python3', 'package_name'],
    check=True, capture_output=True
)
```

---

## Verification Checklist
- [ ] Standard header imported (numpy, numba, pandas, gc)
- [ ] Parallel paths used where possible
- [ ] Memory-conscious chunked processing
- [ ] numba JIT for numerical loops
- [ ] pandas for DataFrame operations (NOT polars)
- [ ] `gc.collect()` after heavy operations
- [ ] No unnecessary materialization
- [ ] float32 over float64 where possible
- [ ] NO polars (SIGILL crash)

## ⚠️ MANDATORY: Judge System Verification (Phase 20X)

After any super-heavy coding task, **DO NOT claim the task is complete until Judge System verification.**

### The Problem
ILMA could run super-heavy computation tasks, but had no way to prove the results were correct. Tests exist, but tests check "did the code run?" not "did the solution solve the problem?"

### The Fix
Run the Judge System after any major coding task:

```bash
# Quick targeted check (L1-L3 checkpoints)
python3 scripts/ilma_judge_system.py <your_output_file.py> \
    --task "Verify computation results are correct" \
    --checkpoints L1_syntax L1_import L2_unit_tests L3_shell_injection

# Full verification (all checkpoints)
python3 scripts/ilma_judge_system.py <your_output_file.py> \
    --task "Super heavy computation result verification" \
    --json
```

### Judge → Tool → Judge Loop for Super Heavy Tasks

```
1. Write/implement the solution
2. Judge evaluates: score = ?
3. If score < 92 (S+), call Claude/OpenCode to fix issues
4. Judge again: score improved?
5. Repeat until S+ or max_loops
```

### What Judge Evaluates for Super Heavy Tasks

| Checkpoint | Why It Matters |
|------------|----------------|
| L1_syntax | Code compiles without error |
| L1_import | All dependencies resolve |
| L2_unit_tests | Results are reproducible |
| L3_shell_injection | No security vulnerabilities |
| L3_secrets | No hardcoded credentials |
| L5_performance | Computations finish within time limit |
| L8_large_input | Handles edge case sizes correctly |

### Example: Post-Computation Verification

```python
# After running heavy computation...
import subprocess, json

# Run judge
result = subprocess.run(
    ['python3', 'scripts/ilma_judge_system.py', 
     'output/computation_result.py', 
     '--task', 'Heavy matrix computation verification',
     '--json'],
    capture_output=True, text=True
)

report = json.loads(result.stdout)
print(f"Grade: {report['grade']}")
print(f"Score: {report['raw_score']}/100")

if report['raw_score'] >= 92:
    print("✅ Production ready")
else:
    print("⚠️ Issues found — see failed checkpoints")
```

### Related Skills
- `ilma-judge-system` — L10 Evaluator for self-verification
- `ilma-evolution` — Evolution patterns including Judge integration
- **`ilma-codex-router`** — Codex gpt-5.5 is PRIMARY model for all actor callbacks (2026-05-11). All `ilma.py run` actor callbacks route through Codex primary → MiniMax fallback. Chain config: `coding_heavy`, `coding_light`, `general`, `reasoning`, `research` all use `codex (gpt-5.5) → minimax`.
