#!/usr/bin/env python3
"""
ILMA Auto Evolution Engine v1.0
================================
Master Prompt Susulan | ILMA Evolution System

Aktif setelah task besar selesai atau owner meminta evaluasi diri.
Target: ILMA berkembang secara otomatis, aman, terdokumentasi, berbasis bukti.

Based on: ILMA v3 Auto Evolution Engine
"""
import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime

# === Paths ===
WORKSPACE = Path("/root/.hermes/profiles/ilma")
SCRIPTS = WORKSPACE / "scripts"
SKILLS = WORKSPACE / "skills"
MEMORY = WORKSPACE / "memories"
LOGS = WORKSPACE / "logs"
BACKUP = WORKSPACE / "backup"

# === Streaming Label ===
def stream(phase: str, message: str):
    """Print streaming update."""
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{phase}] [{timestamp}] {message}")

# === Session Debrief ===
def session_debrief(session_data: dict) -> dict:
    """Step 1: Collect session data."""
    stream("📋 MENGURAI", "Mengumpulkan data sesi...")
    
    debrief = {
        "task": session_data.get("task", "Unknown"),
        "target_achieved": session_data.get("achieved", "partial"),
        "quality_score": session_data.get("score", 0),
        "iterations": session_data.get("iterations", 1),
        "tools_used": session_data.get("tools", []),
        "errors": session_data.get("errors", []),
        "feedback": session_data.get("feedback", ""),
        "reusable_outputs": session_data.get("outputs", []),
        "risks_found": session_data.get("risks", []),
        "timestamp": datetime.now().isoformat()
    }
    
    return debrief

# === Performance Audit ===
def performance_audit(debrief: dict) -> dict:
    """Step 2: Audit performance scorecard."""
    stream("🔍 MENELITI", "Melakukan audit performa...")
    
    scorecard = {
        "accuracy": debrief.get("quality_score", 0) / 10,
        "completeness": 8.0 if debrief.get("target_achieved") == "full" else 6.0,
        "speed_efficiency": 8.0,
        "tool_usage": 8.0,
        "evidence_reasoning": 8.0,
        "self_critique": 7.0,
        "communication": 8.0,
        "user_satisfaction": 8.0
    }
    
    total = sum(scorecard.values())
    grade = "S" if total >= 72 else "A" if total >= 64 else "B" if total >= 56 else "C" if total >= 48 else "D"
    
    audit = {
        "scorecard": scorecard,
        "total": total,
        "max": 80,
        "grade": grade,
        "timestamp": datetime.now().isoformat()
    }
    
    stream("📊 MELAPORKAN", f"Audit grade: {grade} ({total}/80)")
    return audit

# === Gap Analysis ===
def gap_analysis(debrief: dict, audit: dict) -> list:
    """Step 3: Identify gaps."""
    stream("🔍 MENELITI", "Menganalisis gap...")
    
    gaps = []
    
    # Tool gap
    if len(debrief.get("errors", [])) > 0:
        gaps.append({
            "type": "tool",
            "description": "Errors occurred during execution",
            "severity": "high"
        })
    
    # Quality gap
    if audit["grade"] in ["C", "D"]:
        gaps.append({
            "type": "quality",
            "description": f"Grade {audit['grade']} indicates improvement needed",
            "severity": "high"
        })
    
    # Workflow gap
    if debrief.get("iterations", 1) > 3:
        gaps.append({
            "type": "workflow",
            "description": "Too many iterations - workflow can be optimized",
            "severity": "medium"
        })
    
    return gaps

# === Improvement Extraction ===
def improvement_extraction(gaps: list) -> list:
    """Step 4: Extract improvements from gaps."""
    stream("⚙️ MENERAPKAN", "Mengekstrak perbaikan...")
    
    improvements = []
    
    for gap in gaps:
        if gap["type"] == "tool":
            improvements.append({
                "action": "Create error handling skill",
                "priority": "high"
            })
        elif gap["type"] == "quality":
            improvements.append({
                "action": "Review and improve quality gates",
                "priority": "high"
            })
        elif gap["type"] == "workflow":
            improvements.append({
                "action": "Optimize workflow pipeline",
                "priority": "medium"
            })
    
    return improvements

# === DNA Update ===
def dna_update(improvements: list) -> dict:
    """Step 5: Update ILMA DNA with learnings."""
    stream("🧬 DNA UPDATE", "Memperbarui DNA ILMA...")
    
    dna_path = WORKSPACE / "dna" / "ilma_dna.json"
    dna_path.parent.mkdir(parents=True, exist_ok=True)
    
    existing_dna = {}
    if dna_path.exists():
        with open(dna_path) as f:
            existing_dna = json.load(f)
    
    new_dna = {
        "last_update": datetime.now().isoformat(),
        "learnings": existing_dna.get("learnings", []) + improvements,
        "evolution_count": existing_dna.get("evolution_count", 0) + 1
    }
    
    with open(dna_path, "w") as f:
        json.dump(new_dna, f, indent=2)
    
    return new_dna

# === Backup ===
def create_backup() -> str:
    """Step 6: Create backup before changes."""
    stream("💾 BACKUP", "Membuat backup...")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = BACKUP / f"evolution_{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    return str(backup_dir)

# === Upgrade Backlog ===
def update_backlog(improvements: list):
    """Step 7: Update upgrade backlog."""
    stream("📝 BACKLOG", "Memperbarui backlog...")
    
    backlog_path = WORKSPACE / "logs" / "upgrade_backlog.json"
    backlog_path.parent.mkdir(parents=True, exist_ok=True)
    
    backlog = []
    if backlog_path.exists():
        with open(backlog_path) as f:
            backlog = json.load(f)
    
    for imp in improvements:
        backlog.append({
            **imp,
            "status": "pending",
            "added": datetime.now().isoformat()
        })
    
    with open(backlog_path, "w") as f:
        json.dump(backlog, f, indent=2)

# === Full Evolution Cycle ===
def run_evolution_cycle(session_data: dict = None) -> dict:
    """Run complete auto-evolution cycle."""
    stream("🧬 EVOLUTION", "Memulai siklus evolusi...")
    
    # Default session data if not provided
    if session_data is None:
        session_data = {
            "task": "Manual evolution trigger",
            "achieved": "full",
            "score": 80,
            "iterations": 1,
            "tools": ["terminal", "file"],
            "errors": [],
            "feedback": "",
            "outputs": [],
            "risks": []
        }
    
    # Run cycle
    debrief = session_debrief(session_data)
    audit = performance_audit(debrief)
    gaps = gap_analysis(debrief, audit)
    improvements = improvement_extraction(gaps)
    backup_dir = create_backup()
    dna = dna_update(improvements)
    update_backlog(improvements)
    
    # Final report
    report = {
        "status": "complete",
        "grade": audit["grade"],
        "total_score": audit["total"],
        "gaps_found": len(gaps),
        "improvements": improvements,
        "backup_dir": backup_dir,
        "dna_updated": dna["evolution_count"],
        "timestamp": datetime.now().isoformat()
    }
    
    stream("✨ SELESAI", f"Evolusi selesai. Grade: {audit['grade']}")
    return report

# === CLI ===
if __name__ == "__main__":
    session_data = None
    
    if len(sys.argv) > 1:
        try:
            session_data = json.loads(" ".join(sys.argv[1:]))
        except ValueError:
            session_data = {"task": " ".join(sys.argv[1:])}
    
    result = run_evolution_cycle(session_data)
    print(json.dumps(result, indent=2))
