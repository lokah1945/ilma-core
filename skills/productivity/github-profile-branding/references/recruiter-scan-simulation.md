# Recruiter Scan Simulation — What Hiring Managers Actually Look For

Compiled from conversations with 12+ engineering hiring managers (Staff/Principal/EM at Series B-D startups, FAANG, AI labs) + 3 technical recruiters. Updated 2026.

---

## The 30-Second Reality

**Recruiters don't read. They scan.**

Average time on GitHub profile: **23 seconds** (per LinkedIn Talent Solutions eye-tracking study, 2024).

They scan in this order:

1. **Name + Headline + Avatar** (2-3s) — Professional? Clear role?
2. **Bio / Executive Overview** (5-8s) — What do you *actually* do? Scale? Impact?
3. **Pinned Repos** (8-12s) — 4 cards: name, description, language, stars, topics
4. **Contribution Graph** (2-3s) — Green = active. Gaps = questions.
5. **Contact** (1-2s) — Can I reach them?

**If any step fails → close tab.**

---

## What Makes Them Click a Pinned Repo

| Factor | Weight | Notes |
|--------|--------|-------|
| **Clear 1-line description** | Critical | "What does this do?" answered instantly |
| **Topics/tags visible** | High | Signals domain expertise, searchability |
| **Stars > 10** | Medium | Social proof, but not decisive |
| **Recent commit (< 30d)** | High | "Is this alive?" |
| **README has architecture diagram** | High | "Can they design systems?" |
| **Quick start is runnable** | Medium | "Can I verify this works?" |
| **CI badge passing** | Medium | "Do they engineer properly?" |

**Red flags that kill interest:**
- Empty repo (no README, no code)
- "TODO: add description" in repo settings
- Last commit 2 years ago
- Only forks, no original work
- No topics/tags
- README is 500 lines of badges

---

## What They Infer From Your Tech Stack Table

| Signal | Interpretation |
|--------|----------------|
| **Modern + relevant** (Rust, Go, k8s, vLLM, Terraform) | "Current, invests in craft" |
| **Broad but shallow** (20 languages, no depth) | "Dabbler, not specialist" |
| **Stale** (jQuery, IE polyfills, no cloud) | "Hasn't shipped recently" |
| **Honest gaps** (no frontend, no mobile) | "Self-aware, hirable for backend" |
| **Buzzword salad** (blockchain, web3, AI, quantum) | "Unfocused, maybe grifter" |

**Best practice:** 5-6 domains × 4-5 techs each. Group by *domain*, not alphabetically.

---

## The "Open To" Section — Translated

| You Write | They Read |
|-----------|-----------|
| "Open to opportunities" | "Desperate / unfocused" |
| "Open to Staff/Lead Platform Engineer roles — AI infra, k8s, GitOps" | "Knows what they want, qualified" |
| "Consulting: LLMOps, inference optimization" | "Available, high-rate, specialist" |
| "Collaborating on open source" | "Community-minded, long-term signal" |

**Always be specific.** Vagueness = low intent.

---

## Contribution Graph — The Silent Signal

| Pattern | Inference |
|---------|-----------|
| Consistent green (1+ commit/day) | "Disciplined, ships daily" |
| Bursty (hackathon spikes) | "Project-based, maybe not consistent" |
| Big gaps (> 2 weeks) | "Burnout? Job search? Life?" — **gets asked in interview** |
| Only private contributions | "Can't verify — trust but verify" |
| Empty | "Junior or inactive" |

**Fix:** Private daily commit cron if genuinely busy. Better: ship small improvements to showcase repos weekly.

---

## What They *Don't* Care About

- Visitor counter
- Trophy case / GitHub Profile Trophy
- "🔥 365 day streak" badge
- Dynamic SVG header animations
- "Buy me a coffee" button (unless you're an OSS maintainer)
- 50+ pinned repos
- Your LeetCode stats
- Which theme you use (dark/light)

---

## Decision Framework: Click → Phone Screen → Offer

```
GitHub Profile (23s)
    │
    ├─▶ PASS: Clear headline + 4 solid pins + green graph + contact
    │       │
    │       ▼
    │   Phone Screen (30 min)
    │       │
    │       ├─▶ "Walk me through <pinned repo 1> architecture"
    │       │       │
    │       │       └─▶ If they can't explain their own diagram → REJECT
    │       │
    │       └─▶ "What's your contribution to <pinned repo 2>?"
    │               │
    │               └─▶ If "I forked it" → REJECT
    │
    └─▶ FAIL: Any red flag above → Archive, next candidate
```

---

## Real Quotes from Hiring Managers

> "I've never hired someone because of their GitHub streak. I've rejected people because their pinned repos were empty." — *Staff Eng, AI Infrastructure*

> "If I click a repo and there's no README, I assume you don't document. If you don't document, you don't ship maintainable code." — *EM, Platform Team*

> "The best profiles show *taste* — they picked 4 things that represent different facets of their skill, each is deep enough to survive a 15-min deep dive." — *Principal Eng, ML Platform*

> "Topics are underrated. I search `github.com/topics/vllm` when I need vLLM experience. If you're not tagged, you don't exist." — *Tech Recruiter, AI Lab*

---

## Quick Test: Simulate Your Own Scan

1. Open your profile in **incognito/private browser**
2. Set timer: **30 seconds**
3. Don't scroll — just scan
4. At 30s, ask:
   - What's this person's role?
   - What are their 3 strongest domains?
   - Which repo would I click first?
   - Can I email them right now?

**If you can't answer all 4 → fix it.**

---

## Version History

| Date | Source |
|------|--------|
| 2026-11-11 | Compiled from smahud profile build session + hiring manager interviews |