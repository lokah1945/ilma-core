---
name: ilma-felo-free
description: "ILMA FELO-FREE — Native replacement for Felo AI skills (search, Twitter/X, slides, web-fetch). 100% FREE, no API key, no external dependency. Built with python-pptx, BeautifulSoup, requests. USE INSTEAD OF felo-search/felo-x-search/felo-slides/felo-web-fetch when you want zero-cost operation."
triggers:
  - search
  - ppt
  - slides
  - twitter
  - x.com
  - tweet
  - extract url
  - fetch webpage
  - web scraping
---

# ILMA FELO-FREE — 100% Native Free Alternative

## Overview

ILMA has native free replacements for all Felo AI skills. No API key, no rate limits, no cost.

**Felo API dependency:** ❌ REMOVED  
**Felo API key usage:** BLOCKED  
**Alternative:** 100% native Python scripts

## ⚠️ CRITICAL FINDINGS (Trial & Error — 2026-05-08)

### What DOESN'T Work
- **DuckDuckGo HTML**: 403 Forbidden from Python urllib (not a Python user-agent issue — server actively blocks)
- **DuckDuckGo Lite**: 403 Forbidden
- **Nitter.net**: Returns 0 bytes from Python urllib (but works from curl — server-level block)
- **xcancel.com**: 403 Forbidden

### What DOES Work
- **Mojeek** (mojeek.com): Independent search engine, clean HTML, ✅
- **Bing HTML**: Works but URLs are encoded/redirected — need `decode_bing_url()` function
- **arXiv API**: Direct HTTP, always works for academic papers
- **Startpage**: Works but complex HTML parsing
- **python-pptx**: Generates real .pptx files, ✅
- **BeautifulSoup + requests**: Web extraction, ✅

### SSL Workaround (Required)
```python
import ssl
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
# Then use context=ctx in urllib.request.urlopen()
```

## Capabilities

| Felo Skill | Native Script | Method | Status |
|------------|--------------|--------|--------|
| felo-search | `ilma_free_search.py` | Mojeek + Bing HTML + arXiv | ✅ WORKING |
| felo-x-search | `ilma_free_twitter.py` | Multi-instance probing → Hermes fallback | ⚠️ PARTIAL |
| felo-slides | `ilma_free_slides.py` | python-pptx | ✅ WORKING |
| felo-web-fetch | `ilma_free_webfetch.py` | requests + BeautifulSoup | ✅ WORKING |
| felo-superAgent | `delegate_task` + reasoning | Hermes native | ✅ WORKING |
| felo-livedoc | `file` + `memory` | Hermes native | ✅ WORKING |

## Scripts

### 1. ilma_free_search.py — Web Search (FREE)
```
Path:   /root/.hermes/profiles/ilma/scripts/ilma_free_search.py
Usage:  python3 ilma_free_search.py "query here"
Chain:  arXiv (academic) → Mojeek (primary) → Bing HTML (fallback) → Startpage (last)
Output: Markdown with title, URL, snippet, sources
SSL:    Uses CERT_NONE context for unreliable HTTPS
Bing:   URLs need decode via decode_bing_url() — Bing redirects through /ck/a?!
```

### 2. ilma_free_slides.py — PPT Generation (FREE)
```
Path:   /root/.hermes/profiles/ilma/scripts/ilma_free_slides.py
Usage:  python3 ilma_free_slides.py "Topic Title" --slides 10
        python3 ilma_free_slides.py "AI Trends" --slides 5 --output /tmp/ai.pptx
Method: python-pptx → real .pptx file (PowerPoint, Google Slides, LibreOffice)
Output: File path to generated .pptx
Note:   Works perfectly first try, no SSL issues
```

### 3. ilma_free_webfetch.py — URL Extraction (FREE)
```
Path:   /root/.hermes/profiles/ilma/scripts/ilma_free_webfetch.py
Usage:  python3 ilma_free_webfetch.py "https://url.com" [--format markdown]
Method: requests + BeautifulSoup → parse title, content, images, links
Output: Markdown/text with structured data
SSL:    Uses CERT_NONE context
```

### 4. ilma_free_twitter.py — Twitter Search (FREE, PARTIAL)
```
Path:   /root/.hermes/profiles/ilma/scripts/ilma_free_twitter.py
Usage:  python3 ilma_free_twitter.py search "AI news" --limit 10
        python3 ilma_free_twitter.py user elonmusk --tweets 5
Method: Multi-instance probing (nitter.net → xcancel.com) + BeautifulSoup
Status: ⚠️ PARTIAL — nitter returns 0 bytes, xcancel 403 from Python urllib
Fallback: Hermes search tool for Twitter-related queries
Note:   Always include Hermes search as fallback when script returns empty
```

## Routing Rules

| User says... | Route to | Why |
|---|---|---|
| "cari berita AI hari ini" | `ilma_free_search.py` | Real-time web search |
| "buatkan PPT tentang X" | `ilma_free_slides.py` | Generate real .pptx |
| "ambil tweet tentang X" | `ilma_free_twitter.py` → Hermes search fallback | Twitter data (may be empty) |
| "extract URL ini" | `ilma_free_webfetch.py` | URL → markdown/text |
| "research topik X" | `delegate_task` + search | Multi-step reasoning |

## Error Handling

If native script fails:
1. Search empty → try Hermes `search` tool
2. Twitter empty → use Hermes `search` tool (Twitter queries still work)
3. Web fetch fails → try Hermes `browser` tool
4. **Never auto-escalate to paid Felo API**

## Architecture

```
PAID FELO API (BLOCKED: $0.017/task)
    ↓
ILMA FELO-FREE NATIVE
    ├── ilma_free_search.py     → Mojeek → Bing HTML → arXiv
    ├── ilma_free_slides.py    → python-pptx → .pptx file
    ├── ilma_free_webfetch.py  → requests + BeautifulSoup
    └── ilma_free_twitter.py   → nitter probing → Hermes search (fallback)
                                    ↓
                              Hermes search tool
```

## Cost Analysis

| Capability | Felo API | ILMA Free |
|-----------|----------|-----------|
| Search | ~$0.001/req | **$0.00** |
| Slides/PPT | ~$0.01/req | **$0.00** |
| Web Fetch | ~$0.001/req | **$0.00** |
| Twitter Data | ~$0.005/req | **$0.00** |
| **Total** | **~$0.017/task** | **$0.00/task** |

## Key Code Patterns

### Multi-Engine Fallback Chain
```python
def search_with_fallback(query):
    engines = [
        ("mojeek", mojeek_search),
        ("bing", bing_search),
        ("startpage", startpage_search),
    ]
    for name, fn in engines:
        results, err = fn(query)
        if err:
            continue  # Try next engine
        if results:
            return results
    return []  # All failed
```

### SSL Workaround
```python
import ssl
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
    ...
```

### Bing URL Decode
```python
def decode_bing_url(encoded_url):
    match = re.search(r'ru=([^&]+)', encoded_url)
    if match:
        return urllib.parse.unquote(match.group(1))
    return encoded_url
```

### Multi-Instance Twitter Probing
```python
instances = [
    ("nitter.net", "https://nitter.net"),
    ("xcancel.com", "https://xcancel.com"),
]
for name, base_url in instances:
    # Try each, skip if too little data
    if len(raw) < 500:
        continue
    # Found valid data, parse and return
```

## Documentation

Full log: `/root/.hermes/profiles/ilma/docs/ILMA_FELO_FREE_LOG_2026-05-08.md`
