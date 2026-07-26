#!/usr/bin/env python3
"""
ILMA Felo Integration Layer
Felo AI SuperAgent — 11 Skills Package

Account: lokah2150@gmail.com
API Key: <REDACTED-FELO>
Env Var: FELO_API_KEY

SKILL ROUTING MAP:
═══════════════════════════════════════════════════════════════════
│ TUGAS                        │ FELO SKILL           │ TOOL/MODE │
╞══════════════════════════════╪═══════════════════════╪═══════════╡
│ Web search real-time         │ felo-search          │ search.sh │
│ Multi-turn planning/synthesis│ felo-superAgent      │ run_superagent.mjs │
│ Twitter style analysis       │ felo-twitter-writer  │ dual-mode │
│ Webpage → markdown/html/text │ felo-web-fetch       │ run_web_fetch.mjs │
│ YouTube subtitles/captions   │ felo-youtube-subtitling│ run_yt.mjs │
│ X/Twitter data search        │ felo-x-search        │ search.sh │
│ Knowledge base (LiveDoc)    │ felo-livedoc         │ run_livedoc.mjs │
│ URL/YouTube → PPT            │ felo-content-to-slides│ pipeline │
│ Mindmap generation           │ felo-mindmap         │ run_mindmap.mjs │
│ PPT/slides generation        │ felo-slides          │ run_slides.mjs │
│ Apple product advisor        │ apple-buy-advisor    │ interactive │
═══════════════════════════════════════════════════════════════════

USAGE CONTEXT MATRIX — Kapan Pakai Apa:
═══════════════════════════════════════════════════════════════════

1. TUGAS SPESIFIK FELO SUPERAGENT (superagent):
   → multi-turn planning, research synthesis, policy memo
   → continuous conversation dengan context persistence
   → logo/branding design, e-commerce product images
   → BOS: "Buatkan rencana Q3", "Analisa vendor", "Research AI trends"
   
   Command: felo superagent ask "..."
   Persistent session across turns

2. REAL-TIME WEB SEARCH (search):
   → current events, news, stock prices, weather
   → BOS: "What's trending in AI today?", "Latest news on..."
   → Bukan untuk deep research (pakai superagent)
   
   Command: felo search "..."
   Streamed answer, current data

3. KNOWLEDGE BASE / LIVEDOC (livedoc):
   → upload documents, semantic search, knowledge management
   → BOS: "Upload this PDF", "Search my knowledge base", "Add URL"
   → Superagent CAN use LiveDoc as context anchor
   
   Command: felo livedoc [create|list|upload|search]
   Persistent knowledge for superagent sessions

4. TWITTER/X WRITING (twitter-writer):
   → style DNA extraction dari account
   → tweet/thread composition based on style
   → BOS: "Analyze @username's style", "Write a tweet in style of..."
   
   Command: felo twitter [analyze|write]

5. WEB EXTRACTION (web-fetch):
   → extract URL content ke markdown/html/text
   → BOS: "Summarize this article", "Extract data from URL"
   → Input untuk superagent atau analysis
   
   Command: felo web-fetch --url "..."

6. YOUTUBE SUBTITLES:
   → fetch captions dari YouTube video
   → BOS: "Get subtitles of this video", "Extract transcript"
   
   Command: felo youtube-subtitles "..."

7. X/TWITTER SEARCH (x-search):
   → user lookup, tweet search, trending topics
   → BOS: "Search tweets about...", "Who is @username"
   
   Command: felo x-search "..."

8. SLIDES/PPT:
   → generate presentation dari topic atau URL
   → BOS: "Create slides about...", "Make a PPT"
   
   Command: felo slides "..."

9. CONTENT TO SLIDES:
   → URL/YouTube → PPT in one step
   → BOS: "Turn this article into slides", "Video to PPT"
   
   Command: felo content-to-slides --url "..."

10. MINDMAP:
    → generate mindmap dari topic
    → BOS: "Create a mindmap of..."
    
    Command: felo mindmap "..."

11. APPLE BUY ADVISOR:
    → Apple product recommendations
    → BOS: "Which MacBook should I buy?"

═══════════════════════════════════════════════════════════════════

SUPERAGENT THREAD STATE MANAGEMENT:
═══════════════════════════════════════════════════════════════════
SuperAgent maintains persistent threads within a LiveDoc canvas.

Thread state tracking:
- thread_short_id: per conversation thread
- live_doc_id: the canvas (shared across threads)
- NEW conversation: --live-doc-id only (no --thread-id)
- FOLLOW-UP: --thread-id + --live-doc-id (DEFAULT for 2nd+ messages)

Bos MUST provide thread_short_id from previous response.
Store in memory/session after each call.

SUPERAGENT SKILL-IDS:
- twitter-writer → tweet writing
- logo-and-branding → logo/brand design
- ecommerce-product-image → product images
- (none) → general conversation/research

SUPERAGENT STYLE SELECTION:
- Style DNA untuk twitter-writer, logo, product images
- Fetch style library → present to Bos → Bos picks
- Or Bos specifies style directly

═══════════════════════════════════════════════════════════════════

HOW TO CALL FELO FROM ILMA:
═══════════════════════════════════════════════════════════════════
Always set env var first:
  export FELO_API_KEY="<REDACTED-FELO>"

SuperAgent (most complex):
  node ~/.hermes/skills/felo/felo-superAgent/scripts/run_superagent.mjs \
    --query "..." --live-doc-id "..." --thread-id "..." \
    --skill-id "..." --ext '...' --accept-language en --json

Search (simple):
  bash ~/.hermes/skills/felo/felo-search/scripts/search.sh "query"

LiveDoc:
  node ~/.hermes/skills/felo/felo-livedoc/scripts/run_livedoc.mjs \
    create --name "..." --json

Web Fetch:
  node ~/.hermes/skills/felo/felo-web-fetch/scripts/run_web_fetch.mjs \
    --url "..." --format markdown --json

YouTube Subtitles:
  node ~/.hermes/skills/felo/felo-youtube-subtitling/scripts/run_yt_subtitling.mjs \
    --video-id "..." --json

X Search:
  bash ~/.hermes/skills/felo/felo-x-search/scripts/search.sh "query"

Slides:
  node ~/.hermes/skills/felo/felo-slides/scripts/run_slides.mjs \
    --topic "..." --json

Mindmap:
  node ~/.hermes/skills/felo/felo-mindmap/scripts/run_mindmap.mjs \
    --topic "..." --json

Content to Slides:
  node ~/.hermes/skills/felo/felo-content-to-slides/scripts/run_content_to_slides.mjs \
    --url "..." --json

Twitter Writer:
  node ~/.hermes/skills/felo/felo-twitter-writer/scripts/run_twitter_writer.mjs \
    --mode analyze --account "..." --json

═══════════════════════════════════════════════════════════════════
"""

