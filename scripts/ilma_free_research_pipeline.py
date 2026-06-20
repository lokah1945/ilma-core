#!/usr/bin/env python3
"""
ILMA FREE RESEARCH PIPELINE — 100% FREE Alternative to Firecrawl, Tavily, and Exa
================================================================================

This script provides comprehensive web research capabilities using only free tools:
- Firecrawl-like: sitemap discovery, batch crawling, URL extraction
- Tavily-like: structured content extraction, AI-powered summarization (local heuristics)
- Exa-like: semantic/keyword search with relevance scoring

INTEGRATES:
- ilma_free_search.py: Mojeek, Bing HTML, Startpage, arXiv search engines
- ilma_free_webfetch.py: BeautifulSoup-based web fetching

USAGE:
    # CLI mode
    python3 ilma_free_research_pipeline.py --query "your search query"
    python3 ilma_free_research_pipeline.py --crawl "https://example.com"
    python3 ilma_free_research_pipeline.py --batch "urls.txt"
    python3 ilma_free_research_pipeline.py --extract "https://example.com"
    
    # Module mode
    from ilma_free_research_pipeline import deep_search, crawl_urls, get_competitor_analysis
    results = deep_search("AI research", limit=10)

FEATURES:
- crawl_urls(url_list) — crawl multiple URLs with retry logic
- deep_search(query, limit) — search + fetch top results
- extract_structured(url) — extract structured data with content analysis
- search_and_scrape(query, limit) — full pipeline: search → fetch → extract
- get_competitor_analysis(domain) — competitor research pipeline
- batch_crawl(urls, parallel) — concurrent batch crawling
- sitemap_discovery(url) — discover URLs from sitemap
- summarize_content(text) — local heuristic summarization
"""

import sys
import os
import re
import ssl
import json
import time
import logging
import argparse
import hashlib
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import unescape
from typing import List, Dict, Optional, Any

# SSL context for unverified HTTPS
_UNVERIFIED_SSL = ssl.create_default_context()
_UNVERIFIED_SSL.check_hostname = False
_UNVERIFIED_SSL.verify_mode = ssl.CERT_NONE

# Request headers
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
}

# Cache directory
CACHE_DIR = "/root/.hermes/profiles/ilma/data/research_cache"
os.makedirs(CACHE_DIR, exist_ok=True)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(CACHE_DIR, "research_pipeline.log"))
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# SEARCH ENGINES (from ilma_free_search.py)
# ============================================================================

def decode_bing_url(encoded_url: str) -> str:
    """Decode Bing's redirect URL to get real destination URL."""
    match = re.search(r'ru=([^&]+)', encoded_url)
    if match:
        return urllib.parse.unquote(match.group(1))
    return encoded_url

def arxiv_search(query: str, max_results: int = 5) -> tuple:
    """Search arXiv for academic papers (FREE, no API key)."""
    import urllib.request
    import urllib.parse
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
                "type": "academic",
                "source": "arxiv"
            })
    return results, None


def mojeek_search(query: str, num_results: int = 8) -> tuple:
    """Search via Mojeek (independent search engine)."""
    import urllib.request
    import urllib.parse
    url = f"https://www.mojeek.com/search?q={urllib.parse.quote(query)}&fmt=html"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15, context=_UNVERIFIED_SSL) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return [], str(e)

    results = []
    pattern = re.compile(r'<a class="title"[^>]*href="([^"]+)"[^>]*>(.*?)</a>')
    titles = pattern.findall(html)
    
    snippet_pattern = re.compile(r'<p class="excerpt">.*?<a[^>]*>[^<]*</a>\s*(.*?)</p>', re.DOTALL)
    snippets = snippet_pattern.findall(html)
    
    for i, (url, title_raw) in enumerate(titles[:num_results]):
        title = unescape(re.sub(r'<[^>]+>', '', title_raw).replace('\n', ' ').strip())
        snippet = ''
        if i < len(snippets):
            s = re.sub(r'<[^>]+>', '', unescape(snippets[i])).replace('\n', ' ').strip()
            snippet = s[:300]
        results.append({"title": title, "url": url, "snippet": snippet, "type": "web", "source": "mojeek"})
    
    return results, None


def bing_search(query: str, num_results: int = 8) -> tuple:
    """Search via Bing HTML (with URL decoding)."""
    import urllib.request
    import urllib.parse
    url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}&ensearch=0"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15, context=_UNVERIFIED_SSL) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return [], str(e)

    results = []
    pattern = re.compile(
        r'<li[^>]*class="[^"]*b_algo[^"]*"[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>[^<]*<h3[^>]*>(.*?)</h3>',
        re.DOTALL
    )
    matches = pattern.findall(html)
    
    if not matches:
        h2_links = re.findall(r'<h2[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?</h2>', html, re.DOTALL)
        for url_raw, title_raw in h2_links[:num_results]:
            url = decode_bing_url(url_raw)
            title = unescape(re.sub(r'<[^>]+>', '', title_raw).replace('\n', ' ').strip())
            if url and title and not url.startswith('javascript:'):
                results.append({"title": title, "url": url, "snippet": "", "type": "web", "source": "bing"})
    
    for url_raw, title_raw in matches[:num_results]:
        url = decode_bing_url(url_raw)
        title = unescape(re.sub(r'<[^>]+>', '', title_raw).replace('\n', ' ').strip())
        if url and title and not url.startswith('javascript:'):
            results.append({"title": title, "url": url, "snippet": "", "type": "web", "source": "bing"})
    
    return results, None


