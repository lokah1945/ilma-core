# Heartbeat-as-Context-Manager Pattern (Phase 4D-A)

## Pattern

When wrapping any long-running operation (terminal command, test suite, subagent, benchmark) with a heartbeat, the **context manager** form is the cleanest integration point:

```python
class HeartbeatContext:
    def __init__(self, task_type: str, description: str):
        self.task_type = task_type
        self.description = description
        self.hb = None

    def __enter__(self):
        if self.task_type == "terminal":
            self.hb = heartbeat_for_terminal(self.description)
        elif self.task_type == "test":
            self.hb = heartbeat_for_test_runner(self.description)
        # ...
        return self.hb

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.hb:
            self.hb.pulse(f"exit: {exc_type.__name__ if exc_type else 'success'}")
            self.hb.stop()
        return False
```

## Why This Beats Manual Start/Stop

- **No leaked heartbeats** if the inner code raises — `__exit__` runs even on exception
- **Pulse-on-exit** records the success/failure mode in the progress log
- **Single line of caller code**: `with HeartbeatContext("test", "pytest tests/"): run()`

## Activation Threshold (Lesson)

A naive "always heartbeat" will spam logs on small operations. The pattern that worked:

```python
if len(message) > 500:  # Only heartbeat for substantial tasks
    _hb = heartbeat_for_subagent(...)
```

500 chars is a heuristic — for pure routing decisions, it's fine. For subagents with 50-char messages, no heartbeat. Adjust based on real usage.

## Reusable Helpers (5 production wrappers)

```python
heartbeat_for_terminal(command, timeout_s=600)
heartbeat_for_coding_worker(worker_lane, task_desc)
heartbeat_for_benchmark_runner(benchmark_name)
heartbeat_for_test_runner(test_suite)
heartbeat_for_subagent(task_id_hint, description)
```

Each returns a `TelegramHeartbeat` instance with auto-generated task_id (`coding-lane-A-86e7f0`, `test-8527323a`, etc.). The caller is responsible for `.stop()` or using `HeartbeatContext`.

## Non-Critical Pattern

The heartbeat is wrapped in `try/except` everywhere it integrates with existing code:

```python
try:
    from ilma_telegram_heartbeat import heartbeat_for_subagent
    _hb = heartbeat_for_subagent(...)
except Exception:
    pass  # Heartbeat is non-critical
```

This is intentional: **heartbeat failure must never break the main task**. It is observability, not a control flow.

## Reference

- File: `ilma_telegram_heartbeat.py` (now 388 lines, +136 from Phase 4D-A)
- Tests: 8/8 pass in `ILMA_PHASE_4D_L2_TEST_RESULTS.json`
- Integration points wired: `ilma_subagent_router.py` `_execute()` method
