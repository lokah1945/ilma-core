#!/usr/bin/env python3
"""Tests for ilma_phase50_truth_validator.py"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "scripts")
from ilma_phase50_truth_validator import Phase50TruthValidator


def test_all_checks_pass():
    """Valid trace with all checks passing."""
    trace = {
        "wall_clock_seconds": 1800.5,
        "exit_code": 0,
        "heartbeats": list(range(30)),
        "checkpoints": [{"id": 1}, {"id": 2}],
        "cycles": [
            {"lessons_retrieved": [{"id": "L1"}, {"id": "L2"}]},
            {"lessons_retrieved": [{"id": "L3"}]},
            {"lessons_retrieved": []},
        ],
        "judge_results": [
            {"score": 85},
            {"score": 80},
            {"score": 90},
        ],
        "lesson_reuse_count": 3,
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(trace, f)
        path = Path(f.name)

    try:
        v = Phase50TruthValidator(path)
        ec, status = v.validate()
        assert ec == 0, f"Expected exit 0, got {ec}"
        assert "PASS" in status, f"Expected PASS, got {status}"
    finally:
        path.unlink()
    print("✅ test_all_checks_pass PASS")


def test_wall_clock_fail():
    """Wall-clock below 1800s should fail."""
    trace = {
        "wall_clock_seconds": 1700,
        "exit_code": 0,
        "heartbeats": list(range(30)),
        "checkpoints": [{"id": 1}, {"id": 2}],
        "cycles": [{"lessons_retrieved": [{"id": "L1"}]}],
        "judge_results": [{"score": 85}],
        "lesson_reuse_count": 1,
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(trace, f)
        path = Path(f.name)

    try:
        v = Phase50TruthValidator(path)
        ec, status = v.validate()
        assert ec == 1, f"Expected exit 1, got {ec}"
    finally:
        path.unlink()
    print("✅ test_wall_clock_fail PASS")


def test_manufactured_reuse_count():
    """reuse_count > 0 but lessons_retrieved = 0 should fail."""
    trace = {
        "wall_clock_seconds": 1850,
        "exit_code": 0,
        "heartbeats": list(range(30)),
        "checkpoints": [{"id": 1}, {"id": 2}],
        "cycles": [
            {"lessons_retrieved": []},
            {"lessons_retrieved": []},
            {"lessons_retrieved": []},
        ],
        "judge_results": [
            {"score": 85},
            {"score": 80},
            {"score": 90},
        ],  # 3 judges >= 3 threshold
        "lesson_reuse_count": 8,  # MANUFACTURED — 0 retrieved but count = 8
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(trace, f)
        path = Path(f.name)

    try:
        v = Phase50TruthValidator(path)
        ec, status = v.validate()
        # Wall-clock OK, only retrieval broken → PARTIAL (exit 2)
        assert ec == 2, f"Expected exit 2 (PARTIAL), got {ec}, status={status}"
        assert "retrieval invalid" in status, f"Expected retrieval invalid in status, got {status}"
    finally:
        path.unlink()
    print("✅ test_manufactured_reuse_count PASS")


def test_no_cycles_with_retrieval():
    """No cycles with retrieval should fail."""
    trace = {
        "wall_clock_seconds": 1900,
        "exit_code": 0,
        "heartbeats": list(range(30)),
        "checkpoints": [{"id": 1}, {"id": 2}],
        "cycles": [
            {"lessons_retrieved": []},
            {"lessons_retrieved": []},
            {"lessons_retrieved": []},
        ],
        "judge_results": [
            {"score": 85},
            {"score": 80},
            {"score": 90},
        ],  # 3 judges >= 3 threshold
        "lesson_reuse_count": 0,  # Consistent with 0 retrieval
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(trace, f)
        path = Path(f.name)

    try:
        v = Phase50TruthValidator(path)
        ec, status = v.validate()
        # Basic checks pass, retrieval broken → PARTIAL (exit 2)
        assert ec == 2, f"Expected exit 2 (PARTIAL), got {ec}, status={status}"
    finally:
        path.unlink()
    print("✅ test_no_cycles_with_retrieval PASS")


def test_partial_pass_scenario():
    """Wall-clock OK but retrieval broken = PARTIAL."""
    trace = {
        "wall_clock_seconds": 1805,
        "exit_code": 0,
        "heartbeats": list(range(29)),
        "checkpoints": [{"id": 1}, {"id": 2}],
        "cycles": [
            {"lessons_retrieved": []},
            {"lessons_retrieved": []},
            {"lessons_retrieved": []},
        ],  # 3 cycles >= 3 threshold
        "judge_results": [
            {"score": 85},
            {"score": 80},
            {"score": 90},
        ],  # 3 judges >= 3 threshold
        "lesson_reuse_count": 8,  # Manufactured
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(trace, f)
        path = Path(f.name)

    try:
        v = Phase50TruthValidator(path)
        ec, status = v.validate()
        assert ec == 2, f"Expected exit 2 (PARTIAL), got {ec}, status={status}"
    finally:
        path.unlink()
    print("✅ test_partial_pass_scenario PASS")


def test_reasonable_reuse():
    """reuse_count reasonable given retrieval = PASS."""
    trace = {
        "wall_clock_seconds": 1850,
        "exit_code": 0,
        "heartbeats": list(range(30)),
        "checkpoints": [{"id": 1}, {"id": 2}],
        "cycles": [
            {"lessons_retrieved": [{"id": "L1"}]},
            {"lessons_retrieved": [{"id": "L2"}, {"id": "L3"}]},
            {"lessons_retrieved": []},
        ],  # 3 cycles >= 3 threshold
        "judge_results": [
            {"score": 85},
            {"score": 80},
            {"score": 90},
        ],  # 3 judges >= 3 threshold
        "lesson_reuse_count": 3,  # 3 retrieved, 3 reuse = reasonable
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(trace, f)
        path = Path(f.name)

    try:
        v = Phase50TruthValidator(path)
        ec, status = v.validate()
        assert ec == 0, f"Expected exit 0, got {ec}"
    finally:
        path.unlink()
    print("✅ test_reasonable_reuse PASS")


def test_trace_not_found():
    """Missing trace file should fail."""
    v = Phase50TruthValidator(Path("/nonexistent/trace.json"))
    ec, status = v.validate()
    assert ec == 1, f"Expected exit 1, got {ec}"
    assert "NOT FOUND" in status, f"Expected NOT FOUND in status, got {status}"
    print("✅ test_trace_not_found PASS")


def main():
    print("Running ilma_phase50_truth_validator tests...\n")
    test_all_checks_pass()
    test_wall_clock_fail()
    test_manufactured_reuse_count()
    test_no_cycles_with_retrieval()
    test_partial_pass_scenario()
    test_reasonable_reuse()
    test_trace_not_found()
    print("\n✅ All tests passed!")


if __name__ == "__main__":
    main()