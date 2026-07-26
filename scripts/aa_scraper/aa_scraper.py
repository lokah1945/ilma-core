#!/usr/bin/env python3
"""
ILMA Artificial Analysis (AA) Scraper v1.0
===========================================
Fetches benchmark data from artificialanalysis.ai

Sources:
  1. AA API v2 (primary) - with API key
  2. Cached data from AYDA benchmark research
  3. Playwright fallback (website scrape)

Output: benchmark_aa_cache.json
Fields: id, name, slug, provider, release_date,
        artificial_analysis_intelligence_index,
        artificial_analysis_coding_index,
        artificial_analysis_math_index

Author: ILMA v3.27
"""

import json, time, sys, os
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AA_SCRAPER_DIR = SCRIPT_DIR
ILMA_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))  # go up 2 levels: aa_scraper -> scripts -> ilma
CACHE_PATH = os.path.join(ILMA_DIR, "benchmark_aa_cache.json")
AYDA_CACHE = "/root/.hermes/profiles/ilma/home/.cache/ayda/benchmark_research/artificial_analysis_llms_models_raw.json"

def _load_aa_key():
    k = os.environ.get("AA_API_KEY", "")
    if k:
        return k
    try:
        import json as _j
        d = _j.load(open("/root/credential/api_key.json"))
        a = d.get("artificial_analysis", {})
        ks = a.get("keys")
        if ks:
            return ks[0] if isinstance(ks, list) else ks
    except Exception:
        pass
    return ""

AA_API_KEY = _load_aa_key()

# AA API endpoint
AA_API_URL = "https://artificialanalysis.ai/api/v2/data/llms/models"

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def load_ayda_cache():
    """Load from AYDA benchmark research cache (20 records).
    Records have nested structure: {id, name, slug, release_date, model_creator{...}, evaluations{...}}
    """
    if not os.path.exists(AYDA_CACHE):
        return []
    try:
        with open(AYDA_CACHE) as f:
            data = json.load(f)
        records = data.get("records", [])
        log(f"Loaded {len(records)} records from AYDA cache")
        
        # Normalize to flat structure
        normalized = []
        for r in records:
            ev = r.get("evaluations", {})
            mc = r.get("model_creator", {})
            normalized.append({
                "id": r.get("id"),
                "name": r.get("name"),
                "slug": r.get("slug"),
                "provider": mc.get("name"),
                "release_date": r.get("release_date"),
                "artificial_analysis_intelligence_index": ev.get("artificial_analysis_intelligence_index"),
                "artificial_analysis_coding_index": ev.get("artificial_analysis_coding_index"),
                "artificial_analysis_math_index": ev.get("artificial_analysis_math_index"),
                "mmlu_pro": ev.get("mmlu_pro"),
                "gpqa": ev.get("gpqa"),
                "livecodebench": ev.get("livecodebench"),
                "source": "ayda_cache",
                "fetched_at": None,
            })
        
        return normalized
    except Exception as e:
        log(f"Failed to load AYDA cache: {e}")
        return []

def fetch_aa_api():
    """Fetch from AA API v2 with Bearer token."""
    import subprocess
    
    if not AA_API_KEY:
        log("AA_API_KEY not set — skipping API fetch")
        return []
    
    log(f"Fetching AA API: {AA_API_URL}")
    try:
        result = subprocess.run(
            ["curl", "-s", "-L",
             "-H", f"x-api-key: {AA_API_KEY}",
             "-H", "Accept: application/json",
             "-H", "User-Agent: ILMA/1.0",
             "--max-time", "40",
             AA_API_URL],
            capture_output=True, text=True, timeout=45
        )
        if result.returncode != 0:
            log(f"API curl failed: {result.stderr}")
            return []
        data = json.loads(result.stdout)
        records = data.get("data") or data.get("records") or []
        log(f"API returned {len(records)} records")
        _EVAL_FIELDS = [
            "artificial_analysis_intelligence_index",
            "artificial_analysis_coding_index",
            "artificial_analysis_math_index",
            "mmlu_pro", "gpqa", "hle", "livecodebench", "scicode",
            "math_500", "aime", "aime_25", "ifbench", "lcr",
            "terminalbench_hard", "tau2",
        ]
        normalized = []
        for r in records:
            ev = r.get("evaluations", {}) or {}
            rec = {
                "id": r.get("id"),
                "name": r.get("name"),
                "slug": r.get("slug"),
                "provider": (r.get("model_creator") or {}).get("name"),
                "release_date": r.get("release_date"),
                "source": "aa_api_v2",
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
            for f in _EVAL_FIELDS:
                rec[f] = ev.get(f)
            normalized.append(rec)
        return normalized
    except json.JSONDecodeError as e:
        log(f"API returned invalid JSON: {e}")
        return []
    except Exception as e:
        log(f"API fetch error: {e}")
        return []

def fetch_playwright():
    """Fallback: scrape AA website with Playwright."""
    log("Attempting Playwright fallback...")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log("Playwright not installed — skipping")
        return []
    
    results = []
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
                locale="en-US",
            )
            page = context.new_page()
            page.set_default_timeout(30000)
            
            # AA models page
            log("Navigating to artificialanalysis.ai/llms...")
            page.goto("https://artificialanalysis.ai/llms", wait_until="networkidle")
            time.sleep(3)
            
            # Try to find model table
            # Look for data attributes or JSON embedded in page
            content = page.content()
            
            # Try to find embedded data
            import re
            # Look for JSON data in script tags
            json_matches = re.findall(r'"artificial_analysis_intelligence_index"\s*:\s*([0-9.]+)', content)
            
            if json_matches:
                log(f"Found {len(json_matches)} benchmark scores in page")
            
            # Also check for model names
            model_names = re.findall(r'class="[^"]*model-name[^"]*"[^>]*>([^<]+)<', content)
            log(f"Found {len(model_names)} model name elements")
            
            # Try extracting from table rows
            table_rows = page.query_selector_all("table tbody tr")
            log(f"Found {len(table_rows)} table rows")
            
            browser.close()
            
    except Exception as e:
        log(f"Playwright scrape error: {e}")
    
    return results

