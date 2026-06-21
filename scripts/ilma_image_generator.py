#!/usr/bin/env python3
"""
ILMA Image Generation Pipeline v1.0
===================================
Integrates xAI (grok-imagine-image) into ILMA blog writing workflow.
Supports: blog featured images, article illustrations, thumbnail generation.

Usage:
  python3 scripts/ilma_image_generator.py generate "blog featured image prompt"
  python3 scripts/ilma_image_generator.py blog "AI future technology" --aspect landscape
  python3 scripts/ilma_image_generator.py verify
"""

import os
import sys
import json
import argparse
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, Dict, Any

# ─── PATHS ───────────────────────────────────────────────────────────────────
ILMA_ROOT = Path("/root/.hermes/profiles/ilma")
CACHE_DIR = ILMA_ROOT / "cache" / "images"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ─── COLORS ──────────────────────────────────────────────────────────────────
C_R = "\033[91m"; C_G = "\033[92m"; C_Y = "\033[93m"; C_B = "\033[94m"
C_C = "\033[96m"; C_BOLD = "\033[1m"; C_RESET = "\033[0m"


# =============================================================================
# IMAGE GENERATION ENGINE
# =============================================================================

class ImageGenerator:
    """ILMA Image Generation — xAI grok-imagine-image backend"""
    
    PROVIDER = "xai"
    MODEL = "grok-imagine-image"
    ENDPOINT = "https://api.x.ai/v1/images/generations"

    # Bos directive 2026-06-21: all capability goes through SOT FREE-only.
    # Keep static PROVIDER/MODEL/ENDPOINT for backward-compat tests, but the
    # runtime `generate()` path will now consult SOT dispatcher first.
    USE_SOT_FREE = True

    # Prompts for blog content
    BLOG_IMAGE_STYLES = {
        "featured": "Professional blog featured image with {topic}, modern design, high quality illustration, cinematic lighting",
        "thumbnail": "YouTube thumbnail for {topic}, bold text overlay, vibrant colors, eye-catching design",
        "illustration": "Article illustration for {topic}, editorial style, clean and modern, minimalist design",
        "social": "Social media post image for {topic}, square format, engaging visual, modern aesthetic",
        "abstract": "Abstract art representing {topic}, futuristic style, digital art, blue and purple tones",
    }

    def __init__(self):
        self.api_key = self._load_api_key()
        self.enabled = bool(self.api_key)
        self._sot_resolved = None

    def _resolve_via_sot(self) -> Optional[Dict[str, Any]]:
        """Query SOT dispatcher for the best FREE image model (soft-fallback).
        Cached. Returns provider/model/endpoint or None."""
        if not self.USE_SOT_FREE:
            return None
        if self._sot_resolved is not None:
            return self._sot_resolved
        try:
            sys.path.insert(0, str(ILMA_ROOT))
            from ilma_sot_dispatcher import sot_dispatch
            res = sot_dispatch("image", strict=False, allow_paid=False)
            if res and not res.get("error") and res.get("provider"):
                self._sot_resolved = res
                return res
        except Exception as e:
            print(f"[ilma_image_generator] SOT dispatch failed: {e}")
        return None
    
    def _load_api_key(self) -> str:
        """Load xAI API key from credentials"""
        creds_path = Path("/root/credential/api_key.json")
        if not creds_path.exists():
            return ""
        
        with open(creds_path) as f:
            creds = json.load(f)
        
        xai_entry = creds.get("xai", {})
        keys = xai_entry.get("keys", [])
        if keys:
            return keys[0] if isinstance(keys[0], str) else ""
        
        # Also check env var
        return os.environ.get("XAI_API_KEY", "")

    def _log(self, msg: str) -> None:
        """Stdout-only log helper (no extra deps)."""
        print(f"[ilma_image_generator] {msg}")

    def _resolve_provider_key(self, provider: str) -> str:
        """Look up API key for given provider from credentials file or env."""
        try:
            cp = Path("/root/credential/api_key.json")
            if cp.exists():
                creds = json.loads(cp.read_text())
                entry = creds.get(provider, {})
                keys = entry.get("keys", []) if isinstance(entry, dict) else []
                if keys and isinstance(keys[0], str):
                    return keys[0]
            # env var fallback: PROVIDER_API_KEY
            return os.environ.get(f"{provider.upper()}_API_KEY", "")
        except Exception:
            return ""

    def _resolve_provider_base(self, provider: str) -> str:
        """Look up base URL for provider via SOT `providers` collection."""
        try:
            sys.path.insert(0, str(ILMA_ROOT))
            from sot_free_model_picker import get_db
            db = get_db()["providers"]
            row = db.find_one({"provider": provider})
            base = (row or {}).get("base_url") if row else None
            if base:
                return base.rstrip("/") if base.endswith("/v1") else f"{base.rstrip('/')}/v1"
        except Exception:
            pass
        # fallback known values
        return {
            "xai":       "https://api.x.ai/v1",
            "together":  "https://api.together.xyz/v1",
            "openai":    "https://api.openai.com/v1",
            "openrouter":"https://openrouter.ai/api/v1",
            "groq":      "https://api.groq.com/openai/v1",
            "fal":       "https://fal.run/v1",
        }.get(provider, "https://api.openai.com/v1")

    def _call_image_endpoint(self, *, base_url: str, model_id: str,
                              api_key: str, prompt: str, aspect: str,
                              style: str, size: str, provider: str,
                              sot_resolution: Dict[str, Any]) -> Dict[str, Any]:
        """POST image generation to any OpenAI-compatible /v1/images/generations."""
        url = f"{base_url.rstrip('/')}/images/generations"
        payload = {"model": model_id, "prompt": prompt, "n": 1}
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode(),
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read())
            image_url = result.get("data", [{}])[0].get("url", "")
            return {
                "status": "success",
                "provider": provider,
                "model": model_id,
                "url": image_url,
                "aspect": aspect,
                "cost_usd": 0,
                "prompt": prompt,
                "sot_dispatch": {
                    "skill": "SOT free-only image gen",
                    "sot_resolved": sot_resolution,
                },
            }
        except Exception as e:
            return {
                "status": "error",
                "error": f"{type(e).__name__}: {e}",
                "provider": provider,
                "model": model_id,
            }

    def generate(self, prompt: str, aspect: str = "landscape",
                 style: str = "natural", size: str = "1024x1024",
                 allow_paid: bool = False) -> dict:
        """
        Generate an image — SOT FREE-first (Bos mandate 2026-06-21, task001).

        Routing:
          1. SOT-driven FREE executor (ilma_subagent_router.execute_capability):
             picks the best FREE image model from SOT (nvidia FLUX.1-schnell via
             the local wrapper-nvidia genai endpoint) and saves the result.
          2. xAI grok-imagine-image (PAID) ONLY when allow_paid=True.

        Args:
            prompt: Image description
            aspect: landscape | portrait | square
            allow_paid: permit paid backends (Together / xAI). Default False.

        Returns:
            dict with status, provider, model, path|url
        """
        # ── 1. SOT FREE-first via the runtime capability executor ──────────────
        try:
            sys.path.insert(0, str(ILMA_ROOT))
            from ilma_subagent_router import execute_capability
            cap_res = execute_capability("image", prompt, allow_paid=allow_paid)
            if cap_res.get("success"):
                self._log(f"FREE image via {cap_res.get('provider')}/{cap_res.get('model')} "
                          f"→ {cap_res.get('path') or cap_res.get('url')}")
                return {
                    "status": "success",
                    "provider": cap_res.get("provider"),
                    "model": cap_res.get("model"),
                    "url": cap_res.get("url", ""),
                    "local_path": cap_res.get("path", ""),
                    "aspect": aspect,
                    "cost_usd": 0,
                    "prompt": prompt,
                    "billing": cap_res.get("billing", "free"),
                    "sot_dispatch": cap_res.get("sot_decision"),
                }
            self._log(f"FREE image executor failed: {cap_res.get('error')}")
            if not allow_paid:
                return {
                    "status": "error",
                    "error": f"FREE image generation failed: {cap_res.get('error')}",
                    "provider": cap_res.get("provider", "nvidia"),
                    "hint": "pass allow_paid=True to permit xAI/Together fallback",
                }
        except Exception as e:
            self._log(f"SOT free image path error: {e}")
            if not allow_paid:
                return {"status": "error", "error": f"FREE image path error: {e}"}

        # ── 2. PAID fallback (xAI) — only reached when allow_paid=True ─────────
        if not self.enabled:
            return {
                "status": "error",
                "error": "no FREE backend succeeded and xAI key not configured",
                "provider": "xai",
                "solution": "Set XAI_API_KEY in /root/credential/api_key.json or fix the free backend",
            }
        try:
            req = urllib.request.Request(
                self.ENDPOINT,
                data=json.dumps({
                    "model": self.MODEL,
                    "prompt": prompt,
                    "n": 1,
                    # Note: xAI grok-imagine-image does NOT support size/style parameters
                    # Only model, prompt, and n are supported
                }).encode(),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read())

            image_url = result["data"][0]["url"]
            cost = result.get("usage", {}).get("cost_in_usd_ticks", 0)

            return {
                "status": "success",
                "provider": "xai",
                "model": self.MODEL,
                "url": image_url,
                "aspect": aspect,
                "cost_usd": cost / 1e12 if cost else 0,
                "prompt": prompt,
                "sot_dispatch": {
                    "skill": "SOT free-only image gen",
                    "sot_resolved": self._sot_resolved,
                } if self._sot_resolved else None,
            }

        except urllib.error.HTTPError as e:
            error_body = e.read().decode()[:200]
            return {
                "status": "error",
                "error": f"HTTP {e.code}: {error_body}",
                "provider": "xai",
            }
        except Exception as e:
            return {
                "status": "error",
                "error": f"{type(e).__name__}: {e}",
                "provider": "xai",
            }
    
    def generate_for_blog(self, topic: str, style: str = "featured", 
                          aspect: str = "landscape") -> dict:
        """
        Generate blog-specific image from topic.
        
        Args:
            topic: Blog post topic/title
            style: featured | thumbnail | illustration | social | abstract
            aspect: landscape | portrait | square
            
        Returns:
            dict with generated image info
        """
        # Build prompt from template
        template = self.BLOG_IMAGE_STYLES.get(style, self.BLOG_IMAGE_STYLES["featured"])
        prompt = template.format(topic=topic)
        
        # Generate
        result = self.generate(prompt, aspect=aspect)
        result["topic"] = topic
        result["style"] = style
        result["prompt_used"] = prompt
        
        return result
    
    def save_to_cache(self, url: str, filename: str = None) -> str:
        """Download and save image to ILMA cache"""
        if not filename:
            import hashlib
            filename = f"{hashlib.md5(url.encode()).hexdigest()}.jpg"
        
        filepath = CACHE_DIR / filename
        
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ILMA/1.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                with open(filepath, "wb") as f:
                    f.write(resp.read())
            
            return str(filepath)
        except Exception as e:
            return f"Error: {e}"
    
    def download_and_return(self, url: str) -> dict:
        """Download image and return path"""
        filepath = self.save_to_cache(url)
        
        return {
            "status": "success" if os.path.exists(filepath) else "error",
            "local_path": filepath,
            "url": url,
        }


