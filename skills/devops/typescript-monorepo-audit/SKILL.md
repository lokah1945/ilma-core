---
name: typescript-monorepo-audit
description: Production readiness audit for TypeScript/npm monorepos with external API dependencies, catalog synchronization, CLI tooling, and security gates. Covers git sync, dependency audit, test/build/lint gates, live API validation, CLI command verification, documentation claim verification, and vulnerability remediation tracking.
metadata:
  origin: agent
---

# TypeScript Monorepo Production Audit

Use this skill when auditing a TypeScript/npm monorepo (Next.js, worker CLI, shared packages) for production readiness. The audit pattern covers external API dependencies, catalog sync workflows, CLI command surface, and security gates.

## When to Use

- User asks "is this production-ready", "audit this repo", "what breaks in prod" for a TS monorepo
- A monorepo with `apps/*` (web + worker), `packages/*` (shared), external API adapters
- Repo has catalog synchronization, CLI tooling, and npm audit gate
- Need to verify README claims against live reality

## When Not to Use

- Pure libraries without CLI or web surface
- Non-TypeScript projects (use `production-audit` for general case)
- When only CI status is needed (this skill goes deeper: live API, docs claims, vulnerability tracking)

## Audit Protocol

### 1. Git State & Sync

```bash
cd <repo>
git status --short --branch
git fetch origin
git log HEAD..origin/main --oneline
# If behind: git pull origin main
```

**Check:** Clean working tree, up-to-date with origin, no uncommitted secrets.

### 2. Dependency Install & Security Audit

```bash
npm ci                    # Clean install
npm run audit             # MUST return 0 vulnerabilities at high+
npm audit fix             # If vulns exist, attempt fix
npm audit fix --force     # If breaking changes acceptable
```

**Critical:** Track vulnerability counts pre/post fix. Document which packages were upgraded and whether breaking changes occurred.

### 3. Quality Gates (run in order)

```bash
npm test                  # Unit/integration tests - all must pass
npm run typecheck         # TypeScript strict mode - all workspaces
npm run lint              # Lint (tsc or eslint)
npm run build             # Production build (Next.js, etc.)
```

**Record:** Test count, build output (routes, bundle sizes), any warnings.

### 4. Live External API Validation

For each external dependency:

| Dependency | Validation Command | Expected |
|------------|-------------------|----------|
| Official MCP Registry | `npm run providers:check -- --search <term>` | HTTP 200, valid JSON |
| Glama API | `npm run providers:sync-glama -- --check --first 100` | HTTP 200 or 401 (key required) |
| MCPMarket | `npm run providers:mcpmarket-status` | Status message, no bypass |
| npm registry | `npm run library:check-packages` | Pinned versions current |

**Key:** Test read-only first (`--check` flags). Never write/mutate in audit.

### 5. CLI Command Verification

Run every public CLI command documented in README:

```bash
npm run worker:help              # Lists all commands
npm run providers:keys           # Credential presence matrix
npm run library:list             # Catalog snapshot
npm run library:free             # Free-filtered catalog
npm run library:packs            # Pack definitions
npm run library:check-packages   # npm version check
npm run library:status           # Clone manifests
```

**Verify:** Each command exits 0, produces expected output format, no crashes.

### 6. Documentation Claim Verification

Cross-reference every claim in README.md against reality:

| README Claim | Verification Method | Status |
|--------------|---------------------|--------|
| "X tests passed" | `npm test` count | ✅/❌ |
| "0 audit vulnerabilities" | `npm run audit` | ✅/❌ |
| "Build passed" | `npm run build` | ✅/❌ |
| "Glama: No credential required" | Live API test | ❌ (now requires key) |
| "Download tools-0..7.xml" | Check live sitemap.xml | ❌ (now tools-0..12) |
| "Version X.Y.Z" | package.json + CHANGELOG | ✅/❌ |

**Flag:** Any mismatch as documentation debt.

### 7. Security & Credential Hygiene

- `.env` / `library.api.key` / `.env.local` are gitignored
- `.env.example` / `library.api.key.example` have only placeholders
- `git ls-files` shows no secret files
- No tokens in commit history (check `git log --all --full-history -- "**/.env*"`)

### 8. Vulnerability Remediation Tracking

Maintain a findings table:

| Package | Severity | CVE/GHSA | Fixed In Version | Breaking? | Evidence |
|---------|----------|----------|------------------|-----------|----------|
| next | Critical | GHSA-p293-qw3h-jr36 | 16.4.6 | No | npm audit |
| zod | High | GHSA-mrhx-c7xc-m3w5 | 4.6.7 | API compat | npm audit |
| vitest | Critical | GHSA-5gmw-xhrv-c9v3 | 4.1.12 | Config change | npm audit |

**Rule:** Never ship with critical/high vulns. Document every fix.

## Scoring

| Band | Score | Criteria |
|------|-------|----------|
| Blocked | 0-49 | Critical vulns, failing tests, broken build, auth missing |
| Risky | 50-69 | High vulns, docs mismatches, missing live API validation |
| Launchable With Caveats | 70-84 | All gates pass, minor docs debt, all external APIs validated |
| Strong | 85-100 | All gates pass, 0 vulns, docs match reality, full CLI verified |

**Cap at 69 if:** Any critical/high vuln unfixed, auth missing on sensitive endpoints, no rollback path.
**Cap at 84 if:** CI not green, launch-critical path not E2E tested, docs claims unverified.

## Output Format

```text
TS Monorepo Audit: 92/100, strong — 0 vulns, 33 tests pass, build OK, all CLI verified, Glama key documented, MCPMarket sitemap corrected.

Blockers: (none)

High-value fixes:
- Add LICENSE file (public repo without license)
- Decide on arena/ branch merge (security model violation)
- Add eslint/prettier beyond tsc-only lint

Evidence checked:
- git status, log, diff
- npm ci, audit, test, typecheck, lint, build
- providers:check, sync-glama --check, mcpmarket-status, library:list, library:packs
- README.md claim matrix
- AUDIT_REPORT.md (if exists)

Next action: Add LICENSE and resolve arena/ branch.
```

## Pitfalls

- **Trusting README over live test** — Always run the commands; READMEs rot.
- **Ignoring `--check` modes** — They exist for safe validation; use them.
- **Skipping npm audit** — A green CI with 9 vulns is not production-ready.
- **Not verifying CLI commands** — A broken CLI is a broken product for users.
- **Assuming git pull = runtime update** — Running processes may be stale (check `/health` git_commit vs HEAD).
- **Missing external API auth changes** — Providers close public access (Glama 2026-08-26); audit must catch this.
- **Sitemap/endpoint drift** — MCPMarket tools-0..7 became tools-0..12; always check live index.

## References

- `references/mcp-library-audit-2026-11-15.md` — Full audit transcript for mcp_library v0.2.0→0.2.1
- `references/vulnerability-remediation-pattern.md` — Pattern for tracking and fixing npm audit findings
- `references/live-api-validation-pattern.md` — Safe read-only validation of external dependencies
- `references/cli-command-verification.md` — Checklist for verifying every documented CLI command
- `references/docs-claim-verification.md` — Method for cross-referencing README claims against reality

## See Also

- Skill: `production-audit` (general case)
- Skill: `ilma-wrapper-production-audit` (ILMA wrapper services)
- Skill: `security-review`
- Skill: `verification-loop`