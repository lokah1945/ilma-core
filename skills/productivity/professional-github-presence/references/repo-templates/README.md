# Domain Repo Templates

This directory contains starter structures for each showcase domain. Each template is a complete production-grade scaffold — not starter code.

## Directory Structure

```
repo-templates/
├── ai-ml-inference-runtime/      # Python/FastAPI/vLLM
│   ├── src/
│   ├── tests/
│   ├── k8s/
│   ├── configs/
│   ├── scripts/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── pyproject.toml
│   ├── requirements.txt
│   ├── README.md
│   └── .github/workflows/ci-cd.yml
├── kubernetes-gitops-platform/   # ArgoCD/Terraform/Helm
│   ├── apps/
│   ├── clusters/
│   ├── infra/
│   ├── bootstrap/
│   └── README.md
├── distributed-event-pipeline/   # Go/Kafka/ClickHouse
│   ├── cmd/
│   ├── pkg/
│   ├── configs/
│   ├── deployments/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── Makefile
│   ├── go.mod
│   └── README.md
└── enterprise-rag-evaluation/    # Python RAG eval
    ├── src/
    ├── tests/
    ├── configs/
    ├── scripts/
    ├── Dockerfile
    ├── docker-compose.yml
    ├── pyproject.toml
    ├── requirements.txt
    └── README.md
```

## Usage

```bash
# Copy template and customize
cp -r repo-templates/ai-ml-inference-runtime /tmp/my-inference-runtime
cd /tmp/my-inference-runtime
# Edit README.md, configs, source code for your stack
# Then push to GitHub
```

## Customization Checklist Per Template

- [ ] Update README: project name, description, your handle
- [ ] Update Dockerfile: base image, version pins
- [ ] Update pyproject.toml/go.mod: module name, dependencies
- [ ] Update K8s manifests: namespace, image repo, resource limits
- [ ] Update CI/CD: registry, secrets, deploy targets
- [ ] Update Grafana dashboard: service name, metrics prefixes
- [ ] Update scripts: model names, endpoints, parameters
- [ ] Add your specific business logic to src/