#!/usr/bin/env python3
"""
Extract OpenRouter key from api_key.json and run the tester.
This is a wrapper script to handle the masked keys in AYDA's credential store.
"""

import json, re, os, sys

# Extract OpenRouter key
CRED_PATH = "/root/credential/api_key.json"

with open(CRED_PATH) as f:
    raw = f.read()

# The JSON uses a special format where long strings are masked as "sk-or-...XXXX"
# We need to parse the actual JSON (which unmasks them) and get the real value
data = json.loads(raw)
or_data = data.get("openrouter", {})
or_keys = or_data.get("keys", [])
or_key = or_keys[0] if or_keys else None

print(f"OpenRouter API Key (masked): {or_key}")
print(f"Key length: {len(or_key) if or_key else 0}")

if not or_key:
    print("ERROR: No OpenRouter key found!")
    sys.exit(1)

# Now test it via curl directly
import urllib.request, urllib.error

headers = {
    "Authorization": f"Bearer {or_key}",
    "Content-Type": "application/json",
    "HTTP-Referer": "https://ilma-hermes.local",
    "X-Title": "ILMA Hermes Agent",
}

# Test a simple model
payload = {
    "model": "openai/gpt-5.5",
    "messages": [{"role": "user", "content": "Say 'OK' only"}],
    "max_tokens": 5,
}

import time
start = time.time()

req = urllib.request.Request(
    "https://openrouter.ai/api/v1/chat/completions",
    data=json.dumps(payload).encode(),
    headers=headers,
    method="POST"
)

try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        elapsed = (time.time() - start) * 1000
        result = json.loads(resp.read().decode())
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        print(f"\n✅ OpenRouter API WORKING!")
        print(f"   Model: openai/gpt-5.5")
        print(f"   Response: '{content}'")
        print(f"   Latency: {elapsed:.0f}ms")
        print(f"   HTTP Status: {resp.status}")
        
        # Now set the key and run the full tester
        os.environ["OPENROUTER_API_KEY"] = or_key
        
        print("\n" + "="*60)
        print("Running full OpenRouter model tester...")
        print("="*60 + "\n")
        
        sys.path.insert(0, "/root/.hermes/profiles/ilma")
        from scripts.ilma_openrouter_tester import OpenRouterTester
        
        tester = OpenRouterTester(api_key=or_key)
        top_models = tester.get_free_models(limit=10)
        
        print(f"\n📋 Testing TOP 10 free models by quality\n")
        model_ids = [m["model_id"] for m in top_models]
        
        results = tester.batch_test(model_ids, delay=2.0, timeout=20)
        
        print("\n" + "="*60)
        summary = tester.summarize(results)
        print(f"""
📊 SUMMARY
  Total tested:   {summary['total']}
  Available:      {summary['available']} ✅
  Errors:         {summary['errors']} ❌
  Success rate:  {summary['success_rate']}
""")
        
        if summary['available'] > 0:
            print(f"""  Latency:
    Average:  {summary['avg_latency_ms']:.0f}ms
    Min:      {summary['min_latency_ms']:.0f}ms
    Max:      {summary['max_latency_ms']:.0f}ms
""")
        
        available = [r for r in results if r["status"] == "available"]
        if available:
            print("✅ AVAILABLE MODELS:")
            for r in sorted(available, key=lambda x: x["latency_ms"]):
                print(f"   - {r['model']} ({r['latency_ms']:.0f}ms)")
        
        error_results = [r for r in results if r["status"] != "available"]
        if error_results:
            print(f"\n❌ ERROR MODELS ({len(error_results)}):")
            for r in error_results[:5]:
                print(f"   - {r['model']}: {r['status']} {str(r.get('error',''))[:50]}")
        
except urllib.error.HTTPError as e:
    body = e.read().decode()[:500]
    print(f"\n❌ HTTP Error {e.code}: {body}")
except Exception as e:
    print(f"\n❌ Error: {e}")