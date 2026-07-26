#!/usr/bin/env python3
"""
ILMA Agent Registry v1.0
=========================
Registry for multi-agent coordination.

Based on: ILMA agent_registry patterns
"""
import os
import sys
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

WORKSPACE = Path("/root/.hermes/profiles/ilma")
REGISTRY_DIR = WORKSPACE / ".registry"
REGISTRY_DIR.mkdir(parents=True, exist_ok=True)


class AgentRegistry:
    """Registry of agents in the system."""
    
    def __init__(self):
        self.registry_file = REGISTRY_DIR / "agents.json"
        self.agents = {}
        self.load()
    
    def load(self):
        """Load registry from disk."""
        if self.registry_file.exists():
            try:
                with open(self.registry_file) as f:
                    self.agents = json.load(f)
            except ValueError:
                self.agents = {}
    
    def save(self):
        """Save registry to disk."""
        with open(self.registry_file, "w") as f:
            json.dump(self.agents, f, indent=2)
    
    def register(self, agent_id: str, agent_data: Dict) -> bool:
        """Register an agent."""
        self.agents[agent_id] = {
            **agent_data,
            "registered_at": datetime.now().isoformat(),
            "last_seen": datetime.now().isoformat()
        }
        self.save()
        return True
    
    def unregister(self, agent_id: str) -> bool:
        """Unregister an agent."""
        if agent_id in self.agents:
            del self.agents[agent_id]
            self.save()
            return True
        return False
    
    def heartbeat(self, agent_id: str) -> bool:
        """Update agent heartbeat."""
        if agent_id in self.agents:
            self.agents[agent_id]["last_seen"] = datetime.now().isoformat()
            self.save()
            return True
        return False
    
    def get_agent(self, agent_id: str) -> Optional[Dict]:
        """Get agent info."""
        return self.agents.get(agent_id)
    
    def list_agents(self) -> List[Dict]:
        """List all registered agents."""
        return list(self.agents.values())
    
    def get_stats(self) -> Dict:
        """Get registry statistics."""
        return {
            "total_agents": len(self.agents),
            "agents": list(self.agents.keys())
        }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ILMA Agent Registry")
    parser.add_argument("command", nargs="?", default="list",
                        choices=["register", "unregister", "heartbeat", "get", "list", "stats"])
    parser.add_argument("--id", type=str, help="Agent ID")
    parser.add_argument("--name", type=str, help="Agent name")
    parser.add_argument("--type", type=str, help="Agent type")
    
    registry = AgentRegistry()
    args = parser.parse_args()
    
    if args.command == "register":
        if not args.id:
            print("Error: --id required")
            sys.exit(1)
        
        registry.register(args.id, {
            "name": args.name or args.id,
            "type": args.type or "unknown"
        })
        print(f"Registered: {args.id}")
    
    elif args.command == "unregister":
        if not args.id:
            print("Error: --id required")
            sys.exit(1)
        
        if registry.unregister(args.id):
            print(f"Unregistered: {args.id}")
        else:
            print(f"Not found: {args.id}")
    
    elif args.command == "heartbeat":
        if not args.id:
            print("Error: --id required")
            sys.exit(1)
        
        if registry.heartbeat(args.id):
            print(f"Heartbeat updated: {args.id}")
        else:
            print(f"Not registered: {args.id}")
    
    elif args.command == "get":
        if not args.id:
            print("Error: --id required")
            sys.exit(1)
        
        agent = registry.get_agent(args.id)
        if agent:
            print(json.dumps(agent, indent=2))
        else:
            print(f"Not found: {args.id}")
    
    elif args.command == "list":
        for agent in registry.list_agents():
            print(f"  {agent['name']} ({agent['id']})")
    
    elif args.command == "stats":
        stats = registry.get_stats()
        print(json.dumps(stats, indent=2))
