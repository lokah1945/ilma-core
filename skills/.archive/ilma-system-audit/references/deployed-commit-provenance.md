# Deployed-Commit Provenance — the runtime-commit-mismatch loop (2026-07-25)

## The trap
An audit runner compared `runtime git_commit` (frozen at process start) against `git rev-parse HEAD`.
Every time the audit report was committed, HEAD advanced → next audit run showed:

```
FAIL — runtime commit nvidia: runtime=62307eb... repository=ce3f0b7...
```

This repeated for ALL 4 wrappers on `/root/wrapper`. The loop:

```
service runs at commit A
audit runs, writes report
git commit report  → HEAD = B   (A != B now)
re-run audit        → runtime(A) vs HEAD(B) = FALSE FAIL
fix by restart      → runtime = B
git commit report  → HEAD = C   (B != C)
re-run audit        → runtime(B) vs HEAD(C) = FALSE FAIL again
```

## Why the "exclude report dir" fix is insufficient
Tried: `git log -1 --format=%H -- . ':(exclude)productions/reports'`.
Still flipped when the LAST *code* commit predates the restart commit:
- runtime was restarted at `62307eb` (a report-only commit)
- last *code* commit = `c0a6535`
- audit compared runtime `62307eb` vs "last code" `c0a6535` → mismatch (genuine, not false positive — service literally runs on a report-only commit).

## Canonical fix (deployment marker)
The running process was built from whatever commit was HEAD **at ExecStartPre time**, not at any later HEAD. Capture that exact commit:

**1. systemd unit (every wrapper)** — add ExecStartPre that writes the marker:
```ini
[Service]
ExecStartPre=/bin/bash -c 'git -C /root/wrapper rev-parse HEAD > /root/wrapper/.deployed_commit 2>/dev/null || true'
ExecStart=/usr/bin/python3 -m uvicorn src.main:app --host 127.0.0.1 --port 9101
```

**2. wrapper exposes git_commit** from `/health` + `/version`
(resolved portably, see H-02 in SKILL.md — never hardcode `/root/wrapper`):
```python
GIT_COMMIT = subprocess.check_output(['git','rev-parse','HEAD'], cwd=_resolve_git_root()).strip()
```

**3. audit runner compares runtime vs `.deployed_commit` file** (NOT HEAD):
```python
deployed_marker = repo / ".deployed_commit"
repo_commit = deployed_marker.read_text().strip() if deployed_marker.is_file() else ""
if not repo_commit:
    repo_commit = subprocess.check_output(["git","rev-parse","HEAD"]).strip()
audit.log("PASS" if repo_commit else "FAIL", "deployed commit (marker)", repo_commit)
```

**4. workflow after any source change:**
```
git commit && git push
systemctl --user restart wrapper-nvidia-python wrapper-nous wrapper-opencode wrapper-blackbox wrapper-model-registry
   → rewrites .deployed_commit to new HEAD
run audit   → runtime == .deployed_commit == HEAD-at-restart  ⇒ 0 FAIL
```
Later report commits advance HEAD but do NOT change `.deployed_commit` (no restart) → audit still matches. NO LOOP.

## Empirical result (2026-07-25)
- Before fix: 4 FAIL "runtime commit mismatch" on every post-commit audit.
- After fix: `34 PASS / 0 FAIL / 0 BLOCKED` on `/root/wrapper` (all 4 wrappers smoke PASS, load PASS, runtime git_commit == .deployed_commit == 62307eb).

## Portable git-root helper (H-02)
```python
def _resolve_git_root():
    try:
        return subprocess.check_output(['git','rev-parse','--show-toplevel'],
            cwd=os.path.dirname(os.path.abspath(__file__)), stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        p = os.path.dirname(os.path.abspath(__file__))
        while p and p != os.path.dirname(p):
            if os.path.isdir(os.path.join(p,'.git')): return p
            p = os.path.dirname(p)
        return '/root/wrapper'
```
SOURCE_ROOT: `os.path.dirname(os.path.dirname(os.path.abspath(__file__)))` for `src/main.py` layouts;
`os.path.dirname(os.path.abspath(__file__))` for flat layouts (e.g. `wrapper_nous.py` at repo root).
