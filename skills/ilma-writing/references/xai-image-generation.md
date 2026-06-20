# xAI grok-imagine-image — API Reference

## Endpoint
```
POST https://api.x.ai/v1/images/generations
```

## Auth
```bash
Authorization: Bearer xai-5VrEpG7KONn...
```

## Valid Parameters (ONLY these — 400 error if others added)
| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `model` | string | ✅ | Always `grok-imagine-image` |
| `prompt` | string | ✅ | Image description |
| `n` | integer | ❌ | Default 1, max varies |

## INVALID Parameters (causes 400 error)
- `size` — NOT supported by xAI
- `style` — NOT supported by xAI
- `response_format` — NOT supported
- `quality` — NOT supported

## Working Python Call
```python
import urllib.request, json

req = urllib.request.Request(
    'https://api.x.ai/v1/images/generations',
    data=json.dumps({
        'model': 'grok-imagine-image',
        'prompt': 'your image description',
        'n': 1
    }).encode(),
    headers={
        'Content-Type': 'application/json',
        'Authorization': 'Bearer xai-5VrEpG7KONn...'
    },
    method='POST'
)

with urllib.request.urlopen(req, timeout=60) as resp:
    result = json.loads(resp.read())
    image_url = result['data'][0]['url']
```

## Response Shape
```json
{
  "created": 1719000000,
  "data": [
    {
      "url": "https://imgen.x.ai/xai-imgen/xai-tmp-imgen-xxxx.jpeg"
    }
  ]
}
```

## Cost
- $0.0002 per image (extremely cheap)
- 1024x1024 default resolution

## Provider Priority
1. **xAI grok-imagine-image** — Primary (no size/style support)
2. **OpenAI DALL-E 3** — Fallback (Bos key may be invalid: 401)
3. **fal.ai Flux** — Final fallback

## Notes
- xAI returns JPEG URLs that expire — download immediately
- No aspect ratio control — only 1k default square
- If OpenAI key returns 401, always use xAI as primary