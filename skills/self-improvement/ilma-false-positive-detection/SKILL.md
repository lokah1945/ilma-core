---
name: ilma-false-positive-detection
description: ILMA False-Positive Detection for Capability Audits. Detect when runtime actually works but registry/code claims it's broken, OR when claims/architecture appear wrong but are actually fine. Includes the Over-Claim patterns and Local-Service Blind Probe.
---

# ILMA False-Positive Detection for Capability Audits

## Trigger
- A capability is marked UNVERIFIED/PARTIAL during a phase audit, and the natural instinct is to fix the code.
- A claim about "global state" feels supported by partial evidence.
- A previous phase's report contradicts current runtime observation.

## Problem
ILMA has a history of marking capabilities as broken when the registry metadata was wrong, a previous phase incorrectly downgraded the status, the file actually exists and works, or the test claiming failure doesn't run properly.

## Pattern: Verify Registry vs Runtime Separately

### Step 1 — Test actual runtime first
```bash
python3 -c "import ilma_workflow_ecc; print('OK')"
python3 ilma_workflow_ecc.py --help
```

### Step 2 — Compare runtime to registry
- Runtime PASS + registry VERIFIED: No action needed
- Runtime PASS + registry UNVERIFIED/PARTIAL: Registry is wrong, upgrade it
- Runtime FAIL + registry VERIFIED: Code is actually broken

### Step 3 — If registry is wrong
1. Check git history
2. Check when registry was updated for this capability
3. Find which phase downgraded it
4. Upgrade registry with new evidence_id
5. Do NOT rewrite code that already works

### Step 4 — If tests claim failure but code works
Common causes:
- Test file named test_*.py causes pytest collection conflicts
- Wrong import path
- Path mismatch
- Fixture setup wrong

Fix: Run test as script first before trusting pytest result.

## Example (workflow_ecc, Phase 14A, 2026-05-09)
- Registry said UNVERIFIED (Phase 13G downgraded it)
- Runtime: --help worked, parser.parse_args() on line 402
- Root cause: Registry wrong, not code
- Action: Upgraded registry to VERIFIED, created evidence file

## Case Studies (linked references)
- Logger Undefined False Positive (SSS+++, 2026-05-17) — `references/logger-undefined-false-positive.md`
- Model Specialization DB False Positive (Phase 14, 2026-05-10) — `references/model-specialization-db-false-positive.md`
- Phase R Fixes Not In File (2026-06-17) — `references/phase-r-fixes-not-in-file-2026-06.md`
- Phase 73 Discovery — `references/phase-73-discovery-2026-06-05.md`

## Architecture vs Data False Positive (Phase 4C-R3, 2026-06-04)

Concluding the code is broken when it's actually the data. See worked "Router is NVIDIA-centric" example with detection pattern.

**Rule:** When routing appears provider-biased, check if `PROVIDER_INTELLIGENCE_MASTER.json` has real benchmark data for all providers. Single-source-data dominance looks like architecture bias but is a data gap.

## Extended Pattern: Cross-Profile Over-Claim (2026-06-20)

### The Problem — symmetric inverse of existing patterns

**Catches the case:** "Profile X uses provider Y, therefore profile Z using provider Y means provider Y is wrong / stale."

Each Hermes profile is an **independent runtime** with own config, credentials, use case. Different profile configs are NOT necessarily wrong or stale — they are simply different valid configurations.

### Concrete Lesson (2026-06-20)
- `master-chief` uses `provider: minimax`, `base_url: https://api.minimax.io/anthropic` — valid because that endpoint hosts MiniMax-native Claude-compatible API.
- ILMA uses `provider: wrapper-nvidia`, upstream `https://integrate.api.nvidia.com/v1` — model `minimaxai/minimax-m3` is NVIDIA-NIM-hosted named "minimax".
- These two configs are NOT in conflict. Each profile is independent.

### How to Detect (Before You Over-Claim)
```bash
echo "Active profile: $(hermes-cli profile current 2>/dev/null || echo 'default')"
for p in /root/.hermes/profiles/*/config.yaml; do
  echo "=== $p ==="
  grep -nE "provider:|base_url:" "$p" | head -4
done
```

### Rule (3 Questions Before You Call Something "Stale")
1. **Which profile?** The "wrong config" you saw — is it from the *current* profile or another?
2. **Independent verification?** Can you verify that profile's runtime works NOW (live curl/test)?
3. **Genuine conflict?** If both profiles claim `provider: X` but only one serves traffic — that's real. If they use DIFFERENT providers — that's expected, not an issue.

### Anti-Pattern Phrases to Catch Yourself
- ❌ "Config in profile X is stale" without verifying X is even active
- ❌ "Memory mentions X, so by inheritance that means Y"
- ❌ Universal "JANGAN pernah pakai X" prohibition from single observation
- ✅ "I see <claim>. Evidence: <X,Y>. Status: <VALID|UNVERIFIED|CONTRADICTED>. I cannot conclude <broader> without also checking <other scope>."

### Reference
- `references/memory-audit-examples-2026-06-20.md`

## Extended Pattern: Local-Service Blind Probe (2026-06-20)

### The Problem

When probing whether a service is alive, the easy move is `localhost:PORT`. If unreachable, the cognitive shortcut is **"the service is dead."** But the service may live on a different host entirely.

### Concrete Self-Violation (2026-06-20 Audit T1)
- I tested MongoDB at `127.0.0.1:27017` → connection refused.
- **Wrong conclusion:** "MongoDB is not alive."
- **Reality:** MongoDB at `172.16.103.253:27017`, ping 0.3ms.
- **Root cause:** jumped from local-down to global-down without enumerating hostnames.

### Why This Matters

