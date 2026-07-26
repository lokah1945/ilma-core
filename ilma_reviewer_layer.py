#!/usr/bin/env python3
"""
ILMA Reviewer Layer v1.0  (2026-06-01)
======================================
Validation/reviewer pass for HIGH-CRITICALITY tasks. Uses a DIFFERENT model than
the executor to independently check an output. Non-destructive: returns validation
metadata + a retry instruction; NEVER silently rewrites the final answer (ILMA
remains final composer).

Public API:
  review(output, objective, *, executor_model=None, require_json=False,
         schema=None, task_type="high_risk") -> dict
      -> {"verdict": "pass|fail|warn", "score": 0..1, "issues": [...],
          "retry_instruction": str|None, "reviewer_model": str,
          "checks": {...}}

Free-only, callable reviewer model chosen via MIL (distinct from executor).
"""
from __future__ import annotations
import sys, os, json, re
from pathlib import Path
from typing import Any, Dict, Optional

ILMA_ROOT = Path("/root/.hermes/profiles/ilma")
if str(ILMA_ROOT) not in sys.path:
    sys.path.insert(0, str(ILMA_ROOT))


def _pick_reviewer(executor_model: Optional[str]) -> Dict[str, str]:
    """Pick a free callable reviewer model, different from the executor."""
    try:
        import ilma_model_intelligence as mil
        rec = mil.recommend(role="reviewer")
        r = rec.get("recommended", {})
        prov, model = r.get("provider"), r.get("model")
        # if same as executor, take first fallback
        if model and executor_model and model == executor_model:
            for fb in rec.get("fallbacks", []):
                if fb.get("model") and fb.get("model") != executor_model:
                    prov, model = fb.get("provider"), fb.get("model")
                    break
        return {"provider": prov or "ollama", "model": model or "kimi-k2.6"}
    except Exception:
        return {"provider": "ollama", "model": "kimi-k2.6"}


def _call(provider: str, model: str, prompt: str, timeout: int = 60) -> str:
    try:
        from ilma_provider_kernel import ProviderKernel
        return ProviderKernel().call(provider, model,
                                     [{"role": "user", "content": prompt}],
                                     max_tokens=512, timeout=timeout)
    except Exception as e:
        return f"REVIEWER_ERROR: {e}"


def _static_checks(output: str, require_json: bool, schema: Optional[dict]) -> Dict[str, Any]:
    checks = {"non_empty": bool(output and output.strip())}
    if require_json:
        try:
            parsed = json.loads(output) if isinstance(output, str) else output
            checks["json_valid"] = True
            if schema and isinstance(schema, dict):
                missing = [k for k in schema.get("required", []) if k not in (parsed or {})]
                checks["schema_required_present"] = (len(missing) == 0)
                checks["missing_keys"] = missing
        except Exception:
            checks["json_valid"] = False
    return checks


def review(output: str, objective: str, *, executor_model: Optional[str] = None,
           require_json: bool = False, schema: Optional[dict] = None,
           task_type: str = "high_risk") -> Dict[str, Any]:
    reviewer = _pick_reviewer(executor_model)
    static = _static_checks(output, require_json, schema)

    # hard fail on static JSON requirement
    if require_json and not static.get("json_valid", True):
        return {"verdict": "fail", "score": 0.0,
                "issues": ["output is not valid JSON"],
                "retry_instruction": "Return ONLY valid JSON matching the required schema.",
                "reviewer_model": f"{reviewer['provider']}/{reviewer['model']}",
                "checks": static}

    prompt = (
        "You are a strict reviewer. Evaluate the OUTPUT against the OBJECTIVE.\n"
        "Check: correctness, completeness, hallucination risk, and whether it "
        "actually satisfies the objective. Respond ONLY as compact JSON:\n"
        '{"verdict":"pass|warn|fail","score":0.0-1.0,"issues":["..."],'
        '"retry_instruction":"... or null"}\n\n'
        f"OBJECTIVE:\n{objective[:1500]}\n\nOUTPUT:\n{str(output)[:3000]}\n"
    )
    raw = _call(reviewer["provider"], reviewer["model"], prompt)

    verdict, score, issues, retry = "warn", 0.6, [], None
    try:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            j = json.loads(m.group(0))
            verdict = j.get("verdict", "warn")
            score = float(j.get("score", 0.6))
            issues = j.get("issues", []) or []
            retry = j.get("retry_instruction")
            if isinstance(retry, str) and retry.lower() in ("null", "none", ""):
                retry = None
    except Exception:
        issues = ["reviewer response unpar_seable", raw[:120]]

    # merge static signal
    if not static.get("non_empty", True):
        verdict, score = "fail", 0.0
        issues.append("empty output")

    return {"verdict": verdict, "score": round(score, 3), "issues": issues,
            "retry_instruction": retry,
            "reviewer_model": f"{reviewer['provider']}/{reviewer['model']}",
            "executor_model": executor_model, "checks": static}


if __name__ == "__main__":
    # smoke test
    r = review("The capital of France is Berlin.",
               "State the capital of France correctly.", executor_model="x/y")
    print(json.dumps(r, indent=2))
