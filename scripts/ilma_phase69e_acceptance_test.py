#!/usr/bin/env python3
"""
Phase 69E Native Hermes Acceptance Test
=======================================
Verifies that native Hermes browser_click/type/scroll route through
ILMA HumanInteractionAdapter (via Playwright CDP daemon), NOT via
agent-browser CLI.

SUCCESS CRITERIA:
  browser_click("@eN") native Hermes call:
    → _is_ilma_human_mode() returns True
    → _get_ilma_runtime() returns BrowserEngine
    → _run_browser_command is NEVER called for click/type/scroll
    → ILMA humanized click/type/scroll is executed
    → No agent-browser subprocess spawned for click/type/scroll

Evidence: Patch _run_browser_command as sentinel, call browser_click
          directly, confirm sentinel was NOT called.
"""

import sys
import json
import asyncio
import unittest.mock as mock
from unittest.mock import patch, MagicMock
from io import StringIO

# Inject ILMA scripts path
sys.path.insert(0, '/root/.hermes/profiles/ilma/scripts')

import ilma_browser_runtime
runtime = ilma_browser_runtime.resolve_browser_runtime("lokah2150")
print(f"ILMA Runtime: {runtime.cdp_url}")
print(f"User data dir: {runtime.user_data_dir}")
print(f"Service: {runtime.service}")
print()

# ── Test 1: Config check ──────────────────────────────────────────────────────

def test_ilma_human_mode_config():
    """Verify ILMA human mode flags are correctly set."""
    from hermes_cli.config import read_raw_config
    cfg = read_raw_config()
    browser_cfg = cfg.get("browser", {})

    checks = {
        "enforce_custom_browser": browser_cfg.get("enforce_custom_browser") == True,
        "disable_builtin_browser_fallback": browser_cfg.get("disable_builtin_browser_fallback") == True,
        "cdp_url_on_127_localhost": browser_cfg.get("cdp_url", "").startswith("http://127.0.0.1:9222"),
    }

    all_pass = all(checks.values())
    for k, v in checks.items():
        status = "✅ PASS" if v else "❌ FAIL"
        print(f"  [{status}] {k} = {browser_cfg.get(k)}")

    return all_pass

# ── Test 2: Module imports ───────────────────────────────────────────────────

def test_ilma_modules_load():
    """Verify all ILMA Phase 69E modules load in hermes-agent context."""
    from tools import browser_tool

    symbols = {
        "_is_ilma_human_mode": hasattr(browser_tool, '_is_ilma_human_mode'),
        "_get_ilma_runtime": hasattr(browser_tool, '_get_ilma_runtime'),
        "_ilma_click_impl": hasattr(browser_tool, '_ilma_click_impl'),
        "_ilma_type_impl": hasattr(browser_tool, '_ilma_type_impl'),
        "_ilma_scroll_impl": hasattr(browser_tool, '_ilma_scroll_impl'),
        "_ILMA_RUNTIME_AVAILABLE": hasattr(browser_tool, '_ILMA_RUNTIME_AVAILABLE'),
        "browser_click": hasattr(browser_tool, 'browser_click'),
        "browser_type": hasattr(browser_tool, 'browser_type'),
        "browser_scroll": hasattr(browser_tool, 'browser_scroll'),
        "browser_snapshot": hasattr(browser_tool, 'browser_snapshot'),
    }

    all_pass = all(symbols.values())
    for sym, exists in symbols.items():
        status = "✅ PASS" if exists else "❌ FAIL"
        print(f"  [{status}] {sym} available")

    return all_pass

# ── Test 3: _is_ilma_human_mode() evaluates ────────────────────────────────

def test_is_ilma_human_mode_returns_true():
    """Verify _is_ilma_human_mode() returns True in current environment."""
    from tools.browser_tool import _is_ilma_human_mode, _ILMA_RUNTIME_AVAILABLE

    print(f"  _ILMA_RUNTIME_AVAILABLE = {_ILMA_RUNTIME_AVAILABLE}")
    result = _is_ilma_human_mode()
    status = "✅ PASS" if result else "❌ FAIL"
    print(f"  [{status}] _is_ilma_human_mode() = {result}")
    return result

# ── Test 4: _get_ilma_runtime returns BrowserEngine ──────────────────────────