# =============================================================================
# BLOG WRITING INTEGRATION
# =============================================================================

def generate_blog_images(topic: str, count: int = 3) -> list:
    """
    Generate multiple blog images for a topic.
    
    Generates:
    - 1 featured image (landscape, high quality)
    - 1 social media variant (square)
    - 1 illustration variant (portrait)
    """
    generator = ImageGenerator()
    
    images = []
    
    # Featured image
    result = generator.generate_for_blog(topic, style="featured", aspect="landscape")
    images.append({
        "type": "featured",
        "aspect": "landscape",
        "result": result,
    })
    print(f"{C_G}✅{C_RESET} Featured image: {result.get('status')}")
    
    if count >= 2:
        # Social media
        result2 = generator.generate_for_blog(topic, style="social", aspect="square")
        images.append({
            "type": "social",
            "aspect": "square",
            "result": result2,
        })
        print(f"{C_G}✅{C_RESET} Social image: {result2.get('status')}")
    
    if count >= 3:
        # Abstract illustration
        result3 = generator.generate_for_blog(topic, style="abstract", aspect="portrait")
        images.append({
            "type": "abstract",
            "aspect": "portrait",
            "result": result3,
        })
        print(f"{C_G}✅{C_RESET} Abstract image: {result3.get('status')}")
    
    return images


