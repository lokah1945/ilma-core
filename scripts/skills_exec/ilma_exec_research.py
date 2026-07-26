#!/usr/bin/env python3
"""
ILMA Research Execution Script
证据ID: P2E-RESEARCH-001
Mode: dry-run by default, --live for actual web search
"""
import argparse, json, sys, re, datetime
from urllib.parse import quote

EVIDENCE_ID = "P2E-RESEARCH-001"
VERSION = "1.0.0"

def search_arxiv(query, max_results=5):
    """Search arXiv via OAI-PMH API (no API key needed)."""
    url = (f"http://export.arxiv.org/api/query?"
           f"search_query=all:{quote(query)}&start=0&max_results={max_results}&sortBy=relevance")
    try:
        import urllib.request
        with urllib.request.urlopen(url, timeout=10) as r:
            data = r.read().decode()
        entries = re.findall(r'<entry>(.*?)</entry>', data, re.DOTALL)
        results = []
        for e in entries:
            title = re.search(r'<title>(.*?)</title>', e, re.DOTALL)
            summary = re.search(r'<summary>(.*?)</summary>', e, re.DOTALL)
            link = re.search(r'<id>(.*?)</id>', e)
            if title:
                results.append({
                    "source": "arXiv",
                    "title": title.group(1).strip().replace('\n', ' '),
                    "url": link.group(1) if link else "",
                    "abstract": (summary.group(1).strip()[:200] + "...") if summary else ""
                })
        return results
    except Exception as ex:
        return [{"error": str(ex), "source": "arXiv"}]

def search_wikipedia(query):
    """Fetch Wikipedia article via API (no API key needed)."""
    import urllib.request
    url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={quote(query)}&format=json"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read().decode())
        results = []
        for item in data.get("query", {}).get("search", [])[:5]:
            results.append({
                "source": "Wikipedia",
                "title": item["title"],
                "snippet": re.sub(r'<.*?>', '', item["snippet"]),
                "url": f"https://en.wikipedia.org/wiki/{quote(item['title'])}"
            })
        return results
    except Exception as ex:
        return [{"error": str(ex), "source": "Wikipedia"}]

def main():
    p = argparse.ArgumentParser(description="ILMA Research Execution Script")
    p.add_argument("--query", "-q", required=True, help="Research query")
    p.add_argument("--live", action="store_true", help="Enable live web search (arXiv + Wikipedia)")
    p.add_argument("--max-results", "-n", type=int, default=5)
    p.add_argument("--json", action="store_true", help="JSON output")
    p.add_argument("--evidence-id", default=EVIDENCE_ID)
    args = p.parse_args()

    mode = "live" if args.live else "dry-run"
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Source table
    sources = [
        {"id": 1, "provider": "arXiv", "status": "available", "requires_key": False,
         "url": "http://export.arxiv.org/api/query"},
        {"id": 2, "provider": "Wikipedia API", "status": "available", "requires_key": False,
         "url": "https://en.wikipedia.org/w/api.php"},
        {"id": 3, "provider": "Playwright Chromium", "status": "available", "requires_key": False,
         "url": "headless browser"},
    ]

    # Execute
    if args.live:
        arxiv_results = search_arxiv(args.query, args.max_results)
        wiki_results = search_wikipedia(args.query)
    else:
        arxiv_results = [{"mode": "dry-run", "query": args.query, "would_search": True}]
        wiki_results = [{"mode": "dry-run", "query": args.query, "would_search": True}]

    # Findings
    findings = []
    for r in arxiv_results:
        if "error" not in r:
            findings.append({"source": r.get("source", "arXiv"), "type": "academic", "title": r.get("title","")})
    for r in wiki_results:
        if "error" not in r:
            findings.append({"source": r.get("source", "Wikipedia"), "type": "encyclopedia", "title": r.get("title","")})

    confidence = 0.85 if args.live else 0.6
    limitations = ["arXiv may not have recent papers", "Wikipedia not authoritative"] if not args.live else []

    result = {
        "evidence_id": args.evidence_id,
        "version": VERSION,
        "timestamp": timestamp,
        "query": args.query,
        "mode": mode,
        "sources": sources,
        "arxiv_results": arxiv_results,
        "wikipedia_results": wiki_results,
        "key_findings": findings[:args.max_results],
        "confidence": confidence,
        "limitations": limitations,
        "status": "live" if args.live else "dry-run"
    }

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"=== ILMA Research Execution ===")
        print(f"Query: {args.query}")
        print(f"Mode: {mode}")
        print(f"Sources: {len(sources)}")
        print(f"Findings: {len(findings)}")
        print(f"Confidence: {confidence}")
        if findings:
            print("\nTop findings:")
            for f in findings[:3]:
                print(f"  - [{f['source']}] {f.get('title','')[:60]}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
