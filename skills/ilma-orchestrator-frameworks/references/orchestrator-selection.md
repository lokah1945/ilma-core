# Orchestrator Selection Quick Reference

## When to Use Which Framework

| Task Type | Framework | Key Signal |
|------------|-----------|------------|
| Logical validation, deterministic pass/fail | `langgraph` | "validate", "verify", "check", "criteria" |
| Code execution, testing, stack traces | `autogen` | "execute", "run", "stack trace", "test" |
| Prompt optimization, template evolution | `dspy` | "improve", "optimize", "prompt", "template" |
| Multi-role end-to-end deliverables | `metagpt` | "platform", "system", "full build" |
| Adversarial debate, critique | `gemini` | "debate", "critic finds flaws", "actor-critic" |

## Temperature Asymmetry (CRITICAL)

The debate only works if temperature is asymmetric:

| Role | Temperature | Why |
|------|-------------|-----|
| Actor (ILMA/Hermes) | 0.4 - 0.7 | Creative flexibility, can find alternative routes |
| Judge (Critic) | 0.0 - 0.1 | Deterministic, analytical, unforgiving |

**Never set both to same temperature — debate becomes pointless.**

## RCR Pattern Rule

> **Critic's job is NOT to give the correct answer — it's to find flaws.**

If Critic provides solutions, it's not RCR. The Critic should:
- Find gaps, logical errors, unsupported assumptions
- Point out missing edge cases
- Identify what's wrong — NOT how to fix it

## Metric Types (DSPy)

| Metric | Checks | Fail Threshold |
|--------|--------|---------------|
| `correctness` | Structure, function, error handling | score < 0.7 |
| `style` | Tag ordering, formatting | score < 0.7 |
| `efficiency` | Line count, redundancy, complexity | score < 0.6 |
| `safety` | eval(), exec(), shell=True, SQL injection | score < 0.7 |
| `completeness` | Criteria coverage | score < 0.7 |

## SOP Stages (MetaGPT)

```
REQUIREMENTS → ARCHITECTURE → IMPLEMENTATION → TESTING → REVIEW → COMPLETE
     ↓              ↓              ↓              ↓          ↓
   (PM)         (Architect)    (Engineer)      (QA)     (Reviewer)
```

**Rejection loop:** If TESTING fails → back to IMPLEMENTATION → retry  
**Rejection loop:** If REVIEW fails → back to IMPLEMENTATION → retry

## TeachableAgent Pattern (AutoGen)

1. **Before task:** Pull lessons from memory for identical/similar patterns
2. **During task:** Store failure as lesson when resolved
3. **After task:** If memory integration available, extract lesson

```python
# Pre-task: pull
lessons = memory.retrieve(task, limit=3)
for l in lessons: context["lessons_learned"].append(l.solution)

# Post-task: store
if failure_resolved:
    memory.extract_lesson(category="...", problem="...", solution="...")
```

## Conditional Edge Routing (LangGraph)

```
         ┌─────────────┐
         │   ACTOR     │ (produces solution)
         └──────┬──────┘
                │
                ▼
         ┌─────────────┐
         │    JUDGE    │ (evaluates)
         └──────┬──────┘
                │
       ┌────────┴────────┐
       │                 │
    PASS?             FAIL?
       │                 │
       ▼                 ▼
     [END]         [→ ACTOR]
                   (retry with critique)
```

## Teleprompter Mutations (DSPy)

Three mutation types:

| Type | Effect | Example |
|------|--------|---------|
| `ADD_CONSTRAINT` | Hard rule added to prompt | "NEVER use eval()" |
| `EMPHASIZE` | Existing rule made stronger | "CRITICAL: use tags" |
| `ADD_CHECKLIST` | Checklist added | "Check: validation, error, JSON" |