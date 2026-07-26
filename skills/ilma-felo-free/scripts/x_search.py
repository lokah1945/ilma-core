#!/usr/bin/env python3
"""
ILMA_FELO_FREE: Twitter/X Search via Nitter (no API key)
Nitter instances: nitter.net, nitter.privacydev.de, nitter.poast.org
100% free, no authentication needed.
"""

import sys
import urllib.request
import urllib.parse
import re

NITTER_INSTANCES = [
    "https://nitter.net",
    "https://nitter.privacydev.de",
    "https://nitter.poast.org",
]

def fetch_url(url: str, timeout: int = 15) -> str:
    """Fetch URL content with basic headers."""
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; ILMA-FELO-FREE/1.0)",
        "Accept": "text/html,application/xhtml+xml",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return f"ERROR: {e}"

def search_user(username: str) -> str:
    """Get latest tweets from a Twitter user via Nitter."""
    for instance in NITTER_INSTANCES:
        url = f"{instance}/{username.lstrip('@')}"
        html = fetch_url(url)
        if html and not html.startswith("ERROR"):
            return parse_user_tweets(html, username, instance)
    return "ERROR: All Nitter instances failed"

def search_tweets(query: str, limit: int = 10) -> str:
    """Search tweets by keyword via Nitter."""
    encoded = urllib.parse.quote(query)
    for instance in NITTER_INSTANCES:
        url = f"{instance}/search?f=tweets&q={encoded}"
        html = fetch_url(url)
        if html and not html.startswith("ERROR"):
            return parse_search_results(html, query, instance)
    return "ERROR: All Nitter instances failed"

def parse_user_tweets(html: str, username: str, instance: str) -> str:
    """Parse Nitter HTML to extract tweets."""
    # Extract tweet text using regex
    tweet_pattern = re.compile(r'<p class="tweet-content[^"]*">(.*?)</p>', re.DOTALL)
    date_pattern = re.compile(r'<span class="tweet-date[^"]*"><a[^>]*>([^<]+)</a></span>')
    likes_pattern = re.compile(r'<span class="tweet-likes[^"]*">(?:<[^>]*>)*(\d+)', re.DOTALL)
    replies_pattern = re.compile(r'<span class="tweet-replies[^"]*">(?:<[^>]*>)*(\d+)', re.DOTALL)
    
    tweets = tweet_pattern.findall(html)
    dates = date_pattern.findall(html)
    likes = likes_pattern.findall(html)
    replies = replies_pattern.findall(html)
    
    # Strip HTML tags from tweet text
    clean_tweets = []
    for t in tweets[:10]:
        clean = re.sub(r'<[^>]+>', '', t).strip()
        if clean:
            clean_tweets.append(clean)
    
    if not clean_tweets:
        return f"## X Search: @{username} via {instance}\n[No tweets found or parse failed]\nRaw preview: {html[:500]}"
    
    result = f"## X Search Results: @{username}\n"
    result += f"Source: {instance}\n"
    result += f"Tweets found: {len(clean_tweets)}\n\n"
    
    for i, tweet in enumerate(clean_tweets):
        date = dates[i] if i < len(dates) else "N/A"
        like = likes[i] if i < len(likes) else "0"
        reply = replies[i] if i < len(replies) else "0"
        result += f"### Tweet {i+1} [{date}]\n"
        result += f"{tweet}\n"
        result += f"❤️ {like} 💬 {reply}\n\n"
    
    return result

def parse_search_results(html: str, query: str, instance: str) -> str:
    """Parse Nitter search results."""
    # Similar to user tweets but with search context
    tweet_pattern = re.compile(r'<p class="tweet-content[^"]*">(.*?)</p>', re.DOTALL)
    user_pattern = re.compile(r'<a class="username"[^>]*>([^<]+)</a>')
    date_pattern = re.compile(r'<span class="tweet-date[^"]*"><a[^>]*>([^<]+)</a></span>')
    
    tweets = tweet_pattern.findall(html)
    users = user_pattern.findall(html)
    dates = date_pattern.findall(html)
    
    clean_tweets = []
    for t in tweets[:10]:
        clean = re.sub(r'<[^>]+>', '', t).strip()
        if clean:
            clean_tweets.append(clean)
    
    if not clean_tweets:
        return f"## X Search: {query}\n[No results found via {instance}]\nNote: Nitter may have rate limits or IP blocks."
    
    result = f"## X Search: {query}\n"
    result += f"Source: {instance}\n"
    result += f"Tweets found: {len(clean_tweets)}\n\n"
    
    for i, tweet in enumerate(clean_tweets):
        user = users[i] if i < len(users) else "unknown"
        date = dates[i] if i < len(dates) else "N/A"
        result += f"### Tweet {i+1} by @{user} [{date}]\n"
        result += f"{tweet}\n\n"
    
    return result

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 x_search.py <user|search> <query>")
        print("  user <username>   — Get tweets from user")
        print("  search <keyword> — Search tweets by keyword")
        sys.exit(1)
    
    mode = sys.argv[1]
    query = sys.argv[2]
    
    if mode == "user":
        print(search_user(query))
    elif mode == "search":
        print(search_tweets(query))
    else:
        print(f"ERROR: Unknown mode '{mode}'. Use 'user' or 'search'.")