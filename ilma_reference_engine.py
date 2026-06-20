#!/usr/bin/env python3
"""
ILMA Reference Engine v1.0  (2026-06-02)
========================================
Turns raw URLs/sources into VALIDATED bibliographic metadata + credibility scoring,
WITHOUT fabricating data. Powers academic-grade citations.

For each source it extracts REAL metadata from the page (HTML meta tags + academic
`citation_*` tags + JSON-LD + DOI), classifies the source type, scores credibility,
and marks missing fields as n.d. (never invented).

API:
  enrich_source(src) -> src + {authors, year, site_name, published, accessed,
                               source_type, credibility, credibility_label, doi}
  enrich_manifest(manifest, fetch=True, max_workers=6) -> manifest (sources enriched)
  classify_source(url, meta) -> str
  credibility(url, source_type, meta) -> (score 0..1, label, primary/secondary/tertiary)

NO fabrication: if a field isn't found, it stays None -> rendered as "n.d.".
"""
from __future__ import annotations
import re
import json
import html as _html
import urllib.request
from datetime import datetime
from urllib.parse import urlparse
from typing import Any, Dict, List, Optional, Tuple

ACCESSED = datetime.now().strftime("%Y-%m-%d")

# ── domain credibility hints ─────────────────────────────────────────────────
_ACADEMIC_DOMAINS = (".edu", ".ac.id", ".ac.uk", "scholar.google", "sciencedirect.com",
                     "springer.com", "nature.com", "ieee.org", "acm.org", "arxiv.org",
                     "ncbi.nlm.nih.gov", "pubmed", "jstor.org", "doi.org", "wiley.com",
                     "tandfonline.com", "mdpi.com", "sagepub.com", "researchgate.net",
                     "semanticscholar.org", "elsevier.com", "garuda.kemdikbud.go.id",
                     "neliti.com", "sinta.kemdikbud.go.id")
_OFFICIAL_DOMAINS = (".gov", ".go.id", ".int", "who.int", "worldbank.org", "oecd.org",
                     "un.org", "iea.org", "irena.org", "bps.go.id", "kemdikbud.go.id",
                     "esdm.go.id", "europa.eu")
_NEWS_DOMAINS = ("reuters.com", "bbc.", "nytimes.com", "theguardian.com", "kompas.com",
                 "tempo.co", "detik.com", "cnnindonesia.com", "antaranews.com",
                 "thejakartapost.com", "katadata.co.id", "bisnis.com")
_TERTIARY_DOMAINS = ("wikipedia.org", "wikihow.com", "investopedia.com", "britannica.com")
_BLOG_HINTS = ("medium.com", "blogspot", "wordpress", "substack", "blog.")


def _fetch(url: str, timeout: int = 12) -> str:
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; ILMA-RefBot/1.0)",
            "Accept": "text/html,application/xhtml+xml"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read(400_000)
        enc = "utf-8"
        ct = r.headers.get("Content-Type", "") if hasattr(r, "headers") else ""
        m = re.search(r"charset=([\w-]+)", ct)
        if m:
            enc = m.group(1)
        return raw.decode(enc, "replace")
    except Exception:
        return ""


def _meta(html_text: str, *keys: str) -> Optional[str]:
    """Find first matching <meta name|property=key content=...>."""
    for k in keys:
        m = re.search(
            r'<meta[^>]*(?:property|name)\s*=\s*["\']' + re.escape(k) +
            r'["\'][^>]*content\s*=\s*["\']([^"\']+)["\']', html_text, re.I)
        if not m:
            m = re.search(
                r'<meta[^>]*content\s*=\s*["\']([^"\']+)["\'][^>]*(?:property|name)\s*=\s*["\']' +
                re.escape(k) + r'["\']', html_text, re.I)
        if m:
            return _html.unescape(m.group(1).strip())
    return None


def _meta_all(html_text: str, key: str) -> List[str]:
    out = []
    for m in re.finditer(
        r'<meta[^>]*(?:property|name)\s*=\s*["\']' + re.escape(key) +
        r'["\'][^>]*content\s*=\s*["\']([^"\']+)["\']', html_text, re.I):
        out.append(_html.unescape(m.group(1).strip()))
    return out


