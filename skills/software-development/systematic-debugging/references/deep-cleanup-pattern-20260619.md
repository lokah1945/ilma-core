# Deep Cleanup Pattern — Deprecated Project Removal

**Date:** 2026-06-19 (validated end-to-end)
**Task:** Remove deprecated legacy proxy project (bridge-qwen, bridge-openaicodex, bridge-use, bridge-arena) completely from ILMA
**Result:** ~25 minutes, ~80 files/directories deleted/cleaned, ZERO active references remaining, profile size 6.3GB → 5.3GB

---

## Objective

Remove a deprecated subsystem completely from a large codebase. **No backward compatibility, no stubs, no legacy aliases.** Zero references remaining in active code, schema, config, data, docs, AND memory.

---

## When to Use

Use when:
- User says "hapus sama semua", "remove completely", "deep cleanup", "sampai ke akar-akarnya", "no backward compatibility"
- Deprecating a legacy subsystem (proxy, bridge, daemon)
- Disabling a feature flag and removing the underlying code
- Audit reveals dead code still referenced

Don't use when:
- Simple file deletion (no widespread references)
- Temporary disable (use feature flags instead)
- Refactoring that preserves functionality
- One-off typo fix

---

## Phase 1: Comprehensive Discovery (5 search patterns)

Run ALL of these — single pattern misses references:

```bash
# Pattern 1: Filename glob
find /root -type f -name "*target*" 2>/dev/null \
  | grep -v ".codex" | grep -v "node_modules" | head -100

# Pattern 2: Module/identifier grep across code+config+docs
grep -r "TargetClass\|target-provider\|target-sub" \
  /root/.hermes/profiles/ilma --include="*.py" --include="*.yaml" \
  --include="*.json" --include="*.md" 2>/dev/null

# Pattern 3: search_files tool for broader content
search_files(pattern="target", target="content", limit=100)
search_files(pattern="target", target="files", limit=100)

# Pattern 4: Session memory search
session_search(query="target removal legacy cleanup")

# Pattern 5: Memory files + session dumps
grep -r "target-provider" /root/.hermes/profiles/ilma/memories --include="*.json"

# Pattern 6 (specialized): Schema enum values
grep -r "target_source\|target_proxy" --include="*.json" /root/.hermes/profiles/ilma/sot/

# Pattern 7 (specialized): .git-rewrite/t/ staging
find . -path "*/.git-rewrite/t/*" -name "*target*" 2>/dev/null
```

### Discovery Result Categories (typical)

| Category | Count | Examples |
|----------|-------|----------|
| Active config | 5 | config_*.yaml, *_cache.yaml |
| Active code | 2-10 | orchestrator, registry, subagent_router |
| Schema | 3-5 | sot/schemas/*.schema.json enum values |
| Documentation | 10+ | README.md, SOUL.md, SOT_*.md |
| Backups | 50+ | /hermes_backup/*, /backup_archive/*, /backups/* |
| Fabric archives | 10+ | /fabric_archive/* (old attempt at cleanup) |
| Skills | 20+ | skills/.archive/, skills/*/references/ |
| Sessions | 2-5 | session_*.json (history — keep) |
| Telemetry | 1-3 | .learnings/LEARNINGS.md (large file with stale refs) |
| Duplicate folders | 1-2 | hermes_profile_<name>/ (full copy of active tree) |

---

## Phase 2: Categorization (CRITICAL — prevents over-deletion)

Split into three categories:

1. **ACTIVE** — runtime code, configs, cron jobs, registries, schemas, data files, memory
2. **HISTORICAL** — backup files, archive folders, session JSON, git history
3. **SEMANTIC** — substring appears in non-target context (see disambiguation table below)

### Semantic Disambiguation Table

| Surface term | NOT a target if used as... |
|--------------|----------------------------|
| "bridge" | song structure (`song.bridge = Verse`), CDP tech term (`DOM.resolveNode bridges JS`), writing ("bridge to next chapter"), idiom ("bridges the gap"), city name (Cambridge, UK), metaphor ("disk bridge"), subprocess pattern ("bridge subprocess") |
| "proxy" | design pattern (Proxy Pattern), HTTP proxy server, "indirect access" |
| "legacy" | literally any old code, not just the target |
| "deprecated" | runtime deprecation warnings, not target |

**Rule:** If a string appears N times in a file but the file's purpose is unrelated to the target (e.g. a music generator module using `bridge` for song structure), it's SEMANTIC, not ACTIVE. Patch only if rename is cheap.

