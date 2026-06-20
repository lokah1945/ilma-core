#!/usr/bin/env python3
"""
ILMA Agent Civilization — Multi-Agent Collaboration (AYDA-Inspired)
===================================================================
Agent-to-agent collaboration framework for ILMA.

Inspired by AYDA's agent_civilization module.
Supports: collaboration sessions, message passing, reputation, specialization.

Usage:
    from ilma_agent_civilization import AgentCivilization, CollaborationSession
    
    civ = AgentCivilization(agent_id="ilma_main")
    civ.add_collaborator("nara")
    civ.send_message("nara", "Task: analyze this")
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict


class CollaborationType(Enum):
    DIRECT = "direct"
    ROUND_ROBIN = "round_robin"
    PARALLEL = "parallel"
    CASCADE = "cascade"
    HIERARCHICAL = "hierarchical"


class MessagePriority(Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class AgentRole(Enum):
    COORDINATOR = "coordinator"
    SPECIALIST = "specialist"
    REVIEWER = "reviewer"
    EXECUTOR = "executor"


@dataclass
class AgentMessage:
    message_id: str
    sender_id: str
    receiver_ids: List[str]
    content: str
    priority: MessagePriority = MessagePriority.NORMAL
    timestamp: datetime = field(default_factory=datetime.now)
    reply_to: Optional[str] = None
    metadata: Dict = field(default_factory=dict)
    status: str = "pending"


@dataclass
class CollaborationSession:
    session_id: str
    participants: List[str]
    collaboration_type: CollaborationType
    task: str
    status: str = "active"
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    contributions: Dict[str, str] = field(default_factory=dict)


@dataclass
class AgentReputation:
    agent_id: str
    task_completions: int = 0
    success_rate: float = 0.0
    avg_quality: float = 0.0
    specialties: List[str] = field(default_factory=list)
    last_active: datetime = field(default_factory=datetime.now)


class AgentSpecialization:
    """Agent specialization registry."""

    SPECIALIZATIONS = {
        "coding": ["ilma", "nara", "naila"],
        "research": ["ilma", "zara"],
        "creative": ["nara", "zara"],
        "reasoning": ["naila", "ilma"],
        "fast_tasks": ["nara", "zara"],
        "heavy_coding": ["nara", "naila"],
    }

    @classmethod
    def get_specialists(cls, domain: str) -> List[str]:
        """Get specialists for a domain."""
        return cls.SPECIALIZATIONS.get(domain, [])

    @classmethod
    def register_specialist(cls, agent_id: str, domain: str):
        """Register agent as specialist for domain."""
        if domain not in cls.SPECIALIZATIONS:
            cls.SPECIALIZATIONS[domain] = []
        if agent_id not in cls.SPECIALIZATIONS[domain]:
            cls.SPECIALIZATIONS[domain].append(agent_id)


class AgentCivilization:
    """
    Multi-agent collaboration system.
    Inspired by AYDA's agent_civilization module.
    """

    def __init__(self, agent_id: str, workspace: Optional[Path] = None):
        self.agent_id = agent_id
        self.workspace = workspace or Path("/root/.hermes/profiles/ilma")
        self.messages: List[AgentMessage] = []
        self.sessions: Dict[str, CollaborationSession] = {}
        self.reputations: Dict[str, AgentReputation] = {}
        self.subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self.stats = {
            "sessions_created": 0,
            "messages_sent": 0,
            "collaborations_completed": 0,
            "agents_registered": 0
        }

        # Register self
        self._register_agent(agent_id)

    def _register_agent(self, agent_id: str):
        """Register an agent in the civilization."""
        if agent_id not in self.reputations:
            self.reputations[agent_id] = AgentReputation(agent_id=agent_id)
            self.stats["agents_registered"] += 1

    def add_collaborator(self, agent_id: str, specialty: Optional[str] = None):
        """Add a collaborator agent."""
        self._register_agent(agent_id)
        if specialty:
            AgentSpecialization.register_specialist(agent_id, specialty)

    def send_message(
        self,
        receiver_ids: List[str],
        content: str,
        priority: MessagePriority = MessagePriority.NORMAL,
        session_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> str:
        """Send message to one or more agents."""
        self._register_agent(self.agent_id)
        for rid in receiver_ids:
            self._register_agent(rid)

        message_id = f"msg_{len(self.messages)}_{int(time.time())}"
        message = AgentMessage(
            message_id=message_id,
            sender_id=self.agent_id,
            receiver_ids=receiver_ids,
            content=content,
            priority=priority,
            metadata=metadata or {"session_id": session_id} if session_id else {}
        )
        message.status = "delivered"
        self.messages.append(message)
        self.stats["messages_sent"] += 1

        # Notify subscribers
        for receiver_id in receiver_ids:
            for callback in self.subscribers.get(receiver_id, []):
                try:
                    callback(message)
                except Exception:
                    pass

        return message_id

    def subscribe(self, agent_id: str, callback: Callable):
        """Subscribe to messages for an agent."""
        self.subscribers[agent_id].append(callback)

    def get_inbox(self, agent_id: Optional[str] = None) -> List[AgentMessage]:
        """Get messages for an agent (defaults to self)."""
        target = agent_id or self.agent_id
        return [m for m in self.messages if target in m.receiver_ids]

    def get_unread_count(self, agent_id: Optional[str] = None) -> int:
        """Get unread message count."""
        return len(self.get_inbox(agent_id))

    def create_session(
        self,
        session_id: str,
        participants: List[str],
        collaboration_type: CollaborationType,
        task: str
    ) -> CollaborationSession:
        """Create a collaboration session."""
        for p in participants:
            self._register_agent(p)

        session = CollaborationSession(
            session_id=session_id,
            participants=participants,
            collaboration_type=collaboration_type,
            task=task
        )
        self.sessions[session_id] = session
        self.stats["sessions_created"] += 1
        return session

    def update_session(self, session_id: str, contribution: str, agent_id: Optional[str] = None):
        """Update session with agent contribution."""
        session = self.sessions.get(session_id)
        if not session:
            return

        agent_id = agent_id or self.agent_id
        session.contributions[agent_id] = contribution

        # Check if complete
        if len(session.contributions) >= len(session.participants):
            session.completed_at = datetime.now()
            session.status = "completed"
            self.stats["collaborations_completed"] += 1

    def complete_session(self, session_id: str):
        """Mark session as completed."""
        session = self.sessions.get(session_id)
        if session:
            session.completed_at = datetime.now()
            session.status = "completed"
            self.stats["collaborations_completed"] += 1

    def get_active_sessions(self) -> List[CollaborationSession]:
        """Get all active sessions."""
        return [s for s in self.sessions.values() if s.status == "active"]

    def update_reputation(self, agent_id: str, success: bool, quality: float):
        """Update agent reputation."""
        if agent_id not in self.reputations:
            self._register_agent(agent_id)

        rep = self.reputations[agent_id]
        rep.task_completions += 1

        # Update running average
        n = rep.task_completions
        rep.avg_quality = ((n - 1) * rep.avg_quality + quality) / n

        if success:
            success_rate = (rep.task_completions - 1) / rep.task_completions + 1 / rep.task_completions
        else:
            success_rate = (rep.task_completions - 1) / rep.task_completions

        rep.success_rate = success_rate
        rep.last_active = datetime.now()

    def get_reputation(self, agent_id: str) -> Optional[AgentReputation]:
        """Get agent reputation."""
        return self.reputations.get(agent_id)

    def get_best_specialist(self, domain: str) -> Optional[str]:
        """Get best specialist for a domain based on reputation."""
        specialists = AgentSpecialization.get_specialists(domain)
        if not specialists:
            return None

        best = None
        best_score = -1

        for agent_id in specialists:
            rep = self.reputations.get(agent_id)
            if rep:
                score = rep.avg_quality * rep.success_rate
                if score > best_score:
                    best_score = score
                    best = agent_id

        return best

    def broadcast(self, content: str, priority: MessagePriority = MessagePriority.NORMAL):
        """Broadcast to all known agents."""
        all_agents = list(self.reputations.keys())
        return self.send_message(all_agents, content, priority)

    def get_stats(self) -> Dict[str, Any]:
        """Get civilization statistics."""
        return {
            **self.stats,
            "agents": len(self.reputations),
            "active_sessions": len(self.get_active_sessions()),
            "total_messages": len(self.messages)
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "agent_id": self.agent_id,
            "stats": self.stats,
            "reputations": {
                k: {
                    "task_completions": v.task_completions,
                    "success_rate": v.success_rate,
                    "avg_quality": v.avg_quality,
                    "specialties": v.specialties,
                    "last_active": v.last_active.isoformat()
                }
                for k, v in self.reputations.items()
            },
            "active_sessions": len(self.get_active_sessions()),
            "total_messages": len(self.messages)
        }

    @classmethod
    def from_dict(cls, data: Dict, agent_id: str) -> "AgentCivilization":
        """Deserialize from dictionary."""
        civ = cls(agent_id=agent_id)
        civ.stats = data.get("stats", {})
        for agent_id, rep_data in data.get("reputations", {}).items():
            rep = AgentReputation(
                agent_id=agent_id,
                task_completions=rep_data.get("task_completions", 0),
                success_rate=rep_data.get("success_rate", 0.0),
                avg_quality=rep_data.get("avg_quality", 0.0),
                specialties=rep_data.get("specialties", []),
                last_active=datetime.fromisoformat(rep_data.get("last_active", datetime.now().isoformat()))
            )
            civ.reputations[agent_id] = rep
        return civ


# === CLI ===
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ILMA Agent Civilization")
    subparsers = parser.add_subparsers(dest="command", help="Command")

    # status
    subparsers.add_parser("status", help="Show civilization status")

    # send
    send_parser = subparsers.add_parser("send", help="Send message")
    send_parser.add_argument("receiver", help="Receiver agent ID")
    send_parser.add_argument("content", help="Message content")

    # session
    session_parser = subparsers.add_parser("session", help="Create session")
    session_parser.add_argument("session_id", help="Session ID")
    session_parser.add_argument("--participants", nargs="+", help="Participant agents")

    # list
    subparsers.add_parser("inbox", help="Show inbox")
    subparsers.add_parser("sessions", help="Show active sessions")

    args = parser.parse_args()

    civ = AgentCivilization(agent_id="ilma_main")

    if args.command == "status":
        stats = civ.get_stats()
        print(json.dumps(stats, indent=2))

    elif args.command == "send":
        msg_id = civ.send_message([args.receiver], args.content)
        print(f"Message sent: {msg_id}")

    elif args.command == "session":
        if args.participants:
            session = civ.create_session(
                args.session_id,
                args.participants,
                CollaborationType.PARALLEL,
                "Collaborative task"
            )
            print(f"Session created: {session.session_id}")
        else:
            print("Usage: session <session_id> --participants <agent1> <agent2> ...")

    elif args.command == "inbox":
        inbox = civ.get_inbox()
        print(f"Inbox: {len(inbox)} messages")
        for m in inbox:
            print(f"  [{m.message_id}] {m.sender_id} -> {m.receiver_ids}: {m.content[:50]}")

    elif args.command == "sessions":
        active = civ.get_active_sessions()
        print(f"Active sessions: {len(active)}")
        for s in active:
            print(f"  [{s.session_id}] {s.task[:50]} ({s.collaboration_type.value})")

    else:
        parser.print_help()