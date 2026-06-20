#!/usr/bin/env python3
"""
DEPRECATED - Use scripts/ilma_browser_engine.py instead
=========================================================

This file is kept for backward compatibility only.
All new code should use ilma_browser_engine.SyncBrowserEngine.

Migration:
  OLD: from ilma_browser_automation import BrowserAutomation
  NEW: from ilma_browser_engine import SyncBrowserEngine

This file will be removed in future versions.
"""

import sys
import warnings
warnings.warn(
    "ilma_browser_automation.py is deprecated. "
    "Use scripts/ilma_browser_engine.py instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new engine for backward compatibility
sys.path.insert(0, '/root/.hermes/profiles/ilma/scripts')

# Try to import from new engine
try:
    from ilma_browser_engine import (
        SyncBrowserEngine,
        BrowserEngine,
        STEALTH_ARGS,
        USER_AGENTS,
        VIEWPORTS,
    )
except ImportError:
    # Fallback for standalone use
    pass