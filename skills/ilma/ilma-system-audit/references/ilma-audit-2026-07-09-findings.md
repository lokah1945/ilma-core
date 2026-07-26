# ILMA Audit Findings — 2026-07-09 (worked example)

Scope: 110 root modules + 302 scripts, 6 domains. Boot 10/10, runtime 37/37 OK pre-audit.
Method: direct terminal/read_file audit (subagent Wave hit 429 rate-limit, fell back to main-context).

## Findings & fixes

| # | Sev | File:Line | Bug | Fix | Verify |
|---|-----|-----------|-----|-----|--------|
| F1 | HIGH | ilma_model_router.py:722,725 | Duplicate `"is_free"` key — line 725 (`model_meta.get("is_free", False)`) overrides line 722 fallback chain (`intel`/`free_bypass`). Free models without `is_free` in model_meta misclassified PAID → blocked when `allow_paid=False` | Removed dup line 725; single key with `model_meta→intel→free_bypass` fallback | 330 free models resolved correctly post-patch |
| F2 | MED-HIGH | ilma_workflow_ecc.py:1840 | `from ilma_learning_memory import get_learning_memory` — module does NOT exist (0 files) → `except` silent skip → self-improvement loop DEAD every task | Reroute to `ilma_learning_engine.get_learning_engine().learn_from_task({...})` | ECC prints "✅ Learning recorded" (was "⚠️ Learn step skipped") |
| F3 | MED | ilma_integration_manifest.json:32,60 | Trailing commas after `}` / `]` → invalid JSON → `ilma_system_optimizer.py` crashes on `json.load` | `re.sub(r',(\s*[}\]])', r'\1', raw)` then `json.dump` clean (all trailing commas stripped) | `json.load` succeeds, 12 top keys |
| F4 | MED | scripts/ilma_two_way_sync.py:191 | Bare `except Exception: pass` in `_resolve_remote_from_sot` → SOT lookup failure masked, silent .env fallback | `except Exception as _e: logging.warning("[SOT] remote cred lookup failed...: {_e}")` | Warning logged on failure |
| F5 | MED | ilma_subagent_router.py (6 sites) | Bare `except Exception:` swallows errors | Replaced with `except Exception as _e: logger.debug(f"[SubAgentRouter] non-fatal swallow: {_e}")` | Syntax OK, logger defined L30 |
| F6 | MED | ilma_autonomous_loop_engine.py (15 sites) | Bare `except Exception:` swallows loop errors | Replaced with `except Exception as _e: logger.warning(f"[AutonomousLoop] swallowed: {_e}")` | Syntax OK |
| F7 | LOW | boot tier-autofix | 85 models tier mismatch auto-fixed each boot → 6.6s slowdown (cosmetic; record uses computed tier) | Accepted risk — no change | n/a |
| F8 | LOW | ilma_two_way_sync --reconcile never ran (`last_reconcile: null`) | Triggered reconcile → surfaced F10 | See F10 | n/a |
| F9 | LOW | SOUL.md:1036-1068 | Docs drift: 33 old cap names (search, fact_checking…) vs 37 registry taxa (web_search, research…) | Replaced with 37 caps by category; line 355 count → 37 | Registry `get_all()` = 37 |
| F10 | MED (NEW) | scripts/ilma_two_way_sync.py reconcile writes | Remote `rs0` enforces server-side `$jsonSchema`: `key_status` enum (MULTI_ACCOUNT_DEFAULT_VALID not in list) → `WriteError 121`; also `api_key` minLength 5 (masked `***`) and unique index `provider_1_account_email_1` (null) | Added `_sanitize_for_remote_validator()` + `_safe_replace_one/_safe_update_one/_safe_bulk_write()` that catch WriteError, sanitize, retry once | Validator rejection now logged + retried; 2 deeper remote-schema incompatibilities remain (Boss decision: update remote `$jsonSchema` or relax) |

## F10 residual (Boss decision, not force-fixed)
Remote `rs0@172.16.103.253` schema stricter than local SOT v3:
- `opencode` doc `account_email: null` → violates unique index `provider_1_account_email_1`
- `antigravity` `api_key: '***'` (masked) → violates `minLength: 5`
- `key_status: MULTI_ACCOUNT_DEFAULT_VALID` → not in legacy enum
Code is now tolerant; full reconcile needs remote validator update OR data relax. Do NOT modify remote without Bos approval.

## Commands used (repro)
```bash
cd /root/.hermes/profiles/ilma
python3 ilma.py --status
python3 ilma_runtime_wiring.py --verify
python3 ilma_orphan_wiring.py --verify
python3 -m py_compile ilma_*.py
python3 ilma_workflow_ecc.py --task "verify learning fix"   # watch [8/9] learn step
python3 scripts/ilma_two_way_sync.py --status
python3 scripts/ilma_two_way_sync.py --reconcile            # surfaces F10
git push origin HEAD                                        # branch is master, not main
```
