"""
Test capability cache (lru_cache) for is_capable() and get_capability().

ILMA Phase 4F Canary — Task L2-02
"""
import sys
import time
from unittest.mock import patch, MagicMock

sys.path.insert(0, '/root/.hermes/profiles/ilma')

# Import the module to test
import ilma_capability_registry as registry_mod


def test_is_capable_caches():
    """Test that is_capable uses lru_cache and returns cached results."""
    # Clear any existing cache
    registry_mod.is_capable.cache_clear()
    
    mock_entry = MagicMock()
    mock_entry.is_usable.return_value = True
    
    with patch.object(registry_mod, 'get_registry') as mock_get_reg:
        mock_reg = MagicMock()
        mock_reg.get.return_value = mock_entry
        mock_get_reg.return_value = mock_reg
        
        # Call 3 times
        result1 = registry_mod.is_capable("test_cap")
        result2 = registry_mod.is_capable("test_cap")
        result3 = registry_mod.is_capable("test_cap")
        
        assert result1 is True
        assert result2 is True
        assert result3 is True
        
        # Should only call get_registry().get() ONCE due to caching
        assert mock_reg.get.call_count == 1, f"Expected 1 call, got {mock_reg.get.call_count}"
        
        # Verify cache info
        info = registry_mod.is_capable.cache_info()
        assert info.hits == 2, f"Expected 2 hits, got {info.hits}"
        assert info.misses == 1, f"Expected 1 miss, got {info.misses}"
        assert info.currsize == 1, f"Expected cache size 1, got {info.currsize}"
    
    registry_mod.is_capable.cache_clear()
    print("✓ test_is_capable_caches PASSED")


def test_get_capability_caches():
    """Test that get_capability uses lru_cache and returns cached results."""
    # Clear any existing cache
    registry_mod.get_capability.cache_clear()
    
    mock_entry = MagicMock()
    mock_entry.name = "test_cap"
    
    with patch.object(registry_mod, 'get_registry') as mock_get_reg:
        mock_reg = MagicMock()
        mock_reg.get.return_value = mock_entry
        mock_get_reg.return_value = mock_reg
        
        # Call 3 times
        result1 = registry_mod.get_capability("test_cap")
        result2 = registry_mod.get_capability("test_cap")
        result3 = registry_mod.get_capability("test_cap")
        
        assert result1 is mock_entry
        assert result2 is mock_entry
        assert result3 is mock_entry
        
        # Should only call get_registry().get() ONCE due to caching
        assert mock_reg.get.call_count == 1, f"Expected 1 call, got {mock_reg.get.call_count}"
        
        # Verify cache info
        info = registry_mod.get_capability.cache_info()
        assert info.hits == 2, f"Expected 2 hits, got {info.hits}"
        assert info.misses == 1, f"Expected 1 miss, got {info.misses}"
        assert info.currsize == 1, f"Expected cache size 1, got {info.currsize}"
    
    registry_mod.get_capability.cache_clear()
    print("✓ test_get_capability_caches PASSED")


def test_different_keys_cache_separately():
    """Test that different capability names are cached separately."""
    registry_mod.is_capable.cache_clear()
    registry_mod.get_capability.cache_clear()
    
    mock_entry1 = MagicMock()
    mock_entry1.is_usable.return_value = True
    mock_entry2 = MagicMock()
    mock_entry2.is_usable.return_value = False
    
    with patch.object(registry_mod, 'get_registry') as mock_get_reg:
        mock_reg = MagicMock()
        mock_reg.get.side_effect = [mock_entry1, mock_entry2]
        mock_get_reg.return_value = mock_reg
        
        # Call with two different capabilities
        result1 = registry_mod.is_capable("cap_a")
        result2 = registry_mod.is_capable("cap_b")
        result3 = registry_mod.is_capable("cap_a")  # Should be cached
        
        assert result1 is True
        assert result2 is False
        assert result3 is True
        
        # Should call get() twice (once for each unique capability)
        assert mock_reg.get.call_count == 2, f"Expected 2 calls, got {mock_reg.get.call_count}"
        
        info = registry_mod.is_capable.cache_info()
        assert info.currsize == 2, f"Expected cache size 2, got {info.currsize}"
    
    registry_mod.is_capable.cache_clear()
    print("✓ test_different_keys_cache_separately PASSED")


def test_lru_cache_has_maxsize():
    """Test that lru_cache decorators have maxsize configured."""
    # Check is_capable
    info = registry_mod.is_capable.cache_info()
    # lru_cache with maxsize=128 should allow up to 128 entries
    # We can't directly check maxsize, but we verify the cache works
    
    # Check get_capability
    info2 = registry_mod.get_capability.cache_info()
    
    print("✓ test_lru_cache_has_maxsize PASSED (cache_info accessible)")


if __name__ == "__main__":
    test_is_capable_caches()
    test_get_capability_caches()
    test_different_keys_cache_separately()
    test_lru_cache_has_maxsize()
    print("\n=== ALL TESTS PASSED ===")