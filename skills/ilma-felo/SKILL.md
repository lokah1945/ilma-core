---
name: ilma-felo
description: "ILMA Felo AI SuperAgent Integration — multi-turn persistent sessions, LiveDoc canvas, real-time search, and 11 Felo skills. Use when task involves planning, research synthesis, knowledge base, content extraction, or media generation. Handles SuperAgent thread state, routing, and skill selection."
---

# ILMA Felo SuperAgent Skill

## Overview

Felo AI SuperAgent gives ILMA persistent multi-turn sessions on a LiveDoc canvas, real-time search, and specialized tools for content creation.

**Account:** lokah2150@gmail.com
**API Key:** `<REDACTED-FELO>`
**Env Var:** `FELO_API_KEY`
**LiveDoc:** `YfxkwnggzHQJhtfuoZpEnH` (https://felo.ai/livedoc/YfxkwnggzHQJhtfuoZpEnH)
**Current Thread:** `n6hNbX6pndftTYi6xcxqBS` (renewed 2026-05-08 — old thread `LcotMMYL2M8GKcU6cQ2pRs` expired with "fetch failed")

## When to Use

Use Felo when task matches one of these:

| Task | Skill | Why |
|------|-------|-----|
| Multi-turn planning/research | `felo-superAgent` | Persistent sessions, context continuity |
| Real-time web search | `felo-search` | Live data, news, current events |
| Knowledge base management | `felo-livedoc` | Upload, search, RAG over documents |
| Twitter style + writing | `felo-twitter-writer` | Style DNA extraction, tweet composition |
| URL content extraction | `felo-web-fetch` | Turn URLs into markdown/text |
| YouTube subtitles | `felo-youtube-subtitling` | Caption extraction |
| X/Twitter data search | `felo-x-search` | Tweet/user lookup |
| PPT generation | `felo-slides` | Topic → slide deck |
| URL/YT → PPT | `felo-content-to-slides` | One-step content-to-slides |
| Mindmap | `felo-mindmap` | Topic → visual mindmap |
| Apple product advice | `apple-buy-advisor` | Buying recommendations |

## SuperAgent Thread State

```
Session state file: /root/.hermes/profiles/ilma/config/felo_session_state.json
```

**After EVERY SuperAgent call:** Extract from JSON output:
- `data.thread_short_id` → update session state
- `data.live_doc_short_id` → keep (same LiveDoc)
- `data.live_doc_url` → show to Bos

**Decision rules:**
- First message in session → `--live-doc-id` only (new conversation)
- 2nd+ message (same topic) → `--thread-id` + `--live-doc-id` (follow-up, DEFAULT)
- Bos says "new topic" → `--live-doc-id` only (new thread)
- Bos says "new canvas" → create new LiveDoc first

## Execution

### SuperAgent (PRIMARY — multi-turn)

```bash
export FELO_API_KEY="<REDACTED-FELO>"
LIVE_DOC_ID="YfxkwnggzHQJhtfuoZpEnH"
THREAD_ID=""  # or from session state

# New conversation
node ~/.hermes/skills/felo/felo-superAgent/scripts/run_superagent.mjs \
  --query "USER_QUERY" \
  --live-doc-id "$LIVE_DOC_ID" \
  --accept-language en --json

# Follow-up (DEFAULT after first message)
node ~/.hermes/skills/felo/felo-superAgent/scripts/run_superagent.mjs \
  --query "USER_QUERY" \
  --thread-id "$THREAD_ID" \
  --live-doc-id "$LIVE_DOC_ID" \
  --accept-language en --json
```

### Search (simple real-time)

```bash
export FELO_API_KEY="<REDACTED-FELO>"
bash ~/.hermes/skills/felo/felo-search/scripts/search.sh "query"
```

### LiveDoc (knowledge base)

```bash
# List
node ~/.hermes/skills/felo/felo-livedoc/scripts/run_livedoc.mjs list --json

# Create
node ~/.hermes/skills/felo/felo-livedoc/scripts/run_livedoc.mjs create --name "Name" --json

# Search
node ~/.hermes/skills/felo/felo-livedoc/scripts/run_livedoc.mjs search --doc-id "ID" --query "query" --json
```

### Web Fetch

```bash
node ~/.hermes/skills/felo/felo-web-fetch/scripts/run_web_fetch.mjs \
  --url "https://..." --format markdown --json
```

### YouTube Subtitles

```bash
node ~/.hermes/skills/felo/felo-youtube-subtitling/scripts/run_yt_subtitling.mjs \
  --video-id "VIDEO_ID" --json
```

### Slides

```bash
node ~/.hermes/skills/felo/felo-slides/scripts/run_slides.mjs \
  --topic "..." --json
```

### Mindmap

```bash
node ~/.hermes/skills/felo/felo-mindmap/scripts/run_mindmap.mjs \
  --topic "..." --json
```

### Twitter Writer

```bash
# Mode 1: analyze account
node ~/.hermes/skills/felo/felo-twitter-writer/scripts/run_twitter_writer.mjs \
  --mode analyze --account "@username" --json

# Mode 2: write tweet
node ~/.hermes/skills/felo/felo-twitter-writer/scripts/run_twitter_writer.mjs \
  --mode write --style-dna "..." --topic "..." --json
```

## Context Triggers — Kapan Pakai Felo vs Model Lain

| Situation | Use Felo | Use Other |
|-----------|----------|-----------|
| Deep research (15+ sources) | ✅ SuperAgent | |
| Multi-turn planning | ✅ SuperAgent | |
| Real-time news/weather | ✅ Search | |
| Twitter style analysis | ✅ Twitter Writer | |
| URL content extraction | ✅ Web Fetch | |
| YouTube transcript | ✅ YT Subtitles | |
| Knowledge base RAG | ✅ LiveDoc | |
| PPT generation | ✅ Slides/Content-to-Slides | |
| Simple Q&A (no context needed) | | MiniMax/M2.7 |
| Coding task | | Codex |
| Indonesian NLP | | MiniMax/M2.7 |

## Error Handling

- **401 INVALID_API_KEY** → Verify FELO_API_KEY is set
- **502 CONVERSATION_CREATE_FAILED** → LiveDoc may be shared; use `is_shared=false` LiveDoc
- **Stream timeout** → Normal for long outputs; just wait
- **Empty search results** → Try different query, not a system error

## Skills Location

```
~/.hermes/skills/felo/                    # Primary install
~/.agents/skills/                          # Symlinks
/root/.hermes/profiles/ilma/home/.hermes/skills/felo/  # Actual files
/root/.hermes/profiles/ilma/scripts/ilma_felo_integration.py  # Routing logic
/root/.hermes/profiles/ilma/config/felo_session_state.json  # Thread state
```
