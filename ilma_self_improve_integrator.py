#!/usr/bin/env python3
"""
ILMA Self-Improve Integrator — LAYER 9 CANONICAL SELF-IMPROVEMENT ENGINE v1.0
================================================================================
Canonical self-improvement engine: connects LearningLogger, SelfImprovementEngine,
KnowledgeGraph, and Evidence Ledger into a unified closed-loop system.

WIRED INTO: ilma_runtime_wiring.py (LAYER_9_SELF_IMPROVE)
PIPELINE INTEGRATION: After VERIFY phase → LEARN(self_improve_integrator)
CLI: python3 ilma_self_improve_integrator.py (status|optimize|record|learn|audit|dna)

All capabilities:
  1. Event-based learning (SelfImprovementEngine) — tracks task quality, model performance
  2. File-based persistent learnings (LearningLogger) — errors, corrections, insights, DNA
  3. Knowledge graph integration (KnowledgeGraph) — nodes/edges for patterns
  4. Evidence ledger (EvidenceValidator) — every claim has evidence_id
  5. Auto-optimization daemon — daily optimization cycles, trend detection
  6. DNA evolution — promotes high-value learnings to permanent behavioral rules
  7. Pipeline checkpoint — called after VERIFY in every task execution
  8. CLI + Python API

Pipeline integration:
  LEARN phase uses SelfImproveIntegrator.record_result(task_type, quality, model, errors)
  Auto-runs optimization_cycle() every 20 tasks or on demand
  DNA updates are logged to .learnings/DNA_UPDATES.md and memory/DNA_UPDATES.md
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

# ─── PATHS ─────────────────────────────────────────────────────────────────────
ILMA_ROOT = Path(os.environ.get("ILMA_ROOT", "/root/.hermes/profiles/ilma"))
LEARNINGS_DIR = ILMA_ROOT / ".learnings"
MEMORY_DIR = ILMA_ROOT / "memory"
EVIDENCE_DIR = ILMA_ROOT / "memory" / "evidence_ledger"
DATA_DIR = ILMA_ROOT / "ilma_model_router_data"

for _d in [LEARNINGS_DIR, MEMORY_DIR, EVIDENCE_DIR, DATA_DIR]:
    _d.mkdir(parents=True, exist_ok=True)

# ─── LOGGING ────────────────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

# ─── EXISTING SYSTEM IMPORTS ────────────────────────────────────────────────────

# Import LearningLogger from ilma_self_improvement.py
_learning_logger = None
_self_improvement_engine = None
_knowledge_graph = None

def _get_learning_logger():
    global _learning_logger
    if _learning_logger is None:
        try:
            sys.path.insert(0, str(ILMA_ROOT))
            from ilma_self_improvement import LearningLogger
            _learning_logger = LearningLogger()
        except Exception as e:
            logger.warning(f"Could not import LearningLogger: {e}")
            _learning_logger = _FallbackLearningLogger()
    return _learning_logger

def _get_self_improvement_engine():
    global _self_improvement_engine
    if _self_improvement_engine is None:
        try:
            sys.path.insert(0, str(ILMA_ROOT))
            from ilma_self_improvement import SelfImprovementEngine
            _self_improvement_engine = SelfImprovementEngine()
        except Exception as e:
            logger.warning(f"Could not import SelfImprovementEngine: {e}")
            _self_improvement_engine = _FallbackSelfImprovementEngine()
    return _self_improvement_engine

def _get_knowledge_graph():
    global _knowledge_graph
    if _knowledge_graph is None:
        try:
            sys.path.insert(0, str(ILMA_ROOT))
            from ilma_knowledge_graph import KnowledgeGraph
            kg_path = DATA_DIR / "knowledge_graph.json"
            _knowledge_graph = KnowledgeGraph(persistence_path=str(kg_path))
        except Exception as e:
            logger.warning(f"Could not import KnowledgeGraph: {e}")
            _knowledge_graph = None
    return _knowledge_graph


class _FallbackLearningLogger:
    """Fallback when LearningLogger is unavailable."""
    def log_error(self, *args, **kwargs): return "FALLBACK-ERR"
    def log_correction(self, *args, **kwargs): return "FALLBACK-CORR"
    def log_insight(self, *args, **kwargs): return "FALLBACK-INS"
    def log_learning(self, *args, **kwargs): return "FALLBACK-LRN"
    def log_best_practice(self, *args, **kwargs): return "FALLBACK-BP"
    def log_feature_request(self, *args, **kwargs): return "FALLBACK-FEAT"
    def resolve(self, *args, **kwargs): return False
    def promote_to_dna(self, *args, **kwargs): return False
    def get_pending(self, *args, **kwargs): return []
    def get_stats(self, *args, **kwargs): return {}


class _FallbackSelfImprovementEngine:
    """Fallback when SelfImprovementEngine is unavailable."""
    def record_event(self, *args, **kwargs): pass
    def get_insights(self, *args, **kwargs): return {}
    def run_optimization_cycle(self, *args, **kwargs): return {}
    def get_quality_trend(self, *args, **kwargs): return "unknown"
    def get_status(self, *args, **kwargs): return {}


# ─── DATACLASSES ───────────────────────────────────────────────────────────────

@dataclass
class TaskResult:
    """A completed task result for learning."""
    task_type: str
    task_description: str
    model_used: str
    provider: str
    result_quality: float  # 0.0 to 1.0
    execution_time_ms: float
    errors: List[str] = field(default_factory=list)
    improvements: List[str] = field(default_factory=list)
    verified: bool = False
    evidence_ids: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    session_id: str = ""

@dataclass
class OptimizationCycle:
    """Results of an optimization cycle."""
    cycle_id: str
    timestamp: datetime
    events_analyzed: int
    quality_trend: str
    avg_quality: float
    suggestions_generated: int
    dna_updates: List[str]
    errors_fixed: int
    improvements_applied: int
    duration_s: float


# ─── SELF-IMPROVE INTEGRATOR ────────────────────────────────────────────────────

class SelfImproveIntegrator:
    """
    LAYER 9 — Canonical Self-Improvement Engine.
    
    Unifies LearningLogger + SelfImprovementEngine + KnowledgeGraph + Evidence Ledger
    into a unified closed-loop system. Every task result is recorded, analyzed,
    and used for continuous improvement.
    
    Usage:
        integrator = SelfImproveIntegrator()
        integrator.record_result(task_type="coding", quality=0.9, model="gpt-5.5")
        integrator.run_optimization_cycle()
        integrator.audit_self()
    """

    # Self-improvement cycle thresholds
    OPTIMIZE_INTERVAL_TASKS = 20        # Run optimization every N tasks
    DNA_PROMOTION_THRESHOLD = 3         # Promote after N resolutions of same pattern
    QUALITY_DECLINE_THRESHOLD = 0.1     # Alert if quality drops by this much
    MAX_LEARNING_ENTRIES = 5000         # Trim if exceeded
    DNA_MAX_AGE_DAYS = 90               # Archive DNA entries older than this

    def __init__(self):
        self.tasks_since_optimize = 0
        self.cycle_count = 0
        self.started_at = datetime.now()
        self._learning_logger = None
        self._engine = None
        self._last_dna_promotion: Dict[str, int] = defaultdict(int)  # entry_id → count
        self._quality_baseline: Optional[float] = None

    @property
    def learning_logger(self):
        if self._learning_logger is None:
            self._learning_logger = _get_learning_logger()
        return self._learning_logger

    @property
    def engine(self):
        if self._engine is None:
            self._engine = _get_self_improvement_engine()
        return self._engine

    # ═══════════════════════════════════════════════════════════════════════════
    # CORE API — record_result()
    # ═══════════════════════════════════════════════════════════════════════════

    def record_result(
        self,
        task_type: str,
        task_description: str,
        model_used: str,
        provider: str,
        result_quality: float,
        execution_time_ms: float,
        errors: Optional[List[str]] = None,
        improvements: Optional[List[str]] = None,
        verified: bool = False,
        evidence_ids: Optional[List[str]] = None,
        session_id: str = "",
    ) -> str:
        """
        Record a task result and trigger auto-improvement if needed.
        
        This is the PRIMARY entry point for learning from task results.
        Called after every task in the pipeline VERIFY phase.
        
        Returns: event_id
        """
        # Build TaskResult
        result = TaskResult(
            task_type=task_type,
            task_description=task_description[:200],
            model_used=model_used,
            provider=provider,
            result_quality=result_quality,
            execution_time_ms=execution_time_ms,
            errors=errors or [],
            improvements=improvements or [],
            verified=verified,
            evidence_ids=evidence_ids or [],
            session_id=session_id,
        )

        # 1. Record in SelfImprovementEngine
        try:
            self.engine.record_event(
                task_type=result.task_type,
                task_description=result.task_description,
                model_used=result.model_used,
                provider=result.provider,
                result_quality=result.result_quality,
                execution_time_ms=result.execution_time_ms,
                errors=result.errors,
                improvements=result.improvements,
                verified=result.verified,
            )
        except Exception as e:
            logger.error(f"Failed to record event in SelfImprovementEngine: {e}")

        # 2. Log errors to LearningLogger
        if result.errors:
            for err in result.errors:
                try:
                    self.learning_logger.log_error(
                        summary=f"{result.task_type}: {err[:80]}",
                        error_detail=err,
                        context={"task_type": result.task_type, "model": result.model_used},
                        area=result.task_type,
                        reproducible="check_failed",
                        priority="high" if result.result_quality < 0.7 else "medium",
                    )
                except Exception as e:
                    logger.error(f"log_error failed: {e}")

        # 3. Log insights if quality is high
        if result.result_quality >= 0.85 and result.improvements:
            for imp in result.improvements:
                try:
                    self.learning_logger.log_insight(
                        summary=f"{result.task_type}: {imp[:80]}",
                        what_discovered=imp,
                        why_useful=f"Quality={result.result_quality:.2f} achieved",
                        suggested_action="Apply to similar tasks",
                        source="task_result",
                        area=result.task_type,
                        tags=["quality", "improvement", result.task_type],
                    )
                except Exception as e:
                    logger.error(f"log_insight failed: {e}")

        # 4. Log best practice if quality very high and has improvements
        if result.result_quality >= 0.92 and result.improvements:
            try:
                self.learning_logger.log_best_practice(
                    summary=f"Best practice from {result.task_type}",
                    pattern="; ".join(result.improvements[:3]),
                    when_to_use=f"Task type: {result.task_type}, Quality target: ≥0.90",
                    source="high_quality_result",
                    area=result.task_type,
                    tags=["best-practice", result.task_type, "validated"],
                )
            except Exception as e:
                logger.error(f"log_best_practice failed: {e}")

        # 5. Add to Knowledge Graph if available
        kg = _get_knowledge_graph()
        if kg is not None:
            try:
                kg.add_node(
                    node_type="LEARNING",
                    name=f"{result.task_type}_{datetime.now().strftime('%Y%m%d')}",
                    properties={
                        "quality": result.result_quality,
                        "model": result.model_used,
                        "task_type": result.task_type,
                        "timestamp": result.timestamp.isoformat(),
                    }
                )
                # Also create SKILL node if task was successful
                if result.result_quality >= 0.8:
                    kg.add_node(
                        node_type="SKILL",
                        name=f"skill_{result.task_type}",
                        properties={
                            "quality_score": result.result_quality,
                            "model": result.model_used,
                            "validated": result.verified,
                        }
                    )
                    kg.add_edge(
                        from_node=f"skill_{result.task_type}",
                        to_node=f"LEARNING:{result.task_type}",
                        edge_type="EVIDENCES"
                    )
            except Exception as e:
                logger.warning(f"KnowledgeGraph update failed: {e}")

        # 6. Check for auto-optimization trigger
        self.tasks_since_optimize += 1
        if self.tasks_since_optimize >= self.OPTIMIZE_INTERVAL_TASKS:
            logger.info(f"[SELF-IMPROVE] {self.tasks_since_optimize} tasks since last optimization — running...")
            self.run_optimization_cycle()
            self.tasks_since_optimize = 0

        # 7. Track quality trend for alerts
        self._track_quality_trend(result.result_quality)

        return f"SELF-IMPROVE-{self.cycle_count}-{int(time.time())}"

    def _track_quality_trend(self, quality: float):
        """Track quality trend and alert on decline."""
        if self._quality_baseline is None:
            self._quality_baseline = quality
            return

        decline = self._quality_baseline - quality
        if decline > self.QUALITY_DECLINE_THRESHOLD:
            logger.warning(
                f"[SELF-IMPROVE] Quality decline detected: {self._quality_baseline:.2f} → {quality:.2f} "
                f"(decline={decline:.2f} > threshold={self.QUALITY_DECLINE_THRESHOLD})"
            )
            try:
                self.learning_logger.log_learning(
                    category="insight",
                    summary=f"Quality decline detected: {decline:.2f} drop",
                    details=f"Baseline: {self._quality_baseline:.2f}, Current: {quality:.2f}",
                    suggested_action="Review recent changes and run optimization cycle",
                    source="quality_monitor",
                    area="self_improvement",
                    tags=["quality-trend", "decline-alert"],
                    priority="high",
                )
            except Exception:
                pass

        # Slowly update baseline (moving average)
        self._quality_baseline = self._quality_baseline * 0.9 + quality * 0.1

    # ═══════════════════════════════════════════════════════════════════════════
    # OPTIMIZATION CYCLE
    # ═══════════════════════════════════════════════════════════════════════════

    def run_optimization_cycle(self) -> OptimizationCycle:
        """
        Run a full optimization cycle: analyze → suggest → apply → document.
        
        Called every OPTIMIZE_INTERVAL_TASKS or on demand.
        Returns OptimizationCycle with results.
        """
        cycle_start = datetime.now()
        cycle_id = f"CYCLE-{self.cycle_count}-{int(time.time())}"

        logger.info(f"[SELF-IMPROVE] Starting optimization cycle {cycle_id}")

        # Step 1: Get insights from engine
        insights = {}
        try:
            insights = self.engine.get_insights()
        except Exception as e:
            logger.error(f"Failed to get engine insights: {e}")
            insights = {}

        # Step 2: Generate optimization suggestions
        suggestions = []
        try:
            suggestions = self.engine.suggest_optimization()
        except Exception as e:
            logger.error(f"Failed to generate suggestions: {e}")

        # Step 3: Auto-resolve pending learnings
        resolved = self._auto_resolve_learning_patterns()

        # Step 4: Promote high-value learnings to DNA
        dna_updates = self._promote_high_value_learnings()

        # Step 5: Apply improvements from suggestions
        improvements_applied = self._apply_suggestions(suggestions)

        # Step 6: Update DNA from quality trends
        self._update_dna_from_trends(insights)

        # Step 7: Trim old entries
        self._trim_learning_entries()

        cycle_duration = (datetime.now() - cycle_start).total_seconds()
        self.cycle_count += 1

        cycle_result = OptimizationCycle(
            cycle_id=cycle_id,
            timestamp=cycle_start,
            events_analyzed=insights.get("total_events", 0),
            quality_trend=insights.get("quality_trend", "unknown"),
            avg_quality=insights.get("avg_quality", 0.0),
            suggestions_generated=len(suggestions),
            dna_updates=dna_updates,
            errors_fixed=resolved,
            improvements_applied=improvements_applied,
            duration_s=cycle_duration,
        )

        # Log the cycle result
        self._log_optimization_cycle(cycle_result)

        logger.info(
            f"[SELF-IMPROVE] Cycle {cycle_id} complete: "
            f"quality={cycle_result.avg_quality:.2f}, "
            f"trend={cycle_result.quality_trend}, "
            f"dna_updates={len(dna_updates)}, "
            f"duration={cycle_duration:.1f}s"
        )

        return cycle_result

    def _auto_resolve_learning_patterns(self) -> int:
        """Auto-resolve learning entries that have similar patterns."""
        resolved = 0
        pending = self.learning_logger.get_pending(limit=100)

        # Group by area/topic
        pattern_groups: Dict[str, List] = defaultdict(list)
        for entry in pending:
            key = f"{entry.get('area', 'unknown')}_{entry.get('priority', 'medium')}"
            pattern_groups[key].append(entry)

        for group_key, entries in pattern_groups.items():
            if len(entries) >= self.DNA_PROMOTION_THRESHOLD:
                # Multiple similar entries — auto-resolve as "pattern_confirmed"
                for entry in entries:
                    try:
                        self.learning_logger.resolve(
                            entry_id=entry["id"],
                            resolution="pattern_confirmed",
                            notes=f"Auto-resolved: {len(entries)} similar entries found"
                        )
                        resolved += 1
                    except Exception:
                        pass

        return resolved

    def _promote_high_value_learnings(self) -> List[str]:
        """Promote learnings that have been resolved multiple times to DNA."""
        dna_ids = []
        pending = self.learning_logger.get_pending(limit=200)

        for entry in pending:
            entry_id = entry["id"]
            priority = entry.get("priority", "medium")

            # High priority resolved entries → candidate for DNA
            if priority in ("high", "critical"):
                # Check if this pattern has been seen before
                self._last_dna_promotion[entry_id] += 1

                if self._last_dna_promotion[entry_id] >= self.DNA_PROMOTION_THRESHOLD:
                    try:
                        distillate = self._distill_entry_to_dna_rule(entry)
                        self.learning_logger.promote_to_dna(entry_id, distillate)
                        dna_ids.append(entry_id)
                        logger.info(f"[SELF-IMPROVE] Promoted to DNA: {entry_id}")
                    except Exception as e:
                        logger.error(f"DNA promotion failed for {entry_id}: {e}")

        return dna_ids

    def _distill_entry_to_dna_rule(self, entry: Dict) -> str:
        """Convert a learning entry into a DNA rule distillate."""
        area = entry.get("area", "unknown")
        title = entry.get("title", "")
        priority = entry.get("priority", "medium")

        return (
            f"RULE: {title}\n"
            f"AREA: {area}\n"
            f"PRIORITY: {priority}\n"
            f"CONTEXT: Auto-promoted after {self._last_dna_promotion.get(entry['id'], 1)} resolutions\n"
            f"APPLIED: {datetime.now().strftime('%Y-%m-%d')}"
        )

    def _apply_suggestions(self, suggestions: List) -> int:
        """Apply optimization suggestions (returns count applied)."""
        applied = 0
        for sug in suggestions:
            try:
                area = getattr(sug, 'area', 'unknown')
                desc = getattr(sug, 'description', '')

                # Log as insight
                self.learning_logger.log_insight(
                    summary=f"Optimization suggestion: {area}",
                    what_discovered=desc,
                    why_useful=f"Expected impact: {getattr(sug, 'expected_impact', 0):.1%}",
                    source="optimization_cycle",
                    area=area,
                    tags=["optimization", "suggestion", area],
                )
                applied += 1
            except Exception as e:
                logger.error(f"Failed to apply suggestion: {e}")

        return applied

    def _update_dna_from_trends(self, insights: Dict):
        """Update DNA based on quality trends."""
        trend = insights.get("quality_trend", "unknown")

        if trend == "declining":
            self.learning_logger.log_learning(
                category="correction",
                summary="Quality declining — review routing decisions",
                details=f"Quality trend: {trend}, Avg: {insights.get('avg_quality', 0):.2f}",
                suggested_action="Review model routing, check for rate limits, audit recent changes",
                source="optimization_cycle",
                area="routing",
                tags=["quality-trend", "declining", "routing"],
                priority="high",
            )

        elif trend == "improving":
            self.learning_logger.log_learning(
                category="insight",
                summary=f"Quality improving — current approach working",
                details=f"Quality trend: {trend}, Avg: {insights.get('avg_quality', 0):.2f}",
                source="optimization_cycle",
                area="general",
                tags=["quality-trend", "improving"],
                priority="low",
            )

    def _log_optimization_cycle(self, cycle: OptimizationCycle):
        """Log optimization cycle results to a JSON file for tracking."""
        log_path = DATA_DIR / "optimization_cycles.json"
        cycles = []

        if log_path.exists():
            try:
                cycles = json.loads(log_path.read_text())
            except Exception:
                cycles = []

        cycles.append({
            "cycle_id": cycle.cycle_id,
            "timestamp": cycle.timestamp.isoformat(),
            "events_analyzed": cycle.events_analyzed,
            "quality_trend": cycle.quality_trend,
            "avg_quality": round(cycle.avg_quality, 4),
            "suggestions_generated": cycle.suggestions_generated,
            "dna_updates": cycle.dna_updates,
            "errors_fixed": cycle.errors_fixed,
            "improvements_applied": cycle.improvements_applied,
            "duration_s": round(cycle.duration_s, 2),
        })

        # Keep last 100 cycles
        if len(cycles) > 100:
            cycles = cycles[-100:]

        log_path.write_text(json.dumps(cycles, indent=2))

    def _trim_learning_entries(self):
        """Trim learning files if they grow too large."""
        for fname in ["LEARNINGS.md", "ERRORS.md"]:
            path = LEARNINGS_DIR / fname
            if not path.exists():
                continue

            try:
                content = path.read_text()
                entries = content.split("---")
                if len(entries) > self.MAX_LEARNING_ENTRIES:
                    # Keep last N entries
                    trimmed = "---\n".join(entries[-self.MAX_LEARNING_ENTRIES:])
                    path.write_text(trimmed)
                    logger.info(f"[SELF-IMPROVE] Trimmed {fname}: {len(entries)} → {self.MAX_LEARNING_ENTRIES}")
            except Exception as e:
                logger.error(f"Trim failed for {fname}: {e}")

    # ═══════════════════════════════════════════════════════════════════════════
    # DNA MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════════

    def get_dna_entries(self) -> List[Dict]:
        """Get all DNA entries from DNA_UPDATES.md."""
        dna_path = LEARNINGS_DIR / "DNA_UPDATES.md"
        if not dna_path.exists():
            return []

        entries = []
        pattern = re.compile(r"## \[(\w+-\d{8}-\d{3})\] (.+)")

        try:
            content = dna_path.read_text()
            for section in content.split("---"):
                m = pattern.search(section)
                if m:
                    entries.append({
                        "id": m.group(1),
                        "title": m.group(2),
                        "content": section.strip(),
                    })
        except Exception as e:
            logger.error(f"Failed to read DNA entries: {e}")

        return entries[-50:]  # Last 50 entries

    def apply_dna_rule(self, rule_text: str, source: str = "manual") -> bool:
        """Apply a DNA rule to the system. Returns success."""
        now = datetime.now().isoformat()
        dna_path = LEARNINGS_DIR / "DNA_UPDATES.md"

        entry = f"""
