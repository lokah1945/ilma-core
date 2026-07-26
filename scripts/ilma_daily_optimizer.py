#!/usr/bin/env python3
"""
ILMA Daily Optimizer - Rutinitas optimalisasi harian untuk ILMA
=============================================================

Mengadopsi pola ILMA daily optimizer dengan fase-fase:
  1. Backup (mandatory)
  2. Self-Audit (evaluate current state)
  3. Skill Health Check (verify all skills)
  4. Script Quality Check (verify all scripts)
  5. Learning Sync (sync with ILMA patterns)
  6. Improvement Cycle (apply optimizations)
  7. Benchmark (measure progress)

Usage:
    python3 ilma_daily_optimizer.py run          # Full optimization run
    python3 ilma_daily_optimizer.py backup        # Backup only
    python3 ilma_daily_optimizer.py audit         # Self-audit only
    python3 ilma_daily_optimizer.py health        # Health check only
    python3 ilma_daily_optimizer.py learn         # Learning sync only
    python3 ilma_daily_optimizer.py improve      # Improvement cycle only
    python3 ilma_daily_optimizer.py benchmark     # Benchmark only
    python3 ilma_daily_optimizer.py cron-setup    # Setup 05:00 WIB cron
    python3 ilma_daily_optimizer.py status        # Show current status
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

# ─── Paths ─────────────────────────────────────────────────────────────────
PROFILE_DIR = Path("/root/.hermes/profiles/ilma")
WORKSPACE = PROFILE_DIR
BACKUP_DIR = Path("/root/backup/ilma")
CACHE_DIR = Path("/root/.cache/ilma")
LOG_FILE = CACHE_DIR / "optimization_log.jsonl"
SKILLS_DIR = PROFILE_DIR / "skills"
SCRIPTS_DIR = PROFILE_DIR / "scripts"

# ─── ANSI Colors ───────────────────────────────────────────────────────────
C_R = "\033[91m"; C_G = "\033[92m"; C_Y = "\033[93m"; C_B = "\033[94m"
C_C = "\033[96m"; C_BOLD = "\033[1m"; C_RESET = "\033[0m"

def c(t, col): return f"{col}{t}{C_RESET}"

# ─── Data Classes ────────────────────────────────────────────────────────────
@dataclass
class OptimizationPhase:
    name: str
    description: str
    status: str = "pending"  # pending, running, success, failed, skipped
    duration_seconds: Optional[float] = None
    details: str = ""

@dataclass
class OptimizationReport:
    timestamp: str
    phases: List[OptimizationPhase]
    overall_score_before: float
    overall_score_after: float
    improvements_applied: List[str]
    issues_found: List[str]
    recommendations: List[str]

# ─── Utility Functions ───────────────────────────────────────────────────────
def log(msg, color=C_C):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{color}[{ts}] {msg}{C_RESET}")

def log_phase(phase: str, msg: str):
    log(f"[{phase}] {msg}", C_B)

def ensure_dirs():
    """Ensure all required directories exist."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (CACHE_DIR / "insights").mkdir(parents=True, exist_ok=True)

def get_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()

