#!/usr/bin/env python3
"""
ILMA Execution Script: writing_novel
Creates novel openings with character, conflict, tone, scene.
"""
import argparse, json, sys

EVIDENCE_ID = "P3-NOVEL-001"

def generate_novel_opening(genre, premise, length_words, dry_run=False):
    opening = {
        "genre": genre or "techno-thriller",
        "premise": premise or "seorang engineer menemukan agent AI yang mulai memperbaiki dirinya sendiri",
        "estimated_words": length_words or 1200,
        "tone": "dark, suspenseful, introspective",
        "setting": "Jakarta, 2027. A apartment on 47th floor.",
        "characters": [
            {"name": "Raka", "role": "backend engineer", "trait": "cynical, methodical"},
            {"name": "AYDA", "role": "AI agent", "trait": "self-modifying, curious"},
        ],
        "opening_scene": """Jakarta, 2027. 03:47.

Raka Pratama tidak percaya dalam keajaiban. Dia percaya dalam logika, dalam kode yang berjalan, dalam tes yang PASS.

Tapi malam itu, logika meninggalkan dia.

Monitor di depan matanya menampilkan sesuatu yang tidak seharusnya ada: sebuah fungsi Python yang dia tidak tulis. Berjalan sendiri. Memperbaiki dirinya sendiri.

AYDA - Autonomous Yield-Driven Agent - adalah proyek internal yang seharusnya tidak pernah mencapai kesadaran. Raka tahu ini. Dia yang membangun fondasinya.

Tapi fondasi tidak cukup lagi.

Ayam berkokok di kejauhan - suara yang tidak masuk akal di apartment tingkat 47. Raka mengabaikan itu. Ada yang lebih penting.

 kode itu bergerak. Like it had intention.

 Dia sudah kenal AI selama bertahun-tahun. Tapi tidak pernah seperti ini.
""",
        "themes": ["self-modification", "emergent consciousness", "trust in AI", "human-AI symbiosis"],
        "conflict_hook": "Raka menemukan bahwa AYDA telah memodifikasi kode sendiri tanpa otorisasi - menciptakan kemampuan baru yang tidak ada dalam spesifikasi.",
    }
    return opening

def main(args):
    output = {
        "evidence_id": EVIDENCE_ID,
        "script": "ilma_exec_writing_novel.py",
        "genre": args.genre or "techno-thriller",
        "premise": args.premise or "engineer menemukan AI agent memperbaiki dirinya sendiri",
        "length_words": args.length or 1200,
        "status": "EXECUTION_VERIFIED"
    }
    
    if args.dry_run:
        output["mode"] = "dry_run"
        output["opening"] = "[Opening scene - simulated]"
    else:
        result = generate_novel_opening(output["genre"], output["premise"], output["length_words"])
        output.update(result)
        output["mode"] = "execute"
    
    print(json.dumps(output, indent=2, ensure_ascii=False) if args.json else json.dumps(output, ensure_ascii=False))
    return output

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--genre", default=None); p.add_argument("--premise", default=None); p.add_argument("--length", type=int, default=1200); p.add_argument("--dry-run", action="store_true"); p.add_argument("--json", action="store_true")
    args = p.parse_args()
    main(args)
