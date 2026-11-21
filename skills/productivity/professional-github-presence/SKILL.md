---
name: professional-github-presence
description: Create production-grade GitHub profiles with curated showcase repositories that signal senior engineering competence
category: productivity
tags: [github, profile, showcase, career, devops, portfolio]
---

# Professional GitHub Presence — Profile & Showcase Repos

**Class-level skill** for creating production-grade GitHub profiles with curated showcase repositories that signal senior engineering competence.

## When to Use

- User wants to build/refresh GitHub profile for job search, consulting, or credibility
- User needs multiple showcase repos demonstrating end-to-end depth across domains
- User wants professional presentation (not tutorial/starter code)

## Core Workflow

```
1. ANALYZE USER STACK & FOCUS
   → Extract: languages, domains, seniority signals, target roles

2. DESIGN PROFILE README (smahud/smahud repo)
   → Executive overview, focus areas, tech stack table
   → Pinned repo strategy (4 repos max, diverse domains)
   → Metrics badges, open-to section, social links

3. SCAFFOLD SHOWCASE REPOS (4 diverse domains)
   → Each repo: production-grade, not starter code
   → Domain diversity: AI/ML infra, Platform/Infra, Backend/Distributed, Applied AI
   → Standard components per repo:
     - Comprehensive README (arch, features, quickstart, config, K8s, monitoring)
     - Source structure with real entry points
     - Dockerfile (multi-stage) + docker-compose
     - Kubernetes manifests (Deployment, Service, HPA, ConfigMap, Secret, RBAC)
     - CI/CD pipeline (lint, test, build, security scan, deploy)
     - Prometheus metrics + Grafana dashboard
     - Tests (unit, integration, contract)
     - Scripts (benchmark, load-test, model-downloader)
     - LICENSE, .gitignore, pyproject.toml/go.mod

4. PUSH & CONFIGURE
   → gh repo create (public, description, topics)
   → git init, commit, push with proper author
   → gh repo edit --add-topic for discoverability
   → Pin 4 repos on profile
   → Enable private contributions visibility

5. VALIDATE
   → gh repo view --json for each repo
   → Verify topics, visibility, README rendering
```

## Domain Templates (Reusable Patterns)

### 1. AI/ML Inference Runtime (Python/FastAPI/vLLM)
- OpenAI-compatible API (chat, completions, embeddings, streaming)
- Tensor/pipeline parallelism, dynamic batching, prefix caching
- Auth (API keys), rate limiting (RPM/TPM), Prometheus metrics
- K8s: HPA, PVC for HF cache, GPU tolerations, priority class

### 2. Kubernetes GitOps Platform (ArgoCD/Terraform/Helm)
- 10+ platform apps: argocd, cert-manager, external-secrets, cilium, istio, monitoring, kyverno
- Workload apps: api-gateway, ml-inference, data layer (postgresql, redis)
- AWS EKS + GCP GKE Terraform modules
- Bootstrap script, production values, network policies, RBAC

### 3. Distributed Event Pipeline (Go/Kafka/ClickHouse)
- Exactly-once consumer with transactional outbox pattern
- ClickHouse OLAP with partitioned tables, TTL, compression
- Redis caching, OpenTelemetry tracing, Prometheus metrics
- DLQ with retry/backoff, adaptive batch processing
- K8s HPA on CPU/memory/lag

### 4. RAG Evaluation Suite (Python)
- 5 datasets: MS MARCO, NQ, HotpotQA, FEVER, custom
- Dense/sparse/hybrid retrieval (FAISS + BM25 + RRF)
- 4 rerankers: cross-encoder, LLM, hybrid, adaptive
- 3 generators: OpenAI, vLLM, local transformers
- Hallucination: self-consistency, entailment (DeBERTa), citation verification

## Anti-Patterns to Avoid

| Anti-Pattern | Why | Fix |
|--------------|-----|-----|
| Starter code only | Looks junior, not production | Full source + deploy + monitor |
| Single-domain repos | Shows narrow expertise | 4 diverse domains |
| Visitor counters/trophy cases | Noise, not signal | Clean, metrics-driven README |
| Private showcase repos | Invisible to recruiters | All public, pinned |
| Placeholder social links | Looks unfinished | Real LinkedIn/email/blog |
| No CI/CD or K8s | Not deployable | Full pipeline + manifests |

## GitHub CLI Commands (Reference)

```bash
# Create profile repo (must match username)
gh repo create smahud --public --description "👋 Hi, I'm Huda — Senior Engineer · AI/ML Systems · Infrastructure & Automation"

# Create showcase repos
gh repo create smahud/llm-inference-runtime --public --description "High-throughput LLM inference gateway with vLLM"
gh repo create smahud/kubernetes-gitops-platform --public --description "Production-grade GitOps with ArgoCD + Terraform"
gh repo create smahud/distributed-event-pipeline --public --description "Fault-tolerant streaming: Go + Kafka + ClickHouse"
gh repo create smahud/enterprise-rag-evaluation-suite --public --description "RAG evaluation: retrieval, reranking, hallucination detection"

# Add topics for discoverability
gh repo edit smahud/llm-inference-runtime --add-topic python --add-topic vllm --add-topic llmops --add-topic kubernetes

# Push local repo to GitHub
cd /tmp/repo && git init && git config user.name "Name" && git config user.email "email" && git add . && git commit -m "msg" && git branch -M main && git remote add origin https://github.com/user/repo.git && git push -u origin main

# Verify
gh repo view smahud/repo --json name,description,url,repositoryTopics
```

## Quality Gates (Per Repo)

- [ ] README > 5KB with architecture diagram, config table, quickstart
- [ ] Source compiles/runs (no `// TODO` stubs in entry points)
- [ ] Dockerfile multi-stage, non-root user, healthcheck
- [ ] K8s: Deployment + Service + HPA + ConfigMap + Secret + RBAC
- [ ] CI/CD: lint → test → build → security scan → deploy
- [ ] Prometheus metrics + Grafana dashboard JSON
- [ ] Tests: unit + integration + contract
- [ ] Topics: 8-10 relevant tags
- [ ] LICENSE (MIT), .gitignore, pyproject.toml/go.mod

## Pitfalls Learned

- **Force push needed** when remote has initial README → `git push -u origin main --force`
- **Default branch mismatch** (master vs main) → `git branch -M main` before push
- **Topic limit** → GitHub allows unlimited, but 8-10 is optimal for search
- **Profile repo must be public** and named exactly `username/username`
- **Pinning is manual** → User must pin via GitHub UI after push
- **Antigravity CLI (`agy`)** excellent for generating initial markdown concepts

## References

- `references/profile-readme-template.md` — Base template for profile README
- `references/repo-templates/README.md` — Index of domain starter structures
- `references/gh-cli-cheatsheet.md` — Common gh commands for repo management