# Speedtest.net API Reference

## Endpoint
```
GET https://www.speedtest.net/api/js/servers?engine=js&limit=2000
```

## Parameters
- `engine=js` — Required, returns JSON format
- `limit=2000` — Max servers to return (default 1000)

## Response Structure (Array of Objects)

```json
{
  "url": "http://speedtest.example.com:8080/speedtest/upload.php",
  "lat": "-7.2575",
  "lon": "112.7521",
  "distance": 1,
  "name": "Surabaya",
  "country": "Indonesia",
  "cc": "ID",
  "sponsor": "ISP Name",
  "id": "69081",
  "preferred": 0,
  "isp_id": "123456",
  "https_functional": 1,
  "host": "speedtest.example.com:8080"
}
```

## Key Fields
- `host` — Hostname with port (may include `.prod.hosts.ooklaserver.net` suffix)
- `url` — Full upload.php URL (extract hostname from here)
- `id` — Ookla server ID (numeric string)
- `sponsor` — ISP/organization name
- `https_functional` — 1 if HTTPS works, 0/absent if not

## Hostname Cleaning
Many hostnames have `.prod.hosts.ooklaserver.net` suffix added by Ookla CDN:
```
speedtest.example.com.prod.hosts.ooklaserver.net:8080
→ speedtest.example.com:8080 (for DNS resolution)
```

Use the cleaned hostname for `socket.getaddrinfo()` resolution.