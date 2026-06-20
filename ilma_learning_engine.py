#!/usr/bin/env python3
"""
ILMA Learning Engine
====================
Autonomous learning and knowledge acquisition.
Inspired by AYDA autonomous_learning_engine.py

Version: 2.0
"""

import logging
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class LearningMode(Enum):
    SUPERVISED = "supervised"
    UNSUPERVISED = "unsupervised"
    REINFORCEMENT = "reinforcement"
    EXPLORATORY = "exploratory"


class LearningResourceType(Enum):
    DOCUMENT = "document"
    API = "api"
    CODE = "code"
    VIDEO = "video"
    INTERACTIVE = "interactive"


@dataclass
class LearningResource:
    resource_id: str
    title: str
    resource_type: LearningResourceType
    content: str
    difficulty: float  # 0.0 to 1.0
    estimated_hours: float = 1.0
    prerequisites: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)


@dataclass
class LearningPath:
    path_id: str
    goal: str
    resources: List[LearningResource]
    current_index: int = 0
    completed: bool = False
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class LearningProgress:
    resource_id: str
    comprehension_score: float
    time_spent_minutes: int
    completed_at: datetime = field(default_factory=datetime.utcnow)
    notes: str = ""


@dataclass
class LearningInsight:
    insight_id: str
    content: str
    source_resource: str
    confidence: float
    generated_at: datetime = field(default_factory=datetime.utcnow)


class ILMALearningEngine:
    """
    Autonomous learning and knowledge acquisition system.
    Integrates with ILMA memory, skills, and knowledge graph.
    """
    
    def __init__(self, engine_id: str = "ilma_default"):
        self.engine_id = engine_id
        self.resources: Dict[str, LearningResource] = {}
        self.paths: Dict[str, LearningPath] = {}
        self.progress: Dict[str, List[LearningProgress]] = {}
        self.insights: List[LearningInsight] = []
        self.learning_history: List[str] = []
        self.subscribers: List[Callable] = []
        self.stats = {
            "resources_indexed": 0,
            "paths_created": 0,
            "completions": 0,
            "insights_generated": 0,
        }
        
    def index_resource(
        self,
        title: str,
        resource_type: LearningResourceType,
        content: str,
        difficulty: float = 0.5,
        estimated_hours: float = 1.0,
        prerequisites: List[str] = None
    ) -> str:
        """Index a learning resource."""
        resource_id = f"res_{self.engine_id}_{len(self.resources)}"
        resource = LearningResource(
            resource_id=resource_id,
            title=title,
            resource_type=resource_type,
            content=content,
            difficulty=difficulty,
            estimated_hours=estimated_hours,
            prerequisites=prerequisites or []
        )
        self.resources[resource_id] = resource
        self.stats["resources_indexed"] += 1
        return resource_id
    
    def create_learning_path(
        self,
        goal: str,
        resource_ids: List[str]
    ) -> str:
        """Create a learning path for a goal."""
        path_id = f"path_{self.engine_id}_{len(self.paths)}"
        resources = [self.resources[rid] for rid in resource_ids if rid in self.resources]
        
        path = LearningPath(
            path_id=path_id,
            goal=goal,
            resources=resources
        )
        self.paths[path_id] = path
        self.progress[path_id] = []
        self.stats["paths_created"] += 1
        return path_id
    
    def start_path(self, path_id: str) -> bool:
        """Start executing a learning path."""
        path = self.paths.get(path_id)
        if not path:
            return False
        
        path.started_at = datetime.utcnow()
        path.current_index = 0
        self.learning_history.append(f"Started: {path.goal}")
        return True
    
    def record_progress(
        self,
        path_id: str,
        resource_id: str,
        comprehension: float,
        time_spent_minutes: int,
        notes: str = ""
    ) -> bool:
        """Record progress on a learning resource."""
        path = self.paths.get(path_id)
        if not path:
            return False
        
        progress = LearningProgress(
            resource_id=resource_id,
            comprehension_score=comprehension,
            time_spent_minutes=time_spent_minutes,
            notes=notes
        )
        
        if path_id not in self.progress:
            self.progress[path_id] = []
        self.progress[path_id].append(progress)
        
        # Move to next resource
        if path.current_index < len(path.resources) - 1:
            path.current_index += 1
        else:
            path.completed = True
            path.completed_at = datetime.utcnow()
            self.stats["completions"] += 1
        
        return True
    
    def generate_insight(
        self,
        content: str,
        source_resource: str,
        confidence: float = 0.8
    ) -> str:
        """Generate an insight from learned content."""
        insight_id = f"insight_{len(self.insights)}"
        insight = LearningInsight(
            insight_id=insight_id,
            content=content,
            source_resource=source_resource,
            confidence=confidence
        )
        self.insights.append(insight)
        self.stats["insights_generated"] += 1
        return insight_id
    
    def get_current_resource(self, path_id: str) -> Optional[LearningResource]:
        """Get the current resource in a learning path."""
        path = self.paths.get(path_id)
        if not path or path.current_index >= len(path.resources):
            return None
        return path.resources[path.current_index]
    
    def get_path_progress(self, path_id: str) -> float:
        """Get progress percentage for a path."""
        path = self.paths.get(path_id)
        if not path:
            return 0.0
        return (path.current_index / len(path.resources)) * 100 if path.resources else 0.0
    
    def subscribe(self, callback: Callable):
        """Subscribe to learning events."""
        self.subscribers.append(callback)
    
    def notify_subscribers(self, event: str, data: Dict):
        """Notify all subscribers of an event."""
        for callback in self.subscribers:
            try:
                callback(event, data)
            except Exception:
                pass
    
    def get_stats(self) -> Dict:
        """Get learning engine statistics."""
        return {
            **self.stats,
            "resources_available": len(self.resources),
            "active_paths": len([p for p in self.paths.values() if not p.completed]),
            "total_insights": len(self.insights)
        }
    
    def learn_from_task(self, task_result: Dict) -> Optional[str]:
        """Learn from task execution result."""
        if task_result.get("success"):
            # Generate positive insight
            return self.generate_insight(
                content=f"Task '{task_result.get('task')}' succeeded with pattern: {task_result.get('pattern')}",
                source_resource=f"task:{task_result.get('task')}",
                confidence=0.9
            )
        else:
            # Generate improvement insight
            return self.generate_insight(
                content=f"Task '{task_result.get('task')}' failed: {task_result.get('error')}. Needs: {task_result.get('needs')}",
                source_resource=f"task:{task_result.get('task')}",
                confidence=0.7
            )
    
    def get_recommended_next(self) -> List[str]:
        """Get recommended next learning actions."""
        recommendations = []
        
        for path in self.paths.values():
            if not path.completed:
                current_res = self.get_current_resource(path.path_id)
                if current_res:
                    recommendations.append({
                        "path_id": path.path_id,
                        "goal": path.goal,
                        "next_resource": current_res.title,
                        "difficulty": current_res.difficulty
                    })
        
        return recommendations


