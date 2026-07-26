#!/usr/bin/env python3
"""
ILMA Flow Reporter v1.0
=========================
Workflow and task flow reporting for ILMA.

Based on: ILMA ILMA_flow_reporter.py patterns
"""
import os
import sys
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from collections import defaultdict

WORKSPACE = Path("/root/.hermes/profiles/ilma")
REPORTS_DIR = WORKSPACE / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

class FlowReporter:
    """
    Reports on workflow and task flows.
    Tracks execution patterns and generates insights.
    """
    
    def __init__(self):
        self.flows = []
        self.tasks = []
        self.events = []
        self.max_flows = 1000
    
    def start_flow(self, flow_id: str, flow_type: str, metadata: Dict = None) -> Dict:
        """Start tracking a new flow."""
        flow = {
            "flow_id": flow_id,
            "flow_type": flow_type,
            "status": "running",
            "started_at": datetime.now().isoformat(),
            "metadata": metadata or {},
            "steps": [],
            "completed_at": None,
            "duration_seconds": None
        }
        
        self.flows.append(flow)
        
        # Keep only recent flows
        if len(self.flows) > self.max_flows:
            self.flows = self.flows[-self.max_flows:]
        
        return flow
    
    def add_step(self, flow_id: str, step_name: str, step_data: Dict = None) -> Dict:
        """Add a step to a flow."""
        step = {
            "step_name": step_name,
            "started_at": datetime.now().isoformat(),
            "data": step_data or {},
            "completed_at": None,
            "duration_ms": None
        }
        
        # Find flow
        for flow in reversed(self.flows):
            if flow["flow_id"] == flow_id:
                flow["steps"].append(step)
                break
        
        return step
    
    def complete_flow(self, flow_id: str, result: Dict = None) -> Dict:
        """Mark a flow as completed."""
        for flow in self.flows:
            if flow["flow_id"] == flow_id:
                flow["status"] = "completed"
                flow["completed_at"] = datetime.now().isoformat()
                
                # Calculate duration
                start = datetime.fromisoformat(flow["started_at"])
                end = datetime.fromisoformat(flow["completed_at"])
                flow["duration_seconds"] = (end - start).total_seconds()
                
                if result:
                    flow["result"] = result
                
                break
        
        return self.get_flow(flow_id)
    
    def fail_flow(self, flow_id: str, error: str) -> Dict:
        """Mark a flow as failed."""
        for flow in self.flows:
            if flow["flow_id"] == flow_id:
                flow["status"] = "failed"
                flow["completed_at"] = datetime.now().isoformat()
                flow["error"] = error
                
                start = datetime.fromisoformat(flow["started_at"])
                end = datetime.fromisoformat(flow["completed_at"])
                flow["duration_seconds"] = (end - start).total_seconds()
                
                break
        
        return self.get_flow(flow_id)
    
    def get_flow(self, flow_id: str) -> Optional[Dict]:
        """Get a flow by ID."""
        for flow in self.flows:
            if flow["flow_id"] == flow_id:
                return flow
        return None
    
    def get_active_flows(self) -> List[Dict]:
        """Get all running flows."""
        return [f for f in self.flows if f["status"] == "running"]
    
    def get_flow_stats(self) -> Dict:
        """Get flow statistics."""
        total = len(self.flows)
        completed = sum(1 for f in self.flows if f["status"] == "completed")
        failed = sum(1 for f in self.flows if f["status"] == "failed")
        running = sum(1 for f in self.flows if f["status"] == "running")
        
        # Calculate avg duration
        durations = [f["duration_seconds"] for f in self.flows 
                     if f["duration_seconds"] is not None]
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        # Count by type
        by_type = defaultdict(int)
        for f in self.flows:
            by_type[f["flow_type"]] += 1
        
        return {
            "total_flows": total,
            "completed": completed,
            "failed": failed,
            "running": running,
            "success_rate": completed / total if total > 0 else 0,
            "avg_duration_seconds": avg_duration,
            "by_type": dict(by_type)
        }
    
    def add_task(self, task_id: str, task_type: str, priority: str = "normal") -> Dict:
        """Add a task to track."""
        task = {
            "task_id": task_id,
            "task_type": task_type,
            "priority": priority,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "started_at": None,
            "completed_at": None
        }
        
        self.tasks.append(task)
        return task
    
    def start_task(self, task_id: str) -> Dict:
        """Start a task."""
        for task in self.tasks:
            if task["task_id"] == task_id:
                task["status"] = "running"
                task["started_at"] = datetime.now().isoformat()
                break
        
        return self.get_task(task_id)
    
    def complete_task(self, task_id: str, result: Dict = None) -> Dict:
        """Complete a task."""
        for task in self.tasks:
            if task["task_id"] == task_id:
                task["status"] = "completed"
                task["completed_at"] = datetime.now().isoformat()
                if result:
                    task["result"] = result
                break
        
        return self.get_task(task_id)
    
    def get_task(self, task_id: str) -> Optional[Dict]:
        """Get a task by ID."""
        for task in self.tasks:
            if task["task_id"] == task_id:
                return task
        return None
    
    def get_task_stats(self) -> Dict:
        """Get task statistics."""
        total = len(self.tasks)
        pending = sum(1 for t in self.tasks if t["status"] == "pending")
        running = sum(1 for t in self.tasks if t["status"] == "running")
        completed = sum(1 for t in self.tasks if t["status"] == "completed")
        
        by_priority = defaultdict(int)
        for t in self.tasks:
            by_priority[t["priority"]] += 1
        
        return {
            "total_tasks": total,
            "pending": pending,
            "running": running,
            "completed": completed,
            "by_priority": dict(by_priority)
        }
    
    def add_event(self, event_type: str, event_data: Dict = None):
        """Add an event to the event log."""
        event = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "data": event_data or {}
        }
        
        self.events.append(event)
        
        # Keep only recent events
        if len(self.events) > 5000:
            self.events = self.events[-5000:]
    
    def get_events(self, event_type: str = None, limit: int = 100) -> List[Dict]:
        """Get events, optionally filtered by type."""
        events = self.events
        
        if event_type:
            events = [e for e in events if e["type"] == event_type]
        
        return events[-limit:]
    
    def generate_report(self) -> Dict:
        """Generate a comprehensive report."""
        flow_stats = self.get_flow_stats()
        task_stats = self.get_task_stats()
        
        # Recent events
        recent_events = self.events[-50:]
        
        # Active flows
        active_flows = self.get_active_flows()
        
        # Failed flows
        failed_flows = [f for f in self.flows if f["status"] == "failed"][-10:]
        
        report = {
            "generated_at": datetime.now().isoformat(),
            "flow_stats": flow_stats,
            "task_stats": task_stats,
            "recent_events_count": len(recent_events),
            "active_flows": len(active_flows),
            "failed_flows_recent": len(failed_flows)
        }
        
        return report
    
    def save_report(self, report_type: str = "flow") -> str:
        """Save a report to file."""
        if report_type == "flow":
            data = {
                "flows": self.flows,
                "flow_stats": self.get_flow_stats()
            }
        elif report_type == "task":
            data = {
                "tasks": self.tasks,
                "task_stats": self.get_task_stats()
            }
        else:
            data = self.generate_report()
        
        filename = f"{report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = REPORTS_DIR / filename
        
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
        
        return str(filepath)


# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="ILMA Flow Reporter")
    parser.add_argument("command", nargs="?", default="report",
                        choices=["report", "stats", "flows", "tasks", "events", "save"])
    parser.add_argument("--flow-id", type=str, help="Flow ID")
    parser.add_argument("--task-id", type=str, help="Task ID")
    parser.add_argument("--type", type=str, default="flow", help="Report type")
    parser.add_argument("--limit", type=int, default=20, help="Limit results")
    
    reporter = FlowReporter()
    args = parser.parse_args()
    
    if args.command == "report":
        report = reporter.generate_report()
        print(json.dumps(report, indent=2))
    
    elif args.command == "stats":
        flow_stats = reporter.get_flow_stats()
        task_stats = reporter.get_task_stats()
        print("Flow Stats:")
        print(json.dumps(flow_stats, indent=2))
        print("\nTask Stats:")
        print(json.dumps(task_stats, indent=2))
    
    elif args.command == "flows":
        if args.flow_id:
            flow = reporter.get_flow(args.flow_id)
            print(json.dumps(flow, indent=2))
        else:
            flows = reporter.flows[-args.limit:]
            print(f"Recent {len(flows)} flows:")
            for f in flows:
                print(f"  {f['flow_id']}: {f['flow_type']} ({f['status']})")
    
    elif args.command == "tasks":
        if args.task_id:
            task = reporter.get_task(args.task_id)
            print(json.dumps(task, indent=2))
        else:
            tasks = reporter.tasks[-args.limit:]
            print(f"Recent {len(tasks)} tasks:")
            for t in tasks:
                print(f"  {t['task_id']}: {t['task_type']} ({t['status']})")
    
    elif args.command == "events":
        events = reporter.get_events(limit=args.limit)
        print(f"Recent {len(events)} events:")
        for e in events:
            print(f"  [{e['timestamp']}] {e['type']}")
    
    elif args.command == "save":
        filepath = reporter.save_report(args.type)
        print(f"Report saved: {filepath}")

if __name__ == "__main__":
    main()
