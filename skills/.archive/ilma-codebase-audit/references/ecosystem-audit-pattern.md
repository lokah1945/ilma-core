# Ecosystem Audit Pattern — Multi-Component / Growing Systems

Condensed from the 2026-07-24 `/root/wrapper` audit (3 wrappers: nvidia-python :9101, nous :9106, opencode :9107).
Reusable for ANY audit of a sibling-component family that will keep growing.

## 1. Discovery sweep (enumerate ALL siblings, never fixate)
```bash
BASE=/root/wrapper
# All component entrypoints + service files
find $BASE -maxdepth 2 \( -name '*.service' -o -name 'main.py' -o -name 'wrapper_*.py' \) | grep -v __pycache__
# systemd units actually registered
systemctl --user list-units --type=service --no-legend | grep -iE 'wrapper'
# Health every running sibling
for p in 9101 9106 9107; do echo ":$p"; curl -s --max-time 5 http://127.0.0.1:$p/health | head -c 120; echo; done
```

## 2. Parity matrix — test the SAME surface on EVERY sibling
For each port, run (replace KEY per wrapper `.env`):
```bash
K=$(grep -oE 'BEARER_TOKEN=.+' $BASE/<wrapper>/.env|head -1|cut -d= -f2)
B=http://127.0.0.1:<port>
curl -s -o /dev/null -w "responses HTTP %{http_code}\n" $B/v1/responses -H "Authorization: Bearer $K" -d '{"model":"sonnet","input":"hi","stream":false}'
curl -s $B/v1/chat/completions -H "Authorization: Bearer $K" -d '{"model":"sonnet","messages":[{"role":"user","content":"ping"}]}' | head -c 100
curl -s $B/v1/messages -H "Authorization: Bearer $K" -H "anthropic-version: 2023-06-01" -d '{"model":"sonnet","max_tokens":20,"messages":[{"role":"user","content":"hi"}]}' | head -c 100
curl -s $B/v1/capabilities -H "Authorization: Bearer $K" | head -c 80   # may be "Unsupported"
curl -s -o /dev/null -w "badmodel HTTP %{http_code}\n" $B/v1/chat/completions -H "Authorization: Bearer $K" -d '{"model":"nope/xyz","messages":[{"role":"user","content":"hi"}]}'
```
Mark ✅/❌ per capability per component. **Inconsistencies are findings** (e.g. only nvidia had `/v1/capabilities`).

## 3. Per-component 7-category weighted score
| Cat | Weight | What it measures |
|-----|:------:|------------------|
| A. Code correctness / no runtime bug | 22% | crashes, 500s, typos (NameError), broken routes |
| B. SDK compatibility (Chat/Responses/Anthropic) | 24% | all 3 surfaces work E2E |
| C. Resilience / fallback / error handling | 14% | key pool, rate-limit, verify loop, load-shed |
| D. Observability / logging / metrics | 12% | log file present+written, journal, alert/loki wired |
| E. Deployment / service mgmt | 12% | systemd active, single identity, correct port |
| F. Security | 8% | auth enforced, CORS not `*`, bind host |
| G. Documentation accuracy | 8% | README claim vs reality |

**Component score** = Σ(weight×score). **Ecosystem score** = weighted avg of component scores.
Worked result 2026-07-24: nvidia 58, nous 82, opencode 85 → ecosystem **75/100**.

## 4. Scalability lens (flag BEFORE next component is added)
- **Duplication:** same `KeyPool` / alias engine / Responses translator copied N times → extract `wrapper-core`.
- **Structural divergence:** monolith (`wrapper_nous.py` 1236 lines) vs `src/` package → migrate to package.
- **Ops inconsistency:** systemd-active vs manually-run pid; log-to-file vs journal-only (journal dead → blind); bind `0.0.0.0` vs `127.0.0.1`.
- **Recommend:** shared core lib + `wrappers.json` manifest + a `wrapper-ctl` linter enforcing a contract
  (mandatory endpoints, log file, systemd-active, bind localhost, auth). New wrapper = thin adapter.

## 5. Output artifacts (write to /root/audit_report/, NOT inside project)
- `AUDIT_ECOSYSTEM.md` — state + parity matrix + scalability assessment.
- `AUDIT_<component>.md` — deep-dive per component.
- `<ECOSYSTEM_>ROADMAP.md` — P0 blocker fixes → P1 standardization → P2 scale-safe extraction; Definition of Done.

## 6. Read-only mode guardrails (Bos: "jangan edit, hanya scoring & reporting")
- Findings only from `read_file` + `terminal`(curl/grep) + `search_files`. No `write_file`/`patch` in project.
- Report `.md` go to a SEPARATE dir — that is reporting, allowed.
- Remove scratch files created in project (e.g. `_repro_*.py`) before finishing.
- Never restart services / edit `.env` / touch systemd during audit.
