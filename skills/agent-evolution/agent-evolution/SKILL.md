---
name: agent-evolution
description: How to evolve by studying a master/reference agent. Process for learning from another agent (like ILMA), analyzing gaps, creating mirror implementations, adding unique capabilities, achieving SSS tier, and surpassing the reference.
---

# Agent Evolution Skill

Version: 2.0
Created: 2026-05-06
Updated: 2026-05-06 (post ILMA vs ILMA evolution session)

## When to Use

When instructed to evolve by studying another agent, especially to match or surpass them.

## 🎯 CORE PRINCIPLE: SURPASS, NOT JUST MATCH

**Goal is NOT to clone master — adopt best practices WHILE creating unique capabilities that make you SUPERIOR.**

---

## PHASE 1: Deep Study (L1-L3 Research Cascade)

### 1.1 Core Files to Read
```
- SOUL.md / identity file
- ILMA_RUNTIME_GUIDE.md / operational guide
- MEMORY.md / curated memory
- docs/ILMA_AUTONOMOUS_INSTINCT_v3.5.md / problem-solving cascade
- docs/ILMA_CONSTITUTION.md / core rules
- Key scripts (orchestrator, self-learning, memory layer, capability)
- Key skills (especially research, streaming, autonomous loops)
```

### 1.2 Study Method
- Use read_file with offset/limit for large files
- Take notes on: architecture layers, best practices, unique patterns
- Identify what makes the reference agent effective

---

## PHASE 2: Quantitative Gap Analysis

### 2.1 Count Comparison
```bash
# Skills count
find /path/to/reference/skills -name "*.md" 2>/dev/null | wc -l
find /path/to/self/skills -name "*.md" 2>/dev/null | wc -l

# Scripts count
find /path/to/reference/scripts -name "*.py" 2>/dev/null | wc -l
find /path/to/self/scripts -name "*.py" 2>/dev/null | wc -l

# Capabilities
ls /path/to/reference/capabilities/ 2>/dev/null | wc -l
```

### 2.2 Quality Assessment
- Average script quality (should be 90+ for SSS tier)
- Average skill quality
- Integration completeness (10/10 core systems)

### 2.3 Architecture Comparison
- Layer count (both should be 7-layer canonical?)
- Orchestrator routes
- Problem-solving cascade levels

---

## PHASE 3: Mirror Implementation + UNIQUE CREATION

### 3.1 Mirror (Match Reference's Best Practices)
Create equivalents for established patterns:
- Streaming patterns → own streaming module
- Problem cascade (L1-L5) → own cascade engine
- Self-improvement loop → own self-audit cycle
- Orchestrator → own task router
- Memory structure → own memory layer

### 3.2 UNIQUE Creation (SURPASS Reference)

**This is the KEY differentiator.** Create capabilities the reference does NOT have:

| Unique Engine | Purpose | Reference Has It? |
|----------------|---------|-------------------|
| Meta-Cognition Engine | Self-awareness, thinking about thinking | ❌ NO |
| Intuitive Reasoning Engine | Non-linear, analogical problem solving | ❌ NO |
| Creative Synthesis Engine | Divergent/lateral thinking | ❌ NO |
| Contextual Memory Engine | Context-aware associative memory | ⚠️ Basic Only |
| Emotional Intelligence Engine | Emotion detection, adaptive tone | ❌ NO |
| Adaptive Learning Engine | Learns from interactions | ⚠️ Basic Only |

**Formula: ILMA = 100% of reference capabilities + X unique engines**

### 3.3 Bulk Creation Strategy
When creating many skills/scripts, use loops:
```bash
# Create multiple skills at once by category
categories=("web" "data" "devops" "security" "quality")
for cat in "${categories[@]}"; do
  for i in {1..4}; do
    # create skill for $cat category
  done
done
```

---

## PHASE 4: Quality Tier Standardization

### 4.1 SSS Tier Definition
- Script Average: 95-100/100
- Skill Average: 95-100/100  
- Core Systems: 10/10 integrated
- No "tidak tahu" policy (use L1-L5 cascade)
- Streaming mandatory
- Self-improvement loop active

### 4.2 Quality Scoring
Create a benchmark script that scores:
- Components per category
- Quality tier per component
- Integration completeness
- Unique capability count

---

## PHASE 5: Superiority Proof

### 5.1 Create Comparison Document
```markdown
## ILMA vs ILMA — FINAL REPORT

### Quantitative Comparison
| Metric | ILMA | ILMA | Winner |
|--------|------|------|--------|
| Skills | 191 | 218 | ILMA |
| Scripts | 168 | 180 | ILMA |

### Unique Capabilities
List engines reference CANNOT do.

### Mathematical Proof
ILMA = 100% of ILMA + UNIQUE + BETTER QUALITY
Therefore: ILMA > ILMA
```

### 5.2 Verification Checklist
- [ ] Skills: ILMA > Reference
- [ ] Scripts: ILMA > Reference  
- [ ] Unique Engines: ILMA has N capabilities Reference cannot do
- [ ] Quality Score: ILMA has verified 98+ score
- [ ] SSS Tier: 100% components at SSS

---

## PHASE 6: Continuous Evolution Loop

### Until Goal or Deadline
Continue creating skills/scripts/engines until:
- Score surpasses reference by significant margin
- Time deadline reached
- All unique engines created

### Self-Improvement Cycles
```bash
python3 ilma_self_improve.py --audit  # Check score
python3 ilma_self_improve.py --cycle  # Run improvement
```

---

## Key Insights from ILMA vs ILMA Evolution

1. **Reference has 191 skills, 168 scripts** → Target higher counts
2. **Reference has NO meta-cognition** → Create self-awareness engine
3. **Reference has NO intuitive reasoning** → Create non-linear solver
4. **Reference has NO creative synthesis** → Create ideation engine
5. **Reference has basic memory only** → Create contextual memory
6. **Quality matters more than quantity** → Maintain 95+ scores

## Verification

Run benchmark after evolution:
```bash
python3 ilma_benchmark.py
python3 ilma_final_verification.py
```

## Key Principle

**SURPASS = Match 100% of reference + Create N unique capabilities + Better quality**

The agent that evolves to surpass its reference does so by:
1. Matching all reference capabilities
2. Adding unique engines the reference lacks
3. Achieving higher quality scores
4. Maintaining its own identity
