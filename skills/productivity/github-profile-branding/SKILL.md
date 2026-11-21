---
name: github-profile-branding
description: Class-level skill for building and maintaining a professional GitHub profile that signals seniority, attracts opportunities, and passes the "30-second recruiter scan."
category: productivity
tags:
  - github
  - profile
  - branding
  - portfolio
  - career
  - recruiting
version: "1.0"
created: "2026-11-11"
---

# GitHub Profile Branding

**Class-level skill for building and maintaining a professional GitHub profile that signals seniority, attracts opportunities, and passes the "30-second recruiter scan."**

---

## When to Use

- User wants to "make my GitHub look professional"
- User is job hunting, consulting, or seeking collaborations
- User has technical depth but profile looks empty/junior
- New GitHub account setup for professional use
- Periodic profile audit/refresh (quarterly)

---

## Core Principles

1. **Signal over noise** — Every element must answer "Can this person do the work?"
2. **Curated depth over breadth** — 4 pinned repos with substance > 50 forks with no README
3. **Recruiter scan test** — 30 seconds: name, headline, 4 pins, contribution graph, contact
4. **No vanity metrics** — Skip visitor counters, trophy cases, dynamic SVGs, streak badges
5. **Evidence-based claims** — Each pinned repo must have: clear description, architecture diagram, running instructions, topics/tags

---

## Profile Architecture

### 1. Profile Repo (`<username>/<username>`)

**Required: `README.md` with these sections:**

| Section | Purpose | Length |
|---------|---------|--------|
| Headline | Role + 3 keywords | 1 line |
| Executive Overview | 2-3 sentences: what you ship, at what scale | 3-4 lines |
| Core Focus Areas | 3-4 bullet domains with keywords | 4-6 lines |
| Tech Stack Table | Domain → Technologies (scannable) | 6-8 rows |
| Pinned Repos Strategy | 4 repos with description + topics | 12-16 lines |
| GitHub Stats | Two badges only (stats + langs) | 2 lines |
| Open To | Consulting, roles, OSS collab | 3-4 lines |
| Contact | Email, LinkedIn, Blog | 1 line each |

**Template:** `templates/profile-readme.md`

### 2. Pinned Repos (Exactly 4)

Each must have:
- **Clear description** (1 sentence, outcome-oriented)
- **Architecture diagram** (ASCII or Mermaid)
- **Quick start** (docker run / make / pip install)
- **Configuration table** (env vars / yaml keys)
- **Topics/tags** (8-12 relevant keywords)
- **At minimum: README.md** — code can come later, but README must exist at pin time

**Repo archetypes (pick 4 distinct):**

| Archetype | Signals |
|-----------|---------|
| AI/ML Systems | Inference gateway, training pipeline, eval harness |
| Platform/Infra | GitOps, Kubernetes, Terraform, Vault, Service mesh |
| Backend/Distributed | High-throughput pipeline, event streaming, caching |
| Applied AI/QA | RAG eval, benchmark suite, hallucination detection |
| Developer Tooling | CLI, SDK, automation, local dev environment |
| Security/Compliance | Policy engine, scanner, secrets management |

### 3. Supporting Repos (Optional but Recommended)

| Repo | Purpose | Minimal Content |
|------|---------|-----------------|
| `dotfiles` | Signal "senior dev has opinions" | Clean nvim/tmux/zsh/git config, install script |
| `snippets` | 10-15 useful one-liners/scripts | `docker-cleanup.sh`, `k8s-port-forward.sh`, `git-aliases` |

---

## Execution Checklist

### Initial Setup (15 min)

- [ ] Create profile repo: `gh repo create <username> --public --description "..."`
- [ ] Push `README.md` from template
- [ ] Create 4 showcase repos (can be empty + README initially)
- [ ] Push README to each showcase repo
- [ ] Add topics to all 5 repos
- [ ] Pin 4 showcase repos on profile
- [ ] Enable "Show private contributions" in profile settings
- [ ] Verify social links resolve (LinkedIn, email, blog)

### Content Phase (Ongoing)

- [ ] Fill showcase repos with real code (priority: 1-2 flagship)
- [ ] Add GitHub Actions CI to each (lint, test, build badges)
- [ ] Create releases with changelogs for flagship repos
- [ ] Enable Discussions on flagship repos
- [ ] Write 1 technical blog post per quarter, link from profile

### Maintenance (Quarterly)

- [ ] Audit pinned repos — still represent current focus?
- [ ] Update tech stack table — add new, remove stale
- [ ] Refresh contribution graph (1 commit/day minimum via auto-script if needed)
- [ ] Check all links resolve
- [ ] Update "Open To" section

---

## Anti-Patterns (What to Skip)

| Anti-Pattern | Why |
|--------------|-----|
| Visitor counter badges | Zero signal, looks junior |
| Trophy case / achievement lists | Noise, not evidence |
| Dynamic SVG animations | Distracts from content |
| 50+ pinned repos | Dilutes signal, looks unfocused |
| Empty showcase repos | Credibility hit when clicked |
| Generic "I love coding" bio | Wastes prime real estate |
| Outdated tech (jQuery, IE hacks) | Signals stagnation |
| Broken links | Immediate trust loss |

---

## Templates & References

- `templates/profile-readme.md` — Copy, fill brackets, push
- `templates/showcase-readme.md` — Per-repo README template with all required sections
- `templates/repo-topics.json` — Curated topic lists per archetype
- `references/profile-audit-checklist.md` — Quarterly review checklist
- `references/recruiter-scan-simulation.md` — What recruiters actually look for (from hiring manager interviews)

---

## Pitfalls & Fixes

| Pitfall | Fix |
|---------|-----|
| "I have no code to show" | Scaffold 4 repos with excellent READMEs first; add code incrementally. Empty README = fail; good README + TODO = pass. |
| "My real work is private" | Sanitize: remove secrets, generalize configs, keep architecture. Mirror to public showcase. |
| "Topics don't matter" | They do — GitHub search + topic pages are discovery surfaces. 8-12 per repo. |
| "Contribution graph has gaps" | `gh repo create daily-commit --private && cron: daily `git commit --allow-empty -m "daily" && git push`` |
| "Recruiter sees forked repos first" | Hide forks: Settings → Profile → uncheck "Show repositories I've forked" |

---

## Skill Integration

**Load this skill when:**
- User mentions "GitHub profile", "portfolio", "personal branding", "make GitHub professional"
- User is job hunting / consulting / seeking speaking gigs
- Quarterly profile audit requested

**Related skills:**
- `github-auth` — for PAT setup
- `github-pr-workflow` — for showcase repo contribution hygiene
- `writing-plans` — for structuring the content creation plan

---

## Quick Start (One-liner)

```bash
# Create profile + 4 showcase repos with READMEs + topics + pins (manual pin step)
gh repo create $USER --public -d "👋 Hi, I'm <Name> — <Role>"
# Then: push profile README, create 4 repos from showcase template, push, add topics, pin 4
```

---

## Version

1.0 — Created 2026-11-11 from session building `smahud` profile with Antigravity CLI concept generation.