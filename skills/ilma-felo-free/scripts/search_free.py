#!/usr/bin/env python3
"""
ILMA_FELO_FREE: Web Search via free methods (no API key)
Method 1: search_web tool (native)
Method 2: browser DuckDuckGo lite
Method 3: direct curl to free search APIs
100% free, no authentication needed.
"""

import sys
import urllib.request
import urllib.parse
import json
import re

def search_via_duckduckgo(query: str, num_results: int = 10) -> str:
    """Search using DuckDuckGo Lite (no JS required)."""
    encoded = urllib.parse.quote(query)
    url = f"https://lite.duckduckgo.com/lite/?q={encoded}&kl=en-us"
    
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
    
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        
        # Parse results from DuckDuckGo Lite HTML
        # DuckDuckGo Lite format: <a class="result__a" href="...">Title</a>
        #                         <a class="result__snippet" href="...">Snippet</a>
        
        results = []
        
        # Extract title and snippet pairs
        title_pattern = re.compile(r'<a class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>', re.DOTALL)
        snippet_pattern = re.compile(r'<a class="result__snippet"[^>]*>(.*?)</a>', re.DOTALL)
        
        titles = title_pattern.findall(html)
        snippets = snippet_pattern.findall(html)
        
        for i, (href, title_raw) in enumerate(titles[:num_results]):
            title = re.sub(r'<[^>]+>', '', title_raw).strip()
            snippet = re.sub(r'<[^>]+>', '', snippets[i]) if i < len(snippets) else "No snippet"
            results.append({
                "rank": i + 1,
                "title": title,
                "url": href,
                "snippet": snippet[:200]
            })
        
        if not results:
            return f"## Web Search: {query}\n[No results found via DuckDuckGo Lite]\nHTML preview: {html[:300]}"
        
        output = f"## Web Search: {query}\n"
        output += f"Results found: {len(results)}\n\n"
        
        for r in results:
            output += f"### [{r['rank']}] {r['title']}\n"
            output += f"URL: {r['url']}\n"
            output += f"Snippet: {r['snippet']}...\n\n"
        
        return output
        
    except Exception as e:
        return f"ERROR: DuckDuckGo Lite failed - {e}"

def search_via_google_fallback(query: str, num_results: int = 10) -> str:
    """Fallback: Use Startpage or searxng public instance."""
    # Try searxng (open-source meta-search engine)
    searx_instances = [
        "https://searx.be",
        "https://searx.org",
    ]
    
    encoded = urllib.parse.quote(query)
    
    for instance in searx_instances:
        try:
            url = f"{instance}/search?q={encoded}&format=json&engines=google,duckduckgo"
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (ILMA-FELO-FREE/1.0)"
            })
            
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
            
            results = []
            for i, r in enumerate(data.get("results", [])[:num_results]):
                results.append({
                    "rank": i + 1,
                    "title": r.get("title", "No title"),
                    "url": r.get("url", ""),
                    "snippet": r.get("content", "")[:200]
                })
            
            if results:
                output = f"## Web Search: {query}\nSource: {instance}\nResults found: {len(results)}\n\n"
                for r in results:
                    output += f"### [{r['rank']}] {r['title']}\n"
                    output += f"URL: {r['url']}\n"
                    output += f"Snippet: {r['snippet']}...\n\n"
                return output
                
        except Exception as e:
            continue
    
    return f"ERROR: All search engines failed for query: {query}"

def format_search_result(query: str, results_text: str, query_variants: list = None) -> str:
    """Format search results in Felo-style output."""
    output = "## Answer\n"
    
    # Parse results to build answer
    if results_text.startswith("ERROR") or "No results found" in results_text:
        output += f"Mohon maaf, saya tidak dapat menemukan hasil untuk '{query}'.\n"
        output += "Silakan coba kata kunci yang berbeda atau periksa koneksi internet Anda.\n"
        output += f"\nTechnical detail: {results_text[:200]}\n"
    else:
        # Extract key info from results
        output += f"Berikut hasil pencarian untuk '{query}'.\n\n"
        output += results_text
    
    if query_variants:
        output += "\n## Query Analysis\n"
        output += f"Optimized search terms: {', '.join(query_variants)}\n"
    
    return output

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 search_free.py <query>")
        print("  Search via DuckDuckGo Lite (free, no API key)")
        sys.exit(1)
    
    query = " ".join(sys.argv[1:])
    
    print(f"Searching: {query}")
    print("=" * 50)
    
    # Try DuckDuckGo first
    result = search_via_duckduckgo(query)
    
    if result.startswith("ERROR"):
        print("DuckDuckGo failed, trying searxng...")
        result = search_via_google_fallback(query)
    
    print(format_search_result(query, result))