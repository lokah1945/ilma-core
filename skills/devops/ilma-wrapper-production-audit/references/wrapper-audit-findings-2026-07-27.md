# Wrapper Production Audit — Findings 2026-07-27

## Repo state
- HEAD `949ad72` (github/main), up-to-date. Runtime still `1ad8845` (stale — fixes `ddfc711`+`f8f3e1b` need restart to apply).

## CRITICAL findings
- **B2** Model-intelligence control plane DEAD: `MODEL_REGISTRY_URL` NOT set in `.env`/systemd → `MODEL_REGISTRY_CLIENT.enabled=False` (central_client.py:41-42) → all `schedule_observation`/`schedule_catalog` dropped client-side. Registry `/health` shows `providers_loaded:[]` because `central.registries` only populates on direct `/v1/models`/`/v1/resolve` calls the data-plane never makes.
- **B3** nvidia `model_registry.circuit_open=TRUE`, `consecutive_failures=80` → likely `MODEL_REGISTRY_URL` IS set in `nvidia-python/.env` but registry rejects (503, no `MODEL_REGISTRY_ADMIN_TOKEN` match on registry side). ACTION: check `nvidia-python/.env` — either set matching `MODEL_REGISTRY_ADMIN_TOKEN` on BOTH sides, or unset the URL.
- **B1** (cross-ref SDK audit) `_RESPONSE_STORE` unbounded in nous → OOM risk under agent load.

## Verified runtime (probe @ 05:10)
| Svc | /health | /v1/models | E2E |
|-----|---------|-----------|-----|
| nous:9102 | ok (1ad8845) | 22 | ✅ tencent/hy3:free → HELLO_TEST |
| nvidia:9101 | ok (circuit_open:TRUE) | 134 | ⚠ upstream keys exhausted (not wrapper bug) |
| opencode:9103 | ok | 9 | ⚠ upstream rate-limit (not wrapper bug) |
| blackbox:9104 | ok | 7 | n/a |
| model-registry:9200 | ok (providers_loaded:[]) | n/a | control plane dead (B2) |

## Recommendations (priority)
1. **P0 B1**: bound `_RESPONSE_STORE` in nous (mirror `_bounded_store`, cap ~200-500)
2. **P0 B2/B3**: wire `MODEL_REGISTRY_URL`+`MODEL_REGISTRY_ADMIN_TOKEN` consistently across all wrappers + registry, OR disable dead observation path + stop reporting false `circuit_open`
3. **P1 B5/B6**: developer→system mapping, repair tool-call orphans after truncation
4. **P2 B7**: nvidia empty-cache prefix-check fallback
5. Restart all 5 services after fixes to clear stale runtime + nvidia MR circuit

## Security posture (positive)
Header injection sanitized (`sanitize_header_value` strips CRLF), max_tokens capped 1M, secrets redacted (`sanitize_error_detail`), CORS localhost-only, auth gate on `/v1/*`, registry writes fail-closed without ADMIN_TOKEN, request size limiter (10MB).

## Bos convention
Reports → `/root/wrapper/audit_report/` (gitignored). Add `audit_report/` to `.gitignore` so it stays local-only.
