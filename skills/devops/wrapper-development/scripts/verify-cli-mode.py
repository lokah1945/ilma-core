#!/usr/bin/env python3
"""Verify wrapper-opencode CLI mode proxy across all three surfaces.

Usage:
    python3 scripts/verify-cli-mode.py
    python3 scripts/verify-cli-mode.py --base http://127.0.0.1:9104 --token wrapper-local-key
"""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

import aiohttp

# Test free models (from 2026-11-20)
FREE_MODELS = [
    "beam-free",
    "hy4-flash-free",
    "iceman-free",
    "tidepool-alpha-free",
    "nemotron-3.5-super-vl-free",
]

SURFACES = [
    ("/v1/chat/completions", "openai_chat"),
    ("/v1/responses", "openai_responses"),
    ("/v1/messages", "anthropic_messages"),
]


async def test_surface(session, base, token, model, surface_path, surface_type):
    """Test a single surface with a free model."""
    url = f"{base}{surface_path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    if surface_type == "openai_chat":
        payload = {"model": model, "messages": [{"role": "user", "content": "hi"}], "stream": False}
    elif surface_type == "openai_responses":
        payload = {"model": model, "input": "hi"}
    else:  # anthropic_messages
        payload = {"model": model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 100}

    t0 = time.perf_counter()
    try:
        async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as r:
            elapsed = time.perf_counter() - t0
            data = await r.json()
            if r.status == 200:
                # Extract content based on surface
                if surface_type == "openai_chat":
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                elif surface_type == "openai_responses":
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                else:
                    content = data.get("content", [{}])[0].get("text", "")
                return {
                    "surface": surface_type,
                    "model": model,
                    "status": "ok",
                    "latency_s": round(elapsed, 3),
                    "content_preview": content[:50] if content else "EMPTY",
                }
            else:
                return {
                    "surface": surface_type,
                    "model": model,
                    "status": "error",
                    "latency_s": round(elapsed, 3),
                    "error": data.get("error", {}).get("message", str(data))[:100],
                }
    except Exception as e:
        elapsed = time.perf_counter() - t0
        return {
            "surface": surface_type,
            "model": model,
            "status": "exception",
            "latency_s": round(elapsed, 3),
            "error": str(e)[:100],
        }


async def main():
    parser = argparse.ArgumentParser(description="Verify wrapper-opencode CLI mode")
    parser.add_argument("--base", default="http://127.0.0.1:9104", help="Wrapper base URL")
    parser.add_argument("--token", default="wrapper-local-key", help="Bearer token")
    parser.add_argument("--models", nargs="+", default=FREE_MODELS, help="Models to test")
    args = parser.parse_args()

    print(f"Verifying CLI mode at {args.base}")
    print(f"Models: {', '.join(args.models)}")
    print("-" * 80)

    results = []
    async with aiohttp.ClientSession() as session:
        # Health check
        try:
            async with session.get(f"{args.base}/health", timeout=aiohttp.ClientTimeout(total=10)) as r:
                health = await r.json()
                print(f"Health: {health.get('status')} | Keys: {health.get('keys')} | Free only: {health.get('free_only')}")
        except Exception as e:
            print(f"Health check failed: {e}")
            sys.exit(1)

        # Test each surface with each model
        for model in args.models:
            print(f"\nTesting model: {model}")
            for surface_path, surface_type in SURFACES:
                result = await test_surface(session, args.base, args.token, model, surface_path, surface_type)
                results.append(result)
                status = result["status"]
                latency = result["latency_s"]
                preview = result.get("content_preview", result.get("error", ""))
                print(f"  {surface_type:20} : {status:9} ({latency:.3f}s) {preview}")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    by_surface = {}
    for r in results:
        by_surface.setdefault(r["surface"], {"ok": 0, "total": 0, "latencies": []})
        by_surface[r["surface"]]["total"] += 1
        if r["status"] == "ok":
            by_surface[r["surface"]]["ok"] += 1
            by_surface[r["surface"]]["latencies"].append(r["latency_s"])

    for surface, stats in by_surface.items():
        ok = stats["ok"]
        total = stats["total"]
        pct = (ok / total * 100) if total else 0
        avg_lat = sum(stats["latencies"]) / len(stats["latencies"]) if stats["latencies"] else 0
        print(f"  {surface:20} : {ok}/{total} ({pct:.0f}%) avg {avg_lat:.3f}s")

    # Overall
    total_ok = sum(s["ok"] for s in by_surface.values())
    total_all = sum(s["total"] for s in by_surface.values())
    print(f"\nOverall: {total_ok}/{total_all} ({total_ok/total_all*100:.0f}%)")

    sys.exit(0 if total_ok == total_all else 1)


if __name__ == "__main__":
    asyncio.run(main())