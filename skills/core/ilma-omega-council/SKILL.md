---
name: ilma-omega-council
description: "ILMA v4.0 Omega Council — Mixture of Agents Architecture. Sub-Agents: SecOps, Architect, Nexus, Creator with async message broker and L5 conflict resolution. SSS Tier."
triggers:
  - omega-council
  - mixture-of-agents
  - sub-agents
  - council
  - conflict-resolution
version: 4.0.0
tier: SSS-OMEGA
last_updated: 2026-05-07
---

# ILMA v4.0 — OMEGA COUNCIL

## Overview

**Tier:** SSS-OMEGA  
**Version:** 4.0.0  
**Status:** OPERATIONAL

## Architecture

Mixture of Agents Architecture with 4 specialized Sub-Agents communicating via async message broker.

### Sub-Agents

| Agent | Role | Veto Power |
|-------|------|------------|
| SecOps | Security Operations | YES |
| Architect | System Design | NO |
| Nexus | Network Infrastructure | NO |
| Creator | Content Generation | NO |

### Message Broker

Async pub/sub with priority queuing. Non-blocking communication.

### L5 Conflict Resolver

Automatic mediation when SecOps blocks Architect's deployment.

## Files

- /root/.hermes/profiles/ilma/scripts/ilma_council_orchestrator.py (1374 lines)

---

**ILMA v4.0 — THE OMEGA COUNCIL**