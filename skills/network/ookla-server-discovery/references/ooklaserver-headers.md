# OoklaServer HTTP Headers Reference

## Required Headers for "It worked!" Response

| Header | Value | Notes |
|--------|-------|-------|
| `Host` | `<domain>:8080` | **MUST include port**, e.g., `surabaya.trisuladata.net.id:8080` |
| `User-Agent` | Any valid UA | `curl/7.88.1` works |
| `Accept` | `*/*` | Standard |

## Headers That Cause Failure

| Header | Result |
|--------|--------|
| `Host: <IP>` | 500 Internal Server Error or timeout |
| `Host: <domain>` (no port) | 500 or redirect |
| Missing `Host` | 500 minimal response |

## Success Response Headers

```
HTTP/1.1 200 OK
Date: <GMT date>
Connection: Keep-Alive
Cache-Control: no-store
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Strict-Transport-Security: max-age=762542; includeSubDomains
Content-Security-Policy: default-src 'none'; frame-ancestors 'none'; script-src 'none'; object-src 'none'; connect-src *.ookla.com *.speedtest.net *.speedtestcustom.com; upgrade-insecure-requests
Content-Type: text/html
Content-Length: 109
```

## Body (Exact)
```html
<html><head><title>OoklaServer</title></head><body><h1>OoklaServer</h1><p>It worked!<br /></p></body></html>
```

## IPv6 Connection Format
```python
sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
sock.connect((ipv6_addr, port, 0, 0))  # (address, port, flowinfo, scopeid)
```

## Common Redirect (307)
When accessing via IPv6 address directly in Host header:
```
HTTP/1.1 307 Temporary Redirect
Location: https://<domain>:8080/
```
This means the server validates Host against certificate SANs.