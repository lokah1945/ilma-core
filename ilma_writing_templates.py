#!/usr/bin/env python3
"""
ILMA Writing Templates v1.0  (2026-06-01)
=========================================
Document-type structural templates for research-grounded writing. Each template
defines the section plan; the Scriptorium drafts each section grounded in the
research manifest's claims/sources.

API:
  get_template(doc_type) -> dict {sections:[{key,title,objective,kind}], style, ...}
  Section kinds: "front" (abstract/intro), "body" (researched), "synthesis"
                 (conclusion), "refs" (bibliography), "creative" (novel prose).
"""
from __future__ import annotations
from typing import Any, Dict, List

WORDS_PER_PAGE = 275

TEMPLATES: Dict[str, Dict[str, Any]] = {
    # IMRaD scientific paper
    "paper": {
        "citation_style": "ieee",
        "sections": [
            {"key": "abstract", "title": "Abstract", "kind": "front",
             "objective": "150-250 word summary: problem, method, key findings, implication."},
            {"key": "introduction", "title": "1. Introduction", "kind": "body",
             "objective": "Background, problem statement, research questions, objectives, contribution."},
            {"key": "related_work", "title": "2. Related Work", "kind": "body",
             "objective": "Survey prior work from sources; position this study; cite [n]."},
            {"key": "methodology", "title": "3. Methodology", "kind": "body",
             "objective": "Research design, data/source strategy, inclusion criteria, analysis method."},
            {"key": "results", "title": "4. Results", "kind": "body",
             "objective": "Present findings grounded in graded sources with citations and (if any) figures/tables."},
            {"key": "discussion", "title": "5. Discussion", "kind": "body",
             "objective": "Interpret findings, implications, compare to related work, address gaps."},
            {"key": "limitations", "title": "6. Limitations", "kind": "body",
             "objective": "State limitations from the research manifest honestly."},
            {"key": "conclusion", "title": "7. Conclusion", "kind": "synthesis",
             "objective": "Summarize contributions and future work."},
            {"key": "references", "title": "References", "kind": "refs", "objective": ""},
        ],
    },
    "thesis": {"citation_style": "apa", "alias_of": "paper"},
    "report": {
        "citation_style": "apa",
        "sections": [
            {"key": "executive_summary", "title": "Executive Summary", "kind": "front",
             "objective": "Concise summary of purpose, findings, recommendations."},
            {"key": "introduction", "title": "1. Introduction", "kind": "body",
             "objective": "Context, scope, objectives."},
            {"key": "findings", "title": "2. Findings", "kind": "body",
             "objective": "Evidence-based findings with citations [n]."},
            {"key": "analysis", "title": "3. Analysis", "kind": "body",
             "objective": "Interpretation and implications."},
            {"key": "recommendations", "title": "4. Recommendations", "kind": "synthesis",
             "objective": "Actionable, evidence-backed recommendations."},
            {"key": "references", "title": "References", "kind": "refs", "objective": ""},
        ],
    },
    # Blog: hook + sourced sections
    "blog": {
        "citation_style": "links",
        "sections": [
            {"key": "hook", "title": "", "kind": "front",
             "objective": "Compelling hook + what the reader will learn. Engaging, clear."},
            {"key": "context", "title": "Background", "kind": "body",
             "objective": "Set context with sourced facts (link inline)."},
            {"key": "main_1", "title": "Key Insight 1", "kind": "body",
             "objective": "First main point backed by sources."},
            {"key": "main_2", "title": "Key Insight 2", "kind": "body",
             "objective": "Second main point backed by sources."},
            {"key": "main_3", "title": "Key Insight 3", "kind": "body",
             "objective": "Third main point backed by sources."},
            {"key": "takeaways", "title": "Key Takeaways", "kind": "synthesis",
             "objective": "Actionable summary + call to action."},
            {"key": "references", "title": "Sources & Further Reading", "kind": "refs", "objective": ""},
        ],
    },
    "article": {"citation_style": "apa", "alias_of": "blog"},
    # Non-fiction book: chaptered, research-backed
    "book": {
        "citation_style": "chicago",
        "chaptered": True,  # body chapters generated dynamically
        "sections": [
            {"key": "preface", "title": "Preface", "kind": "front",
             "objective": "Purpose of the book, audience, how it is organized."},
            {"key": "introduction", "title": "Introduction", "kind": "front",
             "objective": "Set the stage; thesis of the book."},
            # body chapters injected at runtime
            {"key": "conclusion", "title": "Conclusion", "kind": "synthesis",
             "objective": "Synthesize the book's argument; final reflections."},
            {"key": "references", "title": "References", "kind": "refs", "objective": ""},
        ],
    },
    # Novel: research-informed worldbuilding bible -> chapters
    "novel": {
        "citation_style": "links",
        "chaptered": True,
        "creative": True,
        "sections": [
            {"key": "worldbuilding", "title": "", "kind": "bible",
             "objective": "Internal research bible: setting facts, realism anchors (not printed in final prose)."},
            # chapters injected at runtime
        ],
    },
    "documentation": {
        "citation_style": "links",
        "sections": [
            {"key": "overview", "title": "Overview", "kind": "front", "objective": "What this documents and why."},
            {"key": "concepts", "title": "Concepts", "kind": "body", "objective": "Core concepts with sourced detail."},
            {"key": "howto", "title": "How-To", "kind": "body", "objective": "Step-by-step guidance."},
            {"key": "reference", "title": "Reference", "kind": "body", "objective": "Detailed reference material."},
            {"key": "references", "title": "Sources", "kind": "refs", "objective": ""},
        ],
    },
}