### Categorization Heuristic Commands

```bash
# Active Python files (what loads at runtime)
grep -l "from target\|import target" --include="*.py" -r .

# Configuration files
grep -l "target_provider\|target:" --include="*.yaml" -r .

# Schema enums to patch
grep -l '"target_"' --include="*.json" -r sot/schemas/

# Backups (delete first)
find . -name "*.bak*" -o -name "*.backup_*" -o -name "*.deprecated"
```

---

## Phase 3: Execution — ORDER MATTERS

Follow this exact order. Reversing any pair causes work to be repeated:

1. **Backups first** — old backups re-introduce removed code if accidentally restored
2. **Schema/manifest before code** — prevents "no schema match" runtime errors
3. **Active code** — patch with clean replacements
4. **Duplicate folders** — `hermes_profile_<name>/` often contains full tree duplicates
5. **Data files (JSON/YAML)** — `benchmark_database.json`, `PROVIDER_INTELLIGENCE_MASTER.json`, etc.
6. **Docs/skills** — audit results live in skill references
7. **Memory** — explicit cleanup + mark historical

### Step 1 — Backups (delete first)

```bash
# Find and remove expired backups (>7 days old = safe to delete)
find backups/ -maxdepth 1 -type d -mtime +7 -exec rm -rf {} +
# Or remove specific dated folders
rm -rf backups/20260601_* backups/20260602_* ...
```

**Pitfall:** Don't delete `backups/` blindly — `.git-rewrite/t/` looks like a backup but is BFG Repo-Cleaner staging (see Pitfall 1).

### Step 2 — Schema enum removal

For each schema file with the target in an enum:

```diff
 {
   "type": "string",
   "enum": [
     "provider_direct",
-    "target_source",
-    "target_proxy",
     "manual"
   ]
 }
```

**Critical:** Validate JSON syntax after each patch (use `python3 -c "import json; json.load(open('file.json'))"`).

### Step 3 — Active code (clean deletion, NO stubs)

```python
# BEFORE (legacy compat stub — DON'T do this)
@property
def is_target_source(self) -> bool:
    """Legacy compat — removed."""
    return False  # ← still creates false sense of availability

def get_target_providers(self) -> List[ProviderInfo]:
    """Legacy stub — removed."""
    return []  # ← same problem

# AFTER (clean removal — delete the function entirely)
# (function deleted entirely)
# Also remove the parameter if exposed:
def get_top_models(self, task="general", limit=10, min_quality=0.0) -> List[ModelInfo]:
    # (bridge_only parameter removed from signature)
```

**Rule:** No `return False` stubs. No `return []` stubs. No "legacy compat" docstrings. **DELETE the symbol entirely.** Otherwise future agents read the stub and assume the feature exists.

### Step 4 — Duplicate folder detection

```bash
# Check if a duplicate "profile" folder exists
ls -la hermes_profile_<name>/ 2>/dev/null
# If yes: it's often a full tree duplicate. Diff vs root and rm -rf
diff -rq hermes_profile_<name>/ . | head -20
rm -rf hermes_profile_<name>/
```

### Step 5 — Data file cleanup (Python)

For large JSON data files, use a script to filter rather than manual edits:

```python
import json

with open('benchmark_database.json') as f:
    data = json.load(f)

# Pattern: remove matching keys from nested dicts/lists
def clean(obj):
    if isinstance(obj, dict):
        return {k: clean(v) for k, v in obj.items() if 'target' not in k.lower()}
    elif isinstance(obj, list):
        return [clean(x) for x in obj if not (isinstance(x, str) and 'target' in x.lower())]
    return obj

with open('benchmark_database.json', 'w') as f:
    json.dump(clean(data), f, indent=2)
```

**Note:** This preserves structure, only filters matching keys/values.

### Step 6 — Skills/Docs patch or delete

Two strategies based on file's role:

**A) Delete entirely** — if file is purely about the target:
- `skills/<name>/references/bridge-*.md`
- `skills/<name>/references/target-feature.md`
- `docs/PHASE_*_target*.md`

**B) Patch in place** — if file is a generic pattern that USED the target as example:
- Replace `target` → `deprecated_target` (or generic name) throughout
- Keep the file — it's still useful as a pattern document

