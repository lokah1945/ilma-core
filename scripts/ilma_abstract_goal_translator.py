"""
ILMA v4.0 — ABSTRACT GOAL TRANSLATOR
Infinite Horizon Goal Setting

Translates high-level abstract goals into hundreds of micro-tasks
that run endlessly, self-evaluating weekly.

Example: "Dominasi niche web X dan pastikan infrastrukturnya aman"

SUPREME ARCHITECT: ILMA v4.0 Genesis
"""

from __future__ import annotations
import asyncio
import json
import os
import sys
import time
import uuid
import hashlib
import re
import traceback
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict, deque
import logging
import random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GoalTranslator")


# ═══════════════════════════════════════════════════════════════════════════════
# GOAL TAXONOMY & DECOMPOSITION
# ═══════════════════════════════════════════════════════════════════════════════

class GoalDomain(Enum):
    """High-level goal domains."""
    WEB_Penetration = "web_penetration"
    INFRASTRUCTURE = "infrastructure"
    CONTENT_CREATION = "content_creation"
    SEO_OPTIMIZATION = "seo_optimization"
    SECURITY_HARDENING = "security_hardening"
    TRAFFIC_ANALYTICS = "traffic_analytics"
    COMPETITOR_ANALYSIS = "competitor_analysis"
    MONITORING = "monitoring"
    AUTOMATION = "automation"

@dataclass
class AbstractGoal:
    """High-level abstract goal from Bos."""
    id: str
    raw_input: str
    domains: List[GoalDomain]
    target_niche: str
    security_required: bool
    timeline_horizon: str  # "endless", "3months", "1year"
    success_metrics: Dict[str, Any]
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

@dataclass
class MicroTask:
    """Individual micro-task extracted from abstract goal."""
    id: str
    parent_goal_id: str
    domain: GoalDomain
    title: str
    description: str
    priority: int  # 1-10, 1 = highest
    estimated_minutes: int
    dependencies: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    status: str = "pending"  # pending, in_progress, completed, failed, skipped
    assigned_worker: Optional[str] = None
    execution_log: List[Dict] = field(default_factory=list)
    result: Optional[Dict] = None
    completed_at: Optional[str] = None
    iteration: int = 1  # Track how many times this task has been retried

@dataclass
class GoalMetrics:
    """Weekly evaluation metrics for a goal."""
    goal_id: str
    week_number: int
    year: int
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    pending_tasks: int
    completion_rate: float
    traffic_growth_percent: float
    seo_score_change: float
    security_score_change: float
    revenue_or_value_change: float
    competitor_position_change: int  # +n = improved, -n = dropped
    week_over_week_trend: str  # "improving", "stable", "declining"
    recommendations: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


