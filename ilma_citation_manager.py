#!/usr/bin/env python3
"""
ILMA Citation Manager v2.0  (2026-06-02)
========================================
Formats VALIDATED source metadata (from ilma_reference_engine) into correct
in-text citations + bibliography across major styles. NEVER fabricates metadata:
missing author -> site/org; missing year -> "n.d."/"t.t.".

Styles: APA-7, IEEE, MLA, Chicago, Harvard, Vancouver, "links" (web), "auto".

API:
  CitationManager(manifest, style="auto", doc_type="paper", language="id")
    .cite(source_id) -> in-text marker ("[n]" numeric / "(Author, Year)" author-date)
    .citation_for_claim(claim_id) -> marker
    .bibliography(include_all=False) -> str (markdown)
    .consistency_report() -> dict (cited-not-listed / listed-not-cited)
"""
from __future__ import annotations
import re
from datetime import datetime
from urllib.parse import urlparse
from typing import Any, Dict, List, Optional

# doc_type -> default style
DOCTYPE_STYLE = {
    "paper": "ieee", "thesis": "apa", "tesis": "apa", "disertasi": "apa", "skripsi": "apa",
    "report": "apa", "makalah": "apa", "jurnal": "apa", "book": "chicago",
    "article": "apa", "blog": "links", "esai": "apa", "whitepaper": "ieee",
    "novel": "links", "cerpen": "links", "documentation": "links",
    "proposal": "apa", "modul": "apa", "other": "apa",
}
NUMERIC_STYLES = {"ieee", "vancouver"}
AUTHOR_DATE_STYLES = {"apa", "harvard", "chicago_ad"}


def _nd(language: str) -> str:
    return "t.t." if language == "id" else "n.d."


def _author_family(authors: List[str]) -> Optional[str]:
    if not authors:
        return None
    a = authors[0].strip()
    # "First Last" -> "Last"; "Last, First" -> "Last"
    if "," in a:
        return a.split(",")[0].strip()
    parts = a.split()
    return parts[-1] if parts else a


def _authors_str(authors: List[str], style: str, language: str) -> str:
    if not authors:
        return ""
    fams = []
    for a in authors[:6]:
        a = a.strip()
        if "," in a:
            fams.append(a)
        else:
            p = a.split()
            if len(p) >= 2:
                fams.append(f"{p[-1]}, {' '.join(w[0] + '.' for w in p[:-1])}")
            else:
                fams.append(a)
    if style in ("apa", "harvard"):
        if len(fams) == 1:
            return fams[0]
        if len(fams) <= 5:
            return ", ".join(fams[:-1]) + ", & " + fams[-1]
        return ", ".join(fams[:5]) + ", et al."
    if style == "mla":
        first = authors[0]
        if "," not in first and len(first.split()) >= 2:
            p = first.split(); first = f"{p[-1]}, {' '.join(p[:-1])}"
        return first + (", et al." if len(authors) > 1 else "")
    # ieee/vancouver/chicago: initials first
    out = []
    for a in authors[:6]:
        if "," in a:
            fam, rest = [x.strip() for x in a.split(",", 1)]
            out.append(f"{' '.join(w[0] + '.' for w in rest.split())} {fam}")
        else:
            p = a.split()
            out.append(f"{' '.join(w[0] + '.' for w in p[:-1])} {p[-1]}" if len(p) >= 2 else a)
    return ", ".join(out)


