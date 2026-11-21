#!/usr/bin/env python3
"""
Wrapper verification script — run after deployment to confirm wrapper is healthy.
Usage: python3 verify-wrapper.py <wrapper-name> [--port PORT]
"""

import sys
import json
import argparse
import subprocess
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from common.wrapper_scope import load_wrappers, production_wrappers


def check_port_listening(port: int) -> bool:
    """Check if port is listening."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0


def check_health_endpoint(port: int) -> dict:
    """Check /health endpoint."""
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}


def check_models_endpoint(port: int) -> dict:
    """Check /v1/models endpoint."""
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/v1/models", timeout=10) as resp:
            data = json.loads(resp.read())
            return {"model_count": len(data.get("data", [])), "models": [m.get("id") for m in data.get("data", [])[:5]]}
    except Exception as e:
        return {"error": str(e)}


def check_chat_completion(port: int, model: str = None) -> dict:
    """Check /v1/chat/completions non-streaming."""
    import urllib.request
    if not model:
        model = "claude-fable-5"  # default fallback
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/v1/chat/completions",
            data=json.dumps({
                "model": model,
                "messages": [{"role": "user", "content": "Say hello in one word"}],
                "max_tokens": 50
            }).encode(),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return {"success": bool(content), "content": content[:50]}
    except Exception as e:
        return {"error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="Verify wrapper deployment")
    parser.add_argument("wrapper", help="Wrapper name from wrappers.json")
    parser.add_argument("--port", type=int, help="Override port from wrappers.json")
    args = parser.parse_args()

    wrappers = load_wrappers()
    if args.wrapper not in wrappers:
        print(f"ERROR: Unknown wrapper '{args.wrapper}'")
        print(f"Available: {list(wrappers.keys())}")
        return 1

    config = wrappers[args.wrapper]
    port = args.port or config.get("port")
    status = config.get("status")

    print(f"=== Verifying {args.wrapper} (port {port}, status: {status}) ===\n")

    # 1. Port check
    print("1. Port listening...")
    if check_port_listening(port):
        print(f"   ✅ Port {port} is listening")
    else:
        print(f"   ❌ Port {port} NOT listening")
        return 1

    # 2. Health endpoint
    print("\n2. Health endpoint...")
    health = check_health_endpoint(port)
    if "error" not in health:
        print(f"   ✅ {health}")
    else:
        print(f"   ❌ {health['error']}")
        return 1

    # 3. Models endpoint
    print("\n3. Models endpoint...")
    models = check_models_endpoint(port)
    if "error" not in models:
        print(f"   ✅ {models['model_count']} models (sample: {models['models']})")
    else:
        print(f"   ❌ {models['error']}")
        return 1

    # 4. Chat completion
    print("\n4. Chat completion (non-stream)...")
    chat = check_chat_completion(port)
    if "error" not in chat:
        print(f"   ✅ Response: {chat['content']}")
    else:
        print(f"   ❌ {chat['error']}")
        return 1

    print(f"\n=== {args.wrapper} VERIFICATION PASSED ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())