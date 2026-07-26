#!/usr/bin/env python3
"""URL Validator CLI - WITH BUG"""
import argparse, sys
from urllib.parse import urlparse

def validate_url(url):
    if not url.startswith(("http://","https://")):
        return False, "Must start with http:// or https://"
    try:
        result = urlparse(url)
        # BUG: missing netloc check
        return True, "Valid URL"
    except Exception as e:
        return False, str(e)

def main():
    p = argparse.ArgumentParser(description="Validate URLs")
    p.add_argument("url", help="URL to validate")
    args = p.parse_args()
    ok, msg = validate_url(args.url)
    print(f"URL: {args.url}")
    print(f"Valid: {ok}")
    print(f"Message: {msg}")
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
