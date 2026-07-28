---
name: ilma-system-optimizer-workflow
description: System optimization workflow - detect and replace fake/stub modules with production-ready code. SSS Tier 3.
tags:
  - system-optimization
  - stub-detection
  - fabric-modules
triggers:
  - "optimize system"
  - "fix fake modules"
  - "replace stubs"
  - "system audit"
---

# ILMA System Optimizer Workflow

## Problem Statement

When auditing a system (like ILMA), many files may appear to exist but are actually **fake/stub implementations** OR **unused duplicate modules** that waste space and cause benchmarks to overcount.

**TWO DISTINCT PROBLEMS:**

### Problem A: Fake/Stub Files
Files with minimal code (e.g., 6-20 lines) that are never used.
```python
# Example: 6-line stub
"""ILMA Worker 1 - Additional worker component."""
class Worker1:
    def __init__(self):
        self.id = "worker_1"
```

### Problem B: Duplicate/Unused Modules
Files that have real code but are NOT used by the system runtime. These were often copied from source systems (like AYDA) but never integrated.

**Example:** 20 `fabric_module_*.py` files existed in ILMA but:
- They were ~100 lines each (not stubs)
- They were NOT imported or used anywhere in ILMA runtime
- They duplicated functionality already in other files
- **Correct action: DELETE entirely, not replace**

---

## Solution Pattern

### Decision Tree: Replace vs Delete

```
Is the module being imported/used in runtime?
├── YES → Is it a stub (<20 lines, no real functionality)?
│   ├── YES → Replace with production implementation
│   └── NO → Keep as-is, verify it's production-ready
└── NO → Is it a duplicate of another file?
    ├── YES → DELETE (save space, reduce confusion)
    └── NO → Is it potentially useful?
        ├── YES → Keep with note about non-usage
        └── NO → DELETE
```

### Step 1: Detect Unused/Duplicate Files
```bash
# Find files NOT imported anywhere
cd /root/.hermes/profiles/ilma
grep -r "import.*fabric_module" . --include="*.py" | grep -v ".home" | wc -l

# Find potential duplicates (same size, similar names)
find . -name "ilma_*.py" -exec basename {} \; | sort | uniq -d

# Count all root ilma_*.py files
ls -la ilma_*.py | wc -l
```

### Step 2: Check Runtime Usage
```bash
# Is fabric_module actually used?
grep -r "fabric_module" . --include="*.py" | grep -v "home" | grep -v "__pycache__"

# Is scripts/ilma_*.py used?
grep -r "scripts/ilma_knowledge" ilma_*.py 2>/dev/null
```

### Step 3: Decision Making

**For FABRIC PLACEHOLDERS (not used in runtime):**
```bash
cd /root/.hermes/profiles/ilma/fabric/workers
rm -v fabric_module_*.py
```

**For ROOT DUPLICATES (duplicated in scripts/):**
```bash
cd /root/.hermes/profiles/ilma
# Keep canonical version in root, delete from scripts/
rm -v scripts/ilma_knowledge_graph.py scripts/ilma_learning_engine.py
```

### Step 4: Verify System Still Works
```bash
cd /root/.hermes/profiles/ilma
python3 ilma_complete_system.py 2>&1 | grep -E "FUSION|SCORE|Success"
```

Expected: FUSION SCORE 100.0% (system still works after cleanup)

---

## ILMA v3.0 Optimization Case Study

### Before Optimization
| Category | Count |
|----------|-------|
| Root ilma_*.py | 17 |
| Scripts | 278+ |
| Fabric modules | 20 placeholder |
| Cron duplicates | 15+ |

### Actions Taken
1. **DELETED** 20 fabric_module_*.py (not used in runtime)
2. **DELETED** 5 root duplicates (ilma_system_fusion, ilma_unified_system, ilma_orchestrator, ilma_router, ilma_capability_orchestrator)
3. **DELETED** 38+ scripts duplicates (cron, auto, self, vector, analytics, cloud)
4. **KEPT** all production-ready files with unique functionality

