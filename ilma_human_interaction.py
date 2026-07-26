#!/usr/bin/env python3
"""
ilma_human_interaction — Root import bridge.

Delegates to scripts/ilma_human_interaction.py which is the canonical implementation.
"""
import importlib
import sys
from pathlib import Path

_scripts = str(Path(__file__).resolve().parent / "scripts")
if _scripts not in sys.path:
    sys.path.insert(0, _scripts)

_self_name = __name__
sys.modules.pop(_self_name, None)

_mod = importlib.import_module("ilma_human_interaction")

_public = [n for n in dir(_mod) if not n.startswith("_")]
for _name in _public:
    globals()[_name] = getattr(_mod, _name)

__all__ = _public
sys.modules[_self_name] = _mod
