#!/usr/bin/env python3
"""
sot_sync.py — SOT Unified Sync Orchestrator
============================================

Single entrypoint for all SOT operations. Designed to replace the
current multi-script workflow with one auditable, idempotent command.

Pipeline:
  1. provider_sync  — pull live model lists from each provider
  2. sot_enricher   — port MASTER.json → model_intelligence + model_benchmarks
  3. sot_materialize— write PROVIDER_INTELLIGENCE_MASTER.json + api_key.json
                      (the on-disk cache that runtime consumers read)
  4. validators     — run all 6 collection validators
  5. audit          — record sync_run event in model_audit_trail

Each step is wrapped in a sot_jobs entry (idempotency lock per hour).
Failures are recorded in sot_jobs.result + model_audit_trail.

Usage:
    python3 sot_sync.py                  # full pipeline
    python3 sot_sync.py --skip-sync      # skip provider sync
    python3 sot_sync.py --skip-materialize  # skip materialization
    python3 sot_sync.py --only-validate  # only run validators
    python3 sot_sync.py --provider X     # only sync provider X
    python3 sot_sync.py --dry-run        # no DB writes
"""
import os, sys, json, argparse, time
from datetime import datetime, timezone
from typing import Any, Dict, List

SOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SOT_DIR)
sys.path.insert(0, os.path.join(SOT_DIR, "orchestration"))
sys.path.insert(0, os.path.join(SOT_DIR, "discovery"))
sys.path.insert(0, os.path.join(SOT_DIR, "validators"))

import sot_ops
from sot_ops import (
    models_coll, benchmarks_coll, intelligence_coll, audit_coll, jobs_coll,
    generate_evidence_id, write_audit, ensure_indexes,
)

PIPELINE_START = datetime.now(timezone.utc)


def _run_step(name: str, fn, *args, **kwargs) -> Dict[str, Any]:
    """Run a pipeline step with timing and error capture."""
    t0 = time.time()
    print(f"\n[STEP] {name}...")
    try:
        result = fn(*args, **kwargs)
        elapsed = round(time.time() - t0, 2)
        print(f"  ✓ {name} completed in {elapsed}s — {result}")
        return {"status": "success", "result": result, "elapsed_sec": elapsed}
    except Exception as e:
        elapsed = round(time.time() - t0, 2)
        print(f"  ✗ {name} FAILED in {elapsed}s — {e}")
        return {"status": "error", "error": str(e)[:500], "elapsed_sec": elapsed}


def step_provider_sync(args) -> Dict[str, Any]:
    """Pull live model lists from external providers."""
    import provider_sync
    provider_sync._load_url_overrides()
    ensure_indexes(force=True)
    if args.provider:
        providers = [args.provider]
    else:
        providers = [p for p in provider_sync.PROVIDER_CONFIGS
                     if p not in ("cloudflare", "artificial_analysis")]
    results = {}
    for p in providers:
        r = provider_sync.sync_provider(p, dry_run=args.dry_run)
        results[p] = r
    return {"providers_synced": len(results), "results": results}


def step_enrich(args) -> Dict[str, Any]:
    """Port MASTER.json → model_benchmarks + model_intelligence."""
    import sot_enricher
    r1 = sot_enricher.write_passive_benchmarks(dry_run=args.dry_run)
    r2 = sot_enricher.write_aa_benchmarks(dry_run=args.dry_run)
    r3 = sot_enricher.write_intelligence(dry_run=args.dry_run)
    return {
        "passive": r1, "aa": r2, "intelligence": r3,
        "totals": {
            "passive_written": r1.get("written", 0),
            "aa_written": r2.get("written", 0),
            "intelligence_written": r3.get("written", 0),
        }
    }


def step_materialize(args) -> Dict[str, Any]:
    """Write PROVIDER_INTELLIGENCE_MASTER.json + api_key.json + benchmark_db."""
    import sot_materialize
    r1 = sot_materialize.materialize_master(dry_run=args.dry_run)
    r2 = sot_materialize.materialize_benchmarks(dry_run=args.dry_run)
    r3 = sot_materialize.materialize_api_key(dry_run=args.dry_run, include_secrets=args.include_secrets)
    return {
        "master": r1, "benchmarks": r2, "api_key": r3,
        "totals": {
            "providers": r1.get("providers", 0),
            "models": r1.get("models", 0),
            "llm_providers": r3.get("providers", 0),
        }
    }