### After Optimization
| Category | Count |
|----------|-------|
| Root ilma_*.py | 12 (AYDA canonical) |
| Scripts | 240 (unique utilities) |
| Fabric modules | 9 (real workers) |
| Cron scripts | 7 (minimal set) |

### Result
- ✅ **65+ files removed**
- ✅ **FUSION SCORE: 100.0%** (system still fully functional)
- ✅ **No functionality lost**
- ✅ **No duplicates remaining**

---

## Anti-Patterns

❌ **Don't delete everything "unused"** - Some files are unused but may be needed
❌ **Don't assume "real code" means "used"** - Files can have 100+ lines but never be imported
❌ **Don't delete before verifying** - Always check if module is actually used in runtime
❌ **Don't replace with more code** - Sometimes DELETE is better than REPLACE

## Verification Commands

```bash
# Verify system still works after cleanup
python3 ilma_complete_system.py

# Count files after cleanup
find . -name "ilma_*.py" -not -path "./.home/*" | wc -l
find ./scripts -name "ilma_*.py" | wc -l

# Check for remaining duplicates
find . -name "ilma_*.py" -exec basename {} \; | sort | uniq -d
```

## Runtime Bug Detection (v3.1 — e2e-optimization 2026-06-29)

Beyond stub/duplicate detection, end-to-end audits must also catch **runtime bugs** that look healthy on import but crash on first use.

> Re-runnable AST audit script: `scripts/audit_os_imports.py` (catches B1 + B2 below)
> Session transcript: `references/session-2026-06-29-e2e-optimization.md` (10-bug case study)


### Bug Class B1: Missing stdlib import

Files use `os.environ.*` etc. without importing `os`. Surfaces as `NameError: name 'os' is not defined` deep inside code paths that only trigger on cold-start.

```python
# ❌ BAD
def get_mongo():
    password = os.environ.get("MONGO_PASS")
    return MongoClient(password=password)

# ✅ GOOD
import os

def get_mongo():
    password = os.environ.get("MONGO_PASS", "")
    return MongoClient(password=password)
```

**Detection recipe (AST-based):**
```python
import ast, os
bad = []
for path in walk_python_files(skip={'archive', 'fabric_archive', '__pycache__'}):
    src = open(path).read(); tree = ast.parse(src)
    top_imports = {n.module if isinstance(n, ast.ImportFrom) else a.name
                   for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))
                   for a in (n.names if isinstance(n, ast.Import) else [n])}
    if any(s in src for s in ('os.environ', 'os.path', 'os.getpid', 'os.replace')) \
       and 'os' not in top_imports:
        bad.append(path)
```

### Bug Class B2: Missing default in `os.environ.get()`
```python
# ❌ returns str | None — fails type-checker; MongoDB saslprep crashes on empty
password: str = os.environ.get("MONGO_PASS")
# ✅
password: str = os.environ.get("MONGO_PASS", "")
```

### Bug Class B3: Empty-credential auth crash
`pymongo.saslprep()` raises `IndexError: string index out of range` on empty password. **Always skip auth kwargs when both username AND password are empty** — many local MongoDBs run no-auth (`mongosh --eval 'db.runCommand({connectionStatus:1})'` shows `authenticatedUsers: []`).

```python
conn = {}
if username and password:
    conn.update(username=username, password=password, authSource="admin")
MongoClient(host=host, port=port, **conn)
```

### Bug Class B4: Service unit missing from systemd
Wrapper/helpers may have `*.service` unit files in their working directory but never be registered with systemd. They look healthy in `ls` but refuse connections silently (port-down). Code is fine — registration is the gap.

