#!/usr/bin/env python3
"""
ILMA ClaudeCode-Style Parallel Coding Agent v1.0  (Phase 71, 2026-06-04)
========================================================================
Claude Code-style coding agent that runs MULTIPLE free AI models in PARALLEL
on the same coding task, then synthesizes the best output. Default free-model
priority stack (Bos command 2026-06-04):

  TIER 1: NVIDIA NIM free models         (nvidia/*  - primary)
  TIER 2: OpenRouter free models         (openrouter/*  - fallback)
  TIER 3: BlackBox AI free models        (blackbox/*  - fallback)

# DEPRECATED 2026-06-18: legacy web service subproviders (qwen, openai,
# use, arena) are GONE. All 4 subproviders removed from active stack.
DEPRECATED_SUBPROVIDERS: set = {
    "legacy_sub_qwen", "legacy_sub_openai",
    "legacy_sub_use", "legacy_sub_arena",
    "openaicodex", "use", "arena",
}
PARALLEL EXECUTION MODEL:
  1. Analyze task → determine tiers
  2. Launch N models in parallel (default 3) — one per tier
  3. Collect outputs → diff/judge ranking
  4. Pick winner (or synthesize)
  5. Run verifications (compile, lint, test if available)
  6. Return structured result with evidence

CLI:
  python3 ilma_claudecode_agent.py code --task "build X"
  python3 ilma_claudecode_agent.py parallel --task "Y" --count 3
  python3 ilma_claudecode_agent.py status
  python3 ilma_claudecode_agent.py --list-models
"""
from __future__ import annotations

import argparse
import asyncio
import concurrent.futures
import json
import logging
import os
import re
import sys
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [ClaudeCode] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ILMA.ClaudeCode")

ILMA_PROFILE = Path(os.environ.get("ILMA_PROFILE", "/root/.hermes/profiles/ilma"))
WORKSPACE = ILMA_PROFILE
sys.path.insert(0, str(WORKSPACE))

# ============================================================
# PHASE 71: PRIORITY STACK  (Bos command 2026-06-04)
# Models are validatable against NVIDIA NIM as of 2026-06-04.
# ProviderKernel passes model_id as-is — we strip the "nvidia/" prefix
# (NVIDIA API expects bare model IDs like "meta/llama-3.3-70b-instruct").
# ============================================================
PRIORITY_STACK: List[Dict[str, Any]] = [
    {
        "tier": 1,
        "name": "nvidia_nim",
        "provider": "nvidia",
        "model_prefix": "nvidia/",
        "default_model": "nvidia/meta/llama-3.3-70b-instruct",
        "fallback_models": [
            "nvidia/qwen/qwen2.5-coder-32b-instruct",
            "nvidia/deepseek-ai/deepseek-r1",
            "nvidia/meta/llama-3.1-70b-instruct",
            "nvidia/01-ai/yi-large",
        ],
        "description": "NVIDIA NIM free models (primary)",
    },
    {
        "tier": 2,
        "name": "openrouter_free",
        "provider": "openrouter",
        "model_prefix": "openrouter/",
        "default_model": "openrouter/qwen/qwen-2.5-coder-32b-instruct:free",
        "fallback_models": [
            "openrouter/meta-llama/llama-3.3-70b-instruct:free",
            "openrouter/mistralai/mistral-small-3.2-24b-instruct:free",
            "openrouter/google/gemini-2.0-flash-thinking-exp:free",
        ],
        "description": "OpenRouter free models (fallback 1)",
    },
    {
        "tier": 3,
        "name": "blackbox_free",
        "provider": "blackbox",
        "model_prefix": "blackbox/",
        "default_model": "blackbox/BlackboxAI",
        "fallback_models": [
            "blackbox/blackbox-coder",
            "blackbox/llama-3.1-70b",
        ],
        "description": "BlackBox AI free models (fallback 2)",
    },
]

