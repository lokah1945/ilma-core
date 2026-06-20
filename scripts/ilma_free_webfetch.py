#!/usr/bin/env python3
"""
ILMA FREE WEBFETCH — Native Web Extraction (100% FREE)
Replaces: felo-web-fetch (API felo.ai)

HOW IT WORKS:
  1. requests + BeautifulSoup → fetch any URL
  2. Extract title, meta, main content, images
  3. Convert to markdown/text/html format
  4. No API key needed, no rate limits

USAGE:
  python3 ilma_free_webfetch.py "https://example.com" [--format markdown]
"""

import sys
import re
import ssl
from html import unescape
import urllib.request
import urllib.parse
import urllib.error

_UNVERIFIED_SSL = ssl.create_default_context()
_UNVERIFIED_SSL.check_hostname = False
_UNVERIFIED_SSL.verify_mode = ssl.CERT_NONE

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False


def fetch_url(url: str, format: str = "markdown") -> dict:
    """Fetch and parse a URL, returning structured data."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=20, context=_UNVERIFIED_SSL) as resp:
            raw_html = resp.read()
            content_type = resp.headers.get("Content-Type", "text/html")
            encoding = "utf-8"
            if "charset=" in content_type:
                encoding = content_type.split("charset=")[-1].split(";")[0].strip()
            html = raw_html.decode(encoding, errors="replace")
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.reason}", "url": url}
    except Exception as e:
        return {"error": str(e), "url": url}

    if not BS4_AVAILABLE:
        return fallback_parse(html, url)

    soup = BeautifulSoup(html, "lxml")

    # Remove scripts, styles, nav, footer
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
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

    # Main content extraction
    main = soup.find("main") or soup.find("article") or soup.find("div", class_=re.compile(r"content|article|post|entry")) or soup.body or soup

    # Get text content
    text_parts = []
    for para in main.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6", "li"]):
        t = para.get_text(strip=True)
        if len(t) > 20:  # Skip short fragments
            text_parts.append(t)

    content_text = "\n\n".join(text_parts)

    # Extract images
    images = []
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src", "")
        alt = img.get("alt", "")
        if src and src.startswith("http"):
            images.append({"url": src, "alt": alt})

    # Extract links
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True)
        if href.startswith("http") and text:
            links.append({"url": href, "text": text})

    # Markdown format
    markdown = f"""# {title}

**Source:** {url}

{meta_desc}

---

{content_text[:3000]}

---

**Images:** {len(images)}
**Links:** {len(links)}
"""

    result = {
        "url": url,
        "title": title,
        "meta_description": meta_desc,
        "content_text": content_text,
        "content_markdown": markdown,
        "images": images[:10],
        "links": links[:20],
        "images_count": len(images),
        "links_count": len(links),
        "format": format,
    }
    return result


def fallback_parse(html: str, url: str) -> dict:
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
        "content_markdown": f"# {title}\n\n**Source:** {url}\n\n{text[:3000]}",
        "images": [],
        "links": [],
        "images_count": 0,
        "links_count": 0,
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 ilma_free_webfetch.py <url> [--format markdown|text|html]")
        sys.exit(1)

    url = sys.argv[1]
    format_type = "markdown"
    if "--format" in sys.argv:
        idx = sys.argv.index("--format")
        if idx + 1 < len(sys.argv):
            format_type = sys.argv[idx + 1].lower()

    result = fetch_url(url, format_type)

    if "error" in result:
        print(f"❌ Error: {result['error']}")
        sys.exit(1)

    print(f"## 🌐 {result['title']}")
    print(f"**URL:** {result['url']}")
    if result["meta_description"]:
        print(f"\n_{result['meta_description']}_\n")
    print("---")
    print(result.get(f"content_{format_type}", result["content_text"]))
    print("---")
    print(f"📊 Images: {result['images_count']} | Links: {result['links_count']}")


if __name__ == "__main__":
    main()