def merge_records(ayda_records, api_records):
    """Merge AYDA cache + API records. API takes priority (newer data)."""
    
    # Build slug -> record map from AYDA
    by_slug = {}
    for r in ayda_records:
        slug = r.get("slug", "")
        ev = r.get("evaluations", {})
        by_slug[slug] = {
            "id": r.get("id"),
            "name": r.get("name"),
            "slug": slug,
            "provider": r.get("model_creator", {}).get("name"),
            "release_date": r.get("release_date"),
            "artificial_analysis_intelligence_index": ev.get("artificial_analysis_intelligence_index"),
            "artificial_analysis_coding_index": ev.get("artificial_analysis_coding_index"),
            "artificial_analysis_math_index": ev.get("artificial_analysis_math_index"),
            "mmlu_pro": ev.get("mmlu_pro"),
            "gpqa": ev.get("gpqa"),
            "livecodebench": ev.get("livecodebench"),
            "source": "ayda_cache",
            "fetched_at": None,
        }
    
    # Override with API records (newer data)
    for r in api_records:
        slug = r.get("slug", "")
        if slug in by_slug:
            by_slug[slug].update(r)
        else:
            by_slug[slug] = r
    
    return list(by_slug.values())

def build_slug_index(records):
    """Build a fast lookup index: model name variants -> slug."""
    index = {}
    
    for r in records:
        slug = r["slug"]
        name = r["name"].lower()
        
        # Direct slug
        index[slug] = slug
        # Name with spaces and parens normalized
        index[name.replace(" ", "-").replace("(", "").replace(")", "")] = slug
        index[name.replace(" ", "").replace("(", "").replace(")", "")] = slug
        # Provider prefix
        provider = r.get("provider", "").lower()
        if provider:
            index[f"{provider}-{name}"] = slug
            index[f"{provider}/{slug}"] = slug
    
    return index

def save_cache(records):
    """Save to benchmark_aa_cache.json."""
    cache = {
        "source": "artificialanalysis.ai",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "record_count": len(records),
        "records": records,
        "slug_index": build_slug_index(records),
    }
    
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2)
    
    log(f"Saved {len(records)} records to {CACHE_PATH}")

def main():
    log("=== ILMA AA Scraper v1.0 ===")
    
    # Step 1: Load AYDA cache
    log("Step 1: Loading AYDA cache...")
    ayda_records = load_ayda_cache()
    
    # Step 2: Fetch fresh data from AA API
    log("Step 2: Fetching AA API...")
    api_records = fetch_aa_api()
    
    # Step 3: Merge
    log("Step 3: Merging records...")
    if api_records:
        all_records = merge_records(ayda_records, api_records)
    else:
        all_records = ayda_records
    
    log(f"Total records after merge: {len(all_records)}")
    
    # Step 4: Playwright fallback if we got almost nothing
    if len(all_records) < 5:
        log("Very few records — attempting Playwright fallback...")
        pw_records = fetch_playwright()
        if pw_records:
            all_records.extend(pw_records)
            log(f"Playwright returned {len(pw_records)} additional records")
    
    # Step 5: Save
    log("Step 4: Saving cache...")
    save_cache(all_records)
    
    # Summary
    log("=== Summary ===")
    log(f"Total records: {len(all_records)}")
    
    # Count records with valid benchmark data
    with_index = sum(1 for r in all_records 
                     if r.get("artificial_analysis_intelligence_index") is not None)
    with_coding = sum(1 for r in all_records 
                      if r.get("artificial_analysis_coding_index") is not None)
    with_math = sum(1 for r in all_records 
                    if r.get("artificial_analysis_math_index") is not None)
    
    log(f"Records with intelligence_index: {with_index}")
    log(f"Records with coding_index: {with_coding}")
    log(f"Records with math_index: {with_math}")
    
    # Show top 5 by intelligence index
    top5 = sorted(
        [r for r in all_records if r.get("artificial_analysis_intelligence_index") is not None],
        key=lambda x: x["artificial_analysis_intelligence_index"],
        reverse=True
    )[:5]
    
    log("Top 5 by Intelligence Index:")
    for r in top5:
        log(f"  {r['name']}: {r['artificial_analysis_intelligence_index']} (coding: {r['artificial_analysis_coding_index']}, math: {r['artificial_analysis_math_index']})")
    
    return len(all_records)

if __name__ == "__main__":
    count = main()
    sys.exit(0 if count > 0 else 1)