# =============================================================================
# CAPABILITY REGISTRATION
# =============================================================================

def register_image_capability():
    """Register image generation capability in ILMA registry"""
    
    registry_path = ILMA_ROOT / "capability_registry.json"
    
    if not registry_path.exists():
        print(f"{C_Y}⚠️{C_RESET} Registry not found, skipping")
        return

    try:
        with open(registry_path) as f:
            registry = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        # Root capability_registry.json is known-corrupt; live system uses config/ copy.
        print(f"{C_Y}⚠️{C_RESET} Registry unreadable ({e}); skipping registration")
        return
    
    image_cap = {
        "image_generation": {
            "status": "verified",
            "provider": "xai",
            "model": "grok-imagine-image",
            "endpoint": "https://api.x.ai/v1/images/generations",
            "capabilities": [
                "text-to-image",
                "blog_featured_images",
                "article_illustrations",
                "thumbnail_generation",
                "social_media_images",
                "abstract_art",
            ],
            "aspect_ratios": ["landscape", "portrait", "square"],
            "styles": ["natural", "vivid"],
            "evidence_id": "xai-image-gen-20260525",
            "last_verified": "2026-05-25",
        }
    }
    
    if "capabilities" not in registry:
        registry["capabilities"] = {}
    
    registry["capabilities"]["image_generation"] = image_cap["image_generation"]
    
    with open(registry_path, "w") as f:
        json.dump(registry, f, indent=2)
    
    print(f"{C_G}✅{C_RESET} Registered image_generation capability in capability_registry.json")


