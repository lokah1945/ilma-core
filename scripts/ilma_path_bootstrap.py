#!/usr/bin/env python3
"""
ILMA Path Bootstrap — Shared sys.path setup for all ILMA scripts.
Safe to import from any script. No side effects beyond sys.path setup.
Avoids duplicate entries.
"""
import os
import sys

def bootstrap():
    """Add ILMA profile root and scripts directory to sys.path if not already present."""
    profile_root = "/root/.hermes/profiles/ilma"
    scripts_dir = os.path.join(profile_root, "scripts")

    if profile_root not in sys.path:
        sys.path.insert(0, profile_root)

    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

    return profile_root, scripts_dir

# Auto-bootstrap on import
_bootstrap_root, _bootstrap_scripts = bootstrap()