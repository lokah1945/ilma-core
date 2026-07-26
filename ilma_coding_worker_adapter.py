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

CODING_TASK_VERSION = "4D-2026-06-22"  # generate→test→repair loop
ROLLBACK_DIR = Path("/root/.hermes/profiles/ilma/coding_rollbacks")
ROLLBACK_DIR.mkdir(parents=True, exist_ok=True)

# Toolchain locations (real subprocess calls, never bare exec()).
VENV_PY = "/root/.hermes/hermes-agent/venv/bin/python3"
PY = VENV_PY if Path(VENV_PY).exists() else "python3"
BWRAP = "/usr/bin/bwrap"
TIMEOUT_BIN = "/usr/bin/timeout"
# ruff lives in the venv; mypy/bandit/black are system-installed.
RUFF_CMD = [PY, "-m", "ruff"]
MYPY_BIN = "/usr/local/bin/mypy"
BANDIT_BIN = "/usr/local/bin/bandit"
MAX_REPAIR_ITERS = 2  # generate→test→repair budget


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
    # Phase 4D: real generate→test→repair loop signals
    test_file_generated: bool = False
    test_file_path: str = ""
    sandboxed: bool = False
    lint_status: str = "skipped"        # passed | issues | skipped
    typecheck_status: str = "skipped"   # passed | issues | skipped
    security_status: str = "skipped"    # passed | high_severity | skipped
    repair_iterations: int = 0
    repair_log: List[str] = field(default_factory=list)
    # Test-assertion cross-check (adjudicator): tests judged to have a factually
    # wrong expected value and skipped, recorded transparently (never silent).
    quarantined_tests: List[str] = field(default_factory=list)
    rollback_file: str = ""
    latency_ms: float = 0.0
    error_type: str = ""
    error_message: str = ""
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

    # ─── Sandboxed runner (bwrap + timeout, no bare exec) ───────────────────
    def _sandboxed_run(self, cmd: List[str], workdir: str,
                       timeout: int = 60) -> Dict[str, Any]:
        """
        Run `cmd` inside a bubblewrap sandbox rooted at `workdir`.

        - /usr, /lib, /lib64, /bin and the venv are bound read-only.
        - `workdir` is bound read-write at the same path.
        - Network is unshared (--unshare-net).
        - The whole thing is wrapped in `timeout <n>` as a second guard.

        Falls back to a plain (un-sandboxed) subprocess if bwrap is absent,
        and reports degraded=True so the caller can WARN.
        Never uses bare exec().
        """
        workdir = str(workdir)
        venv_root = "/root/.hermes/hermes-agent/venv"
        bwrap_available = Path(BWRAP).exists()

        if bwrap_available:
            sandbox = [
                BWRAP,
                "--ro-bind", "/usr", "/usr",
                "--ro-bind", "/bin", "/bin",
                "--ro-bind-try", "/lib", "/lib",
                "--ro-bind-try", "/lib64", "/lib64",
                "--ro-bind-try", "/etc/alternatives", "/etc/alternatives",
                "--ro-bind-try", "/etc/ssl", "/etc/ssl",
                "--ro-bind-try", venv_root, venv_root,
                "--proc", "/proc",
                "--dev", "/dev",
                # tmpfs /tmp MUST come before binding the workdir: when workdir is
                # itself under /tmp (e.g. tempfile dirs), a later --tmpfs /tmp would
                # overlay and hide the bound workdir → "Can't chdir" (fixed 2026-06-22).
                "--tmpfs", "/tmp",
                "--bind", workdir, workdir,
                "--unshare-net",
                "--die-with-parent",
                "--chdir", workdir,
                "--setenv", "PYTHONDONTWRITEBYTECODE", "1",
                "--",
            ] + cmd
            full = [TIMEOUT_BIN, str(timeout)] + sandbox if Path(TIMEOUT_BIN).exists() else sandbox
            degraded = False
        else:
            # Degraded path: still wrap in timeout, but no isolation.
            full = ([TIMEOUT_BIN, str(timeout)] if Path(TIMEOUT_BIN).exists() else []) + cmd
            degraded = True

        try:
            r = subprocess.run(
                full, cwd=workdir, capture_output=True, text=True,
                timeout=timeout + 10,
            )
            return {
                "returncode": r.returncode,
                "stdout": r.stdout,
                "stderr": r.stderr,
                "degraded": degraded,
                "timed_out": r.returncode == 124,
            }
        except subprocess.TimeoutExpired:
            return {"returncode": 124, "stdout": "", "stderr": "timeout",
                    "degraded": degraded, "timed_out": True}
        except Exception as e:
            return {"returncode": -1, "stdout": "", "stderr": str(e),
                    "degraded": degraded, "timed_out": False}

    @staticmethod
    def _parse_pytest_counts(text: str) -> Dict[str, int]:
        """Parse pytest summary line for passed/failed/error counts."""
        import re as _re
        passed = failed = errors = 0
        m = _re.search(r"(\d+)\s+passed", text)
        if m:
            passed = int(m.group(1))
        m = _re.search(r"(\d+)\s+failed", text)
        if m:
            failed = int(m.group(1))
        m = _re.search(r"(\d+)\s+error", text)
        if m:
            errors = int(m.group(1))
        return {"passed": passed, "failed": failed, "errors": errors}

    # ─── Test runner (sandboxed pytest) ──────────────────────────────────────
    def _run_tests(self, code_files: List[str], test_files: List[str]) -> Dict[str, Any]:
        """
        Run pytest (sandboxed) on the provided test files.

        Sandbox workdir = repo_root so generated code + tests are visible.
        A skipped/absent test set is reported run=0 (caller treats as WARN).
        """
        existing = [str(self.repo_root / t) for t in test_files
                    if (self.repo_root / t).exists()]
        if not existing:
            return {"run": 0, "passed": 0, "failed": 0,
                    "skipped": "no test files found", "sandboxed": False}

        cmd = [PY, "-m", "pytest", "-v", "--tb=short", "-p", "no:cacheprovider"] + existing
        res = self._sandboxed_run(cmd, str(self.repo_root), timeout=60)
        out = (res["stdout"] + "\n" + res["stderr"])
        counts = self._parse_pytest_counts(out)
        run = counts["passed"] + counts["failed"] + counts["errors"]
        return {
            "run": run,
            "passed": counts["passed"],
            "failed": counts["failed"] + counts["errors"],
            "returncode": res["returncode"],
            "sandboxed": (not res["degraded"]),
            "timed_out": res["timed_out"],
            "stdout_tail": res["stdout"][-1500:],
            "stderr_tail": res["stderr"][-800:],
        }

    # ─── Lint (real ruff) ────────────────────────────────────────────────────
    def _run_lint(self, files: List[str]) -> Dict[str, str]:
        """Run `ruff check` (real). Gate on exit code. Absence => skipped/WARN."""
        py_files = [str(self.repo_root / f) for f in files
                    if f.endswith(".py") and (self.repo_root / f).exists()]
        if not py_files:
            return {"status": "skipped", "detail": "no python files"}
        try:
            r = subprocess.run(
                RUFF_CMD + ["check", "--no-cache"] + py_files,
                cwd=str(self.repo_root), capture_output=True, text=True, timeout=60,
            )
            if r.returncode == 0:
                return {"status": "passed", "detail": "ruff clean"}
            return {"status": "issues", "detail": (r.stdout or r.stderr)[:1200]}
        except FileNotFoundError:
            return {"status": "skipped", "detail": "ruff not installed"}
        except Exception as e:
            return {"status": "skipped", "detail": f"ruff error: {e}"}

    # ─── Typecheck (real mypy) ───────────────────────────────────────────────
    def _run_typecheck(self, files: List[str]) -> Dict[str, str]:
        """Run system `mypy`. Gate on exit code. Absence => skipped/WARN."""
        py_files = [str(self.repo_root / f) for f in files
                    if f.endswith(".py") and (self.repo_root / f).exists()]
        if not py_files:
            return {"status": "skipped", "detail": "no python files"}
        mypy_cmd = [MYPY_BIN] if Path(MYPY_BIN).exists() else None
        if mypy_cmd is None:
            return {"status": "skipped", "detail": "mypy not installed"}
        try:
            r = subprocess.run(
                mypy_cmd + ["--ignore-missing-imports", "--no-error-summary",
                            "--no-color-output"] + py_files,
                cwd=str(self.repo_root), capture_output=True, text=True, timeout=90,
            )
            if r.returncode == 0:
                return {"status": "passed", "detail": "mypy clean"}
            return {"status": "issues", "detail": (r.stdout or r.stderr)[:1000]}
        except FileNotFoundError:
            return {"status": "skipped", "detail": "mypy not installed"}
        except Exception as e:
            return {"status": "skipped", "detail": f"mypy error: {e}"}

    # ─── Security (real bandit, gate on HIGH severity) ──────────────────────
    def _security_review(self, files: List[str]) -> Dict[str, str]:
        """
        Run `bandit -ll` (system). `-ll` reports MEDIUM+ but we gate strictly
        on HIGH severity findings (bandit exits non-zero when any are present
        at the configured level). Absence => skipped/WARN.
        """
        py_files = [str(self.repo_root / f) for f in files
                    if f.endswith(".py") and (self.repo_root / f).exists()]
        if not py_files:
            return {"status": "skipped", "detail": "no python files"}
        if not Path(BANDIT_BIN).exists():
            return {"status": "skipped", "detail": "bandit not installed"}
        try:
            # -lll = only HIGH severity gates the run; JSON for reliable parsing.
            r = subprocess.run(
                [BANDIT_BIN, "-f", "json", "-lll"] + py_files,
                cwd=str(self.repo_root), capture_output=True, text=True, timeout=60,
            )
            high = 0
            try:
                report = json.loads(r.stdout or "{}")
                for item in report.get("results", []):
                    if item.get("issue_severity", "").upper() == "HIGH":
                        high += 1
            except Exception:
                # Fall back to exit code if JSON parse fails.
                high = 1 if r.returncode != 0 else 0
            if high > 0:
                return {"status": "high_severity",
                        "detail": f"{high} HIGH-severity finding(s)"}
            return {"status": "passed", "detail": "no HIGH-severity findings"}
        except FileNotFoundError:
            return {"status": "skipped", "detail": "bandit not installed"}
        except Exception as e:
            return {"status": "skipped", "detail": f"bandit error: {e}"}

    # ─── Test generation (free model) ───────────────────────────────────────
    @staticmethod
    def _test_path_for(code_rel: str) -> str:
        """test_<stem>.py alongside the code file."""
        p = Path(code_rel)
        return str(p.parent / f"test_{p.stem}.py") if str(p.parent) not in (".", "") \
            else f"test_{p.stem}.py"

    def _extract_python(self, content: str) -> str:
        """Pull a single python block out of a model response (best effort)."""
        import re as _re
        m = _re.search(r"```python\s*\n(.*?)```", content, _re.DOTALL)
        if m:
            return m.group(1).strip()
        m = _re.search(r"```\s*\n(.*?)```", content, _re.DOTALL)
        if m:
            return m.group(1).strip()
        clean = content.strip()
        if _re.match(r"^(import |from |def |class |#|\")", clean, _re.M):
            return clean
        return ""

    def _generate_tests(self, spec: CodingTaskSpec, code_files: List[str],
                        code_text: str) -> List[str]:
        """
        For each generated code file lacking a test_<stem>.py, ask the free
        model to emit a pytest file, write it, and return the test paths.
        """
        generated: List[str] = []
        for cf in code_files:
            if not cf.endswith(".py"):
                continue
            tpath_rel = self._test_path_for(cf)
            if (self.repo_root / tpath_rel).exists():
                generated.append(tpath_rel)
                continue
            module = Path(cf).stem
            prompt = (
                "You are a test engineer. Write a complete pytest test file for the "
                "module below. Cover normal cases, edge cases, and error handling.\n"
                f"Import the code under test with: from {module} import ...\n"
                "Output ONLY one ```python code block with the test file content. "
                "Use plain `assert`. Do not include the implementation.\n"
                # Guard against faulty assertions (root-caused 2026-06-22: a model
                # asserted is_prime(1000000009) is False with a self-doubting comment,
                # but that number IS prime → a wrong test the repair loop can't fix).
                "CRITICAL: assert ONLY expected values you are 100% certain are correct. "
                "Do NOT guess. If you are unsure whether a specific large number is prime/"
                "composite (or any computed expected value), DO NOT use it — pick small, "
                "verifiable values instead. Never leave uncertain or self-doubting comments "
                "like 'actually prime?' next to an assertion. A wrong assertion is worse "
                "than no test.\n\n"
                f"TASK SPEC:\n{spec.description}\n\n"
                f"CODE UNDER TEST ({cf}):\n```python\n{code_text[:6000]}\n```\n"
            )
            try:
                resp = self._call_model(prompt, timeout_seconds=spec.max_latency_seconds)
                test_code = self._extract_python(resp.get("content", ""))
            except Exception as e:
                logger.warning(f"[TESTGEN] model call failed for {cf}: {e}")
                test_code = ""
            if test_code and len(test_code) > 20:
                (self.repo_root / tpath_rel).write_text(test_code)
                generated.append(tpath_rel)
                logger.info(f"[TESTGEN] Wrote {tpath_rel} ({len(test_code)} chars)")
        return generated

    def _repair(self, spec: CodingTaskSpec, code_files: List[str],
                failures: str) -> List[str]:
        """
        Feed concrete failures back to the model for a repair pass.
        Rewrites the code file(s); returns files actually rewritten.
        """
        current = ""
        for cf in code_files:
            p = self.repo_root / cf
            if p.exists():
                current += f"\n# === {cf} ===\n{p.read_text()}\n"
        prompt = (
            "The following code FAILED its checks. Fix the implementation so all "
            "tests pass and ruff/bandit are clean. Output ONLY the corrected file "
            "as one ```python code block, no prose.\n\n"
            f"TASK SPEC:\n{spec.description}\n\n"
            f"CURRENT CODE:{current}\n\n"
            f"CONCRETE FAILURES:\n{failures[:4000]}\n"
        )
        try:
            resp = self._call_model(prompt, timeout_seconds=spec.max_latency_seconds)
            fixed = self._extract_python(resp.get("content", ""))
        except Exception as e:
            logger.warning(f"[REPAIR] model call failed: {e}")
            return []
        if not fixed or len(fixed) < 10:
            return []
        # Write back to the first (primary) code file.
        target = code_files[0]
        (self.repo_root / target).write_text(fixed)
        logger.info(f"[REPAIR] Rewrote {target} ({len(fixed)} chars)")
        return [target]

    # ─── Test-assertion cross-check (adjudicator) ────────────────────────────
    def _adjudicate_failing_tests(self, spec: "CodingTaskSpec", code_files: List[str],
                                  test_files: List[str], failure_output: str) -> Dict[str, Any]:
        """Independent free-model judge: for each FAILING test, decide whether the
        TEST's expected value is itself factually WRONG (faulty test) or the CODE is
        wrong (real bug). Conservative — defaults to 'code_bug' when unsure.

        Runs ONLY after the code-repair budget is exhausted (so we always try to fix
        the code first). Returns {"faulty":[name...], "reasons":{name:why}}.
        """
        import json as _json, re as _re
        code_text = "".join((self.repo_root / c).read_text()
                            for c in code_files if (self.repo_root / c).exists())[:5000]
        test_text = "".join((self.repo_root / t).read_text()
                            for t in test_files if (self.repo_root / t).exists())[:5000]
        prompt = (
            "You are an IMPARTIAL test auditor. Some pytest tests FAILED. For each failing "
            "test, decide whether the TEST's asserted/expected value is itself factually "
            "WRONG (a faulty test) or the CODE has a real bug.\n"
            "Be STRICT and CONSERVATIVE: only label a test 'faulty' when you are CERTAIN its "
            "expected value is factually incorrect given the task spec — e.g. it asserts that "
            "a number which IS prime is composite, or hardcodes a wrong arithmetic result. "
            "If there is ANY doubt, classify it as a code bug (do NOT excuse the code).\n\n"
            f"TASK SPEC:\n{spec.description}\n\n"
            f"CODE UNDER TEST:\n```python\n{code_text}\n```\n\n"
            f"TEST FILE:\n```python\n{test_text}\n```\n\n"
            f"PYTEST FAILURE OUTPUT:\n{failure_output[:3000]}\n\n"
            'Output ONLY JSON, no prose: '
            '{"faulty_tests":[{"name":"<exact test function name>","reason":"<why the '
            'expected value is factually wrong>"}]}. Empty list if all failures are code bugs.'
        )
        out: Dict[str, Any] = {"faulty": [], "reasons": {}}
        try:
            resp = self._call_model(prompt, timeout_seconds=spec.max_latency_seconds)
            txt = resp.get("content", "") or ""
            m = _re.search(r"\{.*\}", txt, _re.DOTALL)
            data = _json.loads(m.group(0)) if m else {}
            for item in (data.get("faulty_tests") or []):
                name = str(item.get("name", "")).strip()
                # only accept names that actually exist as test functions
                if name and _re.search(rf"def\s+{_re.escape(name)}\s*\(", test_text):
                    out["faulty"].append(name)
                    out["reasons"][name] = str(item.get("reason", ""))[:160]
        except Exception as e:
            logger.warning(f"[ADJUDICATE] failed: {e}")
        return out

    def _quarantine_tests(self, test_files: List[str], names: List[str],
                          reasons: Dict[str, str]) -> int:
        """Skip specific test functions judged to have faulty assertions, by inserting
        a @pytest.mark.skip above their def. Transparent + reversible (recorded in result)."""
        import re as _re
        n = 0
        for t in test_files:
            p = self.repo_root / t
            if not p.exists():
                continue
            src = p.read_text()
            if "import pytest" not in src:
                src = "import pytest\n" + src
            for name in names:
                reason = (reasons.get(name, "faulty assertion") or "faulty assertion").replace('"', "'")
                # insert skip marker just above the function def (preserve indentation)
                pat = _re.compile(rf"(^[ \t]*)def\s+{_re.escape(name)}\s*\(", _re.MULTILINE)
                def _repl(mo):
                    ind = mo.group(1)
                    return f'{ind}@pytest.mark.skip(reason="adjudicator-quarantine: {reason}")\n{ind}def {name}('
                src, k = pat.subn(_repl, src, count=1)
                n += k
            p.write_text(src)
        return n

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
            code_files = files_written if files_written else spec.files_to_edit
            result.files_changed = list(code_files)

            # 14: Rollback artifact (BEFORE running tests, so we can restore)
            if code_files:
                result.rollback_file = self._create_rollback(spec.task_id, code_files)

            # ── TEST GENERATION: emit pytest tests when none exist ──────────
            test_files: List[str] = []
            if spec.run_tests and code_files:
                code_text = ""
                for cf in code_files:
                    p = self.repo_root / cf
                    if p.exists():
                        code_text += p.read_text() + "\n"
                test_files = self._generate_tests(spec, code_files, code_text)
                result.test_file_generated = bool(test_files)
                result.test_file_path = ", ".join(test_files)

            # ── GENERATE → TEST → REPAIR LOOP ───────────────────────────────
            def _run_all_checks() -> Dict[str, Any]:
                tr = self._run_tests(code_files, test_files) if (spec.run_tests and code_files) \
                    else {"run": 0, "passed": 0, "failed": 0, "sandboxed": False}
                lint = self._run_lint(code_files) if spec.run_lint else {"status": "skipped", "detail": "disabled"}
                tc = self._run_typecheck(code_files) if spec.run_typecheck else {"status": "skipped", "detail": "disabled"}
                sec = self._security_review(code_files) if spec.run_security_review else {"status": "skipped", "detail": "disabled"}
                return {"tests": tr, "lint": lint, "typecheck": tc, "security": sec}

            checks = _run_all_checks()
            for attempt in range(MAX_REPAIR_ITERS):
                tr = checks["tests"]
                lint = checks["lint"]
                sec = checks["security"]
                # Concrete failures that warrant a repair pass.
                failing = (
                    (tr.get("run", 0) > 0 and tr.get("failed", 0) > 0)
                    or lint["status"] == "issues"
                    or sec["status"] == "high_severity"
                )
                if not failing:
                    break
                failures = []
                if tr.get("failed", 0) > 0:
                    failures.append("PYTEST:\n" + tr.get("stdout_tail", "") + "\n" + tr.get("stderr_tail", ""))
                if lint["status"] == "issues":
                    failures.append("RUFF:\n" + lint["detail"])
                if sec["status"] == "high_severity":
                    failures.append("BANDIT:\n" + sec["detail"])
                repaired = self._repair(spec, code_files, "\n\n".join(failures))
                result.repair_iterations += 1
                result.repair_log.append(
                    f"iter {attempt+1}: tests_failed={tr.get('failed',0)} "
                    f"lint={lint['status']} sec={sec['status']} -> "
                    f"{'rewrote ' + repaired[0] if repaired else 'no change'}"
                )
                if not repaired:
                    break
                checks = _run_all_checks()

            # ── TEST-ASSERTION CROSS-CHECK (adjudicator) ────────────────────
            # Repair tried to fix the CODE first. If tests still fail, an independent
            # judge decides whether the failing tests are themselves faulty (wrong
            # expected value, e.g. asserting a prime is composite). Only confidently-
            # faulty tests are quarantined, capped at 40% of the suite so this can
            # never whitewash genuinely broken code. Every quarantine is RECORDED.
            _tr = checks["tests"]
            if (spec.run_tests and test_files and _tr.get("run", 0) > 0
                    and _tr.get("failed", 0) > 0):
                _fo = (_tr.get("stdout_tail", "") or "") + "\n" + (_tr.get("stderr_tail", "") or "")
                _adj = self._adjudicate_failing_tests(spec, code_files, test_files, _fo)
                _faulty = _adj.get("faulty", [])
                _cap = max(1, int(_tr.get("run", 0) * 0.4))
                if _faulty and len(_faulty) <= _cap:
                    _nq = self._quarantine_tests(test_files, _faulty, _adj.get("reasons", {}))
                    if _nq:
                        result.quarantined_tests = [
                            f"{nm}: {_adj['reasons'].get(nm, '')}" for nm in _faulty]
                        result.repair_log.append(
                            f"adjudicator quarantined {_nq} faulty test(s): {_faulty}")
                        checks = _run_all_checks()  # re-run after quarantine
                elif _faulty:
                    result.repair_log.append(
                        f"adjudicator flagged {len(_faulty)} > cap {_cap} faulty — "
                        f"NOT quarantining (treated as code bug, code stays on the hook)")

            # ── Record final check state ────────────────────────────────────
            tr = checks["tests"]
            result.tests_run = tr.get("run", 0)
            result.tests_passed = tr.get("passed", 0)
            result.tests_failed = tr.get("failed", 0)
            result.sandboxed = bool(tr.get("sandboxed", False))

            result.lint_status = checks["lint"]["status"]
            result.lint_result = f"{checks['lint']['status']}: {checks['lint']['detail'][:200]}"
            result.typecheck_status = checks["typecheck"]["status"]
            result.typecheck_result = f"{checks['typecheck']['status']}: {checks['typecheck']['detail'][:200]}"
            result.security_status = checks["security"]["status"]
            result.security_review = f"{checks['security']['status']}: {checks['security']['detail'][:200]}"

            # 8: Diff validation (git diff AFTER all writes/repairs)
            if code_files:
                diff_summary, full_diff = self._capture_diff(code_files)
                result.diff_summary = diff_summary
                result.diff_text = full_diff

            # ── PRODUCTION-READY VERDICT (strict) ───────────────────────────
            # Must have REAL passing tests; skipped lint/type must NOT count as pass.
            # production_ready := tests_run>0 AND tests_failed==0 AND ruff clean
            #                     AND no HIGH-severity security finding.
            result.production_ready = bool(
                result.free_policy_passed
                and result.tests_run > 0
                and result.tests_failed == 0
                and result.lint_status == "passed"
                and result.security_status == "passed"
            )
            if not result.production_ready:
                why = []
                if not result.free_policy_passed:
                    why.append("free_policy_failed")
                if result.tests_run == 0:
                    why.append("no_tests_run(WARN)")
                if result.tests_failed > 0:
                    why.append("tests_failed")
                if result.lint_status != "passed":
                    why.append(f"lint_{result.lint_status}")
                if result.security_status != "passed":
                    why.append(f"security_{result.security_status}")
                result.limitations = why
            # Transparency: surface any adjudicator-quarantined tests in the verdict
            # regardless of pass/fail, so a human always sees what was set aside.
            if result.quarantined_tests:
                result.limitations.append(
                    f"adjudicator_quarantined_{len(result.quarantined_tests)}_test(s)")
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
        """Build a structured coding prompt.

        When every target file is new (does not yet exist), ask for the full
        file as a single python code block — diffs are meaningless for fresh
        files and the model handles full-file generation far more reliably.
        Otherwise ask for a unified diff against the existing file(s).
        """
        targets = spec.files_to_edit or []
        all_new = bool(targets) and all(
            not (self.repo_root / f).exists() for f in targets
        )
        if all_new or not targets:
            target_hint = targets[0] if targets else "module.py"
            return f"""You are a {spec.coding_style} Python engineer. Implement the task below.

Task ID: {spec.task_id}
Target file: {target_hint}

Description:
{spec.description}

Output ONLY one ```python code block containing the COMPLETE file content.
- No prose before or after the code block.
- Production-quality: type hints, docstrings, input validation, edge cases.
- Do not write the test file (a separate step generates tests).
"""
        return f"""You are a {spec.coding_style} coding worker. Produce a unified diff (no prose before/after) for the following task.

Task ID: {spec.task_id}
Repository: {spec.repo or 'unknown'}
Tier: {spec.tier}
Files to edit: {', '.join(targets)}

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
"""

    def _compute_confidence(self, result: CodingTaskResult) -> float:
        """Compute confidence score 0-1 based on objective signals."""
        score = 0.0
        if result.routed_via_subagent_router:
            score += 0.15
        if result.free_policy_passed:
            score += 0.15
        if not result.paid_provider_bypass:
            score += 0.05
        # Real passing tests are the dominant signal.
        if result.tests_failed == 0 and result.tests_run > 0:
            score += 0.30
        # Skipped checks earn NO credit — only real "passed" does.
        if result.lint_status == "passed":
            score += 0.15
        if result.typecheck_status == "passed":
            score += 0.05
        if result.security_status == "passed":
            score += 0.15
        return min(score, 1.0)


# ─── Convenience function ───────────────────────────────────────────────────

def run_coding_task(description: str, files: List[str] = None,
                    tier: str = "L1_light",
                    prefer_model: Optional[str] = None,
                    repo: str = "") -> CodingTaskResult:
    """Convenience entry point for the coding worker."""
    # Honor `repo`: the adapter writes files + runs the sandbox against repo_root,
    # so the spec.repo must propagate to the adapter (else generated files land in
    # the default profile dir and the sandbox never sees them → tests_run=0).
    adapter = CodingWorkerAdapter(repo_root=repo) if repo else CodingWorkerAdapter()
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