def step_validate(args) -> Dict[str, Any]:
    """Run all 6 collection validators."""
    import subprocess
    validators = [
        ("llm_providers",      "validators/validate_llm_providers.py"),
        ("model_audit_trail",  "validators/validate_model_audit_trail.py"),
        ("model_benchmarks",   "validators/validate_model_benchmarks.py"),
        ("model_intelligence", "validators/validate_model_intelligence.py"),
        ("models",             "validators/validate_models.py"),
        ("sot_jobs",           "validators/validate_sot_jobs.py"),
    ]
    results = {}
    overall_pass = True
    for name, path in validators:
        r = subprocess.run(
            ["python3", path, "--all"],
            cwd=SOT_DIR, capture_output=True, text=True, timeout=120
        )
        # Parse "Result: X/Y invalid" from last non-empty line
        lines = [l.strip() for l in r.stdout.split("\n") if l.strip()]
        result_line = next((l for l in reversed(lines) if l.startswith("Result:")), "")
        invalid = 0
        if result_line:
            try:
                invalid = int(result_line.split(":")[1].strip().split("/")[0])
            except (ValueError, IndexError):
                invalid = -1  # parse error
        passed = (r.returncode == 0 and invalid == 0)
        if not passed:
            overall_pass = False
        results[name] = {"exit_code": r.returncode, "invalid": invalid, "passed": passed}
        if not passed:
            # Debug: show stderr + last stdout line
            print(f"  ✗ {name}: {result_line or 'no output'} (exit={r.returncode})")
            if r.stderr:
                print(f"      stderr: {r.stderr[:200]}")
        else:
            print(f"  ✓ {name}: {result_line or 'PASS'}")
    return {"validators": results, "overall_pass": overall_pass}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-sync", action="store_true",
                        help="Skip provider_sync")
    parser.add_argument("--skip-enrich", action="store_true",
                        help="Skip sot_enricher")
    parser.add_argument("--skip-materialize", action="store_true",
                        help="Skip sot_materialize")
    parser.add_argument("--skip-validate", action="store_true",
                        help="Skip validators")
    parser.add_argument("--only-validate", action="store_true",
                        help="Only run validators (alias for --skip-sync --skip-enrich --skip-materialize)")
    parser.add_argument("--provider", help="Only sync this provider")
    parser.add_argument("--include-secrets", action="store_true",
                        help="api_key.json: embed full api_key values (default: masked)")
    parser.add_argument("--dry-run", action="store_true",
                        help="No writes (validators still run)")
    args = parser.parse_args()

    if args.only_validate:
        args.skip_sync = True
        args.skip_enrich = True
        args.skip_materialize = True

    print("=" * 70)
    print("SOT Unified Sync Orchestrator")
    print(f"  started_at:  {PIPELINE_START.isoformat()}")
    print(f"  dry_run:     {args.dry_run}")
    print(f"  skip_sync:   {args.skip_sync}")
    print(f"  skip_enrich: {args.skip_enrich}")
    print(f"  skip_mat:    {args.skip_materialize}")
    print(f"  skip_val:    {args.skip_validate}")
    print(f"  provider:    {args.provider or 'ALL'}")
    print("=" * 70)

    # Acquire job lock
    job_id = f"sync-{PIPELINE_START.strftime('%Y%m%d-%H%M%S')}"
    idempotency_key = f"sync:{PIPELINE_START.strftime('%Y%m%d-%H')}"
    job = sot_ops.acquire_job_lock(
        job_id=job_id, job_type="validate", actor="sot_sync",
        idempotency_key=idempotency_key
    )
    if job is None:
        print(f"\n[JOB] Another sync is running (idempotency_key={idempotency_key}). Exiting.")
        return

    ensure_indexes(force=True)
    pipeline_result: Dict[str, Any] = {"steps": {}}

    try:
        if not args.skip_sync:
            pipeline_result["steps"]["provider_sync"] = _run_step(
                "1/4 provider_sync", step_provider_sync, args)
        if not args.skip_enrich:
            pipeline_result["steps"]["enrich"] = _run_step(
                "2/4 sot_enricher", step_enrich, args)
        if not args.skip_materialize:
            pipeline_result["steps"]["materialize"] = _run_step(
                "3/4 sot_materialize", step_materialize, args)
        if not args.skip_validate:
            pipeline_result["steps"]["validate"] = _run_step(
                "4/4 validators", step_validate, args)

        # Audit
        eid = generate_evidence_id(code="SYNC")
        write_audit(
            provider="*", model_id="*",
            event_type="enrichment_run", actor="sot_sync",
            source_collection="models",
            delta=pipeline_result, evidence_id=eid,
            notes=f"SOT sync pipeline run (dry_run={args.dry_run})"
        )

        # Finish
        sot_ops.finish_job(job_id, "success", result=pipeline_result)
        elapsed = round((datetime.now(timezone.utc) - PIPELINE_START).total_seconds(), 1)
        print("\n" + "=" * 70)
        print(f"SOT SYNC COMPLETE in {elapsed}s — evidence_id={eid}")
        if "validate" in pipeline_result["steps"]:
            v = pipeline_result["steps"]["validate"]["result"]
            print(f"  Validators: {'ALL PASS' if v.get('overall_pass') else 'SOME FAILED'}")
        print("=" * 70)
    except Exception as e:
        sot_ops.finish_job(job_id, "error", error=str(e)[:500])
        print(f"\n[FATAL] {e}")
        raise

if __name__ == "__main__":
    main()
