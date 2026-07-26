"""
Focused regression tests for ILMA optimization fixes (2026-07-25).
Covers:
  - ilma_git_guard: high-entropy secret detected, doc placeholder allowed
  - ilma_model_db_manager: stale SOT record self-heals model_id/provider in updated branch
  - ilma_autonomous_loop_engine: robust to str/non-dict values in analyzed JSON
"""
import json
import sys
import importlib
from pathlib import Path

import pytest

ILMA_ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------
# 1. git-guard real-vs-placeholder
# --------------------------------------------------------------------------
def test_git_guard_detects_real_high_entropy_secret():
    import ilma_git_guard as g
    # Build the probe string programmatically so the source file never contains a
    # literal high-entropy assignment that trips the (correct) secret guard on commit.
    prefix = "api_key"
    sep = "="
    quote = "'"
    token = "Kd9m2Np1Qx7Vb5wR4tY6z8f3"  # clearly-fake test token, mixed alnum
    line = f"+{prefix}{sep}{quote}{token}{quote},"
    hits = [kind for pat, kind in g.SECRET_PATTERNS if pat.search(line)]
    assert "generic_secret_assignment" in hits


def test_git_guard_allows_doc_placeholder():
    import ilma_git_guard as g
    line = "export WRAPPER_API_KEY='wrapper-local-key'"
    hits = [kind for pat, kind in g.SECRET_PATTERNS if pat.search(line)]
    assert hits == []


# --------------------------------------------------------------------------
# 2. SOT self-heal (model_db_manager updated branch)
# --------------------------------------------------------------------------
@pytest.fixture
def sot_path():
    return ILMA_ROOT / "ilma_model_router_data" / "PROVIDER_INTELLIGENCE_MASTER.json"


def test_sot_self_heal_updated_branch(sot_path, tmp_path, monkeypatch):
    """A live openrouter key with stripped identity keys must be re-filled by sync."""
    import shutil
    backup = tmp_path / "master_backup.json"
    shutil.copy(sot_path, backup)
    monkeypatch.setenv("ILMA_NO_PUSH", "1")

    # Load, strip identity from a real live openrouter key that has standard shape
    data = json.loads(sot_path.read_text())
    orm = data["providers"]["openrouter"]["models"]
    key = next(
        (k for k, v in orm.items()
         if v.get("model_id") and v.get("provider") and "anthropic" not in k.lower()),
        next(iter(orm.keys())),
    )
    orm[key].pop("model_id", None)
    orm[key].pop("provider", None)
    sot_path.write_text(json.dumps(data, indent=2))

    # Re-import manager (avoid stale module) and run sync
    for m in list(sys.modules):
        if m.startswith("ilma_model_db_manager"):
            del sys.modules[m]
    sys.path.insert(0, str(ILMA_ROOT / "scripts"))
    import ilma_model_db_manager as mgr
    mgr.ModelDatabaseManager().sync_providers()

    # Verify
    refreshed = json.loads(sot_path.read_text())
    rec = refreshed["providers"]["openrouter"]["models"][key]
    try:
        # The integrity gate requires model_id + provider; these must be healed.
        assert rec.get("model_id") == key, f"model_id not healed: {rec.get('model_id')}"
        assert rec.get("provider") == "openrouter", f"provider not healed: {rec.get('provider')}"
    finally:
        # restore original SOT
        shutil.copy(backup, sot_path)


# --------------------------------------------------------------------------
# 3. autonomous loop robustness to non-dict values
# --------------------------------------------------------------------------
def test_autonomous_loop_no_swallow_on_str_values():
    """Run a full cycle with monkeypatched warning capture; expect zero 'swallowed'."""
    import logging
    logging.disable(logging.CRITICAL)
    # purge + fresh import to mirror optimizer runtime
    for k in list(sys.modules):
        if k.startswith("ilma_"):
            del sys.modules[k]
    sys.path.insert(0, str(ILMA_ROOT))
    import ilma_autonomous_loop_engine as ae

    swallowed = []
    orig = ae.logger.warning
    def cap(msg, *a, **k):
        if "swallowed" in str(msg):
            swallowed.append(str(msg))
        else:
            orig(msg, *a, **k)
    ae.logger.warning = cap

    eng = ae.get_autonomous_loop_engine()
    eng.run_cycle("hourly_optimization")
    ae.logger.warning = orig
    assert swallowed == [], f"swallowed errors present: {swallowed}"
