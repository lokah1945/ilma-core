# Deployment Commit Markers — race-safe pattern (H-04)

## Problem
A single global `/root/wrapper/.deployed_commit` written by every service's
`ExecStartPre` is a RACE: service B restarting overwrites the marker while
service A still runs old code, and the audit compares all runtimes against one
global value. Wrong.

## Fix: per-service marker
Each systemd unit writes its OWN marker file at `ExecStartPre` time:

```ini
# in <svc>/systemd/wrapper-<svc>.service
Environment=LOG_FILE=/root/wrapper/<svc>/<svc>.log
ExecStartPre=/bin/bash -c 'mkdir -p /root/wrapper/runtime && git -C /root/wrapper rev-parse HEAD > /root/wrapper/runtime/<svc>.commit 2>/dev/null || true'
ExecStart=/usr/bin/python3 ...
```

Marker files produced:
```
/root/wrapper/runtime/nvidia-python.commit
/root/wrapper/runtime/nous.commit
/root/wrapper/runtime/opencode.commit
/root/wrapper/runtime/blackbox.commit
/root/wrapper/runtime/model-registry.commit
```

## Audit comparison (the correct logic)
```python
svc_map = {
    "model-registry": "model-registry",
    "nvidia": "nvidia-python",   # <-- the trap: loop key != marker filename
    "nous": "nous",
    "opencode": "opencode",
    "blackbox": "blackbox",
}
for name, port in [("model-registry",9200),("nvidia",9101),("nous",9102),
                   ("opencode",9103),("blackbox",9104)]:
    svc = svc_map[name]
    marker = repo / "runtime" / f"{svc}.commit"
    repo_commit = marker.read_text().strip() if marker.is_file() else ""
    # compare against /health git_commit, NOT git rev-parse HEAD
    runtime_commit = json.loads(curl(f"http://127.0.0.1:{port}/health"))["git_commit"]
    # compare [:12] on BOTH sides if either is truncated
    if runtime_commit[:12] != repo_commit[:12]:
        audit.log("FAIL", f"runtime commit {name}", ...)
```

**Why not HEAD?** Committing the audit report moves `git rev-parse HEAD`, but the
running process was built from the commit at its last restart. Comparing to HEAD
yields a false FAIL after every commit. The marker = "what this process was
deployed from" = correct provenance.

**Truncation rule:** keep `git_commit` full (40-char) in `/health`, OR truncate
both marker and runtime to 12 in the compare. Mixing (12 vs 40) = false FAIL.
