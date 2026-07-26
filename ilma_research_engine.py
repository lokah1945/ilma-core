#!/usr/bin/env python3
"""
ILMA Research Engine v1.0  (2026-06-01)  — Perplexica-style research wrapper
============================================================================
Unifies ILMA's existing free research engine (deep_search/crawl) into a clean
API that produces a graded Research Manifest: question -> queries -> sources
(graded A/B/C) -> extracted claims (claim->source binding) -> gaps/limitations.

This is the EVIDENCE SPINE for research-grounded writing. Free-only.

API:
  research(question, *, depth="deep", max_sources=30, subqueries=None) -> manifest dict
  grade_source(result) -> "A"|"B"|"C"
"""
from __future__ import annotations
import sys, re, json, time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

ILMA_ROOT = Path("/root/.hermes/profiles/ilma")
sys.path.insert(0, str(ILMA_ROOT))
sys.path.insert(0, str(ILMA_ROOT / "scripts"))

DEPTH_SOURCES = {"light": 10, "standard": 20, "deep": 36}

# Source grading heuristics (A=primary/authoritative, B=reputable secondary, C=tertiary)
_A_DOMAINS = (".gov", ".edu", ".int", "who.int", "nature.com", "sciencedirect",
              "springer", "ieee.org", "acm.org", "arxiv.org", "ncbi.nlm.nih.gov",
              "pubmed", "jstor", "doi.org", "oecd.org", "worldbank.org", "un.org")
_B_DOMAINS = ("wikipedia.org", "reuters.com", "bbc.", "nytimes.com", "theguardian",
              "economist.com", "mckinsey", "harvard", "stanford", "mit.edu",
              "ucs.org", "epa.gov", "iea.org", "irena.org")


def grade_source(result: Dict[str, Any]) -> str:
    url = (result.get("url") or "").lower()
    q = float(result.get("quality_score") or 0)
    dom = urlparse(url).netloc.lower()
    if any(d in url for d in _A_DOMAINS):
        return "A"
    if any(d in url for d in _B_DOMAINS):
        return "B"
    if q >= 70:
        return "B"
    return "C"




def _topic_tokens(question: str) -> set:
    import re as _re
    stop = {"the","a","an","of","for","to","and","or","in","on","untuk","dan","di",
            "yang","ke","dari","pada","apa","manfaat","dampak","atau","the","is"}
    toks = {t for t in _re.findall(r"[a-z0-9]+", question.lower()) if len(t) > 2 and t not in stop}
    return toks


def _relevance(question_tokens: set, result: dict) -> float:
    """0..1 topical relevance from title+snippet token overlap."""
    import re as _re
    text = ((result.get("search_title") or result.get("title") or "") + " " +
            (result.get("search_snippet") or "") + " " +
            (result.get("content_text") or "")[:500]).lower()
    rtoks = set(_re.findall(r"[a-z0-9]+", text))
    if not question_tokens:
        return 0.5
    hit = len(question_tokens & rtoks)
    return hit / len(question_tokens)


def _extract_claims(text: str, max_claims: int = 5) -> List[str]:
    """Extract candidate factual claims (sentences with numbers/strong assertions)."""
    if not text:
        return []
    sents = re.split(r"(?<=[.!?])\s+", text)
    if len(sents) < 2:
        sents = [text]  # snippet/short content -> treat as one claim candidate
    scored = []
    for s in sents:
        s = s.strip()
        if not (25 <= len(s) <= 400):
            continue
        score = 0
        if re.search(r"\d", s):
            score += 2  # has numbers/stats
        if re.search(r"\b(percent|%|study|research|found|according|data|report|shows?|increase|decrease|reduce)\b", s, re.I):
            score += 2
        if score > 0:
            scored.append((score, s))
    scored.sort(reverse=True)
    return [s for _, s in scored[:max_claims]]




def _tavily_key():
    try:
        import json as _j
        d = _j.load(open("/root/credential/api_key.json"))
        t = d.get("tavily", {})
        k = t.get("keys")
        return (k[0] if isinstance(k, list) else k) if k else (t.get("api_key") if isinstance(t, dict) else None)
    except Exception:
        return None


def _tavily_search(query: str, limit: int = 8, depth: str = "advanced") -> list:
    """Return [{url,title,content,quality_score,search_source}] from Tavily, or []."""
    key = _tavily_key()
    if not key:
        return []
    import json as _j, subprocess as _sp
    payload = _j.dumps({"api_key": key, "query": query, "max_results": limit,
                        "search_depth": depth, "include_raw_content": False,
                        "include_answer": False})
    try:
        r = _sp.run(["curl", "-s", "--max-time", "30", "https://api.tavily.com/search",
                     "-H", "Content-Type: application/json", "-d", payload],
                    capture_output=True, text=True, timeout=35)
        d = _j.loads(r.stdout)
        out = []
        for x in d.get("results", []):
            out.append({
                "url": x.get("url", ""),
                "search_title": x.get("title", ""),
                "title": x.get("title", ""),
                "content_text": x.get("content", "") or "",
                "search_snippet": x.get("content", "") or "",
                "quality_score": round(float(x.get("score", 0)) * 100, 1),
                "search_source": "tavily",
            })
        return out
    except Exception:
        return []


