# Git Init on Production Deploy — ShankaraWell Pattern (2026-10-31)

**Scenario:** Project deployed via tarball/chat artifact, no source repo on VPS. Need to initialize git, commit essential files, push to private GitHub repo.

---

## Context

- **Host:** 172.16.103.253 (YAPSIDarussalam), SSH alias `yapsi`
- **Project:** `/var/www/shankarawell`
- **Deploy:** Tarball → `/var/www/shankarawell/standalone/` (Next.js standalone output)
- **No source repo on VPS** — only build artifacts
- **Goal:** Version control for docs, scripts, config (NOT node_modules, .next, standalone builds)

---

## Step-by-Step

### 1. Init at Project Root (Parent of Standalone)

```bash
ssh yapsi "cd /var/www/shankarawell && git init"
```

### 2. Create `.gitignore` for Next.js Standalone Deploy

```bash
ssh yapsi "cat > /var/www/shankarawell/.gitignore << 'EOF'
# dependencies
node_modules/
.pnp
.pnp.js

# testing
coverage/

# next.js
.next/
out/
build/

# production
dist/

# standalone builds (tarball artifacts - large, regenerated on deploy)
standalone/
standalone.prev/

# misc
.DS_Store
*.pem

# debug
npm-debug.log*
yarn-debug.log*
yarn-error.log*

# local env files
.env*.local
.env

# vercel
.vercel

# typescript
*.tsbuildinfo
next-env.d.ts

# IDE
.idea/
.vscode/
EOF"
```

### 3. Stage & Commit Essential Files Only

```bash
ssh yapsi "cd /var/www/shankarawell && git add .gitignore UNIT.md start.sh && git -c user.email='deploy@yapsidarussalam.or.id' -c user.name='YAPSI Deploy Bot' commit -m 'chore: init repo with documentation and start script'"
```

**Commits:**
- `.gitignore` — excludes standalone builds, node_modules, .next, env files
- `UNIT.md` — full runbook (architecture, deploy, rollback, port mapping)
- `start.sh` — production start script (`cd standalone && PORT=4080 node server.js`)

**NOT committed:**
- `standalone/` (14MB+ build artifacts)
- `standalone.prev/` (previous build for rollback)
- `node_modules/` (regeneratable)
- `.next/` (build output)
- `.env` (secrets)

### 4. Rename Branch to `main`

```bash
ssh yapsi "cd /var/www/shankarawell && git branch -m main"
```

### 5. GitHub Remote & Push (PAT Auth)

**Option A: gh CLI (if authenticated)**
```bash
ssh yapsi "gh auth login --with-token < /root/credential/pat_lokah1945"
ssh yapsi "cd /var/www/shankarawell && gh repo create lokah1945/LandingPage_Shankara --private --source=. --push"
```

**Option B: Direct HTTPS with PAT (fallback when gh not available)**
```bash
# Get PAT from credential store
PAT=$(cat /root/credential/github.pat.json | grep lokah1945 | cut -d' ' -f2)

# Add remote with embedded token
ssh yapsi "cd /var/www/shankarawell && git remote add origin https://${PAT}@github.com/lokah1945/LandingPage_Shankara.git"

# Push
ssh yapsi "cd /var/www/shankarawell && git push -u origin main"
```

---

## Key Patterns for Tarball-Deploys

| Pattern | Why |
|---|---|
| Init at **parent** of `standalone/` | Keeps repo clean; build artifacts excluded via `.gitignore` |
| Commit only **docs + scripts + config** | Build artifacts are regenerated; source lives elsewhere |
| Use **dedicated deploy user** in commits | Audit trail: `YAPSI Deploy Bot` |
| **PAT in remote URL** as fallback | gh CLI may not be authenticated on target VPS |
| Private repo `LandingPage_<Name>` | Consistent naming with existing `LandingPage_YAPSI` |

---

## Verification

```bash
ssh yapsi "cd /var/www/shankarawell && git log --oneline -5 && git status && git ls-files"
```

**Expected:**
- 3 files tracked (`.gitignore`, `UNIT.md`, `start.sh`)
- `standalone/` and `standalone.prev/` in untracked (correct)
- Clean working tree

---

## Related Audit

See `vps-project-deep-audit/references/2026-10-31-shankarawell-audit.md` for full context — architecture, findings, and recommendations including git remote setup as P0.

---

## Reusable Template

For future tarball-deployed projects:

```bash
# 1. Find project root
PROJECT_ROOT="/var/www/<project-name>"

# 2. Init
cd "$PROJECT_ROOT" && git init

# 3. .gitignore (adapt for framework)
cat > .gitignore << 'EOF'
# framework-specific build outputs
.next/
out/
build/
dist/
standalone/
standalone.prev/
# etc.
EOF

# 4. Add essential files
git add .gitignore <docs> <scripts> <config>

# 5. Commit
git -c user.email='deploy@domain' -c user.name='Deploy Bot' commit -m 'chore: init repo'

# 6. Branch
git branch -m main

# 7. Remote + push (PAT)
PAT=$(get_pat_for_owner)
git remote add origin "https://${PAT}@github.com/<owner>/<repo>.git"
git push -u origin main
```

---

## Credential Note

PAT stored in `/root/credential/github.pat.json` (JSON format):
```json
{
  "lokah1945": "github_pat_...",
  "smahud": "github_pat_..."
}
```
**lokah1945** has existing `LandingPage_YAPSI` repo → use this account for `LandingPage_Shankara`.

---

## Multi-Account PAT Selection & API Repo Creation (Extended 2026-10-31)

When the target account is determined by existing `LandingPage_*` pattern:

```bash
# 1. Check which account owns LandingPage_* repos
for acct in lokah1945 smahud; do
  TOKEN=$(cat /root/credential/github.pat.json | grep $acct | sed 's/.*: "//; s/".*//')
  count=$(curl -s -H "Authorization: token $TOKEN" \
    https://api.github.com/users/$acct/repos?per_page=100 | grep -c "LandingPage_")
  echo "$acct: $count"
done
# Result: lokah1945=1 (LandingPage_YAPSI), smahud=1 (LandingPage_JIPOSNET)
# Bos directed: use smahud

# 2. Verify token scope (classic PAT needs 'repo'; fine-grained needs Contents:R/W)
TOKEN=$(cat /root/credential/github.pat.json | grep smahud | sed 's/.*: "//; s/".*//')
curl -s -I -H "Authorization: token $TOKEN" https://api.github.com/user | grep -i "x-oauth-scopes"

# 3. Create repo via REST API (gh CLI not available)
curl -s -X POST -H "Authorization: token $TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/user/repos \
  -d '{"name":"LandingPage_Shankara","private":true,"description":"Shankara Wellness & Sanctuary — Landing Page (Next.js standalone)"}'

# 4. Push with PAT-embedded remote
ssh yapsi "cd /var/www/shankarawell && git remote add origin https://${TOKEN}@github.com/smahud/LandingPage_Shankara.git && git push -u origin main"
```

**Key Learnings:**
- Token in `/root/credential/github.pat.json` must be FULL (not truncated with `...`)
- Classic PAT: check `X-OAuth-Scopes` header for `repo`
- Fine-grained PAT: check `X-Accepted-OAuth-Scopes` and repository permissions
- REST API `POST /user/repos` works without gh CLI
- PAT in remote URL = reliable push when credential helper not configured