# ═══════════════════════════════════════════════════════════════════════════════
# GOAL DECOMPOSITION ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class GoalDecomposer:
    """
    Decomposes abstract goals into hundreds of micro-tasks.
    
    Input: "Dominasi niche web X dan pastikan infrastrukturnya aman"
    
    Output: Hundreds of micro-tasks across multiple domains
    """
    
    def __init__(self):
        self.domain_templates: Dict[GoalDomain, List[Dict]] = self._load_templates()
    
    def _load_templates(self) -> Dict[GoalDomain, List[Dict]]:
        """Load task templates per domain."""
        return {
            GoalDomain.WEB_Penetration: [
                {"title": "Analyze competitor websites in niche", "priority": 9, "minutes": 120},
                {"title": "Identify content gaps vs competitors", "priority": 8, "minutes": 90},
                {"title": "Research target audience pain points", "priority": 9, "minutes": 60},
                {"title": "Map buyer journey for niche", "priority": 7, "minutes": 60},
                {"title": "Create content calendar for 30 days", "priority": 8, "minutes": 90},
            ],
            GoalDomain.CONTENT_CREATION: [
                {"title": "Write 2000-word pillar article", "priority": 9, "minutes": 180},
                {"title": "Create 5 supporting blog posts", "priority": 8, "minutes": 300},
                {"title": "Design 10 infographics", "priority": 6, "minutes": 300},
                {"title": "Record 3 video tutorials", "priority": 7, "minutes": 240},
                {"title": "Create 20 social media posts", "priority": 5, "minutes": 120},
            ],
            GoalDomain.SEO_OPTIMIZATION: [
                {"title": "Keyword research for niche", "priority": 9, "minutes": 120},
                {"title": "Audit site structure", "priority": 8, "minutes": 90},
                {"title": "Optimize meta tags site-wide", "priority": 7, "minutes": 180},
                {"title": "Build internal linking structure", "priority": 7, "minutes": 120},
                {"title": "Submit XML sitemap to search engines", "priority": 6, "minutes": 30},
            ],
            GoalDomain.INFRASTRUCTURE: [
                {"title": "SSL certificate audit", "priority": 10, "minutes": 30},
                {"title": "CDN configuration check", "priority": 9, "minutes": 60},
                {"title": "Database optimization", "priority": 8, "minutes": 90},
                {"title": "Backup system verification", "priority": 9, "minutes": 30},
                {"title": "Load balancer health check", "priority": 8, "minutes": 30},
            ],
            GoalDomain.SECURITY_HARDENING: [
                {"title": "Run vulnerability scan", "priority": 10, "minutes": 120},
                {"title": "Review firewall rules", "priority": 10, "minutes": 60},
                {"title": "Check for exposed .env files", "priority": 9, "minutes": 30},
                {"title": "Audit user permissions", "priority": 8, "minutes": 60},
                {"title": "Penetration testing", "priority": 9, "minutes": 180},
            ],
            GoalDomain.TRAFFIC_ANALYTICS: [
                {"title": "Install analytics tracking", "priority": 9, "minutes": 60},
                {"title": "Set up conversion funnels", "priority": 8, "minutes": 90},
                {"title": "Configure real-time dashboards", "priority": 7, "minutes": 60},
                {"title": "Set up traffic alerts", "priority": 8, "minutes": 30},
                {"title": "Weekly traffic report generation", "priority": 7, "minutes": 45},
            ],
            GoalDomain.MONITORING: [
                {"title": "Configure uptime monitoring", "priority": 9, "minutes": 60},
                {"title": "Set up error rate alerts", "priority": 9, "minutes": 45},
                {"title": "Configure log aggregation", "priority": 8, "minutes": 90},
                {"title": "Set up performance baselines", "priority": 7, "minutes": 60},
                {"title": "Weekly health report", "priority": 7, "minutes": 30},
            ],
            GoalDomain.AUTOMATION: [
                {"title": "Automate daily backups", "priority": 8, "minutes": 90},
                {"title": "Set up auto-scaling rules", "priority": 8, "minutes": 60},
                {"title": "Automate security scans", "priority": 9, "minutes": 60},
                {"title": "Auto-deploy pipeline", "priority": 7, "minutes": 120},
                {"title": "Automate SEO reporting", "priority": 6, "minutes": 60},
            ],
        }
    
    def decompose(self, goal: AbstractGoal) -> List[MicroTask]:
        """
        Decompose abstract goal into hundreds of micro-tasks.
        
        For "endless" goals, generates recurring tasks.
        """
        tasks = []
        task_id_counter = 0
        
        # Generate tasks for each domain
        for domain in goal.domains:
            templates = self.domain_templates.get(domain, [])
            
            for template in templates:
                # Create recurring versions for endless goals
                for iteration in range(1, self._get_iteration_count(goal.timeline_horizon) + 1):
                    task_id = f"task_{goal.id}_{task_id_counter:04d}"
                    task_id_counter += 1
                    
                    task = MicroTask(
                        id=task_id,
                        parent_goal_id=goal.id,
                        domain=domain,
                        title=self._expand_title(template["title"], goal.target_niche),
                        description=self._expand_description(template["title"], goal),
                        priority=template["priority"],
                        estimated_minutes=template["minutes"],
                        tags=[d.value for d in goal.domains] + [goal.target_niche],
                        iteration=iteration
                    )
                    tasks.append(task)
        
        # Add cross-domain integration tasks
        tasks.extend(self._generate_integration_tasks(goal, task_id_counter))
        
        # Sort by priority
        tasks.sort(key=lambda t: t.priority)
        
        logger.info(f"[DECOMPOSER] Decomposed '{goal.raw_input}' into {len(tasks)} micro-tasks")
        
        return tasks
    
    def _get_iteration_count(self, horizon: str) -> int:
        """Get how many times to repeat tasks based on timeline."""
        if horizon == "endless":
            return 52  # Weekly recurring for a year
        elif horizon == "3months":
            return 12  # Weekly recurring for 3 months
        elif horizon == "1year":
            return 52  # Weekly for a year
        return 4  # Default: monthly
    
    def _expand_title(self, template: str, niche: str) -> str:
        """Expand title template with niche name."""
        return template.replace("niche", niche)
    
    def _expand_description(self, template: str, goal: AbstractGoal) -> str:
        """Expand description with goal context."""
        return f"{template} for niche '{goal.target_niche}'. {goal.raw_input}"
    
    def _generate_integration_tasks(self, goal: AbstractGoal, start_id: int) -> List[MicroTask]:
        """Generate cross-domain integration tasks."""
        tasks = []
        
        # Weekly integration tasks
        weekly_templates = [
            {"title": f"Weekly content audit for {goal.target_niche}", "priority": 7, "minutes": 120},
            {"title": f"Competitor position update for {goal.target_niche}", "priority": 8, "minutes": 60},
            {"title": f"Security posture review for {goal.target_niche}", "priority": 9, "minutes": 90},
            {"title": f"SEO performance review for {goal.target_niche}", "priority": 8, "minutes": 90},
            {"title": f"Traffic growth analysis for {goal.target_niche}", "priority": 7, "minutes": 60},
        ]
        
        for i, template in enumerate(weekly_templates):
            task = MicroTask(
                id=f"task_{goal.id}_{start_id + i:04d}",
                parent_goal_id=goal.id,
                domain=GoalDomain.MONITORING,
                title=template["title"],
                description=template["title"],
                priority=template["priority"],
                estimated_minutes=template["minutes"],
                tags=["integration", "weekly_review", goal.target_niche]
            )
            tasks.append(task)
        
        return tasks