# =====================================================================
# ILMA FELO CAPABILITY REGISTRY ENTRY
# =====================================================================
FELO_CAPABILITIES = {
    "name": "felo-integration",
    "description": "Felo AI 11-skill package — real-time search, multi-turn SuperAgent, knowledge bases, content extraction, media generation",
    "skills": [
        {"id": "felo-superagent", "purpose": "multi-turn planning/research", "persistence": "thread + LiveDoc"},
        {"id": "felo-search", "purpose": "real-time web search", "persistence": "none"},
        {"id": "felo-livedoc", "purpose": "knowledge base management", "persistence": "permanent"},
        {"id": "felo-twitter-writer", "purpose": "Twitter style analysis + writing", "persistence": "style DNA"},
        {"id": "felo-web-fetch", "purpose": "URL content extraction", "persistence": "none"},
        {"id": "felo-youtube-subtitling", "purpose": "YouTube captions", "persistence": "none"},
        {"id": "felo-x-search", "purpose": "X/Twitter data search", "persistence": "none"},
        {"id": "felo-slides", "purpose": "PPT generation", "persistence": "url"},
        {"id": "felo-content-to-slides", "purpose": "URL/YT → PPT", "persistence": "url"},
        {"id": "felo-mindmap", "purpose": "mindmap generation", "persistence": "url"},
        {"id": "apple-buy-advisor", "purpose": "Apple product advice", "persistence": "none"},
    ],
    "account": "lokah2150@gmail.com",
    "api_key_ref": "/root/credential/api_key.json:felo:api_key",
    "env_var": "FELO_API_KEY",
    "install_path": "~/.hermes/skills/felo/",
    "symlink_path": "~/.agents/skills/",
    "base_url": "https://openapi.felo.ai",
    "added": "2026-05-08",
}


