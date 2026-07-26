# Memory Audit Examples 2026-06-20

Audit transkrip end-to-end yang almost over-claim-ed oleh saya. Berisi:
- Real conversation fragments
- The traps I almost fell into
- Corrected output format
- Memory state before/after

## Incident 1: Cross-Profile Over-Claim (Most Important Recurring Pattern)

### Setup

- ILMA profile uses `provider=wrapper-nvidia` (port 9100, upstream NVIDIA NIM at `integrate.api.nvidia.com/v1`).
- Master-chief profile uses `provider=minimax` (base_url `https://api.minimax.io/anthropic`).
- Memory M2-S2 (initial version) said "BRIDGE PROJECT FULLY REMOVED 2026-06-19".

### Wrong Conclusion Drafted

> "Provider: minimax in master-chief profile is also stale (just like ILMA migrated away). The credentials for `provider: minimax` in `master-chief/config.yaml` should be cleaned up."

### Why This Is Wrong

Master-chief profile is a separate runtime. Its `provider: minimax` config is **valid for its own use case** — master-chief uses MiniMax-native Claude-compatible API at `api.minimax.io/anthropic`. That endpoint actually exists and works.

This is NOT ILMA inheriting or sharing config. This is two distinct profiles with distinct valid configurations.

### Correct Approach (What I Should Have Done First)

