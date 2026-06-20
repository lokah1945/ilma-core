# ILMA NumPy/Matplotlib Incompatibility — Resolution Log

**Date:** 2026-06-03
**Session:** Gateway restart after optimization session
**Issue:** `ilma_chart_generator.py` causes wiring verification failure

## Root Cause

| Package | Version | Status |
|---------|---------|--------|
| NumPy | 2.4.4 | ❌ Compiled against NumPy 1.x C ABI |
| matplotlib | 3.6.3 (system) | ❌ Built against NumPy 1.x |

```
AttributeError: _ARRAY_API not found
ImportError: numpy.core.multiarray failed to import
```

**Traceback:**
```
ilma_chart_generator.py:21 → import matplotlib
matplotlib/__init__.py:113 → from . import _api, _version, cbook, _docstring, rcsetup
matplotlib/rcsetup.py:27 → from matplotlib.colors import Colormap, is_color_like
matplotlib/colors.py:56 → from matplotlib import _api, _cm, cbook, scale
matplotlib/scale.py:22 → from matplotlib.ticker import ...
matplotlib/ticker.py:138 → from matplotlib import transforms as mtransforms
matplotlib/transforms.py:49 → from matplotlib._path import ...
AttributeError: _ARRAY_API not found
```

## Fix Applied

```bash
pip3 install 'numpy<2' --break-system-packages
# numpy 2.4.4 → numpy 1.26.4
```

**Note:** `--break-system-packages` required because Debian 11+ uses PEP 668 externally-managed environment marker.

## Verification

```bash
# Before fix
python3 ilma_optimizer_daemon.py --verify
# Result: Wiring: 38/39 modules OK, 0 missing, 1 errors

# After fix
python3 ilma_optimizer_daemon.py --verify
# Result: Wiring: 39/39 modules OK, 0 missing, 0 errors
```

## Result

```
Health Score:   0.800
Pipeline E2E:   100.0%
Wired Modules:  39/39 (was 38/39)
Auto-wired:     4 new modules
Skills:         366
ILMA Core:      10/10 components loaded
Git:            ✅ Committed & pushed (commit 59c5a2f)
```

## Pattern: System Package vs pip Version Mismatch

ILMA runs on a Debian system where:
- `matplotlib 3.6.3` is installed as a system package (Debian apt)
- System matplotlib was compiled against NumPy 1.x
- NumPy was upgraded to 2.x via pip — creates ABI mismatch
- System-level Python packages compiled against old NumPy fail with `_ARRAY_API` error

**General rule:** When system packages use C extensions compiled against a specific NumPy ABI:
- Do NOT upgrade NumPy past 1.x if matplotlib is installed via apt
- Or rebuild matplotlib after any NumPy upgrade: `pip install --force-reinstall --no-cache-dir matplotlib`
- Or use a virtual environment to isolate ILMA's dependencies

## Related Pitfalls (from ilma-optimization-pattern)

- **NumPy 2.x incompatibility**: Any C-extension package (matplotlib, scipy, pandas, etc.) compiled against NumPy 1.x will crash on import when NumPy 2.x is loaded. Fix: downgrade to `numpy<2` or rebuild all C-extension packages.
- **System package manager vs pip conflict**: apt-installed packages may have different ABI expectations than pip-installed NumPy. Use `--break-system-packages` only when necessary and understand the risk.