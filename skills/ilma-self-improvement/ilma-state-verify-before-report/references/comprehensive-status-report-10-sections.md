# Comprehensive System Status Report — 10-Section Pattern

**Verified:** 2026-06-20 (Telegram session, after `lima.py --status` style request).

When Bos asks for "system status secara lengkap dan komprehensif" / "laporan
status lengkap" / "show me everything that's running", use this exact 10-section
structure. Verified end-to-end — every claim in the report goes via a live tool,
NOT memory.

Bos mandate (USER PROFILE):
> "JANGAN asumsi model/config/state. Selalu verify via tool (grep, cat,
> read_file) sebelum claim apapun tentang state sistem."

This pattern is the realization of that mandate at the full-report scale.

---

## 10-Section Structure

| # | Section | Tool to verify |
|---|---|---|
| 1 | Hardware & OS | `uname -a`, `nproc`, `free -h`, `df -h /`, `du -sh /root/.hermes/profiles/<p>` |
| 2 | Active Model (verified) | `grep -E 'default:|provider:|base_url:' config.yaml` + live chat probe |
| 3 | MongoDB SOT | `pymongo.MongoClient(host=..., kwargs=...)` + `db.list_collection_names()` + counts |
| 4 | PROVIDER_INTELLIGENCE_MASTER.json | `json.load(...)`, nested `providers.*.models` count hook (see Recipe) |
| 5 | ILMA Core Runtime Wiring | `python3 ilma.py --status` + `ilma_runtime_wiring.py --verify` |
| 6 | Orphan Wiring | `ilma_orphan_wiring.py --verify` |
| 7 | SOT Runtime Audit | `python3 sot/sot_runtime_audit.py --audit` |
| 8 | Browser Runtime | `systemctl is-active`, `curl /json/version`, `ss -tlnp` |
| 9 | Cron Jobs | `cron/jobs.json` parsing |
| 10 | Script Inventory & Footprint | `ls scripts/ | wc -l`, `du -sh */` top-10 |

Then add two final sections: **Issues Catalog** (priority-sorted) and **HEALTH SNAPSHOT** (one-line green/yellow summary per subsystem).

---

## Recipe A — Active model + live probe

```bash
PROFILE=ilma
grep -nE '^\s*default:|^\s*provider:|^\s*base_url:' \
  /root/.hermes/profiles/$PROFILE/config.yaml | head -5
```

Then live-probe the wrapper:
```bash
DEFAULT=$(grep '^\s*default:' /root/.hermes/profiles/$PROFILE/config.yaml | awk '{print $2}')
curl -s http://127.0.0.1:9100/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer *** \
  -d "{\"model\":\"$DEFAULT\",\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}],\"max_tokens\":10}"
```

A response with non-empty `content` = live path. Empty / 500 = wrapper broken.

---

## Recipe B — MongoDB SOT counts

```python
from pymongo import MongoClient
import os
# pwd source: /root/.hermes/.env ILMA_MONGO_PASS — NOT profile .env
PWD = (os.environ.get('ILMA_MONGO_PASS') or
       next((l.split('=',1)[1].strip()
             for l in open('/root/.hermes/.env')
             if l.startswith('ILMA_MONGO_PASS=')), ''))
c = MongoClient(host='172.16.103.253', port=27017,
    username='quantumtraffic', password=PWD,
    authSource='admin', directConnection=True,
    serverSelectionTimeoutMS=3000)
db = c['credentials']
print('ping:', c.admin.command('ping'))
print('llm_providers:', db.llm_providers.count_documents({}))
print('models:', db.models.count_documents({}))
print('providers:', db.providers.count_documents({}))
print('sot_jobs:', db.sot_jobs.count_documents({}))
```

