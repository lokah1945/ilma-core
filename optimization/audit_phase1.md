# ILMA Optimization Audit - Phase 1

**Date:** May 13, 2026  
**Profile:** `/root/.hermes/profiles/ilma/`

---

## Summary of Findings

| Metric | Value |
|--------|-------|
| **Total Python Files** | 20,577 |
| **Large Files (>500KB)** | 3 |
| **Duplicate Script Basenames** | 2 (`core.py`, `__init__.py`) |
| **Empty Skill Directories** | 7 |
| **Stub Files (<5 lines)** | 20 |
| **Broken Symlinks** | 20+ |
| **Old Logs (>30 days)** | 0 |

---

## Detailed Findings

### 1. File Count
- **20,577** Python files found (excluding node_modules and .next)

### 2. Large Files (>500KB)
All located in cache/backup paths (not critical):
- `/root/.hermes/profiles/ilma/home/.cache/uv/archive-v0/tBaDrayf2uI30Jm8ii7Zt/pandas/core/frame.py`
- `/root/.hermes/profiles/ilma/backups/ilma_codex_primary_backup_20260511_1747/home/.cache/uv/archive-v0/.../pandas/core/frame.py`
- Nested backup duplicates of same

### 3. Duplicate Script Basenames
- `core.py` (appears in multiple directories)
- `__init__.py` (standard package marker, expected duplicates)

### 4. Empty Skill Directories (candidates for cleanup)
```
/root/.hermes/profiles/ilma/skills/ilma-felo-free/references
/root/.hermes/profiles/ilma/skills/ilma-benchmark
/root/.hermes/profiles/ilma/skills/ilma-actor-critic
/root/.hermes/profiles/ilma/skills/ilma-rcr-pattern
/root/.hermes/profiles/ilma/skills/ilma-reflexion
/root/.hermes/profiles/ilma/skills/ilma-mae
/root/.hermes/profiles/ilma/skills/ilma-trajectory-evolution
```

### 5. Stub Files (<5 lines) - 20 found
**Fabric observability/stubs (4 lines each):**
- `fabric/observability/execution_tracing.py`
- `fabric/observability/runtime_metrics.py`
- `fabric/observability/execution_heatmap.py`
- `fabric/observability/realtime_dashboard.py`
- `fabric/queue/realtime_stream_queue.py`
- `fabric/event_bus/internal_event_router.py`
- `fabric/event_bus/websocket_bus.py`
- `fabric/state_sync/execution_replay.py`
- `fabric/state_sync/graph_replication.py`
- `fabric/state_sync/distributed_memory_sync.py`

**Test project stubs (0-1 lines):**
- `test_projects/phase20_425file_codebase/backup_utils/__init__.py` (0 lines - empty!)
- `test_projects/phase20_425file_codebase/workflow_engine/workflow_*.py` (1 line each - 10 files)

### 6. Largest Directories
| Directory | Size |
|-----------|------|
| `backups/` | 5.8G |
| `home/` | 4.6G |
| `memory/` | 311M |
| `sessions/` | 258M |
| `dashboard/` | 113M |
| `test_projects/` | 36M |
| `skills/` | 17M |

### 7. Broken Symlinks (20 found)
All in `home/.openclaw/plugin-runtime-deps/openclaw-unknown-832331dd53e8/dist/` - these are stale plugin artifacts from a deleted/changed plugin version.

### 8. Old Logs
- **0** log files older than 30 days (clean)

---

## Optimization Opportunities Identified

### High Priority
1. **Broken symlinks** - 20 stale symlinks in openclaw plugin cache
2. **Empty skill directories** - 7 skill dirs with no content
3. **Stub files** - 20 nearly-empty Python files in fabric and test_projects

### Medium Priority
4. **Redundant pandas cache** - Multiple copies of pandas/core/frame.py in backups
5. **Large backups directory** - 5.8GB backup directory may contain obsolete snapshots

### Low Priority
6. **Duplicate script basenames** - Normal for Python packages (__init__.py) but core.py may warrant review

---

## Next Steps
- Phase 2: Remove broken symlinks and empty directories
- Phase 3: Audit stub files for content or deletion
- Phase 4: Analyze backup necessity and prune old snapshots