class CitationManager:
    def __init__(self, manifest: Dict[str, Any], style: str = "auto",
                 doc_type: str = "paper", language: str = "id"):
        self.manifest = manifest or {}
        self.doc_type = doc_type
        self.language = language
        self.style = (DOCTYPE_STYLE.get(doc_type, "apa") if style in (None, "auto") else style).lower()
        self.sources = {s["id"]: s for s in self.manifest.get("sources", [])}
        self.claims = {c["id"]: c for c in self.manifest.get("claims", [])}
        self._order: List[str] = []

    # ── numbering / keys ──
    def _num(self, source_id: str) -> Optional[int]:
        if source_id not in self.sources:
            return None
        if source_id not in self._order:
            self._order.append(source_id)
        return self._order.index(source_id) + 1

    def cite(self, source_id: str) -> str:
        if source_id not in self.sources:
            return ""
        n = self._num(source_id)
        if self.style in NUMERIC_STYLES:
            return f"[{n}]"
        if self.style in AUTHOR_DATE_STYLES:
            s = self.sources[source_id]
            fam = _author_family(s.get("authors")) or (s.get("site_name") or urlparse(s.get("url","")).netloc.replace("www.",""))
            yr = s.get("year") or _nd(self.language)
            return f"({fam}, {yr})"
        # mla: (Author page) -> (Author)
        if self.style == "mla":
            s = self.sources[source_id]
            fam = _author_family(s.get("authors")) or (s.get("site_name") or "")
            return f"({fam})" if fam else f"[{n}]"
        return f"[{n}]"

    def citation_for_claim(self, claim_id: str) -> str:
        c = self.claims.get(claim_id)
        return self.cite(c.get("source_id", "")) if c else ""

    @property
    def used_count(self) -> int:
        return len(self._order)

    # ── reference entry formatting (uses REAL metadata; n.d. if missing) ──
    def _entry(self, s: Dict[str, Any], n: int) -> str:
        st = self.style
        title = (s.get("title") or "Untitled").strip().rstrip(".")
        url = s.get("url", "")
        site = s.get("site_name") or urlparse(url).netloc.replace("www.", "")
        authors = s.get("authors") or []
        yr = s.get("year") or _nd(self.language)
        acc = s.get("accessed") or datetime.now().strftime("%Y-%m-%d")
        doi = s.get("doi")
        journal = s.get("journal")
        auth = _authors_str(authors, st, self.language)
        retrieved = ("Diakses pada" if self.language == "id" else "Retrieved")
        avail = ("Tersedia pada" if self.language == "id" else "Available")

        if st == "ieee":
            a = (auth + ", ") if auth else ""
            jr = f" {journal}," if journal else ""
            d = f" doi: {doi}." if doi else ""
            return f"[{n}] {a}\"{title},\"{jr} {site}, {yr}.{d} [Online]. {avail}: {url}"
        if st == "vancouver":
            a = (auth + ". ") if auth else ""
            return f"{n}. {a}{title}. {site}. {yr}. {avail} from: {url}"
        if st in ("apa", "harvard"):
            a = (auth + " " if auth else f"{site}. ")
            d = f" https://doi.org/{doi}" if doi else f" {url}"
            return f"{a}({yr}). {title}. {(journal + '. ') if journal else (site + '. ')}{retrieved} {acc},{d}"
        if st == "mla":
            a = (auth + ". ") if auth else ""
            return f'{a}"{title}." {site}, {yr}, {url}. Accessed {acc}.'
        if st == "chicago":
            a = (auth + ". ") if auth else ""
            return f'{n}. {a}"{title}." {site}. {yr}. Accessed {acc}. {url}.'
        # links (blog/web)
        return f"{n}. [{title}]({url}) — {site}" + (f" ({yr})" if s.get("year") else "")

    def bibliography(self, include_all: bool = False) -> str:
        ids = list(self.sources.keys()) if include_all else list(self._order)
        if include_all:
            for sid in ids:
                self._num(sid)
            ids = list(self._order)
        # APA/MLA/Harvard -> alphabetical by author/site; numeric -> citation order
        if self.style in ("apa", "mla", "harvard", "chicago"):
            def _key(sid):
                s = self.sources[sid]
                return (_author_family(s.get("authors")) or s.get("site_name") or "").lower()
            ids = sorted(ids, key=_key)
        heads = {"ieee": "References", "vancouver": "References", "apa": "Daftar Pustaka",
                 "harvard": "Daftar Pustaka", "mla": "Works Cited", "chicago": "Bibliography",
                 "links": "Sumber & Bacaan Lanjutan"}
        if self.language != "id":
            heads.update({"apa": "References", "harvard": "References", "links": "Sources & Further Reading"})
        out = [f"## {heads.get(self.style, 'References')}", ""]
        for i, sid in enumerate(ids, 1):
            n = (self._order.index(sid) + 1) if sid in self._order else i
            out.append(self._entry(self.sources[sid], n))
            if self.style not in NUMERIC_STYLES:
                out.append("")
        return "\n".join(out)

    # ── citation marker extraction (parse what actually got emitted in the doc) ──
    def _strip_bibliography(self, full_text: str) -> str:
        """Return the body text with the reference/bibliography list removed, so that
        the reference entries themselves are not mistaken for in-text citations."""
        if not full_text:
            return ""
        heads = ("references", "daftar pustaka", "works cited", "bibliography",
                 "sumber & bacaan lanjutan", "sources & further reading", "sources",
                 "sumber")
        lines = full_text.splitlines()
        for i, ln in enumerate(lines):
            s = ln.strip().lstrip("#").strip().lower().rstrip(":")
            if s in heads:
                return "\n".join(lines[:i])
        return full_text

    def extract_markers(self, full_text: str) -> Dict[str, Any]:
        """Parse citation markers ACTUALLY present in the rendered body text.

        Numeric styles (ieee/vancouver) -> set of ints from [n] (and [n]-[m] ranges /
        [n], [m] groups). Author-date styles (apa/harvard/chicago_ad) -> list of
        (family, year) tuples from (Author, Year). MLA -> list of families from (Author).
        Returns {"numeric": set[int], "author_year": [(fam, yr)...], "families": [fam...]}.
        """
        body = self._strip_bibliography(full_text or "")
        out: Dict[str, Any] = {"numeric": set(), "author_year": [], "families": []}
        # Scan ALL marker forms regardless of nominal style: drafted prose frequently
        # uses numeric [n] even when the manager's style is APA/author-date (and vice
        # versa). consistency_report() then reconciles by what is ACTUALLY present,
        # so the nominal style can't cause a false "nothing cited" verdict.
        # Numeric: [1], [1,3], [1]-[3], [1]–[5]
        for grp in re.findall(r"\[\d+(?:\s*[,\-–]\s*\d+)*\]", body):
            nums = [int(x) for x in re.findall(r"\d+", grp)]
            if len(nums) == 2 and ("-" in grp or "–" in grp) and "," not in grp:
                out["numeric"].update(range(min(nums), max(nums) + 1))
            else:
                out["numeric"].update(nums)
        # Author-date: (Author, 2023) / (Author, t.t.) / (Author, n.d.)
        for fam, yr in re.findall(
                r"\(([A-Z][\w'’.\- ]+?),\s*((?:19|20)\d{2}[a-z]?|t\.t\.|n\.d\.)\)", body):
            out["author_year"].append((fam.strip(), yr.strip()))
            out["families"].append(fam.strip())
        # MLA-style bare (Author) families (only when author-date didn't already capture)
        if not out["author_year"]:
            for m in re.findall(r"\(([A-Z][\w'’.\- ]+?)(?:,?\s*\d{1,4})?\)", body):
                fam = m.strip()
                if fam:
                    out["families"].append(fam)
        return out

    # ── QA: citation <-> bibliography consistency (REAL) ──
    def consistency_report(self, full_text: str = "") -> Dict[str, Any]:
        """Reconcile citation markers actually emitted in `full_text` against the
        bibliography entries. Reports:
          - cited_not_listed: markers in the body with NO matching reference entry
          - listed_not_cited: reference entries that are never cited in the body
        When `full_text` is empty, falls back to the runtime cite() order (legacy behavior).
        """
        listed_ids = set(self.sources.keys())

        # Legacy / no-text path: use what cite() recorded; cannot detect orphan markers.
        if not (full_text or "").strip():
            cited = set(self._order)
            return {
                "listed_not_cited": sorted(listed_ids - cited),
                "cited_not_listed": [],
                "cited": len(cited), "listed": len(listed_ids),
                "mode": "runtime",
            }

        markers = self.extract_markers(full_text)
        cited_not_listed: List[Any] = []
        cited_ids: set = set()

        # Reconcile by the marker form ACTUALLY present in the body (auto-detect),
        # not the nominal style — numeric [n] wins when present.
        if markers["numeric"]:
            # Reference numbers = position in self._order (assigned via cite()).
            # If nothing was numbered at runtime (e.g. external markdown), number all
            # listed sources by their natural order so [n] resolves to a real entry.
            if not self._order:
                for sid in self.sources:
                    self._num(sid)
            n_listed = len(self._order)
            for n in sorted(markers["numeric"]):
                if 1 <= n <= n_listed:
                    cited_ids.add(self._order[n - 1])
                else:
                    cited_not_listed.append(n)
            listed_not_cited = sorted(set(self._order) - cited_ids,
                                      key=lambda s: self._order.index(s))
        else:
            # author-date / mla: match by author family (+ year when available)
            def _fam_for(sid: str) -> str:
                s = self.sources[sid]
                return (_author_family(s.get("authors"))
                        or s.get("site_name")
                        or urlparse(s.get("url", "")).netloc.replace("www.", "")
                        or "").lower()

            fam_index: Dict[str, str] = {}   # family(lower) -> sid
            for sid in self.sources:
                fam = _fam_for(sid)
                if fam:
                    fam_index.setdefault(fam, sid)

            pairs = markers["author_year"] if self.style != "mla" else \
                [(f, "") for f in markers["families"]]
            for fam, _yr in pairs:
                sid = fam_index.get(fam.strip().lower())
                if sid:
                    cited_ids.add(sid)
                else:
                    cited_not_listed.append(fam.strip())
            listed_not_cited = sorted(listed_ids - cited_ids)

        # de-dup preserving type/order
        _seen = set(); _cnl = []
        for x in cited_not_listed:
            if x not in _seen:
                _seen.add(x); _cnl.append(x)

        return {
            "listed_not_cited": listed_not_cited,
            "cited_not_listed": _cnl,
            "cited": len(cited_ids), "listed": len(listed_ids),
            "mode": "parsed",
        }


if __name__ == "__main__":
    import json, sys
    mf = json.load(open(sys.argv[1])) if len(sys.argv) > 1 else {"sources": [
        {"id": "s1", "url": "https://www.mdpi.com/x", "title": "Solar Adoption in ASEAN",
         "authors": ["Andi Wijaya", "Budi Santoso"], "year": "2023", "journal": "Sustainability",
         "doi": "10.3390/su13042032", "site_name": "MDPI", "source_type": "journal_article"},
        {"id": "s2", "url": "https://kompas.com/x", "title": "PLTS Indonesia", "authors": [],
         "year": None, "site_name": "Kompas"},
    ], "claims": []}
    for st in ["ieee", "apa", "mla", "chicago", "harvard", "vancouver"]:
        cm = CitationManager(mf, style=st, doc_type="paper")
        print(f"--- {st} ---  cite s1={cm.cite('s1')} s2={cm.cite('s2')}")
        print(cm.bibliography(include_all=True))
        print()
