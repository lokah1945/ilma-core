# Live Research Module Reference
## Phase 57 — ilma_live_research.py

---

## Module Location

```
scripts/ilma_live_research.py
```

---

## Class: LiveResearch

### Constructor

```python
lr = LiveResearch()
```

Internal state:
- `cache_dir`: `.cache/live_research/`
- `cache_ttl`: 1800 seconds (30 min)
- `search_providers`: ["duckduckgo", "bing"]
- `known_patterns_cache`: loaded from cache file

### Methods

#### `research(error_context, task_type, root_cause, failed_attempts, max_duration=30.0)`

Performs live research on error/problem.

**Returns:** `ResearchResult`

```python
result = lr.research(
    error_context="ModuleNotFoundError: No module named 'torch'",
    task_type="code",
    root_cause="unknown",
    failed_attempts=2
)
# result.solutions   — List[str] of potential solutions
# result.papers      — List[Dict] with title, url, abstract
# result.confidence  — float 0.0-1.0
# result.new_knowledge — List[str] of new learnings
# result.sources     — List[str] of source URLs
# result.research_duration — float seconds
```

**Research Flow:**
1. Build queries from error context
2. **FELO FREE native_search** (DuckDuckGo + Wikipedia — 100% FREE, no API key) — PRIMARY
3. arXiv search (for code/analysis/planning tasks)
4. Check known patterns cache
5. Deduplicate and score confidence
6. Generate new knowledge entries
7. Return ResearchResult

#### `should_research(failed_attempts, root_cause, has_lesson_memory, confidence=0.0)`

Pre-research check to determine if live research is warranted.

**Returns:** `(bool, str)` — (should_research, reason)

**Trigger conditions:**
- Failed attempts >= 3 AND root cause unclear → True
- No lesson memory AND confidence < 0.3 → True
- Unknown/uncertain root cause after 2+ attempts → True
- Novel error pattern not in cache after 2+ attempts → True

#### `store_research_result(error_context, result)`

Stores research result for future pattern matching.

**Cache location:** `.cache/live_research/known_patterns.json`

---

## FELO FREE Integration

**IMPORTANT:** Live research uses FELO FREE as the primary search engine.

```python
# In _search_web():
try:
    from ilma_felo_free import native_search as felo_native_search
    search_result = felo_native_search(query, limit=5)
except ImportError:
    # Fallback to direct requests
    results = self._search_web_fallback(queries)
```

**FELO FREE Properties:**
- 100% FREE — no API key needed
- Uses: DuckDuckGo HTML + Wikipedia API
- Status: `ok` means success
- Results: `results` list with title, url, snippet

---

## Query Building

```python
def _build_queries(error_context, task_type, root_cause):
    # Extract key terms from error
    error_terms = re.findall(r'[A-Z][a-z]+Error|ModuleNotFoundError|...', error_context)
    
    # Build queries based on error type
    if 'ModuleNotFoundError' in error_context:
        match = re.search(r"No module named '([^']+)'", error_context)
        if match:
            module = match.group(1)
            queries.append(f"python {module} module not found install")
            queries.append(f"how to install {module} python")
    elif 'Permission' in error_context:
        queries.append(f"linux permission denied fix {task_type}")
    else:
        queries.append(f"{error_context[:80]}")
```

---

## SSL/Network Issues

Test environment has SSL certificate issues. Production notes:

| Provider | URL | SSL Status |
|----------|-----|------------|
| FELO FREE (DuckDuckGo + Wikipedia) | varies | ⚠️ May require `verify=False` |
| arXiv | `export.arxiv.org/api/query` | ✅ Works (but can timeout) |

**Note:** If SSL issues occur, FELO FREE falls back gracefully to direct requests.

---

## Integration Points

### 1. `ilma_reflection_engine.py` — `_generate_fix_plan()`

```python
# At end of _generate_fix_plan():
if len(plan) <= 2 and root_cause and ("unknown" in root_cause.lower() or "unclear" in root_cause.lower()):
    plan = self._enhance_with_live_research(plan, failures, root_cause)
```

### 2. `ilma_task_entrypoint.py` — post-reflection

```python
# After reflection.analyze():
root_cause_unclear = not refl_result.root_cause or "unknown" in refl_result.root_cause.lower()
if root_cause_unclear and iteration >= 2:
    research_result = lr.research(error_context, task_type, root_cause, iteration)
    # Add solutions to fix_plan
    refl_result.fix_plan.insert(0, f"📚 Live research suggests: {research_result.solutions[0][:100]}")
```

---

## Safety Properties

| Property | Implementation |
|----------|----------------|
| Non-fatal | All research failures caught with try/except |
| Timeout | `max_duration=30.0` default, per-source timeouts |
| Confidence scoring | `(solutions * 0.15) + (papers * 0.2) + (cache * 0.1)` |
| Deduplication | `dict.fromkeys()` preserves order, removes duplicates |
| Pattern cache | Stores results for future reuse |
| FELO FREE fallback | Falls back to direct requests if import fails |

---

## Testing

```bash
# Run standalone test
python3 scripts/ilma_live_research.py

# Run tests
python3 -m pytest tests/test_phase56_ilma_cli.py -v
python3 -m pytest tests/ -v -q
```

---

## Files Created/Modified

| File | Action |
|------|--------|
| `scripts/ilma_live_research.py` | CREATED — new LiveResearch class |
| `scripts/ilma_reflection_engine.py` | MODIFIED — added `_enhance_with_live_research()` |
| `scripts/ilma_task_entrypoint.py` | MODIFIED — added live research trigger |
| `scripts/ilma_felo_free.py` | ALREADY EXISTS — used as primary search |
| `skills/ilma-research/references/live-research-module.md` | UPDATED — FELO FREE integration |

---

## Documentation

- `docs/ILMA_PHASE57_LIVE_RESEARCH_ACTIVATION_2026-05-11.md` — Full report
- `skills/ilma-research/SKILL.md` — Main research skill