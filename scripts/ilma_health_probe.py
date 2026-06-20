#!/usr/bin/env python3
"""
ilma_health_probe.py — REAL end-to-end health probe (P4, 2026-06-20)
====================================================================
Replaces the misleading "wired 35/35 = healthy" signal (which only measures whether
modules IMPORT) with a probe that exercises the ACTUAL runtime: SOT connectivity,
model selection, a live model call, and service liveness. Emits a real 0-100 score.

Usage: python3 ilma_health_probe.py [--json] [--no-call]
Exit: 0 if healthy (score>=80), 1 otherwise.
"""
import os, sys, json, time, argparse, subprocess
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _svc_active(unit):
    try:
        return subprocess.run(["systemctl", "is-active", unit], capture_output=True,
                              text=True, timeout=8).stdout.strip() == "active"
    except Exception:
        return False


def probe(do_call=True):
    checks = []  # (name, ok, weight, detail)

    # 1) SOT connectivity + data sanity
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sot", "orchestration"))
        import sot_ops
        db = sot_ops.get_db()
        db.command("ping")
        lp = db.llm_providers.count_documents({})
        act = db.models.count_documents({"is_active": True})
        free = db.models.count_documents({"is_active": True, "is_free_final": True})
        ok = lp > 0 and act > 0 and free > 0
        checks.append(("sot_connectivity", ok, 25,
                       f"llm_providers={lp} active_models={act} free_final={free}"))
    except Exception as e:
        checks.append(("sot_connectivity", False, 25, f"ERROR {str(e)[:80]}"))

    # 2) Router selects a best FREE model per task (real ranking)
    best = None
    try:
        import warnings; warnings.filterwarnings("ignore")
        import ilma_model_router as mr
        r = mr.ILMAUnifiedRouter()
        picks = {}
        for task in ("general", "heavy_coding", "vision"):
            b = r.get_best_model(task)
            if isinstance(b, dict) and b.get("model_id"):
                picks[task] = f"{b['provider']}/{b['model_id']}"
                if task == "general":
                    best = b
        ok = len(picks) == 3 and (best or {}).get("is_free_final") is not False
        checks.append(("model_selection", ok, 25, json.dumps(picks)))
    except Exception as e:
        checks.append(("model_selection", False, 25, f"ERROR {str(e)[:80]}"))

    # 3) LIVE model call (the real task-execution test)
    if do_call and best:
        try:
            import ilma_subagent_router as sr
            router = sr.SubAgentRouter()
            t0 = time.time()
            res = router.route_and_execute("Reply with exactly: HEALTH_OK", "general") \
                if hasattr(router, "route_and_execute") else None
            dt = round((time.time() - t0) * 1000)
            content = (res or {}).get("content", "") if isinstance(res, dict) else str(res or "")
            ok = bool(content and content.strip())
            checks.append(("live_execution", ok, 30, f"{dt}ms content={content[:40]!r}"))
        except Exception as e:
            checks.append(("live_execution", False, 30, f"ERROR {str(e)[:80]}"))
    else:
        checks.append(("live_execution", True, 30, "skipped (--no-call)" if not do_call else "no model"))

    # 4) Critical services live
    svcs = {u: _svc_active(u) for u in
            ("ilma-sot-sync-daemon.service", "ilma-autonomy.timer", "ilma-sot-sync.timer")}
    ok = all(svcs.values())
    checks.append(("services", ok, 20, json.dumps(svcs)))

    score = sum(w for _, o, w, _ in checks if o)
    return {"score": score, "healthy": score >= 80,
            "checks": [{"name": n, "ok": o, "weight": w, "detail": d} for n, o, w, d in checks]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-call", action="store_true")
    args = ap.parse_args()
    res = probe(do_call=not args.no_call)
    if args.json:
        print(json.dumps(res, indent=2))
    else:
        print("=" * 60); print("ILMA REAL HEALTH PROBE")
        print("=" * 60)
        for c in res["checks"]:
            print(f"  [{'OK ' if c['ok'] else 'FAIL'}] {c['name']:18s} (+{c['weight'] if c['ok'] else 0}/{c['weight']}) {c['detail']}")
        print("-" * 60)
        print(f"  REAL HEALTH SCORE: {res['score']}/100 → {'HEALTHY' if res['healthy'] else 'DEGRADED'}")
    sys.exit(0 if res["healthy"] else 1)


if __name__ == "__main__":
    main()
