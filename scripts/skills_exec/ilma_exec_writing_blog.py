#!/usr/bin/env python3
"""
ILMA Writing Blog Execution Script
证据ID: P2E-WRITING-001
"""
import argparse, json, sys, datetime, re

EVIDENCE_ID = "P2E-WRITING-001"
VERSION = "1.0.0"

BLOG_TEMPLATES = {
    "how-to": {
        "structure": ["Pengantar", "Apa itu X", "Langkah 1", "Langkah 2", "Kesimpulan"],
        "tone": "edukatif, langkah-demi-langkah"
    },
    "listicle": {
        "structure": ["Pengantar", "Daftar X items", "Kesimpulan"],
        "tone": "ringkas, engaging"
    },
    "opinion": {
        "structure": ["Pengantar + thesis", "Argumen 1", "Argumen 2", "Kesimpulan"],
        "tone": "personal, reflektif"
    }
}

def generate_outline(topic, style="how-to"):
    template = BLOG_TEMPLATES.get(style, BLOG_TEMPLATES["how-to"])
    outline = []
    for i, section in enumerate(template["structure"]):
        if section == "Apa itu X":
            outline.append({"section": f"Apa itu {topic}?", "purpose": "definisi"})
        elif section.startswith("Langkah"):
            outline.append({"section": f"{section}: Persiapan", "purpose": "langkah persiapan"})
        elif section == "Daftar X items":
            outline.append({"section": f"5 Poin Penting tentang {topic}", "purpose": "informasi"})
        elif section == "Argumen 1":
            outline.append({"section": "Alasan Pertama", "purpose": "argumen pro"})
        elif section == "Argumen 2":
            outline.append({"section": "Alasan Kedua", "purpose": "argumen pro/lawan"})
        else:
            outline.append({"section": section, "purpose": "transisi"})
    return outline, template["tone"]

def generate_draft(topic, outline, audience="IT professional"):
    sections = []
    for item in outline:
        sections.append(f"## {item['section']}\n\nLorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. {item['purpose'].title()} untuk {topic}.\n")
    return f"# {topic}\n\n" + "\n".join(sections)

def main():
    p = argparse.ArgumentParser(description="ILMA Writing Blog Execution Script")
    p.add_argument("--topic", "-t", required=True)
    p.add_argument("--audience", default="IT professional")
    p.add_argument("--style", choices=["how-to", "listicle", "opinion"], default="how-to")
    p.add_argument("--draft", action="store_true", help="Generate draft")
    p.add_argument("--json", action="store_true")
    p.add_argument("--word-count", type=int, default=800)
    p.add_argument("--evidence-id", default=EVIDENCE_ID)
    args = p.parse_args()

    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    outline, tone = generate_outline(args.topic, args.style)
    draft = generate_draft(args.topic, outline, args.audience) if args.draft else ""
    word_count = len(draft.split())

    result = {
        "evidence_id": args.evidence_id,
        "version": VERSION,
        "timestamp": timestamp,
        "topic": args.topic,
        "audience": args.audience,
        "style": args.style,
        "outline": outline,
        "tone": tone,
        "draft": draft,
        "word_count": word_count,
        "target_word_count": args.word_count,
        "meta_title": f"{args.topic}: Panduan Lengkap untuk {args.audience}",
        "meta_description": f"Pelajari cara {args.topic.lower()} dengan panduan lengkap ini. Solusi praktis untuk {args.audience.lower()}.",
        "cta": "Hubungi kami untuk konsultasi gratis",
        "status": "EXECUTED"
    }

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"=== ILMA Writing Blog ===")
        print(f"Topic: {args.topic}")
        print(f"Audience: {args.audience}")
        print(f"Style: {args.style}")
        print(f"Tone: {tone}")
        print(f"Outline sections: {len(outline)}")
        if draft:
            print(f"Word count: {word_count}")
            print(f"\nMeta: {result['meta_title']}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
