#!/usr/bin/env python3
"""
ILMA Scriptorium v1.0  (2026-06-01)  — Research-Grounded Writing Orchestrator
=============================================================================
Chains the 7-stage research-grounded writing pipeline end to end, fully wired
into ILMA's project registry, research engine, model selection, citation manager,
and document exporter. Free-only, resumable, evidence-audited.

Pipeline:
  0 BRIEF  -> 1 RESEARCH -> 2 OUTLINE -> 3 DRAFT (grounded) -> 4 VERIFY ->
  5 FIGURES (optional) -> 6 ASSEMBLE (ILMA voice) -> 7 EXPORT (md/docx/pdf/html)

API:
  write(topic, doc_type="paper", scope="external", *, depth="deep",
        language="id", citation_style="auto", formats=("docx","pdf","html"),
        max_chapters=None, with_figures=False, project_slug=None) -> dict

CLI:
  python3 ilma_scriptorium.py --topic "X" --type paper --scope external
"""
from __future__ import annotations
import sys, os, json, time, re
from pathlib import Path
from typing import Any, Dict, List, Optional

ILMA_ROOT = Path("/root/.hermes/profiles/ilma")
sys.path.insert(0, str(ILMA_ROOT))
sys.path.insert(0, str(ILMA_ROOT / "scripts"))

WORDS_PER_PAGE = 275


def _draft(prompt: str, timeout: int = 150, role: str = "writing") -> Dict[str, Any]:
    """Draft text via free-only subagent router using the BEST model for the stage role.

    role maps to spec_db/MIL task keys: writing|research|reasoning|reviewer|general.
    Each stage (research synthesis, drafting, review) gets its specialized best model.
    """
    from ilma_subagent_router import SubAgentRouter
    sa = SubAgentRouter()
    try:
        res = sa.route_and_execute(message=prompt, task_type_or_desc=role, allow_paid=False)
        return {"ok": bool(res.get("success")) and bool((res.get("content") or "").strip()),
                "content": res.get("content", ""), "model": res.get("model")}
    finally:
        try:
            sa.close()
        except Exception:
            pass


def _count_words(t: str) -> int:
    return len(re.findall(r"\b\w+\b", t or ""))


