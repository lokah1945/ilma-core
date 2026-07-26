# Hard Re-Audit Probe Recipe (independent, don't trust "100/100" self-claims)

Context: 2026-07-27 session. Bos asked "apakah code benar-benar production ready
enterprise-grade". Commits/docstrings claimed "true 100/100 enterprise" — but an
independent re-audit found 1 failing test + inconsistent security fix + unpinned
deps. The self-claim was false. This recipe is the durable probe kit.

## Output location (V-audit rule)
Write the audit report to `/root/audit_report/` — NOT `/root/wrapper/audit_report/`
(the latter pollutes the synced repo and would be committed/pushed).

## Step 1 — Run the repo test suite (the claim-killer)
```bash
cd /root/wrapper && python3 -m pytest -q 2>&1 | tail -20
```
Any `FAILED` line = the "100/100" claim is false. Treat a red test as a finding,
not as "the audit passed". In the 2026-07-27 run: `75 passed, 1 failed` —
`tests/test_central_client.py::test_disabled_client_does_not_enqueue_or_open_connections`
failed because `ModelRegistryClient("")` still resolves `enabled=True` via the
`MODEL_REGISTRY_URL` env fallback in `common/model/central_client.py:24`.

## Step 2 — Read the actual code, not the docstrings
Read `common/` modules (circuit_breaker, middleware, sanitize, model_state) and
each wrapper entry point. Look for:
- Duplicated helper functions that drift from the `common/` canonical copy.
  FOUND: `wrapper_nous.py:49-53` has a LOCAL `_sanitize_header_value` that strips
  only `\r`/`\n` — while `common/middleware.py:88-103` (SEC2 fix) also strips
  control chars `0x00-0x1f/0x7f`. The nous local copy is the weaker one.
- Unpinned dependencies: all 4 `requirements.txt` use `>=` with no upper bound
  (supply-chain drift risk). Enterprise needs `==` or hash-pinned `requirements.lock`.

## Step 3 — Live curl probes against running services
Auth token (local): `wrapper-local-key`. Ports: 9101 nvidia, 9102 nous,
9103 opencode, 9104 blackbox, 9200 model-registry.
```bash
AUTH="Authorization: Bearer wrapper-local-key"
echo -n "no-token chat -> "; curl -s -o /dev/null -w "%{http_code}\n" --max-time 8 \
  -X POST http://127.0.0.1:9102/v1/chat/completions -H "Content-Type: application/json" \
  -d '{"model":"tencent/hy3:free","messages":[{"role":"user","content":"hi"}]}'   # expect 401
echo -n "no-token /v1/models -> "; curl -s -o /dev/null -w "%{http_code}\n" --max-time 5 \
  http://127.0.0.1:9102/v1/models   # 200 = public catalog (acceptable, non-sensitive)
# oversized (13MB > 10MB MAX_REQUEST_BYTES) -> expect 413
python3 -c "import sys; sys.stdout.write('{\"model\":\"tencent/hy3:free\",\"messages\":[{\"role\":\"user\",\"content\":\"' + 'A'*13000000 + '\"}]}')" > /tmp/big.json
curl -s -o /dev/null -w "oversized -> %{http_code}\n" --max-time 10 -H "$AUTH" \
  -X POST http://127.0.0.1:9102/v1/chat/completions -H "Content-Type: application/json" --data @/tmp/big.json
# invalid model -> expect 400 (not 500/crash)
curl -s -o /dev/null -w "invalid-model -> %{http_code}\n" --max-time 8 -H "$AUTH" \
  -X POST http://127.0.0.1:9102/v1/chat/completions -H "Content-Type: application/json" \
  -d '{"model":"nonexistent/dead-model-xyz","messages":[{"role":"user","content":"hi"}]}'
```
Verified-good results from 2026-07-27: no-token chat→401, oversized→413,
invalid model→400, circuit breaker state machine (OPEN→HALF_OPEN) correct.

## Step 4 — Cross-check claims vs reality, write report
Scorecard dimensions: Correctness/Tests, Auth/ACL, Security(injection),
Resilience, Input validation, Observability, Dependency mgmt, Graceful shutdown,
Code hygiene. Give an honest numeric score (the 2026-07-27 run scored ~85/100,
not 100/100). State clearly: runtime is SAFE to keep in production even if the
"enterprise 100/100" claim is false — the gap is maturity/claim-accuracy, not
live danger.

## Re-check pitfalls for THIS class (add to skill body)
- F-1: a red pytest = claim is false; fix the test OR the `enabled` logic.
- F-2: delete duplicated local sanitizers in wrapper entry points; import from common.
- F-3: pin deps with hashes before claiming "enterprise".
- F-4: `/v1/models` public on 3/4 wrappers (nous/nvidia/blackbox) but 401 on
  opencode — either protect all or document "catalog public by design" uniformly.
- F-5: stale "100/100" docstrings/commits mislead operators; update after remediation.