1. Identify which profile is active (= ILMA, confirmed via header)
2. Verify ILMA's runtime (model served, port, PID, base_url) — that's what audit is about
3. For each OTHER profile, check its own use case independently
4. Build per-profile matrix: Profile × {Provider, Base URL, Active, Runtime Evidence, Status}
5. If two profiles use DIFFERENT providers → that's expected, not an issue
6. Only flag genuine conflicts (one profile says provider X, but HIS OWN runtime can't reach it)

### Rule Output

> "ILMA uses provider=wrapper-nvidia (NVIDIA NIM upstream). Master-chief uses provider=minimax (api.minimax.io). These are different profiles with different valid configurations. No conflict. Status: VALID for both."

---

## Incident 2: Local-Service Blind Probe (Self-Protocol Violation)

### Setup

- Memory M2-S2 said "MongoDB LIVE" but I needed to verify.
- First instinctive probe: `curl localhost:27017` → connection refused.
- **Wrong conclusion drafted:** "MongoDB is dead."

### Why This Is Wrong

MongoDB at `172.16.103.253:27017` (NOT localhost). The local probe only checks `127.0.0.1:27017`. The remote subnetwork host runs the actual MongoDB.

### Correct Approach

1. **Grep config first** for `mongo`, `MONGO`, `MONGO_HOST`:
   ```bash
   grep -rE "MONGO_HOST" /root/.hermes/profiles/*/config* /root/.hermes/profiles/*/sot/**/*.py 2>/dev/null
   ```
2. Found: provider_sync.py uses `MONGO_HOST = "172.16.103.253"`.
3. Probe that host: `python3 -c "from pymongo import MongoClient; c=MongoClient(host='172.16.103.253', port=27017, serverSelectionTimeoutMS=5000); print(c.admin.command('ping'))"`
4. Returns: `{'ok': 1.0, ...}` — alive.

### Rule Output

> "MongoDB at `172.16.103.253:27017` is alive. Local probe `127.0.0.1:27017` did not respond but that's because MongoDB lives on a remote host, not local. Status: VALID."

### Why I Almost Got This Wrong (Self-Audit)

I jumped from one probe to a global "dead" verdict. This is **the local-probe cousin** of cross-profile over-claim: both involve jumping to a broader conclusion based on a narrow sample. The fix discipline is the same: enumerate the actual scope before generalizing.

---

## Incident 3: Stale Commit Hash in Memory

### Setup

- Memory M4-S1 said: "Phase D 2026-06-17 commit `d8b4351`".
- I tried `git show d8b4351` to verify the metadata I wanted to reference.
- Got back: `fatal: bad revision`.

### Wrong Conclusion Drafted

> "Either git is corrupted, or the commit was force-pushed away. The memory entry is broken."

### Why This Is Wrong

The commit `d8b4351` simply does not exist in this repo at all. The real Phase D commit is `7a0bd5f` (made 2026-06-17 13:53:28 by AYDA Bot).

### Correct Approach

```bash
git log --all --oneline | grep d8b4351   # → empty
git log --all --oneline --since='2026-06-15' --until='2026-06-20'  # → finds 7a0bd5f
git show 7a0bd5f --stat | head -20   # → confirms "Phase D REWORK: 5 fixes per auditor verdict"
```

### Rule Output

> "Memory M4-S1 claimed commit `d8b4351`. Actual git history has no such commit. Status: CONTRADICTED. Replacement: `7a0bd5f` (Phase D REWORK, 5 items)."

---

## Incident 4: Cron Drift Pattern

### Setup

- Memory SOT entry says cron `bf9ad9925449` runs `ilma_model_db_manager.py --full-sync --git-push`.
- I checked cron output folder: `/root/.hermes/profiles/ilma/cron/output/bf9ad9925449/`.

### Discovery

- Existing cron output: `Script not found: /root/.hermes/profiles/ilma/scripts/python3 scripts/ilma_model_db_manager.py --full-sync --git-push` — meaning cron failed when it last tried.
- New cron entry (post-fix, no_agent=true): script = `bash scripts/ilma_safe_build_and_push.sh`.

### Why Drift Happens

Cron jobs are schedulled scripts. Their PROMPT may have referenced a script that no longer exists, requiring backup migration. The pattern of `cron → bash wrapper → safe` was added to avoid prompt-parser issues.

### Rule Output

> "Cron `bf9ad9925449` schedule=`0 0,12 * * *`, mode=NO_AGENT, script=`bash scripts/ilma_safe_build_and_push.sh`. Memory's claim of `ilma_model_db_manager.py --full-sync --git-push` is OUTDATED. Status: STALE."

---

## Incident 5: MongoDB Numbers Drift Dramatically

### Setup

- Memory said: "FROZEN 25 providers / models=978 / 9 WORKING".

### Discovery (Verified via Real Aggregation)

```python
from pymongo import MongoClient
c = MongoClient(host='172.16.103.253', port=27017, username='quantumtraffic', password='<...>', authSource='admin')
db = c['credentials']
print(db['llm_providers'].estimated_document_count())   # → 22
print(db['models'].estimated_document_count())           # → 2039
print(db['providers'].estimated_document_count())        # → 38
# LIVE-key count check:
print(db['llm_providers'].count_documents({'key_status': 'LIVE'}))   # → 0
```

### Rule Output

> "Memory claimed llm_providers=25, models=978, providers=9 WORKING. Actual: llm_providers=22 (with ZERO LIVE-key), models=2039, providers=38 (28 active). Status: STALE/CONTRADICTED for the specific numbers. Underlying intent (know provider status) is STILL VALID — just numbers drifted."

---

## Lesson: Cascade Discipline

When I do find drift, I also should:

1. **Quantify the drift** — not just "stale", but "off by N"
2. **Find the BASELINE** — when did this become inaccurate?
3. **Choose replacement** — re-run live, capture actual numbers
4. **Validate the underlying intent** — if memory was about "monitor X", the audit moves from "X=25" to "X_current=N". Intent preserved.
5. **Note in replacement entry** — why the old number was changed (memory hygiene)

The over-claim-trap was avoiding steps 2-3 by hand-waving ("this is stale, delete it"). The full audit gives a CLEAN replacement, not just a flag.

---

## Patch File Locations

- Memory framework spec: `~/.hermes/profiles/ilma/skills/self-improvement/memory-audit-protocol/SKILL.md`
- Memory Object Model (v10): `references/v10-autonomous-memory-lifecycle.md`
- False-positive detection complement: `~/.hermes/profiles/ilma/skills/self-improvement/ilma-false-positive-detection/SKILL.md`