def startpage_search(query: str, num_results: int = 8) -> tuple:
    """Search via Startpage (privacy search engine)."""
    import urllib.request
    import urllib.parse
    url = f"https://www.startpage.com/do/search?q={urllib.parse.quote(query)}&lui=english"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15, context=_UNVERIFIED_SSL) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return [], str(e)

    results = []
    pattern = re.compile(r'<div class="result[^"]*"[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*class="title[^"]*"[^>]*>(.*?)</a>', re.DOTALL)
    matches = pattern.findall(html)
    for url, title_raw in matches[:num_results]:
        title = unescape(re.sub(r'<[^>]+>', '', title_raw).replace('\n', ' ').strip())
        results.append({"title": title, "url": url, "snippet": "", "type": "web", "source": "startpage"})
    return results, None


def search_engines(query: str, limit: int = 10) -> List[Dict]:
    """
    Search multiple engines and return merged results.
    This is the main search function that combines all free search engines.
    """
    if not query or not query.strip():
        return []
    
    query = query.strip()
    all_results = []
    errors = []

    # Try academic search first for relevant queries
    academic_keywords = ["paper", "research", "arxiv", "study", "algorithm",
                        "neural", "learning", "deep learning", "model architecture",
                        "transformer", "llm", "machine learning", "ai model",
                        "academic", "scientific", "journal", "conference"]
    is_academic = any(k in query.lower() for k in academic_keywords)

    if is_academic:
        arxiv_results, err = arxiv_search(query, max_results=5)
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
    if len(all_results) < 3:
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

    # Add relevance scores
    for i, result in enumerate(all_results):
        result['rank'] = i
        result['search_query'] = query
        result['timestamp'] = datetime.now().isoformat()
    
    logger.info(f"Search for '{query}' returned {len(all_results)} results")
    return all_results[:limit]


# ============================================================================
# WEB FETCHING (from ilma_free_webfetch.py + enhanced)
# ============================================================================

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

import urllib.request
import urllib.parse
import urllib.error


def fetch_url(url: str, timeout: int = 20) -> Dict[str, Any]:
    """Fetch a URL and return raw data."""
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout, context=_UNVERIFIED_SSL) as resp:
            raw_html = resp.read()
            content_type = resp.headers.get("Content-Type", "text/html")
            encoding = "utf-8"
            if "charset=" in content_type:
                encoding = content_type.split("charset=")[-1].split(";")[0].strip()
            html = raw_html.decode(encoding, errors="replace")
            return {"html": html, "url": url, "status": "success"}
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.reason}", "url": url, "status": "error"}
    except Exception as e:
        return {"error": str(e), "url": url, "status": "error"}


def retry_fetch(url: str, max_retries: int = 3, delay: float = 1.0) -> Dict[str, Any]:
    """Fetch a URL with retry logic."""
    for attempt in range(max_retries):
        result = fetch_url(url)
        if result.get("status") == "success":
            return result
        logger.warning(f"Attempt {attempt + 1}/{max_retries} failed for {url}: {result.get('error', 'Unknown error')}")
        if attempt < max_retries - 1:
            time.sleep(delay * (attempt + 1))
    return {"error": f"Failed after {max_retries} attempts", "url": url, "status": "error"}