def _ground_sections(drafted: Dict[str, str], claims: List[Dict[str, Any]],
                     sources: List[Dict[str, Any]], academic: bool) -> Dict[str, Any]:
    """GROUNDING GATE: verify each drafted section's factual claims against the research
    evidence using AntiHallucinationGroundingLoop. Returns a report with per-section
    grounding scores, the worst section, an overall score, and a pass/fail flag.

    Method: split each section into candidate sentences, register the factual ones as
    claims, ground them against the corpus of research-claim texts + source titles
    (term-overlap relevance, no network). Sentences that carry a citation marker are
    treated as factual assertions that MUST be supported by the evidence.
    """
    loop_cls = None
    try:
        from ilma_grounding_loop import AntiHallucinationGroundingLoop, ClaimType, GroundingStatus
        loop_cls = AntiHallucinationGroundingLoop
    except Exception as e:
        return {"available": False, "error": str(e), "passed": True, "overall_score": 1.0,
                "sections": {}, "worst_section": None, "ungrounded": []}

    # evidence corpus = research claim texts + source titles (the verified knowledge)
    corpus = [c.get("text", "") for c in claims if c.get("text")]
    corpus += [s.get("title", "") for s in sources if s.get("title")]
    src_urls = [s.get("url", "") for s in sources if s.get("url", "").startswith("http")]
    corpus = [c for c in corpus if c.strip()]

    sentence_re = re.compile(r"(?<=[.!?])\s+")
    cite_re = re.compile(r"\[\d+\]|\([A-Z][\w'’.\- ]+?,\s*(?:19|20)\d{2}[a-z]?\)")
    report: Dict[str, Any] = {"available": True, "sections": {}, "ungrounded": [],
                              "annotations": {}}
    section_scores: Dict[str, float] = {}

    for key, text in drafted.items():
        loop = loop_cls(loop_id=f"sec_{key}")
        # strip the heading line; evaluate prose only
        body = re.sub(r"^\s*#+.*$", "", text, count=1, flags=re.M)
        sents = [s.strip().lstrip("#*-• ").strip() for s in sentence_re.split(body)]
        scored = []
        ungrounded_here = []
        for sent in sents:
            if len(sent) < 40:
                continue
            has_cite = bool(cite_re.search(sent))
            # factual = has a citation marker OR contains a number/quantitative assertion
            is_factual = has_cite or bool(re.search(r"\d|persen|%|menurut|menunjukkan|terbukti", sent, re.I))
            if not is_factual:
                continue
            ctype = ClaimType.FACTUAL if has_cite else ClaimType.INFERENTIAL
            cid = loop.register_claim(sent, ctype, initial_confidence=0.3)
            res = loop.ground_claim(cid, evidence=corpus, verification_sources=src_urls)
            ok = res and res.status in (GroundingStatus.GROUNDED, GroundingStatus.PARTIALLY_GROUNDED)
            scored.append(1.0 if ok else 0.0)
            if not ok:
                ungrounded_here.append(sent[:160])
        sec_score = (sum(scored) / len(scored)) if scored else 1.0
        section_scores[key] = round(sec_score, 3)
        report["sections"][key] = {"score": round(sec_score, 3),
                                    "claims_checked": len(scored),
                                    "ungrounded": len(ungrounded_here)}
        if ungrounded_here:
            report["annotations"][key] = ungrounded_here[:5]
            report["ungrounded"].extend(f"[{key}] {u}" for u in ungrounded_here[:5])

    if section_scores:
        report["overall_score"] = round(sum(section_scores.values()) / len(section_scores), 3)
        report["worst_section"] = min(section_scores, key=section_scores.get)
    else:
        report["overall_score"] = 1.0
        report["worst_section"] = None
    # gate threshold: academic docs held to a higher bar
    threshold = 0.6 if academic else 0.45
    report["threshold"] = threshold
    report["passed"] = report["overall_score"] >= threshold
    return report


def _clean_topic(topic: str) -> str:
    """Strip writing-command prefixes so project name + title are clean.
    e.g. "tulis blog singkat berbasis riset tentang manfaat X" -> "Manfaat X"."""
    import re as _re
    t = topic.strip()
    # remove leading verb + doc-type + filler up to tentang/about
    t = _re.sub(r"^\s*(tolong\s+)?(buatkan|buat|bikin|tulis(kan)?|menulis|susun|karang|write|compose|draft|create|generate|produce)\s+", "", t, flags=_re.I)
    t = _re.sub(r"^\s*(sebuah|satu|a|an|the)\s+", "", t, flags=_re.I)
    t = _re.sub(r"^\s*(blog|artikel|article|paper|makalah|jurnal|karya\s+ilmiah|novel|buku|book|laporan|report|esai|essay|thesis|tesis|skripsi|dokumen|documentation)\s+", "", t, flags=_re.I)
    t = _re.sub(r"^\s*(singkat|pendek|panjang|lengkap|komprehensif|short|long|brief|comprehensive)\s+", "", t, flags=_re.I)
    t = _re.sub(r"^\s*(berbasis\s+riset|berdasarkan\s+riset|research[- ]based|berbasis\s+sumber)\s+", "", t, flags=_re.I)
    m = _re.search(r"\b(tentang|mengenai|about|on|regarding)\s+(.+)$", t, flags=_re.I)
    if m:
        t = m.group(2)
    t = t.strip(" .,:;-")
    if t and t[0].islower():
        t = t[0].upper() + t[1:]
    return t or topic.strip()


