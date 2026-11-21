# Quarterly GitHub Profile Audit Checklist

Run this checklist every quarter (or before job search / consulting push).

---

## 1. Profile Repo (`<username>/<username>`)

- [ ] **README renders correctly** — no broken images, links resolve
- [ ] **Headline matches current focus** — update if role/focus shifted
- [ ] **Executive Overview** — still accurate? 2-3 sentences max
- [ ] **Core Focus Areas** — 3-4 domains, keywords current?
- [ ] **Tech Stack Table** — add new tech, remove stale (haven't used in 12+ months)
- [ ] **Pinned Repos section** — points to correct 4 repos?
- [ ] **GitHub Stats badges** — rendering? (vercel.app sometimes flaky)
- [ ] **Open To section** — matches current availability?
- [ ] **Contact links** — LinkedIn, email, blog all resolve?
- [ ] **Profile repo topics** — 6-8 relevant topics set?

---

## 2. Pinned Repos (4 showcase)

For each of the 4 pinned repos:

- [ ] **README exists** — comprehensive (architecture, quick start, config, topics)
- [ ] **Description (repo settings)** — 1 sentence, outcome-oriented
- [ ] **Topics** — 8-12 set, matching archetype
- [ ] **Architecture diagram** — ASCII or Mermaid, renders on GitHub
- [ ] **Quick start** — runnable (docker / make / pip)
- [ ] **Configuration table** — env vars / config keys documented
- [ ] **Code present** — at least scaffold / core module (not empty)
- [ ] **CI badge** — GitHub Actions workflow passing (lint/test/build)
- [ ] **Releases** — at least 1 tagged release with changelog
- [ ] **Discussions enabled** — for flagship repos
- [ ] **Issues templates** — bug report, feature request
- [ ] **License** — MIT/Apache-2.0 present
- [ ] **Contributing guide** — even minimal

---

## 3. Supporting Repos

- [ ] `dotfiles` — clean, install script works, README explains philosophy
- [ ] `snippets` — 10-15 useful scripts, each with 1-line purpose comment

---

## 4. Profile Settings

- [ ] **Public contributions visible** — Settings → Profile → ✅ "Show private contributions"
- [ ] **Forks hidden** — Settings → Profile → ❌ "Show repositories I've forked"
- [ ] **Organizations** — relevant ones public, irrelevant private
- [ ] **Sponsors button** — enabled if open to sponsorship
- [ ] **Status** — not set to "busy/away" indefinitely

---

## 5. Discovery & SEO

- [ ] **GitHub search** — search your username, top results are your profile + 4 pins
- [ ] **Topic pages** — your repos appear on relevant topic pages (e.g., `github.com/topics/vllm`)
- [ ] **Google** — search `"<name> GitHub"` → profile ranks #1

---

## 6. Content Freshness

- [ ] **Last commit** — profile repo < 30 days ago
- [ ] **Last commit** — each flagship repo < 60 days ago
- [ ] **Blog post** — 1 technical post last quarter, linked from profile
- [ ] **Contribution graph** — no gaps > 7 days (auto-script if needed)

---

## 7. Recruiter Scan Simulation (30 seconds)

Open profile in incognito, timer 30s:

| Time | Check | Pass? |
|------|-------|-------|
| 0-3s | Name, headline, avatar professional? | ☐ |
| 3-8s | Executive overview — understand what you do? | ☐ |
| 8-15s | 4 pins — each has clear description + topics? | ☐ |
| 15-22s | Click 1 pin — README has architecture + quick start? | ☐ |
| 22-27s | Tech stack table — scan domains, recognize keywords? | ☐ |
| 27-30s | Contact info — easy to reach? | ☐ |

**If any ☐ = action item for next quarter.**

---

## 8. Metrics to Track

| Metric | Target | Current |
|--------|--------|---------|
| Profile repo stars | > 50 | |
| Each flagship repo stars | > 20 | |
| Profile views (30d) | > 200 | |
| Repo clones (30d, flagship) | > 50 | |
| Inbound messages (quarter) | > 5 | |

---

## Quick Commands

```bash
# Check repo topics
for repo in profile-repo repo1 repo2 repo3 repo4; do
  gh repo view $USER/$repo --json repositoryTopics
done

# Check last commit dates
for repo in profile-repo repo1 repo2 repo3 repo4; do
  gh api repos/$USER/$repo/commits --jq '.[0].commit.author.date'
done

# Verify all links in profile README
# (manual: open README in browser, click each link)
```

---

## Version History

| Date | Change |
|------|--------|
| 2026-11-11 | Created from smahud profile build session |