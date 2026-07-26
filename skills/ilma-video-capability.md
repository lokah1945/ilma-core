---
name: ilma-video-capability
description: ILMA Video Capability Documentation — Hermes v0.13.0 /video tool for native video understanding on Gemini and multimodal models. Future integration target for ILMA's multimodal capabilities. Medium priority. Auto-trigger for video analysis tasks.
trigger_conditions:
  - "video analysis"
  - "video understanding"
  - "multimodal video"
  - "analyze video"
  - "video content"
category: capability
created: 2026-05-09
hermes_version: v0.13.0
source: hermes-agent /video tool
notes: NOT YET INTEGRATED — awaiting Gemini API key setup
---

# ILMA Video Capability — Hermes v0.13.0 /video Tool

## Status

⚠️ **DOCUMENTED ONLY** — Not yet integrated into ILMA. Requires Gemini API key setup.

## Overview

Hermes v0.13.0 introduces native video understanding via `/video` tool (video_analyze). Works with Gemini and compatible multimodal models.

## CLI Usage

```
/video [url or path]
```

## When to Use

- Video content analysis (not just image frames)
- Motion understanding
- Temporal pattern recognition in video
- Video summarization

## ILMA Integration Status

| Aspect | Status |
|--------|--------|
| Tool available | ✅ In Hermes v0.13.0 |
| ILMA skill | ⚠️ Documented only |
| ILMA capability registry | ✅ Added (video_capability) |
| API key | ❌ Not configured |
| Priority | MEDIUM |

## Integration Steps (When Ready)

1. Get Gemini API key
2. Configure in `~/.hermes/config.yaml`
3. Update ILMA skill
4. Test with sample video
5. Document evidence

## Related Skills

- `vision_analyze` — Image understanding (already in ILMA)
- `ilma-multimodal` — Future multimodal expansion

## Status Timeline

- 2026-05-09: Documented from Hermes v0.13.0 changelog
- Pending: Gemini API key setup