"""CLI for web search."""
import argparse
import json
from .searcher import WebSearcher

def main():
    parser = argparse.ArgumentParser(description="Web Search")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--max", type=int, default=5, help="Max results")
    
    args = parser.parse_args()
    
    searcher = WebSearcher()
    results = searcher.search(args.query, args.max)
    
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()
