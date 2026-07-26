#!/usr/bin/env python3
"""
ILMA Vane Adapter v1.0  (2026-06-01)  — Perplexica-Vane research engine for ILMA
================================================================================
Wraps the LIVE Vane (Perplexica) service at http://127.0.0.1:3030 so ILMA can do
agentic web research (reason -> SearXNG search -> synthesize with citations),
FREE-only (NVIDIA NIM chat model + local Transformers embeddings).

Intelligent autonomous use:
  - detect_mode(query)  -> picks focusMode + optimizationMode from query intent
  - vane_research(query) -> returns {ok, answer, sources[], mode, model}
  - graceful fallback to ilma_research_engine (Tavily) if Vane is down/unconfigured.

WHY/WHEN Vane is used (vs plain Tavily):
  - discussions (reddit/forum/opini)         -> Vane discussions focus
  - academic (jurnal/paper/scholar)          -> Vane academic focus
  - deep/complex multi-question research      -> Vane quality mode
  - "latest/terbaru/berita" current info     -> Vane (SearXNG fresh)
  - simple factual lookup                     -> Tavily (faster) unless force_vane

Credentials: configured into Vane from /root/credential/api_key.json (NVIDIA).
"""
from __future__ import annotations
import json, time, re, sys, urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ILMA_ROOT = Path("/root/.hermes/profiles/ilma")
if str(ILMA_ROOT) not in sys.path:
    sys.path.insert(0, str(ILMA_ROOT))
    sys.path.insert(0, str(ILMA_ROOT / "scripts"))

VANE_URL = "http://127.0.0.1:3030"
CHAT_MODEL = {"providerId": "nvidia-nim-free", "key": "qwen/qwen3.5-397b-a17b"}
EMBED_MODEL = {"providerId": "7f2e78e0-e72e-4a0b-810d-64443a492829", "key": "Xenova/all-MiniLM-L6-v2"}

# focusMode values Vane supports
FOCUS = {"web": "webSearch", "academic": "academicSearch",
         "discussions": "redditSearch", "writing": "writingAssistant"}


def _resolve_provider_ids() -> None:
    """Auto-detect current Vane chat/embedding provider ids (config may change)."""
    global CHAT_MODEL, EMBED_MODEL
    try:
        req = urllib.request.Request(VANE_URL + "/api/providers")
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        for p in data.get("providers", []):
            cms = p.get("chatModels", [])
            ems = p.get("embeddingModels", [])
            if cms and "nvidia" in p.get("name", "").lower():
                CHAT_MODEL = {"providerId": p["id"], "key": cms[0]["key"]}
            if ems and "transformers" in p.get("name", "").lower():
                EMBED_MODEL = {"providerId": p["id"], "key": ems[0]["key"]}
    except Exception:
        pass


def detect_mode(query: str) -> Tuple[str, str]:
    """Return (focusMode, optimizationMode) from query intent. Fast-path, no network."""
    q = query.lower()
    if any(k in q for k in ["reddit", "forum", "diskusi", "opini", "hackernews", "stackoverflow", "komunitas"]):
        return (FOCUS["discussions"], "balanced")
    if any(k in q for k in ["jurnal", "paper", "academic", "scholar", "scientific", "akademik", "studi", "penelitian", "journal"]):
        return (FOCUS["academic"], "quality")
    if any(k in q for k in ["cepat", "quick", "ringkas", "singkat", "sekilas"]):
        return (FOCUS["web"], "speed")
    if any(k in q for k in ["terbaru", "latest", "berita", "update", "perkembangan", "terkini", "2025", "2026"]):
        return (FOCUS["web"], "quality")
    qcount = query.count("?")
    if len(query.split()) >= 14 and qcount >= 2:
        return (FOCUS["web"], "quality")
    return (FOCUS["web"], "balanced")


def is_available() -> bool:
    try:
        req = urllib.request.Request(VANE_URL + "/api/config")
        with urllib.request.urlopen(req, timeout=6) as r:
            d = json.loads(r.read())
        return bool(d.get("values", {}).get("setupComplete"))
    except Exception:
        return False


def _parse_stream(raw: str) -> Dict[str, Any]:
    """Parse Vane NDJSON stream. Vane emits typed blocks (text/source/research)
    whose content is filled via updateBlock patches at /data (cumulative replace).
    We track block ids by type and keep the final value of each."""
    text_block_ids = set()
    source_block_ids = set()
    block_text = {}      # blockId -> latest full text
    block_sources = {}   # blockId -> list of source dicts
    reasoning = []
    direct_answer = []

    def _norm_sources(val):
        out = []
        if isinstance(val, list):
            for s in val:
                if isinstance(s, dict):
                    md = s.get("metadata", {}) if isinstance(s.get("metadata"), dict) else {}
                    url = s.get("url") or md.get("url") or s.get("link") or ""
                    title = s.get("title") or md.get("title") or s.get("pageContent", "")[:60] or ""
                    if url:
                        out.append({"title": title, "url": url})
        return out

    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except Exception:
            continue
        et = ev.get("type")
        blk = ev.get("block") or {}
        if et == "block" and isinstance(blk, dict):
            bid = blk.get("id"); bt = blk.get("type")
            if bt == "text":
                text_block_ids.add(bid)
                d = blk.get("data")
                if isinstance(d, str):
                    block_text[bid] = d
            elif bt == "source":
                source_block_ids.add(bid)
                block_sources[bid] = _norm_sources(blk.get("data"))
        elif et == "updateBlock":
            bid = ev.get("blockId")
            for op in (ev.get("patch") or []):
                val = op.get("value")
                path = op.get("path", "")
                if bid in text_block_ids and path in ("/data", "data") and isinstance(val, str):
                    block_text[bid] = val   # cumulative replace -> keep latest
                elif bid in source_block_ids and "data" in path:
                    srcs = _norm_sources(val)
                    if srcs:
                        block_sources[bid] = srcs
                # reasoning substeps
                if isinstance(val, list):
                    for ss in val:
                        if isinstance(ss, dict) and ss.get("type") == "reasoning" and ss.get("reasoning"):
                            reasoning.append(ss["reasoning"])
        elif et in ("message", "response", "answer"):
            d = ev.get("data") or ev.get("content")
            if isinstance(d, str):
                direct_answer.append(d)

    answer = "".join(direct_answer).strip()
    if not answer and block_text:
        # join all text blocks in order of appearance
        answer = "\n\n".join(v for v in block_text.values() if v).strip()
    sources = []
    seen = set()
    for lst in block_sources.values():
        for sdict in lst:
            u = sdict.get("url")
            if u and u not in seen:
                seen.add(u); sources.append(sdict)
    return {"answer": answer, "sources": sources, "reasoning": reasoning}




