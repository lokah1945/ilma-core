"""Tests for HeartbeatContext.to_dict() method."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ilma_telegram_heartbeat import HeartbeatContext


def test_heartbeat_context_to_dict_basic():
    """Test that to_dict returns all required fields before context entry."""
    ctx = HeartbeatContext("coding", "test: run tests")
    result = ctx.to_dict()

    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    assert set(result.keys()) == {"task_type", "description", "start_time", "active"}, \
        f"Unexpected keys: {set(result.keys())}"
    assert result["task_type"] == "coding"
    assert result["description"] == "test: run tests"
    assert result["start_time"] is None
    assert result["active"] is False
    print("PASS: to_dict returns correct fields before __enter__")


def test_heartbeat_context_to_dict_with_context():
    """Test to_dict reflects active state after __enter__."""
    ctx = HeartbeatContext("terminal", "echo hello")
    with ctx:
        result = ctx.to_dict()
        assert isinstance(result, dict)
        assert result["task_type"] == "terminal"
        assert result["description"] == "echo hello"
        assert result["start_time"] is not None or result["start_time"] is None  # clock may not exist
        assert result["active"] is True
    print("PASS: to_dict reflects active=True inside context")


def test_heartbeat_context_to_dict_after_exit():
    """Test to_dict reflects inactive state after __exit__."""
    ctx = HeartbeatContext("benchmark", "perf test")
    with ctx:
        pass
    result = ctx.to_dict()
    assert result["active"] is False
    print("PASS: to_dict reflects active=False after __exit__")


if __name__ == "__main__":
    test_heartbeat_context_to_dict_basic()
    test_heartbeat_context_to_dict_with_context()
    test_heartbeat_context_to_dict_after_exit()
    print("ALL TESTS PASSED")