if __name__ == "__main__":
    engine = ILMALearningEngine()
    
    # Index resources
    r1 = engine.index_resource(
        "Python Patterns",
        LearningResourceType.CODE,
        "Python design patterns content",
        difficulty=0.6,
        estimated_hours=2.0
    )
    
    r2 = engine.index_resource(
        "Memory Management",
        LearningResourceType.DOCUMENT,
        "Memory management strategies",
        difficulty=0.7,
        estimated_hours=1.5
    )
    
    # Create learning path
    path_id = engine.create_learning_path("Master ILMA Development", [r1, r2])
    
    # Start and progress
    engine.start_path(path_id)
    engine.record_progress(path_id, r1, comprehension=0.85, time_spent_minutes=45)
    
    logger.info("Stats: %s", engine.get_stats())
    logger.info("Current resource: %s", engine.get_current_resource(path_id))


# ─── Module-level API wrappers ───────────────────────────────────────────────

def learn(task: str, context: Optional[dict] = None) -> dict:
    """
    Module-level wrapper: record a learning event.
    Delegates to ILMALearningEngine instance.
    """
    engine = ILMALearningEngine()
    path_id = engine.create_learning_path(
        goal=task[:80],
        resource_ids=[]
    )
    engine.start_path(path_id)
    return {
        "status": "learning_recorded",
        "path_id": path_id,
        "task": task,
        "context": context or {}
    }


def get_learning_stats() -> dict:
    """Module-level wrapper: return learning engine statistics."""
    engine = ILMALearningEngine()
    return engine.get_stats()

_global_learning_engine_instance = None

def get_learning_engine() -> "ILMALearningEngine":
    """Get singleton ILMALearningEngine instance."""
    global _global_learning_engine_instance
    if _global_learning_engine_instance is None:
        _global_learning_engine_instance = ILMALearningEngine()
    return _global_learning_engine_instance