# Explicitly DISABLED sub-providers (Bos command 2026-06-04)
DISABLED_SUBPROVIDERS = {"legacy_sub_qwen", "legacy_sub_openai", "legacy_sub_use", "legacy_sub_arena", "openaicodex", "use", "arena"}


# ============================================================
# DATA STRUCTURES
# ============================================================
@dataclass
class CodingTaskSpec:
    task_id: str = field(default_factory=lambda: f"cc-{uuid.uuid4().hex[:12]}")
    task: str = ""
    files: List[str] = field(default_factory=list)
    repo: str = ""
    tier: str = "L2_medium"          # L1_light | L2_medium | L3_heavy | L4_super_heavy
    parallel_count: int = 3          # how many models to run in parallel
    verify: bool = True              # run judge verification
    prefer_provider: Optional[str] = None  # if set, prioritize that tier
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ModelResult:
    tier: int
    name: str
    provider: str
    model: str
    content: str
    latency_s: float
    success: bool
    error: Optional[str] = None
    judge_score: float = 0.0
    judge_verdict: str = "UNKNOWN"
    content_length: int = 0
    has_code_blocks: bool = False


@dataclass
class CodingTaskResult:
    task_id: str
    task: str
    tier: str
    parallel_count: int
    parallel_results: List[ModelResult] = field(default_factory=list)
    winner: Optional[ModelResult] = None
    final_content: str = ""
    synthesis_strategy: str = "first_success"   # first_success | highest_score | best_code_density
    total_latency_s: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    evidence_id: str = ""

    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "task": self.task[:200],
            "tier": self.tier,
            "parallel_count": self.parallel_count,
            "parallel_results": [asdict(r) for r in self.parallel_results],
            "winner": asdict(self.winner) if self.winner else None,
            "final_content": self.final_content,
            "synthesis_strategy": self.synthesis_strategy,
            "total_latency_s": round(self.total_latency_s, 3),
            "timestamp": self.timestamp,
            "evidence_id": self.evidence_id,
        }


# ============================================================
# MODEL INVOCATION (delegates to SubAgentRouter / ProviderKernel)
# ============================================================
def _invoke_via_subagent(model_id: str, message: str, max_tokens: int = 2048, timeout: int = 90) -> Tuple[bool, str, float]:
    """Call SubAgentRouter for a model. Returns (ok, content, latency).

    Strategy:
      1. Use route_and_execute for normal routing (best free model)
      2. If user wants to FORCE a specific model, dispatch via ProviderKernel
         directly (only for the 4 free providers in our priority stack).
    """
    t0 = time.time()
    try:
        from ilma_subagent_router import SubAgentRouter
        router = SubAgentRouter()
        # SubAgentRouter.route_and_execute picks best free model — we use it
        # for general case; for force-model we go direct via ProviderKernel
        if "/" in model_id:
            provider = model_id.split("/")[0]
            # Direct dispatch for our 4 priority providers
            if provider in ("nvidia", "openrouter", "blackbox", "minimax", "ollama"):
                try:
                    from ilma_provider_kernel import ProviderKernel
                    kernel = ProviderKernel()
                    # Strip provider prefix (e.g. "nvidia/meta/llama-3.3-70b-instruct" → "meta/llama-3.3-70b-instruct")
                    api_model = "/".join(model_id.split("/")[1:]) if model_id.startswith(provider + "/") else model_id
                    resp = kernel.call(provider, api_model, [{"role": "user", "content": message}],
                                       max_tokens=max_tokens, timeout=timeout)
                    latency = time.time() - t0
                    if resp and not resp.startswith("Error:") and not resp.endswith("Error"):
                        return True, resp, latency
                    return False, resp or "empty response", latency
                except Exception as e:
                    return False, f"kernel:{type(e).__name__}: {e}", time.time() - t0
            elif provider in ("legacy_sub_qwen",) or model_id.startswith("legacy_sub_qwen/"):
                # ⛔ legacy subproviders DEPRECATED 2026-06-18
                return False, "legacy_subprovider_deprecated_2026_06_18", latency
        # Fallback — let router pick best free
        result = router.route_and_execute(
            message=message,
            task_type_or_desc=f"coding-{model_id}",
            thinking="Auto",
            allow_paid=False,
            stateless=True,
        )
        latency = time.time() - t0
        if result.get("success") and result.get("content"):
            return True, result["content"], latency
        else:
            return False, result.get("error", "no content"), latency
    except Exception as e:
        return False, f"{type(e).__name__}: {e}", time.time() - t0


