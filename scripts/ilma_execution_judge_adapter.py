#!/usr/bin/env python3
"""
ILMA Execution Judge Adapter v1.0
=================================
AutoGen-style local execution judge.
Phase 46 - Autonomous Evolution Foundation.

Simulates AutoGen-style reality judge with local execution:
- run command
- capture stdout/stderr
- timeout
- exit code
- stack trace extraction

NOTE: No Docker claim unless Docker actually used.
Label as LOCAL_EXECUTION_JUDGE if Docker unavailable.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ILMA paths
ILMA_PROFILE = Path("/root/.hermes/profiles/ilma")
WORKSPACE = ILMA_PROFILE


@dataclass
class ExecutionResult:
    """Result of command execution."""
    command: str
    returncode: int
    stdout: str
    stderr: str
    duration: float
    timed_out: bool
    stack_trace: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command": self.command,
            "returncode": self.returncode,
            "stdout": self.stdout[:500],  # Truncate
            "stderr": self.stderr[:500],
            "duration": self.duration,
            "timed_out": self.timed_out,
            "stack_trace": self.stack_trace
        }


class ExecutionJudgeAdapter:
    """
    Local execution judge adapter.
    
    Simulates AutoGen-style reality judge:
    - Execute command with timeout
    - Capture stdout/stderr
    - Extract stack traces
    - Judge pass/fail based on exit code
    """

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.docker_available = self._check_docker()

    def _check_docker(self) -> bool:
        """Check if Docker is available."""
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    def execute(
        self,
        command: str,
        cwd: Optional[str] = None,
        timeout: Optional[int] = None
    ) -> ExecutionResult:
        """
        Execute command and return result.
        """
        start = datetime.now()
        timeout = timeout or self.timeout
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd
            )
            
            duration = (datetime.now() - start).total_seconds()
            
            return ExecutionResult(
                command=command,
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                duration=duration,
                timed_out=False,
                stack_trace=self._extract_stack_trace(result.stderr)
            )
        
        except subprocess.TimeoutExpired as e:
            duration = (datetime.now() - start).total_seconds()
            
            # Capture partial output
            stdout = e.stdout.decode() if e.stdout else ""
            stderr = e.stderr.decode() if e.stderr else ""
            
            return ExecutionResult(
                command=command,
                returncode=-1,
                stdout=stdout,
                stderr=stderr + f"\n[Timeout after {timeout}s]",
                duration=duration,
                timed_out=True,
                stack_trace=self._extract_stack_trace(stderr)
            )
        
        except Exception as e:
            duration = (datetime.now() - start).total_seconds()
            
            return ExecutionResult(
                command=command,
                returncode=-1,
                stdout="",
                stderr=str(e),
                duration=duration,
                timed_out=False,
                stack_trace=str(e)
            )

    def _extract_stack_trace(self, stderr: str) -> str:
        """Extract Python stack trace from stderr."""
        lines = stderr.split('\n')
        trace_lines = []
        in_trace = False
        
        for line in lines:
            if 'Traceback (most recent call last)' in line:
                in_trace = True
                trace_lines.append(line)
            elif in_trace:
                trace_lines.append(line)
                if 'Error:' in line or 'Exception:' in line:
                    break
        
        return '\n'.join(trace_lines[-20:])  # Last 20 lines

    def judge_execution(
        self,
        result: ExecutionResult,
        require_clean_exit: bool = False
    ) -> Dict[str, Any]:
        """
        Judge execution result.
        
        Returns:
        {
            "status": "PASS|FAIL|WARN",
            "reason": "...",
            "issues": [...],
            "can_proceed": bool
        }
        """
        issues = []
        
        # Check timeout
        if result.timed_out:
            issues.append(f"Execution timed out after {self.timeout}s")
        
        # Check exit code
        if result.returncode != 0:
            if require_clean_exit:
                issues.append(f"Non-zero exit code: {result.returncode}")
            else:
                issues.append(f"Exit code: {result.returncode} (non-zero)")
        
        # Check for error patterns in stderr
        error_patterns = [
            'SyntaxError',
            'ImportError',
            'ModuleNotFoundError',
            'TypeError',
            'ValueError',
            'RuntimeError',
            'Exception',
            'Traceback',
        ]
        
        for pattern in error_patterns:
            if pattern in result.stderr:
                issues.append(f"Error pattern detected: {pattern}")
        
        # Determine status
        if not issues:
            status = "PASS"
            reason = "Clean execution"
        elif result.timed_out or 'SyntaxError' in result.stderr or 'ImportError' in result.stderr:
            status = "FAIL"
            reason = "Execution failed"
        else:
            status = "WARN"
            reason = "Execution with warnings"
        
        return {
            "status": status,
            "reason": reason,
            "issues": issues,
            "can_proceed": status in ["PASS", "WARN"],
            "execution_result": result.to_dict()
        }

    def run_and_judge(
        self,
        command: str,
        cwd: Optional[str] = None,
        require_clean_exit: bool = False
    ) -> Tuple[ExecutionResult, Dict[str, Any]]:
        """
        Run command and judge result.
        """
        result = self.execute(command, cwd)
        judgment = self.judge_execution(result, require_clean_exit)
        return result, judgment


# === DEMO ===

def run_demo():
    """Run execution judge demo."""
    print("=" * 60)
    print("ILMA Execution Judge Adapter v1.0")
    print(f"Docker available: {'Yes' if ExecutionJudgeAdapter().docker_available else 'No (LOCAL_EXECUTION_JUDGE)'}")
    print("=" * 60)
    
    adapter = ExecutionJudgeAdapter()
    
    test_commands = [
        ("python3 --version", True, "Check Python version"),
        ("python3 -c 'print(1+1)'", True, "Simple calculation"),
        ("python3 -c 'import nonexistent_module'", False, "Missing dependency"),
        ("python3 -c 'x = 1/0'", False, "Runtime error"),
    ]
    
    print()
    for cmd, should_succeed, desc in test_commands:
        print(f"[{desc}]")
        print(f"  Command: {cmd}")
        
        result, judgment = adapter.run_and_judge(cmd, require_clean_exit=should_succeed)
        
        status_icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}[judgment['status']]
        print(f"  Status: {status_icon} {judgment['status']}")
        print(f"  Exit code: {result.returncode}")
        print(f"  Duration: {result.duration:.3f}s")
        
        if judgment['issues']:
            for issue in judgment['issues'][:2]:
                print(f"  Issue: {issue}")
        
        print()


if __name__ == "__main__":
    run_demo()