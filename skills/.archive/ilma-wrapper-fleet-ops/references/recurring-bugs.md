# Recurring Wrapper Bugs (knowledge bank)

Verified against `/root/wrapper` commit `4706765` (2026-07-28). These bugs
reappear after every `git pull` because they are in the upstream repo and get
re-applied on `reset --hard` / `git pull`. Fix by ADAPTING the healthy sibling
wrappers (nvidia-python, blackbox) — NOT by inventing new methods.

---

## BUG 1 — `Metrics.snapshot()` AttributeError (opencode + vercel)

**Symptom:** `/health` returns 500. Log:
```
File "wrapper_X/src/main.py", line 1251, in health
    ... "metrics": metrics.snapshot(), ...
AttributeError: 'Metrics' object has no attribute 'snapshot'
```

**Root cause:** `Metrics` class in `opencode/src/metrics.py` and
`vercel/metrics.py` only defines `async def summary(self, window="24h")`.
The `/health` endpoint calls `metrics.snapshot()`.

**Fix (match nvidia/blackbox pattern):** change the health endpoint to call
`await metrics.summary()` instead of `metrics.snapshot()`.

```diff
- "metrics": metrics.snapshot(),
+ "metrics": await metrics.summary(),
```

(Alternative if you must keep `snapshot()`: add a sync `snapshot()` method to
the `Metrics` class that returns the same dict shape as `summary()`.)

---

## BUG 2 — asyncio.Lock used with `with` (nous)

**Symptom:** nous fails to start, `/health` 500 or process exits. Log:
```
File "nous/wrapper_nous.py", line 588, in set_dynamic_alias_target
    with _dynamic_alias_lock:
TypeError: 'Lock' object does not support the context manager protocol
```

**Root cause:** `_dynamic_alias_lock = asyncio.Lock()` but `set_dynamic_alias_target`
is a SYNC function using `with` (sync context manager). `asyncio.Lock` needs
`async with`.

**Fix (match nvidia/blackbox — they use threading.Lock):** 
```diff
- _dynamic_alias_lock = asyncio.Lock()
+ _dynamic_alias_lock = threading.Lock()
```
(`import threading` already present in wrapper_nous.py.)

---

## BUG 3 — Vercel flat-layout bugs (vercel)

Vercel is `vercel/wrapper_vercel.py` (flat, no `src/` dir), unlike nvidia/blackbox
which are `X/src/main.py` (nested). Three bugs:

### 3a — Relative imports fail when run as a script
Log: `ModuleNotFoundError: No module named 'common'` OR
`ImportError: attempted relative import with no known parent package`
```diff
- from .key_pool import KeyPool
+ from key_pool import KeyPool
- from .metrics import Metrics
+ from metrics import Metrics
```

### 3b — Wrong uvicorn entrypoint
```diff
- uvicorn.run("src.main:app", host=BIND_HOST, port=LISTEN_PORT, ...)
+ uvicorn.run("wrapper_vercel:app", host=BIND_HOST, port=LISTEN_PORT, ...)
```

### 3c — Wrong repo-root detection
`Path(__file__).resolve().parents[2]` from `/root/wrapper/vercel/` = `/root`
(wrong). nvidia/blackbox need `parents[2]` because of the extra `src/` level.
Vercel needs `parents[1]` (`/root/wrapper`).
```python
# in the `except ImportError` block that bootstraps common/
_repo_root = Path(__file__).resolve().parents[1]
if not (_repo_root / "common" / "__init__.py").exists():
    _repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_repo_root))
```

---

## BUG 4 — New wrapper has no systemd unit

`wrappers.json` lists a new wrapper (e.g. vercel :9105) but `systemctl --user
cat wrapper-<name>.service` says NOT FOUND. Create the unit from the nous
template:

```
[Unit]
Description=wrapper-<name>: <Desc> (port 910X)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/root/wrapper/<name>
Environment=PYTHONPATH=/root/wrapper/<name>
EnvironmentFile=-/root/wrapper/<name>/.env
Environment=LOG_FILE=/root/wrapper/<name>/<name>.log
ExecStartPre=/bin/bash -c 'mkdir -p /root/wrapper/runtime && git -C /root/wrapper rev-parse HEAD > /root/wrapper/runtime/<name>.commit 2>/dev/null || true'
ExecStart=/usr/bin/python3 <entry>.py
Restart=always
RestartSec=3
StandardOutput=append:/root/wrapper/<name>/<name>.log
StandardError=append:/root/wrapper/<name>/<name>.log

[Install]
WantedBy=default.target
```
Then: `systemctl --user daemon-reload && systemctl --user enable wrapper-<name>.service && systemctl --user start wrapper-<name>.service`.

For vercel the `ExecStart` is `/usr/bin/python3 wrapper_vercel.py` (flat file,
not `uvicorn src.main:app`).