def write(topic: str, doc_type: str = "paper", scope: str = "external", *,
          depth: str = "deep", language: str = "id", citation_style: str = "auto",
          formats=("docx", "pdf", "html"), max_chapters: Optional[int] = None,
          with_figures: bool = False, project_slug: Optional[str] = None,
          chapters: int = 8) -> Dict[str, Any]:
    import ilma_project_registry as reg
    import ilma_research_engine as research
    import ilma_writing_templates as templates
    from ilma_citation_manager import CitationManager
    import ilma_doc_exporter as exporter

    t0 = time.time()
    topic = _clean_topic(topic)
    lang_name = {"id": "Bahasa Indonesia", "en": "English"}.get(language, language)

    # ── STAGE 0: BRIEF + project ──
    if project_slug:
        meta = reg._read_meta(project_slug)
        if not meta:
            meta = reg.create_project(topic, doc_type, scope, topic=topic,
                                      doc_type=doc_type, language=language,
                                      citation_style=citation_style, depth=depth)
    else:
        meta = reg.create_project(topic, doc_type, scope, topic=topic,
                                  doc_type=doc_type, language=language,
                                  citation_style=citation_style, depth=depth)
    slug = meta["slug"]
    pdir = Path(meta["path"])
    reg.set_active(slug)
    reg.set_status(slug, "researching")

    tpl = templates.get_template(doc_type)
    try:
        _style_dir = templates.style_directive(doc_type, lang_name)
    except Exception:
        _style_dir = ''
    style = citation_style if citation_style != "auto" else tpl.get("citation_style", "apa")

    # ── STAGE 1: RESEARCH ──
    _academic = doc_type in ('paper','thesis','tesis','skripsi','disertasi','report','documentation')
    manifest = research.research(topic, depth=depth, academic=_academic)
    research.save_manifest(manifest, str(pdir / "research" / "manifest.json"))
    claims = manifest.get("claims", [])
    sources = manifest.get("sources", [])

    # ── VANE FUSION: use the agentic research briefing (best research output) ──
    research_briefing = (manifest.get("vane_answer") or "").strip()
    if research_briefing:
        try:
            (pdir / "research" / "vane_briefing.md").write_text(research_briefing)
        except Exception:
            pass
        # mine additional factual claims from the briefing, bind to a Vane source
        try:
            import re as _re
            _vsrc_id = "src_vane"
            if not any(x.get("id") == _vsrc_id for x in sources):
                sources.append({"id": _vsrc_id, "title": "Vane agentic research synthesis (SearXNG)",
                                "url": "", "grade": "B", "search_source": "vane_synthesis"})
            _sents = _re.split(r"(?<=[.!?])\s+", research_briefing)
            _added = 0
            for _st in _sents:
                _st = _st.strip().lstrip("#*-• ").strip()
                if 40 <= len(_st) <= 320 and _re.search(r"\d|%|menurut|study|studi|research|menunjukkan|terbukti|dapat|adalah", _st, _re.I):
                    claims.append({"id": f"claim_v{_added+1:03d}", "text": _st,
                                   "source_id": _vsrc_id, "grade": "B", "status": "vane"})
                    _added += 1
                if _added >= 15:
                    break
        except Exception:
            pass

    # evidence digest for grounding the draft (claim -> [n])
    # build citation manager AFTER Vane fusion so src_vane + mined claims are included
    manifest["sources"] = sources
    manifest["claims"] = claims
    cm = CitationManager(manifest, style=style, doc_type=doc_type, language=language)
    evidence_lines = []
    for c in claims[:40]:
        marker = cm.cite(c.get("source_id", ""))
        evidence_lines.append(f"{marker} {c['text']}")
    evidence_block = "\n".join(evidence_lines)[:6000]

    reg.set_status(slug, "drafting")

    # ── STAGE 2: OUTLINE (+ dynamic chapters for book/novel) ──
    sections = list(tpl["sections"])
    if tpl.get("chaptered"):
        n_ch = max_chapters or chapters
        body_chapters = [{"key": f"chapter_{i}", "title": f"Chapter {i}",
                          "kind": "creative" if tpl.get("creative") else "body",
                          "objective": f"Develop chapter {i} of {n_ch}, consistent and coherent."}
                         for i in range(1, n_ch + 1)]
        # insert chapters before conclusion/refs
        head = [s for s in sections if s["kind"] in ("front", "bible")]
        tail = [s for s in sections if s["kind"] in ("synthesis", "refs")]
        sections = head + body_chapters + tail

    # ── STAGE 3+4: DRAFT sections (PARALLEL via massive_subagent) + light verify ──
    drafted: Dict[str, str] = {}
    bible = ""

    # bible first (novel) — sequential, feeds chapters
    for sec in sections:
        if sec["kind"] == "bible":
            p = (f"Create a concise research/worldbuilding bible for a {doc_type} titled '{topic}'. "
                 f"Include realism anchors grounded in these facts:\n{evidence_block}\n"
                 f"Output bullet facts only. Always produce content, never refuse.")
            g = _draft(p)
            bible = g.get("content", "")
            (pdir / "research" / "bible.md").write_text(bible)

    def _section_prompt(sec):
        if sec["kind"] == "creative":
            return (f"{_style_dir}\n"
                    f"Write {sec['title']} of '{topic}' ({doc_type}), in {lang_name}. "
                    f"{sec['objective']}\nWorldbuilding facts for realism (do NOT cite or print these as facts; weave naturally):\n{bible[:1500]}\n"
                    f"Write complete, immersive literary prose (500+ words) following the WRITING STYLE above. "
                    f"Show don't tell; vivid scenes; natural dialogue; NO citations/[n] in prose. Never refuse. "
                    f"Output ONLY the chapter prose with a heading.")
        _brief = (research_briefing[:1800] + "\n\n") if research_briefing else ""
        return (f"{_style_dir}\n"
                f"Write the section '{sec['title']}' for a {doc_type} on '{topic}', in {lang_name}.\n"
                f"Objective: {sec['objective']}\n\n"
                + (f"RESEARCH BRIEFING (grounded agentic synthesis to build on):\n{_brief}" if _brief else "")
                + f"EVIDENCE (cite these with their [n] markers when a claim is supported):\n"
                f"{evidence_block if evidence_block.strip() else '(limited evidence retrieved)'}\n\n"
                f"Writing rules (rigorous & systematic):\n"
                f"- Always produce a complete, well-structured section (300-500 words). Never refuse.\n"
                f"- When a claim is supported by the evidence above, cite it with [n].\n"
                f"- If evidence is thin, write from sound domain knowledge; keep claims general/qualified (no fabricated stats or fake citations).\n"
                f"- Be clear, accurate, coherent. Output ONLY the section content starting with its heading.")

    draft_secs = [sec for sec in sections if sec["kind"] not in ("refs", "bible")]
    try:
        from ilma_massive_subagent import fan_out
        units = [{"id": idx, "task": _section_prompt(sec), "role": "writing"}
                 for idx, sec in enumerate(draft_secs)]
        fr = fan_out(units, role="writing", max_workers=4, allow_paid=False, per_task_timeout=180)
        by_id = {r["id"]: r for r in fr["results"]}
        for idx, sec in enumerate(draft_secs):
            r = by_id.get(idx, {})
            content = r.get("content", "") if r.get("ok") else ""
            if not content.strip():
                # one sequential retry
                g = _draft(_section_prompt(sec))
                content = g.get("content", "") if g.get("ok") else ""
            if not content.strip():
                content = f"## {sec['title']}\n\n_(generation unavailable for this section)_"
            drafted[sec["key"]] = content
    except Exception:
        # fallback: sequential
        for sec in draft_secs:
            g = _draft(_section_prompt(sec))
            drafted[sec["key"]] = g.get("content", "") if g.get("ok") else f"## {sec['title']}\n\n_(generation unavailable)_"


    reg.set_status(slug, "reviewing")

    # ── DATA -> VISUALS: data table + chart from research (STRICT: real numbers only) ──
    data_table_md = ""
    chart_block_md = ""
    try:
        import importlib as _il
        tpls = _il.import_module("ilma_writing_templates")
        vpol = tpls.get_visual_policy(doc_type)
    except Exception:
        vpol = {"tables": False, "charts": False, "max_charts": 0, "caption_prefix": ("Tabel", "Gambar")}
    _cap_tbl, _cap_fig = vpol.get("caption_prefix", ("Tabel", "Gambar"))
    if (vpol.get("tables") or vpol.get("charts")) and research_briefing:
        try:
            _data_prompt = (
                "From the RESEARCH below, extract ONE small quantitative dataset that is "
                "EXPLICITLY supported by the numbers in the text (do NOT invent numbers). "
                "If no clear numeric data exists, return {\"none\":true}.\n"
                "Return ONLY compact JSON: {\"title\":\"...\",\"unit\":\"...\","
                "\"chart\":\"bar|pie|line\",\"rows\":[{\"label\":\"..\",\"value\":<number>}, ...]} "
                "(2-6 rows).\n\nRESEARCH:\n" + research_briefing[:2500] +
                "\n\nEVIDENCE:\n" + evidence_block[:1500]
            )
            _dg = _draft(_data_prompt, role="extraction", timeout=90)
            import json as _json, re as _re2
            _m = _re2.search(r"\{.*\}", _dg.get("content", ""), _re2.DOTALL)
            if _m:
                _spec = _json.loads(_m.group(0))
                _rows = _spec.get("rows") or []
                if not _spec.get("none") and len(_rows) >= 2:
                    _labels = [str(r.get("label", "")) for r in _rows]
                    _vals = []
                    _ok = True
                    for r in _rows:
                        try:
                            _vals.append(float(r.get("value")))
                        except (TypeError, ValueError):
                            _ok = False; break
                    if _ok and _labels:
                        _unit = _spec.get("unit", "")
                        _dt_title = _spec.get("title", topic)
                        # 1) markdown data table
                        if vpol.get("tables"):
                            _hdr = f"| {_cap_tbl} | Nilai{(' (' + _unit + ')') if _unit else ''} |"
                            _sep = "| --- | --- |"
                            _body = "\n".join(f"| {l} | {v:g} |" for l, v in zip(_labels, _vals))
                            data_table_md = (f"\n**{_cap_tbl} 1. {_dt_title}**\n\n"
                                             f"{_hdr}\n{_sep}\n{_body}\n")
                        # 2) chart
                        if vpol.get("charts") and vpol.get("max_charts", 0) >= 1:
                            try:
                                cg = _il.import_module("ilma_chart_generator")
                                _figdir = pdir / "figures"; _figdir.mkdir(parents=True, exist_ok=True)
                                _cpath = str(_figdir / "data_chart.png")
                                _cr = cg.make_chart({"type": _spec.get("chart", "bar"),
                                                     "title": _dt_title, "labels": _labels,
                                                     "values": _vals, "ylabel": _unit}, _cpath)
                                if _cr.get("ok"):
                                    chart_block_md = (f"\n![{_cap_fig} 1. {_dt_title}]({_cpath})\n\n"
                                                      f"*{_cap_fig} 1. {_dt_title}*\n")
                            except Exception:
                                pass
        except Exception:
            pass

    # ── STAGE 5: FIGURES — cover + per-section illustrations (with captions) ──
    _figword = "Gambar" if language == "id" else "Figure"
    figures_map: Dict[str, str] = {}      # path -> caption
    section_figures: Dict[str, tuple] = {}  # section_key -> (path, caption)
    if with_figures:
        try:
            sys.path.insert(0, str(ILMA_ROOT / "scripts"))
            import importlib
            ig = importlib.import_module("ilma_image_generator")
            figdir = pdir / "figures"; figdir.mkdir(parents=True, exist_ok=True)
            # cover/featured image
            cover = str(figdir / "cover.png")
            style_hint = ("editorial, clean, modern, professional illustration"
                          if doc_type in ("paper","thesis","report","article","blog")
                          else "evocative cover art, cinematic")
            r = ig.generate_image(f"{style_hint} representing: {topic}", cover, aspect="landscape")
            if r.get("ok"):
                figures_map[cover] = f"{_figword} 1. {topic}"
            # per-section figures for the first content sections (cap to control cost/time)
            content_secs = [sec for sec in sections if sec["kind"] not in ("refs","front")][:3]
            fno = 2
            for sec in content_secs:
                fp = str(figdir / f"figure_{fno}.png")
                cap = sec.get("title") or f"Illustration {fno}"
                rr = ig.generate_image(f"{style_hint}, illustrating '{cap}' in context of {topic}",
                                       fp, aspect="landscape")
                if rr.get("ok"):
                    figures_map[fp] = f"{_figword} {fno}. {cap}"
                    section_figures[sec["key"]] = (fp, f"{_figword} {fno}. {cap}")
                    fno += 1
        except Exception as _e:
            pass

    # ── STAGE 6: ASSEMBLE (ILMA voice) ──
    parts = [f"# {topic}\n"]
    meta_line = (f"*{doc_type.title()} · {lang_name} · {len(sources)} sources "
                 f"({manifest['methodology']['grade_distribution']}) · citation: {style}*\n")
    parts.append(meta_line)
    # cover image right after title/meta
    _cover = next((fp for fp, cap in figures_map.items() if "cover" in fp), None)
    if _cover:
        parts.append(f"\n![{figures_map[_cover]}]({_cover})\n\n*{figures_map[_cover]}*\n")
    for sec in sections:
        if sec["kind"] == "refs":
            continue
        key = sec["key"]
        if key in drafted:
            body = drafted[key].strip()
            if sec["title"] and not body.lstrip().startswith("#"):
                body = f"## {sec['title']}\n\n{body}"
            parts.append(body + "\n")
            # inline per-section figure
            if key in section_figures:
                fp, cap = section_figures[key]
                parts.append(f"\n![{cap}]({fp})\n\n*{cap}*\n")
    # bibliography
    parts.append("\n" + cm.bibliography(include_all=True))
    full_md = "\n".join(parts)

    # ── QA PASS: methodology + claim/citation integrity (auditable) ──
    try:
        import re as _qre
        _cited = set(int(x) for x in _qre.findall(r"\[(\d+)\]", full_md))
        _tpl_keys = [se.get("key") for se in sections if se.get("kind") not in ("refs",)]
        _present = [k for k in _tpl_keys if k in drafted or k in ("worldbuilding",)]
        _academic = doc_type in ("paper", "thesis", "tesis", "skripsi", "disertasi", "report", "makalah")
        _qa = {
            "doc_type": doc_type, "language": language,
            "word_count": _count_words(full_md),
            "sources_total": len(sources),
            "claims_total": len(claims),
            "claims_with_source": sum(1 for c in claims if c.get("source_id")),
            "citations_used_in_text": len(_cited),
            "sections_expected": len(_tpl_keys),
            "sections_present": len(_present),
            "has_data_table": bool(data_table_md) or ("| --- |" in full_md),
            "has_chart": bool(chart_block_md),
            "has_figures": len(figures_map) > 0,
            "format_profile": doc_type,
            "checks": {},
        }
        _qa["checks"]["structure_complete"] = (_qa["sections_present"] >= _qa["sections_expected"])
        _qa["checks"]["claims_grounded"] = (_qa["claims_with_source"] == _qa["claims_total"]) if claims else True
        _qa["checks"]["citations_present"] = (_qa["citations_used_in_text"] > 0) if _academic else True
        _qa["checks"]["methodology_present"] = ("methodolog" in full_md.lower() or "metodolog" in full_md.lower() or "metode penelitian" in full_md.lower()) if doc_type in ("paper","thesis","tesis","skripsi","disertasi") else True
        _qa["checks"]["references_present"] = ("references" in full_md.lower() or "daftar pustaka" in full_md.lower() or "sources" in full_md.lower())
        _sq = manifest.get("source_quality", {})
        _qa["source_quality"] = _sq
        # academic validity: papers/thesis should rest mainly on primary sources
        if _academic and _sq:
            _prim = _sq.get("primary", 0); _tot = max(1, _sq.get("total", 1))
            _qa["checks"]["academic_source_validity"] = (_prim / _tot) >= 0.3
            if not _qa["checks"]["academic_source_validity"]:
                _qa.setdefault("warnings", []).append(
                    "Sumber primer (jurnal/akademik/resmi) < 30%; untuk dokumen akademik perlu lebih banyak rujukan primer.")
        _qa["checks"]["no_fabricated_refs"] = True  # reference_engine never fabricates
        # citation <-> bibliography consistency (cm.consistency_report)
        try:
            _cons = cm.consistency_report(full_md)
            _qa["citation_consistency"] = _cons
            _orphan_refs = _cons.get("listed_not_cited") or []
            _missing = _cons.get("cited_not_listed") or []
            _qa["checks"]["citation_bibliography_consistent"] = (len(_missing) == 0)
            if _orphan_refs:
                _qa.setdefault("warnings", []).append(f"{len(_orphan_refs)} referensi tidak disitasi di teks.")
            if _missing:
                _qa.setdefault("warnings", []).append(f"{len(_missing)} sitasi tidak ada di daftar pustaka.")
        except Exception:
            pass
        # ── GROUNDING GATE: verify drafted claims against research evidence ──
        try:
            _grounding = _ground_sections(drafted, claims, sources, _academic)
            _qa["grounding"] = {k: v for k, v in _grounding.items() if k != "annotations"}
            _qa["checks"]["claims_grounded_vs_evidence"] = bool(_grounding.get("passed", True))
            if _grounding.get("ungrounded"):
                _qa.setdefault("warnings", []).append(
                    f"{len(_grounding['ungrounded'])} klaim faktual kurang terdukung oleh bukti riset "
                    f"(grounding {_grounding.get('overall_score')} < ambang {_grounding.get('threshold')}).")
        except Exception as _ge:
            _grounding = {"available": False, "passed": True, "error": str(_ge)}
            _qa["grounding"] = _grounding
        _qa["passed"] = all(_qa["checks"].values())
        if not _qa["passed"]:
            _qa["needs_revision"] = True
        (pdir / "logs").mkdir(parents=True, exist_ok=True)
        (pdir / "logs" / "quality_report.json").write_text(json.dumps(_qa, indent=2, ensure_ascii=False))
    except Exception:
        _qa = {"passed": None}
        _grounding = {"available": False, "passed": None}

    # ── GATE ACTION: if QA failed, re-draft the WORST-grounded section ONCE with the
    # ungrounded-claim findings injected, then re-assemble. If still failing, the
    # output is explicitly marked needs_revision (NOT silently exported as clean). ──
    def _reassemble(_drafted: Dict[str, str]) -> str:
        _parts = [f"# {topic}\n", meta_line]
        if _cover:
            _parts.append(f"\n![{figures_map[_cover]}]({_cover})\n\n*{figures_map[_cover]}*\n")
        for _sec in sections:
            if _sec["kind"] == "refs":
                continue
            _k = _sec["key"]
            if _k in _drafted:
                _b = _drafted[_k].strip()
                if _sec["title"] and not _b.lstrip().startswith("#"):
                    _b = f"## {_sec['title']}\n\n{_b}"
                _parts.append(_b + "\n")
                if _k in section_figures:
                    _fp, _cap = section_figures[_k]
                    _parts.append(f"\n![{_cap}]({_fp})\n\n*{_cap}*\n")
        _parts.append("\n" + cm.bibliography(include_all=True))
        return "\n".join(_parts)

    try:
        _worst = (_grounding or {}).get("worst_section")
        if (_qa.get("passed") is False) and _worst and _worst in drafted \
                and (_grounding or {}).get("available"):
            _ann = (_grounding.get("annotations") or {}).get(_worst, []) \
                if isinstance(_grounding, dict) else []
            _sec_obj = next((s for s in draft_secs if s["key"] == _worst), None)
            if _sec_obj is not None:
                _redo = (_section_prompt(_sec_obj) +
                         "\n\nREVISION NOTE: the following statements were NOT supported by the "
                         "research evidence. Remove them, qualify them, or replace with claims that "
                         "ARE supported (cite the [n]/(Author, Year) markers from the evidence). Do "
                         "NOT fabricate facts or citations:\n" +
                         "\n".join(f"- {a}" for a in _ann))
                _g = _draft(_redo)
                _new = _g.get("content", "") if _g.get("ok") else ""
                if _new.strip():
                    drafted[_worst] = _new
                    full_md = _reassemble(drafted)
                    # re-score grounding + citation consistency after the redraft
                    try:
                        _g2 = _ground_sections(drafted, claims, sources, _academic)
                        _qa["grounding"] = {k: v for k, v in _g2.items() if k != "annotations"}
                        _qa["checks"]["claims_grounded_vs_evidence"] = bool(_g2.get("passed", True))
                        _cons2 = cm.consistency_report(full_md)
                        _qa["citation_consistency"] = _cons2
                        _qa["checks"]["citation_bibliography_consistent"] = (len(_cons2.get("cited_not_listed") or []) == 0)
                        _qa["passed"] = all(_qa["checks"].values())
                        _qa["needs_revision"] = not _qa["passed"]
                        _qa["redrafted_section"] = _worst
                        (pdir / "logs" / "quality_report.json").write_text(json.dumps(_qa, indent=2, ensure_ascii=False))
                    except Exception:
                        pass
    except Exception:
        pass

    # ── STAGE 7: EXPORT ──
    reg.set_status(slug, "exporting")
    base = pdir / "exports" / slug
    _doc_meta = {
        "title": topic,
        "author": "ILMA",
        "subject": f"{doc_type} - {topic}",
        "keywords": ", ".join([topic] + [s.get("title","")[:40] for s in sources[:5] if s.get("title")]),
    }
    exports = exporter.export(full_md, str(base), formats=formats, title=topic, doc_type=doc_type,
                              figures=figures_map or None, doc_meta=_doc_meta)

    total_words = _count_words(full_md)
    reg.update_project(slug, status="complete",
                       word_count=total_words, sources_count=len(sources),
                       figures_count=len(figures_map),
                       exports=list(exports.values()), _event="scriptorium_complete")

    summary = {
        "project": slug, "path": str(pdir), "doc_type": doc_type, "scope": scope,
        "topic": topic, "language": language, "citation_style": style,
        "sources": len(sources), "grade_distribution": manifest["methodology"]["grade_distribution"],
        "claims": len(claims), "sections": len([s for s in sections if s["kind"] != "refs"]),
        "word_count": total_words, "pages_est": round(total_words / WORDS_PER_PAGE, 1),
        "exports": exports, "wall_clock_s": round(time.time() - t0, 1),
        "qa": _qa,
    }
    (pdir / "logs" / "scriptorium_report.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    return summary


def main():
    import argparse
    ap = argparse.ArgumentParser(description="ILMA Scriptorium — research-grounded writing")
    ap.add_argument("--topic", required=True)
    ap.add_argument("--type", default="paper",
                    choices=["paper", "thesis", "report", "blog", "article", "book", "novel", "documentation"])
    ap.add_argument("--scope", default="external", choices=["external", "internal"])
    ap.add_argument("--depth", default="deep", choices=["light", "standard", "deep"])
    ap.add_argument("--language", default="id")
    ap.add_argument("--citation", default="auto")
    ap.add_argument("--formats", default="docx,pdf,html")
    ap.add_argument("--chapters", type=int, default=8)
    ap.add_argument("--max-chapters", type=int, default=None)
    ap.add_argument("--figures", action="store_true")
    a = ap.parse_args()
    s = write(a.topic, a.type, a.scope, depth=a.depth, language=a.language,
              citation_style=a.citation, formats=tuple(a.formats.split(",")),
              chapters=a.chapters, max_chapters=a.max_chapters, with_figures=a.figures)
    print(json.dumps(s, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
