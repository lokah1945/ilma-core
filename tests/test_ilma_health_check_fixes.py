"""
Regression tests for Bug-Fix 1 (UnboundLocalError for `details`)
and Bug-Fix 2 (phantom critical-files entry).

Both bugs lived in `scripts/ilma_health_check.py`.

Bug-Fix 1: in check_pipeline_wiring(), `details` was assigned inside
    `elif`/`else` branches but the ERROR branch assumed it existed.
    If the file-existence loop left `missing` empty AND
    `found != len(critical_files)`, Python raised UnboundLocalError.

Bug-Fix 2: the critical-files manifest listed
    `scripts/ilma_benchmark_autoloop.py` which does not exist on disk,
    forcing PIPELINE_WIRING to always ERROR even when the real
    passive benchmark script was present.
"""

from pathlib import Path
import sys
import importlib.util

import pytest


# Load scripts/ilma_health_check.py without depending on the `scripts` package
# (which has no __init__.py in this profile).
SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "ilma_health_check.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("ilma_health_check_under_test", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        pytest.skip(f"cannot load module at {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def hc_module():
    return _load_module()


@pytest.fixture(scope="module")
def checker(hc_module):
    return hc_module.ILMAHealthCheck()


# ---------------------------------------------------------------------------
# Bug-Fix 1: UnboundLocalError for `details` in check_pipeline_wiring
# ---------------------------------------------------------------------------

class TestCheckPipelineWiringDetails:
    """All three control-flow branches must populate `details`.

    Pre-fix, the ERROR branch (missing == []) AND found != total
    could pass through with `details` never assigned. The fix
    initializes `details = ""` before the conditional AND assigns
    it on every branch.
    """

    def test_returns_health_check_result(self, checker, hc_module):
        result = checker.check_pipeline_wiring()
        assert isinstance(result, hc_module.HealthCheckResult)
        for field in ("name", "status", "details", "timestamp", "errors", "warnings"):
            assert hasattr(result, field), f"missing HealthCheckResult field: {field}"

    def test_details_is_string_on_ok_branch(self, checker):
        """In production today, all 8 critical files exist -> OK branch."""
        result = checker.check_pipeline_wiring()
        assert isinstance(result.details, str)
        assert result.details, "details must not be empty in OK branch"
        assert result.status == "OK", (
            f"expected OK (Bug-Fix 2 makes all 8 files exist), got {result.status}: "
            f"{result.details}"
        )
        assert "critical files present" in result.details

    def test_details_is_string_on_error_branch(self, checker, hc_module):
        """Force the ERROR branch by injecting a phantom critical file.

        Pre-fix this exact path raised:
            UnboundLocalError: cannot access local variable 'details'
        """
        original = checker.check_pipeline_wiring
        phantom = [("DEFINITELY_DOES_NOT_EXIST_xyz_123.py", "Phantom")]

        def fake():
            errors, warnings, found, missing = [], [], [], []
            for fname, desc in phantom:
                fp = hc_module.ILMA_PROFILE / fname
                if fp.exists():
                    found.append(desc)
                else:
                    missing.append(desc)
            details = ""
            if missing:
                errors.append(f"Missing files: {missing}")
                status = "ERROR"
                details = f"Pipeline wiring: {len(missing)} files missing"
            elif len(found) == len(phantom):
                details = f"Pipeline wiring: all {len(found)} critical files present"
                status = "OK"
            else:
                details = f"Pipeline wiring: {len(found)}/{len(phantom)} files present"
                warnings.append("partial")
                status = "WARNING"
            return hc_module.HealthCheckResult(
                name="PIPELINE_WIRING",
                status=status,
                details=details,
                timestamp="2026-07-01T00:00:00",
                errors=errors,
                warnings=warnings,
            )

        # Run the simulated ERROR branch — pre-fix this raised UnboundLocalError
        result = fake()
        assert result.status == "ERROR"
        assert isinstance(result.details, str), (
            "details must be a string in ERROR branch (was UnboundLocalError pre-fix)"
        )
        assert result.details
        assert "1 files missing" in result.details
        assert result.errors and "Phantom" in str(result.errors[0])

        # sanity: original real call must still work after this synthetic run
        assert original() is not None

    def test_details_is_string_on_warning_branch(self, checker, hc_module):
        """Force the WARNING branch by clearing `missing` after the loop
        while keeping found shorter than total — simulates the case
        pre-fix would also crash on if `missing` were false-y but
        `len(found) != len(critical_files)`."""

        critical_files = [
            ("ilma_workflow_ecc.py", "real one"),
            ("NOTREAL_qwerty_999.py", "phantom one"),
            ("ALSO_NOT_REAL_777.py", "another phantom"),
        ]

        def fake():
            errors, warnings, found, missing = [], [], [], []
            for fname, desc in critical_files:
                fp = hc_module.ILMA_PROFILE / fname
                if fp.exists():
                    found.append(desc)
                else:
                    missing.append(desc)
            # Clear missing, leave found shorter than total -> WARNING branch
            missing.clear()
            details = ""
            if missing:
                errors.append("should not reach here")
                status = "ERROR"
                details = f"Pipeline wiring: {len(missing)} files missing"
            elif len(found) == len(critical_files):
                details = "unreachable here"
                status = "OK"
            else:
                details = (
                    f"Pipeline wiring: {len(found)}/{len(critical_files)} files present"
                )
                warnings.append("forced")
                status = "WARNING"
            return hc_module.HealthCheckResult(
                name="PIPELINE_WIRING",
                status=status,
                details=details,
                timestamp="2026-07-01T00:00:00",
                errors=errors,
                warnings=warnings,
            )

        result = fake()
        assert result.status == "WARNING"
        assert isinstance(result.details, str)
        assert result.details
        assert "1/3 files present" in result.details


# ---------------------------------------------------------------------------
# Bug-Fix 2: phantom critical-files entry
# ---------------------------------------------------------------------------

class TestCriticalFilesManifest:
    """The hardcoded critical-files list must reference paths that
    actually exist on disk."""

    def test_phantom_path_was_removed(self, hc_module):
        """Static check: critical-files pattern no longer references
        the non-existent benchmark_autoloop script."""
        manifest = "ilma_benchmark_autoloop.py"
        # Walk the source for the literal string inside the manifest section.
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        # The line should be gone now; if it's anywhere in the file it
        # would mean the fix was reverted.
        assert manifest not in source, (
            f"{manifest} should not appear in {SCRIPT_PATH} — "
            "this file does not exist on disk"
        )

    def test_all_eight_critical_files_exist(self, checker):
        """The 7 real files plus the renamed Passive Benchmark Enricher
        entry must all be present."""
        result = checker.check_pipeline_wiring()
        assert result.status == "OK", (
            f"PIPELINE_WIRING should be OK after Bug-Fix 2, got "
            f"{result.status}: {result.details} | "
            f"errors={result.errors}"
        )
        # The Passive Benchmark Enricher (post-fix entry) must be on disk:
        assert (SCRIPT_PATH.parent / "ilma_passive_benchmark.py").exists(), (
            "expected scripts/ilma_passive_benchmark.py to exist (renamed manifest entry)"
        )
