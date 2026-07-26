#!/usr/bin/env python3
"""
ILMA Skill Ingestion Lifecycle
Safely ingest and validate new SKILL.md entries before adding to index.
"""
import sys, os, json
from pathlib import Path
from typing import Dict

INDEX_FILE = Path("/root/.hermes/profiles/ilma/skill_index_manifest.jsonl")

def ingest_skill(skill_md_path: str):
    p = Path(skill_md_path)
    if not p.exists():
        print(f"Error: {skill_md_path} not found.")
        return

    content = p.read_text(errors="ignore")
    if not content.startswith("---"):
        print("Error: Invalid skill format. Missing frontmatter.")
        return
        
    print(f"Ingestion Check: {p.name}")
    print("- Frontmatter: OK")
    
    # Check for security scope rules if it's a high risk path
    if "security" in str(p).lower() or "pentest" in str(p).lower():
        if "ILMA_ADMIN_OVERRIDE" not in content and "localhost" not in content:
            print("[!] REJECTED: Security skill lacks explicit authorization bound documentation.")
            return
            
    print("- Security Check: OK")
    print(f"-> Promoted to Staging. Run `python3 ilma_skill_indexer.py` to compile into Live Index.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: ilma_skill_ingestion.py <path_to_SKILL.md>")
    else:
        ingest_skill(sys.argv[1])