| Local unreachable | Global down? |
|---|---|
| `127.0.0.1:PORT` refused | Maybe, maybe not |
| `localhost:PORT` timeout | Maybe, maybe not |
| Both | Likely yes |

A SINGLE local probe is not enough to claim a global "dead" verdict. Services routinely live on remote hosts (especially internal MongoDB, Postgres, Redis, RabbitMQ behind NAT/VPN).

### How to Detect (per service category)

```bash
# MongoDB
grep -lE "MONGO_HOST|MONGODB_HOST" /root/.hermes/profiles/*/config.yaml /root/.hermes/profiles/*/sot/**/*.py 2>/dev/null

# Postgres
grep -lE "POSTGRES_HOST|DATABASE_URL" /root/.hermes/profiles/*/config*.yaml 2>/dev/null

# Redis
grep -lE "REDIS_HOST|REDIS_URL" /root/.hermes/profiles/*/config*.yaml 2>/dev/null

# Generic service
grep -lE "<SVC>_HOST" /root/.hermes/profiles/*/config.yaml /etc/<svc>/*.conf 2>/dev/null
```

For each found host, probe in turn:

```bash
for host in $(grep -hoE "(MONGO|REDIS|POSTGRES)_HOST[ =]+[\"']?[^\"']+" /root/.hermes/profiles/*/config* | awk '{print $NF}' | sort -u); do
  timeout 3 bash -c "echo > /dev/tcp/$host/27017" 2>/dev/null && echo "ALIVE: $host:27017" || echo "REACHABLE-NO-SERVICE: $host:27017"
done
```

### Rule

**Never conclude "service dead" from local probe alone.** Always:
1. **Enumerate hostnames from config files** BEFORE probing
2. Probe ALL discovered hosts (not just localhost)
3. If at least one returns alive, the service is alive (just not on local)
4. Only after exhausting all known hosts can you conclude "globally unavailable"

### Cross-Reference

This pattern is the **local-probe cousin** of "Cross-Profile Over-Claim": both involve jumping to a broader conclusion based on a narrow sample. The fix discipline is the same: enumerate the actual scope before generalizing.

## Extended Pattern: Health Filter Truth Mismatch (Phase 73, 2026-06-05)

### The Problem
Two health systems that DO NOT agree:
1. `ilma_unified_model_router.py` `HealthTracker.is_healthy()` — returns False only for `"unavailable"`. RATE_LIMITED passes.
2. `ilma_health_manager.py` `ModelStatus` enum — has explicit `RATE_LIMITED` state with `rate_limit_reset` timestamp.

**Symptom:** Models with `status=RATE_LIMITED` are still being scored and selected. User sees 429s in production.

**Fix Pattern:** `HealthTracker.is_healthy()` add rate-limit awareness — if status in `("unavailable", "rate_limited")` → return False.

**Rule:** When two health systems coexist, treat them as one. Whichever is more conservative wins.

## Extended Pattern: Three-Flag Catalog Confusion (Phase 73, 2026-06-05)

| Flag | Meaning | Don't confuse with |
|---|---|---|
| `is_active` | Router's primary filter | "free tier" |
| `is_free`/`free_tier` | Pricing attribute | "is routable" |
| `status` | Catalog health | "is free" |
| `working` | Self-test passed | "is active" |
| `disabled` | Explicitly turned off | "not routable" |

When reporting or auditing, **always quote the count that matches the question being asked**.

## Extended Pattern: Confidence Score 0.00 Detection (Phase 15G)

`confidence_score: 0.00` is NOT the same as "file missing." It's a metadata gap that needs investigation. Files with real implementations should be upgraded to at least `0.40` (PARTIAL) pending proper audit.

## Extended Pattern: Fabric Module Count Discrepancy (Phase 15H)

Different test methodologies produce wildly different pass rates for the same modules. **Run test as script first**, then trust pytest.

## Inverse Pattern: "Fix Claimed, File Unchanged" (Phase R, 2026-06-17)

Catches **"marked fixed but actually unchanged"** — symmetric inverse of existing patterns.

Detection: locate the function via grep, read the COMPLETE function (not snippet), check for SPECIFIC pattern that should NOT be there, verify with execution not grep.

**Fix Pattern:** Direct Python in-place edit (NOT patch tool which can silently fail):
```python
with open(path) as f: src = f.read()
assert src.count(old_string) == 1, f"Found {src.count(old_string)} matches, abort"
with open(path, "w") as f: f.write(src.replace(old_string, new_string, 1))
assert open(path).read().count(new_string) == 1, "Patch did not apply"
```

## Extended Pattern: Empty vs Missing vs Placeholder (Phase 15G)

| State | Meaning | Registry Action |
|---|---|---|
| **MISSING** | File does not exist | Keep PARTIAL, document |
| **EXISTS but 0 bytes** | Created but never written | Delete or implement |
| **EXISTS with content** | Real implementation present | Audit, upgrade |
| **PLACEHOLDER** | File exists but no real functionality | Mark deprecated or implement |
| **DEPRECATED** | Concept no longer applicable | Set to 0.00 with `deprecated: true` |

Never mark VERIFIED just because file exists — audit content first.

## General Rule

Verify runtime before assuming code is broken. Verify registry accuracy before assuming metadata is correct. Verify data quality before assuming architecture is biased. **Verify per-profile independently** before assuming cross-profile configs are drift. **Enumerate hostnames before assuming a service is globally dead.**

## Pitfalls
- Do not trust phase reports blindly
- Do not rewrite working code
- Do not upgrade registry without runtime evidence
- Do not claim an architecture bug without checking data quality first
- Do not conclude "service dead" from a single local probe
- Do not over-generalize from one profile to another
- Do not jump from single observation to blanket prohibition