def _year_from(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    m = re.search(r"(19|20)\d{2}", text)
    return m.group(0) if m else None


def _json_ld(html_text: str) -> Dict[str, Any]:
    for m in re.finditer(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
                         html_text, re.I | re.S):
        try:
            data = json.loads(m.group(1).strip())
            if isinstance(data, list):
                data = data[0]
            if isinstance(data, dict):
                return data
        except Exception:
            continue
    return {}


def classify_source(url: str, meta: Dict[str, Any]) -> str:
    u = (url or "").lower()
    if meta.get("doi") or meta.get("journal"):
        return "journal_article"
    if any(d in u for d in _ACADEMIC_DOMAINS):
        return "academic"
    if any(d in u for d in _OFFICIAL_DOMAINS):
        return "official_report"
    if any(d in u for d in _NEWS_DOMAINS):
        return "news"
    if any(d in u for d in _TERTIARY_DOMAINS):
        return "tertiary"
    if any(d in u for d in _BLOG_HINTS):
        return "blog"
    og = (meta.get("og_type") or "").lower()
    if "article" in og:
        return "article"
    return "web"


# source_type -> (credibility 0..1, label, primacy)
_CRED = {
    "journal_article": (0.95, "A — peer-reviewed", "primary"),
    "academic":        (0.85, "A — academic", "primary"),
    "official_report": (0.88, "A — official/institutional", "primary"),
    "news":            (0.65, "B — reputable news", "secondary"),
    "article":         (0.55, "B — article", "secondary"),
    "tertiary":        (0.45, "C — tertiary", "tertiary"),
    "blog":            (0.35, "C — blog/popular", "tertiary"),
    "web":             (0.40, "C — general web", "tertiary"),
}


def credibility(url: str, source_type: str, meta: Dict[str, Any]) -> Tuple[float, str, str]:
    score, label, primacy = _CRED.get(source_type, (0.4, "C — general web", "tertiary"))
    if meta.get("doi"):
        score = max(score, 0.95)
    return round(score, 2), label, primacy


def enrich_source(src: Dict[str, Any], fetch: bool = True) -> Dict[str, Any]:
    url = src.get("url", "") or ""
    dom = urlparse(url).netloc.replace("www.", "") if url else ""
    meta: Dict[str, Any] = {}
    if fetch and url:
        h = _fetch(url)
        if h:
            ld = _json_ld(h)
            # title
            title = (_meta(h, "citation_title", "og:title", "dc.title", "twitter:title")
                     or (re.search(r"<title[^>]*>([^<]+)", h, re.I) or [None, None])[1])
            if title and not (src.get("title") or "").strip():
                src["title"] = _html.unescape(title.strip())[:300]
            # authors (academic citation_author repeats; else article:author/author)
            authors = _meta_all(h, "citation_author") or _meta_all(h, "dc.creator")
            if not authors:
                a = _meta(h, "author", "article:author", "dc.creator")
                if a and not a.startswith("http"):
                    authors = [a]
            if not authors and isinstance(ld.get("author"), dict):
                nm = ld["author"].get("name")
                if nm:
                    authors = [nm]
            if not authors and isinstance(ld.get("author"), list):
                authors = [a.get("name") for a in ld["author"] if isinstance(a, dict) and a.get("name")]
            meta["authors"] = [a for a in authors if a][:6]
            # date
            date = (_meta(h, "citation_publication_date", "citation_date", "article:published_time",
                          "dc.date", "datePublished", "og:updated_time")
                    or ld.get("datePublished"))
            meta["published"] = date
            meta["year"] = _year_from(date)
            # site / publisher
            meta["site_name"] = (_meta(h, "og:site_name", "citation_journal_title", "dc.publisher")
                                 or dom)
            meta["journal"] = _meta(h, "citation_journal_title")
            # DOI
            # DOI only from citation meta (page-body DOIs belong to OTHER refs, not this page)
            doi = _meta(h, "citation_doi")
            meta["doi"] = doi
            meta["og_type"] = _meta(h, "og:type")
    src["authors"] = meta.get("authors") or src.get("authors") or []
    src["year"] = meta.get("year")             # None -> n.d.
    src["published"] = meta.get("published")
    src["site_name"] = meta.get("site_name") or dom
    src["journal"] = meta.get("journal")
    src["doi"] = meta.get("doi")
    src["accessed"] = ACCESSED
    src["source_type"] = classify_source(url, meta)
    sc, lab, prim = credibility(url, src["source_type"], meta)
    src["credibility"] = sc
    src["credibility_label"] = lab
    src["primacy"] = prim
    src["metadata_complete"] = bool(src["authors"] and src["year"])
    return src


def enrich_manifest(manifest: Dict[str, Any], fetch: bool = True, max_workers: int = 6) -> Dict[str, Any]:
    sources = manifest.get("sources", [])
    if not sources:
        return manifest
    from concurrent.futures import ThreadPoolExecutor
    def _do(s):
        try:
            return enrich_source(s, fetch=fetch)
        except Exception:
            s["source_type"] = classify_source(s.get("url", ""), {})
            s["credibility"], s["credibility_label"], s["primacy"] = credibility(s.get("url",""), s["source_type"], {})
            s["accessed"] = ACCESSED
            return s
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        manifest["sources"] = list(ex.map(_do, sources))
    # academic-validity warning
    acad = sum(1 for s in manifest["sources"] if s.get("primacy") == "primary")
    manifest["source_quality"] = {
        "total": len(manifest["sources"]), "primary": acad,
        "secondary": sum(1 for s in manifest["sources"] if s.get("primacy") == "secondary"),
        "tertiary": sum(1 for s in manifest["sources"] if s.get("primacy") == "tertiary"),
        "avg_credibility": round(sum(s.get("credibility", 0) for s in manifest["sources"]) / max(1, len(manifest["sources"])), 2),
    }
    return manifest


if __name__ == "__main__":
    import sys
    test = {"sources": [{"id": "src_001", "url": sys.argv[1] if len(sys.argv) > 1
                         else "https://www.esdm.go.id/en", "title": ""}]}
    out = enrich_manifest(test, fetch=True)
    print(json.dumps(out, indent=2, ensure_ascii=False)[:1200])