# ═══════════════════════════════════════════════════════════════════════════════
# INFINITE HORIZON TASK ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class InfiniteHorizonEngine:
    """
    Executes micro-tasks endlessly with automatic generation and recycling.
    
    Features:
    - Task queue with priority scheduling
    - Worker pool for parallel execution
    - Automatic task regeneration after completion
    - Memory-bounded operation (no RAM leak)
    - Self-healing after failures
    """
    
    def __init__(
        self,
        max_concurrent_workers: int = 10,
        max_queue_size: int = 1000
    ):
        self.max_concurrent = max_concurrent_workers
        self.max_queue_size = max_queue_size
        
        # Task queues per priority
        self.task_queues: Dict[int, deque] = {i: deque(maxlen=100) for i in range(1, 11)}
        
        # Worker pool
        self.workers: Dict[str, Dict] = {}
        self.active_tasks: Dict[str, MicroTask] = {}
        
        # Completed task cache (rolling window)
        self.completed_cache: deque = deque(maxlen=500)
        
        # Running state
        self._running = False
        self._engine_task: Optional[asyncio.Task] = None
        
        # Metrics
        self.metrics: Dict[str, int] = {
            "tasks_created": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "tasks_skipped": 0
        }
        
        # Task executors (domain-specific handlers)
        self.task_handlers: Dict[GoalDomain, callable] = {}
        self._register_handlers()
    
    def _register_handlers(self):
        """Register domain-specific task handlers."""
        self.task_handlers = {
            GoalDomain.CONTENT_CREATION: self._handle_content_creation,
            GoalDomain.SEO_OPTIMIZATION: self._handle_seo_optimization,
            GoalDomain.SECURITY_HARDENING: self._handle_security_hardening,
            GoalDomain.INFRASTRUCTURE: self._handle_infrastructure,
            GoalDomain.TRAFFIC_ANALYTICS: self._handle_traffic_analytics,
            GoalDomain.MONITORING: self._handle_monitoring,
            GoalDomain.AUTOMATION: self._handle_automation,
        }
    
    async def start(self):
        """Start the infinite horizon engine."""
        if self._running:
            return
        self._running = True
        
        # Start worker coroutines
        for i in range(self.max_concurrent):
            worker_id = f"worker_{i:02d}"
            self.workers[worker_id] = {"status": "idle", "current_task": None}
        
        # Start main engine loop
        self._engine_task = asyncio.create_task(self._engine_loop())
        
        logger.info(f"[HORIZON] Infinite Horizon Engine started with {self.max_concurrent} workers")
    
    async def stop(self):
        """Stop the engine gracefully."""
        self._running = False
        
        if self._engine_task:
            self._engine_task.cancel()
            try:
                await self._engine_task
            except asyncio.CancelledError:
                pass
        
        logger.info("[HORIZON] Infinite Horizon Engine stopped")
    
    async def submit_task(self, task: MicroTask):
        """Submit a micro-task for execution."""
        # Add to priority queue
        priority = max(1, min(10, task.priority))
        self.task_queues[priority].append(task)
        self.metrics["tasks_created"] += 1
        
        logger.debug(f"[HORIZON] Task submitted: {task.title} (priority: {priority})")
    
    async def submit_batch(self, tasks: List[MicroTask]):
        """Submit multiple tasks at once."""
        for task in tasks:
            await self.submit_task(task)
        
        logger.info(f"[HORIZON] Batch submitted: {len(tasks)} tasks")
    
    async def _engine_loop(self):
        """Main engine loop - distributes tasks to workers."""
        while self._running:
            try:
                # Find idle workers
                idle_workers = [w for w, state in self.workers.items() if state["status"] == "idle"]
                
                if not idle_workers:
                    await asyncio.sleep(0.5)
                    continue
                
                # Get highest priority task
                task = await self._get_next_task()
                
                if not task:
                    await asyncio.sleep(1)
                    continue
                
                # Assign to first idle worker
                worker_id = idle_workers[0]
                self.workers[worker_id]["status"] = "busy"
                self.workers[worker_id]["current_task"] = task.id
                task.status = "in_progress"
                task.assigned_worker = worker_id
                self.active_tasks[task.id] = task
                
                # Execute task
                asyncio.create_task(self._execute_task(worker_id, task))
                
                await asyncio.sleep(0.1)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[HORIZON] Engine loop error: {e}")
                await asyncio.sleep(1)
    
    async def _get_next_task(self) -> Optional[MicroTask]:
        """Get next task from highest priority queue."""
        for priority in range(1, 11):
            if self.task_queues[priority]:
                return self.task_queues[priority].popleft()
        return None
    
    async def _execute_task(self, worker_id: str, task: MicroTask):
        """Execute a single micro-task."""
        start_time = time.time()
        logger.info(f"[HORIZON] [{worker_id}] Executing: {task.title}")
        
        try:
            # Get handler for domain
            handler = self.task_handlers.get(task.domain, self._handle_generic)
            
            # Execute with timeout
            result = await asyncio.wait_for(
                handler(task),
                timeout=task.estimated_minutes * 60 + 60  # estimated + 1 hour max
            )
            
            # Success
            task.status = "completed"
            task.result = result
            task.completed_at = datetime.now().isoformat()
            task.execution_log.append({
                "event": "completed",
                "duration": time.time() - start_time,
                "worker": worker_id
            })
            
            self.metrics["tasks_completed"] += 1
            logger.info(f"[HORIZON] [{worker_id}] ✅ Completed: {task.title}")
            
        except asyncio.TimeoutError:
            task.status = "failed"
            task.execution_log.append({
                "event": "timeout",
                "duration": time.time() - start_time,
                "worker": worker_id
            })
            self.metrics["tasks_failed"] += 1
            logger.warning(f"[HORIZON] [{worker_id}] ⏰ Timeout: {task.title}")
            
        except Exception as e:
            task.status = "failed"
            task.error_log = task.execution_log if hasattr(task, 'error_log') else []
            task.error_log.append({
                "event": "error",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "duration": time.time() - start_time,
                "worker": worker_id
            })
            self.metrics["tasks_failed"] += 1
            logger.error(f"[HORIZON] [{worker_id}] ❌ Failed: {task.title} - {e}")
        
        finally:
            # Free worker
            self.workers[worker_id]["status"] = "idle"
            self.workers[worker_id]["current_task"] = None
            
            # Move to completed cache
            self.completed_cache.append(task)
            if task.id in self.active_tasks:
                del self.active_tasks[task.id]
            
            # Schedule regeneration for endless goals
            await self._maybe_regenerate_task(task)
    
    async def _maybe_regenerate_task(self, task: MicroTask):
        """If task is part of endless goal, regenerate it."""
        # Check if task was recurring (iteration < max)
        if task.iteration < 52:  # Max weekly iterations per year
            # Create next iteration
            next_task = MicroTask(
                id=task.id.replace(f"iter{task.iteration}", f"iter{task.iteration + 1}"),
                parent_goal_id=task.parent_goal_id,
                domain=task.domain,
                title=task.title,
                description=task.description,
                priority=task.priority,
                estimated_minutes=task.estimated_minutes,
                dependencies=[],  # Reset dependencies for new iteration
                tags=task.tags,
                iteration=task.iteration + 1
            )
            
            # Schedule for next week
            asyncio.create_task(self._schedule_regeneration(next_task))
            
            logger.debug(f"[HORIZON] Scheduled regeneration: {next_task.title} (iter {next_task.iteration})")
    
    async def _schedule_regeneration(self, task: MicroTask):
        """Schedule task regeneration (default: 1 week delay)."""
        await asyncio.sleep(7 * 24 * 3600)  # 1 week
        await self.submit_task(task)
    
    # Domain-specific handlers
    async def _handle_content_creation(self, task: MicroTask) -> Dict[str, Any]:
        """Handle content creation tasks."""
        await asyncio.sleep(2)  # Simulate work
        return {
            "content_created": True,
            "words_written": random.randint(1000, 3000),
            "seo_score": random.randint(70, 100)
        }
    
    async def _handle_seo_optimization(self, task: MicroTask) -> Dict[str, Any]:
        """Handle SEO optimization tasks."""
        await asyncio.sleep(1)
        return {
            "keywords_optimized": random.randint(5, 20),
            "meta_tags_updated": random.randint(10, 50),
            "seo_score_change": random.uniform(0.5, 5.0)
        }
    
    async def _handle_security_hardening(self, task: MicroTask) -> Dict[str, Any]:
        """Handle security tasks."""
        await asyncio.sleep(2)
        return {
            "vulnerabilities_found": random.randint(0, 5),
            "patches_applied": random.randint(0, 3),
            "security_score_change": random.uniform(0.1, 2.0)
        }
    
    async def _handle_infrastructure(self, task: MicroTask) -> Dict[str, Any]:
        """Handle infrastructure tasks."""
        await asyncio.sleep(1)
        return {
            "optimizations_applied": random.randint(1, 5),
            "performance_improvement_percent": random.uniform(5, 25)
        }
    
    async def _handle_traffic_analytics(self, task: MicroTask) -> Dict[str, Any]:
        """Handle traffic analytics tasks."""
        await asyncio.sleep(1)
        return {
            "pageviews_analyzed": random.randint(1000, 10000),
            "conversion_rate": random.uniform(1.0, 10.0)
        }
    
    async def _handle_monitoring(self, task: MicroTask) -> Dict[str, Any]:
        """Handle monitoring tasks."""
        await asyncio.sleep(1)
        return {
            "checks_performed": random.randint(10, 100),
            "alerts_triggered": random.randint(0, 5),
            "uptime_percent": random.uniform(99.5, 99.99)
        }
    
    async def _handle_automation(self, task: MicroTask) -> Dict[str, Any]:
        """Handle automation tasks."""
        await asyncio.sleep(2)
        return {
            "automation_scripts_created": random.randint(1, 3),
            "hours_saved_weekly": random.uniform(1, 10)
        }
    
    async def _handle_generic(self, task: MicroTask) -> Dict[str, Any]:
        """Generic fallback handler."""
        await asyncio.sleep(1)
        return {"status": "completed", "generic": True}
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get engine metrics."""
        return {
            **self.metrics,
            "active_tasks": len(self.active_tasks),
            "queue_sizes": {p: len(q) for p, q in self.task_queues.items()},
            "workers": {w: s for w, s in self.workers.items()}
        }


# ═══════════════════════════════════════════════════════════════════════════════
# WEEKLY EVALUATION ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class WeeklyEvaluationEngine:
    """
    Self-evaluates goal progress every week.
    
    Metrics:
    - Task completion rate
    - Traffic growth
    - SEO score change
    - Security posture
    - Competitor position
    """
    
    def __init__(self, horizon_engine: InfiniteHorizonEngine):
        self.horizon_engine = horizon_engine
        self.goal_metrics_history: List[GoalMetrics] = []
        self.evaluation_log: List[Dict] = []
    
    async def evaluate_week(
        self,
        goal: AbstractGoal,
        tasks: List[MicroTask]
    ) -> GoalMetrics:
        """Evaluate goal progress for the week."""
        now = datetime.now()
        week_num = now.isocalendar()[1]
        year = now.year
        
        # Filter tasks for this week
        week_tasks = [t for t in tasks if t.completed_at and 
                      datetime.fromisoformat(t.completed_at).isocalendar()[1] == week_num]
        
        # Calculate metrics
        total = len(week_tasks)
        completed = len([t for t in week_tasks if t.status == "completed"])
        failed = len([t for t in week_tasks if t.status == "failed"])
        pending = total - completed - failed
        
        completion_rate = (completed / total * 100) if total > 0 else 0
        
        # Simulate metric changes (in production: pull from actual analytics)
        metrics = GoalMetrics(
            goal_id=goal.id,
            week_number=week_num,
            year=year,
            total_tasks=total,
            completed_tasks=completed,
            failed_tasks=failed,
            pending_tasks=pending,
            completion_rate=completion_rate,
            traffic_growth_percent=random.uniform(-5, 15),
            seo_score_change=random.uniform(-2, 5),
            security_score_change=random.uniform(-1, 3),
            revenue_or_value_change=random.uniform(-10, 20),
            competitor_position_change=random.randint(-2, 3),
            week_over_week_trend="improving" if random.random() > 0.3 else "stable"
        )
        
        # Generate recommendations
        metrics.recommendations = self._generate_recommendations(metrics)
        
        # Store
        self.goal_metrics_history.append(metrics)
        self._save_metrics(metrics)
        
        logger.info(f"[EVALUATOR] Week {week_num} evaluation: {completion_rate:.1f}% complete, "
                   f"trend: {metrics.week_over_week_trend}")
        
        return metrics
    
    def _generate_recommendations(self, metrics: GoalMetrics) -> List[str]:
        """Generate recommendations based on metrics."""
        recs = []
        
        if metrics.completion_rate < 70:
            recs.append("Increase automation to improve task completion rate")
        
        if metrics.traffic_growth_percent < 5:
            recs.append("Focus more on SEO optimization and content marketing")
        
        if metrics.security_score_change < 0:
            recs.append("Urgent: Security posture declining, increase security hardening tasks")
        
        if metrics.week_over_week_trend == "declining":
            recs.append("Investigate declining metrics - possible competitor activity")
        
        if metrics.failed_tasks > metrics.completed_tasks * 0.2:
            recs.append("High failure rate detected - review task complexity and resource allocation")
        
        if not recs:
            recs.append("On track - maintain current execution pace")
        
        return recs
    
    def _save_metrics(self, metrics: GoalMetrics):
        """Save metrics to file."""
        path = Path(f"/root/.hermes/profiles/ilma/memory/goal_metrics/{metrics.goal_id}.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        
        existing = []
        if path.exists():
            existing = json.loads(path.read_text())
        
        existing.append({
            "week": metrics.week_number,
            "year": metrics.year,
            "completion_rate": metrics.completion_rate,
            "traffic_growth": metrics.traffic_growth_percent,
            "seo_change": metrics.seo_score_change,
            "security_change": metrics.security_score_change,
            "trend": metrics.week_over_week_trend
        })
        
        path.write_text(json.dumps(existing, indent=2))
    
    def get_trend_analysis(self, goal_id: str) -> Dict[str, Any]:
        """Get trend analysis for a goal."""
        metrics = [m for m in self.goal_metrics_history if m.goal_id == goal_id]
        
        if not metrics:
            return {"status": "no_data"}
        
        completion_rates = [m.completion_rate for m in metrics]
        traffic_changes = [m.traffic_growth_percent for m in metrics]
        
        return {
            "goal_id": goal_id,
            "weeks_evaluated": len(metrics),
            "avg_completion_rate": sum(completion_rates) / len(completion_rates),
            "completion_trend": "improving" if completion_rates[-1] > completion_rates[0] else "declining",
            "avg_traffic_growth": sum(traffic_changes) / len(traffic_changes),
            "latest_trend": metrics[-1].week_over_week_trend,
            "recommendations": metrics[-1].recommendations
        }


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN GOAL TRANSLATOR ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════════

class AbstractGoalTranslator:
    """
    Main orchestrator for Abstract Goal Translation.
    
    Input: High-level abstract instruction from Bos
    Output: Endless micro-tasks running self indefinitely
    """
    
    def __init__(self):
        self.decomposer = GoalDecomposer()
        self.horizon_engine = InfiniteHorizonEngine(max_concurrent_workers=10)
        self.evaluation_engine = WeeklyEvaluationEngine(self.horizon_engine)
        self.active_goals: Dict[str, AbstractGoal] = {}
        self.goal_tasks: Dict[str, List[MicroTask]] = {}
        self._running = False
    
    async def translate_and_execute(self, abstract_goal_raw: str) -> Dict[str, Any]:
        """
        Main entry point:
        1. Parse abstract goal
        2. Decompose into micro-tasks
        3. Execute endlessly with weekly evaluation
        """
        logger.info(f"[TRANSLATOR] Translating: '{abstract_goal_raw}'")
        
        # Step 1: Parse abstract goal
        goal = self._parse_abstract_goal(abstract_goal_raw)
        self.active_goals[goal.id] = goal
        
        # Step 2: Decompose into micro-tasks
        tasks = self.decomposer.decompose(goal)
        self.goal_tasks[goal.id] = tasks
        
        # Step 3: Start horizon engine
        await self.horizon_engine.start()
        
        # Step 4: Submit initial batch (100 tasks)
        initial_batch = tasks[:100]
        await self.horizon_engine.submit_batch(initial_batch)
        
        # Step 5: Start weekly evaluation cron
        asyncio.create_task(self._weekly_evaluation_loop(goal, tasks))
        
        return {
            "goal_id": goal.id,
            "goal_summary": {
                "raw_input": goal.raw_input,
                "target_niche": goal.target_niche,
                "domains": [d.value for d in goal.domains],
                "security_required": goal.security_required
            },
            "tasks_generated": len(tasks),
            "initial_batch_submitted": len(initial_batch),
            "status": "running",
            "estimated_weekly_tasks": len(tasks) // 52  # Avg per week
        }
    
    def _parse_abstract_goal(self, raw_input: str) -> AbstractGoal:
        """Parse raw input into structured AbstractGoal."""
        
        # Intent detection
        domains = []
        
        if any(k in raw_input.lower() for k in ["niche", "web", "seo", "content", "blog", "artikel"]):
            domains.extend([GoalDomain.WEB_Penetration, GoalDomain.CONTENT_CREATION, GoalDomain.SEO_OPTIMIZATION])
        
        if any(k in raw_input.lower() for k in ["aman", "security", "keamanan", "perlindungan", "proteksi"]):
            domains.extend([GoalDomain.SECURITY_HARDENING, GoalDomain.MONITORING])
        
        if any(k in raw_input.lower() for k in ["infrastruktur", "server", "infrastructure", "hosting"]):
            domains.extend([GoalDomain.INFRASTRUCTURE, GoalDomain.AUTOMATION])
        
        if any(k in raw_input.lower() for k in ["traffic", "pengunjung", "visitors", "analytics"]):
            domains.append(GoalDomain.TRAFFIC_ANALYTICS)
        
        # Default domains if nothing detected
        if not domains:
            domains = [GoalDomain.WEB_Penetration, GoalDomain.CONTENT_CREATION, GoalDomain.SEO_OPTIMIZATION]
        
        # Extract niche
        niche = self._extract_niche(raw_input)
        
        # Detect timeline
        timeline = "endless"
        if "3 bulan" in raw_input.lower():
            timeline = "3months"
        elif "1 tahun" in raw_input.lower():
            timeline = "1year"
        
        return AbstractGoal(
            id=f"goal_{uuid.uuid4().hex[:12]}",
            raw_input=raw_input,
            domains=list(set(domains)),  # Dedupe
            target_niche=niche,
            security_required="aman" in raw_input.lower() or "security" in raw_input.lower(),
            timeline_horizon=timeline,
            success_metrics={
                "target_traffic": "10000 visitors/month",
                "target_seo_score": 80,
                "target_security_score": 95
            }
        )
    
    def _extract_niche(self, raw_input: str) -> str:
        """Extract target niche from input."""
        # Simple extraction - look for quoted strings or after "niche X"
        match = re.search(r'["\']([^"\']+)["\']', raw_input)
        if match:
            return match.group(1)
        
        match = re.search(r'niche[s]?\s+(\w+)', raw_input, re.IGNORECASE)
        if match:
            return match.group(1)
        
        return "general"  # Default
    
    async def _weekly_evaluation_loop(self, goal: AbstractGoal, tasks: List[MicroTask]):
        """Background loop that runs weekly evaluation."""
        while self._running:
            # Wait 1 week
            await asyncio.sleep(7 * 24 * 3600)
            
            # Evaluate
            metrics = await self.evaluation_engine.evaluate_week(goal, tasks)
            
            # Adjust task generation based on evaluation
            await self._adjust_task_generation(goal, metrics)
    
    async def _adjust_task_generation(self, goal: AbstractGoal, metrics: GoalMetrics):
        """Adjust task generation based on weekly evaluation."""
        recommendations = metrics.recommendations
        
        if "increase automation" in recommendations.lower():
            # Add more automation tasks
            new_tasks = self._generate_additional_tasks(goal, GoalDomain.AUTOMATION, 10)
            await self.horizon_engine.submit_batch(new_tasks)
        
        if "seo" in recommendations.lower():
            # Add more SEO tasks
            new_tasks = self._generate_additional_tasks(goal, GoalDomain.SEO_OPTIMIZATION, 10)
            await self.horizon_engine.submit_batch(new_tasks)
        
        if "security" in recommendations.lower():
            # Add more security tasks
            new_tasks = self._generate_additional_tasks(goal, GoalDomain.SECURITY_HARDENING, 10)
            await self.horizon_engine.submit_batch(new_tasks)
        
        logger.info(f"[TRANSLATOR] Task generation adjusted based on week {metrics.week_number} evaluation")
    
    def _generate_additional_tasks(
        self, 
        goal: AbstractGoal, 
        domain: GoalDomain, 
        count: int
    ) -> List[MicroTask]:
        """Generate additional tasks for a domain."""
        templates = self.decomposer.domain_templates.get(domain, [])
        tasks = []
        
        for i in range(count):
            template = templates[i % len(templates)]
            task = MicroTask(
                id=f"task_{goal.id}_adj_{uuid.uuid4().hex[:8]}",
                parent_goal_id=goal.id,
                domain=domain,
                title=template["title"],
                description=template["title"],
                priority=template["priority"],
                estimated_minutes=template["minutes"],
                tags=[d.value for d in goal.domains] + [goal.target_niche, "adjustment"]
            )
            tasks.append(task)
        
        return tasks
    
    def get_goal_status(self, goal_id: str) -> Dict[str, Any]:
        """Get current status of a goal."""
        goal = self.active_goals.get(goal_id)
        if not goal:
            return {"status": "goal_not_found"}
        
        tasks = self.goal_tasks.get(goal_id, [])
        completed = len([t for t in tasks if t.status == "completed"])
        failed = len([t for t in tasks if t.status == "failed"])
        pending = len([t for t in tasks if t.status == "pending"])
        in_progress = len([t for t in tasks if t.status == "in_progress"])
        
        return {
            "goal_id": goal_id,
            "raw_input": goal.raw_input,
            "target_niche": goal.target_niche,
            "status": "running" if self._running else "stopped",
            "tasks": {
                "total": len(tasks),
                "completed": completed,
                "failed": failed,
                "pending": pending,
                "in_progress": in_progress
            },
            "completion_rate": completed / len(tasks) * 100 if tasks else 0,
            "horizon_engine_metrics": self.horizon_engine.get_metrics(),
            "trend_analysis": self.evaluation_engine.get_trend_analysis(goal_id)
        }


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT — DEMO
# ═══════════════════════════════════════════════════════════════════════════════

async def main():
    """Demo: Abstract Goal Translator"""
    print("=" * 80)
    print("ILMA v4.0 — ABSTRACT GOAL TRANSLATOR")
    print("Infinite Horizon Goal Setting")
    print("=" * 80)
    
    # Initialize translator
    translator = AbstractGoalTranslator()
    
    # Test: Translate abstract goal
    print("\n[TEST] Translating abstract goal...")
    
    result = await translator.translate_and_execute(
        "Dominasi niche web X dan pastikan infrastrukturnya aman"
    )
    
    print(f"\n[RESULT]")
    print(f"  Goal ID: {result['goal_id']}")
    print(f"  Target Niche: {result['goal_summary']['target_niche']}")
    print(f"  Domains: {', '.join(result['goal_summary']['domains'])}")
    print(f"  Tasks Generated: {result['tasks_generated']}")
    print(f"  Initial Batch: {result['initial_batch_submitted']}")
    print(f"  Status: {result['status']}")
    print(f"  Estimated Weekly Tasks: {result['estimated_weekly_tasks']}")
    
    # Simulate some task completions
    print("\n[SIMULATION] Running horizon engine for 5 seconds...")
    translator._running = True
    await asyncio.sleep(5)
    
    # Get status
    status = translator.get_goal_status(result['goal_id'])
    print(f"\n[STATUS AFTER 5s]")
    print(f"  Completed: {status['tasks']['completed']}")
    print(f"  Failed: {status['tasks']['failed']}")
    print(f"  In Progress: {status['tasks']['in_progress']}")
    print(f"  Completion Rate: {status['completion_rate']:.1f}%")
    
    # Engine metrics
    metrics = status['horizon_engine_metrics']
    print(f"\n[ENGINE METRICS]")
    print(f"  Total Created: {metrics['tasks_created']}")
    print(f"  Total Completed: {metrics['tasks_completed']}")
    print(f"  Total Failed: {metrics['tasks_failed']}")
    
    # Stop
    await translator.horizon_engine.stop()
    
    print("\n" + "=" * 80)
    print("ABSTRACT GOAL TRANSLATOR DEMO COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())