# ══════════════════════════════════════════════════════════════════════════════
# STYLE PROFILES — the WRITING DNA of each category (voice/tone/technique/rigor)
# Injected into drafting prompts so each doc_type is written with its real craft.
# ══════════════════════════════════════════════════════════════════════════════
STYLE_PROFILES: Dict[str, Dict[str, Any]] = {
    "paper": {
        "label": "Scientific / Academic Paper",
        "voice": "third-person, impersonal, objective (avoid 'I/we' except standard 'we propose')",
        "tone": "formal, precise, measured, hedged",
        "register": "academic; discipline-appropriate terminology defined on first use",
        "techniques": [
            "State claims with appropriate hedging (may, suggests, indicates) unless strongly evidenced",
            "Every empirical claim carries a citation [n]; no unsupported assertions",
            "Topic sentence -> evidence -> interpretation per paragraph",
            "Use precise quantities; define metrics; report methodology transparently",
            "Compare findings against prior work; acknowledge counter-evidence",
        ],
        "avoid": ["hype", "marketing language", "rhetorical questions", "first-person anecdote",
                  "fabricated statistics or fake citations", "emotive adjectives"],
        "paragraph_len": "4-7 sentences, dense and logical",
        "citation": "numbered [n], formal reference list",
        "rigor": "HIGH — methodology, reproducibility, limitations explicit",
    },
    "thesis": {"alias_of": "paper", "label": "Thesis / Dissertation",
               "rigor": "HIGH — exhaustive literature grounding, explicit research questions"},
    "report": {
        "label": "Professional / Technical Report",
        "voice": "third-person or measured first-person-plural; professional",
        "tone": "clear, neutral, decision-oriented",
        "register": "business/technical; plain but precise",
        "techniques": ["Lead with the bottom line (BLUF)", "Evidence-backed findings -> analysis -> actionable recommendations",
                       "Use structured lists/tables for scannability", "Quantify impact where possible"],
        "avoid": ["academic verbosity", "vague recommendations", "unsupported claims"],
        "paragraph_len": "3-5 sentences, scannable",
        "citation": "[n] inline + references",
        "rigor": "MEDIUM-HIGH — evidence + actionability",
    },
    "blog": {
        "label": "Blog Post",
        "voice": "second-person, conversational, warm, direct ('you')",
        "tone": "engaging, friendly, confident, lightly persuasive",
        "register": "accessible; explain jargon simply; short punchy sentences mixed with longer ones",
        "techniques": [
            "Open with a strong hook (question, surprising fact, relatable scenario)",
            "Subheadings that promise value; short scannable paragraphs",
            "Concrete examples, analogies, and takeaways",
            "Inline source links for credibility; end with a clear CTA",
            "SEO-aware: natural keyword use, descriptive headings",
        ],
        "avoid": ["dry academic tone", "walls of text", "jargon without explanation", "fake stats"],
        "paragraph_len": "2-4 sentences, airy",
        "citation": "inline links, casual",
        "rigor": "MEDIUM — credible + sourced but reader-first",
    },
    "article": {"alias_of": "blog", "label": "Feature Article",
                "tone": "polished, journalistic, balanced", "rigor": "MEDIUM-HIGH"},
    "book": {
        "label": "Non-fiction Book",
        "voice": "authoritative yet accessible narrator; consistent across chapters",
        "tone": "engaging, explanatory, story-driven where useful",
        "register": "rich but readable; builds concepts progressively",
        "techniques": [
            "Each chapter: clear thesis -> development -> bridge to next chapter",
            "Blend narrative, examples, and evidence; recurring motifs for cohesion",
            "Define terms; assume intelligent non-expert reader",
            "Maintain a consistent authorial voice and through-line across chapters",
        ],
        "avoid": ["disconnected chapters", "repetition without purpose", "unsupported sweeping claims"],
        "paragraph_len": "4-8 sentences, flowing",
        "citation": "chicago notes/references",
        "rigor": "MEDIUM-HIGH — researched, coherent argument",
    },
    "novel": {
        "label": "Novel / Fiction",
        "voice": "narrative POV consistent (1st/3rd limited); distinct character voices",
        "tone": "immersive, emotionally resonant, scene-driven",
        "register": "literary prose; vary sentence rhythm; vivid but purposeful",
        "techniques": [
            "SHOW don't tell: sensory detail, action, subtext over exposition",
            "Scene structure: goal -> conflict -> turn; end chapters on tension/hook",
            "Natural dialogue that reveals character; distinct voices; minimal tags",
            "Maintain continuity (characters, timeline, world) via the research bible",
            "Vary pacing; interiority + external action; avoid info-dumps",
        ],
        "avoid": ["citations or [n] markers in prose", "telling emotions flatly", "purple prose",
                  "head-hopping POV", "exposition dumps", "refusing to write"],
        "paragraph_len": "varied for rhythm; dialogue-heavy where apt",
        "citation": "NONE in prose (facts live in the research bible)",
        "rigor": "realism anchored by research bible; creativity primary",
    },
    "documentation": {
        "label": "Technical Documentation",
        "voice": "second-person imperative ('Run...', 'Configure...'); neutral",
        "tone": "clear, precise, instructional",
        "register": "technical; consistent terminology; no fluff",
        "techniques": ["Task-oriented: prerequisites -> steps -> verification",
                       "Use code blocks, numbered steps, and notes/warnings",
                       "Be explicit and unambiguous; define every term once",
                       "Cover concepts, how-to, and reference distinctly"],
        "avoid": ["narrative tangents", "ambiguity", "marketing tone"],
        "paragraph_len": "short; favor lists and steps",
        "citation": "inline links to sources/specs",
        "rigor": "HIGH on accuracy and completeness",
    },
}