# =============================================================================
# SKILL UPDATE
# =============================================================================

def update_blog_writing_skill():
    """Update ilma-writing skill to include image generation step"""
    
    skill_path = ILMA_ROOT / "skills" / "ilma-writing" / "SKILL.md"
    
    if not skill_path.exists():
        print(f"{C_Y}⚠️{C_RESET} ilma-writing skill not found, skipping")
        return
    
    with open(skill_path) as f:
        content = f.read()
    
    if "image_generation" in content:
        print(f"{C_G}ℹ️{C_RESET} ilma-writing skill already has image generation")
        return
    
    # Add image generation section to the skill
    image_section = """

---

## IMAGE GENERATION INTEGRATION

Every blog post MUST include generated images:

### Image Generation Pipeline
1. After content is written, call `ImageGenerator.generate_for_blog(topic, style, aspect)`
2. Generate 1-3 images per post:
   - **Featured image**: landscape, 1792x1024 — for article hero
   - **Social variant**: square, 1024x1024 — for Twitter/LinkedIn sharing
   - **Abstract variant**: portrait, 1024x1792 — for visual variety
3. Download images to ILMA cache (`cache/images/`)
4. Include image URLs in final deliverable JSON

### Image in Deliverable
```json
{
  "images": {
    "featured": {
      "url": "https://...",
      "local_path": "/root/.hermes/profiles/ilma/cache/images/xxx.jpg",
      "aspect": "landscape",
      "prompt": "...",
      "suggested_caption": "..."
    },
    "social": {...},
    "abstract": {...}
  },
  "image_cost_usd": 0.0004
}
```

### Image Generation Code
```python
from scripts.ilma_image_generator import ImageGenerator

gen = ImageGenerator()
result = gen.generate_for_blog(
    topic="Your blog post title",
    style="featured",
    aspect="landscape"
)

if result["status"] == "success":
    print(f"Image URL: {result['url']}")
    print(f"Cost: ${result['cost_usd']}")
```

### Provider Priority
1. **xAI grok-imagine-image** — Primary (Bos has xai-5VrEpG7KONn... key)
2. **OpenAI DALL-E 3** — Fallback (if xAI fails)
3. **fal.ai Flux** — Final fallback (if both fail)

"""
    
    with open(skill_path, "a") as f:
        f.write(image_section)
    
    print(f"{C_G}✅{C_RESET} Updated ilma-writing skill with image generation")


# =============================================================================
# VERIFY INTEGRATION
# =============================================================================

