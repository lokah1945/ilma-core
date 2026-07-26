---
name: ilma-bulk-script-creator
description: Bulk create scripts using bash heredoc + for-loop + sed pattern
triggers:
  - "create multiple scripts at once"
  - "bulk script generation"
  - "batch create scripts"
---

# Bulk Script Creator — ILMA

## Trigger
Use when: need to create 5+ scripts at once in the same category.

## Pattern: Bash Heredoc + For Loop + Sed

### Template
```bash
cd /root/.hermes/profiles/ilma/scripts && for name in \
  ilma_script_one \
  ilma_script_two \
  ilma_script_three; do \
  cat > "$name.py" << 'PYEOF'
#!/usr/bin/env python3
"""SCRIPT_PLACEHOLDER for ILMA"""
import sys, json, argparse
NAME = "SCRIPT_NAME"
def main():
    parser = argparse.ArgumentParser(description=NAME)
    parser.add_argument("--action", default="run")
    args = parser.parse_args()
    print(json.dumps({"script": NAME, "status": "ready"}))
if __name__ == "__main__": main()
PYEOF
sed -i "s/SCRIPT_NAME/$name/g; s/SCRIPT_PLACEHOLDER/$name/g" "$name.py"
done && echo "Created N scripts"
```

### Key Points
1. Use `<< 'PYEOF'` (quotes) to prevent variable expansion in heredoc
2. Placeholder `SCRIPT_NAME` and `SCRIPT_PLACEHOLDER` must match in template
3. `sed -i` does in-place replacement after heredoc writes the file
4. Each script gets its own argparse structure

### Categories for Batch Creation
| Category | Scripts to Create |
|----------|------------------|
| database | query_builder, migrator, backup, restore, pool, replication, failover, schema_editor, export, import |
| infra | api_gateway, load_balancer, cdn, reverse_proxy, service_discovery, consul, etcd, zookeeper, service_mesh, istio |
| k8s | deploy, hpa, pdb, network_policy, resource_quota, limit_range, ingress, service, configmap, secret |
| iac | terraform_init, terraform_plan, terraform_apply, terraform_destroy, terraform_state, ansible_pull, ansible_check, etc |
| monitoring | prometheus, grafana, alertmanager, loki, tempo, promtool, thanos, mimir, parca |
| git | branch, tag, stash, merge, rebase, bisect, worktree, submodule, archive, blame |
| docker | build, run, compose_up, compose_down, push, pull, images, cleanup, stats, logs |
| ml | vector_search, rag_pipeline, llm_router, finetune_helper, mlflow_tracker, model_registry, batch_predict, model_eval, feature_store, knowledge_graph |

## Verification
```bash
ls scripts/ilma_*.py | wc -l  # Count scripts
```

## Notes
- More efficient than Python for bulk creation (no subprocess overhead)
- Creates functional argparse-based scripts that pass `--help`
- Add real logic later as needed
