# Security & Bug Sweep — 2026-07-19

## Scope
- 112 root `.py` files + 274 script files — syntax check (all pass)
- Secret leak scan: hardcoded API keys, GitHub tokens, AWS keys, MongoDB URIs, private keys, HTTP URLs with creds
- Bare `except:` audit (error-swallowing)
- `assert` in production code
- `subprocess.run` without timeout
- `open()` without context manager
- Division-by-zero risk
- Git tracking of backup files
- `.gitignore` completeness

## Secret leak findings — ZERO leaks
| Check | Result |
|-------|--------|
| `sk-*` (OpenAI-style keys) | None in any `.py` or script |
| `ghp_*`/`gho_*` (GitHub tokens) | None |
| `AKIA*` (AWS keys) | None |
| MongoDB URIs with embedded creds | None — SOT reads from env, not hardcoded |
| `-----BEGIN PRIVATE KEY-----` | None (only in `ilma_git_guard.py` regex pattern) |
| HTTP URLs with `user:pass@` | None |
| `.env` file permissions | 600 root:root ✅ |
| `auth.json` | Stores SHA-256 fingerprints, not raw secrets ✅ |
| `config.yaml` `api_key` | `wrapper-local-key` (localhost internal, not cloud) ✅ |
| Log files | Tokens truncated `[:40]...` ✅ |

## Bug fixes applied (9 files, commit d283e3f)

### 1. Bare `except:` → specific exceptions (6 files)
| File | Line | Old | New |
|------|------|-----|-----|
| `ilma_capability_drift_detector.py` | 31 | `except: pass` | `except (json.JSONDecodeError, KeyError, TypeError): pass` |
| `ilma_capability_improvement_miner.py` | 27 | `except: pass` | `except (json.JSONDecodeError, KeyError, TypeError): pass` |
| `ilma_hermes_skills_router.py` | 581 | `except: pass` | `except (json.JSONDecodeError, KeyError, TypeError, OSError): pass` |
| `ilma_hermes_skills_router.py` | 614 | `except: pass` | `except (OSError, TypeError): pass` |
| `ilma_optimize_db.py` | 48 | `except: return {}` | `except (json.JSONDecodeError, OSError): return {}` |
| `ilma_production_monitor.py` | 29,43 | `except: pass` | `except (json.JSONDecodeError, KeyError, TypeError): pass` |
| `ilma_optimizer_daemon.py` | 778 | `except:` | `except (OSError, ValueError):` |

**Why:** Bare `except:` catches `KeyboardInterrupt`, `SystemExit`, and `GeneratorExit` — silently swallowing real errors and making debugging impossible. Specific exceptions let unexpected errors propagate.

### 2. `assert` → `raise ValueError` (1 file)
| File | Line | Old | New |
|------|------|-----|-----|
| `ilma_client.py` | 724 | `assert fb is not None or model_override, "fb must be set..."` | `if fb is None and not model_override: raise ValueError("fb must be set...")` |

**Why:** `python -O` strips all `assert` statements. If the codebase is ever run optimized, the invariant vanishes and `None` reaches the HTTP layer.

### 3. `subprocess.run` missing timeout (1 file)
| File | Line | Fix |
|------|------|-----|
| `ilma_autonomous_loop_engine.py` | 309 | Added `timeout=10` to `subprocess.run(["grep", ...])` |

**Why:** Without timeout, a deadlocked child process hangs the daemon indefinitely. 9/10 calls in this file already had timeout; this one was missed.

### 4. `open()` without context manager (1 file)
| File | Line | Old | New |
|------|------|-----|-----|
| `ilma_hermes_skills_router.py` | 765 | `content = open(path).read()` | `with open(path) as f: content = f.read()` |

**Why:** File descriptor leak. On long-running daemons, this exhausts the fd limit.

### 5. Division-by-zero guard (1 file)
| File | Line | Fix |
|------|------|-----|
| `ilma_confidence_router.py` | 251 | `total / len(self.routing_history)` → `total / len(self.routing_history) if self.routing_history else 0.0` |

**Why:** On first run or cleared state, `routing_history` is empty → `ZeroDivisionError`.

### 6. Git tracking cleanup
- `ilma_model_router_data/PROVIDER_INTELLIGENCE_MASTER.json.bak.1784330527` (4.8MB) was tracked in git
- Added `.gitignore` patterns: `ilma_model_router_data/*.bak*`, `ilma_model_router_data/*.backup*`
- `git rm --cached` to untrack

## Grep recipes for future audits

```bash
# Bare except (error-swallowing)
grep -rn "except:" *.py scripts/*.py | grep -v "test"

# Assert in production code (stripped by python -O)
grep -rn "^\s*assert " *.py | grep -v "test\|__main__\|_test"

# subprocess.run without timeout (hang risk)
grep -rn "subprocess\.\(run\|call\|Popen\|check_output\)" *.py scripts/*.py | grep -v "timeout"

# open() without context manager (fd leak)
grep -rn "= open(" *.py | grep -v "with\|test\|__main__"

# Division-by-zero on collections
grep -rnE "/ (total|count|n|len\()" *.py | grep -v "max\|min\|if\|//"

# Hardcoded secrets
grep -rnE "sk-[a-zA-Z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{36}|AKIA[0-9A-Z]{16}" *.py scripts/*.py

# MongoDB/HTTP URIs with embedded credentials
grep -rnE "mongodb(\+srv)?://[^:]+:[^@]+@|https?://[^:]+:[^@]+@" *.py scripts/*.py

# Backup files tracked in git
git ls-files | grep -E "\.bak|\.backup|\.old"
```

## Verification
- All 9 patched files: `python3 -m py_compile` ✅
- Full re-check: 112 root + 274 scripts all compile clean ✅
- Commit: `d283e3f` pushed to `ilma-core.git`
