#!/usr/bin/env python3
"""
ILMA Knowledge Graph OS
=======================
Graph-based knowledge management system.
Inspired by AYDA knowledge_graph_os.py

Version: 2.0
"""

import logging
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class NodeType(Enum):
    ENTITY = "entity"
    CONCEPT = "concept"
    EVENT = "event"
    DOCUMENT = "document"
    AGENT = "agent"
    SKILL = "skill"
    MEMORY = "memory"


class EdgeType(Enum):
    RELATES_TO = "relates_to"
    DEPENDS_ON = "depends_on"
    PRECEDES = "precedes"
    DERIVES_FROM = "derives_from"
    REFERENCES = "references"
    LEARNS_FROM = "learns_from"
    IMPROVES = "improves"


@dataclass
class KGNode:
    node_id: str
    node_type: NodeType
    label: str
    properties: Dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict = field(default_factory=dict)


@dataclass
class KGEdge:
    edge_id: str
    source_id: str
    target_id: str
    edge_type: EdgeType
    weight: float = 1.0
    properties: Dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class KGQuery:
    start_node: str = None
    end_node: str = None
    edge_types: List[EdgeType] = None
    node_types: List[NodeType] = None
    max_depth: int = 3
    limit: int = 100


@dataclass
class KGQueryResult:
    nodes: List[KGNode]
    edges: List[KGEdge]
    paths: List[List[str]] = field(default_factory=list)
    query_time_ms: float = 0.0


class KnowledgeGraphOS:
    """
    Operating system for knowledge graph management and querying.
    Integrates with ILMA memory and skills system.
    """
    
    def __init__(self, os_id: str = "ilma_default"):
        self.os_id = os_id
        self.nodes: Dict[str, KGNode] = {}
        self.edges: Dict[str, KGEdge] = {}
        self.node_index: Dict[Tuple[str, str], List[str]] = {}
        self.edge_index: Dict[Tuple[str, str], List[str]] = {}
        self.subscribers: List[Callable] = []
        self.stats = {
            "nodes_created": 0,
            "edges_created": 0,
            "queries_executed": 0,
            "paths_found": 0,
        }
        
    def create_node(
        self,
        label: str,
        node_type: NodeType,
        properties: Dict = None
    ) -> str:
        """Create a node in the knowledge graph."""
        node_id = f"node_{self.os_id}_{len(self.nodes)}"
        node = KGNode(
            node_id=node_id,
            node_type=node_type,
            label=label,
            properties=properties or {}
        )
        
        self.nodes[node_id] = node
        self.stats["nodes_created"] += 1
        
        # Update index
        index_key = (node_type.value, label.lower())
        if index_key not in self.node_index:
            self.node_index[index_key] = []
        self.node_index[index_key].append(node_id)
        
        return node_id
    
    def create_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: EdgeType,
        weight: float = 1.0,
        properties: Dict = None
    ) -> Optional[str]:
        """Create an edge in the knowledge graph."""
        if source_id not in self.nodes or target_id not in self.nodes:
            return None
            
        edge_id = f"edge_{self.os_id}_{len(self.edges)}"
        edge = KGEdge(
            edge_id=edge_id,
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
            weight=weight,
            properties=properties or {}
        )
        
        self.edges[edge_id] = edge
        self.stats["edges_created"] += 1
        
        # Update edge index
        index_key = (source_id, edge_type.value)
        if index_key not in self.edge_index:
            self.edge_index[index_key] = []
        self.edge_index[index_key].append(edge_id)
        
        return edge_id
    
    def query(self, query: KGQuery) -> KGQueryResult:
        """Query the knowledge graph."""
        start_time = datetime.utcnow()
        result_nodes = []
        result_edges = []
        paths = []
        
        # Filter by node types
        if query.node_types:
            for node in self.nodes.values():
                if node.node_type in query.node_types:
                    result_nodes.append(node)
        
        # Filter by edge types
        if query.edge_types:
            for edge in self.edges.values():
                if edge.edge_type in query.edge_types:
                    result_edges.append(edge)
        
        # Limit results
        result_nodes = result_nodes[:query.limit]
        result_edges = result_edges[:query.limit]
        
        query_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return KGQueryResult(
            nodes=result_nodes,
            edges=result_edges,
            paths=paths,
            query_time_ms=query_time
        )
    
    def get_related(
        self,
        node_id: str,
        edge_types: List[EdgeType] = None,
        depth: int = 1
    ) -> List[KGNode]:
        """Get nodes related to a given node."""
        related_ids = set()
        current_level = {node_id}
        
        for _ in range(depth):
            next_level = set()
            for nid in current_level:
                for edge in self.edges.values():
                    if edge.source_id == nid:
                        next_level.add(edge.target_id)
                        related_ids.add(edge.target_id)
                    elif edge.target_id == nid:
                        next_level.add(edge.source_id)
                        related_ids.add(edge.source_id)
            current_level = next_level
            
        return [self.nodes[nid] for nid in related_ids if nid in self.nodes]
    
    def link_skill_to_memory(self, skill_name: str, memory_key: str) -> bool:
        """Link a skill to its related memory."""
        skill_node = None
        memory_node = None
        
        # Find or create skill node
        for node in self.nodes.values():
            if node.label == skill_name and node.node_type == NodeType.SKILL:
                skill_node = node
                break
                
        if not skill_node:
            skill_node_id = self.create_node(
                label=skill_name,
                node_type=NodeType.SKILL,
                properties={"source": "ilma_skills"}
            )
            skill_node = self.nodes[skill_node_id]
        
        # Find or create memory node
        for node in self.nodes.values():
            if node.label == memory_key and node.node_type == NodeType.MEMORY:
                memory_node = node
                break
                
        if not memory_node:
            mem_node_id = self.create_node(
                label=memory_key,
                node_type=NodeType.MEMORY,
                properties={"source": "ilma_memory"}
            )
            memory_node = self.nodes[mem_node_id]
        
        # Create edge
        self.create_edge(
            source_id=skill_node.node_id,
            target_id=memory_node.node_id,
            edge_type=EdgeType.RELATES_TO,
            weight=0.8
        )
        
        return True
    
    def get_stats(self) -> Dict:
        """Get knowledge graph statistics."""
        return {
            **self.stats,
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "node_types": len(NodeType),
            "index_size": len(self.node_index)
        }


