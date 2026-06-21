#!/usr/bin/env python3
"""
ILMA Super Coding Command Center v2.0
=====================================
Military Grade Coding Orchestrator — NO OLLAMA, NO OPENCLAW EXECUTION.

Uses ILMA Smart Model Router (AYDA-powered) for model selection.
Uses ILMA Judge System for verification.
Supports external coding tools: Claude Code, OpenCode, Codex, Gemini.

Rules:
1. FREE_TIER_FIRST — nvidia > alibaba > openrouter > minimax (ENFORCED)
2. NO OLLAMA
3. NO OPENCLAW EXECUTION
4. NO SAME MODEL REPETITION (30-min window)
5. Judge verification before final output

Usage:
    python3 ilma_super_coding_command_center.py code --task "build API"
    python3 ilma_super_coding_command_center.py verify --file mycode.py
    python3 ilma_super_coding_command_center.py status
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# ILMA paths - use environment variable with fallback
ILMA_PROFILE = Path(os.environ.get("ILMA_PROFILE", "/root/.hermes/profiles/ilma"))
WORKSPACE = ILMA_PROFILE

# Import ILMA components
sys.path.insert(0, str(WORKSPACE))
try:
    from ilma_model_router import route_task, get_router_stats, list_free_models
    from ilma_judge_system import verify_file, ALL_LEVELS
    HAS_ROUTER = True
except ImportError as e:
    HAS_ROUTER = False
    logger.warning(f"Model router unavailable: {e}")

# === CONSTANTS ===
SUPPORTED_TOOLS = ["claude", "opencode", "codex", "gemini"]
FREE_PROVIDERS = ["nvidia", "alibaba", "openrouter", "deepseek", "meta"]
BANNED_PROVIDERS = ["blackbox", "perplexity", "ollama"]
BANNED_TOOLS = ["ollama"]


# === UTILITY FUNCTIONS ===

def is_tool_available(tool: str) -> bool:
    """Check if external coding tool is available."""
    result = subprocess.run(
        ["which", tool],
        capture_output=True, text=True
    )
    return result.returncode == 0


def get_available_tools() -> List[str]:
    """Get list of available external coding tools."""
    available = []
    for tool in SUPPORTED_TOOLS:
        if is_tool_available(tool):
            available.append(tool)
    return available


def run_claude(task: str, output_dir: Optional[str] = None) -> Dict[str, Any]:
    """Run Claude Code CLI for coding task."""
    try:
        cmd = ["claude", "--print", f"--model", "claude-sonnet-4-20250514", "--no-input", task]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300
        )
        return {
            "tool": "claude",
            "success": result.returncode == 0,
            "output": result.stdout[:2000] if result.stdout else "",
            "error": result.stderr[:500] if result.stderr else "",
            "returncode": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {"tool": "claude", "success": False, "error": "Timeout after 300s"}
    except Exception as e:
        return {"tool": "claude", "success": False, "error": str(e)}


def run_opencode(task: str) -> Dict[str, Any]:
    """Run OpenCode CLI."""
    try:
        cmd = ["opencode", "--help"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return {
            "tool": "opencode",
            "available": result.returncode == 0,
            "version": result.stdout[:100] if result.stdout else ""
        }
    except Exception as e:
        return {"tool": "opencode", "available": False, "error": str(e)}


def run_codex(task: str) -> Dict[str, Any]:
    """Run OpenAI Codex CLI."""
    try:
        cmd = ["codex", "--version"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return {
            "tool": "codex",
            "available": result.returncode == 0,
            "output": result.stdout[:200] if result.stdout else ""
        }
    except Exception as e:
        return {"tool": "codex", "available": False, "error": str(e)}


def run_gemini(task: str) -> Dict[str, Any]:
    """Run Gemini CLI."""
    try:
        cmd = ["gemini", "--version"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return {
            "tool": "gemini",
            "available": result.returncode == 0,
            "output": result.stdout[:200] if result.stdout else ""
        }
    except Exception as e:
        return {"tool": "gemini", "available": False, "error": str(e)}


def judge_code(code: str, task: str) -> Dict[str, Any]:
    """Judge code quality using ILMA Judge System."""
    if not HAS_ROUTER:
        return {"success": False, "error": "Judge unavailable"}

    try:
        # Write code to temp file
        temp_file = WORKSPACE / f".temp_judge_{int(time.time())}.py"
        temp_file.write_text(code)

        # Verify
        report = verify_file(str(temp_file), levels=ALL_LEVELS[:6])

        # Clean up
        temp_file.unlink(missing_ok=True)

        return {
            "success": True,
            "verdict": report["verdict"],
            "score": report["score"],
            "levels_verified": report["levels_verified"],
            "results": report["results"]
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def select_model_for_task(task: str) -> Dict[str, Any]:
    """Select best model for task using ILMA Smart Router."""
    if not HAS_ROUTER:
        return {"error": "Model router unavailable"}

    try:
        route = route_task(task)
        return {
            "success": True,
            "task_type": route["task_type"],
            "primary_model": route["route"]["model_id"],
            "primary_provider": route["route"]["provider"],
            "primary_score": route["route"]["score"],
            "fallback_count": len(route.get("fallback_chain", [])),
            "routing_method": route.get("routing_method", "unknown")
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def generate_coding_plan(task: str) -> Dict[str, Any]:
    """Generate plan for coding task."""
    plan = {
        "task": task,
        "generated_at": datetime.now().isoformat(),
        "steps": [],
        "estimated_models": [],
        "tools_needed": [],
        "verification_levels": []
    }

    # Analyze task complexity
    task_lower = task.lower()
    if any(w in task_lower for w in ["heavy", "fullstack", "platform", "system", "complex"]):
        plan["complexity"] = "high"
        plan["steps"] = [
            "1. Research architecture",
            "2. Design data model",
            "3. Implement core modules",
            "4. Write tests",
            "5. Security review",
            "6. Integration test",
            "7. Performance test"
        ]
        plan["verification_levels"] = ["L1", "L2", "L5", "L6", "L7", "L8"]
    elif any(w in task_lower for w in ["api", "endpoint", "crud", "backend"]):
        plan["complexity"] = "medium"
        plan["steps"] = [
            "1. Define API spec",
            "2. Implement endpoint",
            "3. Add validation",
            "4. Write tests"
        ]
        plan["verification_levels"] = ["L1", "L2", "L5", "L8"]
    else:
        plan["complexity"] = "low"
        plan["steps"] = [
            "1. Implement solution",
            "2. Quick verification"
        ]
        plan["verification_levels"] = ["L1", "L5"]

    # Add tool recommendations
    available_tools = get_available_tools()
    plan["tools_needed"] = available_tools[:2] if len(available_tools) >= 2 else available_tools

    return plan


# === CLI COMMANDS ===

def cmd_status(args):
    """Display system status including model router, external tools, and judge system.

    Shows:
        - Model router statistics (providers, models, free models, DB size)
        - Availability of external coding tools (claude, opencode, codex, gemini)
        - Judge system availability
        - Active rules configuration
    """
    logger.info("=" * 60)
    logger.info("ILMA Super Coding Command Center v2.0")
    logger.info("=" * 60)

    # Model router status
    logger.info("\n📊 Model Router:")
    if HAS_ROUTER:
        stats = get_router_stats()
        logger.info(f"  Providers: {stats['total_providers']}")
        logger.info(f"  Models: {stats['total_models']}")
        logger.info(f"  Free: {stats['free_models']}")
        logger.info(f"  DB Size: {stats['db_size_mb']} MB")
    else:
        logger.warning("  ❌ Unavailable")

    # External tools status
    logger.info("\n🔧 External Coding Tools:")
    available = get_available_tools()
    for tool in SUPPORTED_TOOLS:
        if tool in available:
            logger.info(f"  ✅ {tool}")
        else:
            logger.warning(f"  ❌ {tool} (not found)")

    # Judge status
    logger.info("\n⚖️ Judge System:")
    if HAS_ROUTER:
        logger.info("  ✅ Available")
    else:
        logger.warning("  ❌ Unavailable")

    logger.info("\n📋 Rules:")
    logger.info("  ✅ FREE_TIER_FIRST (nvidia > alibaba > openrouter > minimax)")
    logger.info("  ✅ NO_OLLAMA")
    logger.info("  ✅ NO_OPENCLAW_EXECUTION")
    logger.info("  ✅ NO_SAME_MODEL_REPETITION (30-min window)")
    logger.info("  ✅ JUDGE_VERIFICATION")

    logger.info("=" * 60)


def cmd_model(args):
    """Analyze task and show recommended model selection.

    Uses ILMA Smart Router to determine the best model for the given task,
    including primary selection and fallback chain information.
    """
    logger.info(f"🔍 Analyzing task: {args.task}")
    result = select_model_for_task(args.task)

    if result.get("success"):
        logger.info("\n📋 Model Selection:")
        logger.info(f"  Task Type: {result['task_type']}")
        logger.info(f"  Primary: {result['primary_model']} ({result['primary_provider']})")
        logger.info(f"  Score: {result['primary_score']:.4f}")
        logger.info(f"  Fallbacks: {result['fallback_count']}")
        logger.info(f"  Method: {result['routing_method']}")
    else:
        logger.error(f"❌ Error: {result.get('error', 'Unknown')}")


def cmd_list_models(args):
    """List available free models, optionally filtered by task type."""
    models = list_free_models(args.task if args.task else None)
    logger.info(f"📋 Free Models ({len(models)} available)")
    for m in models[:20]:
        logger.info(f"  [{m['provider']}] {m['model_id']} | Q:{m.get('quality_score', 0):.2f} C:{m.get('coding_score', 0):.2f}")
    if len(models) > 20:
        logger.info(f"  ... and {len(models) - 20} more")


def cmd_verify(args):
    """Verify code file using ILMA Judge System.

    Performs multi-level verification on the specified code file,
    checking syntax, security, best practices, and performance.
    """
    logger.info(f"⚖️ Verifying: {args.file}")

    # Check if file exists
    file_path = Path(args.file)
    if not file_path.exists():
        logger.error(f"❌ File not found: {args.file}")
        return

    # Run verification
    if HAS_ROUTER:
        report = verify_file(str(file_path), levels=ALL_LEVELS[:6] if not args.full else ALL_LEVELS)
        logger.info(f"\n📋 Verification Result:")
        logger.info(f"  Verdict: {report['verdict']}")
        logger.info(f"  Score: {report['score']:.2%}")
        logger.info(f"  Levels: {', '.join(report['levels_verified'])}")
        logger.info(f"  Time: {report['elapsed_seconds']}s")

        for r in report["results"]:
            status_icon = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️", "ERROR": "❗"}.get(r["status"], "?")
            logger.info(f"  {status_icon} {r['level']}: {r['message']}")
    else:
        logger.error("❌ Judge system unavailable")


def cmd_plan(args):
    """Generate a coding plan for the given task.

    Analyzes task complexity and generates appropriate steps,
    verification levels, and tool recommendations.
    """
    logger.info(f"📝 Generating plan for: {args.task}")
    plan = generate_coding_plan(args.task)

    logger.info(f"\n📋 Coding Plan:")
    logger.info(f"  Complexity: {plan['complexity']}")
    logger.info(f"  Generated: {plan['generated_at']}")
    logger.info(f"\n  Steps:")
    for step in plan["steps"]:
        logger.info(f"    {step}")
    logger.info(f"\n  Verification Levels: {', '.join(plan['verification_levels'])}")
    logger.info(f"\n  Tools: {', '.join(plan['tools_needed']) if plan['tools_needed'] else 'None available'}")


def cmd_judge(args):
    """Judge code quality from file, URL, or direct input.

    Uses ILMA Judge System to evaluate code quality, returning
    a verdict and score based on multi-level checks.
    """
    logger.info(f"⚖️ Judging code from: {args.source}")

    if args.source.startswith("http"):
        # Fetch from URL
        logger.info("Fetching from URL...")
        # (Implementation would use urllib)
    else:
        # Read from file or stdin
        code = Path(args.source).read_text() if Path(args.source).exists() else args.source

    result = judge_code(code, args.task)

    if result.get("success"):
        logger.info(f"\n📋 Judge Result:")
        logger.info(f"  Verdict: {result['verdict']}")
        logger.info(f"  Score: {result['score']:.2%}")
    else:
        logger.error(f"❌ Error: {result.get('error', 'Unknown')}")


def cmd_claudecode(args):
    """Phase 71: Use the ClaudeCode-Style Parallel Coding Agent.

    Default behavior (Bos command 2026-06-04):
      - Tier 1: NVIDIA NIM
      - Tier 2: OpenRouter free
      - Tier 3: BlackBox free
    """
    try:
        from ilma_claudecode_agent import (
            CodingTaskSpec, execute_parallel, get_status, PRIORITY_STACK,
        )
    except ImportError as e:
        logger.error(f"❌ ClaudeCode agent unavailable: {e}")
        return

    if args.status:
        import json as _j
        logger.info(_j.dumps(get_status(), indent=2))
        return

    if args.list_models:
        import json as _j
        out = [{"tier": e["tier"], "name": e["name"], "provider": e["provider"],
                "default_model": e["default_model"], "fallback_count": len(e["fallback_models"])}
               for e in PRIORITY_STACK]
        logger.info(_j.dumps(out, indent=2))
        return

    parallel = args.parallel
    tier = args.tier
    prefer = args.prefer
    logger.info(f"🚀 ClaudeCode Agent — parallel={parallel} tier={tier} prefer={prefer}")
    logger.info("=" * 60)

    spec = CodingTaskSpec(
        task=args.task,
        tier=tier,
        parallel_count=parallel,
        prefer_provider=prefer,
    )
    result = execute_parallel(spec)

    # Print summary
    logger.info(f"\n{'='*70}")
    logger.info(f"PARALLEL CODING RESULT — {result.total_latency_s}s total")
    logger.info(f"{'='*70}")
    for r in result.parallel_results:
        status = "✅" if r.success else "❌"
        logger.info(f"  {status} TIER {r.tier} {r.name:18} score={r.judge_score}/5  "
                    f"verdict={r.judge_verdict}  latency={r.latency_s}s  "
                    f"len={r.content_length}  code_blocks={r.has_code_blocks}")

    if result.winner:
        logger.info(f"\n🏆 WINNER: TIER {result.winner.tier} {result.winner.name} — {result.winner.model}")
        logger.info(f"\n{'─'*70}")
        # Print first 2000 chars of winning content
        out = result.final_content[:2000] if result.final_content else ""
        if len(result.final_content) > 2000:
            out += f"\n... (truncated, full content: {len(result.final_content)} chars)"
        logger.info(out)
    else:
        logger.error(f"\n❌ ALL MODELS FAILED")
        logger.error(result.final_content)

    logger.info(f"\nEvidence: {result.evidence_id}")


# === MAIN ===
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="ILMA Super Coding Command Center v2.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  status        Show system status
  model         Show recommended model for task
  list-models   List free models
  verify        Verify code file
  plan          Generate coding plan
  judge         Judge code quality

Examples:
  python3 ilma_super_coding_command_center.py status
  python3 ilma_super_coding_command_center.py model "build a REST API"
  python3 ilma_super_coding_command_center.py verify mycode.py
  python3 ilma_super_coding_command_center.py plan "implement user authentication"
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # status
    subparsers.add_parser("status", help="Show system status")

    # model
    model_parser = subparsers.add_parser("model", help="Show recommended model")
    model_parser.add_argument("task", help="Task description")
    model_parser.add_argument("--json", action="store_true", help="JSON output")

    # list-models
    list_parser = subparsers.add_parser("list-models", help="List free models")
    list_parser.add_argument("task", nargs="?", help="Task type (optional)")

    # verify
    verify_parser = subparsers.add_parser("verify", help="Verify code file")
    verify_parser.add_argument("file", help="File to verify")
    verify_parser.add_argument("--full", action="store_true", help="Full verification")
    verify_parser.add_argument("--json", action="store_true", help="JSON output")

    # plan
    plan_parser = subparsers.add_parser("plan", help="Generate coding plan")
    plan_parser.add_argument("task", help="Task description")
    plan_parser.add_argument("--json", action="store_true", help="JSON output")

    # judge
    judge_parser = subparsers.add_parser("judge", help="Judge code")
    judge_parser.add_argument("source", help="Code file or URL")
    judge_parser.add_argument("--task", default="general", help="Task type")
    judge_parser.add_argument("--json", action="store_true", help="JSON output")

    # claudecode (Phase 71 — default coding agent)
    cc_parser = subparsers.add_parser(
        "claudecode", aliases=["cc"],
        help="Phase 71: ClaudeCode-Style Parallel Coding Agent (default)"
    )
    cc_parser.add_argument("task", nargs="?", default="", help="Coding task description")
    cc_parser.add_argument("--parallel", type=int, default=3, help="How many models in parallel (1-4)")
    cc_parser.add_argument("--tier", default="L2_medium", help="L1_light | L2_medium | L3_heavy | L4_super_heavy")
    cc_parser.add_argument("--prefer", help="Prefer specific provider (nvidia|openrouter|blackbox|minimax|xai|groq|together)")
    cc_parser.add_argument("--status", action="store_true", help="Show agent status")
    cc_parser.add_argument("--list-models", action="store_true", help="List priority stack")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Dispatch
    if args.command == "status":
        cmd_status(args)
    elif args.command == "model":
        cmd_model(args)
    elif args.command == "list-models":
        cmd_list_models(args)
    elif args.command == "verify":
        cmd_verify(args)
    elif args.command == "plan":
        cmd_plan(args)
    elif args.command == "judge":
        cmd_judge(args)
    elif args.command in ("claudecode", "cc"):
        if not args.task and not args.status and not args.list_models:
            cc_parser.print_help()
            sys.exit(0)
        cmd_claudecode(args)
    else:
        logger.error(f"Unknown command: {args.command}")
        parser.print_help()
        sys.exit(1)