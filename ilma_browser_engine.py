#!/usr/bin/env python3
"""ILMA Browser Engine — Root-level shim for scripts/ilma_browser_engine.py"""

import sys as _sys
from pathlib import Path as _Path

# Lazy import cache
_cache = {}

def _get_cache(name, factory):
    if name not in _cache:
        _cache[name] = factory()
    return _cache[name]

def get_browser_engine(**kwargs):
    """Get singleton BrowserEngine instance."""
    return _get_cache('browser_engine', lambda: _import_be().BrowserEngine(**kwargs))

# Use importlib to avoid name collision
import importlib.util

def _import_be():
    """Import from scripts/ilma_browser_engine avoiding name collision."""
    if 'scripts_ilma_browser_engine' not in _cache:
        scripts_path = _Path(__file__).parent / "scripts"
        if str(scripts_path) not in _sys.path:
            _sys.path.insert(0, str(scripts_path))
        spec = importlib.util.spec_from_file_location(
            "scripts_ilma_browser_engine",
            scripts_path / "ilma_browser_engine.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _cache['scripts_ilma_browser_engine'] = mod
    return _cache['scripts_ilma_browser_engine']

def __getattr__(name):
    """Lazy load from scripts/ilma_browser_engine on demand."""
    if name == 'get_browser_engine':
        return get_browser_engine
    
    mod = _import_be()
    if hasattr(mod, name):
        return getattr(mod, name)
    
    raise AttributeError(f"module has no attribute '{name}'")

__all__ = ['get_browser_engine', 'BrowserFactory', 'BrowserEngine', 'SyncBrowserEngine', 
           'BrowserMode', 'BrowserBackend', 'CDPController', 'BrowserError',
           'StealthConfig', 'ActionType', 'activate_enforcement', 'get_enforcement_status']
