# Port Mapping Verification Reference

## Command Template
```bash
# Quick health check for all standard wrapper ports
for port in 9101 9102 9103 9104 9106 9200; do
  curl -s -m5 http://127.0.0.1:$port/health | jq -r '.status // .ok'
done
```

## Port Discovery Session (2026-08-01)

### Actual Ports Found
- **nvidia-python**: 9101
- **nous**: 9102  
- **opencode**: 9103
- **blackbox**: 9104
- **openrouter**: 9106 (**NOT 9105/9107**)
- **model-registry**: 9200

### Health Response Format
```json
{
  "status": "ok" | "degraded",
  "git_commit": "26c98409cb13ee016178ac2fda8d7ae2523f10a2",
  "source_root": "/root/wrapper/<svc>"
}
```

## Common Issues

1. **OpenRouter on 9106**: Legacy docs may say 9105/9107 - always verify
2. **Stuck old process**: If health check fails, check for zombie processes
3. **Port collision**: `ss -tlnp | grep <port>` to see who's listening

## Related
- `ilma-wrapper-production-audit` skill for full audit procedures