def get_style_profile(doc_type: str) -> Dict[str, Any]:
    sp = STYLE_PROFILES.get(doc_type, STYLE_PROFILES["report"])
    if "alias_of" in sp:
        base = dict(STYLE_PROFILES[sp["alias_of"]])
        base.update({k: v for k, v in sp.items() if k != "alias_of"})
        return base
    return sp


def style_directive(doc_type: str, language_name: str = "the target language") -> str:
    """Render a compact style directive block for prompt injection."""
    sp = get_style_profile(doc_type)
    techniques = "\n".join(f"  - {t}" for t in sp.get("techniques", []))
    avoid = ", ".join(sp.get("avoid", []))
    return (
        f"WRITING STYLE — {sp.get('label', doc_type)} (write in {language_name}):\n"
        f"  Voice: {sp.get('voice','')}\n"
        f"  Tone: {sp.get('tone','')}\n"
        f"  Register: {sp.get('register','')}\n"
        f"  Paragraph: {sp.get('paragraph_len','')}\n"
        f"  Rigor: {sp.get('rigor','')}\n"
        f"  Techniques:\n{techniques}\n"
        f"  Avoid: {avoid}\n"
        f"  Citations: {sp.get('citation','')}\n"
        f"  LANGUAGE: Write ENTIRELY and consistently in {language_name}. Do NOT mix "
        f"languages mid-sentence. Use correct {language_name} spelling, diacritics, and "
        f"punctuation. Keep established proper nouns/technical terms but explain them in "
        f"{language_name}. Use standard, readable Unicode characters only.\n"
    )