def extract_structured(url: str) -> Dict[str, Any]:
    """
    Extract structured data from a URL.
    Similar to Tavily's structured extraction.
    
    Returns:
        Dictionary with title, content, links, images, meta info, etc.
    """
    result = retry_fetch(url)
    
    if result.get("status") != "success":
        return result
    
    html = result.get("html", "")
    
    if not BS4_AVAILABLE:
        return fallback_parse(html, url)
    
    soup = BeautifulSoup(html, "lxml")
    
    # Remove scripts, styles, nav, footer
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "iframe"]):
        tag.decompose()
    
    # Extract title
    title = ""
    if soup.title:
        title = soup.title.string or ""
    title = unescape(title.strip())
    
    # Meta description
    meta_desc = ""
    meta_tag = soup.find("meta", attrs={"name": "description"})
    if meta_tag:
        meta_desc = meta_tag.get("content", "")
    
    # Meta keywords
    meta_keywords = ""
    keywords_tag = soup.find("meta", attrs={"name": "keywords"})
    if keywords_tag:
        meta_keywords = keywords_tag.get("content", "")
    
    # Open Graph tags
    og_data = {}
    for tag in soup.find_all("meta", property=re.compile(r"^og:")):
        og_data[tag.get("property", "").replace("og:", "")] = tag.get("content", "")
    
    # Main content extraction
    main = soup.find("main") or soup.find("article") or soup.find("div", class_=re.compile(r"content|article|post|entry|main|body")) or soup.body or soup
    
    # Get text content with hierarchy
    content_sections = []
    for tag in main.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote"]):
        text = tag.get_text(strip=True)
        if len(text) > 10:
            tag_name = tag.name
            content_sections.append({
                "type": tag_name,
                "text": text,
                "level": int(tag_name[1]) if tag_name.startswith("h") and len(tag_name) == 2 else 0
            })
    
    content_text = "\n\n".join([s["text"] for s in content_sections])
    
    # Extract images
    images = []
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src", "")
        alt = img.get("alt", "")
        if src and src.startswith("http"):
            images.append({"url": src, "alt": alt})
    
    # Extract links with context
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True)
        if href.startswith("http") and text and len(text) > 2:
            links.append({"url": href, "text": text[:100]})
    
    # Extract emails
    emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', html)
    
    # Extract phone numbers
    phones = re.findall(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', html)
    
    # Calculate content quality score
    quality_score = calculate_content_quality(content_sections, images, links)
    
    structured = {
        "url": url,
        "title": title,
        "meta_description": meta_desc,
        "meta_keywords": meta_keywords,
        "og_data": og_data,
        "content_text": content_text,
        "content_sections": content_sections,
        "images": images[:20],
        "links": links[:30],
        "emails": list(set(emails))[:10],
        "phones": list(set(phones))[:10],
        "images_count": len(images),
        "links_count": len(links),
        "quality_score": quality_score,
        "fetch_status": "success",
        "timestamp": datetime.now().isoformat()
    }
    
    return structured


def calculate_content_quality(sections: List[Dict], images: List, links: List) -> float:
    """Calculate a quality score for the content (0-100)."""
    score = 50.0  # Base score
    
    # Length bonus
    text_length = sum(len(s['text']) for s in sections)
    if text_length > 5000:
        score += 20
    elif text_length > 2000:
        score += 15
    elif text_length > 1000:
        score += 10
    elif text_length > 500:
        score += 5
    
    # Structure bonus
    headings = [s for s in sections if s['type'].startswith('h')]
    if len(headings) >= 5:
        score += 10
    elif len(headings) >= 3:
        score += 5
    
    # Media bonus
    if len(images) >= 5:
        score += 10
    elif len(images) >= 2:
        score += 5
    
    # Link quality
    if len(links) >= 10:
        score += 5
    elif len(links) == 0:
        score -= 5
    
    return min(100, max(0, score))


def fallback_parse(html: str, url: str) -> Dict[str, Any]:
    """Fallback parser without BeautifulSoup."""
    title_m = re.search(r"<title>(.*?)</title>", html, re.DOTALL | re.IGNORECASE)
    title = unescape(title_m.group(1).replace("\n", " ").strip()) if title_m else "No title"
    
    text_m = re.findall(r"<p[^>]*>(.*?)</p>", html, re.DOTALL | re.IGNORECASE)
    text = "\n".join(unescape(re.sub(r"<[^>]+>", "", p)) for p in text_m[:20])
    
    return {
        "url": url,
        "title": title,
        "meta_description": "",
        "content_text": text[:3000],
        "content_sections": [],
        "images": [],
        "links": [],
        "emails": [],
        "phones": [],
        "images_count": 0,
        "links_count": 0,
        "quality_score": 30,
        "fetch_status": "success",
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# SITEMAP DISCOVERY (Firecrawl-like)
# ============================================================================

def discover_sitemap(url: str) -> List[str]:
    """
    Discover URLs from sitemap.xml.
    Falls back to robots.txt if no sitemap found.
    """
    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    
    # Try common sitemap locations
    sitemap_urls = [
        f"{base_url}/sitemap.xml",
        f"{base_url}/sitemap_index.xml",
        f"{base_url}/wp-sitemap.xml",
        f"{base_url}/sitemap/index.xml",
    ]
    
    all_urls = []
    
    for sitemap_url in sitemap_urls:
        urls = parse_sitemap(sitemap_url)
        if urls:
            all_urls.extend(urls)
            logger.info(f"Found {len(urls)} URLs in {sitemap_url}")
            break
    
    # If no sitemap, try robots.txt
    if not all_urls:
        robots_url = f"{base_url}/robots.txt"
        robots_urls = parse_robots_txt(robots_url)
        if robots_urls:
            all_urls.extend(robots_urls)
            logger.info(f"Found {len(robots_urls)} URLs in robots.txt")
    
    return list(set(all_urls))


def parse_sitemap(sitemap_url: str) -> List[str]:
    """Parse XML sitemap and return list of URLs."""
    result = retry_fetch(sitemap_url)
    if result.get("status") != "success":
        return []
    
    try:
        root = ET.fromstring(result.get("html", ""))
        # Handle XML namespaces
        ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        
        urls = []
        # Try with namespace first
        for loc in root.findall('.//sm:loc', ns):
            if loc.text:
                urls.append(loc.text.strip())
        
        # Fallback: try without namespace
        if not urls:
            for loc in root.iter():
                if 'loc' in loc.tag.lower() and loc.text:
                    urls.append(loc.text.strip())
        
        return urls
    except ET.ParseError as e:
        logger.warning(f"Failed to parse sitemap {sitemap_url}: {e}")
        return []


def parse_robots_txt(robots_url: str) -> List[str]:
    """Parse robots.txt for sitemap directives."""
    result = retry_fetch(robots_url)
    if result.get("status") != "success":
        return []
    
    urls = []
    for line in result.get("html", "").split("\n"):
        line = line.strip()
        if line.lower().startswith("sitemap:"):
            sitemap_url = line.split(":", 1)[1].strip()
            urls.append(sitemap_url)
    
    return urls


def discover_subdomains(domain: str) -> List[str]:
    """Discover related subdomains for a domain."""
    # Common subdomains to check
    common_subdomains = ["www", "api", "blog", "dev", "test", "stage", "app", "admin", "shop", "docs"]
    
    discovered = []
    for subdomain in common_subdomains:
        url = f"https://{subdomain}.{domain}"
        result = retry_fetch(url)
        if result.get("status") == "success":
            discovered.append(url)
    
    return discovered


# ============================================================================
# SUMMARIZATION (Local Heuristics - No API Required)
# ============================================================================

def summarize_content(text: str, max_length: int = 500) -> str:
    """
    Summarize content using local heuristics (no API needed).
    Uses extractive summarization based on sentence importance.
    """
    if not text or len(text) < 100:
        return text
    
    # Split into sentences
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
    
    if len(sentences) <= 3:
        return text[:max_length] + "..." if len(text) > max_length else text
    
    # Score sentences by importance
    scored = []
    for i, sentence in enumerate(sentences):
        score = 0
        words = sentence.lower().split()
        
        # Position score (first and last sentences are important)
        if i == 0 or i == len(sentences) - 1:
            score += 3
        
        # Length score (prefer medium-length sentences)
        if 50 <= len(sentence) <= 150:
            score += 2
        
        # Keyword density (important words)
        important_words = ["important", "significant", "key", "main", "primary", "essential",
                          "result", "conclusion", "summary", "found", "discovered", "showed",
                          "however", "therefore", "thus", "because", "effect", "impact"]
        score += sum(1 for word in words if word in important_words)
        
        # Repetition bonus (shows depth)
        unique_ratio = len(set(words)) / max(len(words), 1)
        score += int(unique_ratio * 2)
        
        scored.append((score, i, sentence))
    
    # Sort by score and get top sentences
    scored.sort(reverse=True)
    top_sentences = scored[:4]
    
    # Reconstruct in original order
    top_sentences.sort(key=lambda x: x[1])
    
    summary = " ".join([s[2] for s in top_sentences])
    return summary[:max_length] + "..." if len(summary) > max_length else summary


def extract_key_points(text: str, max_points: int = 5) -> List[str]:
    """Extract key points from content."""
    if not text:
        return []
    
    # Split into sentences
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 30]
    
    # Score each sentence
    scored = []
    for sentence in sentences:
        score = 0
        words = set(sentence.lower().split())
        
        # Score based on sentence length
        if 50 <= len(sentence) <= 200:
            score += 2
        
        # Bonus for sentences with numbers (data-driven)
        if re.search(r'\d+', sentence):
            score += 2
        
        # Bonus for sentences with key terms
        key_terms = ["result", "found", "show", "demonstrate", "report", "study", 
                     "research", "data", "analysis", "conclusion", "evidence"]
        score += sum(1 for term in key_terms if term in sentence.lower())
        
        scored.append((score, sentence))
    
    scored.sort(reverse=True)
    return [s[1] for s in scored[:max_points]]


def extract_facts(text: str) -> List[Dict[str, str]]:
    """Extract factual statements with context."""
    facts = []
    
    # Patterns for factual statements
    patterns = [
        (r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:is|are|was|were)\s+([^.!?]+)', 'definition'),
        (r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:reported|announced|revealed|launched)\s+([^.!?]+)', 'announcement'),
        (r'(\d+(?:\.\d+)?)\s*(%|percent|million|billion|thousand)?\s+([^.!?]+)', 'statistic'),
    ]
    
    for pattern, fact_type in patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            if len(match.groups()) >= 2:
                facts.append({
                    "type": fact_type,
                    "subject": match.group(1) if match.group(1) else match.group(0)[:50],
                    "detail": match.group(2) if match.group(2) else match.group(0),
                    "full_match": match.group(0)[:200]
                })
    
    return facts[:20]  # Limit to 20 facts


# ============================================================================
# SEMANTIC SEARCH (Exa-like keyword + relevance)
# ============================================================================

def semantic_search(query: str, documents: List[Dict], limit: int = 10) -> List[Dict]:
    """
    Perform semantic/keyword search on documents.
    Similar to Exa's relevance search.
    """
    if not documents or not query:
        return []
    
    # Expand query with synonyms
    query_terms = expand_query_terms(query)
    
    scored_docs = []
    for doc in documents:
        content = doc.get("content_text", "") + " " + doc.get("title", "")
        content_lower = content.lower()
        
        score = 0
        matched_terms = []
        
        for term in query_terms:
            term_lower = term.lower()
            
            # Title matches are worth more
            title = doc.get("title", "").lower()
            if term_lower in title:
                score += 10
                matched_terms.append(term)
            elif term_lower in content_lower:
                # Count occurrences
                count = content_lower.count(term_lower)
                score += min(count, 5)  # Cap at 5 per term
                if count > 0:
                    matched_terms.append(term)
        
        if score > 0:
            # Normalize by content length
            normalized_score = score / (len(content.split()) + 1) * 100
            scored_docs.append({
                "document": doc,
                "relevance_score": round(normalized_score, 2),
                "matched_terms": list(set(matched_terms)),
                "raw_score": score
            })
    
    # Sort by relevance score
    scored_docs.sort(key=lambda x: x["relevance_score"], reverse=True)
    
    return scored_docs[:limit]


def expand_query_terms(query: str) -> List[str]:
    """Expand query with related terms for better matching."""
    # Basic expansion (could be enhanced with word embeddings)
    terms = query.lower().split()
    
    # Common expansions
    expansions = {
        "ai": ["artificial intelligence", "machine learning", "ml"],
        "ml": ["machine learning", "ai", "deep learning"],
        "dl": ["deep learning", "neural network", "ai"],
        "llm": ["large language model", "nlp", "transformer"],
        "nlp": ["natural language processing", "text", "language"],
        "cv": ["computer vision", "image", "visual"],
        "data": ["dataset", "data science", "analytics"],
        "research": ["study", "paper", "academic"],
        "news": ["article", "update", "latest"],
        "tech": ["technology", "technical", "it"],
    }
    
    expanded = list(terms)
    for term in terms:
        if term in expansions:
            expanded.extend(expansions[term])
    
    return list(set(expanded))


# ============================================================================
# MAIN FUNCTIONS
# ============================================================================

def crawl_urls(url_list: List[str]) -> List[Dict]:
    """
    Crawl multiple URLs and extract structured data.
    Includes retry logic and error handling.
    """
    results = []
    for url in url_list:
        logger.info(f"Crawling: {url}")
        try:
            data = extract_structured(url)
            if data.get("fetch_status") == "success":
                results.append(data)
                logger.info(f"Successfully crawled: {url}")
            else:
                results.append({
                    "url": url,
                    "error": data.get("error", "Unknown error"),
                    "fetch_status": "failed"
                })
                logger.warning(f"Failed to crawl {url}: {data.get('error')}")
        except Exception as e:
            logger.error(f"Exception crawling {url}: {e}")
            results.append({
                "url": url,
                "error": str(e),
                "fetch_status": "failed"
            })
    return results


def deep_search(query: str, limit: int = 10) -> Dict[str, Any]:
    """
    Search for query and fetch top results.
    Full pipeline: search → rank → fetch top N
    """
    logger.info(f"Deep search: '{query}' (limit={limit})")
    
    # Step 1: Search for URLs
    search_results = search_engines(query, limit=limit * 2)  # Get extra in case some fail
    
    if not search_results:
        return {
            "query": query,
            "status": "no_results",
            "results": [],
            "timestamp": datetime.now().isoformat()
        }
    
    # Step 2: Extract URLs
    urls = [r["url"] for r in search_results[:limit]]
    
    # Step 3: Crawl URLs
    crawled = crawl_urls(urls)
    
    # Step 4: Merge results
    merged_results = []
    for i, result in enumerate(crawled):
        if result.get("fetch_status") == "success":
            # Find matching search result
            search_result = search_results[i] if i < len(search_results) else {}
            merged = {
                **result,
                "search_title": search_result.get("title", ""),
                "search_snippet": search_result.get("snippet", ""),
                "search_type": search_result.get("type", "web"),
                "search_source": search_result.get("source", "unknown"),
                "original_rank": search_result.get("rank", i)
            }
            merged_results.append(merged)
        else:
            merged_results.append({
                "url": result.get("url"),
                "error": result.get("error"),
                "fetch_status": "failed",
                "search_title": search_results[i].get("title", "") if i < len(search_results) else "",
                "search_snippet": search_results[i].get("snippet", "") if i < len(search_results) else "",
            })
    
    # Calculate aggregate statistics
    successful = [r for r in merged_results if r.get("fetch_status") == "success"]
    failed = len(merged_results) - len(successful)
    
    return {
        "query": query,
        "status": "complete",
        "results": merged_results,
        "total_results": len(merged_results),
        "successful_crawls": len(successful),
        "failed_crawls": failed,
        "timestamp": datetime.now().isoformat()
    }


def search_and_scrape(query: str, limit: int = 10) -> Dict[str, Any]:
    """
    Full pipeline: search → scrape → extract structured data → summarize.
    This is the main function that replaces Tavily's search+extract.
    """
    logger.info(f"Search and scrape: '{query}' (limit={limit})")
    
    # Run deep search
    deep_result = deep_search(query, limit)
    
    if not deep_result.get("results"):
        return deep_result
    
    # Enhance with summaries and key points
    for result in deep_result["results"]:
        if result.get("fetch_status") == "success":
            # Add summary
            result["summary"] = summarize_content(result.get("content_text", ""), max_length=300)
            
            # Add key points
            result["key_points"] = extract_key_points(result.get("content_text", ""), max_points=5)
            
            # Add facts
            result["facts"] = extract_facts(result.get("content_text", ""))
    
    # Save to cache
    cache_file = os.path.join(CACHE_DIR, f"search_scrape_{hashlib.md5(query.encode()).hexdigest()}.json")
    try:
        with open(cache_file, 'w') as f:
            json.dump(deep_result, f, indent=2, default=str)
        logger.info(f"Results saved to {cache_file}")
    except Exception as e:
        logger.error(f"Failed to save cache: {e}")
    
    return deep_result


def get_competitor_analysis(domain: str) -> Dict[str, Any]:
    """
    Perform competitor analysis for a domain.
    Similar to Firecrawl's site analysis.
    """
    logger.info(f"Competitor analysis for: {domain}")
    
    # Ensure domain has scheme
    if not domain.startswith(("http://", "https://")):
        domain = f"https://{domain}"
    
    parsed = urlparse(domain)
    base_domain = parsed.netloc or parsed.path
    
    analysis = {
        "target_domain": base_domain,
        "timestamp": datetime.now().isoformat(),
        "status": "in_progress"
    }
    
    # Step 1: Discover URLs from sitemap
    discovered_urls = discover_sitemap(domain)
    analysis["discovered_urls_count"] = len(discovered_urls)
    analysis["discovered_urls"] = discovered_urls[:50]  # Limit for output
    
    # Step 2: Crawl main page and key pages
    pages_to_crawl = [domain] + discovered_urls[:10]
    crawled_pages = crawl_urls(pages_to_crawl)
    
    successful_crawls = [p for p in crawled_pages if p.get("fetch_status") == "success"]
    analysis["crawled_pages"] = len(successful_crawls)
    
    # Step 3: Extract key information
    main_page = successful_crawls[0] if successful_crawls else {}
    
    analysis["main_page"] = {
        "title": main_page.get("title", ""),
        "meta_description": main_page.get("meta_description", ""),
        "content_length": len(main_page.get("content_text", "")),
        "images_count": main_page.get("images_count", 0),
        "links_count": main_page.get("links_count", 0),
        "quality_score": main_page.get("quality_score", 0)
    }
    
    # Step 4: Find external links (potential competitors/partners)
    all_links = []
    for page in successful_crawls:
        all_links.extend(page.get("links", []))
    
    # Categorize links
    internal_links = []
    external_links = []
    for link in all_links:
        if base_domain in link.get("url", ""):
            internal_links.append(link)
        else:
            external_links.append(link)
    
    analysis["links"] = {
        "total": len(all_links),
        "internal": len(internal_links),
        "external": len(external_links),
        "external_samples": external_links[:20]
    }
    
    # Step 5: Extract emails and phones
    all_emails = set()
    all_phones = set()
    for page in successful_crawls:
        all_emails.update(page.get("emails", []))
        all_phones.update(page.get("phones", []))
    
    analysis["contact_info"] = {
        "emails": list(all_emails)[:10],
        "phones": list(all_phones)[:10]
    }
    
    # Step 6: Content analysis
    all_content = " ".join([p.get("content_text", "") for p in successful_crawls])
    
    if all_content:
        analysis["content_analysis"] = {
            "total_text_length": len(all_content),
            "summary": summarize_content(all_content, max_length=500),
            "key_points": extract_key_points(all_content, max_points=10),
            "facts": extract_facts(all_content)[:10]
        }
    
    # Step 7: Discover subdomains
    subdomains = discover_subdomains(base_domain)
    analysis["subdomains"] = {
        "discovered": subdomains,
        "count": len(subdomains)
    }
    
    analysis["status"] = "complete"
    
    # Save to cache
    cache_file = os.path.join(CACHE_DIR, f"competitor_{hashlib.md5(base_domain.encode()).hexdigest()}.json")
    try:
        with open(cache_file, 'w') as f:
            json.dump(analysis, f, indent=2, default=str)
        logger.info(f"Competitor analysis saved to {cache_file}")
    except Exception as e:
        logger.error(f"Failed to save cache: {e}")
    
    return analysis


def batch_crawl(urls: List[str], parallel: int = 5) -> List[Dict]:
    """
    Batch crawl multiple URLs concurrently.
    Similar to Firecrawl's batch crawling.
    """
    logger.info(f"Batch crawl: {len(urls)} URLs (parallel={parallel})")
    
    results = []
    
    with ThreadPoolExecutor(max_workers=parallel) as executor:
        future_to_url = {executor.submit(extract_structured, url): url for url in urls}
        
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                result = future.result()
                results.append(result)
                if result.get("fetch_status") == "success":
                    logger.info(f"Successfully crawled: {url}")
                else:
                    logger.warning(f"Failed to crawl {url}")
            except Exception as e:
                logger.error(f"Exception for {url}: {e}")
                results.append({
                    "url": url,
                    "error": str(e),
                    "fetch_status": "failed"
                })
    
    return results


def sitemap_discovery(url: str) -> Dict[str, Any]:
    """
    Discover all URLs from a site's sitemap.
    """
    logger.info(f"Sitemap discovery for: {url}")
    
    # Ensure URL has scheme
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    
    urls = discover_sitemap(url)
    
    result = {
        "base_url": url,
        "discovered_urls": urls,
        "count": len(urls),
        "timestamp": datetime.now().isoformat()
    }
    
    # Categorize URLs
    url_types = {"html": [], "other": []}
    for discovered_url in urls:
        if discovered_url.endswith((".html", "/")):
            url_types["html"].append(discovered_url)
        else:
            url_types["other"].append(discovered_url)
    
    result["url_types"] = {
        "html_pages": len(url_types["html"]),
        "other": len(url_types["other"])
    }
    
    return result


# ============================================================================
# CLI INTERFACE
# ============================================================================

def format_results_markdown(results: Dict) -> str:
    """Format search results as markdown."""
    output = f"# Research Results: {results.get('query', 'N/A')}\n\n"
    output += f"**Status:** {results.get('status', 'unknown')}\n"
    output += f"**Timestamp:** {results.get('timestamp', 'N/A')}\n"
    output += f"**Total Results:** {results.get('total_results', len(results.get('results', [])))}\n\n"
    
    if results.get('successful_crawls') is not None:
        output += f"**Successful Crawls:** {results.get('successful_crawls', 0)}\n"
        output += f"**Failed Crawls:** {results.get('failed_crawls', 0)}\n\n"
    
    output += "---\n\n"
    
    for i, r in enumerate(results.get("results", []), 1):
        if r.get("fetch_status") == "success":
            output += f"## {i}. {r.get('title', r.get('search_title', 'N/A'))}\n\n"
            output += f"**URL:** {r.get('url', 'N/A')}\n"
            if r.get("search_snippet"):
                output += f"**Snippet:** _{r.get('search_snippet', '')[:200]}_\n"
            if r.get("summary"):
                output += f"\n**Summary:** {r.get('summary', '')}\n"
            if r.get("key_points"):
                output += "\n**Key Points:**\n"
                for point in r.get("key_points", []):
                    output += f"- {point}\n"
            if r.get("facts"):
                output += "\n**Facts:**\n"
                for fact in r.get("facts", [])[:5]:
                    output += f"- [{fact.get('type', 'info').upper()}] {fact.get('full_match', '')[:150]}\n"
            output += f"\n**Quality Score:** {r.get('quality_score', 0)}/100\n"
            output += f"**Images:** {r.get('images_count', 0)} | **Links:** {r.get('links_count', 0)}\n"
        else:
            output += f"## {i}. FAILED: {r.get('url', 'N/A')}\n\n"
            output += f"**Error:** {r.get('error', 'Unknown error')}\n"
        output += "\n---\n\n"
    
    return output


def format_competitor_markdown(analysis: Dict) -> str:
    """Format competitor analysis as markdown."""
    output = f"# Competitor Analysis: {analysis.get('target_domain', 'N/A')}\n\n"
    output += f"**Status:** {analysis.get('status', 'unknown')}\n"
    output += f"**Timestamp:** {analysis.get('timestamp', 'N/A')}\n\n"
    
    output += "## Site Overview\n\n"
    main_page = analysis.get("main_page", {})
    output += f"- **Title:** {main_page.get('title', 'N/A')}\n"
    output += f"- **Description:** {main_page.get('meta_description', 'N/A')[:200]}\n"
    output += f"- **Content Length:** {main_page.get('content_length', 0):,} characters\n"
    output += f"- **Quality Score:** {main_page.get('quality_score', 0)}/100\n"
    output += f"- **Images:** {main_page.get('images_count', 0)}\n"
    output += f"- **Links:** {main_page.get('links_count', 0)}\n\n"
    
    output += "## URL Discovery\n\n"
    output += f"- **Discovered URLs:** {analysis.get('discovered_urls_count', 0)}\n"
    output += f"- **Crawled Pages:** {analysis.get('crawled_pages', 0)}\n\n"
    
    if analysis.get("discovered_urls"):
        output += "### Sample URLs\n"
        for url in analysis["discovered_urls"][:10]:
            output += f"- {url}\n"
        output += "\n"
    
    output += "## Link Analysis\n\n"
    links = analysis.get("links", {})
    output += f"- **Total Links:** {links.get('total', 0)}\n"
    output += f"- **Internal Links:** {links.get('internal', 0)}\n"
    output += f"- **External Links:** {links.get('external', 0)}\n\n"
    
    if links.get("external_samples"):
        output += "### External Link Samples\n"
        for link in links["external_samples"][:5]:
            output += f"- [{link.get('text', 'N/A')}]({link.get('url', '')})\n"
        output += "\n"
    
    output += "## Contact Information\n\n"
    contact = analysis.get("contact_info", {})
    if contact.get("emails"):
        output += "**Emails:**\n"
        for email in contact["emails"][:5]:
            output += f"- {email}\n"
    if contact.get("phones"):
        output += "\n**Phones:**\n"
        for phone in contact["phones"][:5]:
            output += f"- {phone}\n"
    output += "\n"
    
    if analysis.get("content_analysis"):
        content = analysis["content_analysis"]
        output += "## Content Analysis\n\n"
        output += f"**Total Text:** {content.get('total_text_length', 0):,} characters\n"
        if content.get("summary"):
            output += f"\n**Summary:** {content.get('summary', '')}\n"
        if content.get("key_points"):
            output += "\n**Key Points:**\n"
            for point in content["key_points"][:10]:
                output += f"- {point}\n"
    
    if analysis.get("subdomains", {}).get("discovered"):
        output += "\n## Subdomains\n\n"
        for subdomain in analysis["subdomains"]["discovered"]:
            output += f"- {subdomain}\n"
    
    return output


def main():
    parser = argparse.ArgumentParser(
        description="ILMA Free Research Pipeline - 100%% FREE alternative to Firecrawl, Tavily, and Exa",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Search and get top results
  python3 ilma_free_research_pipeline.py --query "artificial intelligence news"
  
  # Crawl a single URL
  python3 ilma_free_research_pipeline.py --crawl "https://example.com"
  
  # Batch crawl from file (one URL per line)
  python3 ilma_free_research_pipeline.py --batch urls.txt
  
  # Extract structured data from URL
  python3 ilma_free_research_pipeline.py --extract "https://example.com"
  
  # Sitemap discovery
  python3 ilma_free_research_pipeline.py --sitemap "https://example.com"
  
  # Competitor analysis
  python3 ilma_free_research_pipeline.py --competitor "example.com"
  
  # Search and scrape (full pipeline)
  python3 ilma_free_research_pipeline.py --search-scrape "AI research" --limit 10

Examples as module:
  from ilma_free_research_pipeline import deep_search, crawl_urls, get_competitor_analysis
  results = deep_search("AI research", limit=10)
  crawled = crawl_urls(["https://example.com", "https://example.org"])
  analysis = get_competitor_analysis("example.com")
        """
    )
    
    parser.add_argument("--query", "-q", type=str, help="Search query")
    parser.add_argument("--crawl", "-c", type=str, help="Crawl a single URL")
    parser.add_argument("--batch", "-b", type=str, help="Batch crawl URLs from file")
    parser.add_argument("--extract", "-e", type=str, help="Extract structured data from URL")
    parser.add_argument("--sitemap", "-s", type=str, help="Discover URLs from sitemap")
    parser.add_argument("--competitor", type=str, help="Perform competitor analysis")
    parser.add_argument("--search-scrape", type=str, dest="search_scrape", help="Search and scrape")
    parser.add_argument("--limit", "-l", type=int, default=10, help="Result limit (default: 10)")
    parser.add_argument("--parallel", "-p", type=int, default=5, help="Parallel workers for batch (default: 5)")
    parser.add_argument("--output", "-o", type=str, help="Output file (default: stdout)")
    parser.add_argument("--format", "-f", choices=["markdown", "json"], default="markdown", help="Output format")
    
    args = parser.parse_args()
    
    output = None
    
    try:
        if args.query:
            # Simple search
            results = search_engines(args.query, limit=args.limit)
            output = json.dumps(results, indent=2, default=str)
            
        elif args.crawl:
            # Crawl single URL
            result = extract_structured(args.crawl)
            output = json.dumps(result, indent=2, default=str)
            
        elif args.batch:
            # Batch crawl from file
            with open(args.batch, 'r') as f:
                urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            results = batch_crawl(urls, parallel=args.parallel)
            output = json.dumps(results, indent=2, default=str)
            
        elif args.extract:
            # Extract structured data
            result = extract_structured(args.extract)
            output = json.dumps(result, indent=2, default=str)
            
        elif args.sitemap:
            # Sitemap discovery
            result = sitemap_discovery(args.sitemap)
            output = json.dumps(result, indent=2, default=str)
            
        elif args.competitor:
            # Competitor analysis
            result = get_competitor_analysis(args.competitor)
            output = format_competitor_markdown(result)
            
        elif args.search_scrape:
            # Full search and scrape pipeline
            result = search_and_scrape(args.search_scrape, limit=args.limit)
            output = format_results_markdown(result)
            
        else:
            parser.print_help()
            return
        
        # Output results
        if args.output:
            with open(args.output, 'w') as f:
                f.write(output)
            print(f"Results saved to {args.output}")
        else:
            print(output)
            
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Error: {e}")
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