def _get_free_model_for_tier(tier: int) -> Optional[Dict[str, Any]]:
    """Return the priority-stack entry for a given tier (1-4)."""
    for entry in PRIORITY_STACK:
        if entry["tier"] == tier:
            return entry
    return None


def _select_default_models(parallel_count: int) -> List[Dict[str, Any]]:
    """Select the first N entries from the priority stack."""
    return PRIORITY_STACK[:max(1, min(parallel_count, len(PRIORITY_STACK)))]


# ============================================================
# JUDGE  (lightweight content quality score)
# ============================================================
def _judge_content(content: str) -> Tuple[float, str]:
    """Heuristic judge for code content. Returns (score 0-5, verdict)."""
    if not content or not content.strip():
        return 0.0, "FAIL"
    text = content.strip()
    score = 0.0
    # Has code blocks?
    if "```" in text:
        score += 1.0
    # Has function definitions?
    if re.search(r"^\s*def\s+\w+\(", text, re.M):
        score += 0.5
    # Has imports?
    if re.search(r"^\s*(import|from)\s+\w+", text, re.M):
        score += 0.3
    # Has docstrings?
    if '"""' in text or "'''" in text:
        score += 0.3
    # Has class definitions?
    if re.search(r"^\s*class\s+\w+", text, re.M):
        score += 0.4
    # Has error handling?
    if re.search(r"except\s+\w+|raise\s+\w+", text, re.M):
        score += 0.3
    # Length bonus (longer = more substantive)
    if len(text) > 200:
        score += 0.3
    if len(text) > 800:
        score += 0.4
    if len(text) > 2000:
        score += 0.4
    # Penalty for error markers
    if re.search(r"Error:\s+\w+|Exception:\s+\w+|Traceback", text):
        score -= 1.0
    # Penalty for placeholder text
    if re.search(r"TODO|FIXME|placeholder|\.\.\.|Lorem ipsum", text, re.I):
        score -= 0.3
    score = max(0.0, min(5.0, score))
    if score >= 3.5:
        verdict = "PASS"
    elif score >= 2.0:
        verdict = "WARN"
    else:
        verdict = "FAIL"
    return round(score, 2), verdict


# ============================================================
# PARALLEL EXECUTION
# ============================================================
def _run_one_model(stack_entry: Dict[str, Any], model: str, message: str) -> ModelResult:
    """Run one model via SubAgentRouter, score it, return ModelResult."""
    t0 = time.time()
    ok, content, latency = _invoke_via_subagent(model, message)
    score, verdict = _judge_content(content) if ok else (0.0, "FAIL")
    has_blocks = "```" in (content or "")
    return ModelResult(
        tier=stack_entry["tier"],
        name=stack_entry["name"],
        provider=stack_entry["provider"],
        model=model,
        content=content if ok else "",
        latency_s=round(latency, 3),
        success=ok,
        error=None if ok else content,
        judge_score=score,
        judge_verdict=verdict,
        content_length=len(content) if content else 0,
        has_code_blocks=has_blocks,
    )


