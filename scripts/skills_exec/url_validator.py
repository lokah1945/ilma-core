#!/usr/bin/env python3
"""URL Validator CLI"""
import argparse, sys
from urllib.parse import urlparse

def validate_url(url):
    if not url.startswith(("http://","https://")):
        return False, "Must start with http:// or https://"
    try:
        result = urlparse(url)
        if not all([result.scheme, result.netloc]):
            return False, "Invalid URL structure"
        return True, "Valid URL"
    except Exception as e:
        return False, str(e)

def main():
    p = argparse.ArgumentParser(description="Validate URLs")
    p.add_argument("url", help="URL to validate")
    p.add_argument("--json", action="store_true", help="JSON output")
    args = p.parse_args()
    ok, msg = validate_url(args.url)
    if args.json:
        import json
        print(json.dumps({"url": args.url, "valid": ok, "message": msg}))
    else:
        print(f"URL: {args.url}")
        print(f"Valid: {ok}")
        print(f"Message: {msg}")
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
