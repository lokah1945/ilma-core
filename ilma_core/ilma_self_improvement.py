#!/usr/bin/env python3
"""
ILMA Self-Improvement Engine — Evidence-Based Learning
=====================================================
Continuous self-improvement with evidence tracking.

Inspired by AYDA's self-optimization loops.
Tracks: learning events, optimization cycles, quality metrics.

Usage:
    from ilma_self_improvement import SelfImprovementEngine
    
    engine = SelfImprovementEngine()
    engine.record_event(task, result, quality)
    insights = engine.get_insights()
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class LearningEvent:
    event_id: str
    timestamp: datetime
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


@dataclass
class OptimizationSuggestion:
    suggestion_id: str
    timestamp: datetime
    area: str
    description: str
    expected_impact: float
    status: str = "pending"  # pending, accepted, rejected, implemented
    implemented_at: Optional[datetime] = None


class SelfImprovementEngine:
    """
    Evidence-based self-improvement engine for ILMA.
    Inspired by AYDA's autonomous optimization loops.
    """

    def __init__(self, workspace: Optional[Path] = None):
        self.workspace = workspace or Path("/root/.hermes/profiles/ilma")
        self.events: List[LearningEvent] = []
        self.suggestions: List[OptimizationSuggestion] = []
        self.quality_history: List[float] = []
        self.model_usage: Dict[str, int] = defaultdict(int)
        self.task_stats: Dict[str, Dict] = defaultdict(lambda: {
            "count": 0, "quality_sum": 0, "time_sum": 0, "errors": 0
        })

        # Load existing data
        self._load_data()

    def _get_data_path(self) -> Path:
        """Get data file path."""
        return self.workspace / "ilma_model_router_data" / "self_improvement.json"

    def _load_data(self):
        """Load existing learning data."""
        data_path = self._get_data_path()
        if data_path.exists():
            try:
                with open(data_path) as f:
                    data = json.load(f)

                self.events = [
                    LearningEvent(
                        event_id=e["event_id"],
                        timestamp=datetime.fromisoformat(e["timestamp"]),
                        task_type=e["task_type"],
                        task_description=e["task_description"],
                        model_used=e["model_used"],
                        provider=e["provider"],
                        result_quality=e["result_quality"],
                        execution_time_ms=e["execution_time_ms"],
                        errors=e.get("errors", []),
                        improvements=e.get("improvements", []),
                        verified=e.get("verified", False),
                        evidence_ids=e.get("evidence_ids", [])
                    )
                    for e in data.get("events", [])
                ]

                self.suggestions = [
                    OptimizationSuggestion(
                        suggestion_id=s["suggestion_id"],
                        timestamp=datetime.fromisoformat(s["timestamp"]),
                        area=s["area"],
                        description=s["description"],
                        expected_impact=s["expected_impact"],
                        status=s.get("status", "pending"),
                        implemented_at=datetime.fromisoformat(s["implemented_at"])
                        if s.get("implemented_at") else None
                    )
                    for s in data.get("suggestions", [])
                ]

            except Exception:
                pass

    def _save_data(self):
        """Save learning data."""
        data_path = self._get_data_path()
        data_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "events": [
                {
                    "event_id": e.event_id,
                    "timestamp": e.timestamp.isoformat(),
                    "task_type": e.task_type,
                    "task_description": e.task_description,
                    "model_used": e.model_used,
                    "provider": e.provider,
                    "result_quality": e.result_quality,
                    "execution_time_ms": e.execution_time_ms,
                    "errors": e.errors,
                    "improvements": e.improvements,
                    "verified": e.verified,
                    "evidence_ids": e.evidence_ids
                }
                for e in self.events
            ],
            "suggestions": [
                {
                    "suggestion_id": s.suggestion_id,
                    "timestamp": s.timestamp.isoformat(),
                    "area": s.area,
                    "description": s.description,
                    "expected_impact": s.expected_impact,
                    "status": s.status,
                    "implemented_at": s.implemented_at.isoformat() if s.implemented_at else None
                }
                for s in self.suggestions
            ]
        }

        with open(data_path, "w") as f:
            json.dump(data, f, indent=2)

    def record_event(
        self,
        task_type: str,
        task_description: str,
        model_used: str,
        provider: str,
        result_quality: float,
        execution_time_ms: float,
        errors: Optional[List[str]] = None,
        improvements: Optional[List[str]] = None,
        verified: bool = False
    ) -> LearningEvent:
        """Record a learning event."""
        event_id = f"EVT-{len(self.events):05d}-{int(time.time())}"

        event = LearningEvent(
            event_id=event_id,
            timestamp=datetime.now(),
            task_type=task_type,
            task_description=task_description[:200] if len(task_description) > 200 else task_description,
            model_used=model_used,
            provider=provider,
            result_quality=result_quality,
            execution_time_ms=execution_time_ms,
            errors=errors or [],
            improvements=improvements or [],
            verified=verified
        )

        self.events.append(event)
        self.quality_history.append(result_quality)
        self.model_usage[model_used] += 1

        # Update task stats
        stats = self.task_stats[task_type]
        stats["count"] += 1
        stats["quality_sum"] += result_quality
        stats["time_sum"] += execution_time_ms
        if errors:
            stats["errors"] += 1

        # Trim history
        if len(self.quality_history) > 1000:
            self.quality_history = self.quality_history[-1000:]

        self._save_data()
        return event

    def get_average_quality(self, window: Optional[int] = None) -> float:
        """Get average quality over window (default: all)."""
        history = self.quality_history[-window:] if window else self.quality_history
        return sum(history) / len(history) if history else 0.0

    def get_quality_trend(self) -> str:
        """Get quality trend direction."""
        if len(self.quality_history) < 10:
            return "insufficient_data"

        recent = self.quality_history[-10:]
        older = self.quality_history[-20:-10] if len(self.quality_history) >= 20 else self.quality_history[:10]

        recent_avg = sum(recent) / len(recent)
        older_avg = sum(older) / len(older)

        diff = recent_avg - older_avg
        if diff > 0.05:
            return "improving"
        elif diff < -0.05:
            return "declining"
        else:
            return "stable"

    def get_model_performance(self) -> Dict[str, Dict]:
        """Get performance by model."""
        performance = {}

        for event in self.events[-100:]:
            model = event.model_used
            if model not in performance:
                performance[model] = {"count": 0, "quality_sum": 0, "time_sum": 0}

            performance[model]["count"] += 1
            performance[model]["quality_sum"] += event.result_quality
            performance[model]["time_sum"] += event.execution_time_ms

        # Calculate averages
        for model, stats in performance.items():
            n = stats["count"]
            stats["avg_quality"] = stats["quality_sum"] / n if n > 0 else 0
            stats["avg_time_ms"] = stats["time_sum"] / n if n > 0 else 0

        return performance

    def get_best_model_for_task(self, task_type: str) -> Optional[str]:
        """Get best performing model for task type."""
        task_events = [e for e in self.events if e.task_type == task_type]
        if not task_events:
            return None

        # Group by model
        model_scores = defaultdict(lambda: {"count": 0, "quality_sum": 0})
        for event in task_events:
            model_scores[event.model_used]["count"] += 1
            model_scores[event.model_used]["quality_sum"] += event.result_quality

        # Find best
        best_model = None
        best_score = -1

        for model, scores in model_scores.items():
            n = scores["count"]
            avg_quality = scores["quality_sum"] / n if n > 0 else 0
            # Weight by count (prefer more tested)
            combined = avg_quality * min(n / 5, 1.0)
            if combined > best_score:
                best_score = combined
                best_model = model

        return best_model

    def suggest_optimization(self) -> List[OptimizationSuggestion]:
        """Analyze events and suggest optimizations."""
        suggestions = []

        # Check quality trend
        trend = self.get_quality_trend()
        if trend == "declining":
            suggestions.append(OptimizationSuggestion(
                suggestion_id=f"SUG-{len(self.suggestions):03d}",
                timestamp=datetime.now(),
                area="quality",
                description="Quality declining — review recent changes",
                expected_impact=0.3
            ))

        # Check error rate
        recent_events = self.events[-20:]
        if recent_events:
            error_count = sum(1 for e in recent_events if e.errors)
            if error_count > len(recent_events) * 0.2:
                suggestions.append(OptimizationSuggestion(
                    suggestion_id=f"SUG-{len(self.suggestions):03d}",
                    timestamp=datetime.now(),
                    area="reliability",
                    description=f"High error rate ({error_count}/{len(recent_events)}) — add more robust error handling",
                    expected_impact=0.4
                ))

        # Check model diversity
        if len(self.model_usage) < 3:
            suggestions.append(OptimizationSuggestion(
                suggestion_id=f"SUG-{len(self.suggestions):03d}",
                timestamp=datetime.now(),
                area="model_diversity",
                description="Low model diversity — try different models for better results",
                expected_impact=0.2
            ))

        # Check execution time
        recent_times = [e.execution_time_ms for e in recent_events]
        if recent_times:
            avg_time = sum(recent_times) / len(recent_times)
            if avg_time > 2000:
                suggestions.append(OptimizationSuggestion(
                    suggestion_id=f"SUG-{len(self.suggestions):03d}",
                    timestamp=datetime.now(),
                    area="performance",
                    description=f"High avg execution time ({avg_time:.0f}ms) — optimize routing",
                    expected_impact=0.25
                ))

        self.suggestions.extend(suggestions)
        return suggestions

    def get_insights(self) -> Dict[str, Any]:
        """Get comprehensive learning insights."""
        return {
            "total_events": len(self.events),
            "avg_quality": self.get_average_quality(),
            "quality_trend": self.get_quality_trend(),
            "quality_window_100": self.get_average_quality(100),
            "quality_window_50": self.get_average_quality(50),
            "quality_window_20": self.get_average_quality(20),
            "model_usage": dict(self.model_usage),
            "model_performance": self.get_model_performance(),
            "task_stats": {
                k: {
                    "count": v["count"],
                    "avg_quality": v["quality_sum"] / v["count"] if v["count"] > 0 else 0,
                    "avg_time_ms": v["time_sum"] / v["count"] if v["count"] > 0 else 0,
                    "error_rate": v["errors"] / v["count"] if v["count"] > 0 else 0
                }
                for k, v in self.task_stats.items()
            },
            "suggestions_pending": len([s for s in self.suggestions if s.status == "pending"])
        }

    def run_optimization_cycle(self) -> Dict[str, Any]:
        """Run full optimization cycle."""
        cycle_start = datetime.now()

        # Get insights
        insights = self.get_insights()

        # Generate suggestions
        suggestions = self.suggest_optimization()

        cycle_time = (datetime.now() - cycle_start).total_seconds()

        return {
            "cycle_started": cycle_start.isoformat(),
            "cycle_duration_s": cycle_time,
            "events_analyzed": len(self.events),
            "suggestions_generated": len(suggestions),
            "quality_trend": insights["quality_trend"],
            "avg_quality": insights["avg_quality"],
            "top_model": max(self.model_usage.items(), key=lambda x: x[1])[0] if self.model_usage else None,
            "suggestions": [
                {"area": s.area, "description": s.description, "impact": s.expected_impact}
                for s in suggestions
            ]
        }

    def get_status(self) -> Dict[str, Any]:
        """Get system status."""
        return {
            "events_tracked": len(self.events),
            "quality_avg": self.get_average_quality(),
            "quality_trend": self.get_quality_trend(),
            "models_used": len(self.model_usage),
            "suggestions": len(self.suggestions),
            "suggestions_pending": len([s for s in self.suggestions if s.status == "pending"])
        }


# === CLI ===
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ILMA Self-Improvement Engine")
    subparsers = parser.add_subparsers(dest="command", help="Command")

    # status
    subparsers.add_parser("status", help="Show improvement status")

    # insights
    subparsers.add_parser("insights", help="Get learning insights")

    # record
    record_parser = subparsers.add_parser("record", help="Record learning event")
    record_parser.add_argument("task_type", help="Task type")
    record_parser.add_argument("quality", type=float, help="Quality (0-1)")
    record_parser.add_argument("model", help="Model used")
    record_parser.add_argument("--time", type=float, default=100, help="Execution time (ms)")

    # optimize
    subparsers.add_parser("optimize", help="Run optimization cycle")

    args = parser.parse_args()

    engine = SelfImprovementEngine()

    if args.command == "status":
        status = engine.get_status()
        print(json.dumps(status, indent=2))

    elif args.command == "insights":
        insights = engine.get_insights()
        print(json.dumps(insights, indent=2))

    elif args.command == "record":
        event = engine.record_event(
            task_type=args.task_type,
            task_description=f"CLI recorded: {args.task_type}",
            model_used=args.model,
            provider="unknown",
            result_quality=args.quality,
            execution_time_ms=args.time,
            verified=True
        )
        print(f"Event recorded: {event.event_id}")
        print(f"Quality: {event.result_quality:.2f}")

    elif args.command == "optimize":
        result = engine.run_optimization_cycle()
        print(json.dumps(result, indent=2))

    else:
        parser.print_help()