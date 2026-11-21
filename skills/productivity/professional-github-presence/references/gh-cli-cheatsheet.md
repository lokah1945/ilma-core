# GitHub CLI Cheatsheet for Repo Management

## Profile Repository
```bash
# Must be named exactly: username/username
gh repo create USERNAME --public --description "Description"
```

## Showcase Repositories
```bash
# Create with description
gh repo create USERNAME/REPO --public --description "Description"

# Create with all options
gh repo create USERNAME/REPO \
  --public \
  --description "Description" \
  --enable-issues \
  --disable-wiki \
  --homepage "https://example.com"
```

## Topics (for discoverability)
```bash
# Add topics (repeat --add-topic for each)
gh repo edit USERNAME/REPO \
  --add-topic python \
  --add-topic vllm \
  --add-topic llmops \
  --add-topic kubernetes \
  --add-topic inference \
  --add-topic triton

# List current topics
gh repo view USERNAME/REPO --json repositoryTopics
```

## Repository Settings
```bash
# Enable/disable features
gh repo edit USERNAME/REPO --enable-projects=false --enable-wiki=false

# Set default branch
gh repo edit USERNAME/REPO --default-branch main

# Add homepage
gh repo edit USERNAME/REPO --homepage "https://docs.example.com"
```

## Repository Info
```bash
# View repo details
gh repo view USERNAME/REPO --json name,description,url,repositoryTopics,isPrivate,stargazerCount,forkCount

# List user repos
gh repo list USERNAME --limit 20 --json name,description,url,repositoryTopics
```

## Push Local Repo to GitHub
```bash
# Initialize and push
cd /path/to/local/repo
git init
git config user.name "Your Name"
git config user.email "you@example.com"
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/USERNAME/REPO.git
git push -u origin main

# Force push if remote has different history
git push -u origin main --force
```

## Pin Repositories (Manual - via UI)
1. Go to https://github.com/USERNAME
2. Click "Customize your pins"
3. Select up to 6 repositories
4. Save

## Enable Private Contributions (Manual - via UI)
1. Settings → Profile
2. Check "Show my private contributions on my profile"
3. Save

## Clone with gh
```bash
# HTTPS
gh repo clone USERNAME/REPO

# SSH
gh repo clone USERNAME/REPO --ssh

# Specific directory
gh repo clone USERNAME/REPO my-directory
```

## Create Repo from Template
```bash
gh repo create USERNAME/NEW-REPO --template OWNER/TEMPLATE-REPO --public
```

## Delete Repository
```bash
gh repo delete USERNAME/REPO --confirm
```

## Useful Aliases (add to ~/.bashrc or ~/.zshrc)
```bash
alias ghpr='gh repo list'
alias ghpc='gh repo create'
alias ghpv='gh repo view'
alias ghpe='gh repo edit'
alias ghpp='gh repo clone'
```