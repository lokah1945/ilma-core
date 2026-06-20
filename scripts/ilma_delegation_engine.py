#!/usr/bin/env python3
"""
ILMA Delegation Engine - Delegate to sub-agents with isolated context.

This module provides:
- SubAgentPool: Manages pool of sub-agents with load balancing
- ContextIsolation: Isolated context management per agent
- ResultAggregator: Aggregates results from multiple delegations

Usage:
    python ilma_delegation_engine.py --delegate --task "complex task" --agent-type coder
    python ilma_delegation_engine.py --pool-status
    python ilma_delegation_engine.py --aggregate --ticket ticket1 ticket2

Author: ILMA Team
Version: 1.0.0
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set
from contextvars import ContextVar
from threading import Lock

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Context variable for isolated execution context
_current_context: ContextVar[Dict[str, Any]] = ContextVar("current_context", default={})


class AgentType(Enum):
    """Types of sub-agents available."""
    CODER = "coder"
    RESEARCHER = "researcher"
    ANALYZER = "analyzer"
    WRITER = "writer"
    GENERAL = "general"


class AgentStatus(Enum):
    """Sub-agent status."""
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    OFFLINE = "offline"


class IsolationLevel(Enum):
    """Context isolation levels."""
    NONE = "none"
    PARTIAL = "partial"
    FULL = "full"


@dataclass
class AgentConfig:
    """Configuration for a sub-agent."""
    agent_id: str
    agent_type: AgentType
    capabilities: List[str] = field(default_factory=list)
    max_concurrent_tasks: int = 5
    timeout: int = 300
    isolation_level: IsolationLevel = IsolationLevel.FULL


@dataclass
class DelegationTicket:
    """Ticket tracking a delegation request."""
    ticket_id: str
    agent_id: str
    task_id: str
    task_data: Dict[str, Any]
    context: Dict[str, Any]
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    status: str = "pending"
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@dataclass 
class ContextSnapshot:
    """Snapshot of isolated context at delegation time."""
    snapshot_id: str
    ticket_id: str
    variables: Dict[str, Any]
    capabilities: List[str]
    restrictions: List[str]
    created_at: float = field(default_factory=time.time)


class ContextIsolation:
    """
    Manages isolated context for sub-agent execution.
    
    Features:
    - Full isolation with separate variable scopes
    - Context snapshots for debugging
    - Capability whitelisting
    - Restriction blacklisting
    - Secure data transfer between contexts
    """

    def __init__(self, level: IsolationLevel = IsolationLevel.FULL):
        """
        Initialize context isolation.
        
        Args:
            level: Isolation level to enforce
        """
        self.level = level
        self.snapshots: Dict[str, ContextSnapshot] = {}
        self.contexts: Dict[str, Dict[str, Any]] = {}
        self.logger = logging.getLogger(f"{__name__}.ContextIsolation")
        self._lock = Lock()

    def create_context(
        self,
        ticket_id: str,
        initial_vars: Optional[Dict[str, Any]] = None,
        capabilities: Optional[List[str]] = None,
        restrictions: Optional[List[str]] = None
    ) -> ContextSnapshot:
        """
        Create an isolated context for a delegation ticket.
        
        Args:
            ticket_id: Ticket ID for this context
            initial_vars: Initial variables for the context
            capabilities: Whitelisted capabilities
            restrictions: Blacklisted capabilities
            
        Returns:
            ContextSnapshot with isolated context
        """
        with self._lock:
            snapshot_id = f"snapshot_{uuid.uuid4().hex[:8]}"
            
            # Filter variables based on isolation level
            if self.level == IsolationLevel.FULL:
                filtered_vars = self._filter_sensitive(initial_vars or {})
            elif self.level == IsolationLevel.PARTIAL:
                filtered_vars = self._filter_internal(initial_vars or {})
            else:
                filtered_vars = initial_vars or {}
            
            snapshot = ContextSnapshot(
                snapshot_id=snapshot_id,
                ticket_id=ticket_id,
                variables=filtered_vars,
                capabilities=capabilities or [],
                restrictions=restrictions or []
            )
            
            self.snapshots[snapshot_id] = snapshot
            self.contexts[ticket_id] = filtered_vars
            
            self.logger.info(f"Created context {snapshot_id} for ticket {ticket_id}")
            return snapshot

    def get_context(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        """Get context for a ticket."""
        return self.contexts.get(ticket_id)

    def update_context(self, ticket_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update context variables for a ticket.
        
        Args:
            ticket_id: Ticket ID
            updates: Variables to update
            
        Returns:
            True if successful
        """
        if ticket_id not in self.contexts:
            return False
        
        with self._lock:
            if self.level == IsolationLevel.FULL:
                updates = self._filter_sensitive(updates)
            
            self.contexts[ticket_id].update(updates)
            
            # Update corresponding snapshot
            for snapshot in self.snapshots.values():
                if snapshot.ticket_id == ticket_id:
                    snapshot.variables.update(updates)
            
        return True

    def destroy_context(self, ticket_id: str) -> bool:
        """
        Destroy context for a ticket (cleanup).
        
        Args:
            ticket_id: Ticket ID
            
        Returns:
            True if context was destroyed
        """
        with self._lock:
            if ticket_id in self.contexts:
                del self.contexts[ticket_id]
                # Remove snapshots for this ticket
                to_remove = [
                    sid for sid, s in self.snapshots.items() 
                    if s.ticket_id == ticket_id
                ]
                for sid in to_remove:
                    del self.snapshots[sid]
                self.logger.info(f"Destroyed context for ticket {ticket_id}")
                return True
        return False

    def _filter_sensitive(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Filter potentially sensitive data."""
        sensitive_keys = {
            "password", "secret", "token", "api_key", "apikey",
            "credential", "auth", "private_key", "secret_key"
        }
        return {
            k: ("***REDACTED***" if any(s in k.lower() for s in sensitive_keys) else v)
            for k, v in data.items()
        }

    def _filter_internal(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Filter internal system variables."""
        internal_keys = {"__", "sys.", "os.", "path."}
        return {
            k: v for k, v in data.items()
            if not any(k.startswith(p) for p in internal_keys)
        }

    def get_snapshot(self, snapshot_id: str) -> Optional[ContextSnapshot]:
        """Get a context snapshot by ID."""
        return self.snapshots.get(snapshot_id)


class SubAgent:
    """Represents a single sub-agent instance."""

    def __init__(self, config: AgentConfig):
        """
        Initialize sub-agent.
        
        Args:
            config: Agent configuration
        """
        self.config = config
        self.status = AgentStatus.IDLE
        self.current_tasks: List[str] = []
        self.completed_tasks: List[str] = []
        self.total_completed = 0
        self.logger = logging.getLogger(f"{__name__}.SubAgent.{config.agent_id}")

    def can_accept_task(self) -> bool:
        """Check if agent can accept a new task."""
        return (
            self.status != AgentStatus.OFFLINE and
            len(self.current_tasks) < self.config.max_concurrent_tasks
        )

    def assign_task(self, ticket_id: str) -> bool:
        """Assign a task to this agent."""
        if not self.can_accept_task():
            return False
        self.current_tasks.append(ticket_id)
        self.status = AgentStatus.BUSY
        self.logger.debug(f"Assigned task {ticket_id}")
        return True

    def complete_task(self, ticket_id: str, result: Dict[str, Any]) -> None:
        """Mark a task as completed."""
        if ticket_id in self.current_tasks:
            self.current_tasks.remove(ticket_id)
        self.completed_tasks.append(ticket_id)
        self.total_completed += 1
        
        if self.current_tasks:
            self.status = AgentStatus.BUSY
        else:
            self.status = AgentStatus.IDLE

    def get_load(self) -> float:
        """Get current load ratio (0.0 to 1.0)."""
        return len(self.current_tasks) / self.config.max_concurrent_tasks


class SubAgentPool:
    """
    Manages a pool of sub-agents with load balancing.
    
    Features:
    - Agent registration and lifecycle
    - Load-based task distribution
    - Capability-based routing
    - Health monitoring
    - Auto-scaling simulation
    """

    def __init__(self, initial_size: int = 3):
        """
        Initialize agent pool.
        
        Args:
            initial_size: Number of agents to spawn initially
        """
        self.agents: Dict[str, SubAgent] = {}
        self.agent_configs: Dict[str, AgentConfig] = {}
        self.logger = logging.getLogger(f"{__name__}.SubAgentPool")
        self._lock = Lock()
        
        # Initialize with general-purpose agents
        for i in range(initial_size):
            self._spawn_agent(AgentType.GENERAL)

    def _spawn_agent(self, agent_type: AgentType) -> SubAgent:
        """Spawn a new agent of the given type."""
        agent_id = f"{agent_type.value}_{uuid.uuid4().hex[:8]}"
        
        capabilities_map = {
            AgentType.CODER: ["code_generation", "code_review", "refactoring"],
            AgentType.RESEARCHER: ["web_search", "data_collection", "analysis"],
            AgentType.ANALYZER: ["data_analysis", "statistics", "visualization"],
            AgentType.WRITER: ["content_writing", "editing", "formatting"],
            AgentType.GENERAL: ["general_purpose", "problem_solving"],
        }
        
        config = AgentConfig(
            agent_id=agent_id,
            agent_type=agent_type,
            capabilities=capabilities_map.get(agent_type, ["general_purpose"]),
            max_concurrent_tasks=5,
            timeout=300,
            isolation_level=IsolationLevel.FULL
        )
        
        agent = SubAgent(config)
        self.agents[agent_id] = agent
        self.agent_configs[agent_id] = config
        
        self.logger.info(f"Spawned agent {agent_id} of type {agent_type.value}")
        return agent

    def get_agent(
        self,
        required_capabilities: Optional[List[str]] = None,
        preferred_type: Optional[AgentType] = None
    ) -> Optional[SubAgent]:
        """
        Get an available agent matching criteria.
        
        Args:
            required_capabilities: Required capabilities
            preferred_type: Preferred agent type
            
        Returns:
            Available SubAgent or None
        """
        candidates = []
        
        for agent in self.agents.values():
            if not agent.can_accept_task():
                continue
            
            if preferred_type and agent.config.agent_type != preferred_type:
                continue
            
            if required_capabilities:
                if not all(cap in agent.config.capabilities for cap in required_capabilities):
                    continue
            
            candidates.append(agent)
        
        if not candidates:
            return None
        
        # Return least loaded agent
        return min(candidates, key=lambda a: a.get_load())

    def get_least_loaded(self) -> Optional[SubAgent]:
        """Get the least loaded available agent."""
        available = [a for a in self.agents.values() if a.can_accept_task()]
        if not available:
            return None
        return min(available, key=lambda a: a.get_load())

    def delegate_task(
        self,
        task_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        required_capabilities: Optional[List[str]] = None,
        preferred_type: Optional[AgentType] = None
    ) -> Optional[DelegationTicket]:
        """
        Delegate a task to an appropriate agent.
        
        Args:
            task_data: Task payload
            context: Execution context
            required_capabilities: Required agent capabilities
            preferred_type: Preferred agent type
            
        Returns:
            DelegationTicket or None if no agent available
        """
        agent = self.get_agent(required_capabilities, preferred_type)
        
        if not agent:
            self.logger.warning("No available agent for delegation")
            return None
        
        ticket_id = f"ticket_{uuid.uuid4().hex[:12]}"
        task_id = task_data.get("task_id", str(uuid.uuid4()))
        
        # Create isolated context
        isolation = ContextIsolation(level=agent.config.isolation_level)
        isolation.create_context(
            ticket_id=ticket_id,
            initial_vars=context or {},
            capabilities=agent.config.capabilities
        )
        
        ticket = DelegationTicket(
            ticket_id=ticket_id,
            agent_id=agent.config.agent_id,
            task_id=task_id,
            task_data=task_data,
            context=context or {}
        )
        
        agent.assign_task(ticket_id)
        
        self.logger.info(f"Delegated task {task_id} to agent {agent.config.agent_id}")
        return ticket

    def complete_ticket(self, ticket_id: str, result: Dict[str, Any]) -> None:
        """Mark a ticket as complete."""
        for agent in self.agents.values():
            if ticket_id in agent.current_tasks:
                agent.complete_task(ticket_id, result)
                self.logger.info(f"Ticket {ticket_id} completed")
                break

    def fail_ticket(self, ticket_id: str, error: str) -> None:
        """Mark a ticket as failed."""
        for agent in self.agents.values():
            if ticket_id in agent.current_tasks:
                agent.current_tasks.remove(ticket_id)
                agent.status = AgentStatus.ERROR
                self.logger.error(f"Ticket {ticket_id} failed: {error}")
                break

    def get_pool_status(self) -> Dict[str, Any]:
        """Get overall pool status."""
        total_agents = len(self.agents)
        busy_agents = sum(1 for a in self.agents.values() if a.status == AgentStatus.BUSY)
        idle_agents = sum(1 for a in self.agents.values() if a.status == AgentStatus.IDLE)
        
        avg_load = sum(a.get_load() for a in self.agents.values()) / max(total_agents, 1)
        
        return {
            "total_agents": total_agents,
            "busy_agents": busy_agents,
            "idle_agents": idle_agents,
            "average_load": avg_load,
            "agents": [
                {
                    "agent_id": a.config.agent_id,
                    "type": a.config.agent_type.value,
                    "status": a.status.value,
                    "current_tasks": len(a.current_tasks),
                    "total_completed": a.total_completed,
                    "load": a.get_load()
                }
                for a in self.agents.values()
            ]
        }

    def add_agent_type(self, agent_type: AgentType, count: int = 1) -> List[SubAgent]:
        """Add more agents of a specific type."""
        agents = []
        for _ in range(count):
            agents.append(self._spawn_agent(agent_type))
        return agents


class ResultAggregator:
    """
    Aggregates results from multiple delegation tickets.
    
    Features:
    - Parallel result collection
    - Error aggregation
    - Result merging strategies
    - Timeout handling
    - Partial result support
    """

    def __init__(self, timeout: float = 60.0):
        """
        Initialize result aggregator.
        
        Args:
            timeout: Default timeout for result collection
        """
        self.results: Dict[str, Dict[str, Any]] = {}
        self.timeout = timeout
        self.logger = logging.getLogger(f"{__name__}.ResultAggregator")

    def add_result(self, ticket_id: str, result: Dict[str, Any]) -> None:
        """Add a result for a ticket."""
        self.results[ticket_id] = result
        self.logger.debug(f"Added result for ticket {ticket_id}")

    def get_result(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        """Get result for a specific ticket."""
        return self.results.get(ticket_id)

    def wait_for_results(
        self,
        ticket_ids: List[str],
        timeout: Optional[float] = None,
        poll_interval: float = 0.5
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Wait for results from multiple tickets.
        
        Args:
            ticket_ids: List of ticket IDs to wait for
            timeout: Maximum time to wait
            poll_interval: Polling interval
            
        Returns:
            Dictionary of ticket_id to result (may be None if timeout)
        """
        timeout = timeout or self.timeout
        deadline = time.time() + timeout
        pending = set(ticket_ids)
        results: Dict[str, Optional[Dict[str, Any]]] = {tid: None for tid in ticket_ids}
        
        while pending and time.time() < deadline:
            for ticket_id in list(pending):
                if ticket_id in self.results:
                    results[ticket_id] = self.results[ticket_id]
                    pending.remove(ticket_id)
            
            if pending:
                time.sleep(min(poll_interval, deadline - time.time()))
        
        if pending:
            self.logger.warning(f"Timeout waiting for tickets: {pending}")
        
        return results

    def aggregate(
        self,
        ticket_ids: List[str],
        strategy: str = "merge"
    ) -> Dict[str, Any]:
        """
        Aggregate results from multiple tickets.
        
        Args:
            ticket_ids: List of ticket IDs to aggregate
            strategy: Aggregation strategy (merge, combine, first, last)
            
        Returns:
            Aggregated result dictionary
        """
        results = [self.results.get(tid) for tid in ticket_ids if tid in self.results]
        results = [r for r in results if r is not None]
        
        if not results:
            return {"error": "No results to aggregate", "count": 0}
        
        aggregated = {
            "count": len(results),
            "successful": sum(1 for r in results if r.get("status") != "error"),
            "failed": sum(1 for r in results if r.get("status") == "error"),
        }
        
        if strategy == "merge":
            aggregated["data"] = {}
            for r in results:
                if "data" in r:
                    aggregated["data"].update(r["data"])
                elif "result" in r:
                    aggregated["data"].update(r["result"])
                    
        elif strategy == "combine":
            aggregated["results"] = results
            
        elif strategy == "first":
            aggregated["data"] = results[0] if results else {}
            
        elif strategy == "last":
            aggregated["data"] = results[-1] if results else {}
        
        return aggregated

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all aggregated results."""
        total = len(self.results)
        successful = sum(1 for r in self.results.values() if r.get("status") != "error")
        failed = sum(1 for r in self.results.values() if r.get("status") == "error")
        
        return {
            "total_tickets": total,
            "successful": successful,
            "failed": failed,
            "pending": total - successful - failed
        }


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="ILMA Delegation Engine - Delegate tasks to sub-agents with isolated context",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --delegate --task '{"action": "analyze", "data": "sample"}' --agent-type coder
  %(prog)s --pool-status
  %(prog)s --aggregate --ticket ticket_abc123 ticket_def456
  %(prog)s --add-agents --type researcher --count 2
        """
    )
    
    parser.add_argument("--delegate", "-d", action="store_true", help="Delegate a task")
    parser.add_argument("--task", "-t", help="Task JSON data")
    parser.add_argument("--agent-type", choices=["coder", "researcher", "analyzer", "writer", "general"],
                       default="general", help="Type of agent to use")
    parser.add_argument("--capabilities", "-c", nargs="+", help="Required capabilities")
    
    parser.add_argument("--pool-status", "-p", action="store_true", help="Show pool status")
    parser.add_argument("--add-agents", action="store_true", help="Add agents to pool")
    parser.add_argument("--type", choices=["coder", "researcher", "analyzer", "writer", "general"],
                       help="Agent type to add")
    parser.add_argument("--count", type=int, default=1, help="Number of agents to add")
    
    parser.add_argument("--aggregate", "-a", action="store_true", help="Aggregate results")
    parser.add_argument("--ticket", nargs="+", help="Ticket IDs for aggregation")
    
    parser.add_argument("--json-output", "-j", action="store_true", help="JSON output")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    logger = logging.getLogger(__name__)
    
    try:
        # Initialize pool and aggregator
        pool = SubAgentPool(initial_size=3)
        aggregator = ResultAggregator()
        
        # Pool status
        if args.pool_status:
            status = pool.get_pool_status()
            if args.json_output:
                print(json.dumps(status, indent=2))
            else:
                print(f"Agent Pool Status")
                print("=" * 50)
                print(f"Total agents: {status['total_agents']}")
                print(f"Busy: {status['busy_agents']}, Idle: {status['idle_agents']}")
                print(f"Average load: {status['average_load']:.2%}")
                print("\nAgents:")
                for agent in status["agents"]:
                    print(f"  [{agent['status']}] {agent['agent_id']} ({agent['type']}) "
                          f"- {agent['current_tasks']} tasks, {agent['total_completed']} completed")
            return 0
        
        # Add agents
        if args.add_agents:
            if not args.type:
                logger.error("--type required when adding agents")
                return 1
            
            agent_type = AgentType(args.type)
            new_agents = pool.add_agent_type(agent_type, args.count)
            print(f"Added {len(new_agents)} agent(s) of type {agent_type.value}")
            for agent in new_agents:
                print(f"  - {agent.config.agent_id}")
            return 0
        
        # Delegate task
        if args.delegate:
            if not args.task:
                logger.error("--task required for delegation")
                return 1
            
            task_data = json.loads(args.task)
            task_data["task_id"] = task_data.get("task_id", str(uuid.uuid4()))
            
            preferred_type = AgentType(args.agent_type) if args.agent_type else None
            
            ticket = pool.delegate_task(
                task_data=task_data,
                context={"source": "delegation_engine"},
                required_capabilities=args.capabilities,
                preferred_type=preferred_type
            )
            
            if ticket:
                # Simulate task completion
                time.sleep(0.5)
                result = {
                    "status": "success",
                    "task_id": ticket.task_id,
                    "output": f"Completed by {ticket.agent_id}",
                    "duration": 0.5
                }
                pool.complete_ticket(ticket.ticket_id, result)
                aggregator.add_result(ticket.ticket_id, result)
                
                if args.json_output:
                    print(json.dumps({
                        "ticket_id": ticket.ticket_id,
                        "agent_id": ticket.agent_id,
                        "task_id": ticket.task_id,
                        "result": result
                    }, indent=2))
                else:
                    print(f"Task delegated successfully")
                    print(f"  Ticket: {ticket.ticket_id}")
                    print(f"  Agent: {ticket.agent_id}")
                    print(f"  Result: {result['output']}")
                return 0
            else:
                logger.error("Failed to delegate - no available agent")
                return 1
        
        # Aggregate results
        if args.aggregate:
            if not args.ticket:
                logger.error("--ticket required for aggregation")
                return 1
            
            # For demo, add some mock results if not present
            for tid in args.ticket:
                if tid not in aggregator.results:
                    aggregator.add_result(tid, {
                        "status": "success",
                        "task_id": tid,
                        "output": f"Mock result for {tid}"
                    })
            
            aggregated = aggregator.aggregate(args.ticket)
            summary = aggregator.get_summary()
            
            if args.json_output:
                print(json.dumps({
                    "summary": summary,
                    "aggregated": aggregated
                }, indent=2))
            else:
                print(f"Aggregation Summary")
                print("=" * 50)
                print(f"Total: {summary['total_tickets']}")
                print(f"Successful: {summary['successful']}")
                print(f"Failed: {summary['failed']}")
                print(f"\nAggregated Data: {json.dumps(aggregated.get('data', {}), indent=2)}")
            return 0
        
        # Default: show help
        parser.print_help()
        return 0
        
    except Exception as e:
        logger.exception("Fatal error")
        return 1


if __name__ == "__main__":
    exit(main())