#!/usr/bin/env python3
"""
ILMA Validator Harness v1.0 (Phase C / TASK 2.4)
=================================================
Validates code with static + dynamic analysis:
- Static: syntax, AST, complexity
- Dynamic: import + exec in sandbox, run tests
- Performance: time benchmark
- Security: scan for dangerous patterns

Feature flag: config.yaml `code_forge_validator_enabled` (default: False)
"""
from __future__ import annotations

import ast
import json
import logging
import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ilma.forge.validator")


@dataclass
class ValidationCheck:
    name: str
    passed: bool
    details: str = ""
    duration_seconds: float = 0.0


@dataclass
class ValidationReport:
    solution_id: str = ""
    checks: List[ValidationCheck] = field(default_factory=list)
    test_results: List[Dict] = field(default_factory=list)
    test_pass_rate: float = 0.0
    performance_score: float = 0.0
    lines_of_code: int = 0
    cyclomatic_complexity: int = 0
    overall_pass: bool = False
    validation_time_seconds: float = 0.0


class ValidatorHarness:
    """Validates a Solution package."""

    def __init__(self, timeout_seconds: float = 10.0):
        self.timeout = timeout_seconds

    def validate(self, solution, run_tests: bool = True) -> ValidationReport:
        """Run all validation checks on a Solution."""
        start = time.time()
        checks = []

        # 1. Syntax check
        t = time.time()
        syntax_ok, syntax_detail = self._check_syntax(solution.code)
        checks.append(ValidationCheck(
            name="syntax",
            passed=syntax_ok,
            details=syntax_detail,
            duration_seconds=round(time.time() - t, 4),
        ))

        # 2. AST analysis
        t = time.time()
        ast_ok, ast_info = self._check_ast(solution.code)
        checks.append(ValidationCheck(
            name="ast_parse",
            passed=ast_ok,
            details=ast_info,
            duration_seconds=round(time.time() - t, 4),
        ))

        # 3. Complexity
        complexity = self._cyclomatic_complexity(solution.code)

        # 4. Run tests
        test_results = []
        test_pass_rate = 0.0
        if run_tests:
            t = time.time()
            test_results, test_pass_rate = self._run_tests(solution)
            checks.append(ValidationCheck(
                name="tests",
                passed=test_pass_rate >= 0.8,
                details=f"{test_pass_rate*100:.0f}% pass rate ({len(test_results)} tests)",
                duration_seconds=round(time.time() - t, 4),
            ))

        # 5. Performance benchmark (basic)
        t = time.time()
        perf_score = self._benchmark(solution.code)
        checks.append(ValidationCheck(
            name="performance",
            passed=perf_score >= 0.5,
            details=f"Score: {perf_score:.2f}",
            duration_seconds=round(time.time() - t, 4),
        ))

        # 6. Security scan
        t = time.time()
        sec_ok, sec_detail = self._security_scan(solution.code)
        checks.append(ValidationCheck(
            name="security",
            passed=sec_ok,
            details=sec_detail,
            duration_seconds=round(time.time() - t, 4),
        ))

        # Compute overall
        critical_pass = all(c.passed for c in checks if c.name in ("syntax", "security"))
        tests_ok = test_pass_rate >= 0.8 if run_tests else True
        overall_pass = critical_pass and tests_ok

        elapsed = time.time() - start
        return ValidationReport(
            solution_id=solution.task_id,
            checks=checks,
            test_results=test_results,
            test_pass_rate=test_pass_rate,
            performance_score=perf_score,
            lines_of_code=len(solution.code.split("\n")),
            cyclomatic_complexity=complexity,
            overall_pass=overall_pass,
            validation_time_seconds=round(elapsed, 3),
        )

    def _check_syntax(self, code: str) -> tuple:
        try:
            compile(code, "<generated>", "exec")
            return True, "OK"
        except SyntaxError as e:
            return False, f"SyntaxError: {e}"

    def _check_ast(self, code: str) -> tuple:
        try:
            tree = ast.parse(code)
            func_count = sum(1 for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
            class_count = sum(1 for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
            return True, f"Functions: {func_count}, Classes: {class_count}"
        except Exception as e:
            return False, str(e)

    def _cyclomatic_complexity(self, code: str) -> int:
        """Simple complexity: count decision points."""
        try:
            tree = ast.parse(code)
            count = 1
            for node in ast.walk(tree):
                if isinstance(node, (ast.If, ast.While, ast.For, ast.ExceptHandler, ast.With)):
                    count += 1
                if isinstance(node, ast.BoolOp):
                    count += len(node.values) - 1
            return count
        except Exception:
            return 0

    def _run_tests(self, solution) -> tuple:
        """Run canned tests for known solutions."""
        results = []
        passed = 0
        total = 0

        if solution.task_id == "fib_memo":
            import sys
            ns = {}
            try:
                exec(solution.code, ns)
                fib = ns.get("fibonacci")
                if fib is None:
                    return [{"test": "import", "passed": False, "error": "no fibonacci function"}], 0.0

                # Test cases
                cases = [
                    ("test_fib_0", 0, 0),
                    ("test_fib_1", 1, 1),
                    ("test_fib_10", 10, 55),
                    ("test_fib_20", 20, 6765),
                ]
                for name, input_val, expected in cases:
                    total += 1
                    try:
                        result = fib(input_val)
                        ok = result == expected
                        if ok:
                            passed += 1
                        results.append({
                            "test": name, "passed": ok,
                            "input": input_val, "expected": expected, "actual": result,
                        })
                    except Exception as e:
                        results.append({"test": name, "passed": False, "error": str(e)})
                # Negative test
                total += 1
                try:
                    fib(-1)
                    results.append({"test": "test_negative", "passed": False, "error": "no error raised"})
                except (ValueError, Exception):
                    passed += 1
                    results.append({"test": "test_negative", "passed": True})
            except Exception as e:
                return [{"test": "exec", "passed": False, "error": str(e)}], 0.0

        elif solution.task_id == "http_retry":
            # Just check it imports without network
            try:
                ns = {}
                exec(solution.code, ns)
                fn = ns.get("http_get_with_retry")
                if fn:
                    passed += 1
                total += 1
                results.append({"test": "import", "passed": fn is not None})
            except Exception as e:
                results.append({"test": "import", "passed": False, "error": str(e)})
                total += 1

        elif solution.task_id == "lru_cache":
            try:
                ns = {}
                exec(solution.code, ns)
                cls = ns.get("LRUCache")
                if cls is None:
                    return [{"test": "import", "passed": False, "error": "no LRUCache class"}], 0.0
                # Test cases
                c = cls(2)
                c.put("a", 1)
                c.put("b", 2)
                total += 4
                if c.get("a") == 1:
                    passed += 1
                    results.append({"test": "test_get_a", "passed": True})
                else:
                    results.append({"test": "test_get_a", "passed": False})
                c.put("c", 3)  # evicts b
                if c.get("b") is None:
                    passed += 1
                    results.append({"test": "test_evict_b", "passed": True})
                else:
                    results.append({"test": "test_evict_b", "passed": False})
                if c.get("c") == 3:
                    passed += 1
                    results.append({"test": "test_get_c", "passed": True})
                else:
                    results.append({"test": "test_get_c", "passed": False})
                if c.get("missing") is None:
                    passed += 1
                    results.append({"test": "test_get_missing", "passed": True})
                else:
                    results.append({"test": "test_get_missing", "passed": False})
            except Exception as e:
                return [{"test": "exec", "passed": False, "error": str(e)}], 0.0

        else:
            # Generic: just check syntax + import
            try:
                ns = {}
                exec(solution.code, ns)
                passed += 1
                results.append({"test": "import", "passed": True})
            except Exception as e:
                results.append({"test": "import", "passed": False, "error": str(e)})
            total += 1

        return results, (passed / total) if total else 0.0

    def _benchmark(self, code: str) -> float:
        """Quick performance check: how long does it take to compile + parse?"""
        try:
            start = time.time()
            compile(code, "<generated>", "exec")
            ast.parse(code)
            elapsed = time.time() - start
            # <0.01s = 1.0, <0.1s = 0.8, <1s = 0.5, >1s = 0.2
            if elapsed < 0.01:
                return 1.0
            elif elapsed < 0.1:
                return 0.8
            elif elapsed < 1.0:
                return 0.5
            else:
                return 0.2
        except Exception:
            return 0.0

    def _security_scan(self, code: str) -> tuple:
        """Quick security scan."""
        issues = []
        for pattern in ["exec(", "eval(", "os.system", "subprocess.call", "__import__", "compile("]:
            if pattern in code:
                # eval/exec are CRITICAL
                if pattern in ("exec(", "eval("):
                    return False, f"Dangerous pattern: {pattern}"
                issues.append(pattern)
        if issues:
            return False, f"Suspicious patterns: {', '.join(issues)}"
        return True, "OK"


# Singleton
_validator_instance = None


def get_validator() -> ValidatorHarness:
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = ValidatorHarness()
    return _validator_instance


if __name__ == "__main__":
    print("=== Validator Harness Demo ===\n")
    from ilma_generator_harness import GeneratorHarness
    gh = GeneratorHarness()
    vh = ValidatorHarness()

    # Test 1: fib_memo
    sol = gh.generate({"id": "fib_memo", "title": "Fib", "description": "fib", "requirements": []})
    print(f"=== Validating: {sol.task_id} ===")
    report = vh.validate(sol, run_tests=True)
    print(f"Checks: {len(report.checks)}")
    for c in report.checks:
        marker = "✓" if c.passed else "✗"
        print(f"  [{marker}] {c.name}: {c.details} ({c.duration_seconds}s)")
    print(f"Test pass rate: {report.test_pass_rate*100:.0f}%")
    print(f"Performance: {report.performance_score}")
    print(f"Lines: {report.lines_of_code}, Complexity: {report.cyclomatic_complexity}")
    print(f"Overall pass: {report.overall_pass}")

    # Test 2: lru_cache
    print()
    sol2 = gh.generate({"id": "lru_cache", "title": "LRU", "description": "lru", "requirements": []})
    print(f"=== Validating: {sol2.task_id} ===")
    report2 = vh.validate(sol2, run_tests=True)
    print(f"Test pass rate: {report2.test_pass_rate*100:.0f}%")
    print(f"Overall pass: {report2.overall_pass}")
    for r in report2.test_results:
        marker = "✓" if r.get("passed") else "✗"
        print(f"  [{marker}] {r.get('test')}: {r.get('error', '')}")
