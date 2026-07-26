---
name: ilma-iterate-until-target
description: ILMA Iterate Until Target Pattern — systematic iteration until metrics hit target (not "good enough")
category: self-improvement
triggers:
  - "iterate until"
  - "achieve 100%"
  - "optimize until"
  - "learn until"
  - "repeat until target"
---

# ILMA Iterate Until Target Pattern

## Purpose
Systematic iteration until target metrics are achieved — not "good enough", not 80%, but 100%.

## Origin
Learned from AYDA Fusion session (2026-05-08) where ILMA iterated 1000 times to achieve 100% fusion with AYDA components.

---

## THE PATTERN

```
1. Start with CORE (minimum viable)
2. Measure current state
3. Calculate gap to target
4. Iterate: add/fix → measure → repeat
5. Stop when target MET (not "good enough")
```

---

## EXAMPLE: AYDA Fusion Journey

| Iteration | Components | Score | Status |
|-----------|------------|-------|--------|
| First attempt | 4 | 40% | Started with core |
| Second attempt | 8 | 80% | Expanded, but STUCK |
| **Discovery** | formula = 10 × 10% = 100% |
| Third attempt | 10 | 100% | **TARGET MET** |

**Key moment:** When stuck at 80%, did NOT accept 80%. Discovered WHY (needed 10 components, not 8), then iterated until 100%.

---

## WHEN TO USE

- Task: "Learn X until you achieve Y"
- Task: "Optimize until 100%"
- Task: "Iterate until all tests pass"
- Task: "Repeat until fusion score is 100%"
- Any task with explicit target metrics

---

## ANTI-PATTERNS

### ❌ "Good Enough" Trap
```
Got 80% → "That's probably fine"
Result: Incomplete integration, future problems
```

### ❌ Chasing Quantity (Different!)
```
Create 300 empty scripts to look impressive
Result: Bloated agent, no actual improvement
```
**This is different from Iterate Until Target!**

---

## KEY DISTINCTION

| Pattern | What | Result |
|---------|------|--------|
| Chasing quantity | 300 empty scripts | Bloated, useless |
| Iterate until target | 10 real components | 100% fusion |

Both involve "many iterations", but:
- **Chasing quantity** = iterations without measurement
- **Iterate until target** = iterations WITH measurement until target MET

---

## IMPLEMENTATION

### Step 1: Define Target
```python
TARGET = 100  # percent, tests passed, components, etc.
```

### Step 2: Measure Current State
```python
current = measure()  # Get current score
gap = TARGET - current
```

### Step 3: Iterate with Purpose
```python
while current < TARGET:
    # Analyze WHY gap exists
    reason = analyze_gap(current, TARGET)
    
    # Take targeted action
    action = decide_action(reason)
    execute(action)
    
    # Measure again
    current = measure()
```

### Step 4: Stop When MET
```python
if current >= TARGET:
    print("TARGET ACHIEVED")
    # Don't add more "just in case"
```

---

## LESSONS FROM AYDA FUSION

1. **First attempt ≠ optimal** — Start with core, measure, then expand
2. **80% ≠ almost done** — 80% might mean missing key component
3. **Discover the formula** — Sometimes target = 10 × 10%, sometimes different
4. **Iterate with analysis** — Each iteration should understand WHY gap exists
5. **Stop at target** — Don't over-engineer after target is met

---

## FUSION SCORE EXAMPLE

```python
def calculate_fusion_score(components):
    """
    AYDA Fusion: 10 components × 10% = 100%
    Each component contributes equally
    """
    COMPONENT_COUNT = 10
    PER_COMPONENT = 100 / COMPONENT_COUNT  # 10%
    
    score = len(components) * PER_COMPONENT
    return min(score, 100)  # Cap at 100%
```

---

## Quality Standards

- [x] Target defined clearly
- [x] Measurement at each step
- [x] Gap analysis before action
- [x] Iteration until target MET
- [x] No over-engineering after target