# ══════════════════════════════════════════════════════════════════════════════
# FORMAT PROFILES — publication-grade typography & layout per category.
# Consumed by ilma_doc_exporter to make output READY-TO-USE (justify/indent/etc).
# Units: indent in points (1 inch = 72pt; 1.25cm ~= 35.4pt), spacing = line multiple.
# ══════════════════════════════════════════════════════════════════════════════
FORMAT_PROFILES: Dict[str, Dict[str, Any]] = {
    "paper": {  # IEEE
        "align": "justify", "first_line_indent": 0, "para_space_after": 6,
        "line_spacing": 1.15, "body_font": "serif", "body_size": 10.5,
        "page_size": "A4", "margin_in": 1.0, "heading_numbered": True,
        "block_paragraphs": True,
    },
    "thesis": {  # APA-7
        "align": "justify", "first_line_indent": 36, "para_space_after": 0,
        "line_spacing": 2.0, "body_font": "serif", "body_size": 12,
        "page_size": "A4", "margin_in": 1.0, "heading_numbered": True,
        "block_paragraphs": False,
    },
    "makalah": {  # Indonesian campus standard
        "align": "justify", "first_line_indent": 35, "para_space_after": 0,
        "line_spacing": 1.5, "body_font": "serif", "body_size": 12,
        "page_size": "A4", "margin_top_in": 1.57, "margin_left_in": 1.57,
        "margin_right_in": 1.18, "margin_bottom_in": 1.18,
        "margin_in": 1.18, "heading_numbered": True, "block_paragraphs": False,
    },
    "report": {
        "align": "justify", "first_line_indent": 0, "para_space_after": 8,
        "line_spacing": 1.15, "body_font": "sans", "body_size": 11,
        "page_size": "A4", "margin_in": 1.0, "heading_numbered": True,
        "block_paragraphs": True,
    },
    "blog": {
        "align": "left", "first_line_indent": 0, "para_space_after": 10,
        "line_spacing": 1.5, "body_font": "sans", "body_size": 12,
        "page_size": "A4", "margin_in": 0.9, "heading_numbered": False,
        "block_paragraphs": True,
    },
    "article": {"alias_of": "blog"},
    "book": {
        "align": "justify", "first_line_indent": 22, "para_space_after": 0,
        "line_spacing": 1.3, "body_font": "serif", "body_size": 11.5,
        "page_size": "A4", "margin_in": 1.0, "heading_numbered": False,
        "block_paragraphs": False,
    },
    "novel": {
        "align": "justify", "first_line_indent": 28, "para_space_after": 0,
        "line_spacing": 1.5, "body_font": "serif", "body_size": 12,
        "page_size": "A4", "margin_in": 1.0, "heading_numbered": False,
        "block_paragraphs": False, "chapter_centered": True,
    },
    "documentation": {
        "align": "left", "first_line_indent": 0, "para_space_after": 8,
        "line_spacing": 1.15, "body_font": "sans", "body_size": 10.5,
        "page_size": "A4", "margin_in": 0.8, "heading_numbered": False,
        "block_paragraphs": True,
    },
}


def get_format_profile(doc_type: str) -> Dict[str, Any]:
    fp = FORMAT_PROFILES.get(doc_type, FORMAT_PROFILES["report"])
    if "alias_of" in fp:
        base = dict(FORMAT_PROFILES[fp["alias_of"]])
        base.update({k: v for k, v in fp.items() if k != "alias_of"})
        return base
    return dict(fp)


# ══════════════════════════════════════════════════════════════════════════════
# VISUAL POLICY — when/which tables, charts, images per category.
# ══════════════════════════════════════════════════════════════════════════════
VISUAL_POLICY: Dict[str, Dict[str, Any]] = {
    "paper":         {"tables": True,  "charts": True,  "illustrations": False, "max_charts": 3, "caption_prefix": ("Tabel", "Gambar")},
    "thesis":        {"tables": True,  "charts": True,  "illustrations": False, "max_charts": 4, "caption_prefix": ("Tabel", "Gambar")},
    "makalah":       {"tables": True,  "charts": True,  "illustrations": False, "max_charts": 2, "caption_prefix": ("Tabel", "Gambar")},
    "report":        {"tables": True,  "charts": True,  "illustrations": False, "max_charts": 3, "caption_prefix": ("Tabel", "Gambar")},
    "blog":          {"tables": True,  "charts": True,  "illustrations": True,  "max_charts": 1, "caption_prefix": ("Tabel", "Gambar")},
    "article":       {"tables": True,  "charts": True,  "illustrations": True,  "max_charts": 1, "caption_prefix": ("Tabel", "Gambar")},
    "book":          {"tables": True,  "charts": True,  "illustrations": True,  "max_charts": 2, "caption_prefix": ("Tabel", "Gambar")},
    "novel":         {"tables": False, "charts": False, "illustrations": True,  "max_charts": 0, "caption_prefix": ("", "Ilustrasi")},
    "documentation": {"tables": True,  "charts": False, "illustrations": False, "max_charts": 0, "caption_prefix": ("Tabel", "Gambar")},
}


def get_visual_policy(doc_type: str) -> Dict[str, Any]:
    return dict(VISUAL_POLICY.get(doc_type, VISUAL_POLICY["report"]))


def get_template(doc_type: str) -> Dict[str, Any]:
    t = TEMPLATES.get(doc_type, TEMPLATES["report"])
    if "alias_of" in t:
        base = dict(TEMPLATES[t["alias_of"]])
        base["citation_style"] = t.get("citation_style", base.get("citation_style"))
        return base
    return t


if __name__ == "__main__":
    import sys, json
    print(json.dumps(get_template(sys.argv[1] if len(sys.argv) > 1 else "paper"), indent=2))
