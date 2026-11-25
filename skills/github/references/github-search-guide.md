# GitHub Search Capability Guide — Session Reference

Generated from session: 2026-11-25
Context: User asked "Sejauh apa anda bisa mencari di github public repo dan semua isi nya" (How far can you search in GitHub public repos and all their contents?)

## Summary of Search Depth

| Content Type | Searchable Via | Depth | Limitations |
|--------------|----------------|-------|-------------|
| **Source code** | `gh search code`, REST API `/search/code` | Full file contents (default branch only) | ≤384KB files, default branch only, no forks by default |
| **Repository metadata** | `gh search repos`, REST API `/search/repositories` | Name, description, topics, stars, forks, language, license, visibility | No README/content search |
| **Issues & PRs** | `gh search issues`, REST API `/search/issues` | Titles, bodies, comments, labels, assignees, states | PRs included in issues endpoint |
| **Commits** | `gh search commits`, REST API `/search/commits` | Messages, authors, dates | No diff content search |
| **Users/Orgs** | `gh search users`, REST API `/search/users` | Profiles, locations, followers, repo counts | Limited fields |

## What CAN Be Searched Deeply

1. **Code patterns across public repos** — `gh search code "pattern" --language python --limit 100`
2. **Repos by criteria** — `gh search repos "topic:ml stars:>1000 language:python"`
3. **Security patterns (authorized)** — `gh search code "api_key" --owner org --json path,repository`
4. **Dependency usage** — `gh search code "requirements.txt" "torch" --language python`
5. **Workflow files** — `gh search code "path:.github/workflows" --owner myorg --filename "*.yml"`

## What CANNOT Be Searched via API

- All branches (only default branch indexed)
- Commit diffs/history (only messages)
- Wiki/Pages content
- Releases/assets metadata
- Discussions
- Packages/Container registry
- Private repos (without token)
- Full org-wide search in one call (must paginate per repo)

## Best Practice for Deep Audits

```bash
# 1. Discover targets via API
gh search repos "criteria" --limit 20

# 2. Clone for full history
git clone https://github.com/owner/repo.git

# 3. Local deep search (all branches, all history)
rg "pattern"
git log --all --oneline --grep="pattern"
git log --all -p --grep="pattern"

# 4. Cross-repo patterns via API
gh search code "pattern" --language python --limit 100
```

## Rate Limits

| Auth Status | Limit |
|-------------|-------|
| Authenticated (token) | 30 req/min |
| Unauthenticated | 10 req/min |

## Related Skills in AgentEnhancements

- `oss-hunter` — Hunt popular OSS repos via `gh api search/repositories`
- `web2-recon` — Security recon via `gh search code` for secrets
- `skill-scout` — Find skills via `gh search code "name: keyword" --filename SKILL.md`
- `github-automation` — Rube MCP / Composio toolkit for programmatic ops