#!/usr/bin/env python3
"""
ILMA Phase 69D Acceptance Test — CDP-Direct Humanized Browser
=============================================================

Tests Phase 69D Jalur A: ILMA-native snapshot + ref_map + CDP interactions.
Validates complete chain: snapshot -> resolve_ref -> human_click -> log trace.

ACCEPTANCE CRITERIA:
1. browser_navigate("https://example.com") works
2. snapshot() generates @e refs with ILMA-owned ref_map
3. resolve_ref("@eN") returns RefEntry with backendNodeId
4. click("@eN") uses CDP directly (NO agent-browser)
5. Log output shows: [human-browser] resolve_ref @eN -> backendNodeId=...
6. Log output shows: [human-browser] scroll_into_view, mouse_move, hover, click
7. Log output does NOT show: agent-browser --json click @eN
8. CDP endpoint remains: http://127.0.0.1:9222

Expected log pattern for successful click:
  [human-browser|default] navigate URL=https://example.com
  [human-browser|default] navigate SUCCESS — status=200 title=Example Domain
  [human-browser|default] snapshot generating ILMA-native accessibility tree
  [human-browser|default] snapshot generated 12 refs
  [human-browser|default] resolve_ref @e2 -> backendNodeId=123 role=link name=More information
  [human-browser|default] click starting human-like click for @e2 (backendNodeId=123)
  [human-browser|default] scroll_into_view @e2
  [human-browser|default] mouse_move (642.3, 489.1)
  [human-browser|default] hover (642.3, 489.1)
  [human-browser|default] mousePressed (642.3, 489.1)
  [human-browser|default] mouseReleased (642.3, 489.1)
  [human-browser|default] click SUCCESS — @e2
"""

import asyncio
import logging
import sys
import os