def run_command(cmd: List[str], timeout: int = 300) -> tuple[int, str, str]:
    """Run command and return exit_code, stdout, stderr."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"Command timed out after {timeout}s"
    except Exception as e:
        return -1, "", str(e)

# ─── Phase 1: Backup ─────────────────────────────────────────────────────────
def phase_backup() -> OptimizationPhase:
    """Backup ILMA workspace before optimization."""
    phase = OptimizationPhase(
        name="backup",
        description="Backup ILMA workspace before optimization"
    )
    log_phase(phase.name, "Memulai backup...")
    start = time.time()
    
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = BACKUP_DIR / f"ilma_backup_{timestamp}"
        backup_path.mkdir(parents=True, exist_ok=True)
        
        # Backup skills
        skills_backup = backup_path / "skills"
        if SKILLS_DIR.exists():
            subprocess.run(
                ["cp", "-r", str(SKILLS_DIR), str(skills_backup)],
                check=True
            )
        
        # Backup scripts
        scripts_backup = backup_path / "scripts"
        if SCRIPTS_DIR.exists():
            subprocess.run(
                ["cp", "-r", str(SCRIPTS_DIR), str(scripts_backup)],
                check=True
            )
        
        # Backup memory and configs
        for item in ["memories", "SOUL.md", "config.yaml"]:
            src = PROFILE_DIR / item
            if src.exists():
                subprocess.run(
                    ["cp", "-r", str(src), str(backup_path / item)],
                    check=True
                )
        
        phase.status = "success"
        phase.details = f"Backup saved to {backup_path}"
        log(f"✅ Backup completed: {backup_path}", C_G)
        
    except Exception as e:
        phase.status = "failed"
        phase.details = str(e)
        log(f"❌ Backup failed: {e}", C_R)
    
    phase.duration_seconds = time.time() - start
    return phase

# ─── Phase 2: Self-Audit ─────────────────────────────────────────────────────
def phase_audit() -> OptimizationPhase:
    """Run self-audit to evaluate current state."""
    phase = OptimizationPhase(
        name="audit",
        description="Self-audit current ILMA state"
    )
    log_phase(phase.name, "Memulai self-audit...")
    start = time.time()
    
    try:
        # Run self-improve audit (use -v for verbose output)
        exit_code, stdout, stderr = run_command(
            ["python3", f"{SCRIPTS_DIR}/ilma_self_improve.py", "-v"],
            timeout=120
        )
        
        if exit_code == 0:
            phase.status = "success"
            phase.details = "Self-audit completed successfully"
            log(f"✅ Self-audit completed", C_G)
            # Extract useful info from output
            for line in stdout.split("\n"):
                if "SUCCESS" in line or "Score" in line or "completed" in line.lower():
                    log(f"   {line.strip()}", C_Y)
        else:
            phase.status = "failed"
            phase.details = stderr[:200]
            log(f"❌ Self-audit failed: {stderr[:100]}", C_R)
            
    except Exception as e:
        phase.status = "failed"
        phase.details = str(e)
        log(f"❌ Self-audit error: {e}", C_R)
    
    phase.duration_seconds = time.time() - start
    return phase

# ─── Phase 3: Skill Health Check ─────────────────────────────────────────────
def phase_skill_health() -> OptimizationPhase:
    """Check health of all skills."""
    phase = OptimizationPhase(
        name="skill_health",
        description="Check health of all skills"
    )
    log_phase(phase.name, "Memeriksa health skills...")
    start = time.time()
    
    try:
        # Check if health script exists
        health_script = SCRIPTS_DIR / "ilma_skill_health.py"
        if health_script.exists():
            exit_code, stdout, stderr = run_command(
                ["python3", str(health_script)], timeout=60
            )
        else:
            # Manual check
            skills_ok = 0
            skills_total = 0
            issues = []
            
            for skill_dir in SKILLS_DIR.iterdir():
                skills_total += 1
                if skill_dir.is_dir():
                    skill_md = skill_dir / "SKILL.md"
                    if skill_md.exists():
                        skills_ok += 1
                    else:
                        issues.append(f"Missing SKILL.md: {skill_dir.name}")
                elif skill_dir.suffix == ".py":
                    skills_ok += 1
            
            stdout = f"Skills: {skills_ok}/{skills_total} OK"
            if issues:
                stdout += f"\nIssues: {len(issues)}"
        
        phase.status = "success"
        phase.details = f"Health check: {stdout.split(chr(10))[0]}"
        log(f"✅ Skill health: {stdout.split(chr(10))[0]}", C_G)
        
    except Exception as e:
        phase.status = "failed"
        phase.details = str(e)
        log(f"❌ Skill health check failed: {e}", C_R)
    
    phase.duration_seconds = time.time() - start
    return phase

# ─── Phase 4: Script Quality Check ──────────────────────────────────────────
def phase_script_quality() -> OptimizationPhase:
    """Check quality of all scripts."""
    phase = OptimizationPhase(
        name="script_quality",
        description="Check quality of all scripts"
    )
    log_phase(phase.name, "Memeriksa quality scripts...")
    start = time.time()
    
    scripts_ok = 0
    scripts_total = 0
    errors = []
    
    try:
        for script in SCRIPTS_DIR.glob("*.py"):
            scripts_total += 1
            # Syntax check
            exit_code, _, stderr = run_command(
                ["python3", "-m", "py_compile", str(script)], timeout=10
            )
            if exit_code == 0:
                scripts_ok += 1
            else:
                errors.append(f"{script.name}: syntax error")
        
        # Check for empty/broken scripts
        for script in SCRIPTS_DIR.glob("*.py"):
            size = script.stat().st_size
            if size < 100:  # Suspiciously small
                errors.append(f"{script.name}: suspiciously small ({size} bytes)")
        
        phase.status = "success" if scripts_ok == scripts_total else "partial"
        phase.details = f"{scripts_ok}/{scripts_total} scripts OK"
        if errors:
            phase.details += f", {len(errors)} issues"
            log(f"⚠️ Scripts: {scripts_ok}/{scripts_total} OK, {len(errors)} issues", C_Y)
        else:
            log(f"✅ Scripts: {scripts_ok}/{scripts_total} OK", C_G)
        
    except Exception as e:
        phase.status = "failed"
        phase.details = str(e)
        log(f"❌ Script quality check failed: {e}", C_R)
    
    phase.duration_seconds = time.time() - start
    return phase

# ─── Phase 5: Learning Sync (from ILMA) ─────────────────────────────────────
def phase_learning_sync() -> OptimizationPhase:
    """Sync learning patterns from ILMA."""
    phase = OptimizationPhase(
        name="learning_sync",
        description="Sync learning patterns from ILMA"
    )
    log_phase(phase.name, "Syncing dengan ILMA...")
    start = time.time()
    
    try:
        # Check ILMA's latest learning patterns
        ILMA_learning = Path("/root/.hermes/profiles/ilma/data/learning")
        ilma_learning = CACHE_DIR / "learning"
        ilma_learning.mkdir(parents=True, exist_ok=True)
        
        synced = []
        if ILMA_learning.exists():
            for item in ILMA_learning.glob("*"):
                if item.is_file():
                    dest = ilma_learning / item.name
                    subprocess.run(["cp", str(item), str(dest)], check=False)
                    synced.append(item.name)
        
        # Also sync from ILMA's continuous learning patterns
        ILMA_self_learn = Path("/root/.hermes/profiles/ilma/scripts/ILMA_self_learning.py")
        if ILMA_self_learn.exists():
            # Extract useful patterns
            content = ILMA_self_learn.read_text()
            # Look for DEFAULT_TIMEOUTS, DEFAULT_CACHE_TTL patterns
            if "DEFAULT_TIMEOUTS" in content:
                phase.details += " [ILMA timeouts synced]"
        
        phase.status = "success"
        phase.details = f"Synced {len(synced)} items from ILMA"
        log(f"✅ Learning sync: {len(synced)} items", C_G)
        
    except Exception as e:
        phase.status = "failed"
        phase.details = str(e)
        log(f"❌ Learning sync failed: {e}", C_R)
    
    phase.duration_seconds = time.time() - start
    return phase

# ─── Phase 6: Improvement Cycle ──────────────────────────────────────────────
def phase_improve() -> OptimizationPhase:
    """Run improvement cycle."""
    phase = OptimizationPhase(
        name="improve",
        description="Run improvement cycle"
    )
    log_phase(phase.name, "Menjalankan improvement cycle...")
    start = time.time()
    
    try:
        # Run self-improve (no args needed - it just runs)
        exit_code, stdout, stderr = run_command(
            ["python3", f"{SCRIPTS_DIR}/ilma_self_improve.py", "-v"],
            timeout=180
        )
        
        improvements = []
        for line in stdout.split("\n"):
            if "Applied:" in line or "Improved:" in line or "Fixed:" in line or "SUCCESS" in line:
                improvements.append(line.strip())
        
        phase.status = "success" if exit_code == 0 else "partial"
        phase.details = f"Applied {len(improvements)} improvements"
        log(f"✅ Improvement cycle: {len(improvements)} changes", C_G)
        
        # ── Run Benchmark + Provider Intelligence Enrichment ────────────────
        enrich_logs = []
        
        # Passive Benchmark Enricher
        pbe_script = SCRIPTS_DIR / "ilma_passive_benchmark_enricher.py"
        if pbe_script.exists():
            exit_code2, stdout2, stderr2 = run_command(
                ["python3", str(pbe_script)], timeout=120
            )
            if exit_code2 == 0:
                enrich_logs.append("PassiveBenchmark: OK")
                logger.info("[Optimizer] PassiveBenchmarkEnricher completed")
            else:
                enrich_logs.append(f"PassiveBenchmark: failed ({stderr2[:100]})")
        
        # Provider Intelligence Enricher
        pie_script = SCRIPTS_DIR / "ilma_provider_intelligence_enricher.py"
        if pie_script.exists():
            exit_code3, stdout3, stderr3 = run_command(
                ["python3", str(pie_script), "--enrich"], timeout=180
            )
            if exit_code3 == 0:
                enrich_logs.append("ProviderIntelligence: OK")
                logger.info("[Optimizer] ProviderIntelligenceEnricher completed")
            else:
                enrich_logs.append(f"ProviderIntelligence: failed ({stderr3[:100]})")
        
        if enrich_logs:
            phase.details += f" | Enrichers: {'; '.join(enrich_logs)}"
            log(f"✅ Benchmark enrichment: {'; '.join(enrich_logs)}", C_G)
        
    except Exception as e:
        phase.status = "failed"
        phase.details = str(e)
        log(f"❌ Improvement cycle failed: {e}", C_R)
    
    phase.duration_seconds = time.time() - start
    return phase

# ─── Phase 7: Benchmark ─────────────────────────────────────────────────────
def phase_mil_maintenance() -> OptimizationPhase:
    """MIL production maintenance: aggregate telemetry -> registry, then re-apply
    MIL bindings (self-test-gated, auto-revert). Keeps per-task model selection
    fresh + healthy without touching persona/memory/state."""
    phase = OptimizationPhase(name="mil_maintenance",
                              description="Telemetry aggregate + MIL re-binding (gated)")
    log_phase(phase.name, "MIL maintenance...")
    start = time.time()
    details = []
    ok = 0
    try:
        root = str(PROFILE_DIR) if "PROFILE_DIR" in globals() else "/root/.hermes/profiles/ilma"
        # 1) telemetry -> registry learning loop
        r1 = run_command(["python3", "ilma_model_telemetry.py", "--aggregate"], timeout=60)
        if r1[0] == 0:
            ok += 1; details.append("telemetry_agg")
        # 2) re-apply MIL bindings (only acts if config flags enable bind)
        r2 = run_command(["python3", "ilma_mil_apply.py"], timeout=200)
        if r2[0] == 0:
            ok += 1; details.append("mil_apply")
        phase.status = "success" if ok >= 1 else "partial"
        phase.details = " ".join(details) or "no-op"
        log(f"✅ MIL maintenance: {phase.details}", C_G)
    except Exception as e:
        phase.status = "failed"; phase.details = str(e)
        log(f"❌ MIL maintenance failed: {e}", C_R)
    phase.duration_seconds = time.time() - start
    return phase


def phase_model_pipeline() -> OptimizationPhase:
    """Refresh the model-intelligence pipeline: AA benchmarks -> full-sync (list+
    enrich+score) -> callability validation -> latency benchmark. Keeps the router
    using the best FREE callable models with fresh data."""
    phase = OptimizationPhase(
        name="model_pipeline",
        description="Refresh provider list, benchmarks, scores, callability, latency",
    )
    log_phase(phase.name, "Refreshing model intelligence pipeline...")
    start = time.time()
    steps_ok = 0
    details = []
    try:
        import os as _os
        _os.environ.setdefault("LAT_TOP_N", "25")
        # 1) AA benchmark fetch
        aa = SCRIPTS_DIR / "aa_scraper" / "aa_scraper.py"
        if aa.exists():
            rc, out, err = run_command(["python3", str(aa)], timeout=120)
            if rc == 0: steps_ok += 1; details.append("AA✅")
            else: details.append("AA❌")
        # 2) full-sync (list + benchmark + enrich + score)
        mdb = SCRIPTS_DIR / "ilma_model_db_manager.py"
        if mdb.exists():
            try:
                _os.remove("/tmp/ilma_model_db.lock")
            except OSError:
                pass
            rc, out, err = run_command(["python3", str(mdb), "--full-sync"], timeout=300)
            if rc == 0: steps_ok += 1; details.append("sync✅")
            else: details.append("sync❌")
        # 3) callability validation
        cv = SCRIPTS_DIR / "ilma_callability_validator.py"
        if cv.exists():
            rc, out, err = run_command(["python3", str(cv)], timeout=300)
            if rc == 0: steps_ok += 1; details.append("callable✅")
            else: details.append("callable❌")
        # 4b) specialization DB re-score (measured)
        spec = PROFILE_DIR / "ilma_spec_db_measured.py"
        try:
            import os as _os
            _sp = _os.path.join("/root/.hermes/profiles/ilma", "ilma_spec_db_measured.py")
            rc,out,err = run_command(["python3", _sp], timeout=120)
            if rc==0: steps_ok+=1; details.append("spec✅")
        except Exception: pass
        # 4) latency benchmark
        lb = SCRIPTS_DIR / "ilma_latency_bench.py"
        if lb.exists():
            rc, out, err = run_command(["python3", str(lb)], timeout=500)
            if rc == 0: steps_ok += 1; details.append("latency✅")
            else: details.append("latency❌")

        phase.status = "success" if steps_ok >= 3 else ("partial" if steps_ok else "failed")
        phase.details = " ".join(details) or "no steps run"
        log(f"{'✅' if phase.status=='success' else '⚠️'} Model pipeline: {phase.details}", C_G)
    except Exception as e:
        phase.status = "failed"
        phase.details = str(e)
        log(f"❌ Model pipeline failed: {e}", C_R)
    phase.duration_seconds = time.time() - start
    return phase


def phase_benchmark() -> OptimizationPhase:
    """Run benchmark to measure progress."""
    phase = OptimizationPhase(
        name="benchmark",
        description="Run benchmark to measure progress"
    )
    log_phase(phase.name, "Menjalankan benchmark...")
    start = time.time()
    
    try:
        # Run benchmark
        benchmark_script = SCRIPTS_DIR / "ilma_benchmark.py"
        if benchmark_script.exists():
            exit_code, stdout, stderr = run_command(
                ["python3", str(benchmark_script)], timeout=120
            )
        else:
            # Manual benchmark - count skills and scripts
            skills = len(list(SKILLS_DIR.iterdir()))
            scripts = len(list(SCRIPTS_DIR.glob("*.py")))
            stdout = f"Skills: {skills}, Scripts: {scripts}"
        
        phase.status = "success"
        phase.details = stdout.split("\n")[0] if stdout else "No output"
        log(f"✅ Benchmark: {phase.details}", C_G)
        
    except Exception as e:
        phase.status = "failed"
        phase.details = str(e)
        log(f"❌ Benchmark failed: {e}", C_R)
    
    phase.duration_seconds = time.time() - start
    return phase

# ─── Main Orchestration ─────────────────────────────────────────────────────
def run_full_optimization() -> OptimizationReport:
    """Run full daily optimization."""
    log("=" * 60, C_BOLD)
    log("ILMA DAILY OPTIMIZER - Memulai Optimalisasi Harian", C_BOLD)
    log("=" * 60, C_BOLD)
    
    ensure_dirs()
    
    phases = [
        phase_backup(),
        phase_audit(),
        phase_skill_health(),
        phase_script_quality(),
        phase_learning_sync(),
        phase_improve(),
        phase_model_pipeline(),
        phase_mil_maintenance(),
        phase_benchmark(),
    ]
    
    # Calculate summary
    success = sum(1 for p in phases if p.status == "success")
    failed = sum(1 for p in phases if p.status == "failed")
    partial = sum(1 for p in phases if p.status == "partial")
    
    total_time = sum(p.duration_seconds or 0 for p in phases)
    
    report = OptimizationReport(
        timestamp=get_timestamp(),
        phases=phases,
        overall_score_before=0.0,  # Would need before/after measurement
        overall_score_after=0.0,
        improvements_applied=[],
        issues_found=[p.details for p in phases if p.status != "success"],
        recommendations=[
            f"Completed {success} phases successfully",
            f"Failed: {failed}, Partial: {partial}",
            f"Total time: {total_time:.1f}s"
        ]
    )
    
    # Save report
    log_file = CACHE_DIR / f"optimization_report_{datetime.now().strftime('%Y%m%d')}.json"
    with open(log_file, "w") as f:
        json.dump({
            "timestamp": report.timestamp,
            "phases": [
                {"name": p.name, "status": p.status, "duration": p.duration_seconds, "details": p.details}
                for p in phases
            ],
            "summary": {
                "success": success,
                "failed": failed,
                "partial": partial,
                "total_time": total_time
            }
        }, f, indent=2)
    
    log("=" * 60, C_BOLD)
    log(f"OPTIMIZATION COMPLETE: {success}✅ {partial}⚠️ {failed}❌", C_BOLD)
    log(f"Total time: {total_time:.1f}s", C_Y)
    log("=" * 60, C_BOLD)
    
    return report

def show_status():
    """Show current ILMA status."""
    log("ILMA Status Report", C_BOLD)
    log("-" * 40)
    
    # Count items
    skills = len(list(SKILLS_DIR.iterdir())) if SKILLS_DIR.exists() else 0
    scripts = len(list(SCRIPTS_DIR.glob("*.py"))) if SCRIPTS_DIR.exists() else 0
    
    log(f"Skills: {skills}")
    log(f"Scripts: {scripts}")
    
    # Check for today's optimization
    today_report = CACHE_DIR / f"optimization_report_{datetime.now().strftime('%Y%m%d')}.json"
    if today_report.exists():
        with open(today_report) as f:
            data = json.load(f)
        log(f"Last optimization: {data['timestamp'][:10]}")
        log(f"Success: {data['summary']['success']} phases")
    else:
        log("No optimization run today", C_Y)

def setup_cron():
    """Setup daily cron job at 05:00 WIB."""
    cron_line = "0 5 * * * python3 /root/.hermes/profiles/ilma/scripts/ilma_daily_optimizer.py run >> /root/.cache/ilma/cron.log 2>&1"
    
    # Check if already installed
    result = subprocess.run(
        ["crontab", "-l"], capture_output=True, text=True
    )
    
    if "ilma_daily_optimizer" in result.stdout:
        log("Cron job already installed", C_Y)
    else:
        # Add to crontab
        new_crontab = result.stdout.strip() + "\n" + cron_line + "\n"
        subprocess.run(["crontab", "-"], input=new_crontab, text=True)
        log("✅ Cron job installed: 05:00 WIB daily", C_G)
    
    log("Cron setup complete", C_C)

# ─── CLI Entry Point ─────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="ILMA Daily Optimizer")
    parser.add_argument("action", nargs="?", default="run",
                        choices=["run", "backup", "audit", "health", "learn", "improve", "benchmark", "cron-setup", "status"])
    args = parser.parse_args()
    
    ensure_dirs()
    
    if args.action == "run":
        run_full_optimization()
    elif args.action == "backup":
        result = phase_backup()
        log(f"Backup: {result.status}")
    elif args.action == "audit":
        result = phase_audit()
        log(f"Audit: {result.status}")
    elif args.action == "health":
        result = phase_skill_health()
        log(f"Health: {result.status}")
    elif args.action == "learn":
        result = phase_learning_sync()
        log(f"Learning sync: {result.status}")
    elif args.action == "improve":
        result = phase_improve()
        log(f"Improve: {result.status}")
    elif args.action == "benchmark":
        result = phase_benchmark()
        log(f"Benchmark: {result.status}")
    elif args.action == "cron-setup":
        setup_cron()
    elif args.action == "status":
        show_status()

if __name__ == "__main__":
    main()