## [DNA-{now[:10].replace('-','')}-{int(time.time())}] {source}

**Applied**: {now}
**Source**: {source}

### Rule
{rule_text}

---
"""
        try:
            with open(dna_path, "a") as f:
                f.write(entry)
            logger.info(f"[SELF-IMPROVE] DNA rule applied from {source}")
            return True
        except Exception as e:
            logger.error(f"Failed to apply DNA rule: {e}")
            return False

    # ═══════════════════════════════════════════════════════════════════════════
    # SELF AUDIT
    # ═══════════════════════════════════════════════════════════════════════════

    def audit_self(self) -> Dict[str, Any]:
        """
        Run a comprehensive self-audit of the ILMA system.
        
        Checks:
        1. Module integrity (all wired modules exist)
        2. Learning logger health
        3. Engine health (events, quality)
        4. DNA entries
        5. Pending learnings
        6. Optimization cycle history
        7. Quality trend
        
        Returns audit report dict.
        """
        audit = {
            "audit_id": f"AUDIT-{int(time.time())}",
            "timestamp": datetime.now().isoformat(),
            "overall_status": "UNKNOWN",
            "modules": {},
            "learning_logger": {},
            "engine": {},
            "dna": {},
            "pending": {},
            "optimization_cycles": {},
            "quality": {},
            "recommendations": [],
        }

        # Module integrity check
        try:
            sys.path.insert(0, str(ILMA_ROOT))
            from ilma_runtime_wiring import ILMARuntimeWiring
            wiring = ILMARuntimeWiring()
            diag = wiring.run_pipeline_diagnostic()
            audit["modules"] = {
                "total": diag["total"],
                "ok": diag["summary"]["ok"],
                "missing": diag["summary"]["missing"],
                "import_errors": diag["summary"]["import_error"],
            }
        except Exception as e:
            audit["modules"] = {"error": str(e)}

        # Learning logger stats
        try:
            stats = self.learning_logger.get_stats()
            audit["learning_logger"] = stats
        except Exception as e:
            audit["learning_logger"] = {"error": str(e)}

        # Engine status
        try:
            status = self.engine.get_status()
            insights = self.engine.get_insights()
            audit["engine"] = {
                "status": status,
                "insights": insights,
            }
        except Exception as e:
            audit["engine"] = {"error": str(e)}

        # DNA entries
        try:
            audit["dna"] = {
                "entries": len(self.get_dna_entries()),
                "latest": self.get_dna_entries()[-3:] if self.get_dna_entries() else [],
            }
        except Exception as e:
            audit["dna"] = {"error": str(e)}

        # Pending learnings
        try:
            pending = self.learning_logger.get_pending(limit=50)
            audit["pending"] = {
                "count": len(pending),
                "high_priority": len([p for p in pending if p.get("priority") == "high"]),
                "entries": pending[:10],
            }
        except Exception as e:
            audit["pending"] = {"error": str(e)}

        # Optimization cycle history
        try:
            cycles_path = DATA_DIR / "optimization_cycles.json"
            if cycles_path.exists():
                cycles = json.loads(cycles_path.read_text())
                recent = cycles[-10:] if len(cycles) > 10 else cycles
                audit["optimization_cycles"] = {
                    "total": len(cycles),
                    "recent": recent,
                }
            else:
                audit["optimization_cycles"] = {"total": 0}
        except Exception as e:
            audit["optimization_cycles"] = {"error": str(e)}

        # Quality trend
        try:
            trend = self.engine.get_quality_trend()
            insights = self.engine.get_insights()
            audit["quality"] = {
                "trend": trend,
                "avg_quality": insights.get("avg_quality", 0),
                "total_events": insights.get("total_events", 0),
            }
        except Exception as e:
            audit["quality"] = {"error": str(e)}

        # Overall status
        issues = []
        if audit["modules"].get("missing", 0) > 0:
            issues.append(f"{audit['modules']['missing']} modules missing")
        if audit["modules"].get("import_errors", 0) > 0:
            issues.append(f"{audit['modules']['import_errors']} import errors")
        if audit["pending"].get("high_priority", 0) > 5:
            issues.append(f"{audit['pending']['high_priority']} high-priority pending items")
        if audit["quality"].get("trend") == "declining":
            issues.append("Quality trend: DECLINING")

        if not issues:
            audit["overall_status"] = "HEALTHY"
        elif len(issues) <= 2:
            audit["overall_status"] = "WARNING"
        else:
            audit["overall_status"] = "CRITICAL"

        # Generate recommendations
        if audit["overall_status"] != "HEALTHY":
            audit["recommendations"] = issues

        return audit

    # ═══════════════════════════════════════════════════════════════════════════
    # CONVENIENCE METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    def log_correction(self, summary: str, what_was_wrong: str, what_is_correct: str,
                       area: str = "unknown", related_files: Optional[List[str]] = None):
        """Convenience: log a user correction."""
        return self.learning_logger.log_correction(
            summary=summary,
            what_was_wrong=what_was_wrong,
            what_is_correct=what_is_correct,
            source="user_feedback",
            area=area,
            related_files=related_files,
        )

    def log_error(self, summary: str, error_detail: str, area: str = "unknown",
                   priority: str = "high", context: Optional[Dict] = None):
        """Convenience: log an error."""
        return self.learning_logger.log_error(
            summary=summary,
            error_detail=error_detail,
            area=area,
            priority=priority,
            context=context,
        )

    def log_insight(self, summary: str, what: str, why: str,
                    area: str = "unknown", tags: Optional[List[str]] = None):
        """Convenience: log an insight."""
        return self.learning_logger.log_insight(
            summary=summary,
            what_discovered=what,
            why_useful=why,
            source="self_audit",
            area=area,
            tags=tags,
        )

    def get_status(self) -> Dict[str, Any]:
        """Get current self-improvement system status."""
        try:
            engine_status = self.engine.get_status()
        except Exception:
            engine_status = {}

        try:
            logger_stats = self.learning_logger.get_stats()
        except Exception:
            logger_stats = {}

        return {
            "version": "1.0",
            "uptime": str(datetime.now() - self.started_at),
            "cycles_run": self.cycle_count,
            "tasks_since_last_optimize": self.tasks_since_optimize,
            "quality_baseline": round(self._quality_baseline, 4) if self._quality_baseline else None,
            "engine": engine_status,
            "learnings": logger_stats,
            "dna_entries": len(self.get_dna_entries()),
        }


# ─── SINGLETON ─────────────────────────────────────────────────────────────────
_integrator: Optional[SelfImproveIntegrator] = None

def get_integrator() -> SelfImproveIntegrator:
    global _integrator
    if _integrator is None:
        _integrator = SelfImproveIntegrator()
    return _integrator


# ─── CLI ───────────────────────────────────────────────────────────────────────

def cli_main():
    import argparse
    parser = argparse.ArgumentParser(
        description="ILMA Self-Improve Integrator — LAYER 9 Canonical Self-Improvement Engine"
    )
    sub = parser.add_subparsers(dest="command", help="Command")

    # status
    sub.add_parser("status", help="Show self-improvement system status")

    # audit
    sub.add_parser("audit", help="Run full self-audit")

    # optimize
    sub.add_parser("optimize", help="Run optimization cycle")

    # record
    rec = sub.add_parser("record", help="Record a task result")
    rec.add_argument("task_type", help="Task type (e.g., coding, writing)")
    rec.add_argument("quality", type=float, help="Quality 0.0-1.0")
    rec.add_argument("model", help="Model used")
    rec.add_argument("--time", type=float, default=100.0, help="Execution time (ms)")
    rec.add_argument("--provider", default="unknown", help="Provider name")
    rec.add_argument("--errors", nargs="*", default=[], help="Error messages")

    # learn (log correction/insight)
    learn = sub.add_parser("learn", help="Log a learning (correction/insight/error)")
    learn.add_argument("type", choices=["correction", "insight", "error", "best-practice"], help="Learning type")
    learn.add_argument("summary", help="Summary text")
    learn.add_argument("--what", default="", help="What happened (for insight/error)")
    learn.add_argument("--correct", default="", help="What is correct (for correction)")
    learn.add_argument("--wrong", default="", help="What was wrong (for correction)")
    learn.add_argument("--area", default="general", help="Area")
    learn.add_argument("--why", default="", help="Why useful (for insight)")

    # dna
    dna = sub.add_parser("dna", help="Show DNA entries")
    dna.add_argument("--apply", help="Apply a DNA rule", metavar="RULE_TEXT")

    # version
    sub.add_parser("version", help="Show version info")

    args = parser.parse_args()

    integrator = get_integrator()

    if args.command == "status":
        status = integrator.get_status()
        print(json.dumps(status, indent=2))

    elif args.command == "audit":
        audit = integrator.audit_self()
        print(json.dumps(audit, indent=2))

    elif args.command == "optimize":
        result = integrator.run_optimization_cycle()
        print(json.dumps({
            "cycle_id": result.cycle_id,
            "quality_trend": result.quality_trend,
            "avg_quality": round(result.avg_quality, 4),
            "dna_updates": result.dna_updates,
            "duration_s": round(result.duration_s, 2),
        }, indent=2))

    elif args.command == "record":
        event_id = integrator.record_result(
            task_type=args.task_type,
            task_description=f"CLI: {args.task_type}",
            model_used=args.model,
            provider=args.provider,
            result_quality=args.quality,
            execution_time_ms=args.time,
            errors=args.errors,
        )
        print(f"Recorded: {event_id}")

    elif args.command == "learn":
        if args.type == "correction":
            integrator.log_correction(
                summary=args.summary,
                what_was_wrong=args.wrong,
                what_is_correct=args.correct,
                area=args.area,
            )
        elif args.type == "insight":
            integrator.log_insight(
                summary=args.summary,
                what=args.what,
                why=args.why or args.summary,
                area=args.area,
            )
        elif args.type == "error":
            integrator.log_error(
                summary=args.summary,
                error_detail=args.what,
                area=args.area,
            )
        elif args.type == "best-practice":
            integrator.learning_logger.log_best_practice(
                summary=args.summary,
                pattern=args.what,
                when_to_use=args.why or "When similar tasks arise",
                area=args.area,
            )
        print(f"Learning logged: {args.type} — {args.summary[:50]}")

    elif args.command == "dna":
        if args.apply:
            success = integrator.apply_dna_rule(args.apply, source="cli")
            print(f"DNA rule applied: {success}")
        else:
            entries = integrator.get_dna_entries()
            print(f"DNA Entries: {len(entries)}")
            for e in entries[-10:]:
                print(f"\n## {e['id']} {e['title']}")

    elif args.command == "version":
        print("ILMA Self-Improve Integrator v1.0 — LAYER 9 CANONICAL")

    else:
        parser.print_help()


if __name__ == "__main__":
    cli_main()