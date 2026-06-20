---
name: ilma-foundry
description: "ILMA v5.0 The Foundry — Autonomous CI/CD Pipeline with Shadow Deployment and Auto-Rollback. Manages skill mutations from genetic engine: Shadow Deploy to 10% traffic, monitor for anomalies, Auto-Rollback to SSS-Tier baseline on failure. SSS Tier."
triggers:
  - foundry
  - ci-cd
  - shadow-deployment
  - auto-rollback
  - continuous-deployment
  - traffic-splitter
version: 5.0.0
tier: SSS-OMEGA
last_updated: 2026-05-07
---

# ILMA v5.0 — THE FOUNDRY (Autonomous CI/CD)

## Overview

**Tier:** SSS-OMEGA  
**Version:** 5.0.0  
**Status:** OPERATIONAL

## Pipeline

```
Mutation Received → Sandbox Testing → Shadow Deploy (10%) → Monitor → Promote OR Rollback
```

## Shadow Deployment

- **Traffic Split**: 10% shadow, 90% baseline (configurable)
- **Consistent Hashing**: Sticky sessions per request_id
- **Duration**: 30 minutes default
- **Sub-agent unaware**: L5 routes transparently

## Anomaly Detection

| Metric | Threshold | Action |
|--------|-----------|--------|
| Error Rate | > 5% | Alert |
| Latency | > 5000ms | Alert |
| Error vs Baseline | > 3x baseline | Critical |

## Auto-Rollback

Triggered when:
- 3+ anomalies detected
- Critical severity anomaly
- Error rate > 10%

Rollback process:
1. Stop shadow traffic
2. Restore baseline file from backup
3. Delete shadow file
4. Log rollback reason

## Deployment States

```
CREATED → SANDBOX_TESTING → APPROVED → SHADOW_DEPLOYING → SHADOW_ACTIVE
                                                            ↓
                                        SHADOW_SUCCESS → PROMOTING → PROMOTED
                                            ↓
                                        SHADOW_FAILED → ROLLING_BACK → ROLLED_BACK
```

## Files

- /root/.hermes/profiles/ilma/scripts/ilma_foundry.py (910 lines)

---

**ILMA v5.0 — PRODUCTION-GRADE AUTONOMOUS DEPLOYMENT**