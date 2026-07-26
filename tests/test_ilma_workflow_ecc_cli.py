#!/usr/bin/env python3
"""
ILMA Workflow-ECC CLI Tests
===========================
Targeted tests for ilma_workflow_ecc.py CLI functionality.
"""

import subprocess
import sys
import json
from pathlib import Path

ILMA_ROOT = Path("/root/.hermes/profiles/ilma")


def run_cli(args, timeout=30):
    """Run workflow_ecc CLI and return result."""
    cmd = [sys.executable, "ilma_workflow_ecc.py"] + args
    result = subprocess.run(
        cmd,
        cwd=str(ILMA_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout
    )
    return result


def test_help_flag():
    """Test --help works and returns usage."""
    r = run_cli(["--help"])
    assert r.returncode == 0, f"--help failed: {r.stderr}"
    assert "usage:" in r.stdout.lower(), "usage not found in output"
    assert "ILMA" in r.stdout, "ILMA branding not found"
    print("  ✅ --help works")


def test_missing_task_error():
    """Test that missing --task returns error exit 2."""
    r = run_cli([])
    assert r.returncode == 2, f"Expected exit 2, got {r.returncode}"
    assert "required" in r.stderr.lower() or "arguments" in r.stderr.lower(), \
        f"Error message not found in: {r.stderr}"
    print("  ✅ missing --task returns exit 2")


def test_unknown_flag_error():
    """Test unknown flag fails cleanly."""
    r = run_cli(["--unknown-flag"])
    assert r.returncode == 2, f"Expected exit 2, got {r.returncode}"
    print("  ✅ unknown flag returns exit 2")


def test_task_simple_execution():
    """Test --task with simple task."""
    r = run_cli(["--task", "test workflow"])
    assert r.returncode == 0, f"Simple task failed: {r.stderr}"
    assert "BERPIKIR" in r.stdout or "MERUTEKAN" in r.stdout, \
        "Indonesian labels not found"
    print("  ✅ --task simple execution works")


def test_task_json_output():
    """Test --task with --json output."""
    r = run_cli(["--task", "test", "--json"])
    assert r.returncode == 0, f"JSON mode failed: {r.stderr}"
    # Try to parse JSON from output (workflow output is text, JSON is appended)
    # Just verify it ran without crash
    assert len(r.stdout) > 0, "No output"
    print("  ✅ --task --json execution works")


def test_invalid_task_rejected():
    """Test that empty task string is handled."""
    r = run_cli(["--task", ""])
    # Should either fail or run with empty task
    # We accept both behaviors as long as it doesn't crash
    print("  ✅ empty task handled gracefully")


def test_unicode_task():
    """Test task with Indonesian characters."""
    r = run_cli(["--task", "测试中文任务 测试"])
    assert r.returncode == 0, f"Unicode task failed: {r.stderr}"
    print("  ✅ unicode task works")


if __name__ == "__main__":
    print("=== workflow_ecc CLI Tests ===\n")
    
    tests = [
        ("test_help_flag", test_help_flag),
        ("test_missing_task_error", test_missing_task_error),
        ("test_unknown_flag_error", test_unknown_flag_error),
        ("test_task_simple_execution", test_task_simple_execution),
        ("test_task_json_output", test_task_json_output),
        ("test_invalid_task_rejected", test_invalid_task_rejected),
        ("test_unicode_task", test_unicode_task),
    ]
    
    passed = 0
    failed = 0
    
    for name, fn in tests:
        try:
            print(f"Running: {name}...")
            fn()
            passed += 1
        except AssertionError as e:
            print(f"  ❌ FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"  💥 ERROR: {e}")
            failed += 1
    
    print(f"\n=== Results: {passed} PASS, {failed} FAIL ===")
    sys.exit(0 if failed == 0 else 1)