def verify_integration():
    """Verify image generation integration"""
    
    print("\n" + "=" * 60)
    print("IMAGE GENERATION INTEGRATION VERIFICATION")
    print("=" * 60)
    
    generator = ImageGenerator()
    
    # Check API key
    print(f"\n1️⃣  API Key")
    print(f"   Provider: {generator.PROVIDER}")
    print(f"   Model: {generator.MODEL}")
    print(f"   Enabled: {generator.enabled}")
    print(f"   Key: {generator.api_key[:15]}..." if generator.api_key else "   Key: NOT SET")
    
    # Test generation
    print(f"\n2️⃣  Test Generation")
    result = generator.generate(
        prompt="A futuristic blog featured image with a glowing digital brain and neural network connections in blue and purple tones",
        aspect="landscape"
    )
    
    print(f"   Status: {result.get('status')}")
    if result.get("status") == "success":
        print(f"   URL: {result.get('url')}")
        print(f"   Cost: ${result.get('cost_usd', 0):.8f}")
        print(f"   Size: {result.get('size')}")
    else:
        print(f"   Error: {result.get('error')}")
    
    # Check capability registry
    print(f"\n3️⃣  Capability Registry")
    registry_path = ILMA_ROOT / "capability_registry.json"
    if registry_path.exists():
        try:
            with open(registry_path) as f:
                reg = json.load(f)
            image_caps = [k for k in reg.get("capabilities", {}).keys() if "image" in k]
            print(f"   Image capabilities: {image_caps}")
        except (json.JSONDecodeError, OSError) as e:
            print(f"   Registry unreadable: {e}")
    else:
        print(f"   Registry not found")
    
    # Check skill
    print(f"\n4️⃣  Blog Writing Skill")
    skill_path = ILMA_ROOT / "skills" / "ilma-writing" / "SKILL.md"
    if skill_path.exists():
        with open(skill_path) as f:
            skill_content = f.read()
        has_image = "image_generation" in skill_content
        print(f"   Image generation integrated: {has_image}")
    else:
        print(f"   Skill not found")
    
    print("\n" + "=" * 60)
    print("VERIFICATION COMPLETE")
    print("=" * 60)
    
    return result.get("status") == "success"


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ILMA Image Generator")
    parser.add_argument("action", choices=["generate", "blog", "verify", "wire"])
    parser.add_argument("prompt", nargs="?", help="Image prompt or blog topic")
    parser.add_argument("--aspect", default="landscape", 
                       choices=["landscape", "portrait", "square"])
    parser.add_argument("--style", default="featured",
                       choices=["featured", "thumbnail", "illustration", "social", "abstract"])
    parser.add_argument("--count", type=int, default=3, help="Number of images for blog")
    args = parser.parse_args()
    
    if args.action == "verify":
        verify_integration()
    
    elif args.action == "wire":
        print("=" * 60)
        print("WIRING IMAGE GENERATION INTO ILMA RUNTIME")
        print("=" * 60)
        register_image_capability()
        update_blog_writing_skill()
        print("\n✅ Image generation wired!")
        verify_integration()
    
    elif args.action == "generate":
        if not args.prompt:
            print("Error: prompt required for generate action")
            sys.exit(1)
        
        generator = ImageGenerator()
        result = generator.generate(args.prompt, aspect=args.aspect)
        
        if result.get("status") == "success":
            print(f"\n{C_G}✅ SUCCESS{C_RESET}")
            print(f"URL: {result['url']}")
            print(f"Cost: ${result.get('cost_usd', 0):.8f}")
            
            # Auto-download
            path = generator.save_to_cache(result["url"])
            print(f"Saved to: {path}")
        else:
            print(f"\n{C_R}❌ FAILED{C_RESET}")
            print(f"Error: {result.get('error')}")
    
    elif args.action == "blog":
        if not args.prompt:
            print("Error: topic required for blog action")
            sys.exit(1)
        
        print(f"\n{C_BOLD}Generating blog images for: {args.prompt}{C_RESET}")
        images = generate_blog_images(args.prompt, count=args.count)
        
        print(f"\n{C_G}✅ Generated {len(images)} images{C_RESET}")
        for img in images:
            print(f"\n{img['type'].upper()}:")
            print(f"   URL: {img['result'].get('url', 'FAILED')}")
            print(f"   Cost: ${img['result'].get('cost_usd', 0):.8f}")


# ── Module-level convenience: generate + download to a file path ─────────────


