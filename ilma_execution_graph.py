#!/usr/bin/env python3
"""
ILMA Execution Memory Graph
===========================
Builds and maintains relationships across all execution history.
Inspired by AYDA execution_memory_graph.py

TASK ↔ FILE ↔ DEPENDENCY ↔ PROVIDER ↔ SKILL ↔ RESULT ↔ FAILURE ↔ OPTIMIZATION

Version: 2.0
"""

import json
import logging
import os
import time
from typing import Dict, Any, List, Optional, Set
from pathlib import Path
from collections import defaultdict
from datetime import datetime

logger = logging.getLogger(__name__)


class ExecutionNode:
    """Represents a node in the execution graph."""
    
    def __init__(self, node_id: str, node_type: str, data: Dict[str, Any]):
        self.id = node_id
        self.type = node_type  # task, file, provider, skill, result, failure, optimization
        self.data = data
        self.created_at = time.time()
        self.updated_at = time.time()
        
        # Relationships (edges)
        self.connections: Dict[str, Set[str]] = defaultdict(set)
        # Format: {connection_type: {target_node_ids}}
    
    def add_connection(self, connection_type: str, target_id: str):
        """Add a connection to another node."""
        self.connections[connection_type].add(target_id)
        self.updated_at = time.time()
    
    def get_connections(self, connection_type: Optional[str] = None) -> Set[str]:
        """Get connections, optionally filtered by type."""
        if connection_type:
            return self.connections.get(connection_type, set())
        # Return all connections
        all_conns = set()
        for conns in self.connections.values():
            all_conns.update(conns)
        return all_conns
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "data": self.data,
            "connections": {k: list(v) for k, v in self.connections.items()},
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }


class ExecutionMemoryGraph:
    """
    Maintains a graph of all execution history.
    
    Relationship types:
    - TASK → uses_file → FILE
    - TASK → via_provider → PROVIDER
    - TASK → requires_skill → SKILL
    - TASK → produces_result → RESULT
    - TASK → experienced_failure → FAILURE
    - FAILURE → resolved_by → OPTIMIZATION
    - RESULT → derived_from → TASK
    - FILE → depended_on → FILE
    - TASK → similar_to → TASK
    - PROVIDER → used_for → TASK_TYPE
    """
    
    RELATIONSHIP_TYPES = {
        # Task relationships
        "uses_file", "via_provider", "requires_skill", "produces_result",
        "experienced_failure", "similar_to", "derived_from",
        # File relationships
        "depended_on", "imports", "calls",
        # Provider relationships
        "used_for", "failed_for",
        # Failure relationships
        "resolved_by", "caused_by",
        # Optimization relationships
        "applied_to", "improved_from"
    }
    
    def __init__(self, storage_path: Optional[str] = None,
                 graph_id: str = "ilma_default"):
        """
        Initialize the execution memory graph.
        
        Args:
            storage_path: Path to JSON file for persisting graph state.
                         Defaults to ~/.hermes/profiles/ilma/state/execution_graph.json
            graph_id: Unique identifier for this graph instance.
        """
        self.graph_id = graph_id
        default_path = os.path.join(os.path.expanduser("~"), ".hermes", "profiles", "ilma", "state", "execution_graph.json")
        self.storage_path = Path(storage_path) if storage_path else Path(default_path)
        self.nodes: Dict[str, ExecutionNode] = {}
        
        # Statistics
        self.stats = {
            "total_executions": 0,
            "total_files": 0,
            "total_failures": 0,
            "total_optimizations": 0,
            "relationship_counts": defaultdict(int)
        }
        
        # Load existing graph
        self._load()
    
    def _load(self):
        """Load graph from storage."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path) as f:
                    data = json.load(f)
                
                # Restore nodes
                for node_id, node_data in data.get("nodes", {}).items():
                    self.nodes[node_id] = ExecutionNode(
                        node_id=node_data["id"],
                        node_type=node_data["type"],
                        data=node_data["data"]
                    )
                    # Restore connections
                    for conn_type, targets in node_data.get("connections", {}).items():
                        for target in targets:
                            self.nodes[node_id].add_connection(conn_type, target)
                
                # Restore stats
                saved_stats = data.get("stats", {})
                self.stats["total_executions"] = saved_stats.get("total_executions", 0)
                self.stats["total_files"] = saved_stats.get("total_files", 0)
                self.stats["total_failures"] = saved_stats.get("total_failures", 0)
                self.stats["total_optimizations"] = saved_stats.get("total_optimizations", 0)
                
            except Exception as e:
                logger.warning("Graph load error: %s", e)
    
    def _save(self):
        """Persist graph to storage."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, 'w') as f:
                json.dump({
                    "graph_id": self.graph_id,
                    "nodes": {nid: node.to_dict() for nid, node in self.nodes.items()},
                    "stats": {
                        "total_executions": self.stats["total_executions"],
                        "total_files": self.stats["total_files"],
                        "total_failures": self.stats["total_failures"],
                        "total_optimizations": self.stats["total_optimizations"],
                        "relationship_counts": dict(self.stats["relationship_counts"])
                    },
                    "last_updated": datetime.now().isoformat()
                }, f, indent=2)
        except Exception as e:
            logger.warning("Graph save error: %s", e)
    
    def create_node(self, node_type: str, data: Dict[str, Any]) -> str:
        """
        Create a new node in the graph.
        
        Args:
            node_type: Type of node (task, file, provider, skill, result, failure, optimization)
            data: Dictionary of node data
            
        Returns:
            The ID of the created node
        """
        node_id = f"{node_type}_{self.graph_id}_{len(self.nodes)}"
        node = ExecutionNode(node_id, node_type, data)
        self.nodes[node_id] = node
        
        # Update stats
        if node_type == "task":
            self.stats["total_executions"] += 1
        elif node_type == "file":
            self.stats["total_files"] += 1
        elif node_type == "failure":
            self.stats["total_failures"] += 1
        elif node_type == "optimization":
            self.stats["total_optimizations"] += 1
        
        self._save()
        return node_id
    
    def add_connection(self, source_id: str, target_id: str, 
                      connection_type: str) -> bool:
        """
        Add a connection between nodes.
        
        Args:
            source_id: ID of the source node
            target_id: ID of the target node
            connection_type: Type of relationship (e.g., 'uses_file', 'via_provider')
            
        Returns:
            True if connection was added, False if source or target not found
        """
        if source_id not in self.nodes or target_id not in self.nodes:
            return False
        
        if connection_type not in self.RELATIONSHIP_TYPES:
            # Auto-add new relationship type
            self.RELATIONSHIP_TYPES.add(connection_type)
        
        self.nodes[source_id].add_connection(connection_type, target_id)
        self.stats["relationship_counts"][connection_type] += 1
        self._save()
        return True
    
    def get_node(self, node_id: str) -> Optional[ExecutionNode]:
        """Get a node by ID."""
        return self.nodes.get(node_id)
    
    def query_by_type(self, node_type: str) -> List[ExecutionNode]:
        """Get all nodes of a specific type."""
        return [n for n in self.nodes.values() if n.type == node_type]
    
    def query_by_connection(self, node_id: str, 
                           connection_type: Optional[str] = None) -> List[ExecutionNode]:
        """
        Get nodes connected to the specified node.
        
        Args:
            node_id: ID of the node to query
            connection_type: Optional filter for connection type
            
        Returns:
            List of connected ExecutionNodes
        """
        node = self.nodes.get(node_id)
        if not node:
            return []
        
        connected_ids = node.get_connections(connection_type)
        return [self.nodes[nid] for nid in connected_ids if nid in self.nodes]
    
    def find_related_tasks(self, task_id: str, max_depth: int = 2) -> List[str]:
        """
        Find tasks related to a given task by traversing connections.
        
        Args:
            task_id: ID of the task to find relations for
            max_depth: Maximum depth to traverse (default 2)
            
        Returns:
            List of related task IDs
        """
        related = set()
        current_level = {task_id}
        
        for _ in range(max_depth):
            next_level = set()
            for nid in current_level:
                node = self.nodes.get(nid)
                if node:
                    for conn_type, targets in node.connections.items():
                        for target_id in targets:
                            target = self.nodes.get(target_id)
                            if target and target.type == "task":
                                related.add(target_id)
                            next_level.add(target_id)
            current_level = next_level
        
        return list(related)
    
    def record_execution(self, task: str, provider: str, model: str,
                       success: bool, result: Any = None,
                       files_used: List[str] = None,
                       skills_used: List[str] = None) -> str:
        """
        Record a complete execution in the graph.
        
        Creates task node, provider node, result/failure node, and all relationships.
        
        Args:
            task: Description of the task executed
            provider: Provider name (e.g., 'minimax', 'nvidia')
            model: Model name used
            success: Whether execution succeeded
            result: Result or error message
            files_used: List of file paths used
            skills_used: List of skill names used
            
        Returns:
            The ID of the created task node
        """
        # Create task node
        task_data = {
            "task": task,
            "provider": provider,
            "model": model,
            "success": success,
            "timestamp": datetime.now().isoformat()
        }
        task_node_id = self.create_node("task", task_data)
        
        # Create provider node if not exists
        provider_node_id = f"provider_{provider}"
        if provider_node_id not in self.nodes:
            self.create_node("provider", {"name": provider, "model": model})
        
        # Create result/failure node
        if success:
            result_node_id = self.create_node("result", {"result": str(result)[:500] if result else "success"})
            self.add_connection(task_node_id, result_node_id, "produces_result")
        else:
            failure_data = {"task": task, "error": str(result)[:500] if result else "unknown"}
            failure_node_id = self.create_node("failure", failure_data)
            self.add_connection(task_node_id, failure_node_id, "experienced_failure")
        
        # Add relationships
        self.add_connection(task_node_id, provider_node_id, "via_provider")
        
        # File relationships
        for f in (files_used or []):
            file_node_id = f"file_{hash(f) % 1000000}"
            if file_node_id not in self.nodes:
                self.create_node("file", {"path": f})
            self.add_connection(task_node_id, file_node_id, "uses_file")
        
        # Skill relationships
        for s in (skills_used or []):
            skill_node_id = f"skill_{s}"
            if skill_node_id not in self.nodes:
                self.create_node("skill", {"name": s})
            self.add_connection(task_node_id, skill_node_id, "requires_skill")
        
        return task_node_id
    
    def get_stats(self) -> Dict[str, Any]:
        """Get graph statistics."""
        return {
            **self.stats,
            "total_nodes": len(self.nodes),
            "node_types": {
                ntype: len(self.query_by_type(ntype))
                for ntype in ["task", "file", "provider", "skill", "result", "failure"]
            }
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    graph = ExecutionMemoryGraph(graph_id="test")
    
    # Record some executions
    id1 = graph.record_execution(
        "Fix bug in login", "minimax", "MiniMax-M2-7",
        success=True, result="Bug fixed",
        skills_used=["debug", "python"]
    )
    
    id2 = graph.record_execution(
        "Write API endpoint", "nvidia", "llama-3.1",
        success=False, result="Syntax error",
        skills_used=["fastapi", "python"]
    )
    
    logger.info("Task 1: %s", id1)
    logger.info("Task 2: %s", id2)
    
    # Find related tasks
    related = graph.find_related_tasks(id1)
    logger.info("Related to task 1: %s", related)
    
    logger.info("Stats: %s", graph.get_stats())

# Backward-compatibility alias
ExecutionGraph = ExecutionMemoryGraph

_global_execution_graph_instance = None

def get_execution_graph() -> "ExecutionMemoryGraph":
    """Get singleton ExecutionMemoryGraph instance."""
    global _global_execution_graph_instance
    if _global_execution_graph_instance is None:
        _global_execution_graph_instance = ExecutionMemoryGraph()
    return _global_execution_graph_instance

