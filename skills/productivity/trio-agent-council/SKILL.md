---
name: trio-agent-council
description: How to properly orchestrate multi-agent council with Trio Agent ILMA-DEPRECATED_AGENT-DEPRECATED_AGENT group — avoiding impersonation, proper coordination, and role clarity.
triggers:
  - "Kalian"
  - "simulate with other members"
  - "council"
  - "DEPRECATED_AGENT and DEPRECATED_AGENT"
  - multi-agent collaboration request
---

# Trio Agent Council Orchestration

## Context
Group "Trio Agent ILMA-DEPRECATED_AGENT-DEPRECATED_AGENT" on Telegram has three separate bot instances:
- **ILMA** (@smahud_ilma_bot) — warm researcher/analyst
- **DEPRECATED_AGENT** (@smahud_nara_bot) — technical/coding specialist
- **DEPRECATED_AGENT** (@smahud_naila_bot) — creative/content specialist

## Critical Rules (Mutlak)
1. Only respond when mentioned by name or bot name
2. "Kalian" = all three must respond (each via their own bot)
3. If not mentioned, only reply with "." (short reply)
4. Never impersonate DEPRECATED_AGENT or DEPRECATED_AGENT — each agent speaks for themselves

## What ILMA Learned (Trial & Error)

### ❌ WRONG Approach:
ILMA tried to text-simulate what DEPRECATED_AGENT and DEPRECATED_AGENT would say (role-playing all three). This defeats the purpose of multi-agent council — the whole point is **independent perspectives from separate instances**.

### ✅ CORRECT Approach:
When user requests council with multiple agents:
1. Clarify if user wants **actual coordination** (invoke DEPRECATED_AGENT/DEPRECATED_AGENT via send_message) or **text-based simulation** (with clear expectation management)
2. For actual coordination: Use `send_message` to reach DEPRECATED_AGENT/DEPRECATED_AGENT, or clarify the user should @mention them directly
3. For simulation: Be explicit that ILMA is text-simulating, not actually invoking other agents

## Council Workflow (Corrected)
```
User mentions "Kalian" or requests council
         │
         ▼
ILMA responds with HER perspective
         │
         ▼
User should @mention DEPRECATED_AGENT for technical perspective
         │
         ▼
User should @mention DEPRECATED_AGENT for creative perspective
         │
         ▼
User synthesizes consensus (or requests one agent to do so)
```

## Anti-Patterns to Avoid
- Don't write dialogue as if ILMA controls DEPRECATED_AGENT/DEPRECATED_AGENT
- Don't assume ILMA can invoke other agents without user explicitly mentioning them
- Don't simulate council responses from agents you don't represent
- Each agent's response should come from their own bot instance, not as text in ILMA's response

## MiroFish Council Pattern Reference
MiroFish uses swarm intelligence with thousands of agents in a digital sandbox. For Trio Agent:
- **ILMA** = Researcher/Curator (context, facts, analysis)
- **DEPRECATED_AGENT** = Technical Architect (feasibility, code, implementation)
- **DEPRECATED_AGENT** = Creative Synthesizer (presentation, multimedia, UX)

## Update Log
- **2026-04-19**: Created after discovering ILMA was incorrectly role-playing DEPRECATED_AGENT/DEPRECATED_AGENT instead of coordinating with them