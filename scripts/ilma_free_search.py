#!/usr/bin/env python3
"""
ILMA FREE SEARCH v2 — Native Web Search (100% FREE)
Replaces: felo-search (API felo.ai)

SEARCH ENGINE FALLBACK CHAIN:
  1. arXiv (academic papers) — direct API, always works
  2. Mojeek (independent search) — clean HTML
  3. Bing HTML (with URL decode) — Microsoft's search
  4. Startpage — privacy search
  5. Hermes search tool — as last resort

USAGE:
  python3 ilma_free_search.py "query here"

OUTPUT:
  Markdown-formatted answer with title, URL, snippet
"""

import sys
import re
import ssl
import urllib.request
import urllib.parse
import urllib.error
from html import unescape

_UNVERIFIED_SSL = ssl.create_default_context()
_UNVERIFIED_SSL.check_hostname = False
_UNVERIFIED_SSL.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}


def decode_bing_url(encoded_url: str) -> str:
    """Decode Bing's redirect URL to get real destination URL."""
    # Bing URLs look like: https://www.bing.com/ck/a?!&&p=...JmltdHM9...
    # The actual URL is embedded, try to find it
    match = re.search(r'ru=([^&]+)', encoded_url)
    if match:
        return urllib.parse.unquote(match.group(1))
    # Try base64 decode for some formats
    return encoded_url


def arxiv_search(query: str, max_results: int = 5) -> list:
    """Search arXiv for academic papers (FREE, no API key)."""
    url = f"http://export.arxiv.org/api/query?search_query=all:{urllib.parse.quote(query)}&start=0&max_results={max_results}&sortBy=relevance"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            xml = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return [], str(e)

    results = []
    entries = xml.split('<entry>')
    for entry in entries[1:max_results+1]:
        title_m = re.search(r'<title>(.*?)</title>', entry, re.DOTALL)
        summary_m = re.search(r'<summary>(.*?)</summary>', entry, re.DOTALL)
        link_m = re.search(r'<id>(.*?)</id>', entry)
        author_m = re.search(r'<author>.*?<name>(.*?)</name>', entry, re.DOTALL)
        published_m = re.search(r'<published>(.*?)</published>', entry)
        if title_m:
            title = unescape(title_m.group(1).replace('\n', ' ').strip())
            summary = ''
            if summary_m:
                summary = unescape(summary_m.group(1).replace('\n', ' ').strip()[:300])
            link = link_m.group(1) if link_m else ''
            author = author_m.group(1) if author_m else 'Unknown'
            published = published_m.group(1)[:10] if published_m else ''
            results.append({
                "title": title,
                "url": link,
                "snippet": summary,
                "author": author,
                "published": published,
                "type": "academic"
            })
    return results, None


def mojeek_search(query: str, num_results: int = 8) -> list:
    """Search via Mojeek (independent search engine)."""
    url = f"https://www.mojeek.com/search?q={urllib.parse.quote(query)}&fmt=html"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15, context=_UNVERIFIED_SSL) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return [], str(e)

    results = []
    # Mojeek results: <a class="title" href="...">title</a> with <p class="excerpt">snippet</p>
    pattern = re.compile(r'<a class="title"[^>]*href="([^"]+)"[^>]*>(.*?)</a>')
    titles = pattern.findall(html)
    
    # Get snippets - <p class="excerpt">
    snippet_pattern = re.compile(r'<p class="excerpt">.*?<a[^>]*>[^<]*</a>\s*(.*?)</p>', re.DOTALL)
    snippets = snippet_pattern.findall(html)
    
    for i, (url, title_raw) in enumerate(titles[:num_results]):
        title = unescape(re.sub(r'<[^>]+>', '', title_raw).replace('\n', ' ').strip())
        snippet = ''
        if i < len(snippets):
            s = re.sub(r'<[^>]+>', '', unescape(snippets[i])).replace('\n', ' ').strip()
            snippet = s[:300]
        results.append({"title": title, "url": url, "snippet": snippet, "type": "web"})
    
    return results, None