**Detection recipe:**
```bash
# 1. List unit files in working dirs
ls /root/wrapper/*/*.service 2>/dev/null

# 2. Check what's actually registered
systemctl --user list-units --type=service --no-pager | grep <name>
sudo -n systemctl list-unit-files | grep <name>

# 3. Probe ports as E2E truth (more reliable than service status)
for port in 9100 9102 9103 9104; do
  curl -s --max-time 3 http://127.0.0.1:$port/health || echo "port $port DOWN"
done
```

**Fix recipe:**
```bash
sudo -n cp /root/wrapper/<name>/<name>.service /etc/systemd/system/
sudo -n systemctl daemon-reload
sudo -n systemctl enable <name>.service
sudo -n systemctl start <name>.service
sleep 2 && curl -s --max-time 3 http://127.0.0.1:<port>/health  # verify
```

### Bug Class B5: Duplicate copies of the same module (root ↔ scripts/)
Same `md5sum` for root and `scripts/` copy. Routing layer may import one path while orchestrator imports another. Confusing — both look identical, one shadow hides file changes.

**Detection:**
```bash
md5sum ilma_<name>.py scripts/ilma_<name>.py   # Same hash → dup
# Decide canonical: whichever is in `ilma_orphan_wiring`'s IMPORTS / PURPOSES,
# OR whichever is imported from main runtime files (ilma.py, ilma_actor_critic_core.py).
```

**Fix:** Keep canonical, delete the other. If a test script does `sys.path.insert(.../scripts); import X`, change to the canonical path or remove `sys.path.insert` entirely.

### End-to-End Audit Recipe (P1-P5)

```bash
# P1 — Boot (catches wiring errors fast)
python3 ilma.py --status

# P2 — Wiring integrity
python3 ilma_runtime_wiring.py --verify    # expect ok=N missing=0 import_error=0

# P3 — Orphan wiring
python3 ilma_orphan_wiring.py --verify     # expect N/N OK

# P4 — Bug sweep (missing stdlib imports)
python3 -c "<insert B1 AST recipe above>"

# P5 — Syntax sweep
python3 -c "
import ast, os
errs = []
for root, _, files in os.walk('.'):
    if any(s in root for s in ('.git', '__pycache__', 'archive')): continue
    for f in files:
        if not f.endswith('.py'): continue
        try: ast.parse(open(os.path.join(root, f)).read())
        except SyntaxError as e: errs.append((f, str(e)))
print('Syntax errors:', len(errs))
"

# P6 — Real E2E test (writes go through router)
python3 -c "
from ilma_subagent_router import SubAgentRouter
r = SubAgentRouter()
d = r.route('write hello', thinking='off', allow_paid=False)
print('model:', d.model, 'reason:', d.reasoning[:80])
"
```

**Expected after full audit:**
- `ilma.py --status` → `Ready: ✅` (not ⚠️)
- `ilma_runtime_wiring` → `ok=37 missing=0 import_error=0`
- `ilma_orphan_wiring` → 21/21 OK
- P4 returns 0 files
- P5 returns 0 syntax errors
- P6 returns real model with reasoning string

## Outcome

After applying this pattern to ILMA v3.0 + v3.1:

After applying this pattern to ILMA v3.0:
- Removed 65+ duplicate/unused files
- System still functions at 100% FUSION SCORE
- Cleaner architecture (12 canonical + 240 utilities)
- No functionality lost

---

## Service Teardown (running systemd --user services)

When the deletion target is a **running service** (not just an unused code file), the
delete step must defeat `Restart=always` and unregister the unit, or the process
respawns on next boot / after a crash. This is the teardown half of the optimizer
loop — complementary to the stub/duplicate detection above.