Common gotcha — see SKILL.md pitfalls **P-9** (MongoDB credentials from
`/root/.hermes/.env`) and **P-11** (memory's numbers vs live counts).

---

## Recipe C — Master.json counts (nested shape!)

```python
import json
d = json.load(open('ilma_model_router_data/PROVIDER_INTELLIGENCE_MASTER.json'))
provs = d.get('providers', {})

# CORRECT counting
total_models = sum(len(p.get('models', {})) for p in provs.values() if isinstance(p, dict))
total_providers = len(provs)
live_provs = [k for k, v in provs.items()
              if isinstance(v, dict) and v.get('status', '').lower() in ('active', 'live', 'synced')]
auth_ok = sum(1 for v in provs.values()
              if isinstance(v, dict) and v.get('auth_validated'))
total_keys = sum(v.get('api_key_count', 0) for v in provs.values() if isinstance(v, dict))

# build per-provider table
for k, v in provs.items():
    if not isinstance(v, dict): continue
    nc = v.get('api_key_count', 0)
    nm = len(v.get('models', {}))
    st = v.get('status', '?')
    av = '✓' if v.get('auth_validated') else '✗'
    print(f'  {av} {k:30s} status={st:8s} models={nm:5d} keys={nc}')
```

Pitfall: there is NO top-level `models` array. First instinct
`len(d.get('models', []))` returns 0 and misleads. Authoritative
count lives in `_enrichment_stats.total_models` (canonical) AND can
be recomputed via the nested sum above (source-of-truth).

---

## Recipe D — Live wiring verification

```bash
cd /root/.hermes/profiles/ilma
python3 ilma.py --status                  # 10/10 bootstrap + status summary
python3 ilma_runtime_wiring.py --verify   # 36/36 wired (or whatever layer count)
python3 ilma_orphan_wiring.py --verify    # 22/15 CLI tools wired
python3 sot/sot_runtime_audit.py --audit  # 12-check defect count
```

Each prints a `summary:` block — capture the line and surface verbatim.

---

## Recipe E — Browser CDP + LLM wrapper probe COMBO

```bash
systemctl --user is-active ilma-chrome@lokah2150.service
curl -s http://127.0.0.1:9222/json/version  # must return JSON with Browser field
ss -tlnp | grep -E ':9222|:9100'            # both ports must LISTEN
```

If you want to verify the wrapper really routes to the model — issue the chat
request from Recipe A.

---

## Recipe F — Cron jobs snapshot

```python
import json, os
p = '/root/.hermes/profiles/ilma/cron/jobs.json'
if os.path.exists(p):
    d = json.load(open(p))
    jobs = d if isinstance(d, list) else d.get('jobs', [])
    for j in jobs:
        print(f"  - {j.get('name', '?')[:40]:42s} schedule={j.get('schedule', '?'):15s} {'enabled' if j.get('enabled', True) else 'DISABLED'}")
```

Also look at system `crontab -l` for non-Hermes entries (e.g. legacy
`ilma_daily_optimizer.py run` at `0 5 * * *` overlapping with Hermes job
`2e8463c3e57f` at `0 9 * * *`).

---

## Report Conventions (learned from Sesi 2026-06-20)

1. **Emoji section headers**: 1️⃣ 2️⃣ … 🔟 + ⚠️ Issues + ✅ Health
2. **Tables over bullets** for any countable comparison.
3. **Bold the actionable numbers** (counts, sizes, ports).
4. **Memory vs Tool diff** — when memory says 25 and live says 22, surface
   it explicitly in section 3 (MongoDB) with a footnote explaining `memory
   lagi stale`.
5. **Closing `HEALTH SNAPSHOT`** uses a fixed checkmark-per-subsystem line:
   ```
   ILMA v3.x Phase 72   → BOOT OK ✅
   Active Model         → min.../MiniMax-M3 verified
   ...
   Overall: 🟡 OPERATIONAL with N needs-attention items
   ```
6. **Issues catalog** is a numbered table at the end: # | Issue | Severity | Fix.
7. **No fake numbers.** Every count must trace to a tool output. Re-use the
   `unverified` marker if you ever can't verify something.

---

## What NOT to do

❌ Answer "I think X is set" from session header alone.
❌ Recall MongoDB counts from memory; always re-probe.
❌ Trust MASTER.json's top-level `models` field — there isn't one; count
   via the nested map.
❌ Skip the per-provider breakdown in MASTER.json section — it surfaces
   `status=None` and `auth_validated=false` rows that the headline counts
   hide.
❌ Print only "system operational" without the per-subsystem snapshot —
   Bos wants the granular truth, not a green light.

---

## Sample output (excerpt from Sesi 2026-06-20)

```
✅ Verified runtime facts. Lanjut audit komponen ILMA core.
…
## 3️⃣ MongoDB SOT — Source of Truth (verified live)
172.16.103.253:27017 · auth quantumtraffic · authSource=admin · ping 0.3ms
| credentials.llm_providers  | 22 (semua is_active=True) |
| credentials.models         | 2039                    |
...
> Memory menyebut "25 llm_providers" — actual saat ini 22.
```

The closing memory-vs-tool call-out is the **highest-value pattern** — it
converts a silent stale-memory situation into an auditable evidence trail.
