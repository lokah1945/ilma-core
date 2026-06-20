#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         ILMA OpenRouter Model Tester v1.0                                  ║
║         Test curl to all OpenRouter models in MASTER DB                     ║
║                                                                           ║
║ Database: ilma_model_router_data/PROVIDER_INTELLIGENCE_MASTER.json         ║
║ Usage: python3 scripts/ilma_openrouter_tester.py                           ║
╚══════════════════════════════════════════════════════════════════════════════╝

Tests OpenRouter free models via direct API calls.
Requires OPENROUTER_API_KEY in environment.

Usage:
  python3 scripts/ilma_openrouter_tester.py                    # Test top 10
  python3 scripts/ilma_openrouter_tester.py --all             # Test all free
  python3 scripts/ilma_openrouter_tester.py --model "google/gemma-4-26b-a4b-it:free"
  python3 scripts/ilma_openrouter_tester.py --batch 20        # Test batch of 20
"""

import json
import os
import time
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# ═══════════════════════════════════════════════════════════════════════════
# PATHS
# ═══════════════════════════════════════════════════════════════════════════

ILMA_PROFILE = Path("/root/.hermes/profiles/ilma")
ROUTER_DATA = ILMA_PROFILE / "ilma_model_router_data"
MASTER_DB = ROUTER_DATA / "PROVIDER_INTELLIGENCE_MASTER.json"
HEALTH_FILE = ILMA_PROFILE / "ilma_provider_health_state.json"  # ⛔ renamed 2026-06-18

OPENROUTER_BASE = "https://openrouter.ai/api/v1"
OPENROUTER_CHAT = f"{OPENROUTER_BASE}/chat/completions"

# ═══════════════════════════════════════════════════════════════════════════
# OPENROUTER TESTER
# ═══════════════════════════════════════════════════════════════════════════

class OpenRouterTester:
    """
    Test OpenRouter models via direct API.
    Shows which models are actually accessible.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        self._master: Dict[str, Any] = {}
        self._health: Dict[str, Any] = {}
        self._load_databases()
    
    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key not in ("NOT SET", ""))
    
    def _load_databases(self):
        """Load MASTER and health state."""
        if MASTER_DB.exists():
            with open(MASTER_DB) as f:
                self._master = json.load(f)
    
    def get_free_models(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get all free OpenRouter models sorted by quality."""
        or_provider = self._master.get("providers", {}).get("openrouter", {})
        models = or_provider.get("models", {})
        
        free = []
        for mid, mdata in models.items():
            if mdata.get("is_free") or mdata.get("billing") == "free":
                free.append({
                    "model_id": mid,
                    "name": mdata.get("name", mid),
                    "quality_score": mdata.get("quality_score", 0),
                    "coding_score": mdata.get("coding_score", 0),
                    "context_window": mdata.get("context_window", 0),
                    "capabilities": mdata.get("capabilities", []),
                })
        
        sorted_free = sorted(free, key=lambda x: x["quality_score"], reverse=True)
        return sorted_free[:limit] if limit else sorted_free
    
    def test_model(
        self,
        model: str,
        message: str = "Say 'OK' only",
        timeout: int = 15,
    ) -> Dict[str, Any]:
        """Test a single model."""
        if not self.is_configured:
            return {
                "model": model,
                "status": "unconfigured",
                "error": "OPENROUTER_API_KEY not set",
                "latency_ms": 0,
            }
        
        # Extract bare model
        bare_model = model.replace("openrouter/", "", 1)
        
        import urllib.request, urllib.error
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://ilma-hermes.local",
            "X-Title": "ILMA Hermes Agent",
        }
        
        payload = {
            "model": bare_model,
            "messages": [{"role": "user", "content": message}],
            "max_tokens": 10,
        }
        
        start = time.time()
        try:
            req = urllib.request.Request(
                OPENROUTER_CHAT,
                data=json.dumps(payload).encode(),
                headers=headers,
                method="POST"
            )
            
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                elapsed = (time.time() - start) * 1000
                data = json.loads(resp.read().decode())
                
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                
                return {
                    "model": model,
                    "bare_model": bare_model,
                    "status": "available",
                    "response": content,
                    "latency_ms": round(elapsed, 0),
                    "http_status": resp.status,
                    "error": "",
                }
                
        except urllib.error.HTTPError as e:
            body = e.read().decode()[:200]
            return {
                "model": model,
                "bare_model": bare_model,
                "status": f"error_{e.code}",
                "http_status": e.code,
                "error": body,
                "latency_ms": round((time.time() - start) * 1000, 0),
            }
        except Exception as e:
            return {
                "model": model,
                "bare_model": bare_model,
                "status": "error",
                "error": str(e),
                "latency_ms": round((time.time() - start) * 1000, 0),
            }
    
    def batch_test(
        self,
        models: List[str],
        delay: float = 1.0,
        timeout: int = 15,
    ) -> List[Dict[str, Any]]:
        """Test multiple models with rate limit protection."""
        results = []
        for model in models:
            print(f"  Testing {model}...", end=" ", flush=True)
            result = self.test_model(model, timeout=timeout)
            results.append(result)
            
            status_icon = "✅" if result["status"] == "available" else "❌"
            latency = result.get("latency_ms", 0)
            
            if result["status"] == "available":
                print(f"{status_icon} {result['response']} ({latency:.0f}ms)")
            else:
                err = result.get("error", "")[:60]
                print(f"{status_icon} {result['status']}: {err}")
            
            time.sleep(delay)  # Rate limit protection
        
        return results
    
    def summarize(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Summarize test results."""
        total = len(results)
        available = sum(1 for r in results if r["status"] == "available")
        errors = total - available
        
        latencies = [r["latency_ms"] for r in results if r["status"] == "available"]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        min_latency = min(latencies) if latencies else 0
        max_latency = max(latencies) if latencies else 0
        
        return {
            "total": total,
            "available": available,
            "errors": errors,
            "success_rate": f"{available/total*100:.1f}%" if total else "0%",
            "avg_latency_ms": round(avg_latency, 0),
            "min_latency_ms": round(min_latency, 0),
            "max_latency_ms": round(max_latency, 0),
        }


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="ILMA OpenRouter Model Tester",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/ilma_openrouter_tester.py                    # Top 10 models
  python3 scripts/ilma_openrouter_tester.py --all             # All free models
  python3 scripts/ilma_openrouter_tester.py --top 20           # Top 20 models
  python3 scripts/ilma_openrouter_tester.py --batch 50         # Batch test 50 models
  python3 scripts/ilma_openrouter_tester.py --model "google/gemma-4-26b-a4b-it:free"
  python3 scripts/ilma_openrouter_tester.py --api-key "sk-or-xxx"
        """
    )
    parser.add_argument("--all", action="store_true", help="Test ALL free models")
    parser.add_argument("--top", type=int, default=10, help="Test top N models (default: 10)")
    parser.add_argument("--batch", type=int, metavar="N", help="Test first N free models")
    parser.add_argument("--model", metavar="ID", help="Test a specific model")
    parser.add_argument("--api-key", help="OpenRouter API key")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between tests (default: 1.0s)")
    parser.add_argument("--timeout", type=int, default=15, help="Timeout per request (default: 15s)")
    
    args = parser.parse_args()
    
    tester = OpenRouterTester(api_key=args.api_key)
    
    # Check configuration
    if not tester.is_configured:
        print("🔴 OPENROUTER_API_KEY not configured!")
        print()
        print("Set it via:")
        print("  export OPENROUTER_API_KEY=sk-or-...")
        print("  python3 scripts/ilma_openrouter_tester.py --api-key sk-or-...")
        print()
        print("Get your key at: https://openrouter.ai/keys")
        sys.exit(1)
    
    print("🟢 OpenRouter API configured")
    print()
    
    # Determine which models to test
    if args.model:
        # Single model test
        models = [args.model.replace("openrouter/", "", 1)]
        print(f"Testing single model: {models[0]}")
        results = tester.batch_test([models[0]], delay=args.delay, timeout=args.timeout)
    
    elif args.all:
        # All free models
        all_models = tester.get_free_models()
        models = [m["model_id"] for m in all_models]
        print(f"Testing ALL free models: {len(models)}")
        print()
        results = tester.batch_test(models, delay=args.delay, timeout=args.timeout)
    
    elif args.batch:
        # First N free models
        all_models = tester.get_free_models()
        models = [m["model_id"] for m in all_models[:args.batch]]
        print(f"Testing first {args.batch} free models")
        print()
        results = tester.batch_test(models, delay=args.delay, timeout=args.timeout)
    
    else:
        # Default: top N
        top_models = tester.get_free_models(limit=args.top)
        models = [m["model_id"] for m in top_models]
        print(f"Testing TOP {args.top} free models by quality")
        print()
        results = tester.batch_test(models, delay=args.delay, timeout=args.timeout)
    
    print()
    print("=" * 60)
    
    # Summary
    summary = tester.summarize(results)
    
    print(f"""
📊 SUMMARY
  Total tested:   {summary['total']}
  Available:      {summary['available']} ✅
  Errors:         {summary['errors']} ❌
  Success rate:   {summary['success_rate']}
""")
    
    if summary['available'] > 0:
        print(f"""  Latency:
    Average:  {summary['avg_latency_ms']:.0f}ms
    Min:      {summary['min_latency_ms']:.0f}ms
    Max:      {summary['max_latency_ms']:.0f}ms
""")
    
    # Show available models
    available = [r for r in results if r["status"] == "available"]
    if available:
        print("✅ AVAILABLE MODELS:")
        for r in sorted(available, key=lambda x: x["latency_ms"]):
            print(f"   - {r['model']} ({r['latency_ms']:.0f}ms)")
    
    # Show errors
    error_results = [r for r in results if r["status"] != "available"]
    if error_results:
        print(f"\n❌ ERROR MODELS ({len(error_results)}):")
        for r in error_results[:10]:
            print(f"   - {r['model']}: {r['status']} {r.get('error', '')[:50]}")
        if len(error_results) > 10:
            print(f"   ... and {len(error_results) - 10} more")


if __name__ == "__main__":
    main()