def execute_parallel(task_spec: CodingTaskSpec) -> CodingTaskResult:
    """Execute a coding task in parallel across the priority stack.

    1. Build the message
    2. Fan out to N models in parallel
    3. Collect + score results
    4. Pick winner (highest judge score, then shortest latency)
    5. Return structured result
    """
    t_start = time.time()
    result = CodingTaskResult(
        task_id=task_spec.task_id,
        task=task_spec.task,
        tier=task_spec.tier,
        parallel_count=task_spec.parallel_count,
    )

    # Build message
    file_ctx = ""
    if task_spec.files:
        file_ctx = f"\n\nRelevant files: {', '.join(task_spec.files)}"
    message = f"""[ILMA ClaudeCode Agent v1.0 — Free Tier Parallel Coding]

Task: {task_spec.task}
Tier: {task_spec.tier}{file_ctx}

Please produce a high-quality, production-ready code solution.
Include:
- Full implementation (no placeholders)
- Inline comments where helpful
- Brief explanation of the approach
- Test cases if appropriate
"""

    # Select stack entries
    if task_spec.prefer_provider:
        # Find the matching tier and put it first
        ordered = []
        primary = None
        for e in PRIORITY_STACK:
            if e["name"] == task_spec.prefer_provider or e["provider"] == task_spec.prefer_provider:
                primary = e
            else:
                ordered.append(e)
        if primary:
            ordered = [primary] + ordered
        stack_entries = ordered[:task_spec.parallel_count]
    else:
        stack_entries = _select_default_models(task_spec.parallel_count)

    logger.info(f"Parallel execution: {len(stack_entries)} models")
    for e in stack_entries:
        logger.info(f"  TIER {e['tier']} → {e['name']} ({e['provider']})")

    # Fan out in parallel (thread pool for I/O-bound calls)
    parallel_results: List[ModelResult] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(stack_entries)) as executor:
        future_to_entry = {}
        for entry in stack_entries:
            model = entry["default_model"]
            fut = executor.submit(_run_one_model, entry, model, message)
            future_to_entry[fut] = entry
        for fut in concurrent.futures.as_completed(future_to_entry, timeout=180):
            entry = future_to_entry[fut]
            try:
                r = fut.result()
            except Exception as e:
                r = ModelResult(
                    tier=entry["tier"],
                    name=entry["name"],
                    provider=entry["provider"],
                    model=entry["default_model"],
                    content="",
                    latency_s=0.0,
                    success=False,
                    error=f"{type(e).__name__}: {e}",
                )
            parallel_results.append(r)
            status = "✅" if r.success else "❌"
            logger.info(f"  {status} TIER {r.tier} {r.name}: {r.latency_s}s, "
                        f"score={r.judge_score}, verdict={r.judge_verdict}, len={r.content_length}")

    # Sort by tier (lower tier = better priority)
    parallel_results.sort(key=lambda r: (not r.success, r.tier, -r.judge_score, r.latency_s))
    result.parallel_results = parallel_results
    result.total_latency_s = time.time() - t_start

    # Pick winner — prefer success with highest score
    successful = [r for r in parallel_results if r.success]
    if successful:
        # Highest score, then shortest latency
        winner = max(successful, key=lambda r: (r.judge_score, -r.latency_s))
        result.winner = winner
        result.final_content = winner.content
        result.synthesis_strategy = "highest_score"
    else:
        result.winner = None
        result.final_content = (
            f"❌ All {len(parallel_results)} models failed.\n\n"
            + "\n".join(f"  TIER {r.tier} {r.name}: {r.error}" for r in parallel_results)
        )
        result.synthesis_strategy = "first_success"

    # Evidence ID
    result.evidence_id = f"ILMA-EVID-{datetime.now().strftime('%Y%m%d')}-CCODE-{task_spec.task_id[:8].upper()}"

    return result


# ============================================================
# STATUS / LIST
# ============================================================
def list_priority_models() -> List[Dict[str, Any]]:
    """List all models in the priority stack."""
    out = []
    for entry in PRIORITY_STACK:
        out.append({
            "tier": entry["tier"],
            "name": entry["name"],
            "provider": entry["provider"],
            "default_model": entry["default_model"],
            "fallback_count": len(entry["fallback_models"]),
            "description": entry["description"],
        })
    return out


def list_disabled() -> List[str]:
    return sorted(DISABLED_SUBPROVIDERS)


