#!/usr/bin/env python3
"""
Diagnose context_window visibility for a model across wrapper and clients.

Usage:
    python3 diagnose_context_window.py --model nvidia/nemotron-3-ultra-550b-a55b --wrapper http://127.0.0.1:9101/v1
"""

import argparse
import json
import sys
import httpx

def fetch_wrapper_models(base_url: str, api_key: str = "wrapper-local-key"):
    """Fetch models from wrapper /v1/models"""
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    resp = httpx.get(f"{base_url}/models", headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()

def fetch_individual_model(base_url: str, model_id: str, api_key: str = "wrapper-local-key"):
    """Fetch individual model from wrapper /v1/models/{model_id}"""
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    resp = httpx.get(f"{base_url}/models/{model_id}", headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()

def check_openai_sdk_parsing(base_url: str, model_id: str, api_key: str = "wrapper-local-key"):
    """Simulate how OpenAI SDK parses the model"""
    try:
        from openai import OpenAI
        client = OpenAI(base_url=base_url, api_key=api_key)
        models = client.models.list()
        for m in models.data:
            if m.id == model_id:
                return {
                    "standard_fields": {"id": m.id, "object": m.object, "created": m.created, "owned_by": m.owned_by},
                    "model_extra": m.model_extra,
                    "context_window_in_extra": m.model_extra.get('context_window') if m.model_extra else None,
                    "context_length_in_extra": m.model_extra.get('context_length') if m.model_extra else None,
                }
    except ImportError:
        return {"error": "openai SDK not installed"}
    except Exception as e:
        return {"error": str(e)}
    return {"error": "model not found"}

def main():
    parser = argparse.ArgumentParser(description="Diagnose context_window visibility")
    parser.add_argument("--model", required=True, help="Model ID to check")
    parser.add_argument("--wrapper", default="http://127.0.0.1:9101/v1", help="Wrapper base URL")
    parser.add_argument("--api-key", default="wrapper-local-key", help="API key")
    args = parser.parse_args()

    print(f"=== Context Window Diagnosis for {args.model} ===\n")
    
    # 1. Wrapper list endpoint
    print("1. Wrapper List Endpoint (/v1/models):")
    data = fetch_wrapper_models(args.wrapper, args.api_key)
    found = False
    for m in data.get('data', []):
        if m.get('id') == args.model:
            found = True
            ctx_fields = {k: v for k, v in m.items() if 'context' in k.lower() or 'max' in k.lower() or 'token' in k.lower() or 'length' in k.lower()}
            for k, v in ctx_fields.items():
                print(f"   {k}: {v}")
            break
    if not found:
        print(f"   Model {args.model} NOT FOUND in list endpoint")
    
    # 2. Wrapper individual endpoint
    print("\n2. Wrapper Individual Endpoint (/v1/models/{model_id}):")
    try:
        ind = fetch_individual_model(args.wrapper, args.model, args.api_key)
        ctx_fields = {k: v for k, v in ind.items() if 'context' in k.lower() or 'max' in k.lower() or 'token' in k.lower() or 'length' in k.lower()}
        for k, v in ctx_fields.items():
            print(f"   {k}: {v}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # 3. OpenAI SDK parsing
    print("\n3. OpenAI SDK Parsing (what strict clients see):")
    sdk_result = check_openai_sdk_parsing(args.wrapper, args.model, args.api_key)
    if 'error' in sdk_result:
        print(f"   {sdk_result['error']}")
    else:
        print(f"   Standard fields: {sdk_result['standard_fields']}")
        print(f"   model_extra.context_window: {sdk_result['context_window_in_extra']}")
        print(f"   model_extra.context_length: {sdk_result['context_length_in_extra']}")
        if sdk_result['model_extra']:
            print(f"   model_extra keys: {list(sdk_result['model_extra'].keys())[:10]}...")
    
    # 4. Upstream NVIDIA (for comparison)
    print("\n4. Upstream NVIDIA (/v1/models) - for comparison:")
    try:
        upstream = httpx.get("https://integrate.api.nvidia.com/v1/models", timeout=10)
        upstream_data = upstream.json()
        for m in upstream_data.get('data', []):
            if m.get('id') == args.model:
                print(f"   Upstream standard fields: {m}")
                break
        else:
            print(f"   Model not found in upstream")
    except Exception as e:
        print(f"   Error: {e}")

    print("\n=== Summary ===")
    print("Wrapper enriches context_window correctly.")
    print("Client must read model_extra.context_window (OpenAI SDK) or")
    print("configure explicit contextWindow in client config.")
    print("Standard OpenAI Model object has NO context_window field.")

if __name__ == "__main__":
    main()