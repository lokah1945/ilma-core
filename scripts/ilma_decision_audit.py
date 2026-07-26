#!/usr/bin/env python3
"""
ILMA Decision Audit v1.0
========================
Audit trail for ILMA decision-making process.

Based on: ILMA ILMA_decision_audit.py patterns
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
AUDIT_DIR = WORKSPACE / ".audit"
AUDIT_DIR.mkdir(parents=True, exist_ok=True)


class DecisionAudit:
    """
    Audit trail for all ILMA decisions.
    Tracks decision context, reasoning, and outcomes.
    """
    
    def __init__(self):
        self.decisions = []
        self.max_decisions = 1000
        self.load_audit()
    
    def load_audit(self):
        """Load audit from disk."""
        audit_file = AUDIT_DIR / "decisions.json"
        if audit_file.exists():
            try:
                with open(audit_file) as f:
                    self.decisions = json.load(f)
            except ValueError:
                self.decisions = []
    
    def save_audit(self):
        """Save audit to disk."""
        audit_file = AUDIT_DIR / "decisions.json"
        
        with open(audit_file, "w") as f:
            json.dump(self.decisions[-self.max_decisions:], f, indent=2)
    
    def record_decision(self, decision: Dict) -> str:
        """Record a new decision."""
        decision_id = f"dec_{int(time.time() * 1000)}"
        
        entry = {
            "id": decision_id,
            "timestamp": datetime.now().isoformat(),
            "context": decision.get("context", {}),
            "options": decision.get("options", []),
            "selected_option": decision.get("selected_option"),
            "reasoning": decision.get("reasoning", ""),
            "outcome": decision.get("outcome"),
            "outcome_confidence": decision.get("outcome_confidence"),
            "reviewed": False,
            "tags": decision.get("tags", [])
        }
        
        self.decisions.append(entry)
        self.save_audit()
        
        return decision_id
    
    def get_decision(self, decision_id: str) -> Optional[Dict]:
        """Get a decision by ID."""
        for dec in reversed(self.decisions):
            if dec["id"] == decision_id:
                return dec
        return None
    
    def get_recent_decisions(self, limit: int = 50) -> List[Dict]:
        """Get recent decisions."""
        return self.decisions[-limit:]
    
    def get_decisions_by_context(self, context_key: str, context_value: Any) -> List[Dict]:
        """Get decisions matching a context value."""
        results = []
        for dec in self.decisions:
            if dec.get("context", {}).get(context_key) == context_value:
                results.append(dec)
        return results
    
    def get_decisions_by_outcome(self, outcome: str) -> List[Dict]:
        """Get decisions by outcome."""
        return [d for d in self.decisions if d.get("outcome") == outcome]
    
    def get_unreviewed_decisions(self) -> List[Dict]:
        """Get unreviewed decisions."""
        return [d for d in self.decisions if not d.get("reviewed")]
    
    def mark_reviewed(self, decision_id: str, rating: int = None) -> bool:
        """Mark a decision as reviewed."""
        for dec in self.decisions:
            if dec["id"] == decision_id:
                dec["reviewed"] = True
                if rating is not None:
                    dec["rating"] = rating
                self.save_audit()
                return True
        return False
    
    def update_outcome(self, decision_id: str, outcome: str, confidence: float = None) -> bool:
        """Update the outcome of a decision."""
        for dec in self.decisions:
            if dec["id"] == decision_id:
                dec["outcome"] = outcome
                if confidence is not None:
                    dec["outcome_confidence"] = confidence
                self.save_audit()
                return True
        return False
    
    def analyze_patterns(self) -> Dict:
        """Analyze decision patterns."""
        total = len(self.decisions)
        if total == 0:
            return {"error": "No decisions to analyze"}
        
        # Count by outcome
        outcomes = defaultdict(int)
        for dec in self.decisions:
            outcome = dec.get("outcome", "unknown")
            outcomes[outcome] += 1
        
        # Count by context
        contexts = defaultdict(int)
        for dec in self.decisions:
            ctx = dec.get("context", {}).get("type", "unknown")
            contexts[ctx] += 1
        
        # Review rate
        reviewed = sum(1 for d in self.decisions if d.get("reviewed"))
        
        # Average confidence
        confidences = [d.get("outcome_confidence", 0) for d in self.decisions 
                      if d.get("outcome_confidence") is not None]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        
        # Success rate (for decisions with known outcomes)
        success = sum(1 for d in self.decisions if d.get("outcome") == "success")
        success_rate = success / total if total > 0 else 0
        
        return {
            "total_decisions": total,
            "by_outcome": dict(outcomes),
            "by_context": dict(contexts),
            "review_rate": reviewed / total if total > 0 else 0,
            "avg_confidence": avg_confidence,
            "success_rate": success_rate,
            "unreviewed_count": len(self.get_unreviewed_decisions())
        }
    
    def get_statistics(self) -> Dict:
        """Get comprehensive statistics."""
        total = len(self.decisions)
        
        if total == 0:
            return {"total": 0, "message": "No decisions recorded"}
        
        # Outcome distribution
        outcomes = defaultdict(int)
        for dec in self.decisions:
            outcomes[dec.get("outcome", "none")] += 1
        
        # Context types
        context_types = defaultdict(int)
        for dec in self.decisions:
            ctx = dec.get("context", {}).get("type", "unknown")
            context_types[ctx] += 1
        
        # Recent trend
        recent = self.decisions[-100:]
        recent_success = sum(1 for d in recent if d.get("outcome") == "success")
        
        return {
            "total": total,
            "outcomes": dict(outcomes),
            "context_types": dict(context_types),
            "recent_success_rate": recent_success / len(recent) if recent else 0,
            "unreviewed": len(self.get_unreviewed_decisions())
        }
    
    def export_audit(self, format: str = "json") -> str:
        """Export audit trail."""
        if format == "json":
            export_file = AUDIT_DIR / f"audit_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(export_file, "w") as f:
                json.dump(self.decisions, f, indent=2)
            return str(export_file)
        
        elif format == "csv":
            export_file = AUDIT_DIR / f"audit_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            with open(export_file, "w") as f:
                f.write("id,timestamp,context_type,selected_option,outcome,reviewed\n")
                for d in self.decisions:
                    ctx_type = d.get("context", {}).get("type", "")
                    f.write(f"{d['id']},{d['timestamp']},{ctx_type},{d.get('selected_option','')},{d.get('outcome','')},{d.get('reviewed', False)}\n")
            return str(export_file)
        
        return ""


# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="ILMA Decision Audit")
    parser.add_argument("command", nargs="?", default="stats",
                        choices=["record", "get", "recent", "unreviewed", "patterns", "stats", "export", "mark", "update"])
    parser.add_argument("--id", type=str, help="Decision ID")
    parser.add_argument("--context", type=str, help="Context type")
    parser.add_argument("--option", type=str, help="Selected option")
    parser.add_argument("--reasoning", type=str, help="Decision reasoning")
    parser.add_argument("--outcome", type=str, help="Outcome")
    parser.add_argument("--confidence", type=float, help="Outcome confidence")
    parser.add_argument("--rating", type=int, help="Review rating")
    parser.add_argument("--format", type=str, default="json", help="Export format")
    parser.add_argument("--limit", type=int, default=20, help="Result limit")
    
    audit = DecisionAudit()
    args = parser.parse_args()
    
    if args.command == "record":
        decision = {
            "context": {"type": args.context or "general"},
            "options": [],
            "selected_option": args.option,
            "reasoning": args.reasoning or "",
            "outcome": args.outcome,
            "outcome_confidence": args.confidence
        }
        
        decision_id = audit.record_decision(decision)
        print(f"Decision recorded: {decision_id}")
    
    elif args.command == "get":
        if not args.id:
            print("Error: --id required")
            sys.exit(1)
        
        decision = audit.get_decision(args.id)
        if decision:
            print(json.dumps(decision, indent=2))
        else:
            print(f"Decision not found: {args.id}")
    
    elif args.command == "recent":
        recent = audit.get_recent_decisions(args.limit)
        print(f"Recent {len(recent)} decisions:")
        for d in recent:
            print(f"  [{d['id']}] {d['timestamp']} - {d.get('selected_option', 'N/A')} -> {d.get('outcome', 'N/A')}")
    
    elif args.command == "unreviewed":
        unreviewed = audit.get_unreviewed_decisions()
        print(f"Unreviewed decisions: {len(unreviewed)}")
        for d in unreviewed[:args.limit]:
            print(f"  [{d['id']}] {d['timestamp']} - {d.get('reasoning', '')[:50]}...")
    
    elif args.command == "patterns":
        patterns = audit.analyze_patterns()
        print(json.dumps(patterns, indent=2))
    
    elif args.command == "stats":
        stats = audit.get_statistics()
        print(json.dumps(stats, indent=2))
    
    elif args.command == "export":
        filepath = audit.export_audit(args.format)
        print(f"Audit exported: {filepath}")
    
    elif args.command == "mark":
        if not args.id:
            print("Error: --id required")
            sys.exit(1)
        
        if audit.mark_reviewed(args.id, args.rating):
            print(f"Decision marked as reviewed: {args.id}")
        else:
            print(f"Decision not found: {args.id}")
    
    elif args.command == "update":
        if not args.id or not args.outcome:
            print("Error: --id and --outcome required")
            sys.exit(1)
        
        if audit.update_outcome(args.id, args.outcome, args.confidence):
            print(f"Outcome updated: {args.id}")
        else:
            print(f"Decision not found: {args.id}")

if __name__ == "__main__":
    main()
