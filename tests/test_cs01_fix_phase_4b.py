#!/usr/bin/env python3
"""
Test CS-01 Fix — Phase 4B
Verifies that orchestrator.execute() no longer bypasses SubAgentRouter.

Tests (5):
  T1. test_orchestrator_no_longer_calls_provider_kernel_directly
  T2. test_orchestrator_uses_subagent_router
  T3. test_orchestrator_allow_paid_false_enforced
  T4. test_orchestrator_has_emergency_fallback_path
  T5. test_orchestrator_execute_signature_preserved

Acceptance: 5/5 must pass
"""
import sys
import os
import inspect
from pathlib import Path
from unittest.mock import patch, MagicMock

ILMA_PROFILE = "/root/.hermes/profiles/ilma"
sys.path.insert(0, ILMA_PROFILE)


def test_T1_no_provider_kernel_direct_call():
    """Orchestrator.execute() must NOT call ProviderKernel.call() directly."""
    from ilma_orchestrator import ILMAOrchestrator

    o = ILMAOrchestrator()

    # Patch SubAgentRouter.route_and_execute to track call
    with patch.object(o.subagent, 'route_and_execute',
                      return_value={"success": True, "content": "ok",
                                    "model": "test-model", "decision": {"provider": "nvidia"}}) as mock_sub:

        with patch.object(o.kernel, 'call',
                          return_value="should not be called") as mock_kernel:
            result = o.execute("hello")

    # SubAgentRouter MUST be called
    assert mock_sub.called, "SubAgentRouter.route_and_execute was NOT called"
    # ProviderKernel.call MUST NOT be called in the normal path
    assert not mock_kernel.called, "ProviderKernel.call was called — CS-01 BYPASS"
    print("[T1] ✅ No ProviderKernel direct call")
    return True


def test_T2_uses_subagent_router():
    """Orchestrator.execute() must use SubAgentRouter.route_and_execute()."""
    from ilma_orchestrator import ILMAOrchestrator

    o = ILMAOrchestrator()

    # Verify the source code path
    src = inspect.getsource(o.execute)
    assert "subagent.route_and_execute" in src, \
        "execute() does not call self.subagent.route_and_execute"
    assert "self.subagent" in src, "execute() does not use self.subagent"
    print("[T2] ✅ Uses SubAgentRouter")
    return True


def test_T3_allow_paid_false_enforced():
    """Orchestrator must call route_and_execute with allow_paid=False."""
    from ilma_orchestrator import ILMAOrchestrator

    o = ILMAOrchestrator()

    with patch.object(o.subagent, 'route_and_execute',
                      return_value={"success": True, "content": "ok"}) as mock_sub:
        o.execute("test prompt")

    # Inspect the call
    assert mock_sub.called, "SubAgentRouter not called"
    call_kwargs = mock_sub.call_args.kwargs
    assert "allow_paid" in call_kwargs, "allow_paid not passed"
    assert call_kwargs["allow_paid"] is False, \
        f"allow_paid is {call_kwargs['allow_paid']}, expected False (FREE-ONLY policy)"
    print("[T3] ✅ allow_paid=False enforced")
    return True


def test_T4_emergency_fallback():
    """If SubAgentRouter raises, orchestrator falls back to ProviderKernel."""
    from ilma_orchestrator import ILMAOrchestrator

    o = ILMAOrchestrator()

    with patch.object(o.subagent, 'route_and_execute',
                      side_effect=Exception("subagent crashed")):
        with patch.object(o.kernel, 'call', return_value="kernel-fallback-result") as mock_kernel:
            with patch('ilma_orchestrator.route_task',
                       return_value=("test-model", "nvidia", "test reason")):
                result = o.execute("test")

    assert mock_kernel.called, "Emergency fallback to ProviderKernel NOT triggered"
    assert result.get("used_fallback") is True, "used_fallback flag not set"
    assert "FALLBACK_TO_KERNEL" in result.get("error", ""), "Fallback marker not in error"
    print("[T4] ✅ Emergency fallback works")
    return True