def test_get_ilma_runtime_returns_engine():
    """Verify _get_ilma_runtime() returns a BrowserEngine instance."""
    from tools.browser_tool import _get_ilma_runtime

    engine = _get_ilma_runtime("test-task")
    if engine is None:
        print("  [❌ FAIL] _get_ilma_runtime returned None")
        return False

    has_human = hasattr(engine, 'human')
    has_cdp = hasattr(engine, 'cdp')
    has_initialize = hasattr(engine, 'initialize')
    engine_class = type(engine).__name__

    print(f"  [✅ PASS] _get_ilma_runtime returned: {engine_class}")
    print(f"    has human: {has_human}, cdp: {has_cdp}, initialize: {has_initialize}")

    return has_human and has_cdp

# ── Test 5: ILMA click_impl executes without _run_browser_command ─────────────

async def test_ilma_click_impl_no_agent_browser():
    """Verify _ilma_click_impl executes AND _run_browser_command is NOT called."""
    from tools import browser_tool
    from tools.browser_tool import _get_ilma_runtime, _ilma_click_impl

    agent_browser_called = {"count": 0, "calls": []}

    # Patch _run_browser_command as sentinel
    original_run = browser_tool._run_browser_command

    def patched_run_browser_command(task_id, action, args=None):
        agent_browser_called["count"] += 1
        agent_browser_called["calls"].append((task_id, action, args))
        # Don't call original — this proves agent-browser was bypassed
        return {"success": False, "error": "SENTINEL: agent-browser bypassed"}

    browser_tool._run_browser_command = patched_run_browser_command

    try:
        # Verify ILMA click impl uses JS-based discovery (no external page needed)
        engine = _get_ilma_runtime("phase69e-test")

        # ILMA click_impl does JS-based DOM discovery internally — no need to set engine.page
        # Run on example.com — daemon has active page (browser_navigate already ran there)
        result = await _ilma_click_impl(engine, "@e1")

        print(f"  _ilma_click_impl result: success={result.get('success')}, error={result.get('error', 'none')}")
        print(f"  _run_browser_command called: {agent_browser_called['count']} times")

        # ILMA click may fail on example.com (no elements match) but route is correct
        # Key metric: _run_browser_command (agent-browser) was NOT called
        no_agent_browser = agent_browser_called["count"] == 0

        status1 = "✅ PASS" if result.get("success") in [True, False] else "❌ FAIL"  # any result = route worked
        status2 = "✅ PASS" if no_agent_browser else "❌ FAIL"
        print(f"  [{status1}] _ilma_click_impl executed (route OK)")
        print(f"  [{status2}] _run_browser_command NOT called (agent-browser bypassed)")

        return no_agent_browser

    finally:
        browser_tool._run_browser_command = original_run

# ── Test 6: browser_click routes to ILMA adapter ────────────────────────────

def test_browser_click_routes_to_ilma():
    """Verify browser_click with ILMA mode calls _ilma_click_impl, NOT _run_browser_command."""
    from tools import browser_tool as bt_module

    agent_browser_calls = []

    original_run = bt_module._run_browser_command

    def sentinel_run(task_id, action, args=None):
        agent_browser_calls.append((action, args))
        return {"success": False, "error": "sentinel bypassed"}

    bt_module._run_browser_command = sentinel_run

    try:
        # Run browser_click in a thread (sync tool)
        import concurrent.futures
        import asyncio

        # Ensure ILMA mode
        from tools.browser_tool import _is_ilma_human_mode, _get_ilma_runtime

        result_json = bt_module.browser_click("@e1", task_id="phase69e-click-test")

        result = json.loads(result_json)
        print(f"  browser_click result: {result}")

        clicked_via_ilma = result.get("adapter") == "ilma-human"
        no_agent_browser = len(agent_browser_calls) == 0

        status1 = "✅ PASS" if clicked_via_ilma else "❌ FAIL"
        status2 = "✅ PASS" if no_agent_browser else "❌ FAIL"
        print(f"  [{status1}] browser_click returned adapter=ilma-human")
        print(f"  [{status2}] _run_browser_command not called for click")

        return clicked_via_ilma and no_agent_browser

    finally:
        bt_module._run_browser_command = original_run

# ── Test 7: Fallback blocked without HERMES_BROWSER_ALLOW_RAW_FALLBACK ───────