VANE_CONTAINER = "ilma-vane"


def ensure_vane_running(timeout: int = 25) -> bool:
    """Autonomous self-heal: if Vane is down, start the native ilma-vane container.
    Returns True if Vane becomes available. Native ILMA (no OpenClaw dependency)."""
    if is_available():
        return True
    try:
        import subprocess, time as _t
        r = subprocess.run(["docker", "ps", "-a", "--filter", "name=" + VANE_CONTAINER,
                            "--format", "{{.Names}}"],
                           capture_output=True, text=True, timeout=10)
        if VANE_CONTAINER in (r.stdout or ""):
            subprocess.run(["docker", "start", VANE_CONTAINER], capture_output=True, timeout=20)
        else:
            subprocess.run(["docker", "run", "-d", "--name", VANE_CONTAINER,
                            "--restart", "unless-stopped", "-p", "3030:3000",
                            "-v", "/root/.hermes/profiles/ilma/vane/data:/home/vane/config",
                            "-v", "/root/.hermes/profiles/ilma/vane/data:/home/vane/data",
                            "itzcrazykns1337/vane:latest"], capture_output=True, timeout=40)
        for _ in range(timeout):
            if is_available():
                return True
            _t.sleep(1)
    except Exception:
        pass
    return is_available()


def vane_research(query: str, *, focus: Optional[str] = None,
                  optimization: Optional[str] = None, timeout: int = 150) -> Dict[str, Any]:
    """Run an agentic Vane research query. Returns dict with answer + sources."""
    _resolve_provider_ids()
    fm, om = detect_mode(query)
    fm = focus or fm
    om = optimization or om
    payload = {
        "message": {"content": query, "chatId": "ilma-" + str(int(time.time())), "messageId": "m1"},
        "chatModel": CHAT_MODEL, "embeddingModel": EMBED_MODEL,
        "optimizationMode": om, "focusMode": fm, "history": [],
    }
    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(VANE_URL + "/api/chat", data=data,
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", errors="replace")
        parsed = _parse_stream(raw)
        ok = bool(parsed["answer"]) or bool(parsed["sources"])
        return {"ok": ok, "engine": "vane", "answer": parsed["answer"],
                "sources": parsed["sources"], "reasoning": parsed["reasoning"],
                "mode": fm, "optimization": om, "model": CHAT_MODEL["key"]}
    except Exception as e:
        return {"ok": False, "engine": "vane", "error": str(e)[:160],
                "answer": "", "sources": []}


def research(query: str, *, depth: str = "deep", prefer_vane: bool = True,
             max_sources: int = 20) -> Dict[str, Any]:
    """Smart research: use Vane when beneficial, else/fallback Tavily research engine.

    Returns a manifest-compatible dict (sources/claims/answer) so callers
    (scriptorium/research engine) can consume either source.
    """
    fm, _ = detect_mode(query)
    use_vane = prefer_vane and is_available() and (
        fm in (FOCUS["academic"], FOCUS["discussions"]) or depth in ("deep", "standard")
    )
    if use_vane:
        ensure_vane_running()
        v = vane_research(query)
        if v.get("ok") and (v.get("sources") or len(v.get("answer", "")) > 200):
            return {
                "engine": "vane", "question": query, "answer": v["answer"],
                "sources": [{"id": f"src_{i+1:03d}", "title": s.get("title", ""),
                             "url": s.get("url", ""), "grade": "B", "snippet": ""}
                            for i, s in enumerate(v["sources"])],
                "claims": [], "mode": v.get("mode"),
                "methodology": {"engine": "perplexica_vane", "focus": v.get("mode"),
                                "source_count": len(v["sources"])},
                "limitations": ["Agentic web research via Vane/SearXNG; verify critical facts."],
            }
    # fallback to Tavily-based research engine
    try:
        import ilma_research_engine as re_engine
        m = re_engine.research(query, depth=depth, max_sources=max_sources)
        m["engine"] = "tavily_fallback"
        return m
    except Exception as e:
        return {"engine": "none", "question": query, "sources": [], "claims": [],
                "error": str(e)[:160]}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="ILMA Vane (Perplexica) research adapter")
    ap.add_argument("query", nargs="?", default="manfaat energi surya untuk rumah tangga")
    ap.add_argument("--health", action="store_true")
    ap.add_argument("--raw", action="store_true", help="direct vane (no fallback)")
    a = ap.parse_args()
    if a.health:
        print("vane available:", is_available())
        sys.exit(0)
    if a.raw:
        r = vane_research(a.query)
    else:
        r = research(a.query)
    print(json.dumps({k: v for k, v in r.items() if k not in ("answer",)}, indent=2, default=str)[:800])
    ans = r.get("answer", "")
    if ans:
        print("\n--- ANSWER (first 500 chars) ---\n" + ans[:500])