### Safe teardown sequence (defeats auto-restart)
```bash
SVC=ilma-dashboard-backend.service
PORT=8000

# 1. Disable — removes symlink in default.target.wants, kills boot auto-start
systemctl --user disable "$SVC"

# 2. Stop
systemctl --user stop "$SVC"

# 3. Kill any lingering proc still bound to the port (disable+stop can race)
for p in $(ss -tlnp 2>/dev/null | grep ":$PORT" | grep -oP 'pid=\K[0-9]+' | sort -u); do
  kill -9 "$p"
done

# 4. Remove the unit file (check both user + system dirs)
rm -f ~/.config/systemd/user/"$SVC" /etc/systemd/system/"$SVC"

# 5. Reload
systemctl --user daemon-reload

# 6. Remove code/data dir
rm -rf /path/to/component

# 7. Verify port FREE + unit GONE
ss -tlnp 2>/dev/null | grep ":$PORT" || echo "PORT FREE"
systemctl --user list-units --all 2>/dev/null | grep -i dashboard || echo "no unit"
```
A re-runnable version lives at `scripts/teardown-systemd-service.sh`.

### Pitfall T1: Shared DB / shared resource
A DB file or data dir may be referenced by OTHER modules you are NOT deleting.
Before `rm -rf` or `rm data/x.db`:
```bash
# Find every file that references the resource path
grep -rIl 'data/ilma_dashboard.db' --include='*.py' --include='*.json' . 2>/dev/null
```
If matches exist outside the component being deleted:
- Check whether the *running* service that references it uses a **different** path
  (read its code / `systemctl show <svc> -p ExecStart`). Different path ⇒ safe to delete.
- Check whether the referencing module **guards** the missing file
  (`if DASHBOARD_DB.exists():`) — if so it degrades gracefully, no crash.
- If a module would hard-crash on the missing file, either KEEP the DB or PATCH the
  module to skip-when-missing. Do NOT leave a broken import/reference behind.
- Real example (2026-07-28): `ilma_dashboard.db` was shared by
  `ilma_model_registry.py`, `ilma_kanban_free_model_optimizer.py`,
  `ilma_wrapper_nvidia_dashboard_sync.py`. The active `wrapper-model-registry.service`
  used a DIFFERENT db (`/root/wrapper/.../registry-state.db`), so deletion was safe;
  `ilma_kanban_free_model_optimizer.py` had an `if exists()` guard; only
  `ilma_model_registry.py` lacked a guard and was flagged for a follow-up patch.

### Pitfall T2: Name collision / scope discipline
A name like "dashboard" or a port like "3000" matches MULTIPLE unrelated components.
Before deleting:
- `ss -tlnp | grep ':3000'` → read `pid=`, then `cat /proc/<pid>/cmdline` +
  `readlink /proc/<pid>/cwd` to confirm WHICH component owns it.
- `grep` the port number across skills/configs — `vps_project.json` may mention
  "3000" for a *different* blog project; `ilma-dashboard-design` skill is generic
  design, NOT the observability dashboard.
- Only delete what the audit proves belongs to the target.

### Pitfall T3: Orphan import check
Before deleting a `.py` module, confirm no other module imports it:
```bash
grep -rn "import module_name\|from module_name" --include='*.py' . | grep -v __pycache__
```
0 matches ⇒ safe to delete. >0 matches ⇒ those importers break; keep or migrate first.

### Keep vs delete boundary (worked example, 2026-07-28)
- `ilma_super_coding_command_center.py` did NOT import the deleted
  `command_center_core.py` ⇒ kept as a separate tool.
- `ilma-command-center` skill dir + evidence JSON + log ⇒ deleted (part of component).
- Running services sharing a port *class* but different numbers (command-center on
  18790, not 3000/8000) ⇒ untouched.

## Full-Filesystem Redundancy Sweep (whole-tree, not single component)

When the task is "clean up redundant ILMA/AYDA/ClawHub files scattered under /root", do
NOT grep-and-delete blindly. A bare `find /root -iname '*ilma*'` returns 10k–15k hits;
~90% live inside `/root/backup/` (legitimate rollback). Use a classify-then-delete
pipeline. **For clearly-scoped "remove redundant junk" requests, proceed with this
classification (keep rollback dirs) — do not over-confirm each bucket. Only clarify
when a bucket is genuinely ambiguous (mixed backup + historical).**