def test_T5_signature_preserved():
    """orchestrator.execute(prompt, task_type=None, force_model=None) signature intact."""
    from ilma_orchestrator import ILMAOrchestrator
    sig = inspect.signature(ILMAOrchestrator.execute)
    params = list(sig.parameters.keys())
    # self, prompt, task_type, force_model
    assert "self" in params
    assert "prompt" in params
    assert "task_type" in params
    assert "force_model" in params
    print("[T5] ✅ Signature preserved")
    return True


def test_T6_mark_failure_on_timeout_integration():
    """
    Integration test: simulate a timeout via SubAgentRouter and verify
    that orchestrator's response includes error_type.
    """
    from ilma_orchestrator import ILMAOrchestrator

    o = ILMAOrchestrator()

    # Simulate SubAgentRouter returning a failure result
    fail_result = {
        "success": False,
        "content": "",
        "model": "failing-model",
        "error": "timeout after 60s",
        "error_type": "timeout_failure",
        "decision": {"provider": "nvidia", "reasoning": "test"},
    }

    with patch.object(o.subagent, 'route_and_execute', return_value=fail_result):
        result = o.execute("test")

    assert result["status"] == "error", f"Expected status=error, got {result['status']}"
    assert result.get("error_type") == "timeout_failure", \
        f"Expected error_type=timeout_failure, got {result.get('error_type')}"
    print("[T6] ✅ mark_failure path: error_type captured in orchestrator response")
    return True


def test_T7_used_fallback_observable():
    """
    Verify that when SubAgentRouter triggers fallback, orchestrator
    surfaces used_fallback=True and original_model in response.
    """
    from ilma_orchestrator import ILMAOrchestrator

    o = ILMAOrchestrator()

    fallback_result = {
        "success": True,
        "content": "fallback result",
        "model": "fallback-model",
        "used_fallback": True,
        "original_model": "primary-model",
        "decision": {"provider": "nvidia", "reasoning": "primary failed"},
    }

    with patch.object(o.subagent, 'route_and_execute', return_value=fallback_result):
        result = o.execute("test")

    assert result["used_fallback"] is True
    assert result["original_model"] == "primary-model"
    assert result["model"] == "fallback-model"
    print("[T7] ✅ Fallback observability preserved")
    return True


# ===========================================================================
# Main test runner
# ===========================================================================

if __name__ == "__main__":
    import json
    results = {"tests": [], "passed": 0, "failed": 0, "total": 7}

    test_funcs = [
        ("T1_no_provider_kernel_direct_call", test_T1_no_provider_kernel_direct_call),
        ("T2_uses_subagent_router", test_T2_uses_subagent_router),
        ("T3_allow_paid_false_enforced", test_T3_allow_paid_false_enforced),
        ("T4_emergency_fallback", test_T4_emergency_fallback),
        ("T5_signature_preserved", test_T5_signature_preserved),
        ("T6_mark_failure_on_timeout_integration", test_T6_mark_failure_on_timeout_integration),
        ("T7_used_fallback_observable", test_T7_used_fallback_observable),
    ]

    for name, fn in test_funcs:
        try:
            ok = fn()
            results["tests"].append({"name": name, "passed": True})
            results["passed"] += 1
        except AssertionError as e:
            results["tests"].append({"name": name, "passed": False, "error": str(e)})
            results["failed"] += 1
            print(f"[{name}] ❌ FAILED: {e}")
        except Exception as e:
            results["tests"].append({"name": name, "passed": False, "error": str(e)})
            results["failed"] += 1
            print(f"[{name}] ❌ ERROR: {e}")

    results["pass_rate"] = f"{results['passed']}/{results['total']}"
    results["acceptance"] = "PASS" if results["failed"] == 0 else "FAIL"
    results["timestamp"] = "2026-06-03"

    out_path = "/root/.hermes/profiles/ilma/ILMA_PHASE_4B_CS01_TEST_RESULTS.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)

    print()
    print(f"=== CS-01 Test Results: {results['passed']}/{results['total']} passed ===")
    print(f"Acceptance: {results['acceptance']}")
    print(f"Written to: {out_path}")

    sys.exit(0 if results["failed"] == 0 else 1)
