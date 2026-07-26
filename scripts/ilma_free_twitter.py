#!/usr/bin/env python3
"""
ILMA FREE TWITTER — Native X/Twitter Search (100% FREE)
Replaces: felo-x-search (API felo.ai)

HOW IT WORKS:
  1. Browser → nitter.net (free, no auth) for tweets
  2. Fallback: browser → x.com/search (requires JS)
  3. Extract tweet data via BeautifulSoup

USAGE:
  python3 ilma_free_twitter.py search "AI news" --limit 10
  python3 ilma_free_twitter.py user elonmusk --tweets 5
"""

import sys
import re
import json
from html import unescape

# Use Hermes browser tool via subprocess
def run_hermes_browser(url: str) -> str:
    """Use hermes browser tool via CLI."""
    import subprocess
    result = subprocess.run(
        ["hermes", "browser", "navigate", url],
        capture_output=True, text=True, timeout=30
    )
    return result.stdout + result.stderr


def nitter_search(query: str, limit: int = 10) -> list:
    """
    Search tweets via nitter.net (free, no auth).
    Nitter is an open-source Twitter front-end.
    Falls back to xcancel.com if nitter.net returns empty.
    """
    import urllib.request
    import urllib.parse

    # Try multiple nitter instances
    instances = [
        ("nitter.net", "https://nitter.net"),
        ("xcancel.com", "https://xcancel.com"),
    ]

    html = None
    error_msg = ""
    for name, base_url in instances:
        search_url = f"{base_url}/search?f=tweets&q={urllib.parse.quote(query)}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        }
        try:
            req = urllib.request.Request(search_url, headers=headers)
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
                raw = resp.read()
                if len(raw) < 500:
                    error_msg += f"{name} returned too little data ({len(raw)} bytes). "
                    continue
                html = raw.decode("utf-8", errors="replace")
                break
        except Exception as e:
            error_msg += f"{name} error: {e}. "

    if html is None:
        return [], error_msg or "All nitter instances failed"

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")
    tweets = []

    # Nitter structure: <div class="timeline-item">
    items = soup.find_all("div", class_="timeline-item")
    for item in items[:limit]:
        # Extract username
        username_el = item.find("a", class_="username")
        username = username_el.get_text(strip=True) if username_el else ""

        # Extract full name
        fullname_el = item.find("span", class_="fullname")
        fullname = fullname_el.get_text(strip=True) if fullname_el else ""

        # Extract tweet content
        content_el = item.find("div", class_="tweet-content")
        content = content_el.get_text(strip=True) if content_el else ""

        # Extract timestamp
        time_el = item.find("a", class_="timestamp")
        timestamp = time_el.get_text(strip=True) if time_el else ""
        if time_el and time_el.get("href"):
            link = "https://nitter.net" + time_el["href"]
        else:
            link = ""

        # Extract engagement
        stats = {}
        for stat in item.find_all("span", class_="tweet-stat"):
            icon = stat.find("i") or stat.find("span", class_="tweet-stat-icon")
            val = stat.get_text(strip=True)
            if icon:
                icon_class = icon.get("class", [])
                if "replies" in icon_class:
                    stats["replies"] = val
                elif "retweets" in icon_class:
                    stats["retweets"] = val
                elif "likes" in icon_class:
                    stats["likes"] = val

        if content:
            tweets.append({
                "username": username,
                "fullname": fullname,
                "content": content,
                "timestamp": timestamp,
                "link": link,
                "stats": stats
            })

    return tweets, None


def nitter_user_tweets(username: str, limit: int = 10) -> list:
    """Get tweets from a specific user via nitter."""
    import urllib.request

    # Clean username
    username = username.lstrip("@")

    # Try multiple instances
    instances = [
        ("nitter.net", "https://nitter.net"),
        ("xcancel.com", "https://xcancel.com"),
    ]

    html = None
    error_msg = ""
    for name, base_url in instances:
        url = f"{base_url}/{username}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        }
        try:
            req = urllib.request.Request(url, headers=headers)
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
                raw = resp.read()
                if len(raw) < 500:
                    error_msg += f"{name} returned too little data ({len(raw)} bytes). "
                    continue
                html = raw.decode("utf-8", errors="replace")
                break
        except Exception as e:
            error_msg += f"{name} error: {e}. "

    if html is None:
        return [], error_msg or "All nitter instances failed"

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")
    tweets = []

    items = soup.find_all("div", class_="timeline-item")
    for item in items[:limit]:
        content_el = item.find("div", class_="tweet-content")
        content = content_el.get_text(strip=True) if content_el else ""

        time_el = item.find("a", class_="timestamp")
        timestamp = time_el.get_text(strip=True) if time_el else ""
        link = f"https://nitter.net/{username}" + (time_el["href"] if time_el else "")

        stats = {}
        for stat in item.find_all("span", class_="tweet-stat"):
            icon = stat.find("i") or stat.find("span", class_="tweet-stat-icon")
            val = stat.get_text(strip=True)
            if icon:
                ic = icon.get("class", [])
                if "replies" in ic: stats["replies"] = val
                elif "retweets" in ic: stats["retweets"] = val
                elif "likes" in ic: stats["likes"] = val

        if content:
            tweets.append({
                "username": f"@{username}",
                "content": content,
                "timestamp": timestamp,
                "link": link,
                "stats": stats
            })

    return tweets, None


def format_tweets(tweets: list, mode: str = "search", query: str = "") -> str:
    """Format tweets as markdown."""
    header = f"## 🐦 Twitter Search: {query}" if mode == "search" else f"## 🐦 @{query} Tweets"
    output = f"{header}\n\n"

    if not tweets:
        output += "_No tweets found._\n"
        return output

    for i, t in enumerate(tweets, 1):
        output += f"### {i}. {t.get('fullname', '')} {t.get('username', '')}\n"
        output += f"_{t.get('timestamp', 'N/A')}_\n\n"
        output += f"{t.get('content', '')}\n\n"
        stats = t.get("stats", {})
        if stats:
            parts = [f"💬 {stats.get('replies', '0')}", 
                     f"🔁 {stats.get('retweets', '0')}", 
                     f"❤️ {stats.get('likes', '0')}"]
            output += " ".join(parts) + "\n"
        if t.get("link"):
            output += f"🔗 {t['link']}\n"
        output += "\n---\n\n"

    return output


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 ilma_free_twitter.py search <query> [--limit N]")
        print("  python3 ilma_free_twitter.py user <username> [--tweets N]")
        sys.exit(1)

    mode = sys.argv[1].lower()

    # Parse args
    limit = 10
    remaining = sys.argv[2:]
    if "--limit" in remaining:
        idx = remaining.index("--limit")
        limit = int(remaining[idx+1]) if idx+1 < len(remaining) else 10
        remaining = remaining[:idx] + remaining[idx+2:]
    if "--tweets" in remaining:
        idx = remaining.index("--tweets")
        limit = int(remaining[idx+1]) if idx+1 < len(remaining) else 10
        remaining = remaining[:idx] + remaining[idx+2:]

    if not remaining:
        print("❌ Missing query/username")
        sys.exit(1)

    query = remaining[0]

    if mode == "search":
        tweets, err = nitter_search(query, limit)
        print(format_tweets(tweets, "search", query))
    elif mode == "user":
        tweets, err = nitter_user_tweets(query, limit)
        print(format_tweets(tweets, "user", query))
    else:
        print(f"❌ Unknown mode: {mode}")
        sys.exit(1)

    if err:
        print(f"\n⚠️ Error: {err}")


if __name__ == "__main__":
    main()