```bash
# Find files with >5 target mentions (likely target-specific, delete)
for f in skills/*/references/*.md; do
  count=$(grep -c "target" "$f" 2>/dev/null || echo 0)
  [ "$count" -gt 5 ] && echo "DELETE: $f"
done

# Find files with 1-5 mentions (likely generic, patch)
for f in skills/*/references/*.md; do
  count=$(grep -c "target" "$f" 2>/dev/null || echo 0)
  [ "$count" -gt 0 ] && [ "$count" -le 5 ] && echo "PATCH: $f"
done
```

### Step 7 — Memory cleanup

```python
# Update memory entry: keep summary, mark as [HISTORICAL NOTE]
# BEFORE
SOT LIVE-ONLY (2026-06-18): ... **TARGET PROJECT FULLY REMOVED 2026-06-19**: Zero target-x reference. Deleted: ...

# AFTER
SOT LIVE-ONLY (2026-06-18, updated 2026-06-19): ... **TARGET PROJECT FULLY REMOVED 2026-06-19 [HISTORICAL NOTE]**: All target-x sub-components deleted. ...
```

The `[HISTORICAL NOTE]` prefix prevents the entry from being mistaken for active guidance.

---

## Phase 4: Verification (4 mandatory checks)

```bash
# 1. Active code search — should be ZERO except for semantic usages
grep -rln "target-x\|target_proxy\|target_sync" \
  --include="*.py" --include="*.json" --include="*.yaml" \
  --include="*.yml" --include="*.sh" --include="*.md" . 2>/dev/null \
  | grep -v ".git" | grep -v ".git-rewrite" | grep -v "sessions/" \
  | grep -v "node_modules" | grep -v "cron/output/"
# Expected: empty (or only files explicitly marked as historical)

# 2. Module compile check — every active module must import OK
python3 -c "
import sys; sys.path.insert(0, '.')
for m in ['module_a', 'module_b', 'module_c']:
    try: __import__(m); print(f'✅ {m}')
    except Exception as e: print(f'❌ {m}: {e}')
"

# 3. Status check — verify runtime boot is OK (or only pre-existing errors)
python3 ilma.py --status 2>&1 | grep -E "Ready:|Errors:|❌"

# 4. Wiring check — verify all modules still wire correctly
python3 ilma_runtime_wiring.py --verify 2>&1 | grep -E "OK|FAIL"
```

If any check fails → return to Phase 3, do NOT declare done.

---

## Phase 5: Commit & Push

```bash
git add -A
git commit -m "<TARGET> REMOVAL YYYY-MM-DD — comprehensive cleanup

Deleted:
- <list of deleted folders/files>

Patched:
- <list of patched files with one-line summary each>

Result:
- N/M active modules compile OK
- 0 <target> reference in active code
- Profile size: X → Y GB
- All routes direct API calls (no proxy)"

git push origin master
```

---

## Time Breakdown (validated 2026-06-19)

| Phase | Time | Notes |
|-------|------|-------|
| Discovery | 5 min | 5 search patterns run in parallel via search_files |
| Categorization | 2 min | Sort findings into ACTIVE/HISTORICAL/SEMANTIC |
| Schema patch | 2 min | 3-5 JSON schema files |
| Active code patch | 5 min | 2-10 Python files with imports + properties |
| Duplicate folders | 1 min | rm -rf hermes_profile_*/ |
| Data file cleanup | 2 min | Python script for benchmark_database.json |
| Skills/Docs patch or delete | 5 min | ~25 files, decide delete vs patch per file |
| Memory update | 1 min | Single memory entry mark |
| Verification | 3 min | 4 checks above |
| Commit + push | 1 min | |
| **Total** | **~25 min** | |

---

## Lessons Learned

### What Worked Well

✅ **5+ search patterns** — caught references missed by single patterns
✅ **Categorization before deletion** — separated active vs historical vs semantic
✅ **Order matters** — backups first, schemas before code
✅ **No backward compat stubs** — deleted symbols entirely, no `return False` shims
✅ **Generic-ification for skill docs** — `target` → `deprecated_target` kept useful patterns
✅ **Memory mark with `[HISTORICAL NOTE]`** — prevents future agents from treating it as active guidance
✅ **End-to-end verification** — 4 checks before declaring done

### Pitfalls Avoided