# =====================================================================
# THREAD STATE (for SuperAgent multi-turn sessions)
# =====================================================================
# Usage: Store after each SuperAgent call
# thread_short_id: current conversation thread
# live_doc_id: shared canvas (reuse across threads)
# live_doc_url: for Bos reference

SUPERAGENT_STATE = {
    "thread_short_id": None,
    "live_doc_id": None,
    "live_doc_url": None,
}

# =====================================================================
# ROUTING DECISION TREE
# =====================================================================

def route_felo_task(task_type: str, context: dict = None) -> dict:
    """
    Returns: {skill: str, command_template: str, description: str}
    """
    task_lower = task_type.lower()
    
    # SuperAgent territory
    if any(kw in task_lower for kw in [
        "plan", "rencana", "analisa", "research", "sintesis",
        "multi-turn", "continuous", "persistent", "session",
        "logo", "branding", "product image", "ecommerce",
        "memo", "policy", "vendor", "comparison"
    ]):
        return {
            "skill": "felo-superAgent",
            "primary": True,
            "description": "Multi-turn planning, research, synthesis, design"
        }
    
    # Real-time search
    if any(kw in task_lower for kw in [
        "search", "trending", "news", "current", "latest",
        "weather", "stock", "price", "real-time"
    ]) and not any(kw in task_lower for kw in ["tweet", "twitter", "x.com"]):
        return {
            "skill": "felo-search",
            "primary": True,
            "description": "Real-time web search"
        }
    
    # Twitter/X writing
    if any(kw in task_lower for kw in [
        "tweet", "twitter", "write tweet", "twitter style"
    ]):
        return {
            "skill": "felo-twitter-writer",
            "primary": True,
            "description": "Twitter/X writing and style analysis"
        }
    
    # X/Twitter search (data)
    if any(kw in task_lower for kw in [
        "x search", "search x", "search twitter", "trending topics"
    ]):
        return {
            "skill": "felo-x-search",
            "primary": True,
            "description": "X/Twitter data search"
        }
    
    # Web extraction
    if any(kw in task_lower for kw in [
        "extract", "fetch url", "webpage", "scrape", "get content from"
    ]):
        return {
            "skill": "felo-web-fetch",
            "primary": True,
            "description": "URL content extraction"
        }
    
    # YouTube subtitles
    if any(kw in task_lower for kw in [
        "youtube", "subtitle", "caption", "transcript"
    ]):
        return {
            "skill": "felo-youtube-subtitling",
            "primary": True,
            "description": "YouTube subtitle/caption extraction"
        }
    
    # Knowledge base
    if any(kw in task_lower for kw in [
        "knowledge base", "livedoc", "upload", "rag", "semantic search"
    ]):
        return {
            "skill": "felo-livedoc",
            "primary": True,
            "description": "Knowledge base management"
        }
    
    # PPT/Slides
    if any(kw in task_lower for kw in [
        "slide", "ppt", "presentation", "deck"
    ]):
        if "url" in task_lower or "article" in task_lower:
            return {
                "skill": "felo-content-to-slides",
                "primary": True,
                "description": "URL/YouTube → PPT"
            }
        return {
            "skill": "felo-slides",
            "primary": True,
            "description": "PPT generation from topic"
        }
    
    # Mindmap
    if any(kw in task_lower for kw in [
        "mindmap", "mind map", "thinking map"
    ]):
        return {
            "skill": "felo-mindmap",
            "primary": True,
            "description": "Mindmap generation"
        }
    
    # Apple
    if any(kw in task_lower for kw in [
        "apple", "macbook", "iphone", "ipad", "mac"
    ]) and any(kw in task_lower for kw in [
        "buy", "recommend", "which", "should i"
    ]):
        return {
            "skill": "apple-buy-advisor",
            "primary": True,
            "description": "Apple product buying advice"
        }
    
    # Default to SuperAgent for anything ambiguous
    return {
        "skill": "felo-superAgent",
        "primary": True,
        "description": "General AI conversation — default routing"
    }


if __name__ == "__main__":
    # Test routing
    tests = [
        "Buatkan rencana Q3",
        "What's trending in AI?",
        "Analyze @username style",
        "Get subtitles from this video",
        "Create a mindmap of Python",
        "Make slides about quantum computing",
        "Summarize this article",
        "Search my knowledge base",
    ]
    for t in tests:
        r = route_felo_task(t)
        print(f"'{t}' → {r['skill']} ({r['description']})")
