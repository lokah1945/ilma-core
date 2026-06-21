#!/usr/bin/env python3
"""
ilma_browser_runtime — Root import bridge.

Delegates to scripts/ilma_browser_runtime.py which is the canonical implementation.
This bridge exists so that `from ilma_browser_runtime import ...` works from the
profile root without sys.path manipulation.
"""
import importlib
import sys
from pathlib import Path

_scripts = str(Path(__file__).resolve().parent / "scripts")
if _scripts not in sys.path:
    sys.path.insert(0, _scripts)

# Remove self from sys.modules to avoid circular import
_self_name = __name__
_self_mod = sys.modules.pop(_self_name, None)

# Import canonical module from scripts/
_mod = importlib.import_module("ilma_browser_runtime")

# Re-export all public names
_public = [n for n in dir(_mod) if not n.startswith("_")]
for _name in _public:
    globals()[_name] = getattr(_mod, _name)

__all__ = _public

# Restore self module ref
sys.modules[_self_name] = _mod
