# Phase 69D Audit — Hermes Native Browser Click Humanization Gap

**Date:** 2026-06-01
**Status:** Gap confirmed — NOT YET PATCHED

---

## Summary

Phase 69 established that ILMA's custom Playwright browser runtime (CDP at `http://127.0.0.1:9222`, `ilma-chrome@lokah2150.service`, persistent profile at `/root/user-data/lokah2150`) is fully operational and serves as the default browser backend for Hermes/ILMA.

The claim that "ALL browser interactions use HumanInteractionAdapter by default" is **not yet fully proven** for Hermes native browser tools.

---

## Phase Status

| Phase | Component | Status |
|-------|-----------|--------|
| 69A | Custom Playwright/CDP runtime at `http://127.0.0.1:9222` | ✅ PASS |
| 69B | Per-profile persistent context isolation | ✅ PASS |
| 69C | Python `BrowserEngine.human_click()` via `HumanInteractionAdapter` | ✅ PASS |
| 69D | Hermes native `browser_click` → `HumanInteractionAdapter` | ❌ NOT YET PROVEN |

---

## Code Path: GAP

```
browser_click("@e2") [browser_tool.py:2557]
  → _run_browser_command(task_id, "click", ["@e2"]) [browser_tool.py:2578]
      → agent-browser --cdp <ws_url> --json click @e2 [browser_tool.py:1973-1976]
          ↑ CLI subprocess, raw CDP mouse.click — NEVER touches HumanInteractionAdapter
```

**What works (ILMA Python scripts):**
```
SyncBrowserEngine.click() → await self.human.human_click(locator) → HumanInteractionAdapter ✅
```

**Root cause:** `browser_tool.py`'s `browser_click()` uses `agent-browser` CLI as execution engine. The CLI connects to the correct CDP endpoint but uses raw CDP mouse commands, not HumanInteractionAdapter.

---

## Required Patch

**Option A (preferred):** Patch `browser_click()` in `browser_tool.py` to route through `HumanInteractionAdapter` when CDP URL is `http://127.0.0.1:9222`.

**Option B:** Disable raw Hermes browser tools for ILMA profile. Force all workflows to use `execute_code` with `SyncBrowserEngine` (has humanized interactions built-in).

---

## Acceptance Test

After patch, calling `browser_click("@e2")` from Hermes chat should produce log:
```
[human-browser] resolve_ref @e2
[human-browser] scroll_into_view
[human-browser] mouse_move
[human-browser] hover
[human-browser] click
```

If only raw CDP log appears → patch not applied.

---

## Workaround

Use ILMA Python engine directly for critical interactions:
```python
import sys
sys.path.insert(0, '/root/.hermes/profiles/ilma/scripts')
from ilma_browser_engine import SyncBrowserEngine

with SyncBrowserEngine(stealth=True, cdp=True,
    persistent_user_data_dir="/root/user-data/lokah2150") as browser:
    await browser.page.locator("@e2").click()  # → humanized via HumanInteractionAdapter
```

---

## Related

- `/root/.hermes/hermes-agent/tools/browser_tool.py` — Hermes native browser tools (GAP here)
- `/root/.hermes/profiles/ilma/scripts/ilma_browser_engine.py` — ILMA canonical engine (works ✅)
- `/root/.hermes/profiles/ilma/scripts/ilma_human_interaction.py` — HumanInteractionAdapter (works ✅)
- `/root/.hermes/profiles/ilma/skills/ilma-browser-unified/SKILL.md` — Full Phase 69D section in SKILL.md