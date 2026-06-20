#!/usr/bin/env python3
"""
ILMA Web Search — Mojeek Integration (100% FREE, no tracking)
=============================================================
Component: Web Search
Version: 2.1.0 | Status: OPERATIONAL
============================================================

HOW IT WORKS:
  1. Mojeek.com — independent search engine, no tracking, no account required
  2. No API key needed, no rate limits
  3. Returns title, URL, snippet for each result

USAGE:
  python3 ilma_web_search.py "query" [--limit 10] [--json]
  python3 ilma_web_search.py --help

PYTHON API:
  from scripts.ilma_web_search import search_web, search_web_formatted
  results = search_web("query", limit=10)
  formatted = search_web_formatted("query", limit=5)
"""

import sys
import re
import ssl
import json
import logging
from html import unescape, entities
from urllib.parse import quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

# SSL context
_UNVERIFIED_SSL = ssl.create_default_context()
_UNVERIFIED_SSL.check_hostname = False
_UNVERIFIED_SSL.verify_mode = ssl.CERT_NONE

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)-8s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def _html_unescape(text: str) -> str:
    """Decode HTML entities and clean whitespace."""
    text = unescape(text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


@dataclass
class SearchResult:
    """Single search result."""
    title: str
    url: str
    snippet: str = ""
    source: str = "mojeek"
    
    def to_dict(self) -> Dict[str, str]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "source": self.source
        }


@dataclass
class SearchResponse:
    """Full search response container."""
    query: str
    results: List[SearchResult] = field(default_factory=list)
    total_found: int = 0
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "results": [r.to_dict() for r in self.results],
            "total_found": self.total_found,
            "error": self.error
        }


def _extract_snippet(html: str, idx: int) -> str:
    """Extract snippet from result HTML by position."""
    # Snippet is in <p class="s">...</p>
    snippets = re.findall(r'<p class="s">([^<]+(?:<[^>]+>[^<]+)*)</p>', html)
    if idx < len(snippets):
        # Clean any HTML tags inside snippet
        snippet = re.sub(r'<[^>]+>', '', snippets[idx])
        return _html_unescape(snippet)
    return ""


def _extract_url_from_title_tag(title_tag: str) -> str:
    """Extract URL from title attribute of <a class='title'>."""
    m = re.search(r'title="([^"]+)"', title_tag)
    if m:
        return m.group(1)
    return ""


def search_mojeek(query: str, limit: int = 10) -> Dict[str, Any]:
    """
    Search using Mojeek (independent, no tracking).
    Returns dict with query, results list, total_found, error.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.mojeek.com/",
    }
    
    url = f"https://www.mojeek.com/search?q={quote(query)}&n={limit}"
    
    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=15, context=_UNVERIFIED_SSL) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.reason}", "query": query, "results": []}
    except URLError as e:
        return {"error": str(e.reason), "query": query, "results": []}
    except Exception as e:
        return {"error": str(e), "query": query, "results": []}
    
    results = []
    
    # Extract each result block <li class="r1"> or <li class="r2">
    # Each block has: <a class="title" title="URL">Title</a>
    # and optionally: <p class="s">Snippet text</p>
    
    li_blocks = re.findall(r'<li class="r[12]">(.*?)</li>', html, re.DOTALL)
    
    for block in li_blocks:
        if len(results) >= limit:
            break
        
        # Extract title + URL from <a class="title">
        title_match = re.search(r'<a class="title"[^>]*title="([^"]+)"[^>]*>([^<]+)</a>', block)
        if not title_match:
            continue
        
        url_value = title_match.group(1)
        title_raw = title_match.group(2)
        title = _html_unescape(title_raw)
        
        # Skip if no valid URL
        if not url_value or not url_value.startswith("http"):
            continue
        
        # Extract snippet from <p class="s">...</p>
        snippet_match = re.search(r'<p class="s">(.*?)</p>', block, re.DOTALL)
        if snippet_match:
            snippet_html = snippet_match.group(1)
            snippet = re.sub(r'<[^>]+>', '', snippet_html)
            snippet = _html_unescape(snippet)
        else:
            snippet = ""
        
        results.append(SearchResult(title=title, url=url_value, snippet=snippet))
    
    # Clean HTML unescape for all results
    for r in results:
        r.title = _html_unescape(r.title)
        r.snippet = _html_unescape(r.snippet)
    
    return {
        "query": query,
        "results": results,
        "total_found": len(results),
        "error": None
    }


def search_web(query: str, limit: int = 10) -> Dict[str, Any]:
    """
    PUBLIC API — search the web.
    Returns: {"query": str, "results": [SearchResult], "total_found": int, "error": str|null}
    """
    logger.info(f"Web search: '{query}' (limit={limit})")
    result = search_mojeek(query, limit=limit)
    
    if result.get("error"):
        logger.error(f"Search error: {result['error']}")
    else:
        logger.info(f"Found {result['total_found']} results for '{query}'")
    
    return result


def search_web_formatted(query: str, limit: int = 10) -> str:
    """
    PUBLIC API — formatted human-readable search results.
    """
    result = search_web(query, limit=limit)
    
    if result.get("error"):
        return f"❌ Search failed: {result['error']}"
    
    res_list = result.get("results", [])
    if not res_list:
        return f"🔍 No results found for: \"{query}\""
    
    lines = [f"## 🔍 Search: \"{query}\" ({len(res_list)} results)"]
    lines.append("")
    
    for i, r in enumerate(res_list, 1):
        title = getattr(r, 'title', str(r))
        snippet = getattr(r, 'snippet', '')
        url = getattr(r, 'url', '')
        lines.append(f"**{i}. {title}**")
        if snippet:
            lines.append(f"   {snippet}")
        lines.append(f"   🔗 {url}")
        lines.append("")
    
    return "\n".join(lines)


def search_web_json(query: str, limit: int = 10) -> str:
    """PUBLIC API — JSON output."""
    result = search_web(query, limit=limit)
    return json.dumps(result, indent=2, default=str)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    import argparse
    
    parser = argparse.ArgumentParser(description="ILMA Web Search (Mojeek)")
    parser.add_argument("query", nargs="?", help="Search query")
    parser.add_argument("-l", "--limit", type=int, default=10, help="Max results (default 10)")
    parser.add_argument("-j", "--json", action="store_true", help="Output JSON")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    if not args.query:
        parser.print_help()
        return 0
    
    if args.json:
        print(search_web_json(args.query, limit=args.limit))
    else:
        print(search_web_formatted(args.query, limit=args.limit))
    
    return 0


if __name__ == "__main__":
    sys.exit(main())