### Scan recipe (exclude known-good roots)
```bash
# Loose redundant set = every ilma* EXCEPT active profile, skills, plugins, wrapper, backups
find /root -iname '*ilma*' 2>/dev/null \
  | grep -vE '/\.hermes/profiles/ilma/|/\.hermes/skills/|/\.hermes/plugins/|/wrapper/|/wrapper_remote.git/|node_modules/'
```

### Distribution triage (find the big buckets fast)
```bash
find /root -iname '*ilma*' 2>/dev/null | grep -vE 'EXCLUDE_ABOVE' \
  | sed 's|/[^/]*$||' | sort | uniq -c | sort -rn | head -25
```
Real example (2026-07-28): surfaced `/root/.hermes/profiles/ilma_test/` holding
1,209 of 1,209 residual items (4.2 GB duplicate profile) — the single biggest win.

### Classification buckets
| Bucket | Action |
|--------|--------|
| `/root/backup/`, `/root/backups/`, `/root/backup_archive/`, `/root/ilma_reset_backup/`, `/root/ilma_sot_audit_backup/`, `*.tar.gz` | **KEEP** — rollback point |
| Duplicate profile `/root/.hermes/profiles/ilma_test/` | **DELETE** if no systemd unit + no running process + not referenced by active profile runtime |
| Loose `test_*.py/sh/js/json`, `update_*.py` (AYDA-era provider scripts) | **DELETE** — orphan scratch |
| `/root/.deprecated/`, `/root/__pycache__/`, `/root/.pytest_cache/` | **DELETE** — deprecated / regenerable |
| `/root/clawhub_data/`, `*.bak.ayda-removal*` | **DELETE** — OpenClaw/AYDA leftovers |
| `/root/ilma_audit_reports/`, `/root/konsep/`, `/root/upload/`, `/root/.ilma/`, `/root/hermes_ilma/`, `/root/shared-memory/` | **DELETE** if not referenced by active profile |
| Active systemd units (`hermes-gateway-ilma`, `ilma-chrome`, `ilma-sot-sync`, `ilma-sync-*`) | **KEEP** |
| Other Hermes profiles (`master-chief`), `hermes-agent` venv/git, browser watchdog | **KEEP** — not ILMA-redundant |

### Verify a duplicate profile is safe to delete
```bash
SVC=ilma_test
systemctl --user list-units --all 2>/dev/null | grep -i "$SVC" || echo "no unit"
ps aux 2>/dev/null | grep -i "$SVC" | grep -v grep || echo "no process"
grep -rIl "$SVC" /root/.hermes/profiles/ilma/ 2>/dev/null | head -3 || echo "not referenced"
```

### Pitfall F1: Backup dominance
90% of `ilma*` hits are inside `backup*/`. Never `rm -rf` a backup dir on a loose
"clean up ilma files" request. Confirm whether rollback points may go (default: KEEP).

### Pitfall F2: Other-profile false positives
`master-chief` profile and `hermes-agent` repo also contain `ilma*` strings (skill
references, git remote `ilma-core`). Exclude them — deleting breaks a different agent.

### Pitfall F3: Loose-file reference check
Before `rm` a loose `/root/ilma_*.py`, confirm 0 importers in the active profile:
```bash
base=$(basename "$f" .py)
grep -rl "\b$base\b" /root/.hermes/profiles/ilma/*.py /root/.hermes/profiles/ilma/scripts/*.py 2>/dev/null
```
0 hits ⇒ orphan ⇒ safe delete. Real example: 9 of 10 loose `/root/ilma_*.py` were
orphans; `ilma_intelligence_core.py` had an importer ⇒ KEPT.

Session transcript: `references/session-2026-07-28-filesystem-cleanup.md`

## Related Skills

- `ilma-self-improve` - Continuous improvement
- `ilma-performance-optimizer` - Performance optimization
- `ilma-evolution` - System evolution patterns
- `safe-runtime-patching` - sibling: patch (not delete) a running daemon safely