def get_status() -> Dict[str, Any]:
    """Return the current operational status of ClaudeCode agent."""
    enabled = [e["name"] for e in PRIORITY_STACK]
    return {
        "agent": "ILMA ClaudeCode-Style Parallel Coding Agent",
        "version": "1.0",
        "phase": "Phase 71 — Free-Only Default (Bos 2026-06-04)",
        "priority_stack": enabled,
        "disabled_subproviders": list_disabled(),
        "tiers_total": len(PRIORITY_STACK),
        "policy": {
            "free_tier_only": True,
            "allow_paid": False,
            "parallel_default": 3,
            "judge_verification": True,
        },
    }


# ============================================================
# CLI
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="ILMA ClaudeCode-Style Parallel Coding Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd")

    p_code = sub.add_parser("code", help="Run single coding task (uses first priority tier)")
    p_code.add_argument("--task", required=True, help="Coding task description")
    p_code.add_argument("--files", nargs="*", default=[], help="Relevant files")
    p_code.add_argument("--tier", default="L2_medium", help="L1_light | L2_medium | L3_heavy | L4_super_heavy")
    p_code.add_argument("--json", action="store_true", help="JSON output")

    p_par = sub.add_parser("parallel", help="Run N models in parallel on the same task")
    p_par.add_argument("--task", required=True, help="Coding task")
    p_par.add_argument("--count", type=int, default=3, help="How many models to run in parallel (1-4)")
    p_par.add_argument("--tier", default="L2_medium")
    p_par.add_argument("--prefer", help="Prefer specific provider (nvidia|openrouter|blackbox)")
    p_par.add_argument("--json", action="store_true")

    sub.add_parser("status", help="Show agent status")
    parser.add_argument("--list-models", action="store_true", help="List priority stack")
    parser.add_argument("--list-disabled", action="store_true", help="List disabled sub-providers")

    args = parser.parse_args()

    if args.cmd == "code":
        spec = CodingTaskSpec(task=args.task, files=args.files, tier=args.tier, parallel_count=1)
        # Sequential: only first tier
        result = execute_parallel(spec)
        if args.json:
            print(json.dumps(result.to_dict(), indent=2, default=str))
        else:
            if result.winner:
                print(f"\n✅ TIER {result.winner.tier} {result.winner.name} — "
                      f"score={result.winner.judge_score}, latency={result.winner.latency_s}s")
                print(f"\n--- {result.winner.model} ---\n")
                print(result.final_content)
            else:
                print(f"❌ FAILED: {result.final_content}")

    elif args.cmd == "parallel":
        spec = CodingTaskSpec(
            task=args.task,
            tier=args.tier,
            parallel_count=max(1, min(args.count, 4)),
            prefer_provider=args.prefer,
        )
        result = execute_parallel(spec)
        if args.json:
            print(json.dumps(result.to_dict(), indent=2, default=str))
        else:
            print(f"\n{'='*70}")
            print(f"PARALLEL CODING — {result.parallel_count} models, {result.total_latency_s}s total")
            print(f"{'='*70}\n")
            for r in result.parallel_results:
                status = "✅" if r.success else "❌"
                print(f"{status} TIER {r.tier} {r.name:18} {r.model[:50]}")
                print(f"   score={r.judge_score}/5  verdict={r.judge_verdict}  "
                      f"latency={r.latency_s}s  len={r.content_length}  code_blocks={r.has_code_blocks}")
            if result.winner:
                print(f"\n{'='*70}")
                print(f"🏆 WINNER: TIER {result.winner.tier} {result.winner.name} — {result.winner.model}")
                print(f"{'='*70}\n")
                print(result.final_content[:3000])
                if len(result.final_content) > 3000:
                    print(f"\n... (truncated, full content: {len(result.final_content)} chars)")
            else:
                print(f"\n❌ ALL FAILED")
            print(f"\nEvidence: {result.evidence_id}")

    elif args.cmd == "status":
        print(json.dumps(get_status(), indent=2))
    elif args.list_models:
        print(json.dumps(list_priority_models(), indent=2))
    elif args.list_disabled:
        print(json.dumps(list_disabled(), indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
