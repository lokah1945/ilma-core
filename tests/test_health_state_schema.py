"""
Health State Schema Validation Tests - L2-04

Validates ilma_model_health.json against expected schema:
- last_updated field (ISO format)
- providers dict (not models)
- each provider has status and last_checked
- health_score at top level
- 21 providers expected
"""

import json
import os
import pytest
from datetime import datetime
from typing import Any

# Path to health state file
HEALTH_STATE_PATH = "/root/.hermes/profiles/ilma/state/ilma_model_health.json"


class TestHealthStateSchema:
    """Test suite for health state schema validation."""

    @pytest.fixture
    def health_data(self) -> dict[str, Any]:
        """Load health state JSON file."""
        if not os.path.exists(HEALTH_STATE_PATH):
            pytest.fail(f"Health state file not found: {HEALTH_STATE_PATH}")
        with open(HEALTH_STATE_PATH, "r") as f:
            return json.load(f)

    def test_file_exists(self):
        """Verify health state file exists."""
        assert os.path.exists(HEALTH_STATE_PATH), f"File not found: {HEALTH_STATE_PATH}"

    def test_last_updated_is_iso_format(self, health_data: dict[str, Any]):
        """Verify last_updated field exists and is valid ISO 8601 format."""
        assert "last_updated" in health_data, "Missing 'last_updated' field"
        last_updated = health_data["last_updated"]
        
        # Parse ISO format - should be able to parse without error
        try:
            datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
        except (ValueError, AttributeError) as e:
            pytest.fail(f"'last_updated' is not valid ISO format: {last_updated}. Error: {e}")

    def test_providers_dict_exists(self, health_data: dict[str, Any]):
        """Verify 'providers' dict exists (not 'models')."""
        assert "providers" in health_data, "Missing 'providers' dict. Found keys: " + str(health_data.keys())
        
        providers = health_data["providers"]
        assert isinstance(providers, dict), f"'providers' should be a dict, got {type(providers)}"

    def test_health_score_at_top_level(self, health_data: dict[str, Any]):
        """Verify health_score exists at top level."""
        assert "health_score" in health_data, "Missing 'health_score' at top level"
        health_score = health_data["health_score"]
        assert isinstance(health_score, (int, float)), f"'health_score' should be numeric, got {type(health_score)}"
        assert 0 <= health_score <= 100, f"'health_score' should be 0-100, got {health_score}"

    def test_each_provider_has_status_and_last_checked(self, health_data: dict[str, Any]):
        """Verify each provider has 'status' and 'last_checked' fields."""
        if "providers" not in health_data:
            pytest.skip("providers dict not present - schema validation failed earlier")
        
        providers = health_data["providers"]
        
        for provider_name, provider_data in providers.items():
            assert "status" in provider_data, f"Provider '{provider_name}' missing 'status' field"
            assert "last_checked" in provider_data, f"Provider '{provider_name}' missing 'last_checked' field"
            
            # Validate status is a known value
            valid_statuses = {"healthy", "degraded", "unhealthy", "disabled", "unknown"}
            assert provider_data["status"] in valid_statuses, \
                f"Provider '{provider_name}' has invalid status: {provider_data['status']}"

    def test_expected_provider_count(self, health_data: dict[str, Any]):
        """Verify there are 21 providers as expected."""
        if "providers" not in health_data:
            pytest.skip("providers dict not present - schema validation failed earlier")
        
        providers = health_data["providers"]
        provider_count = len(providers)
        
        assert provider_count == 21, \
            f"Expected 21 providers, found {provider_count}. Providers: {list(providers.keys())}"


class TestHealthStateSchemaActual:
    """Test suite for ACTUAL schema in the health state file (for documentation)."""
    
    def test_actual_schema_structure(self):
        """Document what the actual schema looks like."""
        if not os.path.exists(HEALTH_STATE_PATH):
            pytest.fail(f"Health state file not found: {HEALTH_STATE_PATH}")
        
        with open(HEALTH_STATE_PATH, "r") as f:
            health_data = json.load(f)
        
        # Document actual structure
        actual_keys = list(health_data.keys())
        
        # Check if it uses 'models' instead of 'providers'
        if "models" in health_data:
            models = health_data["models"]
            model_entries = list(models.keys())
            print(f"\nACTUAL SCHEMA uses 'models' dict with {len(model_entries)} entries:")
            for name, data in models.items():
                print(f"  - {name}: {list(data.keys())}")
            
            # The actual schema has inconsistent structures per model
            # Some have 'status', some have 'unavailable', etc.
            pytest.fail(
                f"SCHEMA MISMATCH: File uses 'models' dict, not 'providers' dict. "
                f"Keys: {actual_keys}. This does not match expected schema."
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
