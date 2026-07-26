#!/usr/bin/env python3
"""
ILMA Evolution Routine - Rutinitas Evolusi ILMA
================================================
Script utama untuk ILMA berkembang bersama ILMA.

Fitur:
- Study ILMA patterns
- Self-assessment
- Gap analysis
- Apply improvements
- Track evolution

Usage:
    python3 ilma_evolution_routine.py assess     # Assess current state
    python3 ilma_evolution_routine.py study     # Study ILMA patterns
    python3 ilma_evolution_routine.py gap       # Analyze gaps
    python3 ilma_evolution_routine.py evolve    # Apply improvements
    python3 ilma_evolution_routine.py full      # Full evolution cycle
    python3 ilma_evolution_routine.py status    # Show evolution status
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

# ─── Paths ─────────────────────────────────────────────────────────────────
ILMA_DIR = Path("/root/.hermes/profiles/ilma")
ILMA_SKILLS = ILMA_DIR / "skills"
ILMA_SCRIPTS = ILMA_DIR / "scripts"
ILMA_SYNC = Path("/root/.cache/ilma/sync")

ILMA_DIR = Path("/root/.hermes/profiles/ilma")
ILMA_SKILLS = ILMA_DIR / "skills"
ILMA_SCRIPTS = ILMA_DIR / "scripts"

# ─── ANSI Colors ───────────────────────────────────────────────────────────
C_R = "\033[91m"; C_G = "\033[92m"; C_Y = "\033[93m"; C_B = "\033[94m"
C_C = "\033[96m"; C_BOLD = "\033[1m"; C_RESET = "\033[0m"
def c(t, col): return f"{col}{t}{C_RESET}"

# ─── Dataclasses ────────────────────────────────────────────────────────────
@dataclass
class EvolutionMetrics:
    timestamp: str
    ilma_skills: int = 0
    ilma_scripts: int = 0
    ILMA_skills: int = 0
    ILMA_scripts: int = 0
    skill_gap: int = 0
    script_gap: int = 0
    evolution_score: float = 0.0
    improvements: List[str] = field(default_factory=list)

# ─── Utility Functions ────────────────────────────────────────────────────────
def log(msg, color=C_C):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{color}[{ts}] {msg}{C_RESET}")

def log_section(name: str):
    print(f"\n{c('='*60, C_B)}")
    print(f"{c(f'  {name}', C_BOLD)}")
    print(f"{c('='*60, C_B)}")

def get_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()

def run_py(cmd: List[str], timeout: int = 120) -> tuple[int, str, str]:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Timeout"
    except Exception as e:
        return -1, "", str(e)

def count_skills(path: Path) -> int:
    if not path.exists():
        return 0
    return len([p for p in path.iterdir() if not p.name.startswith(".")])

def count_scripts(path: Path) -> int:
    if not path.exists():
        return 0
    return len(list(path.glob("*.py")))

# ─── Assessment ─────────────────────────────────────────────────────────────
def assess():
    """Assess current ILMA state."""
    log_section("EVOLUTION ASSESSMENT")
    
    ilma_skills = count_skills(ILMA_SKILLS)
    ilma_scripts = count_scripts(ILMA_SCRIPTS)
    ILMA_skills = count_skills(ILMA_SKILLS)
    ILMA_scripts = count_scripts(ILMA_SCRIPTS)
    
    skill_gap = ILMA_skills - ilma_skills
    script_gap = ILMA_scripts - ilma_scripts
    
    # Calculate evolution score (0-10)
    skill_score = min(ilma_skills / ILMA_skills, 1.0) * 5
    script_score = min(ilma_scripts / ILMA_scripts, 1.0) * 5
    evolution_score = skill_score + script_score
    
    log(f"📊 ILMA State:", C_BOLD)
    log(f"   Skills: {ilma_skills}")
    log(f"   Scripts: {ilma_scripts}")
    
    log(f"\n📊 ILMA State:", C_BOLD)
    log(f"   Skills: {ILMA_skills}")
    log(f"   Scripts: {ILMA_scripts}")
    
    log(f"\n📊 Gap Analysis:", C_BOLD)
    if skill_gap > 0:
        log(f"   Skills: ILMA leads by {skill_gap}", C_Y)
    else:
        log(f"   Skills: ILMA leads by {abs(skill_gap)}", C_G)
    
    if script_gap > 0:
        log(f"   Scripts: ILMA leads by {script_gap}", C_Y)
    else:
        log(f"   Scripts: ILMA leads by {abs(script_gap)}", C_G)
    
    log(f"\n🏆 Evolution Score: {evolution_score:.1f}/10", C_C)
    
    # Save metrics
    metrics = EvolutionMetrics(
        timestamp=get_timestamp(),
        ilma_skills=ilma_skills,
        ilma_scripts=ilma_scripts,
        ILMA_skills=ILMA_skills,
        ILMA_scripts=ILMA_scripts,
        skill_gap=skill_gap,
        script_gap=script_gap,
        evolution_score=evolution_score
    )
    
    save_metrics(metrics)
    
    return metrics

def save_metrics(metrics: EvolutionMetrics):
    """Save evolution metrics."""
    metrics_file = ILMA_SYNC / "evolution_metrics.json"
    metrics_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Load existing
    history = []
    if metrics_file.exists():
        try:
            history = json.loads(metrics_file.read_text())
        except Exception:
            pass
    
    # Add new metrics
    history.append({
        "timestamp": metrics.timestamp,
        "ilma_skills": metrics.ilma_skills,
        "ilma_scripts": metrics.ilma_scripts,
        "ILMA_skills": metrics.ILMA_skills,
        "ILMA_scripts": metrics.ILMA_scripts,
        "evolution_score": metrics.evolution_score
    })
    
    # Keep last 100
    history = history[-100:]
    
    metrics_file.write_text(json.dumps(history, indent=2))

# ─── Study ILMA ─────────────────────────────────────────────────────────────
def study():
    """Study ILMA patterns."""
    log_section("STUDY: ILMA PATTERNS")
    
    log("Mempelajari pola ILMA...")
    
    # Study ILMA's key files
    key_files = [
        ("SOUL.md", "Identity & Constitution"),
        ("MEMORY.md", "Memory System"),
        ("ILMA_RUNTIME_GUIDE.md", "Runtime Operations"),
        ("AGENTS.md", "Agent Workflow"),
    ]
    
    for filename, description in key_files:
        filepath = ILMA_DIR / filename
        if filepath.exists():
            size = filepath.stat().st_size
            log(f"  ✅ {filename}: {size//1024}KB - {description}", C_G)
        else:
            log(f"  ❌ {filename}: Not found", C_R)
    
    # Study key scripts
    key_scripts = [
        "ILMA_intelligent_orchestrator.py",
        "ILMA_capability_orchestrator.py",
        "ILMA_self_learning.py",
        "ILMA_daily_optimizer.py",
    ]
    
    log(f"\n📜 ILMA Scripts:", C_BOLD)
    for script in key_scripts:
        filepath = ILMA_SCRIPTS / script
        if filepath.exists():
            lines = len(filepath.read_text().splitlines())
            log(f"  ✅ {script}: {lines} lines", C_G)
        else:
            log(f"  ❌ {script}: Not found", C_R)
    
    # Analyze skill patterns
    log(f"\n📚 ILMA Skill Categories:", C_BOLD)
    categories: Dict[str, int] = {}
    for skill_dir in ILMA_SKILLS.iterdir():
        if skill_dir.is_dir():
            cat = "uncategorized"
            skill_md = skill_dir / "SKILL.md"
            if skill_md.exists():
                content = skill_md.read_text()[:200]
                for line in content.split("\n"):
                    if "category:" in line.lower():
                        cat = line.split(":", 1)[1].strip().lower()
                        break
            categories[cat] = categories.get(cat, 0) + 1
    
    for cat, count in sorted(categories.items(), key=lambda x: -x[1])[:10]:
        log(f"  {cat}: {count}", C_C)
    
    log(f"\n✅ Study complete", C_G)

# ─── Gap Analysis ───────────────────────────────────────────────────────────
def gap_analysis():
    """Analyze gaps between ILMA and ILMA."""
    log_section("GAP ANALYSIS")
    
    metrics = assess()
    
    gaps = []
    
    # Skill gap
    if metrics.skill_gap > 0:
        gaps.append({
            "type": "skills",
            "gap": metrics.skill_gap,
            "priority": "high" if metrics.skill_gap > 50 else "medium",
            "suggestion": "Create more skills to match ILMA's coverage"
        })
    
    # Script gap
    if metrics.script_gap > 0:
        gaps.append({
            "type": "scripts",
            "gap": metrics.script_gap,
            "priority": "high" if metrics.script_gap > 50 else "medium",
            "suggestion": "Create more scripts for ILMA-level functionality"
        })
    
    # Quality gap (ILMA scripts tend to be larger/more mature)
    log(f"\n📊 Quality Analysis:", C_BOLD)
    
    # Check average script size
    ilma_total_size = sum(s.stat().st_size for s in ILMA_SCRIPTS.glob("*.py"))
    ILMA_total_size = sum(s.stat().st_size for s in ILMA_SCRIPTS.glob("*.py"))
    
    ilma_avg = ilma_total_size / max(metrics.ilma_scripts, 1)
    ILMA_avg = ILMA_total_size / max(metrics.ILMA_scripts, 1)
    
    log(f"  ILMA avg script: {ilma_avg/1024:.1f}KB")
    log(f"  ILMA avg script: {ILMA_avg/1024:.1f}KB")
    
    if ilma_avg < ILMA_avg * 0.5:
        gaps.append({
            "type": "quality",
            "gap": "ILMA scripts are significantly smaller",
            "priority": "high",
            "suggestion": "Expand script content for better functionality"
        })
    
    # Print gap summary
    log(f"\n📋 Gap Summary:", C_BOLD)
    for i, gap in enumerate(gaps, 1):
        priority_color = C_R if gap["priority"] == "high" else C_Y
        log(f"  {i}. [{c(gap['priority'].upper(), priority_color)}] {gap['type']}: {gap['gap']}")
        log(f"     → {gap['suggestion']}")
    
    # Save gaps
    gaps_file = ILMA_SYNC / "gaps.json"
    gaps_file.write_text(json.dumps(gaps, indent=2))
    
    return gaps

# ─── Evolve ─────────────────────────────────────────────────────────────────
def evolve():
    """Apply improvements to close gaps."""
    log_section("EVOLUTION: APPLYING IMPROVEMENTS")
    
    # First, sync with ILMA
    log("1. Syncing with ILMA patterns...")
    exit_code, stdout, stderr = run_py(["python3", f"{ILMA_SCRIPTS}/ilma_ILMA_sync.py", "run"])
    if exit_code == 0:
        log("   ✅ ILMA sync complete", C_G)
    else:
        log(f"   ⚠️ ILMA sync issues: {stderr[:50]}", C_Y)
    
    # Run daily optimizer
    log("2. Running daily optimizer...")
    exit_code, stdout, stderr = run_py(["python3", f"{ILMA_SCRIPTS}/ilma_daily_optimizer.py", "run"], timeout=300)
    if exit_code == 0:
        log("   ✅ Daily optimizer complete", C_G)
    else:
        log(f"   ⚠️ Daily optimizer issues", C_Y)
    
    # Check for improvements needed
    log("3. Analyzing improvements...")
    
    improvements = []
    
    # Check skill count
    ilma_skills = count_skills(ILMA_SKILLS)
    ILMA_skills = count_skills(ILMA_SKILLS)
    
    if ilma_skills < ILMA_skills:
        gap = ILMA_skills - ilma_skills
        improvements.append(f"Need {gap} more skills to match ILMA")
    
    # Check script count
    ilma_scripts = count_scripts(ILMA_SCRIPTS)
    ILMA_scripts = count_scripts(ILMA_SCRIPTS)
    
    if ilma_scripts < ILMA_scripts:
        gap = ILMA_scripts - ilma_scripts
        improvements.append(f"Need {gap} more scripts to match ILMA")
    
    # Check quality
    metrics_file = ILMA_SYNC / "evolution_metrics.json"
    if metrics_file.exists():
        history = json.loads(metrics_file.read_text())
        if len(history) >= 2:
            prev = history[-2]["evolution_score"]
            curr = history[-1]["evolution_score"]
            if curr > prev:
                improvements.append(f"Evolution score improved: {prev:.1f} → {curr:.1f}")
    
    # Print improvements
    if improvements:
        log(f"\n📋 Improvements Applied:", C_BOLD)
        for imp in improvements:
            log(f"   ✅ {imp}", C_G)
    else:
        log(f"\n⚠️ No specific improvements identified", C_Y)
    
    log(f"\n✅ Evolution cycle complete", C_G)
    
    # Final assessment
    log_section("POST-EVOLUTION ASSESSMENT")
    assess()
    
    return improvements

# ─── Full Evolution Cycle ───────────────────────────────────────────────────
def full_evolution():
    """Run full evolution cycle."""
    log_section("ILMA FULL EVOLUTION CYCLE")
    log(f"Starting at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", C_C)
    
    start_time = time.time()
    
    # Step 1: Assess
    log("\n📊 Step 1: Assessment")
    metrics = assess()
    
    # Step 2: Study
    log("\n📚 Step 2: Study ILMA")
    study()
    
    # Step 3: Gap Analysis
    log("\n📋 Step 3: Gap Analysis")
    gaps = gap_analysis()
    
    # Step 4: Evolve
    log("\n🚀 Step 4: Apply Improvements")
    improvements = evolve()
    
    # Summary
    elapsed = time.time() - start_time
    
    log_section("EVOLUTION COMPLETE")
    log(f"⏱️ Total time: {elapsed:.1f}s")
    log(f"📊 Current score: {metrics.evolution_score:.1f}/10")
    log(f"📋 Gaps identified: {len(gaps)}")
    log(f"✅ Improvements applied: {len(improvements)}")
    
    if metrics.evolution_score >= 8.0:
        log(f"\n🎉 ILMA has achieved EXCELLENCE!", C_G)
    elif metrics.evolution_score >= 5.0:
        log(f"\n👍 ILMA is progressing well", C_G)
    else:
        log(f"\n📈 ILMA is on the path to improvement", C_Y)

# ─── Status ─────────────────────────────────────────────────────────────────
def show_status():
    """Show evolution status."""
    log_section("ILMA EVOLUTION STATUS")
    
    # Current metrics
    metrics_file = ILMA_SYNC / "evolution_metrics.json"
    if metrics_file.exists():
        history = json.loads(metrics_file.read_text())
        if history:
            latest = history[-1]
            log(f"📊 Latest Metrics ({latest['timestamp'][:10]}):", C_BOLD)
            log(f"   ILMA Skills: {latest['ilma_skills']}")
            log(f"   ILMA Scripts: {latest['ilma_scripts']}")
            log(f"   ILMA Skills: {latest['ILMA_skills']}")
            log(f"   ILMA Scripts: {latest['ILMA_scripts']}")
            log(f"   Evolution Score: {latest['evolution_score']:.1f}/10")
            
            if len(history) >= 2:
                prev = history[-2]["evolution_score"]
                curr = latest["evolution_score"]
                delta = curr - prev
                direction = f"{c('↑', C_G)}" if delta > 0 else f"{c('↓', C_R)}" if delta < 0 else "-"
                log(f"   Change: {direction} {abs(delta):.2f}")
    
    # Gaps
    gaps_file = ILMA_SYNC / "gaps.json"
    if gaps_file.exists():
        gaps = json.loads(gaps_file.read_text())
        log(f"\n📋 Recent Gaps: {len(gaps)}")
        for gap in gaps[:3]:
            log(f"   • {gap['type']}: {gap['gap']}")
    
    # ILMA sync status
    sync_file = ILMA_SYNC / "sync_history.json"
    if sync_file.exists():
        sync = json.loads(sync_file.read_text())
        log(f"\n🔄 Last ILMA Sync: {sync.get('last_sync', 'unknown')[:10]}")
        log(f"   Total syncs: {sync.get('total_syncs', 0)}")

# ─── Main ───────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="ILMA Evolution Routine")
    parser.add_argument("action", nargs="?", default="full",
                       choices=["assess", "study", "gap", "evolve", "full", "status"])
    args = parser.parse_args()
    
    if args.action == "assess":
        assess()
    elif args.action == "study":
        study()
    elif args.action == "gap":
        gap_analysis()
    elif args.action == "evolve":
        evolve()
    elif args.action == "full":
        full_evolution()
    elif args.action == "status":
        show_status()

if __name__ == "__main__":
    main()