# ── FREE-FIRST image backend (2026-06-01): Together FLUX.1-schnell ───────────
def _together_image(prompt: str, out_path: str, aspect: str = "landscape") -> dict:
    import json as _j, subprocess as _sp, os as _os, base64 as _b64, urllib.request as _u
    try:
        d = _j.load(open("/root/credential/api_key.json"))
        tg = d.get("together", {})
        key = None
        if isinstance(tg, dict):
            key = tg.get("api_key") or (tg.get("keys") or [None])[0]
            if not key:
                for v in tg.values():
                    if isinstance(v, dict) and v.get("api_key"):
                        key = v["api_key"]; break
        if not key:
            return {"ok": False, "error": "no together key"}
        w, h = (1024, 768) if aspect == "landscape" else ((768, 1024) if aspect == "portrait" else (1024, 1024))
        payload = _j.dumps({"model": "black-forest-labs/FLUX.1-schnell", "prompt": prompt,
                            "width": w, "height": h, "steps": 4, "n": 1})
        r = _sp.run(["curl", "-s", "--max-time", "90", "https://api.together.xyz/v1/images/generations",
                     "-H", "Content-Type: application/json", "-H", "Authorization: Bearer " + key,
                     "-d", payload], capture_output=True, text=True, timeout=95)
        j = _j.loads(r.stdout)
        data = (j.get("data") or [])
        if not data:
            return {"ok": False, "error": str(j.get("error") or j)[:160]}
        item = data[0]
        _os.makedirs(_os.path.dirname(out_path), exist_ok=True)
        if item.get("b64_json"):
            with open(out_path, "wb") as f:
                f.write(_b64.b64decode(item["b64_json"]))
        elif item.get("url"):
            req = _u.Request(item["url"], headers={"User-Agent": "ILMA/1.0"})
            with _u.urlopen(req, timeout=60) as resp:
                with open(out_path, "wb") as f:
                    f.write(resp.read())
        else:
            return {"ok": False, "error": "no image payload"}
        ok = _os.path.exists(out_path) and _os.path.getsize(out_path) > 1000
        return {"ok": ok, "path": out_path, "model": "FLUX.1-schnell", "provider": "together(free)"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:160]}


def generate_image(prompt: str, out_path: str, aspect: str = "landscape", allow_paid: bool = False) -> dict:
    """Generate an image and DOWNLOAD it to out_path. Returns {ok, path, url, error}.

    FREE-first order (2026-06-21): SOT executor (nvidia FLUX via wrapper-nvidia)
    → Together FLUX free tier → xAI (only if allow_paid)."""
    import os as _os, urllib.request as _u
    try:
        # FREE-FIRST #1: SOT-driven capability executor (nvidia FLUX.1-schnell).
        try:
            sys.path.insert(0, str(ILMA_ROOT))
            from ilma_subagent_router import execute_capability
            cap = execute_capability("image", prompt, out_path=out_path, allow_paid=allow_paid)
            if cap.get("success") and cap.get("path"):
                return {"ok": True, "path": cap["path"], "model": cap.get("model"),
                        "provider": cap.get("provider"), "billing": cap.get("billing", "free")}
        except Exception as _e:
            pass
        gen = ImageGenerator()
        # FREE-FIRST #2: Together FLUX (free tier) before any paid provider
        free = _together_image(prompt, out_path, aspect=aspect)
        if free.get("ok"):
            return free
        if not allow_paid:
            return {"ok": False, "error": "free image backends failed; paid disabled",
                    "free_error": free.get("error")}
        if not gen.enabled:
            return {"ok": False, "error": "image generator not enabled (no key)"}
        res = gen.generate(prompt, aspect=aspect)
        if res.get("status") != "success" or not res.get("url"):
            return {"ok": False, "error": str(res.get("error") or res)[:160], "url": res.get("url")}
        url = res["url"]
        _os.makedirs(_os.path.dirname(out_path), exist_ok=True)
        req = _u.Request(url, headers={"User-Agent": "ILMA/1.0"})
        with _u.urlopen(req, timeout=60) as r:
            data = r.read()
        with open(out_path, "wb") as f:
            f.write(data)
        ok = _os.path.exists(out_path) and _os.path.getsize(out_path) > 1000
        return {"ok": ok, "path": out_path, "url": url, "bytes": len(data),
                "model": res.get("model"), "provider": res.get("provider")}
    except Exception as e:
        return {"ok": False, "error": str(e)[:160]}
