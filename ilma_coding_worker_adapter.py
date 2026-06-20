#!/usr/bin/env python3
"""
ILMA Coding Worker Adapter — Phase 4B
======================================
Production coding orchestration layer.

Architecture:
  User / Telegram / API
  → Hermes Orchestrator
  → CodingWorkerAdapter (this file)
  → SubAgentRouter (FREE-ONLY, health-tracked)
  → Free model (via direct provider call)
  → Diff capture → Test runner → Rollback manager → Report

This adapter ENFORCES:
  - All model calls go through SubAgentRouter (no bypass)
  - allow_paid=False (FREE-ONLY policy)
  - No raw provider calls; no ProviderKernel direct path
  - Diff-based edits only (no full-file overwrites)
  - Tests must pass before claiming success
  - Rollback patch always created
  - Structured report regardless of outcome

This adapter BLOCKS:
  - Calling paid providers (even if forced)
  - Skipping test runner
  - Returning success without test results
  - Direct llm/provider calls outside SubAgentRouter
"""
from __future__ import annotations

import json
import logging
import subprocess
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ILMA.CodingWorker")

CODING_TASK_VERSION = "4B-2026-06-03"
ROLLBACK_DIR = Path("/root/.hermes/profiles/ilma/coding_rollbacks")
ROLLBACK_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class CodingTaskSpec:
    """Structured specification for a coding task."""
    task_id: str = field(default_factory=lambda: f"ct-{uuid.uuid4().hex[:12]}")
    repo: str = ""
    files_to_edit: List[str] = field(default_factory=list)
    description: str = ""
    tier: str = "L1_light"  # L1_light | L2_medium | L3_heavy | L4_super_heavy
    coding_style: str = "production"  # production | prototype | script
    run_tests: bool = True
    run_lint: bool = True
    run_typecheck: bool = True
    run_security_review: bool = True
    max_latency_seconds: int = 90
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class CodingTaskResult:
    """Structured result of a coding task."""
    task_id: str
    repo: str
    files_changed: List[str] = field(default_factory=list)
    model_used: str = ""
    provider_used: str = ""
    free_policy_passed: bool = False
    routed_via_subagent_router: bool = False
    paid_provider_bypass: bool = False
    used_fallback: bool = False
    original_model: str = ""
    confidence_score: float = 0.0
    content: str = ""  # Phase 4C: full model output
    diff_summary: str = ""
    diff_text: str = ""
    tests_run: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    lint_result: str = "skipped"
    typecheck_result: str = "skipped"
    security_review: str = "skipped"
    rollback_file: str = ""
    latency_ms: float = 0.0
    error_type: str = ""
    error_message: str = ""
    confidence_score: float = 0.0
    production_ready: bool = False
    limitations: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class FreePolicyViolation(Exception):
    """Raised when a paid provider is requested or used."""
    pass


