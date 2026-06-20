#!/usr/bin/env python3
"""
ILMA Indonesian NLP Execution Script
证据ID: P2E-NLP-001
Connects to ilma_indonesian_nlp.py engine
"""
import argparse, json, sys, os, datetime

EVIDENCE_ID = "P2E-NLP-001"
VERSION = "1.0.0"

def load_nlp_engine():
    """Try to load ILMA Indonesian NLP engine."""
    try:
        sys.path.insert(0, "/root/.hermes/profiles/ilma/scripts")
        from ilma_indonesian_nlp import analyze_text
        return analyze_text, None
    except ImportError as e:
        return None, str(e)

def simple_tokenize(text):
    """Simple tokenizer for Indonesian."""
    import re
    words = re.findall(r'\b\w+\b', text.lower())
    stopwords = {'yang', 'dan', 'di', 'ke', 'dari', 'ini', 'itu', 'dengan', 'untuk', 'pada', 'adalah', 'akan', 'tidak', 'ada', 'atau', 'bisa', 'juga', 'sudah', 'saya', 'kita', 'kami'}
    keywords = [w for w in words if len(w) > 3 and w not in stopwords]
    return list(set(keywords))

def extract_keyphrases(text):
    """Extract simple bigrams as keyphrases."""
    words = text.split()
    bigrams = [f"{words[i]} {words[i+1]}" for i in range(len(words)-1) if len(words[i]) > 2 and len(words[i+1]) > 2]
    return list(dict.fromkeys(bigrams))[:5]

def analyze_seo(text):
    """Basic SEO analysis."""
    words = text.lower().split()
    word_count = len(words)
    char_count = len(text)
    h1_match = text.count('#')
    bold_match = text.count('**')
    links = text.count('http')
    density = {}
    for w in set(words):
        if len(w) > 3:
            density[w] = text.lower().count(w) / word_count * 100
    top_words = sorted(density.items(), key=lambda x: x[1], reverse=True)[:5]
    return {
        "word_count": word_count,
        "char_count": char_count,
        "heading_markers": h1_match,
        "bold_markers": bold_match,
        "external_links": links,
        "top_keyword_density": [{"word": w, "density_pct": round(d, 2)} for w, d in top_words]
    }

def main():
    p = argparse.ArgumentParser(description="ILMA Indonesian NLP Execution Script")
    p.add_argument("--text", required=True)
    p.add_argument("--json", action="store_true")
    p.add_argument("--seo", action="store_true", help="Include SEO analysis")
    p.add_argument("--evidence-id", default=EVIDENCE_ID)
    args = p.parse_args()

    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Try ILMA engine first
    engine_fn, engine_error = load_nlp_engine()
    if engine_fn:
        nlp_result = engine_fn(args.text)
        mode = "ilma_engine"
    else:
        keywords = simple_tokenize(args.text)
        keyphrases = extract_keyphrases(args.text)
        nlp_result = {
            "error": engine_error,
            "fallback": "simple_tokenizer",
            "keywords": keywords,
            "keyphrases": keyphrases
        }
        mode = "fallback"

    result = {
        "evidence_id": args.evidence_id,
        "version": VERSION,
        "timestamp": timestamp,
        "input": args.text,
        "mode": mode,
        "nlp_analysis": nlp_result,
        "intent": "informative" if any(w in args.text.lower() for w in ["apa","bagaimana","mengapa"]) else "transactional",
        "tone": "formal" if args.text.isupper() else "semi-formal",
        "seo": analyze_seo(args.text) if args.seo else None,
        "status": "EXECUTED"
    }

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"=== ILMA Indonesian NLP ===")
        print(f"Mode: {mode}")
        print(f"Intent: {result['intent']}")
        print(f"Tone: {result['tone']}")
        if isinstance(nlp_result, dict):
            for k, v in nlp_result.items():
                if k != "error":
                    print(f"{k}: {v if isinstance(v, str) else v[:3] if isinstance(v, list) else v}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