def research(question: str, *, depth: str = "deep", max_sources: int = None,
             subqueries: Optional[List[str]] = None, academic: bool = True) -> Dict[str, Any]:
    from ilma_free_research_pipeline import deep_search
    cap = max_sources or DEPTH_SOURCES.get(depth, 20)

    # query plan: main question + expansions/subqueries
    queries = [question]
    if subqueries:
        queries += subqueries
    elif academic:
        queries += [f"{question} statistics", f"{question} data", f"{question} overview"]
    else:
        # non-academic (blog/article): avoid arxiv-triggering keywords
        queries += [f"{question} data terbaru", f"{question} fakta", f"{question} contoh"]

    seen = set()
    sources: List[Dict[str, Any]] = []
    claims: List[Dict[str, Any]] = []
    t0 = time.time()

    qtokens = _topic_tokens(question)
    MIN_RELEVANCE = 0.34
    per_q = max(3, cap // max(1, len(queries)))
    for q in queries:
        results_list = _tavily_search(q, limit=per_q)
        if not results_list:
            try:
                results_list = deep_search(q, limit=per_q).get("results", [])
            except Exception:
                results_list = []
        for r in results_list:
            url = r.get("url", "")
            if not url or url in seen:
                continue
            # topical relevance gate — drop off-topic junk from free search
            rel = _relevance(qtokens, r)
            if rel < MIN_RELEVANCE:
                continue
            seen.add(url)
            grade = grade_source(r)
            sid = f"src_{len(sources)+1:03d}"
            title = r.get("search_title") or r.get("title") or url
            content = r.get("content_text") or ""
            snippet = r.get("search_snippet") or ""
            claim_src = content if len(content) > 80 else (snippet or content)
            src = {
                "id": sid, "title": title[:200], "url": url, "grade": grade,
                "quality_score": r.get("quality_score"),
                "search_source": r.get("search_source"), "query": q,
                "snippet": (r.get("search_snippet") or content[:300]),
            }
            sources.append(src)
            src["relevance"] = round(rel, 3)
            for c in _extract_claims(claim_src):
                claims.append({"id": f"claim_{len(claims)+1:03d}", "text": c,
                               "source_id": sid, "grade": grade, "status": "registered"})
            if len(sources) >= cap:
                break
        if len(sources) >= cap:
            break

    # ── Vane (Perplexica) enrichment: agentic SearXNG research for academic/deep ──
    vane_answer = ""
    try:
        import ilma_vane_adapter as _vane
        _fm, _ = _vane.detect_mode(question)
        if _vane.is_available() and (academic or depth == "deep"):
            _v = _vane.vane_research(question, optimization="speed", timeout=70)
            if _v.get("ok"):
                vane_answer = _v.get("answer", "")
                for _s in _v.get("sources", []):
                    _u = _s.get("url", "")
                    if _u and _u not in seen:
                        seen.add(_u)
                        sources.append({"id": f"src_{len(sources)+1:03d}",
                                        "title": (_s.get("title") or _u)[:200], "url": _u,
                                        "grade": "B", "search_source": "vane_searxng",
                                        "query": question, "snippet": "", "relevance": 1.0})
    except Exception:
        pass

    grade_counts = {"A": 0, "B": 0, "C": 0}
    for s in sources:
        grade_counts[s["grade"]] += 1

    manifest = {
        "question": question,
        "depth": depth,
        "queries": queries,
        "methodology": {
            "search_engines": sorted({s.get("search_source") for s in sources if s.get("search_source")}),
            "source_count": len(sources),
            "grade_distribution": grade_counts,
            "grading_scheme": "A=primary/authoritative (.gov/.edu/journals), B=reputable secondary, C=tertiary",
            "inclusion": "crawlable, on-topic, quality_score-ranked",
        },
        "sources": sources,
        "claims": claims,
        "gaps": [] if grade_counts["A"] + grade_counts["B"] >= 3 else
                ["Limited high-grade (A/B) sources found; treat conclusions as preliminary."],
        "limitations": [
            "Automated web research; not a substitute for systematic literature review.",
            f"Sources gathered {time.strftime('%Y-%m-%d')}; web content may change.",
        ],
        "elapsed_s": round(time.time() - t0, 1),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "vane_answer": vane_answer,
    }
    # ── Reference metadata enrichment (REAL metadata, no fabrication) ──
    # Fetch per-source meta for academic/deep docs; lighter modes skip (latency).
    try:
        if academic or depth == "deep":
            import ilma_reference_engine as _ref
            manifest = _ref.enrich_manifest(manifest, fetch=True, max_workers=6)
        else:
            import ilma_reference_engine as _ref
            manifest = _ref.enrich_manifest(manifest, fetch=False)  # classify+score only
    except Exception:
        pass
    return manifest


def save_manifest(manifest: Dict[str, Any], path: str) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    return str(p)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--depth", default="deep")
    ap.add_argument("--max-sources", type=int, default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    m = research(a.question, depth=a.depth, max_sources=a.max_sources)
    if a.out:
        save_manifest(m, a.out)
    print(json.dumps({k: v for k, v in m.items() if k not in ("sources", "claims")}, indent=2, ensure_ascii=False))
    print(f"sources={len(m['sources'])} claims={len(m['claims'])} grades={m['methodology']['grade_distribution']}")