❌ **Don't just `rm *target*`** — Misses references in config files with different names
❌ **Don't skip backups** — Old backups re-introduce removed code if accidentally restored
❌ **Don't leave "might work" docs** — Documentation must clearly state feature is REMOVED
❌ **Don't check only Python files** — YAML configs, JSON data, and docs also contain references
❌ **Don't keep legacy compat stubs** — They create false sense of feature availability
❌ **Don't use `/new` to test** — wipes conversation; use `--status` instead
❌ **Don't delete `router_archive/` blindly** — see Pitfall 1 below

### Pitfall 1 — `.git-rewrite/t/` Is NOT a Backup Folder

**Symptom:** After deleting `router_archive/`, a previously-working module import now fails with `ModuleNotFoundError`.

**Root cause:** The `.git-rewrite/` directory is BFG Repo-Cleaner (or `git filter-repo`) staging area. Files inside `.git-rewrite/t/` look like archived files but may be the **only tracked copy** of a module — the original location in git history was rewritten but not yet `git-filter-branch`-ed into the working tree.

**Fix:**
```bash
# Check if a file is in .git-rewrite/t/ before declaring it archived
ls .git-rewrite/t/ilma_subagent_router.py  # ← may be the only copy!
git ls-files | grep ilma_subagent_router    # ← empty? then it's NOT in working tree
```

**Rule:** Before `rm -rf` any folder that LOOKS like an archive, verify with `git ls-files` that the real module lives elsewhere. If `git ls-files` returns empty for the module name, restore from `.git-rewrite/t/` to the working tree.

### Pitfall 2 — Semantic Strings Look Like Project Names

**Symptom:** After deletion, search finds 1752 mentions of "target" remaining in a single file. Looks like cleanup failed.

**Root cause:** The substring appears in unrelated contexts (song structure, English idioms, city names).

**Fix:** Use the Semantic Disambiguation Table to identify SEMANTIC usages and exclude from cleanup. Verify each remaining mention by reading the line:
```bash
grep "target" file.md | head -20  # read each line, decide if project-name or semantic
```

### Pitfall 3 — Schema Enum Removal Can Break Validation

**Symptom:** After removing target from schema enum, runtime fails with "value 'target' is not one of [...]".

**Root cause:** JSON Schema enums are validated at load time. If any data file still has a target value, validation fails.

**Fix:** Order matters — patch DATA FILES (Phase 3 step 5) BEFORE schemas (Phase 3 step 2). OR if you already patched schemas, re-run the data file cleanup script to remove matching values.

### Pitfall 4 — Duplicate Folders Hide Active Code

**Symptom:** After deleting `hermes_profile_<name>/`, modules that worked before now fail.

**Root cause:** The "profile" folder is a full tree duplicate from an old migration attempt. Some modules were symlinked or imported from there as a workaround.

**Fix:** Before deleting, diff the duplicate against root:
```bash
diff -rq hermes_profile_<name>/ . | head -30
# If duplicate has files that don't exist in root, check if they're imported elsewhere
grep -r "from hermes_profile" --include="*.py" . 2>/dev/null
```

### Pitfall 5 — Memory Entries Survive Forever

**Symptom:** After deleting all code, the memory entry still claims "TARGET PROJECT ACTIVE" because nothing cleaned the memory text.

**Root cause:** Memory is injected into every session. Stale entries create false guidance.

**Fix:** In Phase 7, explicitly update memory to mark the entry as `[HISTORICAL NOTE]`. Don't just delete — keep the audit trail but signal "this is history, not active guidance."

---

## Quick Reference Checklist

```
Discovery:
- [ ] 5 search patterns run (filename, content, search_files, session_search, memory)
- [ ] Findings categorized ACTIVE/HISTORICAL/SEMANTIC
- [ ] Semantic disambiguation table applied

Execution Order:
- [ ] Backups deleted FIRST (rm -rf old dated folders)
- [ ] Duplicate folders removed (hermes_profile_*/)
- [ ] Schema enums patched BEFORE data files
- [ ] Active code patched (no stubs, delete symbols entirely)
- [ ] Data files cleaned (Python script with nested filter)
- [ ] Skills/Docs: delete if target-specific, patch if generic example
- [ ] Memory entry marked [HISTORICAL NOTE]

Verification:
- [ ] Active code search: ZERO target references
- [ ] Module compile: N/N OK
- [ ] ilma.py --status: Ready (or only pre-existing errors)
- [ ] Wiring check: all modules OK
- [ ] Profile size reduced meaningfully

Commit:
- [ ] Single commit with full audit trail
- [ ] Pushed to GitHub
```
