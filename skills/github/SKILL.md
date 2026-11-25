---
name: github
description: "Comprehensive GitHub operations — search, issues, PRs, code review, automation, and repo management via gh CLI, REST API, and MCP integrations."
version: 2.0.0
author: ILMA
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [GitHub, Search, Issues, Pull-Requests, Code-Review, Automation, API, MCP]
    related_skills: [github-auth, github-issues, github-code-review, github-pr-workflow, github-repo-management, search-first]
---

# GitHub Operations — Class-Level Skill

This skill covers the full spectrum of GitHub interactions available to ILMA. It serves as the central hub routing to specialized sub-skills and provides the search command reference.

## When to Use

- Searching public repositories, code, issues, commits, users
- Creating/managing issues and pull requests
- Code review workflows (local and remote)
- Repository automation via API or MCP
- Any task requiring GitHub as a data source or mutation target

## Authentication

**Always run auth detection first** — see `github-auth` skill for full setup.

```bash
# Quick detection
if command -v gh &>/dev/null && gh auth status &>/dev/null; then
  AUTH_METHOD=gh
elif [ -n "$GITHUB_TOKEN" ] || grep -q "github.com" ~/.git-credentials 2>/dev/null; then
  AUTH_METHOD=curl
else
  echo "NO AUTH — run github-auth setup first"
fi
```

## Search Capabilities (Core)

### GitHub CLI (`gh search`)

| Target | Command | Key Options |
|--------|---------|-------------|
| **Code** | `gh search code "query" [--owner org] [--repo owner/repo] [--language lang] [--filename pattern] [--limit N]` | Searches default branch only |
| **Repositories** | `gh search repos "query" [--stars >N] [--pushed >date] [--language lang] [--topic topic] [--limit N]` | Name, description, topics |
| **Issues/PRs** | `gh search issues "query" [--repo owner/repo] [--state open/closed/all] [--label label] [--assignee user] [--author user] [--limit N]` | Includes PRs by default |
| **Commits** | `gh search commits "query" [--repo owner/repo] [--author user] [--committer user] [--since date] [--until date] [--limit N]` | Commit messages |
| **Users** | `gh search users "query" [--location loc] [--followers >N] [--repos >N] [--limit N]` | Profiles and orgs |

### REST API (`curl` fallback)

```bash
# Code search
curl -s -H "Authorization: token $GITHUB_TOKEN" \
  "https://api.github.com/search/code?q=QUERY+repo:OWNER/REPO+language:python&per_page=100"

# Repository search
curl -s -H "Authorization: token $GITHUB_TOKEN" \
  "https://api.github.com/search/repositories?q=stars:>1000+language:go&per_page=100"

# Issues search
curl -s -H "Authorization: token $GITHUB_TOKEN" \
  "https://api.github.com/search/issues?q=repo:OWNER/REPO+is:issue+label:bug&per_page=100"
```

### Search Constraints (Critical)

| Limit | Value |
|-------|-------|
| Rate limit (auth) | 30 req/min |
| Rate limit (unauth) | 10 req/min |
| Max results | 1,000 (paginated 100/page) |
| Query length | 256 chars |
| File size indexed | ≤ 384 KB |
| Branches indexed | Default branch only |
| Forks indexed | No (use `fork:true`) |

## Sub-Skills (Route to These for Specialized Work)

| Skill | Purpose |
|-------|---------|
| `github-auth` | Authentication setup (HTTPS token, SSH, gh CLI) |
| `github-issues` | Issue lifecycle: create, triage, label, assign, close, bulk ops |
| `github-code-review` | Local diff review + PR review with inline comments |
| `github-pr-workflow` | PR lifecycle: create, review, checks, merge, branch management |
| `github-repo-management` | Repo settings, collaborators, branch protection, webhooks |
| `github-automation` | Rube MCP / Composio toolkit for programmatic ops (AgentEnhancements) |
| `oss-hunter` | Hunt popular OSS repos (AgentEnhancements) |
| `web2-recon` | Security recon via code search (AgentEnhancements) |
| `skill-scout` | Find skills across repos via `gh search code` (AgentEnhancements) |

## MCP Integrations

- **GitHub MCP Server** — Managed agents (GitHub Copilot): `https://api.githubcopilot.com/mcp/`
- **Rube MCP** — Composio GitHub toolkit (via `github-automation` skill)
- **github-issues-mcp** — Issue-specific MCP server

## Deep Search Workflow (Best Practice)

For comprehensive audits requiring full history/branch coverage:

```bash
# 1. Discover target repos
gh search repos "topic:ml language:python stars:>100" --limit 20

# 2. Clone locally for full branch history
git clone https://github.com/owner/repo.git
cd repo

# 3. Local deep search (all branches, all history)
rg "pattern"                    # ripgrep - fast
git log --all --oneline --grep="pattern"  # commit messages
git log --all -p --grep="pattern"         # commit diffs

# 4. GitHub code search for cross-repo patterns
gh search code "pattern" --language python --limit 100
```

## Common Patterns

### Find all workflow files in an org
```bash
gh search code "path:.github/workflows" --owner myorg --filename "*.yml"
```

### Find potential secrets (authorized only)
```bash
gh search code "api_key" --owner myorg --json path,repository
gh search code "password" --owner myorg --json path,repository
```

### Find repos by dependency
```bash
gh search code "requirements.txt" "torch" --language python --limit 50
gh search code "package.json" "\"react\"" --language json --limit 50
```

## Failure Rules

- **Re-resolve tool schemas** when Rube/GitHub API reports changed parameters
- **Stop on**: repository ambiguity, stale SHA, missing permissions, incomplete pagination, inconclusive protection state
- **Never bypass**: required checks, reviews, merge queues, maintainer commands, branch protection
- **Never claim success** without reading resulting remote state

## References

- `references/git-sync-workflow-2026-05-17.md` — Git sync workflow
- `references/git-sync-workflow-2026-06-02.md` — Updated git sync workflow
- `references/github-search-guide.md` — This session's search capability summary
- `references/github-api-cheatsheet.md` — Quick API reference

## Limitations

- Code search only indexes default branch
- No full-text search across all branches in one API call
- Private repos require token with `repo` scope
- Discussions, releases, packages, wikis need separate API endpoints
- Forks excluded from search index by default