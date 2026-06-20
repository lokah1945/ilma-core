#!/usr/bin/env python3
"""
ILMA Phase 4F — Task L1-04: Router Timeout Wrapper Verification
Verify: _timeout_wrapper is already present and functional in ilma_model_router.py
"""
import sys, time, json
sys.path.insert(0, '/root/.hermes/profiles/ilma')

RESULTS = {"passed": [], "failed": []}

def test_timeout_wrapper_exists():
    """_timeout_wrapper function must exist in ilma_model_router."""
    from ilma_credentials_v2 import get_credential  # just to confirm path
    from ilma_model_router import _timeout_wrapper, RoutingTimeoutError
    assert callable(_timeout_wrapper), "_timeout_wrapper not callable"
    assert callable(RoutingTimeoutError), "RoutingTimeoutError not a class"
    RESULTS["passed"].append("timeout_wrapper_exists")

def test_timeout_wrapper_triggers():
    """_timeout_wrapper raises RoutingTimeoutError when function exceeds timeout."""
    from ilma_model_router import _timeout_wrapper, RoutingTimeoutError
    import time as _tm
    def slow_func():
        _tm.sleep(2.0)
        return "done"
    start = _tm.time()
    try:
        _timeout_wrapper(slow_func, timeout_seconds=0.1)()
        RESULTS["failed"].append("timeout_wrapper_triggers: no exception raised")
    except RoutingTimeoutError:
        elapsed = _tm.time() - start
        assert elapsed < 1.5, f"took {elapsed}s, too slow"
        RESULTS["passed"].append("timeout_wrapper_triggers")
    except Exception as e:
        RESULTS["failed"].append(f"timeout_wrapper_triggers: {e}")

def test_timeout_wrapper_fallback():
    """_timeout_wrapper fallback is used when _get_best_model_impl times out."""
    # Test via real router: get_best_model with _timeout=0.001 should use fallback
    from ilma_model_router import ILMAUnifiedRouter
    router = ILMAUnifiedRouter()
    # Very short timeout → fallback should trigger
    result = router.get_best_model("what is 1+1", _timeout=0.001)
    # Fallback returns emergency_fallback dict with is_free=True
    assert isinstance(result, dict), f"got {type(result)}"
    assert "model_id" in result, f"missing model_id: {result}"
    assert result.get("is_free") == True, f"fallback should be free, got {result}"
    RESULTS["passed"].append("timeout_wrapper_fallback")

def test_get_best_model_has_timeout_arg():
    """get_best_model() accepts timeout_seconds parameter."""
    from ilma_model_router import ILMAUnifiedRouter
    router = ILMAUnifiedRouter()
    import inspect
    sig = inspect.signature(router.get_best_model)
    assert '_timeout' in sig.parameters, f"_timeout not in sig: {sig}"
    RESULTS["passed"].append("get_best_model_has_timeout_arg")

def test_get_best_model_default_30s():
    """get_best_model() default timeout is 30s."""
    from ilma_model_router import ILMAUnifiedRouter
    router = ILMAUnifiedRouter()
    import inspect
    sig = inspect.signature(router.get_best_model)
    timeout_param = sig.parameters.get('_timeout')
    assert timeout_param is not None, "_timeout param missing"
    assert timeout_param.default == 30.0, f"default is {timeout_param.default}, expected 30.0"
    RESULTS["passed"].append("get_best_model_default_30s")

def test_get_best_model_timeout_functional():
    """Live get_best_model call completes within timeout."""
    from ilma_model_router import ILMAUnifiedRouter
    router = ILMAUnifiedRouter()
    start = time.time()
    result = router.get_best_model("general chat", _timeout=30.0)
    elapsed = time.time() - start
    assert elapsed < 30.0, f"took {elapsed}s > 30s"
    assert isinstance(result, dict), f"got {type(result)}"
    RESULTS["passed"].append("get_best_model_timeout_functional")

def test_timeout_error_class():
    """RoutingTimeoutError is a proper Exception subclass."""
    from ilma_model_router import RoutingTimeoutError
    try:
        raise RoutingTimeoutError("test")
    except RoutingTimeoutError:
        RESULTS["passed"].append("routing_timeout_error_class")
    except Exception as e:
        RESULTS["failed"].append(f"routing_timeout_error_class: {e}")

def run():
    print("=" * 60)
    print("L1-04: Router Timeout Wrapper Verification")
    print("=" * 60)
    test_timeout_wrapper_exists()
    test_timeout_wrapper_triggers()
    test_timeout_wrapper_fallback()
    test_get_best_model_has_timeout_arg()
    test_get_best_model_default_30s()
    test_get_best_model_timeout_functional()
    test_timeout_error_class()
    print(f"\nResults: {len(RESULTS['passed'])} passed, {len(RESULTS['failed'])} failed")
    for f in RESULTS["failed"]:
        print(f"  FAIL: {f}")
    print(json.dumps(RESULTS, indent=2))
    return len(RESULTS["failed"]) == 0

if __name__ == "__main__":
    ok = run()
    sys.exit(0 if ok else 1)
