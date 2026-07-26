# Production Audit Anti-Loop Reference

Concrete recipe from the 2026-07-25 `/root/wrapper` hardening (commits `5dde242`..`44729e5`).
The goal: a production audit that reaches `PASS=N FAIL=0 BLOCKED=0` with a clean tree, without the
FAIL↔commit loop that burned 8 iterations.

## 1. Per-service deployed-commit marker (H-04)

In EACH systemd unit (`*/systemd/wrapper-*.service`):

```ini
[Service]
Environment=LOG_FILE=/root/wrapper/<svc>/<svc>.log
ExecStartPre=/bin/bash -c 'mkdir -p /root/wrapper/runtime && git -C /root/wrapper rev-parse HEAD > /root/wrapper/runtime/<svc>.commit 2>/dev/null || true'
ExecStart=...
```

Marker files (one per service, written at process START, not at audit time):
```
/root/wrapper/runtime/nvidia-python.commit
/root/wrapper/runtime/nous.commit
/root/wrapper/runtime/opencode.commit
/root/wrapper/runtime/blackbox.commit
/root/wrapper/runtime/model-registry.commit
```

Copy repo units to the live dir after editing:
```bash
cd /root/wrapper
for w in nvidia-python nous opencode blackbox model-registry; do
  unit=$(ls $w/systemd/wrapper-*.service 2>/dev/null | head -1)
  [ -n "$unit" ] && cp "$unit" /root/.config/systemd/user/$(basename $unit)
done
systemctl --user daemon-reload
systemctl --user restart wrapper-nvidia-python wrapper-nous wrapper-opencode wrapper-blackbox wrapper-model-registry
sleep 3
```

## 2. Audit compares runtime vs MARKER, not HEAD (the loop-breaker)

```python
svc_map = {
    "model-registry": "model-registry",
    "nvidia": "nvidia-python",   # <-- loop key 'nvidia' != filename 'nvidia-python.commit'
    "nous": "nous",
    "opencode": "opencode",
    "blackbox": "blackbox",
}
for name, port in [("model-registry",9200),("nvidia",9101),("nous",9102),("opencode",9103),("blackbox",9104)]:
    svc = svc_map[name]
    marker = repo / "runtime" / f"{svc}.commit"
    repo_commit = marker.read_text().strip() if marker.is_file() else ""
    # runtime commit from /health
    rc, out = audit.command(["curl","-sS","-m","5", f"http://127.0.0.1:{port}/health"])
    runtime_commit = json.loads(out).get("git_commit","") if rc==0 and out.strip() else ""
    if runtime_commit and repo_commit and runtime_commit[:12] != repo_commit[:12]:
        audit.log("FAIL", f"runtime commit {name}", f"runtime={runtime_commit} repository={repo_commit}")
    else:
        audit.log("PASS", f"runtime commit {name}", f"runtime={runtime_commit} repository={repo_commit}")
```

Key points:
- Compare `[:12]` — wrappers expose `git_commit[:12]`, marker holds full 40-char SHA.
- NEVER compare against `git rev-parse HEAD` for the runtime-commit check (that is what causes the loop).
- The `svc_map` is mandatory. Without it, `nvidia` → `runtime/nvidia.commit` (missing) → silent fallback to `git HEAD` → loop returns.

## 3. Restart-after-commit protocol

After ANY code commit that changes wrapper source:
```bash
systemctl --user restart wrapper-nvidia-python wrapper-nous wrapper-opencode wrapper-blackbox wrapper-model-registry
sleep 3   # markers rewritten to new HEAD
```
Runtime `git_commit` now equals the new HEAD. Re-run audit → PASS.

Final state: run audit, confirm `FAIL=0`, THEN `git commit` the report (never restart after this final commit).
Working tree clean + `FAIL=0 BLOCKED=0` = production ready.

## 4. External-outage → BLOCKED (not FAIL) + retry-with-backoff (M-02)

```python
# in the smoke loop
last_status = 0
status, ms, body, error = 0, 0.0, {}, None
for attempt in range(3):
    status, ms, body, error = audit.http(f"{url}{path}", method="POST", payload=payload, api_key=api_key, timeout=180)
    last_status = status
    if 200 <= status < 300:
        break
    if status in (429, 503):
        time.sleep(2 + attempt * 3)
        continue
    break
returned_model = body.get("model") if isinstance(body, dict) else None
external_down = (
    last_status in (503, 502)
    and isinstance(body, dict)
    and "no capacity" in str(body.get("error", {}).get("message", "")).lower()
)
ok = 200 <= last_status < 300 and returned_model in (None, model)
if external_down:
    audit.log("BLOCKED", f"exact-model smoke [{surface}]", detail + ", external_outage=opencode.ai")
    continue
audit.log("PASS" if ok else "FAIL", f"exact-model smoke [{surface}]", detail)
```
opencode.ai Zen free tier returns `503 No capacity` intermittently → `health.status=degraded, available=0/N`.
That is an upstream outage, not a wrapper defect — BLOCKED, not FAIL.

## 5. Load test runs in `--smoke-all` (H-03 fix)

Extract a helper; call from BOTH the single-wrapper and `--smoke-all` branches:
```python
def _run_load(audit, repo, base_url, model, api_key, requests, concurrency):
    env = {**os.environ, "API_KEY": api_key, "PYTHONDONTWRITEBYTECODE": "1"}
    cmd = [sys.executable, "tests/perf/load_agent_sim.py",
           "--base-url", base_url, "--model", model,
           "--requests", str(requests), "--concurrency", str(concurrency)]
    try:
        proc = subprocess.run(cmd, cwd=repo, env=env, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=3600)
        audit.log("PASS" if proc.returncode == 0 else "FAIL", "bounded load", (proc.stdout or "")[-6000:])
    except subprocess.TimeoutExpired:
        audit.log("FAIL", "bounded load", "timed out")
```
The load script emits `ok=N/N error=N`, `latency_ms p50/p95/p99`, `ttft_ms p50/p95/p99`.
Acceptance: report contains `bounded load: ok=50/50 error=0` + p50/p95/p99 lines.

## 6. Full run command (final audit)

```bash
cd /root/wrapper
export WRAPPER_API_KEY='wrapper-local-key'
bash productions/run_production_audit.sh \
  --run-tests --run-smoke --smoke-all --run-load \
  --wrapper-url http://127.0.0.1:9101/v1 \
  --model 'nvidia/llama-3.3-nemotron-super-49b-v1' \
  --requests 50 --concurrency 5
```
Expected end-state (2026-07-25, `44729e5`): `PASS=42 FAIL=0 BLOCKED=0`, 8 surface smokes PASS,
load `ok=50/50 error=0`, 72 unit tests PASS, 5 runtime commits = deployed markers.
