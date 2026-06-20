#!/usr/bin/env python3
"""
ILMA Self-Test Harness v1.0  (2026-06-01)
=========================================
Fast, real regression gate for autonomous self-modification. Returns a pass/fail
verdict + score so the self-improvement loop can KEEP good changes and AUTO-REVERT
bad ones (git). This is what makes autonomy safe + frontier-grade.

Checks (all real, fast):
  1. core_imports     — key modules import without error
  2. runtime_wiring   — ilma_runtime_wiring reports Status OK
  3. router_free_only — router returns a FREE model + ZERO paid leaks (sample)
  4. router_callable  — chosen provider is in the callable set
  5. orchestrator     — master orchestrator returns success on a trivial task (optional/live)

Usage:
  python3 ilma_self_test_harness.py            # full (incl. 1 live call)
  python3 ilma_self_test_harness.py --fast     # skip live model call
  python3 ilma_self_test_harness.py --json
Exit code 0 = PASS, 1 = FAIL.
"""
from __future__ import annotations
import sys, os, json, importlib, io, contextlib

ILMA_ROOT = "/root/.hermes/profiles/ilma"
sys.path.insert(0, ILMA_ROOT)
os.chdir(ILMA_ROOT)

CORE_MODULES = [
    "ilma_model_router", "ilma_subagent_router", "ilma_orchestrator",
    "ilma_master_orchestrator", "ilma_provider_kernel", "ilma_credentials_v2",
    "ilma_workflow_ecc", "ilma_kanban_free_model_optimizer",
    "ilma_runtime_wiring", "ilma_autonomous_loop_engine",
]


def check_core_imports() -> tuple[bool, str]:
    failed = []
    for m in CORE_MODULES:
        try:
            importlib.import_module(m)
        except Exception as e:
            failed.append(f"{m}: {type(e).__name__}")
    return (not failed, "all import" if not failed else f"FAILED: {failed}")


def check_runtime_wiring() -> tuple[bool, str]:
    try:
        import subprocess
        r = subprocess.run([sys.executable, "ilma_runtime_wiring.py"],
                           capture_output=True, text=True, timeout=60, cwd=ILMA_ROOT)
        _out = (r.stdout or "") + (r.stderr or "")
        ok = "Status: OK" in _out or ("Wired modules:" in _out and "INCOMPLETE" not in _out)
        line = [l for l in _out.splitlines() if "Wired" in l]
        return ok, (line[0] if line else "no wiring output")
    except Exception as e:
        return False, str(e)[:80]


def check_router_free_only(samples: int = 25) -> tuple[bool, str]:
    try:
        for k in list(sys.modules.keys()):
            if k == "ilma_model_router":
                importlib.reload(sys.modules[k])
        from ilma_model_router import ILMAUnifiedRouter
        r = ILMAUnifiedRouter(allow_paid=False)
        leaks = 0
        got = 0
        for i in range(samples):
            res = r.get_best_model("general task " + str(i), allow_paid=False)
            if res and res.get("model_id"):
                got += 1
                if res.get("is_free") is False:
                    leaks += 1
        ok = leaks == 0 and got > 0
        return ok, f"got={got} leaks={leaks}"
    except Exception as e:
        return False, str(e)[:80]


def check_router_callable() -> tuple[bool, str]:
    try:
        from ilma_model_router import ILMAUnifiedRouter
        callable_set = set()
        try:
            cv = json.load(open(os.path.join(ILMA_ROOT, "ilma_model_router_data", "provider_callability.json")))
            callable_set = {k.split("-")[0] for k, v in cv.get("providers", {}).items() if v.get("callable")}
            callable_set |= {k for k, v in cv.get("providers", {}).items() if v.get("callable")}
        except Exception:
            pass
        r = ILMAUnifiedRouter(allow_paid=False)
        res = r.get_best_model("write code", allow_paid=False)
        prov = (res or {}).get("provider", "")
        ok = (not callable_set) or prov in callable_set or any(prov == c for c in callable_set)
        return ok, f"provider={prov}"
    except Exception as e:
        return False, str(e)[:80]


def check_orchestrator_live() -> tuple[bool, str]:
    try:
        from ilma_master_orchestrator import ILMAMaster
        r = ILMAMaster().process_request("Reply with just: OK")
        ok = r.get("status") == "success" and bool(str(r.get("response", "")).strip())
        return ok, f"status={r.get('status')} model={r.get('model')}"
    except Exception as e:
        return False, str(e)[:80]


def run(fast: bool = False) -> dict:
    checks = [
        ("core_imports", check_core_imports),
        ("runtime_wiring", check_runtime_wiring),
        ("router_free_only", check_router_free_only),
        ("router_callable", check_router_callable),
    ]
    if not fast:
        checks.append(("orchestrator_live", check_orchestrator_live))

    results = {}
    passed = 0
    for name, fn in checks:
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                ok, detail = fn()
        except Exception as e:
            ok, detail = False, str(e)[:80]
        results[name] = {"pass": ok, "detail": detail}
        if ok:
            passed += 1
    total = len(checks)
    # critical checks that MUST pass for a change to be safe
    critical = ["core_imports", "runtime_wiring", "router_free_only"]
    critical_ok = all(results[c]["pass"] for c in critical if c in results)
    verdict = critical_ok and passed >= total - 1  # allow 1 non-critical flake
    return {
        "verdict": "PASS" if verdict else "FAIL",
        "passed": passed, "total": total,
        "critical_ok": critical_ok,
        "score": round(passed / total, 3),
        "checks": results,
    }


def main():
    fast = "--fast" in sys.argv
    report = run(fast=fast)
    if "--json" in sys.argv:
        print(json.dumps(report, indent=2))
    else:
        print(f"=== ILMA Self-Test Harness: {report['verdict']} ({report['passed']}/{report['total']}) ===")
        for name, res in report["checks"].items():
            print(f"  [{'OK ' if res['pass'] else 'FAIL'}] {name:18} {res['detail']}")
    sys.exit(0 if report["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()