def bing_search(query: str, num_results: int = 8) -> list:
    """Search via Bing HTML (with URL decoding)."""
    url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}&ensearch=0"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15, context=_UNVERIFIED_SSL) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return [], str(e)

    results = []
    # Bing results: <h2> with links inside b_algo divs
    # Pattern: <a ... href="REAL_URL" ...>title</a>
    pattern = re.compile(
        r'<li[^>]*class="[^"]*b_algo[^"]*"[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>[^<]*<h3[^>]*>(.*?)</h3>',
        re.DOTALL
    )
    matches = pattern.findall(html)
    
    if not matches:
        # Alternative: find all links in h2
        h2_links = re.findall(r'<h2[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?</h2>', html, re.DOTALL)
        for url_raw, title_raw in h2_links[:num_results]:
            url = decode_bing_url(url_raw)
            title = unescape(re.sub(r'<[^>]+>', '', title_raw).replace('\n', ' ').strip())
            if url and title and not url.startswith('javascript:'):
                results.append({"title": title, "url": url, "snippet": "", "type": "web"})
    
    for url_raw, title_raw in matches[:num_results]:
        url = decode_bing_url(url_raw)
        title = unescape(re.sub(r'<[^>]+>', '', title_raw).replace('\n', ' ').strip())
        if url and title and not url.startswith('javascript:'):
            results.append({"title": title, "url": url, "snippet": "", "type": "web"})
    
    return results, None


def startpage_search(query: str, num_results: int = 8) -> list:
    """Search via Startpage (privacy search engine)."""
    url = f"https://www.startpage.com/do/search?q={urllib.parse.quote(query)}&lui=english"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15, context=_UNVERIFIED_SSL) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return [], str(e)

    results = []
    # Startpage results in <div class="result">
    pattern = re.compile(r'<div class="result[^"]*"[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*class="title[^"]*"[^>]*>(.*?)</a>', re.DOTALL)
    matches = pattern.findall(html)
    for url, title_raw in matches[:num_results]:
        title = unescape(re.sub(r'<[^>]+>', '', title_raw).replace('\n', ' ').strip())
        results.append({"title": title, "url": url, "snippet": "", "type": "web"})
    return results, None


def search(query: str) -> str:
    """Main search — tries multiple free engines in priority order."""
    if not query or not query.strip():
        return "❌ Query cannot be empty."

    query = query.strip()
    all_results = []
    errors = []

    # Priority: academic first, then web
    academic_keywords = ["paper", "research", "arxiv", "study", "algorithm",
                          "neural", "learning", "deep learning", "model architecture",
                          "transformer", "llm", "machine learning", "ai model"]
    is_academic = any(k in query.lower() for k in academic_keywords)

    if is_academic:
        arxiv_results, err = arxiv_search(query)
        if err:
            errors.append(f"arXiv: {err}")
        else:
            all_results.extend(arxiv_results)

    # Try Mojeek first (cleanest HTML)
    mojeek_results, mojeek_err = mojeek_search(query)
    if mojeek_err:
        errors.append(f"Mojeek: {mojeek_err}")
    else:
        all_results.extend(mojeek_results)

    # Fallback to Bing if Mojeek returned nothing
    if not all_results:
        bing_results, bing_err = bing_search(query)
        if bing_err:
            errors.append(f"Bing: {bing_err}")
        else:
            all_results.extend(bing_results)

    # Last resort: Startpage
    if not all_results:
        sp_results, sp_err = startpage_search(query)
        if sp_err:
            errors.append(f"Startpage: {sp_err}")
        else:
            all_results.extend(sp_results)

    return format_results(query, all_results[:10], errors if errors else None)


def format_results(query: str, results: list, errors: list = None) -> str:
    """Format search results as markdown."""
    output = f"## 🔍 Search: {query}\n\n"
    if errors:
        output += f"⚠️ Engine errors: {', '.join(errors)}\n\n"
    if not results:
        output += "_No results found. Try the Hermes search tool as fallback._\n"
        return output

    for i, r in enumerate(results, 1):
        rtype = r.get("type", "web")
        icon = "📚" if rtype == "academic" else "🌐"
        output += f"### {icon} {i}. {r.get('title', 'N/A')}\n"
        output += f"**URL:** {r.get('url', 'N/A')}\n"
        if r.get("snippet"):
            output += f"_{r['snippet'][:300]}_\n"
        if r.get("author"):
            output += f"👤 {r.get('author', '')}"
            if r.get("published"):
                output += f" ({r['published']})"
            output += "\n"
        output += "\n"
    return output


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 ilma_free_search.py <query>")
        sys.exit(1)
    query = " ".join(sys.argv[1:])
    print(search(query))
