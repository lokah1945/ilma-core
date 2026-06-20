#!/usr/bin/env python3
"""
ILMA Webhook Handler
==================
Process webhooks from various services.
"""

import json
import subprocess
from pathlib import Path

WEBHOOKS_DIR = Path("/root/.hermes/profiles/ilma/webhooks")
WEBHOOKS_DIR.mkdir(exist_ok=True)

HANDLERS = {
    "github": "handle_github",
    "gitlab": "handle_gitlab",
    "docker": "handle_docker",
    "jenkins": "handle_jenkins",
}

def handle_github(payload):
    event = os.environ.get("GITHUB_EVENT", "")
    if event == "push":
        print(f"GitHub push: {payload.get('ref')}")
    elif event == "pull_request":
        print(f"GitHub PR: {payload.get('action')}")
    return {"status": "processed"}

def handle_gitlab(payload):
    print(f"GitLab hook: {payload.get('object_kind')}")
    return {"status": "processed"}

def handle_docker(payload):
    print(f"Docker hook: {payload.get('state')}")
    return {"status": "processed"}

def handle_jenkins(payload):
    print(f"Jenkins hook: {payload.get('name')}")
    return {"status": "processed"}

def main():
    import sys
    if len(sys.argv) < 2:
        print("Usage: ilma_webhook_handler.py <source>")
        return
    
    source = sys.argv[1]
    if source not in HANDLERS:
        print(f"Unknown source: {source}")
        return
    
    payload = json.load(sys.stdin)
    handler = HANDLERS[source]
    result = globals()[handler](payload)
    print(json.dumps(result))

if __name__ == "__main__":
    main()