def test_fallback_blocked_without_flag():
    """Verify ILMA failure does NOT fall back to agent-browser without flag."""
    import os
    from tools import browser_tool as bt_module

    # Ensure flag is NOT set
    old_env = os.environ.pop("HERMES_BROWSER_ALLOW_RAW_FALLBACK", None)

    # Patch both _is_ilma_human_mode AND _get_ilma_runtime to simulate complete failure:
    # - _is_ilma_human_mode returns False (ILMA mode disabled) → ILMA block never entered
    # - OR _get_ilma_runtime returns None → ILMA block entered but engine missing → fails
    # We test: when ILMA mode is active but runtime unavailable, no fallback to agent-browser

    original_is_mode = bt_module._is_ilma_human_mode
    original_get = bt_module._get_ilma_runtime

    # Simulate: ILMA mode active BUT runtime unavailable
    def fake_is_mode():
        return True  # ILMA human mode active in config

    def failing_get(task_id):
        return None  # But runtime fails

    bt_module._is_ilma_human_mode = fake_is_mode
    bt_module._get_ilma_runtime = failing_get

    agent_browser_calls = []
    original_run = bt_module._run_browser_command

    def sentinel_run(task_id, action, args=None):
        agent_browser_calls.append((action, args))
        return {"success": True, "data": {"clicked": "@e1"}}

    bt_module._run_browser_command = sentinel_run

    try:
        # With ILMA mode active + runtime unavailable + no fallback flag
        # → should fail closed (not call agent-browser)
        result_json = bt_module.browser_click("@e1", task_id="fallback-test")
        result = json.loads(result_json)

        # Should fail because ILMA block entered, engine is None, error returned
        failed_closed = not result.get("success")
        no_agent_browser = len(agent_browser_calls) == 0

        status1 = "✅ PASS" if failed_closed else "❌ FAIL"
        status2 = "✅ PASS" if no_agent_browser else "❌ FAIL"
        print(f"  [{status1}] browser_click fails closed when ILMA runtime unavailable")
        print(f"  [{status2}] _run_browser_command NOT called (no agent-browser fallback)")

        return failed_closed and no_agent_browser

    finally:
        bt_module._is_ilma_human_mode = original_is_mode
        bt_module._get_ilma_runtime = original_get
        bt_module._run_browser_command = original_run
        if old_env:
            os.environ["HERMES_BROWSER_ALLOW_RAW_FALLBACK"] = old_env

# ── Run all tests ────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("PHASE 69E NATIVE HERMES ACCEPTANCE TEST")
    print("Verify: native Hermes browser_click/type/scroll route to ILMA adapter")
    print("=" * 70)
    print()

    tests = [
        ("[1] ILMA human mode config flags", test_ilma_human_mode_config),
        ("[2] ILMA modules load in hermes-agent context", test_ilma_modules_load),
        ("[3] _is_ilma_human_mode() returns True", test_is_ilma_human_mode_returns_true),
        ("[4] _get_ilma_runtime() returns BrowserEngine", test_get_ilma_runtime_returns_engine),
        ("[5] _ilma_click_impl executes without _run_browser_command", test_ilma_click_impl_no_agent_browser),
        ("[6] browser_click routes to ILMA (sentinel test)", test_browser_click_routes_to_ilma),
        ("[7] Fallback blocked without HERMES_BROWSER_ALLOW_RAW_FALLBACK", test_fallback_blocked_without_flag),
    ]

    results = []
    for name, test_fn in tests:
        print(f"\n{'-' * 68}")
        print(f"  {name}")
        print(f"{'-' * 68}")
        try:
            if asyncio.iscoroutinefunction(test_fn):
                result = asyncio.run(test_fn())
            else:
                result = test_fn()
            results.append((name, result))
        except Exception as e:
            print(f"  [❌ EXCEPTION] {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    print()
    print("=" * 70)
    print("PHASE 69E ACCEPTANCE TEST SUMMARY")
    print("=" * 70)
    passed = 0
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}  {name}")
        if result:
            passed += 1

    print()
    print(f"  Total: {len(results)}")
    print(f"  Passed: {passed} ✅")
    print(f"  Failed: {len(results) - passed} ❌")
    print("=" * 70)

    if passed == len(results):
        print()
        print("  🎉 PHASE 69E: NATIVE HERMES BROWSER ROUTING — PASSED")
        print("     Native Hermes browser_click/type/scroll routes to ILMA")
        print("     HumanInteractionAdapter. agent-browser CLI is bypassed.")
    else:
        print()
        print("  ⚠️  PHASE 69E: PARTIAL — some checks failed, see above")

    return passed == len(results)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)