#!/usr/bin/env python3
"""ILMA Adversarial QA — Root-level shim for hermes_profile_ilma/ilma_adversarial_qa.py"""

import sys as _sys
from pathlib import Path as _Path

_hermes_path = _Path(__file__).parent / "hermes_profile_ilma"
if str(_hermes_path) not in _sys.path:
    _sys.path.insert(0, str(_hermes_path))

# Lazy loading pattern — use importlib to avoid circular reference
_imported = {}

def _lazy_import(name):
    if name not in _imported:
        import importlib
        _src = importlib.import_module(f'hermes_profile_ilma.ilma_adversarial_qa')
        _imported[name] = getattr(_src, name)
    return _imported[name]

# === SINGLETON ACCESSOR ===
_global_aqa_instance = None

def get_adversarial_qa():
    """Get singleton AdversarialQAEngine instance."""
    global _global_aqa_instance
    if _global_aqa_instance is None:
        _global_aqa_instance = _lazy_import('AdversarialQAEngine')()
    return _global_aqa_instance

def __getattr__(name):
    if name in ('AdversarialQAEngine', 'AdversarialQuestion', 'QAResult'):
        return _lazy_import(name)
    raise AttributeError(f"module has no attribute '{name}'")
