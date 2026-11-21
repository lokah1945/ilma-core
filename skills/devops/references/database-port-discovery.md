# Database Non-Standard Port Discovery Evidence

## Session Context: 2026-08-04
**Target**: 172.16.103.253
**Finding**: MariaDB/MySQL running on port 33445 (non-standard)

## Evidence Chain

### 1. Initial Standard Port Test
```text
Port 3306: ❌ CLOSED/TIMEOUT
```
Standard MySQL port blocked → suspected non-standard port usage

### 2. Port Inference Logic
- Server responds to ping (0.3ms latency)
- Web server (80/443) accessible
- SSL certificate on port 7080: `*.yapsidarussalam.or.id`
- Database must be on alternate port

### 3. Port Discovery Commands
```bash
# TCP connectivity test
timeout 5 bash -c "echo >/dev/tcp/172.16.103.253/33445" && echo "OPEN" || echo "CLOSED"

# Service banners (requires SSH)
nc -zv 172.16.103.253 33445
```

### 4. Result
```text
Port 33445: ✅ OPEN
✅ MySQL/MariaDB Port 33445: OPEN
```

## Key Pattern: Port Inference for Internal Services

1. **When standard port (3306) unreachable** → scan common alternatives: 3307, 33445, 3406
2. **Use TCP connectivity test**: `timeout 5 bash -c "echo >/dev/tcp/HOST/PORT"`
3. **Combine with HTTP enumeration** to identify web stack
4. **Evidence**: Document port + certificate details for service fingerprinting

## Next Steps
- SSH access required for credential discovery
- Check: `/etc/mysql/my.cnf`, `/etc/my.cnf` for port config
- Service status: `systemctl status mysql mariadb`