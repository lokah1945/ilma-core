#!/usr/bin/env python3
"""
Test suite for L2-01: Router Trace Logging
Phase 4F Canary

Verifies that get_best_model() calls _log_route_trace() and writes
JSON traces to /root/.hermes/profiles/ilma/logs/router_traces.ndjson.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure the ilma profile path is importable
ILMA_PROFILE = Path(os.environ.get("ILMA_PROFILE", "/root/.hermes/profiles/ilma"))
import sys
if str(ILMA_PROFILE) not in sys.path:
    sys.path.insert(0, str(ILMA_PROFILE.parent))


class TestRouterTraceLogging(unittest.TestCase):
    """Tests for router trace logging functionality."""

    @classmethod
    def setUpClass(cls):
        cls.ilma_profile = Path("/root/.hermes/profiles/ilma")
        cls.trace_file = cls.ilma_profile / "logs" / "router_traces.ndjson"
        cls.router_module_path = cls.ilma_profile / "ilma_model_router.py"

        # Read initial line count if file exists
        cls._initial_lines = 0
        if cls.trace_file.exists():
            with open(cls.trace_file) as f:
                cls._initial_lines = len(f.readlines())

    def setUp(self):
        # Count lines before this test
        if self.trace_file.exists():
            with open(self.trace_file) as f:
                self._before_lines = len(f.readlines())
        else:
            self._before_lines = 0

    def tearDown(self):
        # No cleanup — we want to inspect the actual trace file
        pass

    def test_01_router_module_imports(self):
        """Router module must import and have TRACE_FILE defined."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "ilma_model_router", self.router_module_path
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertTrue(
            hasattr(module, "TRACE_FILE"),
            "ilma_model_router must define TRACE_FILE constant"
        )
        self.assertIn("router_traces.ndjson", str(module.TRACE_FILE))
        print(f"  TRACE_FILE = {module.TRACE_FILE}")

    def test_02_get_best_model_is_callable(self):
        """ILMAUnifiedRouter.get_best_model must be a callable method."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "ilma_model_router", self.router_module_path
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        router = module.ILMAUnifiedRouter.__new__(module.ILMAUnifiedRouter)
        router._master_db = None
        router._health_state = {}
        router._failure_count = {}
        router._cooldown_until = {}
        router._recent_used = {}
        router.allow_paid = True
        self.assertTrue(
            callable(getattr(router, "get_best_model", None)),
            "ILMAUnifiedRouter must have a get_best_model method"
        )

    def test_03_trace_file_location_exists(self):
        """TRACE_FILE path must be resolvable and logs directory must exist."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "ilma_model_router", self.router_module_path
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        trace_path = module.TRACE_FILE
        self.assertTrue(
            trace_path.parent.exists(),
            f"Logs directory must exist: {trace_path.parent}"
        )
        print(f"  Trace file parent exists: {trace_path.parent}")

    def test_04_get_best_model_writes_trace(self):
        """get_best_model() must append at least one JSON line to router_traces.ndjson."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "ilma_model_router", self.router_module_path
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        router = module.ILMAUnifiedRouter.__new__(module.ILMAUnifiedRouter)
        router._master_db = None
        router._health_state = {}
        router._failure_count = {}
        router._cooldown_until = {}
        router._recent_used = {}
        router.allow_paid = True

        # Mock _load_master to return empty so we hit emergency fallback
        with patch.object(router, "_load_master", return_value={"providers": {}}):
            result = router.get_best_model("general")

        self.assertIsInstance(result, dict)
        self.assertIn("model_id", result)

        # Read current trace file
        if not self.trace_file.exists():
            self.fail("router_traces.ndjson was not created")

        with open(self.trace_file) as f:
            all_lines = f.readlines()

        new_lines = all_lines[self._before_lines:]
        self.assertGreater(
            len(new_lines), 0,
            f"No new trace lines written. Before={self._before_lines}, "
            f"Total={len(all_lines)}"
        )

        # Verify last line is valid JSON with expected keys
        last_entry = json.loads(new_lines[-1].strip())
        self.assertIn("timestamp", last_entry)
        self.assertIn("event", last_entry)
        self.assertIn("task_type", last_entry)
        # fallback_used entries (no candidates) don't have best_model_id
        # only routing_complete entries have full model selection info
        if not last_entry.get("fallback_used"):
            self.assertIn("best_model_id", last_entry)
        print(f"  Last trace entry event: {last_entry.get('event')}")
        print(f"  Last trace entry model: {last_entry.get('best_model_id')}")
        print(f"  Fallback used: {last_entry.get('fallback_used')}")

    def test_05_trace_entries_are_valid_json(self):
        """All new trace entries must be valid JSON objects."""
        if not self.trace_file.exists():
            self.skipTest("router_traces.ndjson does not exist yet")

        with open(self.trace_file) as f:
            all_lines = f.readlines()

        new_lines = all_lines[self._before_lines:]
        for i, line in enumerate(new_lines):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                self.assertIsInstance(obj, dict, f"Line {i} must be a JSON object")
                self.assertIn("timestamp", obj)
            except json.JSONDecodeError as e:
                self.fail(f"Line {i} is not valid JSON: {e}")

    def test_06_trace_event_types(self):
        """Trace entries must have one of the expected event types."""
        if not self.trace_file.exists():
            self.skipTest("router_traces.ndjson does not exist yet")

        valid_events = {
            "candidates_built",
            "scoring_complete",
            "routing_complete",
        }

        with open(self.trace_file) as f:
            all_lines = f.readlines()

        new_lines = all_lines[self._before_lines:]
        for i, line in enumerate(new_lines):
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            self.assertIn(
                obj.get("event"),
                valid_events,
                f"Line {i} has unexpected event: {obj.get('event')}"
            )

    def test_07_trace_contains_routing_info(self):
        """Trace entries must contain the expected fields for their event type."""
        if not self.trace_file.exists():
            self.skipTest("router_traces.ndjson does not exist yet")

        with open(self.trace_file) as f:
            all_lines = f.readlines()

        new_lines = all_lines[self._before_lines:]
        self.assertGreater(
            len(new_lines), 0,
            f"No new trace lines for this test run. "
            f"before={self._before_lines}, total={len(all_lines)}"
        )

        for l in new_lines:
            l = l.strip()
            if not l:
                continue
            obj = json.loads(l)
            self.assertIn("event", obj)
            event = obj["event"]

            if event == "routing_complete":
                # Full routing info only on successful route
                self.assertIn("best_model_id", obj)
                self.assertIn("composite_score", obj)
                self.assertIn("capability_score", obj)
                self.assertIn("routing_reason", obj)
            elif event == "candidates_built":
                # Fallback case
                self.assertTrue(obj.get("fallback_used"))
                self.assertIn("candidates", obj)
                self.assertGreaterEqual(obj["candidates"], 0)
            elif event == "scoring_complete":
                # Fallback after scoring
                self.assertTrue(obj.get("fallback_used"))
                self.assertIn("scored", obj)


if __name__ == "__main__":
    print("=" * 60)
    print("L2-01: Router Trace Logging Tests — Phase 4F Canary")
    print("=" * 60)
    unittest.main(verbosity=2)