if __name__ == "__main__":
    kg = KnowledgeGraphOS()
    
    # Create sample nodes
    n1 = kg.create_node("ILMA", NodeType.AGENT, {"version": "2.0"})
    n2 = kg.create_node("memory", NodeType.CONCEPT, {"type": "persistent"})
    n3 = kg.create_node("skills", NodeType.SKILL, {"count": 253})
    
    # Create edges
    kg.create_edge(n1, n2, EdgeType.RELATES_TO)
    kg.create_edge(n1, n3, EdgeType.DEPENDS_ON)
    
    # Query
    result = kg.query(KGQuery(node_types=[NodeType.AGENT]))
    logger.info("Query time: %.2fms", result.query_time_ms)
    logger.info("Nodes found: %d", len(result.nodes))
    logger.info("Stats: %s", kg.get_stats())

# Backward-compatibility alias
KnowledgeGraph = KnowledgeGraphOS

_global_knowledge_graph_instance = None

def get_knowledge_graph() -> "KnowledgeGraphOS":
    """Get singleton KnowledgeGraphOS instance."""
    global _global_knowledge_graph_instance
    if _global_knowledge_graph_instance is None:
        _global_knowledge_graph_instance = KnowledgeGraphOS()
    return _global_knowledge_graph_instance


# ══════════════════════════════════════════════════════════════════════════════
# Compatibility wrapper (2026-06-01) — activates KG for self-improve integrator.
# Accepts persistence_path, string node_type, and persists to JSON.
# ══════════════════════════════════════════════════════════════════════════════
import json as _kg_json
from pathlib import Path as _KGPath


class KnowledgeGraph(KnowledgeGraphOS):
    """Persistent, string-friendly facade over KnowledgeGraphOS."""

    def __init__(self, persistence_path: str = None, os_id: str = "ilma_default"):
        super().__init__(os_id=os_id)
        self.persistence_path = _KGPath(persistence_path) if persistence_path else None
        self._load()

    def _coerce_type(self, node_type):
        if isinstance(node_type, NodeType):
            return node_type
        try:
            return NodeType[str(node_type).upper()]
        except (KeyError, AttributeError):
            # fall back to first/CONCEPT-like type
            try:
                return list(NodeType)[0]
            except Exception:
                return node_type

    def add_node(self, node_type=None, name: str = "", label: str = None,
                 properties: dict = None, **kw) -> str:
        """Integrator-style add_node(node_type=str, name=..., properties=...)."""
        nt = self._coerce_type(node_type)
        lbl = label or name or "unnamed"
        nid = self.create_node(label=lbl, node_type=nt, properties=properties or {})
        self._save()
        return nid

    def add_edge(self, source_id: str, target_id: str, edge_type=None,
                 weight: float = 1.0, properties: dict = None, **kw):
        et = edge_type
        if not isinstance(et, EdgeType):
            try:
                et = EdgeType[str(edge_type).upper()]
            except (KeyError, AttributeError):
                try:
                    et = list(EdgeType)[0]
                except Exception:
                    et = edge_type
        eid = self.create_edge(source_id, target_id, et, weight=weight, properties=properties or {})
        self._save()
        return eid

    def _save(self):
        if not self.persistence_path:
            return
        try:
            self.persistence_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "os_id": self.os_id,
                "stats": self.stats,
                "nodes": {nid: {"label": n.label, "type": n.node_type.value,
                                "properties": n.properties}
                          for nid, n in self.nodes.items()},
            }
            tmp = self.persistence_path.with_suffix(".tmp")
            tmp.write_text(_kg_json.dumps(data, indent=2, default=str))
            tmp.replace(self.persistence_path)
        except Exception:
            pass

    def _load(self):
        if not self.persistence_path or not self.persistence_path.exists():
            return
        try:
            data = _kg_json.loads(self.persistence_path.read_text())
            self.stats.update(data.get("stats", {}))
            for nid, nd in data.get("nodes", {}).items():
                try:
                    nt = NodeType[str(nd.get("type", "")).upper()]
                except (KeyError, AttributeError):
                    nt = list(NodeType)[0]
                self.nodes[nid] = KGNode(node_id=nid, node_type=nt,
                                         label=nd.get("label", ""),
                                         properties=nd.get("properties", {}))
        except Exception:
            pass
