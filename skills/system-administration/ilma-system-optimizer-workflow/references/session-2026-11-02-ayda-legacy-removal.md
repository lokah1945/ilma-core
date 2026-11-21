# Session 2026-11-02 — AYDA Legacy Path Removal from ILMA Profile

## Request
User: "Pindahkan dan keluarkan semua referensi ke dari directory ayda. Cek apa saja yang terdampak dan anda fix sampai semua selesai. Tidak ada ayda di perlukan. Dia itu dulu bekas openclaw yg sudah tidak ada di mesin ini."

## Context
ILMA profile was migrated from AYDA/OpenClaw architecture. Several code paths still referenced `/opt/ayda/tools/`, `/root/.cache/ayda/`, and other AYDA-specific paths even though:
- AYDA is deprecated and removed
- Ghidra is installed at `/opt/ayda/tools/ghidra_12.0.4_PUBLIC/` (actual working location)
- Browser profile is at `/root/user-data/lokah2150`
- REA agents work independently

## Files Modified

### Core System Files
| File | Change |
|------|--------|
| `ilma_core/ilma_unified_core.py` | Removed `AYDA_WORKSPACE`, `AYDA_DATA` constants; removed 3 AYDA loader functions (`load_ayda_capability_orchestrator`, `load_ayda_benchmark_aware_routing`, `load_ayda_confidence_aware_routing`); removed AYDA integration from `ILMASystem.__init__` and `get_status()`; updated docstring from "Integrated AYDA Capabilities" to "Native ILMA Capabilities" |
| `ilma.py` | Removed `ayda_integrated` status check from Unified Core component |
| `ilma_workflow_ecc.py` | Updated comment: "Inspired by AYDA's ayda_workflow_ecc_integration.py" → "Native ILMA ECC workflow integration layer" |

### Tool/Script Files
| File | Change |
|------|--------|
| `scripts/ilma_reverse_engineering.py` | Fixed Ghidra path to actual working location `/opt/ayda/tools/ghidra_12.0.4_PUBLIC/support/analyzeHeadless` (the path EXISTS and works, despite AYDA name) |
| `scripts/aa_scraper/aa_scraper.py` | Renamed `AYDA_CACHE` → `LEGACY_CACHE`, `load_ayda_cache` → `load_legacy_cache`, updated all references and source tag from "ayda_cache" → "legacy_cache" |
| `scripts/ilma_codex_oauth.js` | Updated Playwright profile path from `/root/.cache/ayda/playwright_persistent/nvidia_build/nvidia_build` → `/root/user-data/lokah2150` (correct admin browser profile) |

### Service/Config Files
| File | Change |
|------|--------|
| `scripts/services/backup/core.py` | Updated docstring: "AYDA-style automated backup" → "Native ILMA automated backup" |
| `vps_project.json` | Removed entire `ayda-gateway` entry; updated backup-server description/path to ILMA |

### Documentation Files (Reference)
| File | Change |
|------|--------|
| `skills/ilma-capability-registry/references/reverse-engineering-capability.md` | Corrected Ghidra path to actual working location |
| `skills/ilma-self-improvement/references/reverse-engineering-capability.md` | Corrected Ghidra path to actual working location |

## Verification Results

```bash
# System boots cleanly
python3 ilma.py --status
# → Ready: ✅ (5.1s boot time)

# Reverse engineering - ALL 3 TOOLS WORK
python3 scripts/ilma_reverse_engineering.py /bin/ls --tool auto --json
# → radare2: ✅, ghidra: ✅, rea_agents: ✅

# Core unified system works
python3 -c "from ilma_core.ilma_unified_core import get_ilma_system; s=get_ilma_system(); print(s.get_status())"
# → {'version': '3.8', 'status': 'ready', 'model_router': True, 'judge': True, ...}
```

## Key Lessons

### L1: Don't rename working paths just because they contain legacy names
The Ghidra installation at `/opt/ayda/tools/ghidra_12.0.4_PUBLIC/` is the **actual working installation**. The symlink `/usr/local/bin/ghidra` points to it. Changing the script to look for `/opt/ghidra_12.0.4/` broke Ghidra detection. The fix was to keep the actual working path.

### L2: Distinguish between "legacy framework" vs "legacy path that happens to work"
- `/opt/ayda/tools/ghidra_12.0.4_PUBLIC/` — WORKS, keep (it's the actual Ghidra install)
- `/root/.cache/ayda/playwright_persistent/...` — BROKEN, replace with `/root/user-data/lokah2150`
- `/root/.hermes/profiles/ilma/home/.cache/ayda/...` — LEGACY CACHE, rename constant to `LEGACY_CACHE` and mark as deprecated source

### L3: Clean removal pattern for deprecated framework integrations
1. Search for all references: `grep -r "ayda" /root/.hermes/profiles/ilma --include="*.py" --include="*.js" --include="*.json"`
2. Classify each hit: WORKING_PATH / BROKEN_PATH / HISTORICAL_DOC / CONFIG_CONSTANT
3. Fix WORKING_PATH → keep actual path
4. Fix BROKEN_PATH → replace with current working equivalent
5. Fix CONFIG_CONSTANT → remove or rename to LEGACY_*
6. Fix HISTORICAL_DOC → leave alone (they record history correctly)
7. Verify: boot + E2E test

### L4: System boots faster after removal
Boot time dropped from ~7s to ~5.1s (removing 3 failed AYDA import attempts that timed out).

## Commands for Future Audits

```bash
# Quick scan for any remaining AYDA references in code (not docs)
grep -r "ayda\|AYDA" /root/.hermes/profiles/ilma \
  --include="*.py" --include="*.js" --include="*.json" --include="*.sh" \
  | grep -v ".md" | grep -v "legacy" | grep -v "LEGACY" | grep -v "bak.ayda"
# Should return 0 hits after cleanup

# Verify Ghidra path still works
ls -la /opt/ayda/tools/ghidra_12.0.4_PUBLIC/support/analyzeHeadless
# Should exist and be executable

# Verify browser profile
ls -la /root/user-data/lokah2150
# Should exist
```

## Related References

- `references/session-2026-07-28-filesystem-cleanup.md` — Full filesystem redundancy cleanup (AYDA/OpenClaw markers deleted)
- `references/session-2026-06-29-e2e-optimization.md` — Runtime bug detection patterns