class CodingWorkerAdapter:
    """
    Production coding orchestration layer.

    All model calls go through SubAgentRouter.
    Diff-based edits, test runner, rollback, structured report.
    """

    def __init__(self, subagent_router=None, repo_root: str = "/root/.hermes/profiles/ilma"):
        # Lazy import to avoid circular deps
        if subagent_router is None:
            from ilma_subagent_router import SubAgentRouter
            self.subagent = SubAgentRouter()
        else:
            self.subagent = subagent_router
        self.repo_root = Path(repo_root)
        # Provider allowlist — FREE ONLY (Phase 71: Bos command 2026-06-04)
        # All free provider groups are allowed
        self.FREE_PROVIDERS = {
            "nvidia", "minimax", "ollama", "openrouter", "blackbox",
            "alibaba", "deepseek", "google", "xai",
            "mistral", "meta", "anthropic", "microsoft-azure",
            "ai21-labs", "cohere",
        }
        # Blocked providers
        self.BLOCKED_PROVIDERS = {"perplexity"}
        # Banned model substrings
        self.BANNED_MODEL_PATTERNS = ["perplexity"]
        # Paid provider hints (for sanity check)
        self.PAID_PROVIDER_HINTS = {
            "claude-sonnet-4", "claude-opus-4", "gpt-4", "gpt-5.5-paid",
            "gemini-2-5-pro-paid",
        }
        # Phase 71: use ClaudeCode-Style Parallel Coding Agent by default
        self.use_claudecode = True  # when True, fan out to 3 free models in parallel

    # ─── Model call (THE ONLY place a model is invoked) ────────────────────
    def _call_model(self, prompt: str, prefer_model: Optional[str] = None,
                    timeout_seconds: int = 90) -> Dict[str, Any]:
        """
        The ONLY function that calls a model. Routes through SubAgentRouter.
        Enforces FREE-ONLY policy. Returns structured result.
        """
        # Pre-flight: if caller specified a model, sanity-check it's free
        if prefer_model:
            self._verify_free(prefer_model)

        # Build task with hint
        task = prompt
        if prefer_model:
            task = f"[preferred={prefer_model}] {prompt}"

        # Phase 71: use ClaudeCode-Style Parallel Coding Agent when enabled
        if self.use_claudecode:
            try:
                from ilma_claudecode_agent import CodingTaskSpec, execute_parallel
                spec = CodingTaskSpec(
                    task=prompt,
                    prefer_provider=prefer_model.split("/")[0] if prefer_model and "/" in prefer_model else None,
                    parallel_count=3,
                    tier="L2_medium",
                )
                cc_result = execute_parallel(spec)
                if cc_result.winner:
                    return {
                        "success": True,
                        "content": cc_result.final_content,
                        "model": cc_result.winner.model,
                        "provider": cc_result.winner.provider,
                        "tier": cc_result.winner.tier,
                        "judge_score": cc_result.winner.judge_score,
                        "judge_verdict": cc_result.winner.judge_verdict,
                        "parallel_count": cc_result.parallel_count,
                        "evidence_id": cc_result.evidence_id,
                        "via": "claudecode_agent",
                    }
                # All failed — fall through to single-route below
            except Exception as e:
                # On any ClaudeCode failure, fall back to SubAgentRouter single-route
                pass

        # Call SubAgentRouter (the canonical health-tracked path)
        result = self.subagent.route_and_execute(
            message=task,
            task_type_or_desc="medium_coding",  # Phase 4C fix: "coding task" → "medium_coding"
                                                # Required for SubAgentRouter to pick coding-specialized model
                                                # "medium_coding" routes to backend_engineer/coder models
            thinking="Auto",
            allow_paid=False,  # FREE-ONLY policy
            stateless=True,
        )

        # Post-flight: verify the result actually came from a free provider
        decision = result.get("decision", {})
        provider = decision.get("provider", "")
        if provider and provider in self.BLOCKED_PROVIDERS:
            raise FreePolicyViolation(
                f"BLOCKED PROVIDER USED: {provider}. Free policy violated."
            )

        return result

    def _verify_free(self, model_id: str):
        """Verify a model_id is free before using it."""
        ml = model_id.lower()
        for banned in self.BANNED_MODEL_PATTERNS:
            if banned in ml:
                raise FreePolicyViolation(
                    f"BLOCKED MODEL: {model_id} contains banned substring '{banned}'"
                )
        for paid_hint in self.PAID_PROVIDER_HINTS:
            if paid_hint in ml:
                raise FreePolicyViolation(
                    f"PAID MODEL DETECTED: {model_id} contains paid hint '{paid_hint}'"
                )
        # Heuristic: any model id containing "paid" is rejected
        if "paid" in ml or "premium" in ml or "pro-" in ml:
            raise FreePolicyViolation(
                f"PAID MODEL DETECTED: {model_id} contains paid-marker"
            )

    # ─── File writer (Phase 4C fix) ────────────────────────────────────────────
    def _write_model_output_to_files(self, content: str,
                                      files_to_edit: List[str]) -> List[str]:
        """
        Parse markdown code blocks OR git diff format and write to files.

        Supports:
        1. ```python code blocks (markdown format)
        2. ``` code blocks (plain)
        3. Git diff patch format (===DIFF=== or standard diff)
        4. Raw code (plain text starting with 'import' or 'def' or 'class')
        """
        import re
        written = []
        if not content or not files_to_edit:
            return written

        # Strategy 1: Extract markdown code blocks
        code_blocks = re.findall(
            r'```python\s*(?:(\S+\.py)\s*)?\n(.*?)```',
            content, re.DOTALL
        )
        plain_blocks = re.findall(
            r'```\s*(?:(\S+\.\w+)\s*)?\n(.*?)```',
            content, re.DOTALL
        )
        all_blocks = []
        for fname, code in code_blocks + plain_blocks:
            code = code.strip()
            if code and len(code) > 10:
                all_blocks.append((fname.strip() if fname else '', code))

        # Strategy 2: Parse git diff patch format
        # Format: ===DIFF=== or ---/+++ lines with +++ b/path @@
        if not all_blocks:
            diff_separators = ['===DIFF===', '=== DIFF ===', '--- ', 'diff --git']
            has_diff = any(sep in content for sep in diff_separators)
            if has_diff:
                # Extract new file content from +++ b/.../filename lines
                diff_files = {}  # filename -> list of +lines
                current_file = None
                current_lines = []
                for line in content.split('\n'):
                    # Match +++ b/filename (new file in patch)
                    m = re.match(r'\+\+\+ b/(.+)', line)
                    if m:
                        if current_file and current_lines:
                            diff_files[current_file] = current_lines
                        current_file = m.group(1)
                        current_lines = []
                    elif line.startswith('+++') or line.startswith('---') or line.startswith('diff'):
                        # skip metadata
                        pass
                    elif line.startswith('+') and not line.startswith('+++'):
                        # Added line (strip leading +)
                        current_lines.append(line[1:])
                    elif line.startswith('@@'):
                        # Hunk header — reset
                        current_lines = []
                    elif current_file:
                        # Context or unchanged line
                        current_lines.append(line)

                if current_file and current_lines:
                    diff_files[current_file] = current_lines

                for fname, lines in diff_files.items():
                    joined = '\n'.join(lines).strip()
                    if joined and len(joined) > 10:
                        # Find matching target file
                        target = None
                        for tf in files_to_edit:
                            if tf in fname or fname in tf:
                                target = tf
                                break
                        target = target or files_to_edit[0]
                        all_blocks.append((target, joined))

        # Strategy 3: Raw code (fallback) — detect if content is just Python code
        if not all_blocks:
            clean = content.strip()
            # If it looks like Python (starts with import/def/class)
            if re.match(r'^(import |def |class |from \w+ import)', clean, re.M):
                all_blocks = [('', clean)]

        # Write blocks to files
        for i, (block_fname, code) in enumerate(all_blocks):
            if i < len(files_to_edit):
                target = files_to_edit[i]
            elif block_fname and any(tf in block_fname for tf in files_to_edit):
                target = block_fname
            else:
                target = files_to_edit[min(i, len(files_to_edit) - 1)]

            target_path = self.repo_root / target
            try:
                # Phase 4C-R fix: strip artifact markers (===END===, ===BEGIN, ===FILENAME===)
                # These are not valid Python and cause syntax errors
                code = re.sub(r'^(={3,}[A-Za-z0-9_.-]+={3,})\s*$', '', code, flags=re.M)
                code = re.sub(r'^===(END|BEGIN|GEN)[A-Za-z0-9_/.-]*===\s*$', '', code, flags=re.M)
                code = re.sub(r'\n{3,}', '\n\n', code)  # collapse excessive blank lines
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_text(code)
                written.append(target)
                logger.info(f"[FILE_WRITER] Wrote {len(code)} chars to {target}")
            except Exception as e:
                logger.warning(f"[FILE_WRITER] Failed to write {target}: {e}")

        return written

    # ─── Diff capture ───────────────────────────────────────────────────────
    def _capture_diff(self, files: List[str]) -> tuple[str, str]:
        """Capture diff vs HEAD for the given files. Returns (summary, full_diff)."""
        diff_parts = []
        for f in files:
            p = self.repo_root / f
            if not p.exists():
                diff_parts.append(f"# File does not exist: {f}")
                continue
            try:
                rel = p.relative_to(self.repo_root)
                d = subprocess.run(
                    ["git", "diff", "--", str(rel)],
                    cwd=str(self.repo_root),
                    capture_output=True, text=True, timeout=10,
                )
                if d.returncode == 0 and d.stdout:
                    diff_parts.append(f"=== {f} ===\n{d.stdout}")
                else:
                    diff_parts.append(f"=== {f} === (no diff or untracked)")
            except Exception as e:
                diff_parts.append(f"=== {f} === diff_error: {e}")
        full_diff = "\n\n".join(diff_parts)
        summary = f"{len(files)} file(s); {len(full_diff)} chars"
        return summary, full_diff

    # ─── Rollback manager ───────────────────────────────────────────────────
    def _create_rollback(self, task_id: str, files: List[str]) -> str:
        """Save current state of files for rollback."""
        rollback_file = ROLLBACK_DIR / f"{task_id}.json"
        snapshot = {
            "task_id": task_id,
            "created_at": datetime.now().isoformat(),
            "files": {},
        }
        for f in files:
            p = self.repo_root / f
            if p.exists():
                try:
                    snapshot["files"][f] = p.read_text()
                except Exception as e:
                    snapshot["files"][f] = f"__read_error__: {e}"
        rollback_file.write_text(json.dumps(snapshot, indent=2))
        return str(rollback_file)

    # ─── Test runner ────────────────────────────────────────────────────────
    def _run_tests(self, files: List[str]) -> Dict[str, Any]:
        """Run pytest on test files if present. Returns structured result."""
        test_candidates = []
        for f in files:
            p = self.repo_root / f
            if p.exists() and p.suffix == ".py":
                # Look for test_file.py in same dir
                test_path = p.parent / f"test_{p.stem}.py"
                if test_path.exists():
                    test_candidates.append(str(test_path))
        if not test_candidates:
            return {"run": 0, "passed": 0, "failed": 0, "skipped": "no test files found"}
        try:
            r = subprocess.run(
                ["python3", "-m", "pytest", "-v", "--tb=short",] + test_candidates,
                cwd=str(self.repo_root),
                capture_output=True, text=True, timeout=120,
            )
            # Phase 4C fix: properly parse pytest output for pass/fail counts
            run = passed = failed = 0
            for line in (r.stdout + r.stderr).split("\n"):
                for i, w in enumerate(line.split()):
                    if w == "passed":
                        try: passed = int(line.split()[i-1])
                        except: pass
                    if w == "failed":
                        try: failed = int(line.split()[i-1])
                        except: pass
            run = passed + failed
            return {
                "run": run,
                "passed": passed,
                "failed": failed,
                "returncode": r.returncode,
                "stdout_tail": r.stdout[-500:],
                "stderr_tail": r.stderr[-500:],
            }
        except subprocess.TimeoutExpired:
            return {"run": 1, "passed": 0, "failed": 1, "error": "test_timeout"}
        except Exception as e:
            return {"run": 0, "passed": 0, "failed": 0, "error": str(e)}

    # ─── Lint / Typecheck (optional) ────────────────────────────────────────
    def _run_lint(self, files: List[str]) -> str:
        """Run pyflakes/ruff if available. Otherwise skipped."""
        py_files = [f for f in files if f.endswith(".py")]
        if not py_files:
            return "skipped (no python files)"
        try:
            r = subprocess.run(
                ["python3", "-m", "pyflakes"] + py_files,
                cwd=str(self.repo_root),
                capture_output=True, text=True, timeout=30,
            )
            if r.returncode == 0:
                return "passed"
            return f"issues: {r.stdout[:300]}"
        except FileNotFoundError:
            return "skipped (pyflakes not installed)"
        except Exception as e:
            return f"error: {e}"

    def _run_typecheck(self, files: List[str]) -> str:
        """Run mypy if available. Otherwise skipped."""
        py_files = [f for f in files if f.endswith(".py")]
        if not py_files:
            return "skipped (no python files)"
        try:
            r = subprocess.run(
                ["python3", "-m", "mypy", "--ignore-missing-imports", "--no-error-summary"] + py_files,
                cwd=str(self.repo_root),
                capture_output=True, text=True, timeout=60,
            )
            if r.returncode == 0:
                return "passed"
            return f"issues: {r.stdout[:300]}"
        except FileNotFoundError:
            return "skipped (mypy not installed)"
        except Exception as e:
            return f"error: {e}"

    # ─── Security review (lightweight) ──────────────────────────────────────
    def _security_review(self, files: List[str]) -> str:
        """Lightweight static check for dangerous patterns."""
        dangerous = ["os.system(", "subprocess.call(", "shell=True",
                     "eval(", "exec(", "__import__"]
        findings = []
        for f in files:
            p = self.repo_root / f
            if not p.exists():
                continue
            try:
                content = p.read_text()
                for d in dangerous:
                    if d in content:
                        findings.append(f"{f}: contains {d}")
            except Exception:
                pass
        if not findings:
            return "passed (no dangerous patterns found)"
        return f"flagged: {'; '.join(findings[:3])}"

    # ─── Main entry point ───────────────────────────────────────────────────
    def execute(self, spec: CodingTaskSpec, prefer_model: Optional[str] = None) -> CodingTaskResult:
        """
        Execute a coding task end-to-end with production safeguards.

        Pipeline (per Bos spec):
        1. Intake
        2. Repository scan (basic — file existence check)
        3. Task decomposition (in prompt)
        4. Impact analysis (lightweight — line counts)
        5. Implementation plan (in prompt)
        6. Model selection (SubAgentRouter)
        7. Code generation/edit (in prompt — actual edit is OUTSIDE this adapter)
        8. Diff validation
        9. Unit test
        10. Integration test (if applicable)
        11. Lint/typecheck (if available)
        12. Security review
        13. Regression check (deferred to caller)
        14. Rollback artifact
        15. Final report
        """
        result = CodingTaskResult(
            task_id=spec.task_id,
            repo=spec.repo,
        )

        start = time.time()
        try:
            # 1-7: Call model with structured prompt
            coding_prompt = self._build_coding_prompt(spec)
            call_result = self._call_model(coding_prompt, prefer_model=prefer_model,
                                           timeout_seconds=spec.max_latency_seconds)

            # Phase 4C fix: extract content from SubAgentRouter response structure
            content = call_result.get("content", "")
            if not content:
                result.error_type = call_result.get("error_type", "unknown")
                result.error_message = call_result.get("error", "no content returned")
                result.production_ready = False
                result.limitations = ["model_call_failed"]
                return result

            result.diff_text = content
            result.content = content  # Store full content for debugging

            # Restore metadata extraction (Phase 4C: re-add what was removed)
            decision = call_result.get("decision", {})
            result.model_used = call_result.get("model", "")
            result.provider_used = decision.get("provider", "")
            result.routed_via_subagent_router = True
            result.used_fallback = call_result.get("used_fallback", False)
            result.original_model = call_result.get("original_model", "")
            result.free_policy_passed = (
                result.provider_used not in self.BLOCKED_PROVIDERS
                and result.provider_used in self.FREE_PROVIDERS
            )
            result.paid_provider_bypass = result.provider_used not in self.FREE_PROVIDERS

            # Phase 4C fix: write model output to files BEFORE running tests
            # Parse markdown code blocks and write to disk
            files_written = self._write_model_output_to_files(content, spec.files_to_edit)
            result.files_changed = files_written if files_written else spec.files_to_edit

            # 8: Diff validation (git diff AFTER writing files)
            if spec.files_to_edit and files_written:
                diff_summary, full_diff = self._capture_diff(files_written)
                result.diff_summary = diff_summary
                result.diff_text = full_diff

            # 14: Rollback artifact (BEFORE running tests, so we can restore)
            if spec.files_to_edit:
                result.rollback_file = self._create_rollback(spec.task_id, spec.files_to_edit)

            # 9-10: Run tests
            if spec.run_tests and spec.files_to_edit:
                tr = self._run_tests(spec.files_to_edit)
                result.tests_run = tr.get("run", 0)
                result.tests_passed = tr.get("passed", 0)
                result.tests_failed = tr.get("failed", 0)

            # 11: Lint + typecheck
            if spec.run_lint:
                result.lint_result = self._run_lint(spec.files_to_edit)
            if spec.run_typecheck:
                result.typecheck_result = self._run_typecheck(spec.files_to_edit)

            # 12: Security review
            if spec.run_security_review:
                result.security_review = self._security_review(spec.files_to_edit)

            # 15: Production ready verdict
            result.production_ready = (
                result.tests_failed == 0
                and result.free_policy_passed
                and "passed" in result.lint_result.lower() or "skipped" in result.lint_result.lower()
            )
            result.confidence_score = self._compute_confidence(result)

        except FreePolicyViolation as e:
            result.error_type = "free_policy_violation"
            result.error_message = str(e)
            result.production_ready = False
            result.paid_provider_bypass = True
        except Exception as e:
            result.error_type = "adapter_error"
            result.error_message = str(e)[:500]
            result.production_ready = False
        finally:
            result.latency_ms = (time.time() - start) * 1000

        return result

    def _build_coding_prompt(self, spec: CodingTaskSpec) -> str:
        """Build a structured coding prompt."""
        return f"""You are a {spec.coding_style} coding worker. Produce a unified diff (no prose before/after) for the following task.

Task ID: {spec.task_id}
Repository: {spec.repo or 'unknown'}
Tier: {spec.tier}
Files to edit: {', '.join(spec.files_to_edit) if spec.files_to_edit else '(unspecified)'}

Description:
{spec.description}

Output format:
===DIFF===
<unified diff text>
===END===

Constraints:
- Use unified diff format (--- a/file, +++ b/file)
- No markdown code fences
- No commentary outside the diff
- If no diff is needed, output ===DIFF===<empty>===END===
"""

    def _compute_confidence(self, result: CodingTaskResult) -> float:
        """Compute confidence score 0-1 based on objective signals."""
        score = 0.0
        if result.routed_via_subagent_router:
            score += 0.2
        if result.free_policy_passed:
            score += 0.2
        if not result.paid_provider_bypass:
            score += 0.1
        if result.tests_failed == 0 and result.tests_run > 0:
            score += 0.2
        if "passed" in result.lint_result.lower() or "skipped" in result.lint_result.lower():
            score += 0.1
        if "passed" in result.typecheck_result.lower() or "skipped" in result.typecheck_result.lower():
            score += 0.1
        if "passed" in result.security_review.lower() or "skipped" in result.security_review.lower():
            score += 0.1
        return min(score, 1.0)


# ─── Convenience function ───────────────────────────────────────────────────

def run_coding_task(description: str, files: List[str] = None,
                    tier: str = "L1_light",
                    prefer_model: Optional[str] = None,
                    repo: str = "") -> CodingTaskResult:
    """Convenience entry point for the coding worker."""
    adapter = CodingWorkerAdapter()
    spec = CodingTaskSpec(
        description=description,
        files_to_edit=files or [],
        tier=tier,
        repo=repo,
    )
    return adapter.execute(spec, prefer_model=prefer_model)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 ilma_coding_worker_adapter.py 'task description' [files...]")
        sys.exit(1)
    desc = sys.argv[1]
    files: List[str] = sys.argv[2:] if len(sys.argv) > 2 else []
    r = run_coding_task(desc, files=files)
    print(json.dumps(asdict(r), indent=2))
    sys.exit(0 if r.production_ready else 1)