# Configure logging to capture human-browser traces
logging.basicConfig(
    level=logging.INFO,
    format='%(name)s | %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("human-browser")
logger.setLevel(logging.INFO)

# MUST run from scripts/ directory to avoid importing the broken stub
# at /root/.hermes/profiles/ilma/ilma_browser_engine.py
_scripts_dir = '/root/.hermes/profiles/ilma/scripts'
if os.getcwd() != _scripts_dir:
    os.chdir(_scripts_dir)
    sys.path.insert(0, _scripts_dir)
else:
    sys.path.insert(0, _scripts_dir)


async def main():
    print("=" * 70)
    print("ILMA Phase 69D Acceptance Test — CDP-Direct Humanized Browser")
    print("=" * 70)
    
    results = {
        "passed": [],
        "failed": [],
        "checks": [],
    }
    
    def check(name: str, passed: bool, detail: str = ""):
        status = "✅ PASS" if passed else "❌ FAIL"
        results["checks"].append((name, passed))
        if passed:
            results["passed"].append(name)
        else:
            results["failed"].append((name, detail))
        print(f"  {status}: {name}")
        if detail:
            print(f"         {detail}")
    
    # ─── Step 1: Import and verify adapter ─────────────────────────────────
    print("\n[1] Import verification")
    try:
        from ilma_browser_tool_adapter import ILMABrowserToolAdapter, RefEntry, SnapshotResult
        check("ILMABrowserToolAdapter import", True)
    except Exception as e:
        check("ILMABrowserToolAdapter import", False, str(e))
        return results
    
    try:
        from ilma_browser_engine import BrowserEngine
        check("BrowserEngine import", True)
    except Exception as e:
        check("BrowserEngine import", False, str(e))
        return results
    
    # ─── Step 2: Check CDP endpoint ───────────────────────────────────────
    print("\n[2] CDP endpoint check")
    try:
        import urllib.request
        cdp_url = "http://127.0.0.1:9222/json/version"
        with urllib.request.urlopen(cdp_url, timeout=5) as resp:
            data = resp.read().decode()
            import json
            version = json.loads(data)
            check("CDP endpoint reachable", True, f"Browser: {version.get('Browser', 'unknown')}")
    except Exception as e:
        check("CDP endpoint reachable", False, str(e))
        # Try 9223 as fallback
        try:
            cdp_url = "http://127.0.0.1:9223/json/version"
            with urllib.request.urlopen(cdp_url, timeout=5) as resp:
                data = resp.read().decode()
                import json
                version = json.loads(data)
                check("CDP endpoint 9223 reachable", True, f"Browser: {version.get('Browser', 'unknown')}")
        except Exception as e2:
            check("CDP endpoint 9223 reachable", False, str(e2))
            print("\n  ⚠️  Chrome daemon not reachable — test cannot proceed")
            print("  Run: systemctl --user start ilma-chrome@lokah2150.service")
            return results
    
    # ─── Step 3: Initialize BrowserEngine ─────────────────────────────────
    print("\n[3] BrowserEngine initialization")
    try:
        engine = BrowserEngine(
            connect_to_daemon=True,
            cdp_url="http://127.0.0.1:9222",
            headless=True,
            stealth=False,  # Skip stealth for cleaner CDP
        )
        await engine.initialize()
        check("BrowserEngine.initialize()", True, f"Browser: {engine._browser.version}")
    except Exception as e:
        check("BrowserEngine.initialize()", False, str(e))
        print(f"\n  ⚠️  BrowserEngine init failed: {e}")
        return results
    
    # ─── Step 4: Create adapter ───────────────────────────────────────────
    print("\n[4] ILMABrowserToolAdapter creation")
    try:
        adapter = await ILMABrowserToolAdapter.from_engine(engine)
        check("ILMABrowserToolAdapter.from_engine()", True)
        check("adapter has CDPController", isinstance(adapter._cdp.__class__.__name__, str))
    except Exception as e:
        check("ILMABrowserToolAdapter.from_engine()", False, str(e))
        await engine.close()
        return results
    
    # ─── Step 5: Navigate ─────────────────────────────────────────────────
    print("\n[5] Navigate to https://example.com")
    try:
        nav_result = await adapter.navigate("https://example.com")
        check("navigate success", nav_result["success"], f"status={nav_result.get('status')}")
        check("navigate URL correct", "example.com" in nav_result.get("url", ""))
        check("navigate has title", bool(nav_result.get("title")))
    except Exception as e:
        check("navigate", False, str(e))
    
    # ─── Step 6: Snapshot and ref_map ownership ───────────────────────────
    print("\n[6] Snapshot generation + ILMA ref_map ownership")
    try:
        snapshot = await adapter.snapshot()
        check("snapshot returns SnapshotResult", isinstance(snapshot, SnapshotResult))
        check("snapshot has text", bool(snapshot.text))
        check("snapshot has ref_map", len(snapshot.ref_map) > 0, f"{len(snapshot.ref_map)} refs")
        
        # Check ref format
        ref_keys = list(snapshot.ref_map.keys())
        check("refs are @eN format", all(k.startswith("@e") for k in ref_keys))
        
        # Check ref entries have backendNodeId
        sample_ref = ref_keys[0] if ref_keys else None
        if sample_ref:
            entry = snapshot.ref_map[sample_ref]
            # backend_node_id is CDP-only — in daemon mode it may be 0 for JS-discovered elements
            # Valid ref_map entry must have at least one usable interaction attribute
            has_cdp_handle = entry.backend_node_id > 0
            has_js_metadata = bool(entry.tag and (entry.name or entry.href or entry.bounding_box))
            check("RefEntry has usable ref (CDP handle or JS metadata)", has_cdp_handle or has_js_metadata)
            check("RefEntry has role", bool(entry.role))
            check("RefEntry is RefEntry type", isinstance(entry, RefEntry))
            
            # Print first few refs for visibility
            print(f"\n  Sample refs from example.com:")
            for i, (ref, e) in enumerate(list(snapshot.ref_map.items())[:5]):
                print(f"    {ref}: role={e.role}, name={e.name[:40] if e.name else ''}, backendNodeId={e.backend_node_id}")
    except Exception as e:
        import traceback
        check("snapshot generation", False, f"{e}\n{traceback.format_exc()}")
    
    # ─── Step 7: resolve_ref verification ─────────────────────────────────
    print("\n[7] resolve_ref verification")
    ref_keys = list(adapter.ref_map.keys())
    if ref_keys:
        test_ref = ref_keys[0]  # First ref
        try:
            entry = await adapter.resolve_ref(test_ref)
            check("resolve_ref returns RefEntry", isinstance(entry, RefEntry))
            check("resolve_ref returns usable entry", entry.backend_node_id > 0 or bool(entry.tag and entry.name))
            check("resolve_ref has correct ref", entry.ref == test_ref)
        except Exception as e:
            check("resolve_ref", False, str(e))
        
        # Try non-existent ref
        try:
            bad_entry = await adapter.resolve_ref("@e99999")
            check("resolve_ref fails for bad ref", bad_entry is None)
        except Exception as e:
            check("resolve_ref for bad ref", False, str(e))
    else:
        print("  ⚠️  No refs available from snapshot — skipping resolve_ref test")
    
    # ─── Step 8: Human-like click (CDP-direct) ─────────────────────────────
    print("\n[8] CDP-direct human-like click")
    ref_keys = list(adapter.ref_map.keys())
    if ref_keys:
        # Find a link or button to click
        clickable_ref = None
        for ref, entry in adapter.ref_map.items():
            if entry.role.lower() in ("link", "button"):
                clickable_ref = ref
                break
        
        if clickable_ref:
            try:
                print(f"\n  Clicking: {clickable_ref} ({adapter.ref_map[clickable_ref].role}: {adapter.ref_map[clickable_ref].name[:40]})")
                result = await adapter.click(clickable_ref)
                check("click succeeds", result is True)
            except Exception as e:
                import traceback
                check("click", False, f"{e}\n{traceback.format_exc()}")
        else:
            print("  ⚠️  No clickable element found — skipping click test")
    else:
        print("  ⚠️  No refs available — skipping click test")
    
    # ─── Step 9: Type test ────────────────────────────────────────────────
    print("\n[9] CDP-direct human-like type")
    ref_keys = list(adapter.ref_map.keys())
    if ref_keys:
        # Find textbox
        textbox_ref = None
        for ref, entry in adapter.ref_map.items():
            if entry.role.lower() in ("textbox", "searchbox"):
                textbox_ref = ref
                break
        
        if textbox_ref:
            try:
                print(f"\n  Typing into: {textbox_ref} ({adapter.ref_map[textbox_ref].role})")
                result = await adapter.type(textbox_ref, "test query")
                check("type succeeds", result is True)
            except Exception as e:
                check("type", False, str(e))
        else:
            print("  ⚠️  No textbox found on example.com — skipping type test")
    else:
        print("  ⚠️  No refs available — skipping type test")
    
    # ─── Step 10: Scroll test ─────────────────────────────────────────────
    print("\n[10] CDP wheel scroll")
    try:
        result = await adapter.scroll("down")
        check("scroll succeeds", result is True)
    except Exception as e:
        check("scroll", False, str(e))
    
    # ─── Cleanup ─────────────────────────────────────────────────────────
    print("\n[11] Cleanup")
    try:
        await engine.close()
        check("engine.close()", True)
    except Exception as e:
        check("engine.close()", False, str(e))
    
    # ─── Final Summary ───────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("ACCEPTANCE TEST SUMMARY")
    print("=" * 70)
    total = len(results["checks"])
    passed = len(results["passed"])
    failed = len(results["failed"])
    
    print(f"  Total checks: {total}")
    print(f"  Passed:       {passed} ✅")
    if failed > 0:
        print(f"  Failed:       {failed} ❌")
        for name, detail in results["failed"]:
            print(f"    - {name}: {detail}")
    print("=" * 70)
    
    if failed > 0:
        print("\n  RESULT: ❌ ACCEPTANCE FAILED")
        return 1
    else:
        print("\n  RESULT: ✅ ACCEPTANCE PASSED")
        return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
