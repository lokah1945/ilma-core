# Shell=True Hardening Reference
**Source:** Phase 15B (2026-05-09) — ILMA security hardening sweep

## Why shell=True Is Dangerous

`subprocess.run(..., shell=True)` spawns `/bin/sh -c "..."`, which means:
- Shell metacharacters (`;`, `|`, `&&`, `||`, `` ` ``, `$()`, `>`, `<`) are interpreted
- Variable expansion (`$VAR`, `${VAR}`) happens
- Command substitution works

**Attack vector:** If any variable in the command string comes from user input or external config, shell injection is possible.

## Conversion Quick Reference

### Type 1: Simple command with string interpolation
```python
# BAD
subprocess.run(f"curl -s {url}", shell=True)

# GOOD
subprocess.run(["curl", "-s", url], shell=False)
```

### Type 2: Command with pipeline fallback
```python
# BAD
subprocess.run("netstat -tuln 2>/dev/null || ss -tuln", shell=True)

# GOOD
result1 = subprocess.run(["netstat", "-tuln"], shell=False, capture_output=True)
if result1.returncode != 0:
    result1 = subprocess.run(["ss", "-tuln"], shell=False, capture_output=True)
```

### Type 3: Shell backticks / command substitution
```python
# BAD
subprocess.run(f"openssl rand -base64 $({length_var})", shell=True)

# GOOD
subprocess.run(["openssl", "rand", "-base64", str(length_var)], shell=False)
```

## Files Hardened (Phase 15)

| File | Instances |
|------|-----------|
| scripts/database/ilma_elasticsearch.py | 2 |
| scripts/database/ilma_mysql.py | 2 |
| scripts/database/ilma_mongodb.py | 1 |
| scripts/database/ilma_postgres.py | 2 |
| scripts/database/ilma_redis.py | 1 |
| scripts/monitoring/ilma_log_aggregator.py | 2 |
| scripts/security/ilma_ssl_check.py | 1 |
| scripts/security/ilma_security_scan.py | 2 |
| scripts/security/ilma_secret_rotation.py | 1 |
| scripts/webdev/ilma_api_server.py | 1 (with allowlist) |
| scripts/webdev/ilma_image_optimizer.py | 2 |
| scripts/github/ilma_github_issue.py | 1 |
| scripts/github/ilma_github_pr.py | 1 |

## Verification Checklist

```bash
grep -rn "subprocess.*shell=True" scripts/database/ scripts/monitoring/ scripts/security/ scripts/webdev/ scripts/github/
python3 -m py_compile scripts/database/*.py
pytest test_projects/phase10_250file_codebase/ --tb=no -q
```